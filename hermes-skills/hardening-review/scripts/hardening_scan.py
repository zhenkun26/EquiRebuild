#!/usr/bin/env python3
"""Mechanical adversarial-review scanner for the hardening-review skill.

Scans a target file or directory for mechanically detectable P0/P1 findings:

  D1 logic:        bare ``except:`` / ``except X: pass`` / unparseable files
  D2 performance:  HTTP client calls without an explicit timeout
  D3 security:     hardcoded secret-like assignments and secret prefixes
  D4 configuration: absolute filesystem paths and non-UTF-8 files

Exit codes: 0 = clean, 1 = findings, 2 = usage or target error.
Pure Python stdlib only; no third-party dependencies.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import os
import re
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

SEVERITY_P0 = "P0"
SEVERITY_P1 = "P1"

CONFIG_FILENAME = ".hardening-scan.toml"

SUPPRESSION_RE = re.compile(
    r"#\s*hardening-scan:\s*ignore(?:\s*=\s*([A-Za-z0-9_,\s]+))?"
)

DIMENSION_NAMES = {
    1: "logic-and-races",
    2: "performance",
    3: "security",
    4: "configuration",
    5: "observability",
}

SKIPPED_DIRECTORY_NAMES = frozenset(
    {
        ".git", ".venv", "venv", "__pycache__", "node_modules", ".archive",
        ".ruff_cache", ".pytest_cache", ".mypy_cache", ".tox",
        "dist", "build", "__pypackages__",
    }
)

BINARY_SUFFIXES = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz",
        ".woff", ".woff2", ".ttf", ".pyc", ".so", ".dylib", ".exe", ".dll",
        ".lock", ".mp3", ".mp4", ".webm",
    }
)

HTTP_MODULES = frozenset({"requests", "httpx", "aiohttp"})
HTTP_METHOD_NAMES = frozenset({"get", "post", "put", "patch", "delete", "request"})
HTTP_CLIENT_CONSTRUCTORS = frozenset({"Client", "AsyncClient", "ClientSession"})

SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(secret|password|passwd|api[_-]?key|apikey|token|jwt|"
    r"private[_-]?key|access[_-]?key|secret[_-]?key|auth[_-]?key|client[_-]?secret)\b"
    r"\s*[:=]\s*['\"](?P<value>[^'\"]{8,})['\"]",
    re.IGNORECASE,
)
SECRET_PREFIX_RE = re.compile(
    r"\b(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{30,}|"
    r"glpat-[A-Za-z0-9_-]{20}|xox[bpoa]-[A-Za-z0-9-]{10,}|"
    r"AIza[0-9A-Za-z_-]{35})\b"
    r"|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
)
PLACEHOLDER_VALUE_RE = re.compile(
    r"(<YOUR_[A-Z0-9_]*>|REPLACE_WITH_[A-Z0-9_]*|\$\{[^}]+\}|"
    r"\*{3,}|x{3,}|changeme|example|sample|dummy|placeholder|"
    r"your-[a-z0-9-]+|todo)",
    re.IGNORECASE,
)
ABSOLUTE_PATH_RE = re.compile(
    r"""['"`](/)(Users|home|var|etc|opt|usr|tmp|root|app|data)/""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    """A single review finding with severity, dimension, and location."""

    severity: str
    dimension: int
    path: Path
    line: int
    rule: str
    message: str
    needs_confirmation: bool = False


@dataclass(frozen=True)
class Rule:
    """Static metadata for one detection rule (single source of truth)."""

    rule_id: str
    severity: str
    dimension: int
    message: str
    needs_confirmation: bool = False


RULES: dict[str, Rule] = {
    rule.rule_id: rule
    for rule in (
        Rule("BARE_EXCEPT", SEVERITY_P0, 1, "bare except swallows every exception"),
        Rule(
            "SWALLOWED_EXCEPTION",
            SEVERITY_P0,
            1,
            "exception handler swallows errors without logging or re-raise",
        ),
        Rule("SYNTAX_ERROR", SEVERITY_P0, 1, "file cannot be parsed"),
        Rule(
            "NON_UTF8",
            SEVERITY_P1,
            4,
            "file is not valid UTF-8; encoding is unverified",
        ),
        Rule(
            "HTTP_NO_TIMEOUT",
            SEVERITY_P1,
            2,
            "HTTP client call without explicit timeout; risk of cascading hang",
        ),
        Rule(
            "HARDCODED_SECRET",
            SEVERITY_P0,
            3,
            "possible hardcoded secret-like value",
            needs_confirmation=True,
        ),
        Rule(
            "ABSOLUTE_PATH",
            SEVERITY_P1,
            4,
            "absolute filesystem path in source",
            needs_confirmation=True,
        ),
    )
}

KNOWN_RULES = frozenset(RULES)


def make_finding(
    rule_id: str, path: Path, line: int, message: str | None = None
) -> Finding:
    """Build a Finding from the rule registry; message may be specialised."""
    rule = RULES[rule_id]
    return Finding(
        severity=rule.severity,
        dimension=rule.dimension,
        path=path,
        line=line,
        rule=rule.rule_id,
        message=message if message is not None else rule.message,
        needs_confirmation=rule.needs_confirmation,
    )


@dataclass(frozen=True)
class ScanConfig:
    """Repository-level configuration loaded from .hardening-scan.toml."""

    exclude: tuple[str, ...] = ()
    disable_rules: frozenset[str] = frozenset()
    source: Path | None = None


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse CLI arguments; argparse exits with code 2 on invalid input."""
    parser = argparse.ArgumentParser(
        prog="hardening_scan.py",
        description=(
            "Mechanical adversarial scan: bare except, HTTP timeouts, "
            "hardcoded secrets, absolute paths."
        ),
    )
    parser.add_argument("target", nargs="?", help="file or directory to scan")
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="print the rule registry and exit (no target needed)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="write the findings report to PATH (UTF-8)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        metavar="GLOB",
        help="path globs to skip, fnmatch style (e.g. 'tests/**')",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="explicit path to a .hardening-scan.toml config file",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="ignore any .hardening-scan.toml configuration",
    )
    return parser.parse_args(argv)


def find_config_path(
    target: Path, explicit: Path | None, no_config: bool
) -> Path | None:
    """Resolve the config file to honour, or None when configs are off."""
    if no_config:
        return None
    if explicit is not None:
        return explicit
    candidates = []
    if target.is_dir():
        candidates.append(target / CONFIG_FILENAME)
    candidates.append(Path.cwd() / CONFIG_FILENAME)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_config(path: Path) -> ScanConfig:
    """Parse a .hardening-scan.toml file; raise ValueError on bad content."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read config {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"cannot parse config {path}: {exc}") from exc
    exclude = data.get("exclude", [])
    disable = data.get("disable-rules", [])
    if not isinstance(exclude, list) or not all(
        isinstance(pattern, str) for pattern in exclude
    ):
        raise ValueError(f"config {path}: 'exclude' must be a list of strings")
    if not isinstance(disable, list) or not all(
        isinstance(rule, str) for rule in disable
    ):
        raise ValueError(
            f"config {path}: 'disable-rules' must be a list of strings"
        )
    unknown = set(disable) - KNOWN_RULES
    if unknown:
        raise ValueError(
            f"config {path}: unknown rules in disable-rules: {sorted(unknown)}"
        )
    return ScanConfig(
        exclude=tuple(exclude), disable_rules=frozenset(disable), source=path
    )


def is_suppressed(finding: Finding, line_text: str) -> bool:
    """Return True when the line carries a matching ignore comment.

    Supported forms: ``# hardening-scan: ignore`` (all rules) and
    ``# hardening-scan: ignore=RULE_A,RULE_B`` (listed rules only).
    """
    match = SUPPRESSION_RE.search(line_text)
    if match is None:
        return False
    rules = match.group(1)
    if rules is None:
        return True
    return finding.rule in {rule.strip() for rule in rules.split(",")}


def _apply_suppressions(
    findings: Sequence[Finding], lines: Sequence[str]
) -> list[Finding]:
    """Drop findings whose line carries an inline ignore comment."""
    kept: list[Finding] = []
    for finding in findings:
        if 1 <= finding.line <= len(lines) and is_suppressed(
            finding, lines[finding.line - 1]
        ):
            continue
        kept.append(finding)
    return kept


def _read_utf8(path: Path) -> str | Finding:
    """Read a file as UTF-8; return a NON_UTF8 finding when decoding fails."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return make_finding("NON_UTF8", path, 1)


def scan_python_file(path: Path) -> list[Finding]:
    """Run AST and line-based checks on a single Python source file."""
    result = _read_utf8(path)
    if isinstance(result, Finding):
        return [result]
    source = result
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [
            make_finding(
                "SYNTAX_ERROR",
                path,
                exc.lineno or 1,
                message=f"file cannot be parsed: {exc.msg}",
            )
        ]
    lines = source.splitlines()
    findings = _check_exception_handlers(tree, path)
    findings.extend(_check_http_timeouts(tree, path))
    findings.extend(_scan_lines(path, lines))
    return _apply_suppressions(findings, lines)


def scan_text_file(path: Path) -> list[Finding]:
    """Run line-based checks on a non-Python text file."""
    result = _read_utf8(path)
    if isinstance(result, Finding):
        return [result]
    lines = result.splitlines()
    return _apply_suppressions(_scan_lines(path, lines), lines)


def scan_file(path: Path) -> tuple[list[Finding], list[Path]]:
    """Scan one file; return (findings, unreadable_paths)."""
    try:
        if path.suffix.lower() == ".py":
            findings = scan_python_file(path)
        else:
            findings = scan_text_file(path)
    except OSError:
        return [], [path]
    return findings, []


def iter_scan_targets(root: Path, exclude_patterns: Sequence[str]) -> list[Path]:
    """Return sorted scan targets under root, honouring skip rules."""
    targets: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIPPED_DIRECTORY_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        if _matches_exclude(path, root, exclude_patterns):
            continue
        targets.append(path)
    return sorted(targets)


def _matches_exclude(
    path: Path, root: Path, exclude_patterns: Sequence[str]
) -> bool:
    """Return True when path matches any fnmatch exclude pattern."""
    absolute = path.as_posix()
    relative = path.relative_to(root).as_posix()
    return any(
        fnmatch.fnmatch(absolute, pattern) or fnmatch.fnmatch(relative, pattern)
        for pattern in exclude_patterns
    )


def _check_exception_handlers(tree: ast.Module, path: Path) -> list[Finding]:
    """Find bare except clauses and exception handlers that only pass."""
    findings: list[Finding] = []
    try_types = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())
    for node in ast.walk(tree):
        if not isinstance(node, try_types):
            continue
        for handler in node.handlers:
            if handler.type is None:
                findings.append(make_finding("BARE_EXCEPT", path, handler.lineno))
            elif _handler_only_passes(handler):
                exception_name = (
                    ast.unparse(handler.type) if handler.type is not None else "?"
                )
                findings.append(
                    make_finding(
                        "SWALLOWED_EXCEPTION",
                        path,
                        handler.lineno,
                        message=(
                            f"except {exception_name}: pass swallows errors "
                            "without logging or re-raise"
                        ),
                    )
                )
    return findings


def _handler_only_passes(handler: ast.ExceptHandler) -> bool:
    """Return True when the handler body is exactly a single pass statement."""
    return len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)


@dataclass(frozen=True)
class HttpBindings:
    """Names that refer to known HTTP modules, functions, or constructors."""

    module_aliases: frozenset[str]
    bare_functions: frozenset[str]
    bare_constructors: frozenset[str]


def _collect_http_bindings(tree: ast.Module) -> HttpBindings:
    """Collect import bindings so only genuine HTTP client calls are flagged.

    A call like ``AsyncClient(...)`` from an unrelated SDK must not be
    flagged; we only consider names that trace back to an import of
    ``requests``, ``httpx``, or ``aiohttp``.
    """
    module_aliases: set[str] = set()
    bare_functions: set[str] = set()
    bare_constructors: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in HTTP_MODULES:
                    module_aliases.add(alias.asname or root)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in HTTP_MODULES:
                continue
            for alias in node.names:
                bound = alias.asname or alias.name
                if alias.name in HTTP_METHOD_NAMES:
                    bare_functions.add(bound)
                elif alias.name in HTTP_CLIENT_CONSTRUCTORS:
                    bare_constructors.add(bound)
    return HttpBindings(
        module_aliases=frozenset(module_aliases),
        bare_functions=frozenset(bare_functions),
        bare_constructors=frozenset(bare_constructors),
    )


def _check_http_timeouts(tree: ast.Module, path: Path) -> list[Finding]:
    """Find HTTP client calls that lack an explicit timeout keyword."""
    findings: list[Finding] = []
    bindings = _collect_http_bindings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_http_call_without_timeout(
            node, bindings
        ):
            findings.append(make_finding("HTTP_NO_TIMEOUT", path, node.lineno))
    return findings


def _is_http_call_without_timeout(node: ast.Call, bindings: HttpBindings) -> bool:
    """Return True for known HTTP client calls missing the timeout kwarg."""
    for keyword in node.keywords:
        if keyword.arg == "timeout":
            return False
        if keyword.arg is None:
            # ``**kwargs`` may carry a timeout; heuristic gives it a pass.
            return False
    func = node.func
    if isinstance(func, ast.Attribute):
        # ``requests.get(...)`` / ``httpx.Client(...)`` on an imported module.
        return (
            isinstance(func.value, ast.Name)
            and func.value.id in bindings.module_aliases
            and func.attr in HTTP_METHOD_NAMES | HTTP_CLIENT_CONSTRUCTORS
        )
    if isinstance(func, ast.Name):
        # ``from httpx import Client`` → ``Client(...)`` etc.
        return (
            func.id in bindings.bare_functions
            or func.id in bindings.bare_constructors
        )
    return False


def _scan_lines(path: Path, lines: Sequence[str]) -> list[Finding]:
    """Run secret and absolute-path regexes over source lines."""
    findings: list[Finding] = []
    for index, line_text in enumerate(lines, start=1):
        secret_match = SECRET_ASSIGNMENT_RE.search(line_text)
        if secret_match and PLACEHOLDER_VALUE_RE.search(
            secret_match.group("value")
        ):
            # Obvious placeholder (`<YOUR_...>`, `REPLACE_WITH_*`, ...), not a
            # real credential — do not flag.
            secret_match = None
        if secret_match or SECRET_PREFIX_RE.search(line_text):
            findings.append(make_finding("HARDCODED_SECRET", path, index))
        if ABSOLUTE_PATH_RE.search(line_text):
            findings.append(make_finding("ABSOLUTE_PATH", path, index))
    return findings


def render_report(target: Path, findings: Sequence[Finding]) -> str:
    """Render findings as a human-readable text report."""
    if not findings:
        return f"hardening scan: {target} clean\n"
    lines = [f"hardening scan: {target} found {len(findings)} finding(s)\n"]
    for finding in findings:
        manual_marker = " [manual]" if finding.needs_confirmation else ""
        lines.append(
            f"[{finding.severity}][D{finding.dimension}] "
            f"{finding.path}:{finding.line} {finding.rule}{manual_marker}: "
            f"{finding.message}"
        )
    p0_count = sum(1 for finding in findings if finding.severity == SEVERITY_P0)
    p1_count = len(findings) - p0_count
    lines.append(f"summary: P0={p0_count} P1={p1_count}")
    return "\n".join(lines) + "\n"


def render_rule_listing() -> str:
    """Render the rule registry for `--list-rules`."""
    lines = []
    for rule_id in sorted(RULES):
        rule = RULES[rule_id]
        manual = " [manual]" if rule.needs_confirmation else ""
        lines.append(
            f"{rule.rule_id} [{rule.severity}][D{rule.dimension}]{manual}: "
            f"{rule.message}"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the scan and return the process exit code."""
    args = parse_args(argv)
    if args.list_rules:
        print(render_rule_listing(), end="")
        return EXIT_CLEAN
    if args.target is None:
        print("error: target is required unless --list-rules", file=sys.stderr)
        return EXIT_ERROR
    target = Path(args.target)
    if not target.exists():
        print(f"error: target does not exist: {target}", file=sys.stderr)
        return EXIT_ERROR

    config_path = find_config_path(
        target, Path(args.config) if args.config else None, args.no_config
    )
    config = ScanConfig()
    if config_path is not None:
        try:
            config = load_config(config_path)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR

    exclude_patterns = [*config.exclude, *args.exclude]
    paths = (
        [target] if target.is_file() else iter_scan_targets(target, exclude_patterns)
    )
    findings: list[Finding] = []
    unreadable_paths: list[Path] = []
    for path in paths:
        file_findings, file_errors = scan_file(path)
        findings.extend(file_findings)
        unreadable_paths.extend(file_errors)

    if unreadable_paths:
        for path in unreadable_paths:
            print(f"error: cannot read: {path}", file=sys.stderr)
        return EXIT_ERROR

    if config.disable_rules:
        findings = [
            finding
            for finding in findings
            if finding.rule not in config.disable_rules
        ]

    findings.sort(key=lambda item: (item.dimension, item.path.as_posix(), item.line))
    report = render_report(target, findings)
    if args.output:
        try:
            Path(args.output).write_text(report, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write output file: {exc}", file=sys.stderr)
            return EXIT_ERROR
    exit_code = EXIT_FINDINGS if findings else EXIT_CLEAN
    try:
        print(report, end="")
    except BrokenPipeError:
        # Downstream closed the pipe (e.g. `| head`): the scan itself
        # succeeded, so keep the verdict instead of reporting a usage
        # error. Redirect stdout so the shutdown flush cannot re-raise.
        sys.stdout = Path(os.devnull).open("w", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
