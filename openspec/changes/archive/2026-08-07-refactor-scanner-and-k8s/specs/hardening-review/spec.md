## Purpose

Extends the hardening-review behavior contract after the scanner-and-manifest refactor: scan suppression and configuration, a rule registry, false-positive corrections, refined exit-code semantics, CI/packaging requirements, and internally consistent Kubernetes manifests.

## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: Verification gate
The skill SHALL verify its own scripts with unit tests located at `tests/skills/test_hardening_review_skill.py` using only stdlib, pytest, and `unittest.mock` with no live network calls; measured line coverage of the helper script SHALL be ≥80%, enforced via `fail_under = 80` in `pyproject.toml`. The acceptance run SHALL include a 1000-concurrent-invocation smoke of the helper script completing without errors. The project SHALL ship a GitHub Actions CI workflow running ruff, pytest with coverage, a dogfood scan, and Kubernetes manifest validation across a Python 3.11–3.13 matrix, and SHALL be installable as a package (`pip install -e '.[dev]'`) exposing the `hardening-scan` entry point.

#### Scenario: Tests and coverage pass
- **WHEN** pytest runs `tests/skills/test_hardening_review_skill.py`
- **THEN** all tests pass and the helper script achieves ≥80% line coverage with no network calls

#### Scenario: Concurrency smoke passes
- **WHEN** the helper script is invoked 1000 times concurrently against a small fixture tree
- **THEN** every invocation exits without error

#### Scenario: CI is green on main
- **WHEN** a commit is pushed to `main`
- **THEN** the CI workflow runs ruff, pytest with coverage, a dogfood scan, and manifest validation successfully on Python 3.11, 3.12, and 3.13

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
