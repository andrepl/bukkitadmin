from __future__ import absolute_import

import logging
import os
import shutil

import yaml

from . import jenkins, bukkitdev
from bukkitadmin.util import extract_plugin_info, hashfile, download_file, query_yes_no, prompt_number, terminal_size, smart_truncate
from bukkitadmin.versionparser import parse_version


class InvalidPlugin(Exception):
    pass


class PluginFile(object):

    @property
    def shasum(self):
        return hashfile(path=self.jarpath)

    def __init__(self, jarpath):
        self.jarpath = jarpath
        self._plugin_yml = extract_plugin_info(self.jarpath)
        if self._plugin_yml is None:
            raise InvalidPlugin("%s is not a valid plugin file." % (self.jarpath,));

    def __repr__(self):
        return "%s-%s" % (self.name, self.version)

    def reload(self):
        self._plugin_yml = extract_plugin_info(self.jarpath)

    @classmethod
    def is_valid_plugin(cls, jarpath):
        return extract_plugin_info(jarpath) is not None

    @property
    def authors(self):
        authors = set()
        for key in ('author', 'authors'):
            if key in self._plugin_yml:
                if isinstance(self._plugin_yml[key], basestring):
                    authors.add(self._plugin_yml[key])
                else:
                    for author in self._plugin_yml[key]:
                        authors.add(author)
        return list(authors)

    @property
    def name(self):
        return self._plugin_yml['name']

    @property
    def main(self):
        return self._plugin_yml['main']

    @property
    def version(self):
        return self._plugin_yml['version']

    @property
    def dependencies(self):
        if 'depend' not in self._plugin_yml:
            return []
        return self._plugin_yml['depend']

    def _get_meta_path(self):
        return os.path.splitext(self.jarpath)[0] + ".yml"

    def get_meta(self):
        if not self.has_meta():
            return {}
        with open(self._get_meta_path()) as metafile:
            data = yaml.load(metafile)
        return data

    def set_meta(self, meta):
        with open(self._get_meta_path(), 'w') as metafile:
            yaml.dump(meta, metafile)

    def has_meta(self):
        return os.path.exists(self._get_meta_path())

    def has_correct_name(self):
        return os.path.basename(self.jarpath) == "%s.jar" % (self.name,)

    def newer_than(self, other):
        my_version = parse_version(self.version)
        other_version = parse_version(other.version)
        if my_version == other_version:
            return self.shasum != other.shasum
        return my_version > other_version

    def is_live(self):
        return os.path.basename(os.path.dirname(self.jarpath)) == 'plugins'

    def rename_jar(self):
        meta = None
        if self.has_meta():
            meta = self.get_meta()
            if os.path.exists(self._get_meta_path()):
                os.unlink(self._get_meta_path())
        newjarpath = os.path.join(os.path.dirname(self.jarpath), "%s.jar" % (self.name,))
        if os.path.exists(newjarpath):
            raise IOError("File %s already exists" % (newjarpath,))
        shutil.move(self.jarpath, newjarpath)
        self.jarpath = newjarpath
        if meta is not None:
            self.set_meta(meta)


class PluginNotFound(Exception):
    pass


class NoPluginSource(Exception):
    pass



