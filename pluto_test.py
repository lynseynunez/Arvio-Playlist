#!/usr/bin/env python3
"""Create an isolated VLC test playlist for Pluto channels; never modify Arvio."""
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

ROOT = Path(__file__).resolve().parent
TEST_NAMES = {"Boruto: Naruto Next Generations", "One Piece", "Inuyasha",
              "Pluto TV Anime", "Pluto TV Anime Movies", "Big A Anime", "Pluto TV Horror"}
API = "https://service-channels.clusters.pluto.tv/v1/guide"

def main():
    request = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = json.load(response)
    channels = data.get("channels", []) if isinstance(data, dict) else data
    if not isinstance(channels, list):
        raise RuntimeError("Unexpected Pluto guide response")
    found = {}
    for channel in channels:
        name = channel.get("name", "")
        if name not in TEST_NAMES:
            continue
        stitched = channel.get("stitched") or {}
        urls = stitched.get("urls") or []
        url = urls[0].get("url", "") if urls else ""
        if not url.startswith("https://"):
            continue
        found[name] = {"id": channel.get("id") or channel.get("_id"), "url": url}
    if not found:
        raise RuntimeError("No matching direct Pluto test URLs; no file generated")
    output = ["#EXTM3U"]
    for name in sorted(found):
        output += [f'#EXTINF:-1,{name} (direct Pluto test)', found[name]["url"]]
    (ROOT / "pluto-test.m3u").write_text("\n".join(output) + "\n", encoding="utf-8")
    (ROOT / "pluto-test-audit.json").write_text(json.dumps({"found": list(found), "missing": sorted(TEST_NAMES - set(found))}, indent=2) + "\n", encoding="utf-8")
    print("Generated isolated Pluto test playlist:", len(found), "channels; missing:", sorted(TEST_NAMES - set(found)))

if __name__ == "__main__":
    main()
