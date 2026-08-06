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
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

SEVERITY_P0 = "P0"
SEVERITY_P1 = "P1"

DIMENSION_NAMES = {
    1: "logic-and-races",
    2: "performance",
    3: "security",
    4: "configuration",
    5: "observability",
}

SKIPPED_DIRECTORY_NAMES = frozenset(
    {".git", ".venv", "venv", "__pycache__", "node_modules", ".archive"}
)

BINARY_SUFFIXES = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz",
        ".woff", ".woff2", ".ttf", ".pyc", ".so", ".dylib", ".exe", ".dll",
        ".lock", ".mp3", ".mp4", ".webm",
    }
)

HTTP_TOP_LEVEL_CLIENTS = frozenset({"requests", "httpx"})
HTTP_METHOD_NAMES = frozenset({"get", "post", "put", "patch", "delete", "request"})
HTTP_CLIENT_CONSTRUCTORS = frozenset({"Client", "AsyncClient", "ClientSession"})

SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(secret|password|passwd|api[_-]?key|apikey|token|jwt|"
    r"private[_-]?key|access[_-]?key|secret[_-]?key|auth[_-]?key|client[_-]?secret)\b"
    r"\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    re.IGNORECASE,
)
SECRET_PREFIX_RE = re.compile(
    r"\b(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{30,})\b"
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


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse CLI arguments; argparse exits with code 2 on invalid input."""
    parser = argparse.ArgumentParser(
        prog="hardening_scan.py",
        description=(
            "Mechanical adversarial scan: bare except, HTTP timeouts, "
            "hardcoded secrets, absolute paths."
        ),
    )
    parser.add_argument("target", help="file or directory to scan")
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
    return parser.parse_args(argv)


def scan_python_file(path: Path) -> list[Finding]:
    """Run AST and line-based checks on a single Python source file."""
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [
            Finding(
                severity=SEVERITY_P1,
                dimension=4,
                path=path,
                line=1,
                rule="NON_UTF8",
                message="file is not valid UTF-8; encoding is unverified",
            )
        ]
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [
            Finding(
                severity=SEVERITY_P0,
                dimension=1,
                path=path,
                line=exc.lineno or 1,
                rule="SYNTAX_ERROR",
                message=f"file cannot be parsed: {exc.msg}",
            )
        ]
    findings = _check_exception_handlers(tree, path)
    findings.extend(_check_http_timeouts(tree, path))
    findings.extend(_scan_lines(path, source.splitlines()))
    return findings


def scan_text_file(path: Path) -> list[Finding]:
    """Run line-based checks on a non-Python text file."""
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [
            Finding(
                severity=SEVERITY_P1,
                dimension=4,
                path=path,
                line=1,
                rule="NON_UTF8",
                message="file is not valid UTF-8; encoding is unverified",
            )
        ]
    return _scan_lines(path, source.splitlines())


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
                findings.append(
                    Finding(
                        severity=SEVERITY_P0,
                        dimension=1,
                        path=path,
                        line=handler.lineno,
                        rule="BARE_EXCEPT",
                        message="bare except swallows every exception",
                    )
                )
            elif _handler_only_passes(handler):
                exception_name = (
                    ast.unparse(handler.type) if handler.type is not None else "?"
                )
                findings.append(
                    Finding(
                        severity=SEVERITY_P0,
                        dimension=1,
                        path=path,
                        line=handler.lineno,
                        rule="SWALLOWED_EXCEPTION",
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


def _check_http_timeouts(tree: ast.Module, path: Path) -> list[Finding]:
    """Find HTTP client calls that lack an explicit timeout keyword."""
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_http_call_without_timeout(node):
            findings.append(
                Finding(
                    severity=SEVERITY_P1,
                    dimension=2,
                    path=path,
                    line=node.lineno,
                    rule="HTTP_NO_TIMEOUT",
                    message="HTTP client call without explicit timeout; "
                    "risk of cascading hang",
                )
            )
    return findings


def _is_http_call_without_timeout(node: ast.Call) -> bool:
    """Return True for known HTTP client calls missing the timeout kwarg."""
    if any(keyword.arg == "timeout" for keyword in node.keywords):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if isinstance(func.value, ast.Name):
        if (
            func.value.id in HTTP_TOP_LEVEL_CLIENTS
            and func.attr in HTTP_METHOD_NAMES | HTTP_CLIENT_CONSTRUCTORS
        ):
            return True
    return func.attr in HTTP_CLIENT_CONSTRUCTORS


def _scan_lines(path: Path, lines: Sequence[str]) -> list[Finding]:
    """Run secret and absolute-path regexes over source lines."""
    findings: list[Finding] = []
    for index, line_text in enumerate(lines, start=1):
        if SECRET_ASSIGNMENT_RE.search(line_text) or SECRET_PREFIX_RE.search(line_text):
            findings.append(
                Finding(
                    severity=SEVERITY_P0,
                    dimension=3,
                    path=path,
                    line=index,
                    rule="HARDCODED_SECRET",
                    message="possible hardcoded secret-like value",
                    needs_confirmation=True,
                )
            )
        if ABSOLUTE_PATH_RE.search(line_text):
            findings.append(
                Finding(
                    severity=SEVERITY_P1,
                    dimension=4,
                    path=path,
                    line=index,
                    rule="ABSOLUTE_PATH",
                    message="absolute filesystem path in source",
                    needs_confirmation=True,
                )
            )
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the scan and return the process exit code."""
    args = parse_args(argv)
    target = Path(args.target)
    if not target.exists():
        print(f"error: target does not exist: {target}", file=sys.stderr)
        return EXIT_ERROR

    paths = [target] if target.is_file() else iter_scan_targets(target, args.exclude)
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

    findings.sort(key=lambda item: (item.dimension, item.path.as_posix(), item.line))
    report = render_report(target, findings)
    if args.output:
        try:
            Path(args.output).write_text(report, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write output file: {exc}", file=sys.stderr)
            return EXIT_ERROR
    try:
        print(report, end="")
    except BrokenPipeError:
        return EXIT_ERROR
    return EXIT_FINDINGS if findings else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
