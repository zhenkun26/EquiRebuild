## Purpose

Extends the hardening-review behavior contract with instance-level HTTP timeout data flow and an entropy-based second secret signal, plus skill metadata and install ergonomics.

## MODIFIED Requirements

### Requirement: Mechanical scan helper
The skill SHALL ship a stdlib-only helper script `scripts/hardening_scan.py` that mechanically detects at least: bare `except` clauses that swallow exceptions, hardcoded secret-like values (prefixes `sk-`/`AKIA`/`ghp_`/`glpat-`/`xox*-`/`AIza`, private-key blocks, and common key-name assignments), high-entropy string tokens, absolute filesystem paths, HTTP client calls without an explicit timeout, and non-UTF-8 files. HTTP timeout detection SHALL be import-aware (only constructors imported from known HTTP libraries are flagged), SHALL accept instance-level or `**kwargs`-forwarded timeouts, and SHALL track simple assignment-level data flow: method calls on a client whose constructor set `timeout=` are cleared, while method calls on a client constructed without a default timeout (including `requests.Session`, which cannot carry one) are flagged; reassignment to an unknown value SHALL restore the conservative default (not flagged). Placeholder tokens such as `<YOUR_...>`, `REPLACE_WITH_*`, and `${VAR}` SHALL NOT be reported as secrets. High-entropy detection (Shannon entropy ≥ 4.5 over tokens of ≥20 characters with mixed lower/upper/digit classes) SHALL be a second signal reported only on the `needs_confirmation` channel (`HIGH_ENTROPY_STRING`, `[manual]`), and a line already reported by the prefix or assignment rules SHALL NOT receive a duplicate entropy finding. Duplicate findings for the same file and rule SHALL be collapsed. The script SHALL exit with a dedicated nonzero code when findings exist, a zero code when none exist, and a distinct error code with usage output when invoked with missing or invalid arguments; a missing or unreadable source path SHALL be an error, never a silent success; a broken output pipe (e.g. `| head`) SHALL preserve the findings exit code instead of reporting a usage error.

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

#### Scenario: Instance method on timeout-configured client is cleared
- **WHEN** a scanned file assigns `client = httpx.Client(timeout=30)` and later calls `client.get(url)`
- **THEN** no missing-timeout finding is emitted for the method call

#### Scenario: Instance method on timeout-less client is flagged
- **WHEN** a scanned file assigns `client = httpx.Client()` (or `session = requests.Session()`) and later calls a method on it without `timeout=`
- **THEN** a missing-timeout finding is emitted for the method call

#### Scenario: High-entropy token is a manual-confirmation finding
- **WHEN** a scanned line contains a token of ≥20 characters with mixed character classes and Shannon entropy ≥ 4.5, and no prefix or assignment secret rule fires on that line
- **THEN** a `HIGH_ENTROPY_STRING` finding marked `[manual]` (needs confirmation) is emitted
