#!/usr/bin/env python3
"""Reuse or safely download the official Brreg snapshot, select 100 eligible 2025 filers, and run the batch CLI."""
from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.sampling import deterministic_financial_filer_sample  # noqa: E402

SNAPSHOT_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv"


def validate_gzip(path: Path) -> int:
    """Read the complete gzip stream and return its uncompressed byte count."""
    total = 0
    with gzip.open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
    return total


def ensure_snapshot(snapshot: Path) -> int:
    """Reuse a valid snapshot or download, validate, and atomically install one."""
    if snapshot.exists():
        try:
            size = validate_gzip(snapshot)
            print(f"Reusing verified Brreg snapshot: {snapshot} ({size:,} uncompressed bytes)")
            return size
        except (EOFError, OSError, zlib.error) as exc:
            print(f"Existing snapshot is invalid; downloading a fresh copy: {exc}")

    temporary = snapshot.with_name(snapshot.name + ".download.part")
    temporary.unlink(missing_ok=True)

    request = Request(
        SNAPSHOT_URL,
        headers={
            "User-Agent": "SignalpostCompanyAgent/1.0",
            "Accept": "application/gzip, application/octet-stream, */*",
        },
    )

    try:
        print(f"Downloading official Brreg snapshot from {SNAPSHOT_URL}")
        with urlopen(request, timeout=180) as response:
            with temporary.open("wb") as target:
                shutil.copyfileobj(response, target)

        size = validate_gzip(temporary)
        os.replace(temporary, snapshot)
        print(f"Download verified and installed: {size:,} uncompressed bytes")
        return size
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    artifacts = Path(
        os.environ.get("SIGNALPOST_SMOKE_DIR", ROOT / "artifacts" / "smoke")
    )
    artifacts.mkdir(parents=True, exist_ok=True)

    data_dir = Path(
        os.environ.get("SIGNALPOST_DATA_DIR", ROOT / ".smoke-data")
    )
    data_dir.mkdir(parents=True, exist_ok=True)

    snapshot = data_dir / "brreg-entities.csv.gz"
    ensure_snapshot(snapshot)

    print("Selecting 100 eligible organisations with 2025 annual accounts...")
    selected, sample_report = deterministic_financial_filer_sample(
        snapshot,
        100,
        latest_year="2025",
        seed=20261023,
    )

    if len(selected) != 100:
        raise SystemExit(
            f"Expected 100 eligible 2025 filers; selected {len(selected)}"
        )

    organisations = artifacts / "organisations.jsonl"
    with organisations.open("w", encoding="utf-8") as handle:
        for row in selected:
            handle.write(
                json.dumps(
                    {
                        "organisation_number": row["organisation_number"],
                        "sample_slice": row.get("sample_slice"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    run_id = "smoke-100-" + datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    output = artifacts / "terminal-results.jsonl"
    profiles = artifacts / "profiles.jsonl"
    report = artifacts / "run-report.json"

    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_competition_batch.py"),
        "--organisations", str(organisations),
        "--bulk", str(snapshot),
        "--output", str(output),
        "--profiles-output", str(profiles),
        "--report", str(report),
        "--run-id", run_id,
        "--expected-count", "100",
        "--workers", "8",
        "--checkpoint-every", "10",
    ]

    print("Starting the 100-company research batch...")
    subprocess.run(command, cwd=ROOT, check=True)

    final_report = json.loads(report.read_text(encoding="utf-8"))
    final_report["smoke_sample"] = {
        "source": SNAPSHOT_URL,
        "eligible_account_year": "2025",
        "seed": 20261023,
        "selection": sample_report,
    }
    report.write_text(
        json.dumps(final_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "run_id": run_id,
                "sample_count": len(selected),
                "envelope_count": final_report.get("emitted_envelopes"),
                "validation": final_report.get("validation"),
                "artifacts": [
                    str(output),
                    str(profiles),
                    str(report),
                    str(organisations),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
