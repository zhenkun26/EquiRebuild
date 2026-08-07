# hardening-review Specification

## Purpose

Defines the behavior of the hardening-review Hermes skill: an adversarial production-grade review workflow (5 dimensions, P0/P1 grading, fixes, verification, deployment guidance) that runs against a target codebase without modifying the pristine upstream Hermes Agent clone.

## Requirements

### Requirement: Skill is a valid Hermes user skill
The skill SHALL ship as a Hermes user skill directory containing `SKILL.md`, `scripts/`, and `templates/`, with frontmatter fields `name`, `description` (single sentence, ≤60 characters), `version`, `author`, `license`, `platforms`, and `metadata.hermes.category` set to `security`. Installing the skill into `~/.hermes/skills/security/hardening-review/` SHALL NOT require any change to the `hermes-agent` clone.

#### Scenario: Skill bundle is complete
- **WHEN** the skill directory `hermes-skills/hardening-review/` is inspected
- **THEN** it contains `SKILL.md`, at least one script under `scripts/`, and a report template under `templates/`, and `SKILL.md` frontmatter passes the Hermes description-length check (≤60 characters)

#### Scenario: Upstream clone stays pristine
- **WHEN** the skill is installed and exercised
- **THEN** `git -C hermes-agent status --porcelain` reports no modifications introduced by this change

### Requirement: Five-dimension adversarial review procedure
The skill SHALL guide an adversarial production-grade review across exactly five dimensions: (1) logic holes and race conditions (check-then-act races, missing Saga compensation, swallowed exceptions), (2) latent performance killers (N+1 queries, blocking event-loop work, HTTP clients without timeout/retry), (3) OWASP Top 10 security issues (injection, hardcoded secrets, horizontal/vertical privilege escalation), (4) configuration and environment illusions (absolute paths, unvalidated environment variables), and (5) logging and observability (sensitive data in logs, missing TraceId propagation). Every finding SHALL include the concrete file location, a reproducible attack or failure case, and a severity grade of `[严重][P0]` or `[中危][P1]`.

#### Scenario: Findings are reported per dimension
- **WHEN** the review procedure scans a target directory
- **THEN** output lists findings grouped by the five dimensions with file location, attack/failure case, and P0/P1 grade

#### Scenario: Clean dimensions are explicit
- **WHEN** a dimension has no findings
- **THEN** the report states that dimension as explicitly clean rather than omitting it

### Requirement: Mechanical scan helper
The skill SHALL ship a stdlib-only helper script `scripts/hardening_scan.py` that mechanically detects at least: bare `except` clauses that swallow exceptions, hardcoded secret-like values (prefixes `sk-`/`AKIA`/`ghp_`/`glpat-`/`xox*-`/`AIza`, private-key blocks, and common key-name assignments), absolute filesystem paths, HTTP client calls without an explicit timeout, and non-UTF-8 files. HTTP timeout detection SHALL be import-aware (only constructors imported from known HTTP libraries are flagged) and SHALL accept instance-level or `**kwargs`-forwarded timeouts to avoid false positives. Placeholder tokens such as `<YOUR_...>`, `REPLACE_WITH_*`, and `${VAR}` SHALL NOT be reported as secrets. Duplicate findings for the same file and rule SHALL be collapsed. The script SHALL exit with a dedicated nonzero code when findings exist, a zero code when none exist, and a distinct error code with usage output when invoked with missing or invalid arguments; a missing or unreadable source path SHALL be an error, never a silent success; a broken output pipe (e.g. `| head`) SHALL preserve the findings exit code instead of reporting a usage error.

#### Scenario: Bare except is detected
- **WHEN** `hardening_scan.py` scans a Python file containing a bare `except:` clause
- **THEN** it emits a finding with the file and line, and exits with the findings code

#### Scenario: Invalid arguments fail fast
- **WHEN** `hardening_scan.py` is invoked with no path or an unknown flag
- **THEN** it prints usage and exits with a distinct error code without scanning

#### Scenario: Missing source path is an error
- **WHEN** the scan target does not exist
- **THEN** the script reports the error and exits nonzero instead of passing silently

#### Scenario: Placeholder secrets are exempt
- **WHEN** a file assigns a placeholder such as `<YOUR_API_KEY>` or `REPLACE_WITH_SECRET` to a key-like name
- **THEN** no hardcoded-secret finding is emitted for that line

#### Scenario: Same-named non-HTTP constructor is not flagged
- **WHEN** a scanned file calls a constructor whose name matches an HTTP client but is not imported from a known HTTP library
- **THEN** no missing-timeout finding is emitted for that call

