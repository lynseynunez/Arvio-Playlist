import sqlite3
import unittest
import xml.etree.ElementTree as ET

from epg_aliases import apply_aliases


class AliasTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE channels (id TEXT PRIMARY KEY, xml BLOB)")
        self.db.execute("CREATE TABLE programmes (id TEXT, start TEXT, stop TEXT, xml BLOB, PRIMARY KEY(id, start, stop))")
        self.db.execute("INSERT INTO channels VALUES (?, ?)", ("source", b'<channel id="source"><display-name>TMZ</display-name></channel>'))
        self.db.execute("INSERT INTO programmes VALUES (?, ?, ?, ?)",
                        ("source", "20261012000000 +0000", "20261012010000 +0000",
                         b'<programme channel="source" start="20261012000000 +0000" stop="20261012010000 +0000"><title>TMZ LIVE</title></programme>'))

    def test_alias_keeps_source_and_changes_xml_id(self):
        result = apply_aliases(self.db, {"target": "source"})
        self.assertEqual(result["target"]["programmes_added"], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM programmes").fetchone()[0], 2)
        xml = self.db.execute("SELECT xml FROM programmes WHERE id='target'").fetchone()[0]
        self.assertEqual(ET.fromstring(xml).get("channel"), "target")
        self.assertEqual(ET.fromstring(self.db.execute("SELECT xml FROM channels WHERE id='target'").fetchone()[0]).get("id"), "target")

    def test_does_not_override_existing_guide(self):
        self.db.execute("INSERT INTO programmes VALUES (?, ?, ?, ?)", ("target", "a", "b", b'<programme channel="target"/>'))
        result = apply_aliases(self.db, {"target": "source"})
        self.assertEqual(result["target"]["status"], "already_covered")

    def test_missing_source_does_not_create_empty_guide(self):
        result = apply_aliases(self.db, {"target": "missing"})
        self.assertEqual(result["target"]["status"], "source_channel_missing")
        self.assertFalse(self.db.execute("SELECT 1 FROM channels WHERE id='target'").fetchone())


if __name__ == "__main__":
    unittest.main()
