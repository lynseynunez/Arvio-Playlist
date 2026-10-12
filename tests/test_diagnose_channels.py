import gzip
import json
import tempfile
import unittest
from pathlib import Path
from diagnose_channels import normalize, read_playlist, read_guide, suggestions, main

class DiagnosticTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize("ION Plus (1080p)"), "ionplus")
        self.assertEqual(normalize("ION Plus"), "ionplus")

    def test_playlist_and_guide_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            playlist = base / "test.m3u"
            guide = base / "test.xml.gz"
            playlist.write_text('#EXTM3U\n#EXTINF:-1 tvg-id="ion" tvg-logo="https://example.org/logo.png" group-title="TV",ION Plus (1080p)\nhttps://example.org/stream.m3u8\n', encoding="utf-8")
            with gzip.open(guide, "wb") as out:
                out.write(b'<tv><channel id="ion"><display-name>ION Plus</display-name></channel><programme channel="ion" start="20261011000000 +0000" stop="20261011010000 +0000"><title>Test</title></programme></tv>')
            channels = read_playlist(playlist)
            names, covered = read_guide(guide)
            self.assertEqual(len(channels), 1)
            self.assertEqual(channels[0]["tvg_id"], "ion")
            self.assertIn("ion", covered)
            self.assertEqual(names["ion"], ["ION Plus"])
            self.assertEqual(suggestions({"name": "ION Plus (1080p)", "tvg_id": "wrong"}, names, covered)[0]["id"], "ion")

if __name__ == "__main__":
    unittest.main()
