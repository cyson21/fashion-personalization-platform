#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
PROJECT = "fashion-personalization-platform"
PROVEN_BOUNDARIES = [
    "deterministic core event, recommendation, and batch behavior",
    "in-process FastAPI TestClient request validation and response contracts",
    "CLI portfolio audit against the in-memory demo service",
]
NOT_PROVEN_BOUNDARIES = [
    "deployed ASGI server or external network behavior",
    "asynchronous HTTP event worker or message broker delivery",
    "persistent storage or distributed idempotency",
    "AWS deployment or machine-learning model quality",
]


def _count(value: str | None, *, field: str) -> int:
    try:
        parsed = int(value or 0)
    except ValueError as exc:
        raise ValueError(f"invalid JUnit {field}: {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"JUnit {field} must be non-negative: {parsed}")
    return parsed


def read_junit(junit_path: Path) -> tuple[list[dict[str, object]], dict[str, int | float]]:
    root = ET.parse(junit_path).getroot()
    candidates = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    suites: list[dict[str, object]] = []
    for suite in candidates:
        if not suite.findall("testcase"):
            continue
        tests = _count(suite.get("tests"), field="tests")
        failures = _count(suite.get("failures"), field="failures")
        errors = _count(suite.get("errors"), field="errors")
        skipped = _count(suite.get("skipped"), field="skipped")
        non_passing = failures + errors + skipped
        if non_passing > tests:
            raise ValueError("JUnit failure, error, and skipped counts exceed total tests")
        suites.append(
            {
                "name": suite.get("name") or "unnamed-suite",
                "tests": tests,
                "passed": tests - non_passing,
                "failures": failures,
                "errors": errors,
                "skipped": skipped,
            }
        )
    if not suites:
        raise ValueError(f"no JUnit test suites with test cases found in {junit_path}")
    suites.sort(key=lambda suite: str(suite["name"]))
    totals: dict[str, int | float] = {
        key: sum(int(suite[key]) for suite in suites)
        for key in ("tests", "passed", "failures", "errors", "skipped")
    }
    return suites, totals


def read_cli_summary(cli_json_path: Path) -> dict[str, object]:
    payload = json.loads(cli_json_path.read_text(encoding="utf-8"))
    if payload.get("project") != PROJECT:
        raise ValueError(f"unexpected CLI project: {payload.get('project')!r}")
    if payload.get("verificationScope") != "local-deterministic":
        raise ValueError(f"unexpected CLI verification scope: {payload.get('verificationScope')!r}")
    boundaries = payload.get("claimBoundary")
    if not isinstance(boundaries, list) or not all(isinstance(item, str) for item in boundaries):
        raise ValueError("CLI claimBoundary must be a list of strings")
    return {
        "project": payload["project"],
        "verification_scope": payload["verificationScope"],
        "claim_boundary": boundaries,
    }


def source_timestamp(environ: dict[str, str]) -> str | None:
    raw_epoch = environ.get("SOURCE_DATE_EPOCH")
    if raw_epoch is None:
        return None
    try:
        epoch = int(raw_epoch)
    except ValueError as exc:
        raise ValueError("SOURCE_DATE_EPOCH must be a non-negative integer") from exc
    if epoch < 0:
        raise ValueError("SOURCE_DATE_EPOCH must be a non-negative integer")
    try:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("SOURCE_DATE_EPOCH is outside the supported timestamp range") from exc


def build_report(
    junit_path: Path,
    cli_json_path: Path,
    environ: dict[str, str] | None = None,
) -> dict[str, object]:
    environ = dict(os.environ if environ is None else environ)
    suites, totals = read_junit(junit_path)
    cli_summary = read_cli_summary(cli_json_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "source": {
            "commit": environ.get("EVIDENCE_COMMIT") or environ.get("GITHUB_SHA"),
            "timestamp": source_timestamp(environ),
        },
        "runtime": environ.get("EVIDENCE_RUNTIME"),
        "verification": {
            "scope": "local-in-process",
            "passed": totals["failures"] == 0 and totals["errors"] == 0,
            "proven": PROVEN_BOUNDARIES,
            "not_proven": NOT_PROVEN_BOUNDARIES,
        },
        "totals": totals,
        "suites": suites,
        "cli": cli_summary,
    }


def write_report(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output.parent,
        prefix=f".{output.name}.",
        delete=False,
    ) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    temporary_path.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic fashion portfolio evidence.")
    parser.add_argument("--junit", type=Path, required=True, help="pytest JUnit XML path")
    parser.add_argument("--cli-json", type=Path, required=True, help="CLI evidence JSON path")
    parser.add_argument("--output", type=Path, required=True, help="JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.junit, args.cli_json)
    write_report(report, args.output)
    return 0 if report["verification"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
