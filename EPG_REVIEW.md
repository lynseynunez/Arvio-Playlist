# EPG candidate review

Source: GitHub Actions diagnostic run 38191142709.

Of 228 playlist channels, 216 have programme coverage and 12 do not. All 228 channel logo URLs returned an image response during the audit.

## Promising matches requiring schedule verification

- Sonic TV: exact-name guide candidate; verify channel identity.
- Game Show Network: strong guide-name candidate; stream is marked Not 24/7, so verify schedule alignment.
- ION Plus: multiple exact-name guide candidates; compare listings before choosing.
- TMZ: multiple exact-name guide candidates; verify the stream is the same channel.
- Wipeout Xtra: multiple exact-name guide candidates; compare listings.

## Lower-confidence match

- PLEX TV: similar-name candidates, but the channel identity is ambiguous. Do not automatically map.

## No candidate from current matching threshold

- Toonami Aftermath West
- NickOnline HD
- Tooncast
- A&E
- E! East
- MTV East

All suggestions are advisory only. No live playlist, channel IDs, streams or guide data have been modified. Next step: compare guide programme titles and time windows to channel-specific sources before proposing aliases.
