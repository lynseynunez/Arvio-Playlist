#!/usr/bin/env python3
"""Build one compact XMLTV guide containing only channels in our Arvio playlist."""
import gzip
import json
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
    ("EPGShare US", "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz", False),
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

def id_aliases(wanted):
    aliases = {cid: cid for cid in wanted}
    for cid in wanted:
        base = cid.split("@", 1)[0]
        if base not in aliases:
            aliases[base] = cid
    return aliases

def read_source(url, wanted, channels, programmes):
    aliases = id_aliases(wanted)
    req = Request(url, headers={"User-Agent": "ArvioPlaylistEPG/1.0"})
    with urlopen(req, timeout=90) as response:
        with tempfile.TemporaryFile() as tmp:
            # Download without loading entire feed into memory.
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
            tmp.seek(0)
            magic = tmp.read(2)
            tmp.seek(0)
            if magic == b"\x1f\x8b":
                stream = gzip.GzipFile(fileobj=tmp)
            else:
                stream = tmp
            # Only retain selected IDs and matching programmes.
            for event, elem in ET.iterparse(stream, events=("end",)):
                if elem.tag == "channel" and elem.get("id") in aliases:
                    target = aliases[elem.get("id")]
                    if target not in channels:
                        elem.set("id", target)
                        channels[target] = ET.tostring(elem, encoding="utf-8")
                elif elem.tag == "programme" and elem.get("channel") in aliases:
                    target = aliases[elem.get("channel")]
                    key = (target, elem.get("start"), elem.get("stop"))
                    if key not in programmes:
                        elem.set("channel", target)
                        programmes[key] = ET.tostring(elem, encoding="utf-8")
                if elem.tag in ("channel", "programme"):
                    elem.clear()

def main():
    wanted = playlist_channels()
    channels, programmes, source_status = {}, {}, {}
    for name, url, required in SOURCES:
        before = len(programmes)
        try:
            read_source(url, wanted, channels, programmes)
            source_status[name] = {"status": "ok", "new_programmes": len(programmes) - before}
        except Exception as exc:
            source_status[name] = {"status": "unavailable", "reason": str(exc)[:180]}
            if required:
                raise RuntimeError(f"Required {name} EPG unavailable; preserving old guide") from exc
            print(f"Skipping optional {name}: {exc}")
    if len(programmes) < 100:
        raise RuntimeError(f"Only {len(programmes)} programmes found; preserving old guide")
    root = ET.Element("tv", {"generator-info-name": "Arvio-Playlist"})
    for channel_id in wanted:
        if channel_id in channels:
            root.append(ET.fromstring(channels[channel_id]))
    for data in programmes.values():
        root.append(ET.fromstring(data))
    path = ROOT / "epg.xml.gz"
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=6) as out:
            out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=False)
    covered = {key[0] for key in programmes}
    audit = {
        "playlist_channels": len(wanted),
        "channels_with_programmes": len(covered),
        "programmes": len(programmes),
        "sources": source_status,
        "without_guide": [name for cid, name in wanted.items() if cid not in covered],
    }
    (ROOT / "epg-audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))

if __name__ == "__main__":
    main()
