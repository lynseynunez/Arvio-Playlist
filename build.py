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
EPGS = ["https://raw.githubusercontent.com/lynseynunez/Arvio-Playlist/main/epg.xml.gz"]
PLUTO_CURATED_FEED = "https://raw.githubusercontent.com/lynseynunez/pluto-tv/main/output/plutotv_us.m3u8"
PRIORITY = {"Pluto Direct": 0, "Samsung": 1, "Pluto": 2, "Roku": 3, "Tubi": 4, "Plex": 5}

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
    curation = json.loads((ROOT / "pluto-curation.json").read_text(encoding="utf-8"))
    approved = set(curation["keep"])
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
            # The approved Pluto allowlist applies across providers, avoiding reintroduced removals.
            index.setdefault(norm(channel["name"]), []).append(channel)
    request = Request(PLUTO_CURATED_FEED, headers={"User-Agent": "ArvioPlaylist/1.0"})
    with urlopen(request, timeout=90) as response:
        curated_source = parse(response.read().decode("utf-8-sig"), "Pluto")
    source_names = {channel["name"] for channel in curated_source}
    if len(source_names) < 300:
        raise RuntimeError("Pluto source looks incomplete; preserving the previous playlist")
    excluded_names = {norm(name) for name in source_names - approved}
    # Drop all nonapproved Pluto names, including copies offered by other providers.
    for name in list(index):
        if name in excluded_names:
            del index[name]
    for channel in curated_source:
        if channel["name"] in approved:
            # Prefer direct, freshly generated Pluto URLs over third-party Pluto redirects.
            channel["provider"] = "Pluto Direct"
            index.setdefault(norm(channel["name"]), []).append(channel)
    counts["Curated Pluto"] = sum(c["name"] in approved for c in curated_source)
    if counts["Curated Pluto"] != len(approved):
        raise RuntimeError("Curated Pluto source incomplete; preserving previous playlist")

    # Import only the independently tested IPTV-org channels; leave Pluto intact.
    wanted = {
        "Sonic TV": ("sonic tv",),
        "Toonami Aftermath West": ("toonami aftermath west",),
        "NickOnline HD": ("nickonline hd", "nickonline"),
        "Tooncast": ("tooncast",),
    }
    extra_found = {}
    try:
        request = Request("https://iptv-org.github.io/iptv/categories/animation.m3u",
                          headers={"User-Agent": "ArvioPlaylist/1.0"})
        with urlopen(request, timeout=45) as response:
            extra_channels = parse(response.read().decode("utf-8-sig"), "IPTV-org")
        print("IPTV-org entries:", len(extra_channels))
        for label, variants in wanted.items():
            matches = [c for c in extra_channels if any(norm(c["name"]).startswith(norm(v)) for v in variants)]
            if matches:
                extra_found[label] = matches[0]
                print(f"IPTV-org selected {label}: {matches[0]['name']}")
            else:
                print(f"IPTV-org channel not found: {label}")
    except Exception as exc:
        print(f"IPTV-org unavailable; preserving existing lineup: {exc}")

    # Additional channels confirmed playable by the user in IPTV-org Entertainment.
    entertainment_wanted = {
        "A&E": ("A&E", "A and E"),
        "E! (United States) East": ("E! (United States) East", "E! East"),
        "Game Show Network": ("Game Show Network", "GSN"),
        "ION Plus": ("ION Plus",),
        "MTV (United States)": ("MTV (United States)", "MTV US"),
        "Plex TV": ("Plex TV",),
        "TMZ": ("TMZ",),
        "Wipeout Xtra": ("Wipeout Xtra",),
    }
    entertainment_found = {}
    request = Request("https://iptv-org.github.io/iptv/categories/entertainment.m3u",
                      headers={"User-Agent": "ArvioPlaylist/1.0"})
    with urlopen(request, timeout=60) as response:
        entertainment_channels = parse(response.read().decode("utf-8-sig"), "IPTV-org Entertainment")
    print("IPTV-org Entertainment entries:", len(entertainment_channels))
    for label, variants in entertainment_wanted.items():
        matches = [c for c in entertainment_channels
                   if any(norm(c["name"]) == norm(v) or
                          re.fullmatch(re.escape(v) + r"\s*\(\d+p\)", c["name"], re.I)
                          for v in variants)]
        if matches:
            entertainment_found[label] = matches[0]
            print(f"Entertainment selected {label}: {matches[0]['name']}")
        else:
            print(f"Entertainment channel not found: {label}")
    if len(entertainment_found) != len(entertainment_wanted):
        raise RuntimeError("Entertainment selections incomplete; preserving previous playlist: " +
                           ", ".join(set(entertainment_wanted) - set(entertainment_found)))

    output = ['#EXTM3U url-tvg="' + ",".join(EPGS) + '"']
    audit = []
    seen = set()
    published = 0
    selections["Approved Pluto"] = "; ".join(curation["keep"])
    for category, text in selections.items():
        for requested in text.split("; "):
            target = aliases.get(requested, requested)
            options = index.get(norm(target), [])
            # Approved Pluto channels must retain the EXACT entry and stream URL from
            # the independently generated Pluto playlist, never a Samsung or
            # BuddyChewChew substitute that happens to share the same name.
            if target in approved:
                options = [item for item in options if item["provider"] == "Pluto Direct"]
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
    # Naruto Shippuden is excluded until the 403 is resolved.
    # Nickelodeon Pluto TV already exists, so don't create a duplicate.
    for label, channel in extra_found.items():
        if norm(label) in seen:
            continue
        group = "Anime & Animation" if label in ("Sonic TV", "Toonami Aftermath West") else "Kids & Family"
        output.extend([set_group(channel["extinf"], group), channel["url"]])
        seen.add(norm(label))
        published += 1
        audit.append({"category": "IPTV-org additions", "requested": label,
                      "status": "exact", "matched": channel["name"],
                      "provider": "IPTV-org", "tvg_id": channel["tvg_id"]})
    for label, channel in entertainment_found.items():
        if norm(label) in seen or norm(channel["name"]) in seen:
            continue
        group = ("Game Shows" if label in ("Game Show Network", "Wipeout Xtra")
                 else "Music" if label == "MTV (United States)"
                 else "Reality TV" if label in ("A&E", "E! (United States) East", "TMZ")
                 else "TV Shows & Classics")
        output.extend([set_group(channel["extinf"], group), channel["url"]])
        seen.add(norm(label))
        seen.add(norm(channel["name"]))
        published += 1
        audit.append({"category": "IPTV-org Entertainment additions", "requested": label,
                      "status": "exact", "matched": channel["name"],
                      "provider": "IPTV-org Entertainment", "tvg_id": channel["tvg_id"]})
    if published < 100:
        raise RuntimeError(f"Only {published} matches; refusing to replace previous playlist")
    missing_curated = [name for name in curation["keep"] if norm(name) not in seen]
    if missing_curated:
        raise RuntimeError("Approved Pluto channels missing: " + "; ".join(missing_curated))
    (ROOT / "arvio.m3u").write_text("\n".join(output) + "\n", encoding="utf-8")
    (ROOT / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Published {published} channels; source entries: {counts}")
    print("Missing:", "; ".join(row["requested"] for row in audit if row["status"] == "missing"))

if __name__ == "__main__":
    main()
