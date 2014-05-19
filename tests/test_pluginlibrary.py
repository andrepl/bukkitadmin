import os
import random
import shutil
import string
import tempfile
import unittest
import yaml
import zipfile
from bukkitadmin import bukkitdev, jenkins
from bukkitadmin.plugins import Library, PluginFile, PluginNotFound


class PluginLibraryTest(unittest.TestCase):

    def create_dummy_jar(self, filename=None, **kwargs):
        if filename is None:
            filename = "TestPlugin.jar"
        zf = zipfile.ZipFile(os.path.join(self.tmpdir, filename), mode='w')
        defaults = dict(name="TestPlugin", version="1.0-SNAPSHOT", author='metalhedd', main='me.metalhedd.TestPlugin')
        defaults.update(kwargs)
        zf.writestr("plugin.yml", yaml.dump(defaults))
        zf.close()
        return os.path.join(self.tmpdir, filename)

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp("bukkitadmin-tests")
        jar1 = PluginFile(self.create_dummy_jar("Plugin1.jar", name="Plugin1"))
        jar2 = PluginFile(self.create_dummy_jar("Plugin2.jar", name="Plugin2"))
        jar3 = PluginFile(self.create_dummy_jar("Plugin3.jar", name="Plugin3"))

        jar1.set_meta(dict(source='bukkitdev'))
        jar2.set_meta(dict(source='bukkitdev'))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_init(self):
        lib = Library(self.tmpdir)
        self.assertEqual(lib.path, self.tmpdir)
        self.assertEqual(len(lib.plugins), 3)
        self.assertEqual(len(lib.sources), 1)

    def test_get_plugin(self):
        lib = Library(self.tmpdir)
        p = lib.get_plugin("Plugin1")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "Plugin1")

    def test_get_plugin_doesnt_exist(self):
        lib = Library(self.tmpdir)
        p = lib.get_plugin("Plugin4")
        self.assertIsNone(p)

    def test_load_sources(self):
        sources_yml = os.path.join(self.tmpdir, ".sources.yml")
        with open(sources_yml, 'w') as sourcesf:
            yaml.dump({'minevsmine': {'type': 'jenkins', 'host': 'ci.minevsmine.com'}}, sourcesf)
        lib = Library(self.tmpdir)
        self.assertEqual(len(lib.sources), 2)
        self.assertIsInstance(lib.sources['bukkitdev'], bukkitdev.PluginSource)
        self.assertIsInstance(lib.sources['minevsmine'], jenkins.PluginSource)
        self.assertEqual(lib.sources['minevsmine'].host, 'ci.minevsmine.com')
        self.assertEqual(lib.sources['minevsmine'].serialize(), {'type': 'jenkins', 'host': 'ci.minevsmine.com'})

    def test_save_sources(self):
        sources_yml = os.path.join(self.tmpdir, ".sources.yml")
        with open(sources_yml, 'w') as sourcesf:
            yaml.dump({'minevsmine': {'type': 'jenkins', 'host': 'ci.minevsmine.com'}}, sourcesf)
        lib = Library(self.tmpdir)
        self.assertEqual(len(lib.sources), 2)
        self.assertIsInstance(lib.sources['bukkitdev'], bukkitdev.PluginSource)
        self.assertIsInstance(lib.sources['minevsmine'], jenkins.PluginSource)
        self.assertEqual(lib.sources['minevsmine'].host, 'ci.minevsmine.com')
        self.assertEqual(lib.sources['minevsmine'].serialize(), {'type': 'jenkins', 'host': 'ci.minevsmine.com'})
        lib.add_source('md5', host='ci.md-5.net')
        lib.save_sources()
        with open(os.path.join(self.tmpdir, '.sources.yml')) as f:
            data = yaml.load(f)
        self.assertEqual(data, {'minevsmine': {'type': 'jenkins', 'host': 'ci.minevsmine.com'}, 'md5': {'type': 'jenkins', 'host': "ci.md-5.net"}})

    @unittest.skipIf(os.environ.get('SKIP_SLOW', None), "update_plugin_no_meta - Skipped (SLOW)")
    def test_update_plugin_no_meta(self):
        jar1 = PluginFile(self.create_dummy_jar("Instances.jar", name="Instances"))
        lib = Library(self.tmpdir)
        p = lib.get_plugin("Instances")
        self.assertIsNotNone(p)
        hash = p.shasum
        lib.update_plugin(p)
        self.assertNotEqual(hash, p.shasum)

    @unittest.skipIf(os.environ.get('SKIP_SLOW', None), "test_search_bukkitdev - Skipped (SLOW)")
    def test_search_bukkitdev(self):
        lib = Library(self.tmpdir)
        lib.register_new_plugin("ToughAnvils")
        self.assertEqual(len(lib.plugins), 4)
        self.assertTrue(lib.get_plugin("ToughAnvils").has_meta())

    @unittest.skipIf(os.environ.get('SKIP_SLOW', None), "test_search_jenkins - Skipped (SLOW)")
    def test_search_jenkins(self):
        lib = Library(self.tmpdir)
        lib.add_source('minevsmine', host='ci.minevsmine.com')
        lib.register_new_plugin("Scribe", source='minevsmine')
        self.assertEqual(len(lib.plugins), 4)
        self.assertTrue(lib.get_plugin("Scribe").has_meta())
        plugin = lib.get_plugin("Scribe")
        meta = plugin.get_meta()
        self.assertEqual(plugin.authors, ['metalhedd'])
        self.assertEqual(plugin.name, "Scribe")
        self.assertEqual(meta['source'], 'minevsmine')

    @unittest.skipIf(os.environ.get('SKIP_SLOW', None), "test_search_bukkitdev_none - Skipped (SLOW)")
    def test_search_bukkitdev_none(self):
        lib = Library(self.tmpdir)
        randomname = ''.join(random.sample(string.ascii_letters, 12))
        self.assertRaises(PluginNotFound, lib.register_new_plugin, randomname)

    @unittest.skipIf(os.environ.get('SKIP_SLOW', None), "test_search_jenkins - Skipped (SLOW)")
    def test_search_jenkins_none(self):
        lib = Library(self.tmpdir)
        lib.add_source('minevsmine', host='ci.minevsmine.com')
        randomname = ''.join(random.sample(string.ascii_letters, 12))
        self.assertRaises(PluginNotFound, lib.register_new_plugin, randomname, source='minevsmine')

    @unittest.skipIf(os.environ.get('SKIP_SLOW', None), "test_register_with_unsatisfied_dependency - Skipped (SLOW)")
    def test_register_with_unsatisfied_dependency(self):
        lib = Library(self.tmpdir)
        lib.register_new_plugin("PortableHorses")
        self.assertEqual(len(lib.plugins), 5)
        self.assertIn('PortableHorses', [p.name for p in lib.plugins])
        self.assertIn('ProtocolLib', [p.name for p in lib.plugins])

    @unittest.skipIf(os.environ.get('SKIP_SLOW', None), "test_register_with_unsatisfied_dependency - Skipped (SLOW)")
    def test_register_with_satisfied_dependency(self):
        lib = Library(self.tmpdir)
        lib.register_new_plugin("ProtocolLib")
        lib.register_new_plugin("PortableHorses")
        self.assertEqual(len(lib.plugins), 5)
        self.assertIn('PortableHorses', [p.name for p in lib.plugins])
        self.assertIn('ProtocolLib', [p.name for p in lib.plugins])

    def test_remove_dependencies(self):
        jar1 = self.create_dummy_jar("PortableHorses.jar", depend=['ProtocolLib'], name="PortableHorses")
        jar2 = self.create_dummy_jar("ProtocolLib.jar", name="ProtocolLib")
        lib = Library(self.tmpdir)
        self.assertEqual(len(lib.plugins), 5)
        lib.unregister_plugin("PortableHorses", clean_unused_dependencies=True)
        self.assertEqual(len(lib.plugins), 3)




