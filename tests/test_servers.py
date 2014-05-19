import os
import shutil
import tempfile
import unittest
import zipfile
from bukkitadmin.servers import Server, InvalidServerJar


class ServerTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir =  tempfile.mkdtemp("server-test")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def create_fake_craftbukkit(self, subdir=None, name="craftbukkit.jar", manifest=None):
        if subdir is None:
            subdir = self.tmpdir
        else:
            subdir = self.mkdtemp(dir=self.tmpdir)
        if manifest is None:
            manifest = {}
        f = os.path.join(subdir, name)
        zf = zipfile.ZipFile(f, mode='w')
        zf.writestr("META-INF/MANIFEST.MF", "\n".join([": ".join(pair) for pair in manifest.iteritems()]))
        zf.close()

    def test_validate_missing(self):
        self.assertRaises(InvalidServerJar, Server, 'test', os.path.join(self.tmpdir, "craftbukkit.jar"), validate=True)

    def test_validate_bad_jar(self):
        self.create_fake_craftbukkit()
        self.assertRaises(InvalidServerJar, Server, 'test', os.path.join(self.tmpdir, "craftbukkit.jar"), validate=True)

    def test_validate_good_jar(self):
        self.create_fake_craftbukkit(manifest={"Specification-Title": "Bukkit"})
        server = Server('test', os.path.join(self.tmpdir, "craftbukkit.jar"), validate=True)
        self.assertIsNotNone(server)



