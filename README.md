# Combined Arvio TV playlist

A single curated M3U containing existing Samsung/Roku/Tubi/Plex selections plus **164 explicitly approved Pluto TV US channels**. Previously rejected Pluto channels are excluded even if another upstream provider carries a same-named entry.

## Add to Arvio

**Playlist (M3U):**
https://raw.githubusercontent.com/lynseynunez/Arvio-Playlist/main/arvio.m3u

**Combined guide (XMLTV gzip):**
https://raw.githubusercontent.com/lynseynunez/Arvio-Playlist/main/epg.xml.gz

Set the XMLTV URL as a separate EPG source in Arvio if it does not pick up the playlist's `url-tvg` header. Refresh the playlist and guide after a successful workflow run.

## Automatic updates

The **Update Arvio M3U** GitHub Actions workflow runs daily at 12:23 UTC, and can be started manually from **Actions → Update Arvio M3U → Run workflow**. It refreshes stream URLs, rebuilds the combined M3U and XMLTV guide, and commits updated `arvio.m3u`, `epg.xml.gz`, `audit.json`, and `epg-audit.json` only after successful generation.

The dedicated `lynseynunez/pluto-tv` repository updates Pluto stream URLs every six hours. The Arvio builder reads its latest output, imports only approved Pluto names, and deduplicates channels by normalized name. Where duplicate names exist, the existing provider priority is Samsung → Pluto → Roku → Tubi → Plex.

## Curation

- `pluto-curation.json`: approved 164 Pluto source names, and 14 unresolved requests tracked separately. No automatic aliases for unresolved additions.
- `selections.json`: your existing requested channels from other providers; unrelated selections remain eligible.
- `aliases.json`: existing explicit aliases.
- `audit.json`: individual matched/missing selection results.
- `epg-audit.json`: channel-level programme coverage and source health.
- `build.py`: merges providers and applies Pluto removals across duplicate names.
- `merge_epg.py`: generates a compact guide for the final M3U, matching `tvg-id` to XMLTV channel IDs.

**Guide limitations:** Matching EPG IDs does not guarantee programme listings for every new Pluto stream. Check `epg-audit.json` after the next successful run; `without_guide` lists any uncovered channels. The build will preserve the previous guide rather than publish one if required guide feeds fail or there are fewer than 100 programmes.

**Stream limitations:** Source presence does not prove every stream plays on every device or network. Existing streams and guide remain unchanged until the first successful workflow refresh.
