"""Rich demo catalog fixtures for local PostgreSQL seeding."""
# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.governance import (
    CallerIdentity,
    LifecycleStatus,
    ProvenanceMetadata,
    SkillGovernanceInput,
)
from app.core.skills.bundle_archive import SKILL_ARTIFACT_MEDIA_TYPE, build_skill_bundle
from app.core.skills.models import (
    CreateSkillVersionCommand,
    SkillContentInput,
    SkillMetadataInput,
    SkillRelationshipSelector,
    SkillRelationshipsInput,
)

_PUBLISHER_CALLER = CallerIdentity(
    token_id="demo-seed-publisher",
    scopes=frozenset({"read", "publish"}),
)
_ADMIN_CALLER = CallerIdentity(
    token_id="demo-seed-admin",
    scopes=frozenset({"read", "publish", "admin"}),
)


@dataclass(frozen=True, slots=True)
class DemoSeedEntry:
    """One immutable version to seed into the local demo catalog."""

    publish_caller: CallerIdentity
    command: CreateSkillVersionCommand
    desired_lifecycle_status: LifecycleStatus = "published"


def build_demo_catalog() -> tuple[DemoSeedEntry, ...]:
    """Return the fixed rich demo catalog used for local Docker seeding."""
    return (
        _entry(
            slug="python-base",
            version="1.0.0",
            name="Python Base Runtime",
            description="Foundational execution and environment setup patterns for Python skills.",
            tags=("python", "runtime", "base", "foundation"),
            trust_tier="internal",
            token_estimate=420,
            maturity_score=0.86,
            security_score=0.92,
            publisher_identity="ci/demo-runtime",
            content=_markdown(
                title="Python Base Runtime",
                purpose=(
                    "Provide a stable baseline for Python-oriented skills: interpreter setup, "
                    "virtualenv handling, dependency sync with uv, logging defaults, and shared "
                    "environment assumptions."
                ),
                when_to_use=(
                    "Use this when a downstream skill needs a predictable Python toolchain, "
                    "dependency installation, or standard shell/bootstrap steps before doing "
                    "linting, formatting, testing, or security scanning."
                ),
                prerequisites=(
                    "- Python 3.12+\n"
                    "- `uv` available on PATH\n"
                    "- Repository checkout present\n"
                    "- Network access only when dependency sync is required"
                ),
                inputs=(
                    "- `project_root`: absolute path to the repository\n"
                    "- `python_version`: desired interpreter family\n"
                    "- `install_dev_dependencies`: boolean toggle for extra tooling"
                ),
                outputs=(
                    "- Resolved virtual environment path\n"
                    "- Dependency installation summary\n"
                    "- Normalized runtime assumptions for child skills"
                ),
                steps=(
                    "1. Inspect the repository for `pyproject.toml`, `uv.lock`, and any local env files.\n"
                    "2. Ensure the requested Python version is compatible with the project metadata.\n"
                    "3. Create or reuse the local virtual environment with `uv venv` when needed.\n"
                    "4. Install base or dev dependencies with `uv sync`, preferring lockfile fidelity.\n"
                    "5. Export runtime details such as interpreter path, package roots, and env vars.\n"
                    "6. Return a concise execution summary that downstream skills can trust."
                ),
                examples=(
                    "- Bootstrap a fresh checkout before running lint/test skills.\n"
                    "- Standardize CI worker setup for Python repositories.\n"
                    "- Recreate local dev environments after dependency graph changes."
                ),
                failure_modes=(
                    "- Missing `pyproject.toml` or broken lockfiles prevent deterministic setup.\n"
                    "- Interpreter mismatches can yield confusing import or ABI failures.\n"
                    "- Partial installs leave child skills with inconsistent tooling assumptions."
                ),
                version_notes=(
                    "- `1.0.0`: initial baseline covering uv-based environment setup and shared runtime rules."
                ),
            ),
        ),
        _entry(
            slug="python-base",
            version="1.1.0",
            name="Python Base Runtime",
            description="Foundational Python environment setup with stronger CI and cache guidance.",
            tags=("python", "runtime", "base", "foundation", "ci"),
            trust_tier="internal",
            token_estimate=448,
            maturity_score=0.9,
            security_score=0.94,
            publisher_identity="ci/demo-runtime",
            content=_markdown(
                title="Python Base Runtime",
                purpose=(
                    "Extend the Python runtime baseline with cache-aware CI guidance, stricter "
                    "tool verification, and safer dependency synchronization defaults."
                ),
                when_to_use=(
                    "Use this version when downstream automation needs repeatable CI behavior, "
                    "explicit cache handling, and cleaner failure diagnostics than the earlier baseline."
                ),
                prerequisites=(
                    "- Python 3.12+\n"
                    "- `uv` and POSIX shell utilities available\n"
                    "- Writable cache directory such as `.uv-cache`\n"
                    "- Project lockfile committed and current"
                ),
                inputs=(
                    "- `project_root`\n"
                    "- `cache_dir`\n"
                    "- `sync_mode`: `locked` or `refresh`\n"
                    "- `ci`: whether execution is local or CI-driven"
                ),
                outputs=(
                    "- Verified interpreter and venv\n"
                    "- Dependency sync report with cache policy\n"
                    "- Reusable runtime contract for dependent skills"
                ),
                steps=(
                    "1. Validate lockfile presence and confirm the requested sync mode.\n"
                    "2. Create the environment with `uv venv` if a compatible venv does not already exist.\n"
                    "3. Route package downloads through the configured cache directory.\n"
                    "4. Run `uv sync` with the minimum extras required by the caller.\n"
                    "5. Verify the environment by importing a lightweight dependency or checking `python --version`.\n"
                    "6. Emit normalized environment facts that dependent skills can consume directly."
                ),
                examples=(
                    "- Prepare a CI worker for lint, format, and test stages.\n"
                    "- Reuse `.uv-cache` in local Docker-based smoke tests.\n"
                    "- Normalize local and container execution paths for child skills."
                ),
                failure_modes=(
                    "- A stale lockfile can mask dependency drift until later stages fail.\n"
                    "- Reusing an incompatible venv leads to subtle version skew.\n"
                    "- Missing cache directories can slow pipelines or break sandbox assumptions."
                ),
                version_notes=(
                    "- `1.1.0`: adds cache-aware CI setup, explicit verification steps, and sharper diagnostics."
                ),
            ),
        ),
        _entry(
            slug="python-lint",
            version="1.0.0",
            name="Python Lint",
            description="Legacy lint workflow for Python repositories using older rule baselines.",
            tags=("python", "lint", "quality", "legacy"),
            trust_tier="internal",
            token_estimate=540,
            maturity_score=0.73,
            security_score=0.84,
            publisher_identity="ci/demo-quality",
            desired_lifecycle_status="deprecated",
            depends_on=(_dependency(slug="python-base", version_constraint=">=1.0.0,<2.0.0"),),
            extends=(_exact_relationship(slug="python-base", version="1.1.0"),),
            overlaps_with=(_exact_relationship(slug="python-format", version="2.0.0"),),
            content=_markdown(
                title="Python Lint",
                purpose=(
                    "Run a legacy lint workflow for Python repositories that still depend on an older "
                    "Ruff rule profile and transitional code-health conventions."
                ),
                when_to_use=(
                    "Use this only when maintaining repositories that have not yet migrated to the newer "
                    "quality baseline. It is deprecated and retained mainly to test lifecycle behavior."
                ),
                prerequisites=(
                    "- A bootstrapped Python runtime\n"
                    "- Ruff installed in the active environment\n"
                    "- A repository with Python sources and a stable rule configuration"
                ),
                inputs=(
                    "- `paths`: list of files or directories to lint\n"
                    "- `strict`: whether warnings should fail the run\n"
                    "- `report_format`: text or machine-readable summary"
                ),
                outputs=(
                    "- Lint finding summary\n"
                    "- Exit status aligned with the configured strictness\n"
                    "- Normalized issue buckets for downstream reporting"
                ),
                steps=(
                    "1. Resolve the Python environment and verify Ruff is available.\n"
                    "2. Expand the requested path set while excluding generated files.\n"
                    "3. Run Ruff with the legacy rule profile expected by transitional repositories.\n"
                    "4. Collapse findings into deterministic severity buckets.\n"
                    "5. Return both a human summary and machine-readable counts for automation."
                ),
                examples=(
                    "- Keep an older service lint-clean during a migration to stricter checks.\n"
                    "- Compare deprecated lint results against the newer `2.0.0` baseline.\n"
                    "- Feed finding counts into release-readiness dashboards."
                ),
                failure_modes=(
                    "- Running the legacy profile against new code can hide issues fixed by the newer baseline.\n"
                    "- Generated files in the path set create noisy results unless filtered.\n"
                    "- Mixed rule configurations cause inconsistent CI behavior across repos."
                ),
                version_notes=(
                    "- `1.0.0`: legacy lint baseline retained for deprecation and lifecycle-governance testing."
                ),
            ),
        ),
        _entry(
            slug="python-lint",
            version="2.0.0",
            name="Python Lint",
            description="Modern Ruff-based lint workflow for Python repositories.",
            tags=("python", "lint", "quality", "ruff"),
            trust_tier="internal",
            token_estimate=588,
            maturity_score=0.93,
            security_score=0.95,
            publisher_identity="ci/demo-quality",
            depends_on=(_dependency(slug="python-base", version_constraint=">=1.0.0,<2.0.0"),),
            extends=(_exact_relationship(slug="python-base", version="1.1.0"),),
            overlaps_with=(_exact_relationship(slug="python-format", version="2.0.0"),),
            content=_markdown(
                title="Python Lint",
                purpose=(
                    "Lint Python repositories with the current Ruff baseline, fast feedback loops, and "
                    "clear finding normalization for CI and local development."
                ),
                when_to_use=(
                    "Use this for day-to-day Python code-health checks, pre-merge validation, or as a "
                    "shared dependency in broader code-quality bundles."
                ),
                prerequisites=(
                    "- `python-base` runtime available\n"
                    "- Ruff installed via the repo toolchain\n"
                    "- Project rule configuration committed or intentionally inherited"
                ),
                inputs=(
                    "- `paths`\n"
                    "- `fix`: whether autofix is allowed\n"
                    "- `preview_rules`: whether experimental rules are enabled"
                ),
                outputs=(
                    "- Finding summary grouped by rule family\n"
                    "- Optional autofix report\n"
                    "- Deterministic exit status for CI gating"
                ),
                steps=(
                    "1. Verify the repository runtime and Ruff version match the expected baseline.\n"
                    "2. Normalize target paths and exclude vendored or generated content.\n"
                    "3. Run `ruff check` with the requested fix and preview settings.\n"
                    "4. Collect rule-level findings and aggregate them into stable categories.\n"
                    "5. Return an actionable summary for humans and machines."
                ),
                examples=(
                    "- Gate pull requests with a fast lint step.\n"
                    "- Run local pre-commit quality checks before formatting or testing.\n"
                    "- Provide reusable lint coverage inside a bundled quality workflow."
                ),
                failure_modes=(
                    "- Preview rules can destabilize CI if repos are not aligned on Ruff version.\n"
                    "- Autofix on generated or hand-crafted snapshots may cause noisy churn.\n"
                    "- Missing excludes can surface irrelevant findings from vendored code."
                ),
                version_notes=(
                    "- `2.0.0`: modern Ruff baseline with stronger categorization and CI-oriented defaults."
                ),
            ),
        ),
        _entry(
            slug="python-format",
            version="1.0.0",
            name="Python Format",
            description="Archived formatting workflow kept for exact-read and lifecycle testing.",
            tags=("python", "format", "quality", "archive"),
            trust_tier="internal",
            token_estimate=500,
            maturity_score=0.68,
            security_score=0.83,
            publisher_identity="ci/demo-quality",
            desired_lifecycle_status="archived",
            depends_on=(_dependency(slug="python-base", version="1.1.0"),),
            overlaps_with=(_exact_relationship(slug="python-lint", version="2.0.0"),),
            content=_markdown(
                title="Python Format",
                purpose=(
                    "Apply an older formatting workflow preserved only to exercise archived exact-read "
                    "behavior and historical skill-version listings."
                ),
                when_to_use=(
                    "Use this only for admin-only archived catalog validation. It should not be selected "
                    "for normal discovery or reader-facing exact fetches."
                ),
                prerequisites=(
                    "- Bootstrapped Python runtime\n"
                    "- Legacy formatter configuration\n"
                    "- Admin/operator context when exact archived reads are required"
                ),
                inputs=("- `paths`\n- `check_only`\n- `line_length`"),
                outputs=(
                    "- Formatting diff or check summary\n"
                    "- Exit code suitable for regression validation\n"
                    "- Archived historical behavior sample"
                ),
                steps=(
                    "1. Load the legacy formatting config and verify compatibility with the repo.\n"
                    "2. Resolve the requested path set.\n"
                    "3. Run the formatter in check or write mode.\n"
                    "4. Summarize touched files or pending formatting drift.\n"
                    "5. Preserve the results as historical reference data."
                ),
                examples=(
                    "- Validate admin-only archived reads through the API.\n"
                    "- Compare historical formatter output with the current version.\n"
                    "- Exercise lifecycle-aware list ordering for archived versions."
                ),
                failure_modes=(
                    "- Legacy formatter assumptions can drift badly from modern repositories.\n"
                    "- Archived content should not drive normal discovery or resolution decisions.\n"
                    "- Check/write mode confusion can make regression comparisons unreliable."
                ),
                version_notes=(
                    "- `1.0.0`: archived historical formatter retained for governance and exact-read tests."
                ),
            ),
        ),
        _entry(
            slug="python-format",
            version="2.0.0",
            name="Python Format",
            description="Current formatting workflow for Python repositories.",
            tags=("python", "format", "quality", "style"),
            trust_tier="internal",
            token_estimate=552,
            maturity_score=0.91,
            security_score=0.94,
            publisher_identity="ci/demo-quality",
            depends_on=(_dependency(slug="python-base", version="1.1.0"),),
            overlaps_with=(_exact_relationship(slug="python-lint", version="2.0.0"),),
            content=_markdown(
                title="Python Format",
                purpose=(
                    "Format Python repositories with the current style baseline and deterministic "
                    "reporting for local development and CI."
                ),
                when_to_use=(
                    "Use this when code style should be normalized before linting, testing, or packaging, "
                    "or when a bundle needs explicit formatting coverage."
                ),
                prerequisites=(
                    "- `python-base` runtime available\n"
                    "- Active formatter configuration such as Ruff format or Black-compatible rules\n"
                    "- Write permissions when not running in check mode"
                ),
                inputs=("- `paths`\n- `check_only`\n- `respect_gitignore`"),
                outputs=(
                    "- Files changed or pending drift summary\n"
                    "- Stable style baseline for downstream lint/test stages\n"
                    "- Optional machine-readable drift counts"
                ),
                steps=(
                    "1. Resolve the formatter binary and confirm configuration compatibility.\n"
                    "2. Expand the target path set while honoring ignores.\n"
                    "3. Run the formatter in check or write mode.\n"
                    "4. Aggregate changed files and style drift counts.\n"
                    "5. Return a concise summary that downstream jobs can consume."
                ),
                examples=(
                    "- Enforce clean formatting before `python-lint`.\n"
                    "- Normalize style in local development before pushing a branch.\n"
                    "- Provide reusable formatting capability inside a code-quality bundle."
                ),
                failure_modes=(
                    "- Running write mode on generated snapshots can produce noisy diffs.\n"
                    "- Ignoring gitignore rules may touch vendored content unexpectedly.\n"
                    "- Formatter drift without lint alignment can confuse developers."
                ),
                version_notes=(
                    "- `2.0.0`: current formatting baseline designed for repeatable local and CI runs."
                ),
            ),
        ),
        _entry(
            slug="python-test",
            version="1.0.0",
            name="Python Test",
            description="Verified pytest execution workflow for Python services and libraries.",
            tags=("python", "test", "pytest", "verified"),
            trust_tier="verified",
            token_estimate=640,
            maturity_score=0.95,
            security_score=0.98,
            publisher_identity="release/demo-verified",
            depends_on=(
                _dependency(slug="python-base", version="1.1.0"),
                _dependency(
                    slug="python-lint",
                    version_constraint=">=2.0.0,<3.0.0",
                    optional=True,
                    markers=("ci", "linux"),
                ),
            ),
            content=_markdown(
                title="Python Test",
                purpose=(
                    "Run verified pytest-based test suites with environment normalization, selective "
                    "targeting, and explicit output capture appropriate for production-grade automation."
                ),
                when_to_use=(
                    "Use this when a repository needs trusted test execution behavior, especially in CI "
                    "pipelines or smoke-test stacks that rely on verified catalog entries."
                ),
                prerequisites=(
                    "- Verified or internal Python runtime baseline\n"
                    "- pytest installed through project tooling\n"
                    "- Optional lint coverage available when running CI on Linux"
                ),
                inputs=("- `test_targets`\n- `extra_pytest_args`\n- `ci_mode`\n- `max_failures`"),
                outputs=(
                    "- Pass/fail summary\n"
                    "- Test duration and target coverage stats\n"
                    "- Structured failure excerpts for triage"
                ),
                steps=(
                    "1. Verify the runtime and pytest entrypoint.\n"
                    "2. Expand requested test targets and confirm they exist.\n"
                    "3. Optionally run the lint prerequisite in CI/Linux contexts when configured.\n"
                    "4. Execute pytest with stable output settings and any requested flags.\n"
                    "5. Summarize pass/fail counts, runtime, and key failure excerpts."
                ),
                examples=(
                    "- Run integration tests before publishing a Python service image.\n"
                    "- Execute a focused regression suite during a smoke test.\n"
                    "- Feed verified test execution into a broader code-quality bundle."
                ),
                failure_modes=(
                    "- Mis-scoped test targets lead to false confidence or empty runs.\n"
                    "- Optional prerequisites can create CI/local differences if not documented.\n"
                    "- Poor output normalization makes failures harder to interpret downstream."
                ),
                version_notes=(
                    "- `1.0.0`: verified pytest workflow with optional lint prerequisite markers for CI."
                ),
            ),
        ),
        _entry(
            slug="python-security-scan",
            version="1.0.0",
            name="Python Security Scan",
            description="Verified security scanning workflow for Python projects.",
            tags=("python", "security", "scan", "verified"),
            trust_tier="verified",
            token_estimate=690,
            maturity_score=0.94,
            security_score=0.99,
            publisher_identity="release/demo-security",
            depends_on=(_dependency(slug="python-test", version_constraint=">=1.0.0,<2.0.0"),),
            conflicts_with=(_exact_relationship(slug="python-legacy-audit", version="0.9.0"),),
            content=_markdown(
                title="Python Security Scan",
                purpose=(
                    "Perform trusted dependency and static security checks for Python projects with "
                    "repeatable reporting that can gate release decisions."
                ),
                when_to_use=(
                    "Use this before releases, during security review, or inside demo environments "
                    "that need a verified skill with conflict metadata and trusted provenance."
                ),
                prerequisites=(
                    "- Verified test workflow available\n"
                    "- Security tooling installed in the runtime\n"
                    "- Repository dependency manifests present and current"
                ),
                inputs=(
                    "- `paths`\n- `dependency_manifests`\n- `severity_threshold`\n- `report_format`"
                ),
                outputs=(
                    "- Vulnerability and misconfiguration summary\n"
                    "- Threshold-aware pass/fail result\n"
                    "- Structured evidence for release or remediation decisions"
                ),
                steps=(
                    "1. Confirm the test prerequisite has already validated baseline project health.\n"
                    "2. Resolve dependency manifests and scan targets.\n"
                    "3. Run security tools against dependencies and relevant source paths.\n"
                    "4. Normalize findings by severity and category.\n"
                    "5. Return a release-oriented report with clear remediation guidance."
                ),
                examples=(
                    "- Gate a release candidate on dependency vulnerability thresholds.\n"
                    "- Produce a trusted security summary for an internal change review.\n"
                    "- Exercise conflict metadata against the legacy audit skill."
                ),
                failure_modes=(
                    "- Stale manifests can underreport real dependency risk.\n"
                    "- Tool version drift changes severity baselines unexpectedly.\n"
                    "- Mixing this with the legacy audit workflow produces overlapping or conflicting advice."
                ),
                version_notes=(
                    "- `1.0.0`: verified release-grade security scan with explicit conflict metadata."
                ),
            ),
        ),
        _entry(
            slug="python-legacy-audit",
            version="0.9.0",
            name="Python Legacy Audit",
            description="Deprecated untrusted audit workflow retained for compatibility testing.",
            tags=("python", "security", "legacy", "audit"),
            trust_tier="untrusted",
            token_estimate=470,
            maturity_score=0.51,
            security_score=0.58,
            publisher_identity="community/demo-legacy",
            desired_lifecycle_status="deprecated",
            overlaps_with=(_exact_relationship(slug="python-security-scan", version="1.0.0"),),
            content=_markdown(
                title="Python Legacy Audit",
                purpose=(
                    "Preserve an older, lower-trust security audit workflow so the registry can exercise "
                    "deprecated untrusted entries and overlap metadata."
                ),
                when_to_use=(
                    "Use this only for compatibility and governance tests. It should not be preferred over "
                    "the verified `python-security-scan` workflow."
                ),
                prerequisites=(
                    "- Python runtime available\n"
                    "- Historical audit scripts or scanners\n"
                    "- Awareness that outputs are advisory and lower trust"
                ),
                inputs=("- `manifest_paths`\n- `source_paths`\n- `legacy_policy_mode`"),
                outputs=(
                    "- Advisory audit report\n"
                    "- Deprecated historical findings snapshot\n"
                    "- Registry data to validate deprecated/untrusted visibility"
                ),
                steps=(
                    "1. Resolve historical audit tooling and manifests.\n"
                    "2. Run the legacy audit checks with compatibility settings.\n"
                    "3. Normalize findings into a simplified advisory report.\n"
                    "4. Mark outputs clearly as deprecated and low-trust.\n"
                    "5. Preserve the result for comparison against verified scans."
                ),
                examples=(
                    "- Validate list ordering between published and deprecated entries.\n"
                    "- Exercise overlap metadata against the verified security scan.\n"
                    "- Demonstrate how untrusted historical content remains fetchable when policy allows."
                ),
                failure_modes=(
                    "- Historical tooling may produce stale or misleading recommendations.\n"
                    "- Low-trust results can be misread as release-ready guidance.\n"
                    "- Deprecated workflows tend to drift from current dependency ecosystems."
                ),
                version_notes=(
                    "- `0.9.0`: deprecated historical audit retained for compatibility and governance validation."
                ),
            ),
        ),
        _entry(
            slug="documentation-writing",
            version="1.0.0",
            name="Documentation Writing",
            description="Internal workflow for writing documentation, docs, guides, and API references.",
            tags=("documentation", "docs", "writing", "guides", "reference"),
            trust_tier="internal",
            token_estimate=520,
            maturity_score=0.9,
            security_score=0.93,
            publisher_identity="ci/demo-documentation",
            content=_markdown(
                title="Documentation Writing",
                purpose=(
                    "Write clear technical documentation for projects, APIs, workflows, and operational "
                    "guides while keeping structure, audience, and maintenance needs explicit."
                ),
                when_to_use=(
                    "Use this when a user asks for docs, documentation, guides, references, tutorials, "
                    "or other written technical material that should be easy to scan and maintain."
                ),
                prerequisites=(
                    "- Source material or repository context available\n"
                    "- Target audience and document purpose understood\n"
                    "- Existing docs conventions reviewed when present"
                ),
                inputs=("- `topic`\n- `audience`\n- `source_paths`\n- `document_type`"),
                outputs=(
                    "- Draft or revised documentation\n"
                    "- Clear section structure\n"
                    "- Notes on assumptions and follow-up source gaps"
                ),
                steps=(
                    "1. Identify the reader goal and choose the appropriate documentation shape.\n"
                    "2. Gather relevant source material from code, examples, and existing docs.\n"
                    "3. Draft concise sections with accurate commands, paths, and examples.\n"
                    "4. Remove stale or redundant wording while preserving public contracts.\n"
                    "5. Return the updated document and verification notes."
                ),
                examples=(
                    "- Write an API usage guide from endpoint tests.\n"
                    "- Clean up a contributor reference after runtime changes.\n"
                    "- Add operator documentation for a new deployment setting."
                ),
                failure_modes=(
                    "- Writing from incomplete source context can create inaccurate guarantees.\n"
                    "- Mixing tutorials and references makes docs harder to maintain.\n"
                    "- Unverified commands or examples drift quickly from the implementation."
                ),
                version_notes=(
                    "- `1.0.0`: initial documentation-writing workflow for docs, guides, and references."
                ),
            ),
        ),
        _entry(
            slug="python-bundle-code-quality",
            version="1.0.0",
            name="Python Code Quality Bundle",
            description="Composite internal quality workflow that combines lint, format, and test coverage.",
            tags=("python", "bundle", "quality", "automation"),
            trust_tier="internal",
            token_estimate=760,
            maturity_score=0.92,
            security_score=0.96,
            publisher_identity="ci/demo-bundles",
            depends_on=(
                _dependency(slug="python-lint", version="2.0.0"),
                _dependency(slug="python-format", version="2.0.0"),
                _dependency(slug="python-test", version_constraint=">=1.0.0,<2.0.0"),
            ),
            extends=(_exact_relationship(slug="python-base", version="1.1.0"),),
            content=_markdown(
                title="Python Code Quality Bundle",
                purpose=(
                    "Provide a single orchestration-oriented skill that chains formatting, linting, and "
                    "verified testing into a coherent quality gate for Python repositories."
                ),
                when_to_use=(
                    "Use this when local Docker demos, smoke tests, or automation flows need a richer "
                    "dependency graph than a single skill can provide."
                ),
                prerequisites=(
                    "- Current Python runtime baseline\n"
                    "- Published `python-lint`, `python-format`, and `python-test` skills available\n"
                    "- Repository targets suitable for a full quality pass"
                ),
                inputs=(
                    "- `paths`\n- `test_targets`\n- `fix_formatting`\n- `stop_on_first_failure`"
                ),
                outputs=(
                    "- Combined quality gate result\n"
                    "- Per-stage summaries for format, lint, and test phases\n"
                    "- Execution order and dependency evidence for troubleshooting"
                ),
                steps=(
                    "1. Resolve the shared runtime and validate required dependent skills are present.\n"
                    "2. Run formatting first to normalize style drift.\n"
                    "3. Run linting against the normalized tree.\n"
                    "4. Execute verified tests against the resulting workspace state.\n"
                    "5. Aggregate outcomes into a bundle-level report with clear stage attribution."
                ),
                examples=(
                    "- Seed a realistic multi-skill graph for Docker demo stacks.\n"
                    "- Run a local pre-merge quality gate in one step.\n"
                    "- Validate dependency resolution and discovery ranking against a composite workflow."
                ),
                failure_modes=(
                    "- A single broken stage can hide useful signal from later stages unless reported clearly.\n"
                    "- Overly broad target sets make bundle runs expensive and noisy.\n"
                    "- Dependency drift across stages can produce misleading bundle summaries."
                ),
                version_notes=(
                    "- `1.0.0`: first bundled quality workflow combining current lint, format, and verified test skills."
                ),
            ),
        ),
    )


