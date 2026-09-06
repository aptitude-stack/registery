"""Integration coverage for the canonical clean Alembic schema baseline."""

from __future__ import annotations

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


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
        assert "skill_metadata" not in inspector.get_table_names()
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
        metadata_columns = {column["name"] for column in inspector.get_columns("skill_versions")}
        assert "inputs_schema" not in metadata_columns
        assert "outputs_schema" not in metadata_columns
        metadata_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspector.get_check_constraints("skill_versions")
        }
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
        assert "overall_score" in metadata_columns
        assert "assessment" in metadata_columns
        assert "overall_score" in metadata_checks["ck_skill_versions_overall_score"]

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
            "distinct_run_count",
            "co_usage_rate",
            "lift_score",
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

    command.downgrade(config, "0011_overall_score")
    downgraded_migration_engine = create_engine(clean_integration_database)
    try:
        metadata_columns = {
            column["name"]: column
            for column in inspect(downgraded_migration_engine).get_columns("skill_metadata")
        }
        assert metadata_columns["inputs_schema"]["nullable"] is True
        assert metadata_columns["outputs_schema"]["nullable"] is True
    finally:
        downgraded_migration_engine.dispose()

    command.upgrade(config, "0013_db_structure_cleanup")
    pre_assessment_engine = create_engine(clean_integration_database)
    try:
        version_columns = {
            column["name"]
            for column in inspect(pre_assessment_engine).get_columns("skill_versions")
        }
        assert "assessment" not in version_columns
    finally:
        pre_assessment_engine.dispose()

    command.upgrade(config, "head")
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
def test_metadata_schema_removal_preserves_existing_checksums_and_bundles(
    clean_integration_database: str,
) -> None:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", clean_integration_database)
    command.upgrade(config, "0011_overall_score")

    engine = create_engine(clean_integration_database)
    try:
        with engine.begin() as connection:
            skill_id = connection.execute(
                text(
                    """
                    INSERT INTO skills (slug, namespace_fk)
                    SELECT :slug, id FROM namespaces WHERE slug = 'public'
                    RETURNING id
                    """
                ),
                {"slug": "migration-schema-removal"},
            ).scalar_one()
            content_id = connection.execute(
                text(
                    """
                    INSERT INTO skill_contents (
                        payload, media_type, storage_size_bytes, checksum_digest
                    )
                    VALUES (:payload, 'application/zstd', :size_bytes, :checksum)
                    RETURNING id
                    """
                ),
                {
                    "payload": b"existing-bundle-bytes",
                    "size_bytes": len(b"existing-bundle-bytes"),
                    "checksum": "1" * 64,
                },
            ).scalar_one()
            metadata_id = connection.execute(
                text(
                    """
                    INSERT INTO skill_metadata (
                        name, description, tags, inputs_schema, outputs_schema
                    )
                    VALUES (
                        'Migration fixture', 'Existing metadata', ARRAY['fixture']::text[],
                        '{"type":"object"}'::jsonb, '{"type":"string"}'::jsonb
                    )
                    RETURNING id
                    """
                )
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO skill_versions (
                        skill_fk, version, content_fk, metadata_fk, checksum_digest
                    )
                    VALUES (:skill_fk, '1.2.3', :content_fk, :metadata_fk, :checksum)
                    """
                ),
                {
                    "skill_fk": skill_id,
                    "content_fk": content_id,
                    "metadata_fk": metadata_id,
                    "checksum": "2" * 64,
                },
            )

        command.upgrade(config, "0012_remove_metadata_schemas")
        with engine.connect() as connection:
            preserved = (
                connection.execute(
                    text(
                        """
                    SELECT
                        version.checksum_digest AS version_checksum,
                        content.payload,
                        content.checksum_digest AS content_checksum
                    FROM skill_versions AS version
                    JOIN skill_contents AS content ON content.id = version.content_fk
                    WHERE version.version = '1.2.3'
                    """
                    )
                )
                .mappings()
                .one()
            )
            metadata_columns = {
                column["name"] for column in inspect(connection).get_columns("skill_metadata")
            }

        assert preserved == {
            "version_checksum": "2" * 64,
            "payload": b"existing-bundle-bytes",
            "content_checksum": "1" * 64,
        }
        assert {"inputs_schema", "outputs_schema"}.isdisjoint(metadata_columns)

        command.downgrade(config, "0011_overall_score")
        with engine.connect() as connection:
            restored = (
                connection.execute(
                    text(
                        """
                    SELECT
                        metadata.inputs_schema,
                        metadata.outputs_schema,
                        version.checksum_digest AS version_checksum,
                        content.payload,
                        content.checksum_digest AS content_checksum
                    FROM skill_versions AS version
                    JOIN skill_metadata AS metadata ON metadata.id = version.metadata_fk
                    JOIN skill_contents AS content ON content.id = version.content_fk
                    WHERE version.version = '1.2.3'
                    """
                    )
                )
                .mappings()
                .one()
            )

        assert restored["inputs_schema"] is None
        assert restored["outputs_schema"] is None
        assert restored["version_checksum"] == "2" * 64
        assert restored["payload"] == b"existing-bundle-bytes"
        assert restored["content_checksum"] == "1" * 64
    finally:
        engine.dispose()


@pytest.mark.integration
def test_graph_projection_cleanup_migration_deactivates_stale_and_missing_edges(
    clean_integration_database: str,
) -> None:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", clean_integration_database)
    command.upgrade(config, "0009_skill_graph_edges")

    prefix = "migration-graph-cleanup"
    source = f"{prefix}-source"
    target = f"{prefix}-target"
    missing = f"{prefix}-missing"
    _seed_graph_cleanup_rows(
        clean_integration_database,
        source=source,
        target=target,
        missing=missing,
    )

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


def _seed_graph_cleanup_rows(
    database_url: str,
    *,
    source: str,
    target: str,
    missing: str,
) -> None:
    """Seed the pre-0010 graph projection without using the current ORM schema."""
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            namespace_id = connection.execute(
                text("SELECT id FROM namespaces WHERE slug = 'public'")
            ).scalar_one()

            skill_ids: dict[str, int] = {}
            for slug in (source, target):
                skill_ids[slug] = int(
                    connection.execute(
                        text(
                            """
                            INSERT INTO skills (slug, namespace_fk)
                            VALUES (:slug, :namespace_id)
                            RETURNING id
                            """
                        ),
                        {"slug": slug, "namespace_id": namespace_id},
                    ).scalar_one()
                )

            version_ids: dict[tuple[str, str], int] = {}
            for slug, version, published_at in (
                (source, "0.1.0", "2026-01-01T09:00:00+00:00"),
                (source, "0.1.1", "2026-01-02T09:00:00+00:00"),
                (target, "0.1.0", "2026-01-01T09:00:00+00:00"),
            ):
                payload = f"legacy-{slug}-{version}".encode()
                content_id = connection.execute(
                    text(
                        """
                        INSERT INTO skill_contents (
                            payload,
                            media_type,
                            storage_size_bytes,
                            checksum_digest
                        )
                        VALUES (:payload, 'application/zstd', :size_bytes, :checksum)
                        RETURNING id
                        """
                    ),
                    {
                        "payload": payload,
                        "size_bytes": len(payload),
                        "checksum": f"{len(version_ids) + 1:064d}",
                    },
                ).scalar_one()
                metadata_id = connection.execute(
                    text(
                        """
                        INSERT INTO skill_metadata (name, description, tags)
                        VALUES (:name, :description, ARRAY['fixture']::text[])
                        RETURNING id
                        """
                    ),
                    {"name": slug, "description": "migration fixture"},
                ).scalar_one()
                version_ids[(slug, version)] = int(
                    connection.execute(
                        text(
                            """
                            INSERT INTO skill_versions (
                                skill_fk,
                                version,
                                content_fk,
                                metadata_fk,
                                checksum_digest,
                                published_at
                            )
                            VALUES (
                                :skill_id,
                                :version,
                                :content_id,
                                :metadata_id,
                                :checksum,
                                :published_at
                            )
                            RETURNING id
                            """
                        ),
                        {
                            "skill_id": skill_ids[slug],
                            "version": version,
                            "content_id": content_id,
                            "metadata_id": metadata_id,
                            "checksum": f"{len(version_ids) + 1:064d}",
                            "published_at": published_at,
                        },
                    ).scalar_one()
                )

            for version, target_slug in (
                ("0.1.0", target),
                ("0.1.1", target),
                ("0.1.1", missing),
            ):
                connection.execute(
                    text(
                        """
                        INSERT INTO skill_graph_edges (
                            source_skill_fk,
                            source_skill_version_fk,
                            target_slug,
                            edge_type,
                            provenance,
                            active
                        )
                        VALUES (
                            :source_skill_id,
                            :source_version_id,
                            :target_slug,
                            'overlaps_with',
                            'authored',
                            TRUE
                        )
                        """
                    ),
                    {
                        "source_skill_id": skill_ids[source],
                        "source_version_id": version_ids[(source, version)],
                        "target_slug": target_slug,
                    },
                )
    finally:
        engine.dispose()
