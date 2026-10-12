"""Explicit, conservative XMLTV aliases; never alter playlist tvg-id values."""
import xml.etree.ElementTree as ET

# Source IDs are provisional until independently checked against the live streams.
# Keep disabled by default. Enable only after confirming schedule alignment.
REVIEWED_ALIASES = {
    "TMZ.us@SD": "USBD70000213",
}

def apply_aliases(db, aliases):
    """Duplicate source XMLTV rows under playlist IDs; return per-alias audit."""
    results = {}
    for target, source in aliases.items():
        if target == source:
            results[target] = {"status": "same_id"}
            continue
        if db.execute("SELECT 1 FROM programmes WHERE id=? LIMIT 1", (target,)).fetchone():
            results[target] = {"status": "already_covered"}
            continue
        row = db.execute("SELECT xml FROM channels WHERE id=?", (source,)).fetchone()
        if row is None:
            results[target] = {"status": "source_channel_missing", "source": source}
            continue
        entries = db.execute("SELECT start, stop, xml FROM programmes WHERE id=?", (source,)).fetchall()
        if not entries:
            results[target] = {"status": "source_programmes_missing", "source": source}
            continue
        channel = ET.fromstring(row[0])
        channel.set("id", target)
        db.execute("INSERT OR IGNORE INTO channels VALUES (?, ?)",
                   (target, ET.tostring(channel, encoding="utf-8")))
        added = 0
        for start, stop, xml in entries:
            programme = ET.fromstring(xml)
            programme.set("channel", target)
            cur = db.execute("INSERT OR IGNORE INTO programmes VALUES (?, ?, ?, ?)",
                             (target, start, stop, ET.tostring(programme, encoding="utf-8")))
            added += cur.rowcount
        results[target] = {"status": "aliased", "source": source, "programmes_added": added}
    db.commit()
    return results
