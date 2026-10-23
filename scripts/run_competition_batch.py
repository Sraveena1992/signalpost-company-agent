#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.batch import profile_complete_for_modules, profiles_from_bulk, read_organisation_inputs, terminal_envelope, validate_envelopes  # noqa: E402
from norway_company_agent.evidence import evidence, utc_now  # noqa: E402
from norway_company_agent.identity import apply_website_identity_gate  # noqa: E402
from norway_company_agent.official import accounting_obligation_assessment, fetch_official_modules  # noqa: E402
from norway_company_agent.website import fetch_website  # noqa: E402


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Signalpost batch runner with Builderr terminal-state contract")
    parser.add_argument("--organisations", required=True, help="Evaluator company-number batch: JSON, JSONL, or text")
    parser.add_argument("--bulk", help="Optional frozen Brreg entity snapshot; without it, seed identity from the live official API")
    parser.add_argument("--output", required=True, help="Terminal envelope JSONL")
    parser.add_argument("--profiles-output", required=True, help="Evidence-rich profile JSONL")
    parser.add_argument("--report", required=True, help="Machine-readable run report")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-count", type=int, help="Optional exact input count; default is the batch's actual count")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--modules",
        default="registry,accounting_obligation,registry_live,financials,financial_history,roles,group,locations,website",
        help="Comma-separated implemented modules",
    )
    args = parser.parse_args()

    if args.workers < 1 or args.checkpoint_every < 1:
        raise SystemExit("--workers and --checkpoint-every must be positive integers")

    started_at = utc_now()
    organisation_inputs = read_organisation_inputs(args.organisations)
    orgs = [item["organisation_number"] for item in organisation_inputs]
    if not orgs:
        raise SystemExit("The organisation batch is empty")
    expected_count = args.expected_count if args.expected_count is not None else len(orgs)
    if expected_count < 1 or len(orgs) != expected_count:
        raise SystemExit(f"Expected {expected_count} organisations, received {len(orgs)}")

    if args.bulk:
        profiles, registry_metadata = profiles_from_bulk(args.bulk, orgs)
    else:
        profiles = [{"organisation_number": org, "evidence": {}} for org in orgs]
        registry_metadata = {"mode": "live_official_registry", "requested": len(orgs), "selected": len(orgs)}

    annotations = {item["organisation_number"]: item for item in organisation_inputs}
    for profile in profiles:
        for key in ("evaluation_split", "sample_slice"):
            if key in annotations[profile["organisation_number"]]:
                profile[key] = annotations[profile["organisation_number"]][key]

    requested_modules = list(dict.fromkeys(item.strip() for item in args.modules.split(",") if item.strip()))
    # Identity is mandatory for attribution even when a caller customises other modules.
    if "registry_live" not in requested_modules:
        requested_modules.insert(0, "registry_live")
    fetch_modules = set(requested_modules) - {"registry", "accounting_obligation", "website"}
    operations = {"requests": 0, "bytes": 0, "latencies_ms": []}

    def enrich(profile: dict) -> tuple[dict, dict]:
        records, metrics = fetch_official_modules(profile["organisation_number"], fetch_modules)
        profile.setdefault("evidence", {}).update(records)

        live_registry = profile["evidence"].get("registry_live")
        if live_registry and live_registry.get("status") == "available" and isinstance(live_registry.get("value"), dict):
            # Normalised official identity fields are used for exact-company gating.
            for key, value in live_registry["value"].items():
                if value is not None:
                    profile[key] = value

        if "registry" in requested_modules and not profile["evidence"].get("registry"):
            if live_registry:
                profile["evidence"]["registry"] = {
                    **live_registry,
                    "field": "registry",
                }
            else:
                profile["evidence"]["registry"] = evidence(
                    "registry", "source_error", "official_registry_live",
                    "https://data.brreg.no/enhetsregisteret/api/enheter/" + profile["organisation_number"],
                    note="Registry lookup was not completed",
                )

        if "accounting_obligation" in requested_modules and not profile["evidence"].get("accounting_obligation"):
            if live_registry and live_registry.get("status") == "available":
                profile["evidence"]["accounting_obligation"] = accounting_obligation_assessment(profile)
            else:
                profile["evidence"]["accounting_obligation"] = evidence(
                    "accounting_obligation", "not_applicable", "official_rule_interpretation",
                    "https://www.brreg.no/",
                    note="Cannot assess without a verified registry identity",
                )

        website_metrics = {"requests": 0, "bytes": 0, "latencies_ms": []}
        if "website" in requested_modules:
            try:
                website_record, website_metrics = fetch_website(profile.get("website"))
                profile["evidence"]["website"] = apply_website_identity_gate(profile, website_record)["website"]
            except Exception as exc:
                profile["evidence"]["website"] = evidence(
                    "website", "source_error", "company_website",
                    str(profile.get("website") or "https://www.brreg.no/"),
                    note=f"Website module failed safely: {type(exc).__name__}",
                )

        metric = {
            "requests": len(metrics) + website_metrics["requests"],
            "bytes": sum(item.bytes_received for item in metrics) + website_metrics["bytes"],
            "latencies_ms": [item.elapsed_ms for item in metrics] + website_metrics["latencies_ms"],
        }
        profile["run_metrics"] = metric
        return profile, metric

    def safe_enrich(profile: dict) -> tuple[dict, dict]:
        try:
            return enrich(profile)
        except Exception as exc:
            # A single module/organisation exception must not drop this company
            # or abort the remaining batch. Preserve existing evidence and mark
            # every missing requested module with an explicit terminal failure.
            profile.setdefault("evidence", {})
            for module in requested_modules:
                if module not in profile["evidence"] or profile["evidence"][module].get("status") == "not_fetched":
                    profile["evidence"][module] = evidence(
                        module, "source_error", "batch_runner",
                        "https://data.brreg.no/enhetsregisteret/api/enheter/" + profile["organisation_number"],
                        note=f"Organisation enrichment failed safely: {type(exc).__name__}",
                    )
            profile["run_metrics"] = {"requests": 0, "bytes": 0, "latencies_ms": []}
            return profile, {"requests": 0, "bytes": 0, "latencies_ms": []}

    state: dict[str, dict] = {}
    resumed_profiles = 0
    profiles_output = Path(args.profiles_output)
    if args.resume and profiles_output.exists():
        prior = [json.loads(line) for line in profiles_output.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not set(item["organisation_number"] for item in prior).issubset(set(orgs)):
            raise SystemExit("Resume profile membership is not a subset of this batch")
        state = {
            item["organisation_number"]: item
            for item in prior
            if profile_complete_for_modules(item, requested_modules)
        }
        resumed_profiles = len(state)

    pending_profiles = [profile for profile in profiles if profile["organisation_number"] not in state]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(safe_enrich, profile): profile["organisation_number"] for profile in pending_profiles}
        for index, future in enumerate(as_completed(futures), 1):
            profile, metric = future.result()
            state[profile["organisation_number"]] = profile
            operations["requests"] += metric["requests"]
            operations["bytes"] += metric["bytes"]
            operations["latencies_ms"].extend(metric["latencies_ms"])
            if index % args.checkpoint_every == 0 or index == len(pending_profiles):
                checkpoint = [state[org] for org in orgs if org in state]
                write_jsonl(profiles_output, checkpoint)

    completed_at = utc_now()
    ordered_profiles = [state[org] for org in orgs]
    envelopes = [
        terminal_envelope(profile, run_id=args.run_id, modules=requested_modules, started_at=started_at, completed_at=completed_at)
        for profile in ordered_profiles
    ]
    validation = validate_envelopes(envelopes, expected_count, orgs)
    write_jsonl(profiles_output, ordered_profiles)
    write_jsonl(Path(args.output), envelopes)
    latencies = sorted(operations.pop("latencies_ms"))
    operations["p50_ms"] = latencies[len(latencies) // 2] if latencies else None
    operations["p95_ms"] = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else None
    report = {
        "run_id": args.run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "expected_count": expected_count,
        "input_count": len(orgs),
        "emitted_envelopes": len(envelopes),
        "resumed_profiles": resumed_profiles,
        "profiles_fetched_this_run": len(pending_profiles),
        "modules": requested_modules,
        "registry": registry_metadata,
        "operations": operations,
        "validation": validation,
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if validation["passed"] else 1)


if __name__ == "__main__":
    main()
