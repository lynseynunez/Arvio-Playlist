#!/usr/bin/env python3
"""Create a categorized preview playlist and a non-destructive stream health report."""
import argparse
import concurrent.futures
import json
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

RULES = [
 ("Anime & Animation", r"anime|naruto|boruto|inuyasha|one piece|jojo|toonami|tooncast|crunchyroll|hidive|retrocrush|sailor moon"),
 ("Kids & Family", r"kids|nick|dora|pokemon|pokémon|peppa|garfield|lego|cartoon|turtles|icarly|power rangers"),
 ("Horror & Thriller", r"horror|terror|thriller|monsters|scary|halloween"),
 ("Sci-Fi & Fantasy", r"sci.fi|science fiction|stargate|charmed|supernatural|fantasy"),
 ("Movies", r"movie|cinema|film|flick|paramount|shout"),
 ("Crime & Drama", r"crime|criminal|law & order|walking dead|drama|degrassi|narcos"),
 ("Comedy", r"comedy|sitcom|funny|failarmy|afv|laugh"),
 ("Reality & Competition", r"reality|competition|survivor|big brother|top gear|storage wars|hell.s kitchen|bar rescue|ink master|challenge"),
 ("Gaming", r"gaming|esports|team liquid|pixel world"),
 ("Classic TV", r"classic|retro tv|mission impossible|21 jump street"),
]
def entries(path):
    lines=path.read_text(encoding="utf-8-sig").splitlines()
    header=lines[0]
    items=[]
    for i,line in enumerate(lines):
        if line.startswith("#EXTINF:") and i+1<len(lines):
            items.append((line,lines[i+1].strip()))
    return header,items

def category(meta):
    name=meta.rsplit(",",1)[-1].strip()
    original=re.search(r'group-title="([^"]*)"',meta)
    original=original.group(1) if original else "Other"
    for group,pattern in RULES:
        if re.search(pattern,name,re.I):return group
    return original

def probe(item):
    meta,url=item
    name=meta.rsplit(",",1)[-1].strip()
    cid=re.search(r'tvg-id="([^"]*)"',meta)
    result={"name":name,"tvg_id":cid.group(1) if cid else "","host":urlsplit(url).hostname,"status":"unknown"}
    if not url.startswith(("https://","http://")):
        result["status"]="invalid_url";return result
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Range":"bytes=0-2047"})
        with urllib.request.urlopen(req,timeout=9) as response:
            sample=response.read(2048)
            result["http_status"]=response.status
            if b"#EXTM3U" in sample or b"#EXT-X-" in sample:
                result["status"]="playlist_accessible"
            elif sample:
                result["status"]="reachable_unverified"
            else:result["status"]="empty_response"
    except urllib.error.HTTPError as e:
        result["http_status"]=e.code
        result["status"]="restricted_or_expired" if e.code in (401,403,404,410,429) else "http_error"
    except Exception as e:
        result["status"]="network_error"
        result["error"]=type(e).__name__
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="arvio.m3u")
    p.add_argument("--output",default="arvio-smart-preview.m3u")
    p.add_argument("--report",default="stream-health-preview.json")
    p.add_argument("--check-streams",action="store_true")
    a=p.parse_args()
    header,items=entries(Path(a.input))
    grouped={}
    for meta,url in items:
        group=category(meta)
        updated=re.sub(r'group-title="[^"]*"',f'group-title="{group}"',meta)
        if 'group-title=' not in updated:updated=updated.replace('#EXTINF:-1',f'#EXTINF:-1 group-title="{group}"',1)
        grouped.setdefault(group,[]).append((updated,url))
    output=[header]
    for group in grouped:
        for meta,url in grouped[group]:output.extend([meta,url])
    Path(a.output).write_text("\n".join(output)+"\n",encoding="utf-8")
    report={"generated_utc":datetime.now(timezone.utc).isoformat(),"channels":len(items),"categories":dict(Counter({k:len(v) for k,v in grouped.items()})),"note":"HTTP probes are not playback tests. No channels are removed or replaced."}
    if a.check_streams:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(probe,items))
        report["status_counts"]=dict(Counter(x["status"] for x in results))
        report["streams"]=results
    Path(a.report).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="streams"},indent=2))

if __name__=="__main__":main()
