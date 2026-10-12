#!/usr/bin/env python3
"""Add only verified-name US linear TV schedules to isolated Arvio preview."""
import gzip
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

FEEDS = [
 "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_guide.xml.gz",
 "https://vcicio.github.io/US-EPG/merged_epg.xml.gz",
 "https://iptv-org.github.io/epg/guides/us/tvguide.com.epg.xml.gz",
 "https://iptv-org.github.io/epg/guides/us-az/tvtv.us.epg.xml",
]
TARGETS = {
 "AE.us@East": {"aande","aetv","aandeeast","aetelevision","aeeast","ae"},
 "E.us@East": {"eentertainment","eentertainmenttelevision","eentertainmenteast"},
 "MTV.us@East": {"mtv","mtveast","mtvusa","mtveastern"},
 "NickOnline.br@HD": {"nickonlinehd","nickonline"},
 "PLEXTV.cm@SD": {"plextv","plextvcm"},
 "SonicTV.us@SD": {"sonictv"},
 "ToonamiAftermath.us@West": {"toonamiaftermath","toonamiaftermathwest"},
 "Tooncast.us@SD": {"tooncast"},
}
def norm(s):
 return re.sub(r"[^a-z0-9]","",s.lower())
def main():
 src=Path("epg-preview.xml.gz")
 existing=set()
 with gzip.open(src,"rb") as stream:
  for _,e in ET.iterparse(stream,events=("end",)):
   if e.tag=="programme": existing.add(e.get("channel"))
   if e.tag in ("programme","channel"): e.clear()
 remaining={k:v for k,v in TARGETS.items() if k not in existing}
 report={}
 # Record the original playlist stream provider for each unresolved channel.
 playlist=Path("arvio.m3u")
 if playlist.exists():
  lines=playlist.read_text(encoding="utf-8",errors="replace").splitlines()
  for idx,line in enumerate(lines):
   if line.startswith("#EXTINF:"):
    for target in remaining:
     if f'tvg-id="{target}"' in line:
      report.setdefault("stream_providers",{})[target]={"metadata":line[:450],"stream":lines[idx+1].split("?")[0][:300] if idx+1<len(lines) else ""}
 additions=[]
 for url in FEEDS:
  if not remaining: break
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"ArvioEPGPreview/1.0"})
   with urllib.request.urlopen(req,timeout=90) as resp:
    guide=resp.read()
   if guide[:2]==bytes((31,139)): guide=gzip.decompress(guide)
   root=ET.fromstring(guide)
   names={}
   for ch in root.findall("channel"):
    cid=ch.get("id")
    names[cid]=[norm(x.text or "") for x in ch.findall("display-name")] + [norm(cid or "")]
   for target, accepted in list(remaining.items()):
    matches=[cid for cid,labels in names.items() if any(x in accepted for x in labels)]
    if len(matches)!=1:
     candidates=[{"id":cid,"names":[x.text for x in ch.findall("display-name")]} for ch in root.findall("channel") for cid in [ch.get("id")] if any(any(t in n for t in accepted if len(t)>=6) for n in names.get(cid,[]))][:15]
     report.setdefault(target,{"status":"ambiguous_or_missing","feeds":[]})["feeds"].append({"url":url,"matches":matches[:8],"candidates":candidates})
     continue
    cid=matches[0]
    programmes=[e for e in root.findall("programme") if e.get("channel")==cid]
    if len(programmes)<4:
     report[target]={"status":"insufficient_programmes","feed":url,"count":len(programmes)}
     continue
    channel=next(ch for ch in root.findall("channel") if ch.get("id")==cid)
    channel.set("id",target)
    additions.append(ET.tostring(channel,encoding="utf-8")+b"\n")
    for e in programmes:
     e.set("channel",target)
     additions.append(ET.tostring(e,encoding="utf-8")+b"\n")
    report[target]={"status":"added","feed":url,"source_id":cid,"count":len(programmes)}
    del remaining[target]
  except Exception as exc:
   report[url]={"status":"source_error","error":str(exc)[:200]}
 if additions:
  with gzip.open(src,"rb") as stream: data=stream.read()
  pos=data.rfind(b"</tv>")
  if pos<0: raise RuntimeError("Malformed original preview")
  with gzip.open(src,"wb",compresslevel=6) as stream:
   stream.write(data[:pos]+b"".join(additions)+data[pos:])
 Path("epg-extra-source-report.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps(report,indent=2))
if __name__=="__main__": main()
