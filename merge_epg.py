#!/usr/bin/env python3
"""Build one compact XMLTV guide containing only channels in our Arvio playlist."""
import gzip
import json
import sqlite3
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
# Samsung/Pluto are known working sources. Optional Roku/Plex may fail or lack matches.
SOURCES = [
    ("Samsung", "https://i.mjh.nz/SamsungTVPlus/us.xml.gz", True),
    ("Pluto", "https://i.mjh.nz/PlutoTV/us.xml.gz", True),
    ("Roku", "https://i.mjh.nz/Roku/all.xml.gz", False),
    ("Plex", "https://i.mjh.nz/Plex/us.xml.gz", False),
    # Independent XMLTV feeds; availability and actual channel coverage are audited.
    ("EPGShare US Alt", "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz", False),
    ("EPGShare Brazil", "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz", False),
]

def playlist_channels():
    result = {}
    for line in (ROOT / "arvio.m3u").read_text(encoding="utf-8").splitlines():
        if not line.startswith("#EXTINF:"):
            continue
        match = re.search(r'tvg-id="([^"]+)"', line)
        if match:
            result[match.group(1)] = line.rsplit(",", 1)[-1].strip()
    return result

def read_source(url, db):
    req = Request(url, headers={"User-Agent": "ArvioPlaylistEPG/1.0"})
    with urlopen(req, timeout=120) as response:
        with tempfile.TemporaryFile() as tmp:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
            tmp.seek(0)
            magic = tmp.read(2)
            tmp.seek(0)
            stream = gzip.GzipFile(fileobj=tmp) if magic == bytes((31, 139)) else tmp
            added = 0
            for _, elem in ET.iterparse(stream, events=("end",)):
                if elem.tag == "channel" and elem.get("id"):
                    db.execute("INSERT OR IGNORE INTO channels VALUES (?, ?)",
                               (elem.get("id"), ET.tostring(elem, encoding="utf-8")))
                elif elem.tag == "programme" and elem.get("channel"):
                    cursor = db.execute("INSERT OR IGNORE INTO programmes VALUES (?, ?, ?, ?)",
                                        (elem.get("channel"), elem.get("start"), elem.get("stop"),
                                         ET.tostring(elem, encoding="utf-8")))
                    added += cursor.rowcount
                if elem.tag in ("channel", "programme"):
                    elem.clear()
            db.commit()
            return added

def main():
    wanted = playlist_channels()
    source_status = {}
    with tempfile.TemporaryDirectory() as folder:
        db = sqlite3.connect(str(Path(folder) / "epg.sqlite"))
        db.execute("CREATE TABLE channels (id TEXT PRIMARY KEY, xml BLOB)")
        db.execute("CREATE TABLE programmes (id TEXT, start TEXT, stop TEXT, xml BLOB, PRIMARY KEY(id, start, stop))")
        for name, url, required in SOURCES:
            try:
                count = read_source(url, db)
                source_status[name] = {"status": "ok", "new_programmes": count}
                print(f"{name}: {count} new programmes", flush=True)
            except Exception as exc:
                source_status[name] = {"status": "unavailable", "reason": str(exc)[:180]}
                if required:
                    raise RuntimeError(f"Required {name} EPG unavailable; preserving old guide") from exc
                print(f"Skipping optional {name}: {exc}", flush=True)
        programmes = db.execute("SELECT COUNT(*) FROM programmes").fetchone()[0]
        if programmes < 100:
            raise RuntimeError("Guide too small; preserving previous guide")
        # Publish the entire merged guide. Do not restrict to playlist channels.
        path = ROOT / "epg.xml.gz"
        with path.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=6) as out:
                out.write(b'<?xml version="1.0" encoding="UTF-8"?>' + bytes((10,)))
                out.write(b'<tv generator-info-name="Arvio-Playlist">' + bytes((10,)))
                for (xml,) in db.execute("SELECT xml FROM channels"):
                    out.write(xml + bytes((10,)))
                for (xml,) in db.execute("SELECT xml FROM programmes"):
                    out.write(xml + bytes((10,)))
                out.write(b'</tv>' + bytes((10,)))
        covered = {cid for (cid,) in db.execute("SELECT DISTINCT id FROM programmes")}
        audit = {
            "playlist_channels": len(wanted),
            "channels_with_programmes": sum(cid in covered for cid in wanted),
            "programmes": programmes,
            "total_guide_channels": db.execute("SELECT COUNT(*) FROM channels").fetchone()[0],
            "sources": source_status,
            "without_guide": [name for cid, name in wanted.items() if cid not in covered],
        }
        (ROOT / "epg-audit.json").write_text(json.dumps(audit, indent=2) + chr(10), encoding="utf-8")
        print(json.dumps(audit, indent=2))

if __name__ == "__main__":
    main()