def _entry(
    *,
    slug: str,
    version: str,
    name: str,
    description: str,
    tags: tuple[str, ...],
    trust_tier: str,
    token_estimate: int,
    maturity_score: float,
    security_score: float,
    publisher_identity: str,
    content: str,
    desired_lifecycle_status: LifecycleStatus = "published",
    depends_on: tuple[SkillRelationshipSelector, ...] = (),
    extends: tuple[SkillRelationshipSelector, ...] = (),
    conflicts_with: tuple[SkillRelationshipSelector, ...] = (),
    overlaps_with: tuple[SkillRelationshipSelector, ...] = (),
) -> DemoSeedEntry:
    publish_caller = _ADMIN_CALLER if trust_tier == "verified" else _PUBLISHER_CALLER
    return DemoSeedEntry(
        publish_caller=publish_caller,
        desired_lifecycle_status=desired_lifecycle_status,
        command=CreateSkillVersionCommand(
            slug=slug,
            intent="create_skill" if version in {"1.0.0", "0.9.0"} else "publish_version",
            version=version,
            content=SkillContentInput(
                payload=_bundle_content(content),
                media_type=SKILL_ARTIFACT_MEDIA_TYPE,
            ),
            metadata=SkillMetadataInput(
                name=name,
                description=description,
                tags=tags,
                inputs_schema=_inputs_schema(slug),
                outputs_schema=_outputs_schema(slug),
                token_estimate=token_estimate,
                maturity_score=maturity_score,
                security_score=security_score,
            ),
            relationships=SkillRelationshipsInput(
                depends_on=depends_on,
                extends=extends,
                conflicts_with=conflicts_with,
                overlaps_with=overlaps_with,
            ),
            governance=SkillGovernanceInput(
                trust_tier=trust_tier,  # type: ignore[arg-type]
                provenance=_provenance(
                    slug=slug,
                    version=version,
                    publisher_identity=publisher_identity,
                ),
            ),
        ),
    )


