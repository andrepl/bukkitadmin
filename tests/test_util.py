import unittest

from bukkitadmin.util import format_as_kwargs


class UtilTestCase(unittest.TestCase):
    def test_format_kwargs(self):
        self.assertEqual("k1='one', k2=2",
                         format_as_kwargs(dict(k1='one', k2=2), priority_keys=('k1',)))