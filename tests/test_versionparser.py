import unittest
from bukkitadmin.versionparser import parse_version


class VersionParserTestCase(unittest.TestCase):
    def test_snapshot_is_older(self):
        v1 = parse_version("1.0")
        v1s = parse_version("1.0-SNAPSHOT")
        self.assertLess(v1s, v1)
        self.assertGreater(v1, v1s)
