#!/usr/bin/env python3
"""Create a blind, reproducible review queue; never manufacture gold labels.

Source: existing real 500-company profiles. Output is NOT an accuracy score.
Independent reviewer must obtain original publisher/source records and resolve
wrong-entity, missing, temporal, and contradiction cases before any scoring.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random


def build_queue(profiles, sample_size=384, seed=20261114, minimum_per_category=10):
    if sample_size < 1 or minimum_per_category < 1:
        raise ValueError("sample_size and minimum_per_category must be positive")
    if len(profiles) != 500 or len({str(p["organisation_number"]) for p in profiles}) != 500:
        raise ValueError("Expected exactly 500 unique companies from the audited batch")
    rows = []
    seen = set()
    for p in profiles:
        org = str(p["organisation_number"])
        for n, f in enumerate((p.get("synthesis") or {}).get("facts") or []):
            label = str(f.get("claim") or "")
            classification = str(f.get("classification") or "unclassified")
            canonical = json.dumps([org, classification, label, f.get("value"), f.get("source_url")],
                                   sort_keys=True, ensure_ascii=False, default=str)
            cid = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
            if cid in seen:
                continue
            seen.add(cid)
            rows.append({
                "claim_id": cid, "organisation_number": org,
                "company_name": str(p.get("name") or ""),
                "category": classification, "claim": label, "value": f.get("value"),
                "claimed_source_url": f.get("source_url"),
                "claimed_retrieval_time": f.get("retrieved_at"),
                "review": {
                    "status": "UNREVIEWED",
                    "independent_primary_source_url": None,
                    "independent_observed_value": None,
                    "independently_verified_company_orgnr": None,
                    "independent_source_retrieved_at": None,
                    "reviewer": None, "reviewer_notes": None,
                },
            })
    if not rows:
        raise ValueError("No claims available for review")
    rng = random.Random(seed)
    strata = defaultdict(list)
    for row in rows:
        strata[row["category"]].append(row)
    for items in strata.values():
        rng.shuffle(items)
    groups = sorted(strata)
    budget = min(sample_size, len(rows))
    if len(groups) > budget:
        raise ValueError("Requested sample too small to cover all claim categories")
    counts = {cat: min(minimum_per_category, len(strata[cat])) for cat in groups}
    if sum(counts.values()) > budget:
        # Cover every group first; the remainder is allocated without exceeding n.
        counts = {cat: 1 for cat in groups}
    remaining = budget - sum(counts.values())
    while remaining:
        eligible = [cat for cat in groups if counts[cat] < len(strata[cat])]
        if not eligible:
            break
        # Largest residual proportional need, deterministic tie breaking.
        best = max(eligible, key=lambda cat: ((len(strata[cat]) / len(rows)) * budget - counts[cat], -groups.index(cat)))
        counts[best] += 1
        remaining -= 1
    queue = [entry for cat in groups for entry in strata[cat][:counts[cat]]]
    rng.shuffle(queue)
    manifest = {
        "method": "deterministic stratified random sample without replacement",
        "sample_seed": seed, "requested_sample_size": sample_size, "actual_sample_size": len(queue),
        "population_claim_count": len(rows), "population_companies": len(profiles),
        "category_population_counts": dict(sorted(Counter(row["category"] for row in rows).items())),
        "category_sample_counts": dict(sorted(counts.items())),
        "is_gold_labelled": False, "precision_established": False,
        "limitations": [
            "Review queue has no independent adjudications; never claim accuracy from this output.",
            "Source corroboration is not independent ground truth.",
            "Precision of asserted claims can be sampled; recall requires separate reference facts and FN enumeration.",
            "Oversampling small categories requires design-aware weights for pooled population precision.",
            "Reviewer must check original legal company identity and source time before marking VERIFIED_TRUE.",
        ],
    }
    return queue, manifest


def evaluate_adjudicated(queue, manifest):
    allowed = {"VERIFIED_TRUE", "FALSE_CONTRADICTED", "FALSE_UNSUPPORTED", "FALSE_WRONG_COMPANY", "UNVERIFIABLE"}
    for item in queue:
        review = item["review"]
        if review.get("status") not in allowed:
            raise ValueError("Cannot score: unreviewed claims remain")
        if not review.get("reviewer") or not review.get("reviewer_notes") or not review.get("independent_source_retrieved_at"):
            raise ValueError("Missing independent reviewer evidence")
        if review["status"] != "UNVERIFIABLE" and not review.get("independent_primary_source_url"):
            raise ValueError("Missing independent primary source")
        if review["status"] == "VERIFIED_TRUE" and str(review.get("independently_verified_company_orgnr")) != str(item["organisation_number"]):
            raise ValueError("Verified claim missing exact independent organisation match")
    # Never discard unknowns. Report bounds without declaring threshold success.
    counts = Counter(item["review"]["status"] for item in queue)
    tp = counts["VERIFIED_TRUE"]
    fp = sum(counts[k] for k in ("FALSE_CONTRADICTED", "FALSE_UNSUPPORTED", "FALSE_WRONG_COMPANY"))
    unknown = counts["UNVERIFIABLE"]
    decided = tp + fp
    by_cat = {}
    for cat in sorted(set(item["category"] for item in queue)):
        group = [x for x in queue if x["category"] == cat]
        k = Counter(x["review"]["status"] for x in group)
        true_count = k["VERIFIED_TRUE"]
        false_count = sum(k[key] for key in ("FALSE_CONTRADICTED", "FALSE_UNSUPPORTED", "FALSE_WRONG_COMPANY"))
        by_cat[cat] = {"sampled": len(group), "verified_true": true_count, "false": false_count,
                       "unverifiable": k["UNVERIFIABLE"],
                       "decidable_precision": true_count/(true_count+false_count) if true_count+false_count else None}
    return {
        "status": "adjudicated_sample_only", "population_size": manifest["population_claim_count"],
        "sample_size": len(queue), "true": tp, "false": fp, "unverifiable": unknown,
        "decidable_precision": tp/decided if decided else None,
        "conservative_precision_lower_bound": tp/len(queue) if queue else None,
        "by_category": by_cat,
        "recall": None, "recall_note": "Requires independently collected reference facts and false negatives",
        "official_builderr_score": None,
        "independent_95pct_certified": False,
        "limitations": "Non-probability classification of unknowns and stratified allocation require reviewer-approved inference; not an automatic qualification certificate.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", type=Path)
    ap.add_argument("--queue", required=True, type=Path)
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--mode", choices=["sample", "score"], default="sample")
    ap.add_argument("--sample-size", type=int, default=384)
    args = ap.parse_args()
    if args.mode == "sample":
        if not args.profiles or not args.manifest:
            ap.error("--profiles and --manifest are required to create queue")
        profiles = [json.loads(line) for line in args.profiles.read_text(encoding="utf-8").splitlines() if line.strip()]
        queue, manifest = build_queue(profiles, sample_size=args.sample_size)
        args.queue.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.queue.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"queued": len(queue), "claims_in_population": manifest["population_claim_count"]}))
    else:
        if not args.manifest or not args.report:
            ap.error("--manifest and --report required to score")
        queue = json.loads(args.queue.read_text(encoding="utf-8"))
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = evaluate_adjudicated(queue, manifest)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
