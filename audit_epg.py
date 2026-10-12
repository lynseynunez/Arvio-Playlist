import gzip, re, xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

playlist = Path("arvio.m3u").read_text(encoding="utf-8-sig")
entries = [(m.group(1), line.rsplit(",",1)[-1].strip()) for line in playlist.splitlines() if line.startswith("#EXTINF") and (m := re.search(r'tvg-id="([^"]+)"',line))]
channels, programs = set(), Counter()
with gzip.open("epg.xml.gz","rb") as epg:
    for _, e in ET.iterparse(epg,events=("end",)):
        if e.tag == "channel" and e.get("id"): channels.add(e.get("id"))
        if e.tag == "programme" and e.get("channel"): programs[e.get("channel")] += 1
        e.clear()
missing = [(i,n) for i,n in entries if i not in channels]
empty = [(i,n) for i,n in entries if i in channels and not programs[i]]
report = [f"Playlist entries: {len(entries)}",f"EPG channels: {len(channels)}",f"EPG programmes: {sum(programs.values())}",f"Missing IDs: {len(missing)}",f"Zero-programme IDs: {len(empty)}",f"DAZN Ringside programmes: {programs['649b6898f2ec0000081a9460']}"]
report += [f"MISSING: {n} | {i}" for i,n in missing]
report += [f"NO_PROGRAMMES: {n} | {i}" for i,n in empty]
Path("epg-audit.txt").write_text("\n".join(report)+"\n")
print("\n".join(report))
