#!/usr/bin/env python3
"""Measure EPG coverage before/after provisional aliases without publishing guide."""
import gzip
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from epg_aliases import REVIEWED_ALIASES, apply_aliases

ROOT = Path(__file__).resolve().parent

def main():
    ids = set()
    for line in (ROOT / "arvio.m3u").read_text(encoding="utf-8").splitlines():
        if line.startswith("#EXTINF:"):
            match = re.search(r'tvg-id="([^"]+)"', line)
            if match:
                ids.add(match.group(1))
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE channels (id TEXT PRIMARY KEY, xml BLOB)")
    db.execute("CREATE TABLE programmes (id TEXT, start TEXT, stop TEXT, xml BLOB, PRIMARY KEY(id, start, stop))")
    relevant = ids | set(REVIEWED_ALIASES.values())
    with gzip.open(ROOT / "epg.xml.gz", "rb") as stream:
        for _, elem in ET.iterparse(stream, events=("end",)):
            cid = elem.get("id") if elem.tag == "channel" else elem.get("channel")
            if cid in relevant and elem.tag == "channel":
                db.execute("INSERT OR IGNORE INTO channels VALUES (?, ?)", (cid, ET.tostring(elem, encoding="utf-8")))
            elif cid in relevant and elem.tag == "programme":
                db.execute("INSERT OR IGNORE INTO programmes VALUES (?, ?, ?, ?)",
                           (cid, elem.get("start"), elem.get("stop"), ET.tostring(elem, encoding="utf-8")))
            if elem.tag in ("channel", "programme"):
                elem.clear()
    before = {x for (x,) in db.execute("SELECT DISTINCT id FROM programmes")}
    outcome = apply_aliases(db, REVIEWED_ALIASES)
    after = {x for (x,) in db.execute("SELECT DISTINCT id FROM programmes")}
    print(json.dumps({"dry_run": True, "live_files_modified": False,
                      "playlist_channels": len(ids),
                      "covered_before": len(ids & before),
                      "covered_after_provisional_alias": len(ids & after),
                      "newly_covered": sorted((ids & after) - before),
                      "alias_results": outcome}, indent=2))

if __name__ == "__main__":
    main()