### Requirement: Scan suppression and configuration
The scanner SHALL support per-line suppression via `# hardening-scan: ignore` (all rules) or `# hardening-scan: ignore=RULE_A,RULE_B` (listed rules only), and repo-level configuration via `.hardening-scan.toml` with `exclude` (glob list) and `disable-rules` (rule ID list), auto-discovered from the target directory or current working directory unless `--no-config` is given; `--config PATH` SHALL load an explicit configuration file. Configuration `exclude` entries and CLI `--exclude` flags SHALL combine additively, not override each other.

#### Scenario: Inline suppression drops a finding
- **WHEN** a line that would produce a finding carries `# hardening-scan: ignore=<RULE_ID>`
- **THEN** that finding is omitted from the output

#### Scenario: Repo config excludes paths
- **WHEN** `.hardening-scan.toml` lists a glob under `exclude`
- **THEN** matching files are skipped during the scan

#### Scenario: Dogfood scan can bypass config
- **WHEN** the scanner is invoked with `--no-config` against an otherwise-exempted directory
- **THEN** findings in that directory are reported normally

### Requirement: Rule registry
The scanner SHALL define its rules in a single registry (`Rule` dataclass entries in `RULES`) carrying rule ID, severity, and review dimension, and SHALL derive the set of known rule IDs from that registry. `hardening-scan --list-rules` SHALL print the registry (rule ID, severity, dimension) for discovery.

#### Scenario: Registry is introspectable
- **WHEN** `hardening-scan --list-rules` is invoked
- **THEN** it prints every registered rule with its severity and dimension and exits zero

### Requirement: Structured Markdown report
The skill SHALL produce a comprehensive Markdown report following `templates/report_template.md` with sections: project overview (tech stack and architecture), adversarial review report (finding list, risk scores, before/after fix comparison with diffs), acceptance test results (load-test numbers or key curl commands), and rollback plan. All code blocks in the report SHALL be copy-paste ready, and any unknown credentials SHALL be placeholder tokens such as `<YOUR_DB_PASSWORD>` highlighted in the report.

#### Scenario: Report contains all required sections
- **WHEN** a report is generated by the skill
- **THEN** it contains the project overview, adversarial review report, acceptance test results, and rollback plan sections, with fixes shown as code diffs

#### Scenario: Secrets are placeholders
- **WHEN** the report or deployment guidance references credentials
- **THEN** they appear as `<YOUR_...>` placeholders and are highlighted, never as real values

### Requirement: Verification gate
The skill SHALL verify its own scripts with unit tests located at `tests/skills/test_hardening_review_skill.py` using only stdlib, pytest, and `unittest.mock` with no live network calls; measured line coverage of the helper script SHALL be ≥80%, enforced via `fail_under = 80` in `pyproject.toml`. The acceptance run SHALL include a 1000-concurrent-invocation smoke of the helper script completing without errors. The project SHALL ship a GitHub Actions CI workflow running ruff, pytest with coverage, a dogfood scan, and Kubernetes manifest validation across a Python 3.11–3.13 matrix, and SHALL be installable as a package (`pip install -e '.[dev]'`) exposing the `hardening-scan` entry point.

#### Scenario: Tests and coverage pass
- **WHEN** pytest runs `tests/skills/test_hardening_review_skill.py`
- **THEN** all tests pass and the helper script achieves ≥80% line coverage with no network calls

#### Scenario: Concurrency smoke passes
- **WHEN** the helper script is invoked 1000 times concurrently against a small fixture tree
- **THEN** every invocation exits without error

### Requirement: Deployment guidance
The skill SHALL include deployment guidance covering both Docker Compose (verifying the upstream `docker-compose.yml` gateway + dashboard services) and Kubernetes manifests under `deploy/` (namespace, configmap, secret, deployment, pod disruption budget, service, ingress, horizontal pod autoscaler, and persistent volume claim) that validate statically with no real secrets embedded. The manifests SHALL be internally consistent: gateway and dashboard share a single PVC for `~/.hermes` state (never `emptyDir`), the gateway is pinned to one replica with `Recreate` strategy and the HPA caps `maxReplicas` at 1 while session state is pod-local, the PDB uses `maxUnavailable: 1` (compatible with a single replica), containers run as the same non-root UID, and the Ingress enforces basic-auth fail-closed.

#### Scenario: Kubernetes manifests are statically valid
- **WHEN** every `deploy/*.yaml` manifest is parsed as YAML
- **THEN** all parse successfully and contain no real secret values (only placeholders)

#### Scenario: Stateful components share one PVC
- **WHEN** `deploy/03-deployment.yaml` and `deploy/08-pvc.yaml` are inspected
- **THEN** both gateway and dashboard mount the same RWX persistent volume claim at the shared state path

#### Scenario: Compose guidance is concrete
- **WHEN** the skill's deployment section is followed
- **THEN** it states the exact `HERMES_UID`/`HERMES_GID` invocation for the upstream `docker-compose.yml` and documents the localhost-only dashboard constraint
