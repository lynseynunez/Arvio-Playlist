#!/usr/bin/env python3
"""Dry-run one proposed XMLTV alias against the checked-in guide. No writes to guide."""
import gzip
import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from epg_aliases import REVIEWED_ALIASES, apply_aliases

ROOT = Path(__file__).resolve().parent

def main():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE channels (id TEXT PRIMARY KEY, xml BLOB)")
    db.execute("CREATE TABLE programmes (id TEXT, start TEXT, stop TEXT, xml BLOB, PRIMARY KEY(id, start, stop))")
    sources = set(REVIEWED_ALIASES.values())
    targets = set(REVIEWED_ALIASES)
    with gzip.open(ROOT / "epg.xml.gz", "rb") as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag == "channel" and element.get("id") in sources | targets:
                db.execute("INSERT OR IGNORE INTO channels VALUES (?, ?)",
                           (element.get("id"), ET.tostring(element, encoding="utf-8")))
            elif element.tag == "programme" and element.get("channel") in sources | targets:
                db.execute("INSERT OR IGNORE INTO programmes VALUES (?, ?, ?, ?)",
                           (element.get("channel"), element.get("start"), element.get("stop"),
                            ET.tostring(element, encoding="utf-8")))
            if element.tag in ("channel", "programme"):
                element.clear()
    results = apply_aliases(db, REVIEWED_ALIASES)
    for target, result in results.items():
        count = db.execute("SELECT COUNT(*) FROM programmes WHERE id=?", (target,)).fetchone()[0]
        if result["status"] == "aliased" and count == 0:
            raise RuntimeError(f"Alias created without programmes: {target}")
    previews = {}
    for target in REVIEWED_ALIASES:
        rows = db.execute("SELECT start, stop, xml FROM programmes WHERE id=? ORDER BY start", (target,)).fetchall()
        previews[target] = [
            {"start": start, "stop": stop, "title": ET.fromstring(xml).findtext("title") or ""}
            for start, stop, xml in rows[:20]
        ]
    print(json.dumps({"dry_run": True, "guide_unchanged": True, "aliases": results,
                      "programme_previews": previews}, indent=2))

if __name__ == "__main__":
    main()
