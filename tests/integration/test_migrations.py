"""Integration coverage for the canonical clean Alembic schema baseline."""

from __future__ import annotations

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

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
        assert "skill_versions" in inspector.get_table_names()
        assert "skill_contents" in inspector.get_table_names()
        assert "skill_metadata" in inspector.get_table_names()
        assert "skill_relationship_selectors" in inspector.get_table_names()
        assert "skill_search_documents" in inspector.get_table_names()
        assert "skill_dependencies" not in inspector.get_table_names()
        assert "skill_relationship_edges" not in inspector.get_table_names()
        assert "skill_version_checksums" not in inspector.get_table_names()

        skill_columns = {column["name"] for column in inspector.get_columns("skills")}
        version_columns = {column["name"] for column in inspector.get_columns("skill_versions")}
        content_columns = {column["name"] for column in inspector.get_columns("skill_contents")}
        search_columns = {
            column["name"] for column in inspector.get_columns("skill_search_documents")
        }

        assert {"slug", "install_count", "created_at", "updated_at"} <= skill_columns
        assert "current_version_id" not in skill_columns

        assert {
            "lifecycle_status",
            "lifecycle_changed_at",
            "trust_tier",
            "provenance_repo_url",
            "provenance_commit_sha",
            "provenance_tree_path",
            "provenance_publisher_identity",
            "policy_profile_at_publish",
        } <= version_columns
        assert "rendered_summary" not in content_columns

        assert {"lifecycle_status", "trust_tier"} <= search_columns
    finally:
        upgraded_engine.dispose()

    command.downgrade(config, "base")

    downgraded_engine = create_engine(clean_integration_database)
    try:
        inspector = inspect(downgraded_engine)
        assert "audit_events" not in inspector.get_table_names()
        assert "skills" not in inspector.get_table_names()
        assert "skill_versions" not in inspector.get_table_names()
        assert "skill_contents" not in inspector.get_table_names()
        assert "skill_metadata" not in inspector.get_table_names()
        assert "skill_relationship_selectors" not in inspector.get_table_names()
        assert "skill_search_documents" not in inspector.get_table_names()
    finally:
        downgraded_engine.dispose()
