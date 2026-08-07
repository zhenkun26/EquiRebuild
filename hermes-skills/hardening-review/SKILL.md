---
name: hardening-review
description: "Adversarial review grades, fixes, verifies P0/P1 findings."
version: 0.1.0
author: yuzheng
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [review, security, hardening, adversarial]
    category: security
    related_skills: [ponytail-review]
---

# Hardening Review Skill

Runs an adversarial production-grade review across five dimensions, grades every finding `[严重][P0]` or `[中危][P1]`, drives fixes with tests, and delivers a comprehensive Markdown acceptance report. It hardens existing code; it does not implement new features.

## When to Use

- Before shipping or deploying a component that touches money, auth, migrations, state machines, external APIs, or environment operations.
- After a feature lands, when you want a final "would this survive production?" pass.
- When a reviewer asks for an auditable trail: findings, fixes, tests, and rollback in one document.

Do not use it for greenfield feature design or for simple typo fixes — those belong to other skills.

## Prerequisites

- Python 3.11+ for `scripts/hardening_scan.py` (stdlib only, no third-party packages).
- Hermes native tools: `search_files`, `read_file`, `patch`, `terminal`, `delegate_task`.
- A git repository so fixes can be shown as diffs and rolled back.
- For the concurrency smoke: a POSIX shell or Python `concurrent.futures` (no network required).

## How to Run

1. Mechanical scan first — it is fast and deterministic:

   `terminal`: `python3 scripts/hardening_scan.py <target> --exclude 'tests/**'`

   Exit codes: `0` clean, `1` findings found, `2` usage or target error.
2. Then read the flagged lines with `read_file` and confirm or dismiss each `[manual]` finding.
3. Manual review of the five dimensions follows; record findings in the report.

## Quick Reference

| Step | Action |
|:---|:---|
| Scan | `python3 scripts/hardening_scan.py <target> [--output report.md] [--exclude GLOB ...] [--config PATH] [--no-config]` |
| List rules | `python3 scripts/hardening_scan.py --list-rules` |
| Suppress | inline `# hardening-scan: ignore=RULE_ID`, or `.hardening-scan.toml` (`exclude`, `disable-rules`) |
| Find code | `search_files` with the target directory |
| Fix | `patch` each P0/P1 finding; never silence an error silently |
| Verify | `pytest tests/skills/ -q` and `coverage report` (≥80%) |
| Smoke | 1000 concurrent invocations of the scanner (exit codes must all match) |
| Report | Fill `templates/report_template.md` |

## Procedure

### Phase 1: Mechanical scan

Run `scripts/hardening_scan.py` over the target. It detects:

- **D1 logic**: bare `except:` and `except X: pass` (swallowed exceptions), unparseable files.
- **D2 performance**: HTTP client calls (`requests`, `httpx`, `aiohttp`) without an explicit `timeout` — import-aware, so same-named constructors from other SDKs are not flagged.
- **D3 security**: hardcoded secret-like assignments and known secret prefixes (`sk-`, `AKIA`, `ghp_`, `glpat-`, `xox*-`, `AIza`, private-key blocks); obvious placeholders (`<YOUR_...>`, `REPLACE_WITH_*`, `${VAR}`) are not flagged.
- **D4 configuration**: absolute filesystem paths and non-UTF-8 files.

Line-based findings are marked `[manual]` — confirm them with `read_file` before fixing.

Suppression, when a finding is a confirmed false positive or intentional:

- Inline: `# hardening-scan: ignore=RULE_ID` on the flagged line (omit `=RULE_ID` to suppress all rules on that line).
- Repo-wide: `.hardening-scan.toml` with `exclude = [...]` / `disable-rules = [...]`; auto-discovered from the target directory or CWD, overridable with `--config` / `--no-config`.
- `python3 scripts/hardening_scan.py --list-rules` prints the rule registry (IDs, severities, dimensions).

### Phase 2: Five-dimension manual review

Review every dimension explicitly; write "clean" when nothing is found — omission is not allowed.

1. **Logic holes and races**: check-then-act races, distributed transactions without compensation (Saga), stack traces swallowed by `except Exception`.
2. **Performance killers**: N+1 queries in loops, blocking work on event loops, HTTP clients without timeout/retry, object churn.
3. **Security (OWASP Top 10)**: injection (SQL/NoSQL/command), hardcoded secrets, horizontal/vertical privilege escalation.
4. **Configuration illusions**: local absolute paths, unvalidated environment variables that fail silently at startup, missing feature flags.
5. **Observability**: sensitive data (passwords, ID numbers) in logs, missing TraceId propagation on critical paths.

Hermes-specific probes: gateway multi-platform concurrency (`gateway/run.py`), SQLite/FTS5 session store (`hermes_state.py`), plugin trust boundaries, HTTP clients in tools, and `agent.log`/`errors.log`/`gateway.log` output.

### Phase 3: Fix P0 and P1

- Fix every P0 and P1 with `patch`; keep changes backward compatible.
- Never fix with `# type: ignore`, `cast()`, or bare `except` as a last resort — that is an escape hatch and must be recorded as quality debt.
- Record before/after diffs in the acceptance report.

### Phase 4: Verify

- Add or update unit tests for every fix (stdlib + pytest + `unittest.mock`, no live network).
- Require line coverage ≥80% on the reviewed module.
- Run the 1000-concurrent-invocation smoke: all invocations must exit with the expected code.

### Phase 5: Deployment guidance and report

- Docker Compose: validate `docker compose -f docker-compose.yml config`; document `HERMES_UID`/`HERMES_GID` startup and the localhost-only dashboard constraint.
- Kubernetes: validate `deploy/*.yaml` statically; every credential must be a `<YOUR_...>` placeholder, never a real value.
- Deliver the Markdown report from `templates/report_template.md` with all sections filled.

## Pitfalls

- Regex findings are heuristics, not verdicts: `[manual]` means confirm before fixing.
- Do not scan vendored trees (`.git`, `.venv`, `node_modules`) — exclude them or the noise hides real findings.
- "Financial-grade" is a posture, not a literal requirement: adapt the five dimensions to the project's actual shape (a CLI skill has no N+1 query problem).
- A missing scan target must be an error (exit `2`), never a silent pass.

## Verification

- `python3 scripts/hardening_scan.py <target>` exits `0` on a clean tree and `1` when findings exist.
- `pytest tests/skills/test_hardening_review_skill.py -q` passes.
- `coverage report` shows ≥80% line coverage for `hardening_scan.py`.
- The 1000-concurrent smoke completes with all exit codes as expected.
