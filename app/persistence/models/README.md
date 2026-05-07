# app.persistence.models module

SQLAlchemy ORM models mapped to Aptitude Registry tables.

## Purpose

Defines relational schema mappings used by persistence adapters and Alembic
migrations.

## Key Files

- `base.py`: declarative base class.
- `skill.py`: logical skill root table (`skills`).
- `skill_version.py`: immutable version metadata plus advisory provenance snapshot (`skill_versions`).
- `skill_content.py`: canonical markdown storage (`skill_contents`).
- `skill_metadata.py`: normalized metadata storage (`skill_metadata`).
- `skill_relationship_selector.py`: authored relationship selectors
  (`skill_relationship_selectors`).
- `skill_search_document.py`: denormalized advisory search documents (`skill_search_documents`)
  for compact candidate retrieval.
- Semantic embeddings and co-usage aggregates are currently migration-backed
  derived tables queried through raw SQL because pgvector `halfvec` operations
  are kept isolated to the semantic retrieval path.
- `audit_event.py`: audit event table (`audit_events`).
- `__init__.py`: package exports.

## Notes

Keep model docs aligned with Alembic migrations and persistence adapter behavior.
