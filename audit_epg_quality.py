#!/usr/bin/env python3
"""Read-only EPG quality report: freshness, gaps and generic titles."""
import argparse
import gzip
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

def parse_time(value):
    try:
        base = datetime.strptime(value[:14], "%Y%m%d%H%M%S")
        match = re.search(r"([+-])(\\d{2})(\\d{2})$", (value or "").strip())
        offset = timedelta(hours=int(match.group(2)), minutes=int(match.group(3))) if match else timedelta()
        if match and match.group(1) == "-": offset = -offset
        return base.replace(tzinfo=timezone(offset)).timestamp()
    except (ValueError, TypeError):
        return None

def playlist_ids(path):
    ids = set()
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('#EXTINF:'):
            m = re.search(r'tvg-id="([^"]+)"', line)
            if m and m.group(1): ids.add(m.group(1))
    return ids

def audit(guide, wanted):
    by_channel = defaultdict(list)
    with gzip.open(guide, "rb") as stream:
        for _, el in ET.iterparse(stream, events=("end",)):
            if el.tag == "programme":
                cid = el.get("channel", "")
                start, stop = parse_time(el.get("start")), parse_time(el.get("stop"))
                title = (el.findtext("title") or "").strip()
                if cid in wanted and start is not None and stop is not None and stop > start:
                    by_channel[cid].append((start, stop, title))
                el.clear()
            elif el.tag == "channel":
                el.clear()
    now = datetime.now(timezone.utc).timestamp()
    flagged = []
    flag_counts = Counter()
    for cid, entries in by_channel.items():
        entries.sort()
        titles = Counter(x[2].casefold() for x in entries if x[2])
        gaps = [round((b[0] - a[1])/3600, 2) for a, b in zip(entries, entries[1:]) if b[0] > a[1]]
        active = sum(a <= now < b for a,b,_ in entries)
        future = sum(b > now for _,b,_ in entries)
        reasons = []
        if not future: reasons.append("no_current_or_future_programmes")
        if not active: reasons.append("no_programme_now")
        if gaps and max(gaps) >= 6: reasons.append("gap_over_6_hours")
        if len(entries) >= 5 and titles and titles.most_common(1)[0][1] / len(entries) >= .8:
            reasons.append("repetitive_titles")
        if reasons:
            flag_counts.update(reasons)
            flagged.append({"channel_id": cid, "programmes": len(entries),
                            "future_programmes": future, "max_gap_hours": max(gaps, default=0),
                            "most_common_title": titles.most_common(1)[0][0] if titles else "",
                            "flags": reasons})
    expired = sorted(({"channel_id": cid, "last_stop_utc": datetime.fromtimestamp(max(stop for _, stop, _ in entries), timezone.utc).isoformat(), "programme_count": len(entries)} for cid, entries in by_channel.items() if entries and max(stop for _, stop, _ in entries) <= now), key=lambda x:x["channel_id"])
    recent_expiry = [x for x in expired if (now - datetime.fromisoformat(x["last_stop_utc"]).timestamp()) < 6*3600]
    stale_expiry = [x for x in expired if (now - datetime.fromisoformat(x["last_stop_utc"]).timestamp()) >= 6*3600]
    return {"recently_expired_under_6h": recent_expiry, "stale_over_6h": stale_expiry, "expired_channels": expired, "playlist_ids": len(wanted), "playlist_ids_with_programmes": len(by_channel),
            "playlist_ids_without_programmes": sorted(wanted - set(by_channel)),
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "channels_with_programmes": len(by_channel),
            "flagged_count": len(flagged),
            "flag_counts": dict(flag_counts),
            "flagged": sorted(flagged, key=lambda x: x["channel_id"]),
            "note": "Guide-only heuristic; no live stream playback verification."}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--guide", type=Path, default=Path(__file__).resolve().parent / "epg-preview.xml.gz")
    p.add_argument("--output", type=Path, default=Path("epg-quality-report.json"))
    p.add_argument("--playlist", type=Path, default=Path(__file__).resolve().parent / "arvio.m3u")
    a = p.parse_args()
    report = audit(a.guide, playlist_ids(a.playlist))
    a.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k:v for k,v in report.items() if k != "flagged"}, indent=2))
