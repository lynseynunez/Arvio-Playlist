#!/usr/bin/env python3
"""Generate a curated Arvio M3U from Samsung, Pluto, Plex, Roku and Tubi."""
import json
import re
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
BASE = "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/"
FEEDS = {"Samsung": BASE + "samsungtvplus_us.m3u", "Pluto": BASE + "plutotv_us.m3u",
         "Roku": BASE + "roku_all.m3u", "Tubi": BASE + "tubi_all.m3u",
         "Plex": BASE + "plex_us.m3u"}
EPGS = ["https://i.mjh.nz/SamsungTVPlus/us.xml.gz", "https://i.mjh.nz/PlutoTV/us.xml.gz"]
PRIORITY = {"Samsung": 0, "Pluto": 1, "Roku": 2, "Tubi": 3, "Plex": 4}

CATEGORY_MAP = {
    "Anime": "Anime & Animation",
    "Movies": "Movies",
    "TV shows & classics": "TV Shows & Classics",
    "Kids & family": "Kids & Family",
    "Comedy": "Comedy",
    "Reality TV": "Reality TV",
    "Sports": "Sports",
    "Food & home": "Food & Home",
    "Music": "Music",
    "Game shows": "Game Shows",
}
NEWS_TERMS = ("news", "weather", "accuweather", "livenow")
SCIENCE_TERMS = ("nature", "wild life", "wildlife", "clarity 4k", "pbs nature")

def category_for(category, requested):
    if requested in ("Pluto TV Horror", "Pluto TV Thrillers", "FilmRise Horror",
                     "The Asylum", "FreeTV Horror"):
        return "Horror"
    if category == "Other":
        lower = requested.casefold()
        if any(term in lower for term in NEWS_TERMS):
            return "News & Weather"
        if any(term in lower for term in SCIENCE_TERMS):
            return "Science & Nature"
        return "Gaming & Entertainment"
    if category == "Additional channels":
        if requested in ("Anime 24/7", "Animation+"):
            return "Anime & Animation"
        if requested in ("FilmRise Comedy",):
            return "Comedy"
        return "Movies"
    return CATEGORY_MAP.get(category, "Gaming & Entertainment")

def set_group(extinf, category):
    # Keep all original upstream attributes, including tvg-id and tvg-logo.
    safe = category.replace('"', "")
    if re.search(r'group-title="[^"]*"', extinf):
        return re.sub(r'group-title="[^"]*"', lambda _: f'group-title="{safe}"', extinf, count=1)
    return extinf.replace("#EXTINF:", f'#EXTINF: group-title="{safe}" ', 1)


def norm(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in value if c.isascii() and c.isalnum())

def parse(text, provider):
    lines = text.splitlines()
    channels = []
    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        name = line.rsplit(",", 1)[-1].strip()
        url = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if not url.startswith(("https://", "http://")):
            continue
        found = re.search(r'tvg-id="([^"]+)"', line)
        channels.append({"name": name, "provider": provider, "extinf": line,
                         "url": url, "tvg_id": found.group(1) if found else ""})
    return channels

def main():
    selections = json.loads((ROOT / "selections.json").read_text(encoding="utf-8"))
    aliases = json.loads((ROOT / "aliases.json").read_text(encoding="utf-8"))
    index = {}
    counts = {}
    for provider, feed in FEEDS.items():
        request = Request(feed, headers={"User-Agent": "ArvioPlaylist/1.0"})
        with urlopen(request, timeout=45) as response:
            channels = parse(response.read().decode("utf-8-sig"), provider)
        counts[provider] = len(channels)
        if len(channels) < 50:
            raise RuntimeError(f"{provider} source appears incomplete: {len(channels)} channels")
        for channel in channels:
            index.setdefault(norm(channel["name"]), []).append(channel)

    output = ['#EXTM3U url-tvg="' + ",".join(EPGS) + '"']
    audit = []
    seen = set()
    published = 0
    for category, text in selections.items():
        for requested in text.split("; "):
            target = aliases.get(requested, requested)
            options = index.get(norm(target), [])
            options.sort(key=lambda item: (PRIORITY[item["provider"]], item["name"]))
            match = options[0] if options else None
            audit.append({"category": category, "requested": requested,
                          "status": ("approved-alias" if requested in aliases else "exact") if match else "missing",
                          "matched": match["name"] if match else None,
                          "provider": match["provider"] if match else None,
                          "tvg_id": match["tvg_id"] if match else None})
            if match and norm(match["name"]) not in seen:
                output.extend([set_group(match["extinf"], category_for(category, requested)), match["url"]])
                seen.add(norm(match["name"]))
                published += 1
    if published < 60:
        raise RuntimeError(f"Only {published} matches; refusing to replace previous playlist")
    (ROOT / "arvio.m3u").write_text("\n".join(output) + "\n", encoding="utf-8")
    (ROOT / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Published {published} channels; source entries: {counts}")
    print("Missing:", "; ".join(row["requested"] for row in audit if row["status"] == "missing"))

if __name__ == "__main__":
    main()
