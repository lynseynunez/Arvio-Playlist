#!/usr/bin/env python3
"""Read-only comparison of candidate XMLTV programme schedules.

Reads diagnostics-report.json and epg.xml.gz; writes a separate review JSON.
Never edits channel IDs, streams, playlists, or guide data.
"""
import argparse
import gzip
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_programmes(guide, wanted, max_samples=8):
    programmes = defaultdict(list)
    opener = gzip.open if guide.suffix == ".gz" else open
    with opener(guide, "rb") as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag == "programme":
                channel = element.get("channel", "")
                if channel in wanted:
                    title = element.findtext("title") or ""
                    start = element.get("start", "")
                    stop = element.get("stop", "")
                    programmes[channel].append((start, stop, title))
                element.clear()
            elif element.tag == "channel":
                element.clear()
    for channel in programmes:
        programmes[channel].sort()
    return programmes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=ROOT / "diagnostics-report.json")
    parser.add_argument("--guide", type=Path, default=ROOT / "epg.xml.gz")
    parser.add_argument("--output", type=Path, default=ROOT / "epg-candidate-review.json")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    missing = [row for row in report["channels"] if not row["has_programmes"]]
    wanted = {item["id"] for row in missing for item in row["epg_candidates"]}
    programmes = load_programmes(args.guide, wanted)
    reviewed = []
    for row in missing:
        candidates = []
        for item in row["epg_candidates"]:
            entries = programmes.get(item["id"], [])
            candidates.append({**item, "programme_count": len(entries),
                               "first_start": entries[0][0] if entries else None,
                               "last_start": entries[-1][0] if entries else None,
                               "sample_programmes": [
                                   {"start": start, "stop": stop, "title": title}
                                   for start, stop, title in entries[:8]
                               ]})
        reviewed.append({"channel": row["name"], "existing_tvg_id": row["tvg_id"],
                         "candidates": candidates,
                         "verified_stream_alignment": False})
    result = {"channels_without_programmes": len(missing), "review": reviewed,
              "warning": "XMLTV listing availability does not verify that a candidate guide aligns with the live stream. Manual verification required; no automatic ID replacements."}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Reviewed {len(missing)} channels and {len(wanted)} unique candidate guide IDs")
    print("Wrote", args.output)

if __name__ == "__main__":
    main()
