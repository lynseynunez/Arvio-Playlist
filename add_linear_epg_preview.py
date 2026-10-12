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
 "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
 "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
]
TARGETS = {
 "AE.us@East": {"aande","aetv","aandeeast","aetelevision"},
 "E.us@East": {"eentertainment","eentertainmenttelevision","eentertainmenteast"},
 "MTV.us@East": {"mtv","mtveast","mtvusa","mtveastern"},
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
    names[cid]=[norm(x.text or "") for x in ch.findall("display-name")]
   for target, accepted in list(remaining.items()):
    matches=[cid for cid,labels in names.items() if any(x in accepted for x in labels)]
    if len(matches)!=1:
     report[target]={"status":"ambiguous_or_missing","feed":url,"matches":matches[:8]}
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
