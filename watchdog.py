#!/usr/bin/env python3
"""Check production assets and refresh health; manage one actionable GitHub issue."""
import gzip
import json
import os
import urllib.request
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

repo = os.environ["GITHUB_REPOSITORY"]
token = os.environ["GITHUB_TOKEN"]
base = f"https://api.github.com/repos/{repo}"
headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "Arvio-Watchdog"}
def api(path, data=None, method=None):
    req = urllib.request.Request(base + path, headers=headers, method=method, data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=30) as res:
        body = res.read()
        return json.loads(body) if body else None

errors = []
try:
    runs = api("/actions/workflows/update.yml/runs?per_page=15")["workflow_runs"]
    completed = next((r for r in runs if r["status"] == "completed"), None)
    if not completed:
        errors.append("No completed production refresh workflow found")
    else:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(completed["created_at"].replace("Z", "+00:00"))).total_seconds() / 3600
        if age > 12:
            errors.append(f"Latest completed refresh is {age:.1f} hours old")
        if completed["conclusion"] != "success":
            errors.append(f"Latest refresh failed: {completed['html_url']}")
except Exception as exc:
    errors.append(f"Cannot check workflow: {exc}")

raw = f"https://raw.githubusercontent.com/{repo}/main/"
playlist = ""
try:
    with urllib.request.urlopen(raw + "arvio.m3u", timeout=30) as res:
        playlist = res.read().decode("utf-8-sig")
    count = sum(s.startswith("#EXTINF:") for s in playlist.splitlines())
    if not playlist.lstrip().startswith("#EXTM3U") or count < 100:
        errors.append(f"Published playlist invalid ({count} channels)")
except Exception as exc:
    errors.append(f"Published playlist inaccessible: {exc}")
# Pluto channels play through token-free redirect links; make sure the redirect host still
# hands back a real stream manifest. A couple of failures out of a sample may just be a flaky
# channel, so only a majority failing is reported.
try:
    redirects = [l.strip() for l in playlist.splitlines() if l.startswith("https://jmp2.uk/plu-")]
    sample = redirects[:: max(1, len(redirects) // 5)][:5]
    failed = []
    for link in sample:
        try:
            req = urllib.request.Request(link, headers={"User-Agent": "Arvio-Watchdog"})
            with urllib.request.urlopen(req, timeout=30) as res:
                if not res.read(200).lstrip().startswith(b"#EXTM3U"):
                    failed.append(link)
        except Exception:
            failed.append(link)
    if sample and len(failed) * 2 > len(sample):
        errors.append(f"Pluto redirect links failing ({len(failed)} of {len(sample)} sampled, e.g. {failed[0]}); "
                      "Pluto channels will not play")
except Exception as exc:
    errors.append(f"Cannot check Pluto redirect links: {exc}")
try:
    with urllib.request.urlopen(raw + "epg.xml.gz", timeout=60) as res:
        guide = gzip.decompress(res.read())
    root = ET.fromstring(guide)
    if root.tag != "tv" or len(root.findall("programme")) < 1000:
        errors.append("Published guide has too few programme entries")
except Exception as exc:
    errors.append(f"Published guide inaccessible/invalid: {exc}")

title = "Arvio production health alert"
open_issues = api("/issues?state=open&per_page=100")
issue = next((x for x in open_issues if x.get("title") == title and "pull_request" not in x), None)
if errors:
    body = "Automated production checks found:\n\n" + "\n".join("- " + e for e in errors) + "\n\nThe currently published files have not been modified by this watchdog."
    if issue:
        api(f"/issues/{issue['number']}/comments", {"body": body})
    else:
        api("/issues", {"title": title, "body": body})
    raise SystemExit("\n".join(errors))
if issue:
    api(f"/issues/{issue['number']}", {"state": "closed"}, method="PATCH")
print("Production playlist, EPG, and scheduled refresh are healthy")
