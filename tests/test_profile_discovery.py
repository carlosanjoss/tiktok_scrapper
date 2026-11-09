import json
import tempfile
import unittest
from pathlib import Path

from main import save_profile_manifest
from tiktokcomment.profile_discovery import canonical_video_url, extract_profile_username


class ProfileDiscoveryTests(unittest.TestCase):
    def test_extracts_profile_username(self):
        self.assertEqual(extract_profile_username("@lulaoficial"), "lulaoficial")
        self.assertEqual(
            extract_profile_username("https://www.tiktok.com/@lulaoficial?lang=pt-BR"),
            "lulaoficial",
        )
        self.assertIsNone(extract_profile_username("https://example.com/@lulaoficial"))

    def test_normalizes_video_url(self):
        self.assertEqual(
            canonical_video_url("https://www.tiktok.com/@perfil/video/7418294751977327878?lang=pt"),
            "https://www.tiktok.com/@perfil/video/7418294751977327878",
        )
        self.assertIsNone(canonical_video_url("https://www.tiktok.com/@perfil"))

    def test_saves_profile_manifest(self):
        videos = ["https://www.tiktok.com/@perfil/video/7418294751977327878"]
        with tempfile.TemporaryDirectory() as directory:
            path = save_profile_manifest("https://www.tiktok.com/@perfil", videos, directory)
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(payload["username"], "perfil")
        self.assertEqual(payload["video_count"], 1)
        self.assertEqual(payload["video_urls"], videos)


if __name__ == "__main__":
    unittest.main()
