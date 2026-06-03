"""Integration coverage for the canonical clean Alembic schema baseline."""

from __future__ import annotations

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.core.settings import reset_settings_cache
from app.main import create_app
from app.persistence.db import dispose_engine
from tests.integration.skill_endpoint_helpers import _publish, _request


@pytest.mark.integration
def test_migrations_upgrade_and_downgrade(clean_integration_database: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", clean_integration_database)

    command.downgrade(config, "base")
    command.upgrade(config, "head")

    upgraded_engine = create_engine(clean_integration_database)
    try:
        inspector = inspect(upgraded_engine)
        assert "audit_events" in inspector.get_table_names()
        assert "skills" in inspector.get_table_names()
        assert "organizations" in inspector.get_table_names()
        assert "namespaces" in inspector.get_table_names()
        assert "policy_packs" in inspector.get_table_names()
        assert "trust_evidence" in inspector.get_table_names()
        assert "skill_versions" in inspector.get_table_names()
        assert "skill_contents" in inspector.get_table_names()
        assert "skill_metadata" in inspector.get_table_names()
        assert "skill_relationship_selectors" in inspector.get_table_names()
        assert "skill_search_documents" in inspector.get_table_names()
        assert "skill_search_embeddings" in inspector.get_table_names()
        assert "skill_user_stars" in inspector.get_table_names()
        assert "skill_usage_observation_runs" in inspector.get_table_names()
        assert "skill_usage_observations" in inspector.get_table_names()
        assert "skill_co_usage_pairs" in inspector.get_table_names()
        assert "skill_dependencies" not in inspector.get_table_names()
        assert "skill_relationship_edges" not in inspector.get_table_names()
        assert "skill_version_checksums" not in inspector.get_table_names()
        user_star_columns = {column["name"] for column in inspector.get_columns("skill_user_stars")}

        skill_columns = {column["name"] for column in inspector.get_columns("skills")}
        metadata_columns = {column["name"] for column in inspector.get_columns("skill_metadata")}
        version_columns = {column["name"] for column in inspector.get_columns("skill_versions")}
        content_columns = {column["name"] for column in inspector.get_columns("skill_contents")}
        trust_columns = {column["name"] for column in inspector.get_columns("trust_evidence")}
        search_columns = {
            column["name"] for column in inspector.get_columns("skill_search_documents")
        }
        embedding_columns = {
            column["name"] for column in inspector.get_columns("skill_search_embeddings")
        }
        embedding_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspector.get_check_constraints("skill_search_embeddings")
        }
        co_usage_columns = {
            column["name"] for column in inspector.get_columns("skill_co_usage_pairs")
        }
        graph_edge_columns = {
            column["name"] for column in inspector.get_columns("skill_graph_edges")
        }
        graph_edge_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspector.get_check_constraints("skill_graph_edges")
        }

        assert {
            "slug",
            "install_count",
            "star_count",
            "namespace_fk",
            "created_at",
            "updated_at",
        } <= skill_columns
        assert "current_version_id" not in skill_columns
        assert {"user_subject", "skill_fk", "created_at"} <= user_star_columns

        assert {
            "lifecycle_status",
            "lifecycle_changed_at",
            "trust_tier",
            "artifact_origin",
            "review_state",
            "promotion_channel",
            "policy_pack_fk",
            "provenance_repo_url",
            "provenance_commit_sha",
            "provenance_tree_path",
            "provenance_publisher_identity",
            "policy_profile_at_publish",
        } <= version_columns
        assert "rendered_summary" not in content_columns
        assert "headers" not in metadata_columns

        assert {"evidence_type", "subject", "digest", "uri", "payload"} <= trust_columns

        assert {
            "namespace",
            "artifact_origin",
            "review_state",
            "promotion_channel",
            "policy_pack_slug",
            "lifecycle_status",
            "trust_tier",
        } <= search_columns
        assert {
            "skill_version_fk",
            "embedding_model",
            "embedding_dimensions",
            "source_checksum_digest",
            "embedding_vector",
            "index_status",
            "indexed_at",
            "last_error",
        } <= embedding_columns
        assert "processing" in embedding_checks["ck_skill_search_embeddings_index_status"]
        assert {
            "anchor_skill_fk",
            "related_skill_fk",
            "observation_count",
            "distinct_run_count",
            "co_usage_rate",
            "lift_score",
            "pmi_score",
            "window_days",
        } <= co_usage_columns
        assert {
            "source_skill_fk",
            "source_skill_version_fk",
            "target_skill_fk",
            "target_slug",
            "edge_type",
            "provenance",
            "active",
            "confidence",
            "evidence",
            "created_at",
            "updated_at",
        } <= graph_edge_columns
        assert "relates_to" in graph_edge_checks["ck_skill_graph_edges_edge_type"]
        assert "co_usage" in graph_edge_checks["ck_skill_graph_edges_provenance"]
        assert "authored" in graph_edge_checks["ck_skill_graph_edges_provenance"]
    finally:
        upgraded_engine.dispose()

    command.downgrade(config, "base")

    downgraded_engine = create_engine(clean_integration_database)
    try:
        inspector = inspect(downgraded_engine)
        assert "audit_events" not in inspector.get_table_names()
        assert "skills" not in inspector.get_table_names()
        assert "organizations" not in inspector.get_table_names()
        assert "namespaces" not in inspector.get_table_names()
        assert "policy_packs" not in inspector.get_table_names()
        assert "trust_evidence" not in inspector.get_table_names()
        assert "skill_versions" not in inspector.get_table_names()
        assert "skill_contents" not in inspector.get_table_names()
        assert "skill_metadata" not in inspector.get_table_names()
        assert "skill_relationship_selectors" not in inspector.get_table_names()
        assert "skill_search_documents" not in inspector.get_table_names()
        assert "skill_search_embeddings" not in inspector.get_table_names()
        assert "skill_user_stars" not in inspector.get_table_names()
        assert "skill_usage_observation_runs" not in inspector.get_table_names()
        assert "skill_usage_observations" not in inspector.get_table_names()
        assert "skill_co_usage_pairs" not in inspector.get_table_names()
        assert "skill_graph_edges" not in inspector.get_table_names()
    finally:
        downgraded_engine.dispose()


