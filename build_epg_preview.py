#!/usr/bin/env python3
"""Create an OPTIONAL preview XMLTV guide; never modify epg.xml.gz or main.

Appends alias channel/programme nodes from existing guide data, preserving the
original guide and every existing channel ID. For user testing only.
"""
import argparse
import gzip
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from epg_aliases import REVIEWED_ALIASES

ROOT = Path(__file__).resolve().parent

def generate(source, output, aliases):
    if source.resolve() == output.resolve():
        raise ValueError("Preview output cannot overwrite the input guide")
    if not aliases:
        raise ValueError("No preview aliases configured")
    targets = set(aliases)
    wanted_sources = set(aliases.values())
    existing_channels = set()
    existing_programmes = set()
    channel_xml = {}
    programme_xml = {cid: [] for cid in wanted_sources}
    with gzip.open(source, "rb") as stream:
        for _, node in ET.iterparse(stream, events=("end",)):
            if node.tag == "channel":
                cid = node.get("id")
                if cid in targets:
                    existing_channels.add(cid)
                if cid in wanted_sources:
                    channel_xml[cid] = ET.tostring(node, encoding="utf-8")
                node.clear()
            elif node.tag == "programme":
                cid = node.get("channel")
                if cid in targets:
                    existing_programmes.add(cid)
                if cid in wanted_sources:
                    programme_xml[cid].append(ET.tostring(node, encoding="utf-8"))
                node.clear()
    additions = []
    status = {}
    for target, source_id in aliases.items():
        if target in existing_programmes:
            status[target] = {"status": "already_covered"}
            continue
        if source_id not in channel_xml or not programme_xml.get(source_id):
            status[target] = {"status": "source_missing"}
            continue
        if target not in existing_channels:
            node = ET.fromstring(channel_xml[source_id])
            node.set("id", target)
            additions.append(ET.tostring(node, encoding="utf-8") + b"\n")
        count = 0
        for raw in programme_xml[source_id]:
            node = ET.fromstring(raw)
            node.set("channel", target)
            additions.append(ET.tostring(node, encoding="utf-8") + b"\n")
            count += 1
        status[target] = {"status": "previewed", "source": source_id, "programmes": count}
    if not additions:
        raise RuntimeError("No candidate aliases could be previewed")
    # Stream-copy the existing guide and insert additions before its closing tv tag.
    with gzip.open(source, "rb") as src, gzip.open(output, "wb", compresslevel=6) as dst:
        tail = b""
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            tail += chunk
            if len(tail) > 64:
                dst.write(tail[:-64])
                tail = tail[-64:]
        match = re.search(rb"</tv>\s*$", tail)
        if not match:
            raise RuntimeError("Original XMLTV guide does not end with </tv>")
        dst.write(tail[:match.start()])
        for item in additions:
            dst.write(item)
        dst.write(tail[match.start():])
    # Reject malformed previews before publishing artifacts.
    with gzip.open(output, "rb") as stream:
        for _, node in ET.iterparse(stream, events=("end",)):
            if node.tag in ("channel", "programme"):
                node.clear()
    return status

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "epg.xml.gz")
    parser.add_argument("--output", type=Path, default=ROOT / "epg-preview.xml.gz")
    args = parser.parse_args()
    result = generate(args.source, args.output, REVIEWED_ALIASES)
    print(json.dumps({"preview_only": True, "original_guide_unchanged": True, "results": result}, indent=2))
