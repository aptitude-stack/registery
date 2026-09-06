# app.persistence.models module

SQLAlchemy ORM models mapped to Aptitude Registry tables.

## Purpose

Defines relational schema mappings used by persistence adapters and Alembic
migrations.

## Key Files

- `base.py`: declarative base class.
- `skill.py`: logical skill root table (`skills`).
- `skill_version.py`: immutable version metadata plus advisory provenance snapshot (`skill_versions`).
- `skill_content.py`: deduplicated opaque artifact storage (`skill_contents`).
- `skill_relationship_selector.py`: authored relationship selectors
  (`skill_relationship_selectors`).
- `skill_search_document.py`: denormalized advisory search documents (`skill_search_documents`)
  for compact candidate retrieval.
- Semantic embeddings and co-usage aggregates are migration-backed derived
  tables queried through raw SQL because pgvector `halfvec` operations and
  worker claim states are kept isolated to the semantic retrieval/indexing
  paths.
- `audit_event.py`: audit event table (`audit_events`).
- `__init__.py`: package exports.

## Notes

Keep model docs aligned with Alembic migrations and persistence adapter behavior.