@pytest.mark.integration
def test_graph_projection_cleanup_migration_deactivates_stale_and_missing_edges(
    monkeypatch: pytest.MonkeyPatch,
    clean_integration_database: str,
) -> None:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", clean_integration_database)
    command.upgrade(config, "0009_skill_graph_edges")

    monkeypatch.setenv("DATABASE_URL", clean_integration_database)
    prefix = "migration-graph-cleanup"
    source = f"{prefix}-source"
    target = f"{prefix}-target"
    missing = f"{prefix}-missing"
    reset_settings_cache()
    dispose_engine()
    with TestClient(create_app()) as client:
        _publish(
            client,
            source,
            _request(
                "0.1.0",
                intent="create_skill",
                name="Cleanup Source",
                overlaps_with=[{"slug": target, "version": "0.1.0"}],
            ),
        )
        _publish(
            client,
            source,
            _request(
                "0.1.1",
                intent="publish_version",
                name="Cleanup Source",
                overlaps_with=[
                    {"slug": target, "version": "0.1.0"},
                    {"slug": missing, "version": "0.1.0"},
                ],
            ),
        )
        _publish(
            client,
            target,
            _request("0.1.0", intent="create_skill", name="Cleanup Target"),
        )
    reset_settings_cache()
    dispose_engine()

    command.upgrade(config, "head")

    engine = create_engine(clean_integration_database)
    try:
        with engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT
                            version.version AS source_version,
                            edge.target_slug,
                            edge.active,
                            edge.target_skill_fk IS NOT NULL AS target_fk_backfilled
                        FROM skill_graph_edges AS edge
                        JOIN skill_versions AS version
                            ON version.id = edge.source_skill_version_fk
                        JOIN skills AS source
                            ON source.id = edge.source_skill_fk
                        WHERE source.slug = :source
                        ORDER BY version.version, edge.target_slug
                        """
                    ),
                    {"source": source},
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()

    assert [
        (
            row["source_version"],
            row["target_slug"],
            row["active"],
            row["target_fk_backfilled"],
        )
        for row in rows
    ] == [
        ("0.1.0", target, False, True),
        ("0.1.1", missing, False, False),
        ("0.1.1", target, True, True),
    ]
