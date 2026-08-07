"""Unit tests for the hardening-review scanner (stdlib + pytest only).

No live network calls. Fixture files live in ``fixtures/`` and are excluded
from self-review scans because they intentionally contain vulnerable samples.
"""

from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

import hardening_scan
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER_PATH = (
    REPO_ROOT / "hermes-skills" / "hardening-review" / "scripts" / "hardening_scan.py"
)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the scanner as a subprocess and capture output.

    A timeout guards CI: a hung scanner must fail the test, not the runner.
    """
    return subprocess.run(
        [sys.executable, str(SCANNER_PATH), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_should_find_bare_except_when_scanning_fixture():
    findings = hardening_scan.scan_python_file(FIXTURES_DIR / "bare_except.py")
    bare_except_findings = [
        finding for finding in findings if finding.rule == "BARE_EXCEPT"
    ]
    assert len(bare_except_findings) == 1
    assert bare_except_findings[0].severity == hardening_scan.SEVERITY_P0
    assert bare_except_findings[0].dimension == 1
    assert bare_except_findings[0].line == 4


def test_should_find_swallowed_exception_when_handler_only_passes():
    findings = hardening_scan.scan_python_file(
        FIXTURES_DIR / "swallowed_exception.py"
    )
    swallowed_findings = [
        finding
        for finding in findings
        if finding.rule == "SWALLOWED_EXCEPTION"
    ]
    assert len(swallowed_findings) == 1
    assert swallowed_findings[0].severity == hardening_scan.SEVERITY_P0


def test_should_find_http_calls_without_timeout():
    findings = hardening_scan.scan_python_file(
        FIXTURES_DIR / "http_no_timeout.py"
    )
    timeout_findings = [
        finding for finding in findings if finding.rule == "HTTP_NO_TIMEOUT"
    ]
    assert len(timeout_findings) == 2
    assert all(
        finding.severity == hardening_scan.SEVERITY_P1
        for finding in timeout_findings
    )


def test_should_not_flag_http_call_with_explicit_timeout():
    findings = hardening_scan.scan_python_file(FIXTURES_DIR / "clean_module.py")
    assert findings == []


def test_should_find_hardcoded_secret_assignment():
    findings = hardening_scan.scan_python_file(
        FIXTURES_DIR / "secrets_and_paths.py"
    )
    secret_findings = [
        finding
        for finding in findings
        if finding.rule == "HARDCODED_SECRET"
    ]
    assert len(secret_findings) == 1
    assert secret_findings[0].line == 1
    assert secret_findings[0].needs_confirmation is True


def test_should_find_absolute_filesystem_path():
    findings = hardening_scan.scan_python_file(
        FIXTURES_DIR / "secrets_and_paths.py"
    )
    path_findings = [
        finding for finding in findings if finding.rule == "ABSOLUTE_PATH"
    ]
    assert len(path_findings) == 1
    assert path_findings[0].line == 2
    assert path_findings[0].severity == hardening_scan.SEVERITY_P1


def test_should_report_syntax_error_as_p0_finding():
    findings = hardening_scan.scan_python_file(FIXTURES_DIR / "bad_syntax.py")
    assert len(findings) == 1
    assert findings[0].rule == "SYNTAX_ERROR"
    assert findings[0].severity == hardening_scan.SEVERITY_P0


def test_should_report_non_utf8_file_when_bytes_are_invalid(tmp_path):
    fixture = tmp_path / "invalid.py"
    fixture.write_bytes(b"\xff\xfe\x00invalid utf-8 bytes")
    findings = hardening_scan.scan_python_file(fixture)
    assert len(findings) == 1
    assert findings[0].rule == "NON_UTF8"
    assert findings[0].severity == hardening_scan.SEVERITY_P1


def test_should_find_secret_in_markdown_file(tmp_path):
    fixture = tmp_path / "notes.md"
    fixture.write_text(
        (FIXTURES_DIR / "secret_line.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    findings = hardening_scan.scan_text_file(fixture)
    assert any(finding.rule == "HARDCODED_SECRET" for finding in findings)


def test_scan_text_file_should_report_non_utf8_content(tmp_path):
    fixture = tmp_path / "notes.md"
    fixture.write_bytes(b"\xff\xfe\x00broken")
    findings = hardening_scan.scan_text_file(fixture)
    assert len(findings) == 1
    assert findings[0].rule == "NON_UTF8"


def test_scan_file_should_return_unreadable_path_for_directory(tmp_path):
    findings, errors = hardening_scan.scan_file(tmp_path)
    assert findings == []
    assert errors == [tmp_path]


def test_scan_file_should_route_python_and_text_files(tmp_path):
    py_fixture = tmp_path / "sample.py"
    py_fixture.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")
    text_fixture = tmp_path / "sample.md"
    text_fixture.write_text(
        (FIXTURES_DIR / "secret_line.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    py_findings, py_errors = hardening_scan.scan_file(py_fixture)
    text_findings, text_errors = hardening_scan.scan_file(text_fixture)
    assert py_errors == [] and text_errors == []
    assert any(finding.rule == "BARE_EXCEPT" for finding in py_findings)
    assert any(finding.rule == "HARDCODED_SECRET" for finding in text_findings)


def test_iter_scan_targets_should_skip_binary_and_excluded_files(tmp_path):
    (tmp_path / "keep.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "image.png").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "skip.py").write_text("VALUE = 3\n", encoding="utf-8")
    targets = hardening_scan.iter_scan_targets(tmp_path, ["skip.py"])
    assert [target.name for target in targets] == ["keep.py"]


def test_matches_exclude_should_accept_absolute_pattern(tmp_path):
    fixture = tmp_path / "file.py"
    fixture.write_text("VALUE = 1\n", encoding="utf-8")
    assert (
        hardening_scan._matches_exclude(fixture, tmp_path, [fixture.as_posix()])
        is True
    )


def test_should_flag_aiohttp_client_session_without_timeout(tmp_path):
    fixture = tmp_path / "aio.py"
    fixture.write_text(
        "import aiohttp\nsession = aiohttp.ClientSession()\n", encoding="utf-8"
    )
    findings = hardening_scan.scan_python_file(fixture)
    assert any(finding.rule == "HTTP_NO_TIMEOUT" for finding in findings)


def test_render_report_should_mark_manual_findings_and_clean_target(tmp_path):
    finding = hardening_scan.Finding(
        severity=hardening_scan.SEVERITY_P0,
        dimension=3,
        path=tmp_path / "x.py",
        line=1,
        rule="HARDCODED_SECRET",
        message="possible secret",
        needs_confirmation=True,
    )
    dirty_report = hardening_scan.render_report(tmp_path, [finding])
    assert "[manual]" in dirty_report
    assert "summary: P0=1 P1=0" in dirty_report
    clean_report = hardening_scan.render_report(tmp_path, [])
    assert "clean" in clean_report


def test_main_should_return_error_when_target_is_missing():
    assert (
        hardening_scan.main(["missing-target-path"])
        == hardening_scan.EXIT_ERROR
    )


def test_main_should_write_output_file_and_return_findings(tmp_path, capsys):
    output_path = tmp_path / "out.txt"
    exit_code = hardening_scan.main(
        [str(FIXTURES_DIR / "bare_except.py"), "--output", str(output_path)]
    )
    assert exit_code == hardening_scan.EXIT_FINDINGS
    assert "BARE_EXCEPT" in output_path.read_text(encoding="utf-8")
    assert "BARE_EXCEPT" in capsys.readouterr().out


def test_main_should_return_error_when_output_write_fails(
    tmp_path, monkeypatch, capsys
):
    output_path = tmp_path / "out.txt"

    def fail_write_text(_self, _text, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write_text)
    exit_code = hardening_scan.main(
        [str(FIXTURES_DIR / "bare_except.py"), "--output", str(output_path)]
    )
    assert exit_code == hardening_scan.EXIT_ERROR
    assert "cannot write output file" in capsys.readouterr().err


def test_main_should_keep_verdict_on_broken_pipe(tmp_path, monkeypatch):
    def fail_print(*_args, **_kwargs):
        raise BrokenPipeError

    monkeypatch.setattr("builtins.print", fail_print)
    assert (
        hardening_scan.main([str(FIXTURES_DIR / "bare_except.py")])
        == hardening_scan.EXIT_FINDINGS
    )


def test_cli_entrypoint_should_exit_when_run_as_main(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["hardening_scan.py", str(FIXTURES_DIR / "clean_module.py")],
    )
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(SCANNER_PATH), run_name="__main__")
    assert excinfo.value.code == hardening_scan.EXIT_CLEAN


def test_cli_should_exit_zero_when_target_is_clean():
    completed = run_cli(str(FIXTURES_DIR / "clean_module.py"))
    assert completed.returncode == hardening_scan.EXIT_CLEAN
    assert "clean" in completed.stdout


def test_cli_should_exit_one_when_findings_exist():
    completed = run_cli(str(FIXTURES_DIR / "bare_except.py"))
    assert completed.returncode == hardening_scan.EXIT_FINDINGS
    assert "BARE_EXCEPT" in completed.stdout
    assert "summary: P0=" in completed.stdout


def test_cli_should_exit_two_when_target_is_missing():
    completed = run_cli(str(Path("definitely-missing-path")))
    assert completed.returncode == hardening_scan.EXIT_ERROR
    assert "does not exist" in completed.stderr


def test_cli_should_exit_two_when_arguments_are_invalid():
    no_target = run_cli()
    unknown_flag = run_cli("--unknown", str(FIXTURES_DIR))
    assert no_target.returncode == hardening_scan.EXIT_ERROR
    assert unknown_flag.returncode == hardening_scan.EXIT_ERROR


def test_cli_should_write_report_to_output_file(tmp_path):
    output_path = tmp_path / "report.txt"
    completed = run_cli(
        str(FIXTURES_DIR / "bare_except.py"), "--output", str(output_path)
    )
    assert completed.returncode == hardening_scan.EXIT_FINDINGS
    assert output_path.exists()
    assert "BARE_EXCEPT" in output_path.read_text(encoding="utf-8")


def test_cli_should_respect_exclude_pattern(tmp_path):
    fixture = tmp_path / "bare_except.py"
    fixture.write_text(
        (FIXTURES_DIR / "bare_except.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    completed = run_cli(str(tmp_path), "--exclude", "bare_except.py")
    assert completed.returncode == hardening_scan.EXIT_CLEAN


def test_cli_should_skip_vendored_directories(tmp_path):
    vendored_dir = tmp_path / ".git"
    vendored_dir.mkdir()
    (vendored_dir / "evil.py").write_text(
        "try:\n    pass\nexcept:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    completed = run_cli(str(tmp_path))
    assert completed.returncode == hardening_scan.EXIT_CLEAN


def test_cli_should_skip_binary_suffixes(tmp_path):
    (tmp_path / "image.png").write_text(
        (FIXTURES_DIR / "api_key_line.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    completed = run_cli(str(tmp_path))
    assert completed.returncode == hardening_scan.EXIT_CLEAN


def test_main_should_fail_fast_on_unreadable_file(tmp_path, monkeypatch):
    (tmp_path / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")

    def fake_scan_file(path: Path):
        return [], [path]

    monkeypatch.setattr(hardening_scan, "scan_file", fake_scan_file)
    assert hardening_scan.main([str(tmp_path)]) == hardening_scan.EXIT_ERROR


# --- Inline suppression -----------------------------------------------------


def test_inline_ignore_should_suppress_specific_rule(tmp_path):
    fixture = tmp_path / "sup.py"
    fixture.write_text(
        "try:\n    pass\nexcept:  # hardening-scan: ignore=BARE_EXCEPT\n    pass\n",
        encoding="utf-8",
    )
    findings = hardening_scan.scan_python_file(fixture)
    assert findings == []


def test_inline_ignore_without_rule_should_suppress_all_rules(tmp_path):
    fixture = tmp_path / "sup.py"
    fixture.write_text(
        "try:\n    pass\nexcept:  # hardening-scan: ignore\n    pass\n",
        encoding="utf-8",
    )
    findings = hardening_scan.scan_python_file(fixture)
    assert findings == []


def test_inline_ignore_with_other_rule_should_keep_finding(tmp_path):
    fixture = tmp_path / "sup.py"
    fixture.write_text(
        "try:\n    pass\nexcept:  # hardening-scan: ignore=HARDCODED_SECRET\n"
        "    pass\n",
        encoding="utf-8",
    )
    findings = hardening_scan.scan_python_file(fixture)
    assert any(finding.rule == "BARE_EXCEPT" for finding in findings)


def test_inline_ignore_should_apply_to_text_files(tmp_path):
    fixture = tmp_path / "notes.md"
    fixture.write_text(
        "api_key = 'supersecretvalue'  # hardening-scan: ignore=HARDCODED_SECRET\n",
        encoding="utf-8",
    )
    findings = hardening_scan.scan_text_file(fixture)
    assert findings == []


# --- Config file ------------------------------------------------------------


def test_load_config_should_parse_exclude_and_disable_rules(tmp_path):
    config = tmp_path / ".hardening-scan.toml"
    config.write_text(
        'exclude = ["fixtures/*"]\ndisable-rules = ["ABSOLUTE_PATH"]\n',
        encoding="utf-8",
    )
    parsed = hardening_scan.load_config(config)
    assert parsed.exclude == ("fixtures/*",)
    assert parsed.disable_rules == frozenset({"ABSOLUTE_PATH"})


def test_load_config_should_reject_unknown_rule(tmp_path):
    config = tmp_path / ".hardening-scan.toml"
    config.write_text('disable-rules = ["NO_SUCH_RULE"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown rules"):
        hardening_scan.load_config(config)


def test_main_should_return_error_when_config_is_invalid(tmp_path):
    config = tmp_path / "bad.toml"
    config.write_text("not toml [", encoding="utf-8")
    target = tmp_path / "ok.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    assert (
        hardening_scan.main([str(target), "--config", str(config)])
        == hardening_scan.EXIT_ERROR
    )


def test_main_should_honour_config_exclude_in_target_dir(tmp_path):
    (tmp_path / ".hardening-scan.toml").write_text(
        'exclude = ["dirty.py"]\n', encoding="utf-8"
    )
    (tmp_path / "dirty.py").write_text(
        "try:\n    pass\nexcept:\n    pass\n", encoding="utf-8"
    )
    assert hardening_scan.main([str(tmp_path)]) == hardening_scan.EXIT_CLEAN


def test_main_should_honour_config_disable_rules(tmp_path):
    (tmp_path / ".hardening-scan.toml").write_text(
        'disable-rules = ["BARE_EXCEPT"]\n', encoding="utf-8"
    )
    (tmp_path / "dirty.py").write_text(
        "try:\n    pass\nexcept:\n    pass\n", encoding="utf-8"
    )
    assert hardening_scan.main([str(tmp_path)]) == hardening_scan.EXIT_CLEAN


def test_main_should_ignore_config_when_no_config_flag(tmp_path):
    (tmp_path / ".hardening-scan.toml").write_text(
        'exclude = ["dirty.py"]\n', encoding="utf-8"
    )
    (tmp_path / "dirty.py").write_text(
        "try:\n    pass\nexcept:\n    pass\n", encoding="utf-8"
    )
    assert (
        hardening_scan.main([str(tmp_path), "--no-config"])
        == hardening_scan.EXIT_FINDINGS
    )


# --- HTTP timeout rule: false-positive guards --------------------------------


def test_should_not_flag_unrelated_client_constructor(tmp_path):
    fixture = tmp_path / "llm.py"
    fixture.write_text(
        "from openai import AsyncClient\nclient = AsyncClient()\n",
        encoding="utf-8",
    )
    findings = hardening_scan.scan_python_file(fixture)
    assert findings == []


def test_should_not_flag_http_call_with_kwargs_splat(tmp_path):
    fixture = tmp_path / "splat.py"
    fixture.write_text(
        "import requests\nrequests.get('https://a.com', **opts)\n",
        encoding="utf-8",
    )
    findings = hardening_scan.scan_python_file(fixture)
    assert findings == []


def test_should_flag_from_imported_constructor_without_timeout(tmp_path):
    fixture = tmp_path / "ctor.py"
    fixture.write_text(
        "from httpx import Client\nclient = Client()\n", encoding="utf-8"
    )
    findings = hardening_scan.scan_python_file(fixture)
    assert any(finding.rule == "HTTP_NO_TIMEOUT" for finding in findings)


def test_should_flag_from_imported_function_without_timeout(tmp_path):
    fixture = tmp_path / "func.py"
    fixture.write_text(
        "from requests import get\nget('https://a.com')\n", encoding="utf-8"
    )
    findings = hardening_scan.scan_python_file(fixture)
    assert any(finding.rule == "HTTP_NO_TIMEOUT" for finding in findings)


# --- Secret rule: placeholder allowlist and new prefixes ---------------------


def test_should_not_flag_placeholder_secret_values(tmp_path):
    fixture = tmp_path / "placeholders.py"
    fixture.write_text(
        "api_key = '<YOUR_API_KEY>'\n"
        "token = \"REPLACE_WITH_REAL_TOKEN\"\n"
        "password = '${DB_PASSWORD}'\n",
        encoding="utf-8",
    )
    findings = hardening_scan.scan_python_file(fixture)
    assert findings == []


def test_should_flag_gitlab_and_slack_token_prefixes(tmp_path):
    fixture = tmp_path / "tokens.txt"
    fixture.write_text(
        (FIXTURES_DIR / "prefix_tokens.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    findings = hardening_scan.scan_text_file(fixture)
    secret_findings = [f for f in findings if f.rule == "HARDCODED_SECRET"]
    assert len(secret_findings) == 2


# --- Rule registry -----------------------------------------------------------


def test_rule_registry_should_cover_known_rules():
    assert hardening_scan.KNOWN_RULES == frozenset(hardening_scan.RULES)
    for rule in hardening_scan.RULES.values():
        assert rule.severity in (
            hardening_scan.SEVERITY_P0,
            hardening_scan.SEVERITY_P1,
        )


def test_cli_should_list_rules_without_target():
    completed = run_cli("--list-rules")
    assert completed.returncode == hardening_scan.EXIT_CLEAN
    assert "BARE_EXCEPT" in completed.stdout
    assert "ABSOLUTE_PATH" in completed.stdout


def test_cli_should_exit_two_when_target_is_omitted():
    completed = run_cli("--exclude", "x")
    assert completed.returncode == hardening_scan.EXIT_ERROR
