import os
import shutil
import tempfile
import unittest
import yaml
import zipfile

from bukkitadmin.plugins import PluginFile

class PluginFileTest(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp("bukkitadmin-tests")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def create_dummy_jar(self, filename=None, **kwargs):
        if filename is None:
            filename = "TestPlugin.jar"
        zf = zipfile.ZipFile(os.path.join(self.tmpdir, filename), mode='w')
        defaults = dict(name="TestPlugin", version="1.0-SNAPSHOT", author='metalhedd', main='me.metalhedd.TestPlugin')
        defaults.update(kwargs)
        zf.writestr("plugin.yml", yaml.dump(defaults))
        zf.close()
        return os.path.join(self.tmpdir, filename)

    def test_init(self):
        pf = PluginFile(self.create_dummy_jar())
        self.assertIsNotNone(pf)

    def test_required_properties(self):
        jar = PluginFile(self.create_dummy_jar())
        self.assertEqual(jar.name, "TestPlugin")
        self.assertEqual(jar.main, "me.metalhedd.TestPlugin")
        self.assertEqual(jar.authors, ["metalhedd"])
        self.assertEqual(jar.version, "1.0-SNAPSHOT")

    def test_hash_equal(self):
        jar1 = PluginFile(self.create_dummy_jar("TestPlugin1.jar"))
        jar2 = PluginFile(self.create_dummy_jar("TestPlugin2.jar"))
        self.assertEqual(jar1.shasum, jar2.shasum)

    def test_hash_not_equal(self):
        jar1 = PluginFile(self.create_dummy_jar("TestPlugin1.jar", name="StupidPlugin"))
        jar2 = PluginFile(self.create_dummy_jar("TestPlugin2.jar"))
        self.assertNotEqual(jar1.shasum, jar2.shasum)

    def test_has_no_meta(self):
        jar = PluginFile(self.create_dummy_jar())
        self.assertFalse(jar.has_meta())

    def test_set_meta(self):
        jar = PluginFile(self.create_dummy_jar())
        jar.set_meta({'source': 'bukkitdev'})
        self.assertTrue(jar.has_meta())
        self.assertEqual(jar.get_meta()['source'], 'bukkitdev')

    def test_has_correct_name(self):
        jar = PluginFile(self.create_dummy_jar())
        self.assertTrue(jar.has_correct_name())

    def test_has_incorrect_name(self):
        jar = PluginFile(self.create_dummy_jar("TestPlugin2.jar"))
        self.assertFalse(jar.has_correct_name())

    def test_rename_jar_no_meta(self):
        jar = PluginFile(self.create_dummy_jar("TestPlugin2.jar"))
        oldpath = jar.jarpath
        jar.rename_jar()
        self.assertEqual(os.path.basename(jar.jarpath), "TestPlugin.jar")
        self.assertTrue(os.path.exists(jar.jarpath))
        self.assertFalse(os.path.exists(oldpath))

    def test_rename_jar_with_meta(self):
        jar = PluginFile(self.create_dummy_jar("TestPlugin2.jar"))
        jar.set_meta({'source': 'bukkitdev'})
        self.assertTrue(jar.has_meta())
        oldpath = jar.jarpath
        oldmeta = jar.get_meta()
        jar.rename_jar()
        self.assertEqual(os.path.basename(jar.jarpath), "TestPlugin.jar")
        self.assertTrue(jar.has_meta())
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(jar.jarpath), "TestPlugin2.yml")))