# Custom Arvio TV playlist

A curated Samsung TV Plus + Pluto TV US playlist for Arvio.

## Playlist URL

https://raw.githubusercontent.com/lynseynunez/Arvio-Playlist/main/arvio.m3u

Add this URL as an M3U playlist in Arvio. The playlist contains selected channels only, using Samsung when both providers carry the same channel. Each entry retains its original stream URL, logo and tvg-id.

## Automatic updates

The GitHub Actions workflow at `.github/workflows/update.yml` runs daily at 12:23 UTC and can also be run manually: **Actions → Update Arvio M3U → Run workflow**. The workflow rebuilds `arvio.m3u` and `audit.json` from current BuddyChewChew US source files.

## Edit your channels

- `selections.json`: all 120 original requests, organized by category.
- `aliases.json`: approved channel-name substitutions; currently empty. Do not add a mapping until you've confirmed the channel.
- `alias-candidates.json`: suggested substitutions for manual review only.
- `audit.json`: shows matched and missing selections from the last build.
- `build.py`: generates the playlist and preserves upstream channel metadata.

The playlist only includes verified name matches unless you explicitly add an alias. A missing channel remains listed in `audit.json`, not silently replaced.

## Guide data

The playlist includes both EPG sources in its M3U header:
- https://i.mjh.nz/SamsungTVPlus/us.xml.gz
- https://i.mjh.nz/PlutoTV/us.xml.gz

If Arvio needs an EPG configured separately, add those URLs in its EPG settings. Playback depends on third-party stream availability and any service restrictions; playlist generation alone does not guarantee every channel plays.
