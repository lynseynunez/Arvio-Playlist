#!/usr/bin/env python3
"""Read-only shortlist of alternative EPG IDs for still-uncovered playlist channels."""
import argparse
import json
from pathlib import Path
from epg_aliases import REVIEWED_ALIASES

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--diagnostics", type=Path, default=Path("diagnostics-report.json"))
    p.add_argument("--review", type=Path, default=Path("epg-candidate-review.json"))
    p.add_argument("--output", type=Path, default=Path("epg-missing-shortlist.json"))
    a = p.parse_args()
    diagnostic = json.loads(a.diagnostics.read_text())
    review = json.loads(a.review.read_text())
    covered_by_preview = set(REVIEWED_ALIASES)
    rows = []
    for item in review["review"]:
        target = item["existing_tvg_id"]
        if target in covered_by_preview:
            continue
        candidates = sorted(item["candidates"], key=lambda x: (x.get("programme_count", 0)>0, x.get("score", 0)), reverse=True)
        exact = [x for x in candidates if x.get("programme_count",0)>0 and x.get("score",0)>=0.95]
        generic = [x for x in exact if x.get("sample_programmes") and len({p.get("title","").strip().casefold() for p in x["sample_programmes"]}) <= 1]
        rows.append({"channel":item["channel"], "tvg_id":target,
                     "exact_name_candidates": len(exact),
                     "exact_name_generic_title_candidates": len(generic),
                     "recommendation": "manual_review_only" if exact else "seek_additional_epg_sources",
                     "candidates_with_programmes":[x for x in candidates if x.get("programme_count", 0)>0],
                     "candidates_without_programmes":[x for x in candidates if not x.get("programme_count", 0)],
                     "requires_stream_verification": True})
    result = {"remaining_missing":len(rows),"channels":rows,
              "note":"Read-only suggestions; candidate name similarity does not prove stream alignment."}
    a.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))

if __name__=="__main__":
    main()
