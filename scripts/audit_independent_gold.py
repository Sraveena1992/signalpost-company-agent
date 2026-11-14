#!/usr/bin/env python3
"""Independent gold-label comparator. This tool does NOT create gold labels."""
import argparse
import json
from pathlib import Path

CATEGORIES = ("identity", "financials", "roles", "locations", "websites", "news", "jobs", "other")

def load(path):
    items = {}
    for n, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("category") not in CATEGORIES:
            raise ValueError(f"{path}:{n}: invalid category")
        if any(not str(row.get(field) or "").strip() for field in ("organisation_number", "claim_key", "value")):
            raise ValueError(f"{path}:{n}: missing claim data")
        key = (str(row["organisation_number"]), row["category"], str(row["claim_key"]))
        if key in items:
            raise ValueError(f"{path}:{n}: duplicate claim")
        items[key] = row
    return items

def audit(predicted, gold):
    if not gold:
        raise ValueError("Independent labeled gold file is empty")
    by_category = {}
    for category in CATEGORIES:
        p = {k:v for k,v in predicted.items() if k[1] == category}
        g = {k:v for k,v in gold.items() if k[1] == category}
        for value in g.values():
            if value.get("verdict") not in ("true", "false", "unknown"):
                raise ValueError("Gold verdict must be true, false, or unknown")
        known = {k:v for k,v in g.items() if v["verdict"] != "unknown"}
        positives = {k:v for k,v in known.items() if v["verdict"] == "true"}
        tp = sum(k in p and str(p[k]["value"]).strip() == str(v["value"]).strip() for k,v in positives.items())
        fn = len(positives) - tp
        fp = sum(k in known and (known[k]["verdict"] == "false" or str(p[k]["value"]).strip() != str(known[k]["value"]).strip()) for k in p)
        unreviewed = sum(k not in known for k in p)
        precision = tp/(tp+fp) if tp+fp else None
        recall = tp/(tp+fn) if tp+fn else None
        by_category[category] = {"true_positive":tp,"verified_false_positive":fp,"false_negative":fn,
            "unreviewed_predictions":unreviewed,"unknown_gold_labels":len(g)-len(known),
            "precision":precision,"recall":recall,
            "precision_95_established":precision is not None and precision >= 0.95 and unreviewed == 0}
    fields = ("true_positive","verified_false_positive","false_negative","unreviewed_predictions","unknown_gold_labels")
    total = {field:sum(row[field] for row in by_category.values()) for field in fields}
    denominator = total["true_positive"]+total["verified_false_positive"]
    total["precision"] = total["true_positive"]/denominator if denominator else None
    total["recall"] = total["true_positive"]/(total["true_positive"]+total["false_negative"]) if total["true_positive"]+total["false_negative"] else None
    total["all_categories_95_established"] = all(row["precision_95_established"] for row in by_category.values())
    return {"total":total,"categories":by_category,"note":"Requires independently sourced human-reviewed labels; not an official competition score."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--predictions",required=True)
    parser.add_argument("--gold",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    result=audit(load(args.predictions),load(args.gold))
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__ == "__main__":
    main()