def _dependency(
    *,
    slug: str,
    version: str | None = None,
    version_constraint: str | None = None,
    optional: bool | None = None,
    markers: tuple[str, ...] = (),
) -> SkillRelationshipSelector:
    return SkillRelationshipSelector(
        slug=slug,
        version=version,
        version_constraint=version_constraint,
        optional=optional,
        markers=markers,
    )


def _exact_relationship(*, slug: str, version: str) -> SkillRelationshipSelector:
    return SkillRelationshipSelector(slug=slug, version=version)


def _provenance(*, slug: str, version: str, publisher_identity: str) -> ProvenanceMetadata:
    digests = {
        ("python-base", "1.0.0"): "1111111111111111111111111111111111111111",
        ("python-base", "1.1.0"): "1111111111111111111111111111111111111112",
        ("python-lint", "1.0.0"): "2222222222222222222222222222222222222221",
        ("python-lint", "2.0.0"): "2222222222222222222222222222222222222222",
        ("python-format", "1.0.0"): "3333333333333333333333333333333333333331",
        ("python-format", "2.0.0"): "3333333333333333333333333333333333333332",
        ("python-test", "1.0.0"): "4444444444444444444444444444444444444444",
        ("python-security-scan", "1.0.0"): "5555555555555555555555555555555555555555",
        ("python-legacy-audit", "0.9.0"): "6666666666666666666666666666666666666666",
        ("documentation-writing", "1.0.0"): "8888888888888888888888888888888888888888",
        ("python-bundle-code-quality", "1.0.0"): "7777777777777777777777777777777777777777",
    }
    return ProvenanceMetadata(
        repo_url="https://github.com/example/aptitude-demo-skills",
        commit_sha=digests[(slug, version)],
        tree_path=f"skills/{slug}",
        publisher_identity=publisher_identity,
    )