class Library(object):
    """The bukkit plugin registry"""

    VALID_SOURCE_TYPES = {
        "jenkins": jenkins.PluginSource
    }

    @classmethod
    def get(cls, rootdir=None):
        if rootdir is None:
            rootdir = os.getcwd()
        libdir = os.path.join(rootdir, "plugin-library")
        if not os.path.exists(libdir):
            raise IOError("Plugin library not found.")
        return Library(libdir)

    def __init__(self, path):
        self.path = path
        self.reload_sources()
        self.reload()

    def reload_sources(self):
        sources_file = os.path.join(self.path, ".sources.yml")
        if not os.path.exists(sources_file):
            with open(sources_file, 'w') as sources:
                yaml.dump({}, sources)
        self.sources = {'bukkitdev': bukkitdev.PluginSource()}

        sources = yaml.load(open(sources_file))
        for source_name, source_cfg in sources.iteritems():
            source_type = source_cfg.pop('type', None)
            if source_type is None or source_type not in self.VALID_SOURCE_TYPES:
                logging.warn("Unknown source type %s" % (source_type,))
                continue
            self.add_source(source_name, source_type, **source_cfg)

    def add_source(self, name, type='jenkins', **kwargs):
        if name in self.sources:
            raise KeyError("source %s is already registered" % (name,))
        if type not in self.VALID_SOURCE_TYPES:
            raise KeyError("Unknown source type %s" % (type,))
        source = self.VALID_SOURCE_TYPES[type](name, **kwargs)
        self.sources[name] = source

    def remove_source(self, name):
        if name in self.sources:
            return self.sources.pop(name)

    def save_sources(self):
        cfg = {}
        for source_name, source in self.sources.iteritems():
            if source.source_type == 'bukkitdev':
                continue # don't save the bukkitdev one, its default
            cfg[source_name] = source.serialize()
        yaml.dump(cfg, open(os.path.join(self.path, ".sources.yml"), 'w'))

    def reload(self):
        self._cached = []

        for _file in os.listdir(self.path):
            if not _file.endswith(".jar"):
                continue
            try:
                plugin = PluginFile(os.path.join(self.path, _file))
                self._cached.append(plugin)
            except InvalidPlugin as e:
                logging.warn("Invalid jar file found in plugin registry: %s" % (_file,))
                continue
            logging.debug("Found %s" % (_file,))

    def update_plugin(self, plugin):
        if isinstance(plugin, basestring):
            plugin = self.get_plugin(plugin)
        source = self.get_plugin_source(plugin)
        if source is None:
            raise NoPluginSource()
        url = source.get_download_url(plugin)
        meta = plugin.get_meta()
        if meta.get('last_download_url', '') == url:
            return False
        filename = download_file(url)
        pf = PluginFile(filename)
        meta['last_download_url'] = url
        plugin.set_meta(meta)
        ret = False
        if pf.newer_than(plugin):
            ret = True
            shutil.move(filename, plugin.jarpath)
            plugin.reload()

        return ret

    def register_new_plugin(self, name, source=None, jarpath=None):
        info = None
        dest = None
        meta = {}
        plugin = self.get_plugin(name)
        if plugin is not None:
            raise KeyError("Plugin %s is already in the registry")

        if jarpath:
            info = extract_plugin_info(jarpath)
            dest = os.path.join(self.path, "%s.jar" %(info['name'],))
            shutil.copy(jarpath, dest)

        else:
            if source is None:
                source = self.sources['bukkitdev']
            elif isinstance(source, basestring):
                source = self.sources[source]

            results = source.search(name)

            if len(results) == 0:
                raise PluginNotFound(name)

            elif len(results) == 1:
                choice = results[0]
            else:
                print "Found multiple matches for '%s' on source %s" % (name, source.name)
                desc_width = terminal_size()[0] - 8
                if desc_width < 10:
                    desc_width = 20 # if the terminal is too small, just display a decent amount and wrap

                for i, plugin in enumerate(results):
                    print "%s) %s\n    %s" % (i+1, plugin['name'], smart_truncate(plugin['summary'], ))
                print "0) None of the above."
                choice = prompt_number(0, i+1)
                if not choice:
                    return 0
                choice = results[choice-1]

            download_url, meta = source.search_result_url(choice)
            file = download_file(download_url)
            info = extract_plugin_info(file)
            dest = os.path.join(self.path, "%s.jar" %(info['name'],))
            shutil.move(file, dest)

        pluginfile = PluginFile(dest)
        pluginfile.set_meta(meta)
        self._cached.append(pluginfile)
        if not jarpath:
            self.get_plugin_dependencies(pluginfile)

    def get_plugin_dependencies(self, plugin):
        if isinstance(plugin, basestring):
            plugin = self.get_plugin(plugin)
        if plugin.dependencies:
            print "Checking dependencies for %s" % (plugin.name,)
            for dep in plugin.dependencies:
                depjar = self.get_plugin(dep)
                if depjar is None:
                    source = self.get_plugin_source(plugin)
                    print "  %s not registered, searching %s" % (dep, source.name)
                    try:
                        self.register_new_plugin(dep, source=self.get_plugin_source(plugin))
                    except PluginNotFound:
                        if not isinstance(source, bukkitdev.PluginSource):
                            print "%s not found on %s, searching bukkitdev" % (dep, source.name)
                            self.register_new_plugin(dep)
                        else:
                            raise
                else:
                    print "  %s - Dependency Satisfied." % (depjar.name,)

    def unregister_plugin(self, pluginname, clean_unused_dependencies=True):
        removed = []
        plugin = None
        if isinstance(pluginname, basestring):
            plugin = self.get_plugin(pluginname)
        else:
            plugin = pluginname
            pluginname = plugin.name

        if plugin is None:
            raise PluginNotFound("%s is not a registered plugin" % (pluginname,))

        self._cached.remove(plugin)
        if os.path.exists(plugin._get_meta_path()):
            os.unlink(plugin._get_meta_path())
        os.unlink(plugin.jarpath)
        removed.append(plugin)
        if clean_unused_dependencies or clean_unused_dependencies is None:
            unused = []
            all_dependencies = self.get_remaining_dependencies()
            for dep in plugin.dependencies:
                dep_plugin = self.get_plugin(dep)
                if dep_plugin is None:
                    print "dependency %s is not registered." % (dep,)
                    continue
                for ad in all_dependencies:
                    if ad.name == dep_plugin.name:
                        # existing dependency is still required.
                        break;
                else:
                    unused.append(dep)
            if unused and clean_unused_dependencies is None:
                print "The following dependencies are no longer required: %s" % (", ".join([repr(p) for p in unused]),)
                if not query_yes_no("Remove unused dependencies?"):
                    return removed
            for up in unused:
                print "removing unused dependency: %s" % (up,)
                removed += self.unregister_plugin(up, clean_unused_dependencies=clean_unused_dependencies)
            return removed
    def get_remaining_dependencies(self):
        deps = set()
        for p in self.plugins:
            for dep in p.dependencies:
                dp = self.get_plugin(dep)
                if dp is not None:
                    deps.add(dp)
        return list(deps)

    def get_plugin_source(self, plugin):
        if isinstance(plugin, basestring):
            plugin = self.get_plugin(plugin)
        if not plugin.has_meta():
            return self.sources['bukkitdev']
        meta = plugin.get_meta()
        if 'source' in meta:
            return self.sources.get(meta['source'], None)
        return self.sources['bukkitdev']

    @property
    def plugins(self):
        return list(self._cached)

    def get_plugin(self, name):
        for p in self._cached:
            if p.name.lower() == name.lower():
                return p

