"""Switch immutable content storage from markdown text to tar.zst bundles.

Revision ID: 0003_skill_bundle_storage
Revises: 0002_skill_install_counts
Create Date: 2026-04-12
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from collections import defaultdict
from io import BytesIO

import sqlalchemy as sa
import zstandard

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_skill_bundle_storage"
down_revision = "0002_skill_install_counts"
branch_labels = None
depends_on = None

_MEDIA_TYPE = "application/zstd"
_SKILL_BUNDLE_MARKDOWN_PATH = "skill-bundle/SKILL.md"
_RELATIONSHIP_EDGE_ORDER = {
    "depends_on": 0,
    "extends": 1,
    "conflicts_with": 2,
    "overlaps_with": 3,
}


def upgrade() -> None:
    op.add_column("skill_contents", sa.Column("payload", sa.LargeBinary(), nullable=True))
    op.add_column("skill_contents", sa.Column("media_type", sa.Text(), nullable=True))

    connection = op.get_bind()
    content_rows = connection.execute(
        sa.text("SELECT id, raw_markdown FROM skill_contents ORDER BY id")
    ).mappings()
    for row in content_rows:
        bundle_bytes = _bundle_markdown(str(row["raw_markdown"]))
        connection.execute(
            sa.text(
                """
                UPDATE skill_contents
                SET payload = :payload,
                    media_type = :media_type,
                    storage_size_bytes = :storage_size_bytes,
                    checksum_digest = :checksum_digest
                WHERE id = :content_id
                """
            ),
            {
                "content_id": row["id"],
                "payload": bundle_bytes,
                "media_type": _MEDIA_TYPE,
                "storage_size_bytes": len(bundle_bytes),
                "checksum_digest": _sha256(bundle_bytes),
            },
        )

    op.alter_column("skill_contents", "payload", nullable=False)
    op.alter_column("skill_contents", "media_type", nullable=False)

    _recompute_version_checksums(connection)

    connection.execute(
        sa.text(
            """
            UPDATE skill_search_documents AS doc
            SET content_size_bytes = content.storage_size_bytes
            FROM skill_versions AS version_row
            JOIN skill_contents AS content ON content.id = version_row.content_fk
            WHERE doc.skill_version_fk = version_row.id
            """
        )
    )

    op.drop_column("skill_contents", "raw_markdown")


def downgrade() -> None:
    op.add_column("skill_contents", sa.Column("raw_markdown", sa.Text(), nullable=True))

    connection = op.get_bind()
    content_rows = connection.execute(
        sa.text("SELECT id, payload FROM skill_contents ORDER BY id")
    ).mappings()
    for row in content_rows:
        markdown = _extract_skill_markdown(bytes(row["payload"]))
        connection.execute(
            sa.text(
                """
                UPDATE skill_contents
                SET raw_markdown = :raw_markdown,
                    storage_size_bytes = :storage_size_bytes,
                    checksum_digest = :checksum_digest
                WHERE id = :content_id
                """
            ),
            {
                "content_id": row["id"],
                "raw_markdown": markdown,
                "storage_size_bytes": len(markdown.encode("utf-8")),
                "checksum_digest": _sha256(markdown.encode("utf-8")),
            },
        )

    op.alter_column("skill_contents", "raw_markdown", nullable=False)
    op.drop_column("skill_contents", "media_type")
    op.drop_column("skill_contents", "payload")


def _recompute_version_checksums(connection: sa.Connection) -> None:
    selector_rows = connection.execute(
        sa.text(
            """
            SELECT
                source_skill_version_fk,
                edge_type,
                ordinal,
                target_slug,
                target_version,
                version_constraint,
                optional,
                markers
            FROM skill_relationship_selectors
            ORDER BY source_skill_version_fk, ordinal
            """
        )
    ).mappings()
    selectors_by_version: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in selector_rows:
        selectors_by_version[int(row["source_skill_version_fk"])].append(dict(row))

    version_rows = connection.execute(
        sa.text(
            """
            SELECT
                version_row.id,
                skills.slug,
                version_row.version,
                content.checksum_digest AS content_checksum_digest,
                metadata.name,
                metadata.description,
                metadata.tags,
                metadata.inputs_schema,
                metadata.outputs_schema,
                metadata.token_estimate,
                metadata.maturity_score,
                metadata.security_score,
                version_row.trust_tier,
                version_row.provenance_repo_url,
                version_row.provenance_commit_sha,
                version_row.provenance_tree_path,
                version_row.provenance_publisher_identity,
                version_row.policy_profile_at_publish
            FROM skill_versions AS version_row
            JOIN skills ON skills.id = version_row.skill_fk
            JOIN skill_contents AS content ON content.id = version_row.content_fk
            JOIN skill_metadata AS metadata ON metadata.id = version_row.metadata_fk
            ORDER BY version_row.id
            """
        )
    ).mappings()

    for row in version_rows:
        relationships = {
            "depends_on": [],
            "extends": [],
            "conflicts_with": [],
            "overlaps_with": [],
        }
        selectors = sorted(
            selectors_by_version.get(int(row["id"]), []),
            key=lambda item: (
                _RELATIONSHIP_EDGE_ORDER[str(item["edge_type"])],
                int(item["ordinal"]),
            ),
        )
        for item in selectors:
            relationships[str(item["edge_type"])].append(
                {
                    "slug": item["target_slug"],
                    "version": item["target_version"],
                    "version_constraint": item["version_constraint"],
                    "optional": item["optional"],
                    "markers": list(item["markers"] or []),
                }
            )

        payload = {
            "slug": row["slug"],
            "version": row["version"],
            "content_checksum_digest": row["content_checksum_digest"],
            "metadata": {
                "name": row["name"],
                "description": row["description"],
                "tags": list(row["tags"]),
                "inputs_schema": row["inputs_schema"],
                "outputs_schema": row["outputs_schema"],
                "token_estimate": row["token_estimate"],
                "maturity_score": row["maturity_score"],
                "security_score": row["security_score"],
            },
            "governance": {
                "trust_tier": row["trust_tier"],
                "provenance": (
                    None
                    if row["provenance_repo_url"] is None or row["provenance_commit_sha"] is None
                    else {
                        "repo_url": row["provenance_repo_url"],
                        "commit_sha": row["provenance_commit_sha"],
                        "tree_path": row["provenance_tree_path"],
                        "publisher_identity": row["provenance_publisher_identity"],
                        "policy_profile": row["policy_profile_at_publish"],
                    }
                ),
            },
            "relationships": relationships,
        }
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        connection.execute(
            sa.text("UPDATE skill_versions SET checksum_digest = :checksum_digest WHERE id = :id"),
            {"id": row["id"], "checksum_digest": _sha256(canonical_json)},
        )


def _bundle_markdown(markdown: str) -> bytes:
    tar_buffer = BytesIO()
    payload = markdown.encode("utf-8")
    with tarfile.open(fileobj=tar_buffer, mode="w") as archive:
        info = tarfile.TarInfo(_SKILL_BUNDLE_MARKDOWN_PATH)
        info.size = len(payload)
        info.mode = 0o644
        info.mtime = 0
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        archive.addfile(info, BytesIO(payload))

    compressor = zstandard.ZstdCompressor()
    return compressor.compress(tar_buffer.getvalue())


def _extract_skill_markdown(payload: bytes) -> str:
    with zstandard.ZstdDecompressor().stream_reader(BytesIO(payload)) as reader:
        with tarfile.open(fileobj=reader, mode="r|") as archive:
            for member in archive:
                if member.name == _SKILL_BUNDLE_MARKDOWN_PATH:
                    extracted = archive.extractfile(member)
                    if extracted is not None:
                        return extracted.read().decode("utf-8")
    raise RuntimeError("Could not locate SKILL.md while downgrading bundle storage.")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
