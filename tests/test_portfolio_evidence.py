import json
import tempfile
from pathlib import Path

import pytest

from scripts.generate_portfolio_evidence import build_report, source_timestamp, write_report


PASSING_JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="zeta" tests="3" failures="0" errors="0" skipped="1" time="1.25">
    <testcase name="one" />
    <testcase name="two" />
    <testcase name="three"><skipped /></testcase>
  </testsuite>
  <testsuite name="alpha" tests="2" failures="0" errors="0" skipped="0" time="0.5">
    <testcase name="one" />
    <testcase name="two" />
  </testsuite>
</testsuites>
"""


def _write_inputs(root: Path, *, project: str = "fashion-personalization-platform") -> tuple[Path, Path]:
    junit = root / "pytest.xml"
    cli_json = root / "cli.json"
    junit.write_text(PASSING_JUNIT, encoding="utf-8")
    cli_json.write_text(
        json.dumps(
            {
                "project": project,
                "verificationScope": "local-deterministic",
                "claimBoundary": ["local only", "not deployed"],
                "ignoredVolatileField": {"event_watermark": "2026-01-01T00:00:00"},
            }
        ),
        encoding="utf-8",
    )
    return junit, cli_json


def test_report_aggregates_sorted_suites_and_preserves_claim_boundary() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        junit, cli_json = _write_inputs(Path(tmp_dir))
        report = build_report(
            junit,
            cli_json,
            {
                "SOURCE_DATE_EPOCH": "0",
                "EVIDENCE_COMMIT": "abc123",
                "EVIDENCE_RUNTIME": "python-3.11",
            },
        )

    assert [suite["name"] for suite in report["suites"]] == ["alpha", "zeta"]
    assert report["totals"] == {
        "tests": 5,
        "passed": 4,
        "failures": 0,
        "errors": 0,
        "skipped": 1,
    }
    assert report["verification"]["passed"] is True
    assert report["verification"]["scope"] == "local-in-process"
    assert report["cli"]["claim_boundary"] == ["local only", "not deployed"]
    assert report["source"] == {"commit": "abc123", "timestamp": "1970-01-01T00:00:00Z"}
    assert report["runtime"] == "python-3.11"


def test_same_inputs_produce_byte_identical_json() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        junit, cli_json = _write_inputs(root)
        report = build_report(junit, cli_json, {"SOURCE_DATE_EPOCH": "123"})
        first = root / "first.json"
        second = root / "second.json"

        write_report(report, first)
        write_report(report, second)

        assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("value", ["invalid", "-1"])
def test_invalid_source_date_epoch_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        source_timestamp({"SOURCE_DATE_EPOCH": value})


def test_cli_project_mismatch_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        junit, cli_json = _write_inputs(Path(tmp_dir), project="wrong-project")
        with pytest.raises(ValueError, match="unexpected CLI project"):
            build_report(junit, cli_json, {})


def test_inconsistent_junit_counts_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        junit, cli_json = _write_inputs(root)
        junit.write_text(
            '<testsuite name="bad" tests="1" failures="1" errors="1" skipped="0">'
            '<testcase name="bad" /></testsuite>',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="counts exceed total tests"):
            build_report(junit, cli_json, {})


def test_absent_source_date_epoch_is_explicitly_null() -> None:
    assert source_timestamp({}) is None
