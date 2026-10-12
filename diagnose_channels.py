#!/usr/bin/env python3
"""Read-only diagnostic of existing M3U logos and XMLTV programme coverage.

Never modifies the playlist, guide, or channel identifiers.
"""
import argparse
import difflib
import gzip
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent

def normalize(value):
    value = re.sub(r"\([^)]*\b(?:480|720|1080|2160)p\b[^)]*\)", "", value, flags=re.I)
    value = re.sub(r"\[[^]]*\]", "", value)
    return re.sub(r"[^a-z0-9]", "", value.casefold())

def attrs(line):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', line))

def read_playlist(path):
    channels = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("#EXTINF:"):
            a = attrs(line)
            channels.append({"name": line.rsplit(",", 1)[-1].strip(),
                             "tvg_id": a.get("tvg-id", ""),
                             "logo": a.get("tvg-logo", ""),
                             "group": a.get("group-title", "")})
    return channels

def read_guide(path):
    opener = gzip.open if path.suffix == ".gz" else open
    names = {}
    covered = set()
    with opener(path, "rb") as stream:
        for _, node in ET.iterparse(stream, events=("end",)):
            if node.tag == "channel":
                cid = node.get("id", "")
                names[cid] = [n.text.strip() for n in node.findall("display-name") if n.text]
            elif node.tag == "programme":
                covered.add(node.get("channel", ""))
            if node.tag in ("channel", "programme"):
                node.clear()
    return names, covered

def check_logo(url, timeout):
    if not url:
        return "missing", None
    if urlparse(url).scheme not in ("http", "https"):
        return "invalid_url", None
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ArvioLogoAudit/1.0)"}
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                kind = response.headers.get("Content-Type", "").split(";")[0].lower()
                if method == "HEAD" and (not kind or kind == "application/octet-stream"):
                    continue
                if kind.startswith("image/"):
                    return "ok", response.status
                return "not_image", response.status
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue
            return "http_error", exc.code
        except Exception:
            if method == "HEAD":
                continue
            return "network_error", None
    return "unknown", None

def suggestions(channel, names, covered, limit=5):
    desired = normalize(channel["name"])
    cid = normalize(channel["tvg_id"].split("@")[0])
    ranked = []
    for guide_id, labels in names.items():
        candidates = [guide_id, guide_id.split("@")[0], *labels]
        score = max((difflib.SequenceMatcher(None, desired, normalize(x)).ratio()
                     for x in candidates if normalize(x)), default=0)
        if cid and any(normalize(x) == cid for x in candidates):
            score = 1.0
        if score >= 0.65:
            ranked.append({"id": guide_id, "names": labels[:3],
                           "score": round(score, 3),
                           "has_programmes": guide_id in covered})
    ranked.sort(key=lambda x: (x["has_programmes"], x["score"]), reverse=True)
    return ranked[:limit]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist", type=Path, default=ROOT / "arvio.m3u")
    parser.add_argument("--guide", type=Path, default=ROOT / "epg.xml.gz")
    parser.add_argument("--output", type=Path, default=ROOT / "diagnostics-report.json")
    parser.add_argument("--skip-network", action="store_true", help="Do not probe logo URLs")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    channels = read_playlist(args.playlist)
    names, covered = read_guide(args.guide)
    cache = {}
    rows = []
    for ch in channels:
        logo = ch["logo"]
        if logo not in cache:
            cache[logo] = ("not_checked", None) if args.skip_network else check_logo(logo, args.timeout)
        status, http_status = cache[logo]
        guide_ok = bool(ch["tvg_id"] and ch["tvg_id"] in covered)
        rows.append({**ch, "logo_status": status, "logo_http_status": http_status,
                     "has_programmes": guide_ok,
                     "epg_candidates": [] if guide_ok else suggestions(ch, names, covered)})
    report = {
        "playlist_channels": len(rows),
        "with_programmes": sum(r["has_programmes"] for r in rows),
        "without_programmes": [r["name"] for r in rows if not r["has_programmes"]],
        "logo_status_counts": dict(Counter(r["logo_status"] for r in rows)),
        "channels": rows,
        "note": "Candidate matches are suggestions only; no tvg-id or source is changed."
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Audited {len(rows)} channels; {report['with_programmes']} have programmes")
    print("Logo status:", report["logo_status_counts"])
    print("Report:", args.output)

if __name__ == "__main__":
    main()