def _inputs_schema(slug: str) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["project_root"],
        "properties": {
            "project_root": {"type": "string"},
            "paths": {"type": "array", "items": {"type": "string"}},
            "test_targets": {"type": "array", "items": {"type": "string"}},
            "mode": {"type": "string", "default": "standard"},
            "skill_slug": {"type": "string", "const": slug},
        },
    }


def _outputs_schema(slug: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "skill_slug": {"type": "string", "const": slug},
            "summary": {"type": "string"},
            "artifacts": {"type": "array", "items": {"type": "string"}},
            "metrics": {"type": "object"},
            "status": {"type": "string"},
        },
    }


def _markdown(
    *,
    title: str,
    purpose: str,
    when_to_use: str,
    prerequisites: str,
    inputs: str,
    outputs: str,
    steps: str,
    examples: str,
    failure_modes: str,
    version_notes: str,
) -> str:
    return f"""# {title}

## Purpose
{purpose}

This demo entry is intentionally rich enough to exercise exact content fetches, metadata storage,
search projection ranking, provenance rendering, and lifecycle-aware listings in the registry.

## When To Use
{when_to_use}

The primary goal of this authored skill document is to give local Docker and smoke-test environments a
non-trivial skill document with enough structure to validate content integrity, storage sizing,
and downstream rendering.

## Prerequisites
{prerequisites}

Each prerequisite is written as operator-facing guidance so the exact content endpoint can be
tested with realistic documentation rather than placeholder filler text.

## Inputs
{inputs}

Input contracts are mirrored in the structured metadata schema, but the prose here is useful for
exact bundle reads and for validating that the registry stores comprehensive authored content.

## Outputs
{outputs}

Outputs are intentionally described in operational terms so discovery and exact metadata reads have
stronger descriptions to rank and return.

## Step-By-Step Flow
{steps}

The step sequence is verbose on purpose. It gives the demo catalog a realistic body size and helps
validate that the service can preserve meaningful long-form skill content in PostgreSQL.

## Examples
{examples}

These examples are written as concrete operator scenarios instead of generic placeholders so local
clients can inspect substantive content via exact fetches.

## Failure Modes
{failure_modes}

Failure mode sections are included in every demo skill to make the content useful for debugging and
to ensure the seeded catalog covers richer documentation patterns than a minimal happy-path sample.

## Version Notes
{version_notes}

Future demo updates should extend this section rather than rewriting history so version-to-version
differences remain easy to inspect through the immutable fetch APIs.
"""


def _bundle_content(markdown: str) -> bytes:
    return build_skill_bundle(markdown)
