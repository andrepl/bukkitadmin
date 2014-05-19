from __future__ import absolute_import

import os
import yaml
import shutil
import zipfile

from .plugins import PluginFile, InvalidPlugin, PluginNotFound


class InvalidServerJar(Exception):
    pass

class ServerNotFound(Exception):
    pass

def get_servers_file_path():
    return os.path.join(os.getcwd(), "servers.yml")

def get_servers_file(create=False):
    fp = get_servers_file_path()
    if create and not os.path.exists(fp):
        yaml.dump({}, open(fp, 'w'))
    elif not os.path.exists(fp):
        raise IOError("servers.yml not found.")
    data = yaml.load(open(fp))
    return data or {}

def get_server(name, validate=True):
    try:
        cfg = get_servers_file()
        servercfg = cfg.get(name)
        if servercfg is None:
            raise ServerNotFound(name)
        return Server(name, servercfg['path'], validate=validate)
    except IOError as e:
        raise ServerNotFound(name)

def list_servers():
    yml = get_servers_file()
    return list(yml.keys())

def save_servers_file(data):
    yaml.dump(data, open(get_servers_file_path(), 'w'))

class Server(object):
    def __init__(self, name, jarpath, validate=True):
        self.name = name
        self.jarpath = jarpath
        if validate:
            self.validate()

    def read_manifest(self, zf):
        manifest = zf.read("META-INF/MANIFEST.MF")
        data = {}
        for line in manifest.splitlines():
            line = line.strip()
            if line:
                parts = line.split(": ", 1)
                data[parts[0]] = parts[1]
        return data

    def validate(self):
        try:
            zf = zipfile.ZipFile(open(self.jarpath, 'r'), mode='r')
        except IOError:
            raise InvalidServerJar("Jar file not found %s" % (self.jarpath,))
        try:
            self.manifest = manifest = self.read_manifest(zf)
        except KeyError:
            raise InvalidServerJar("No jar manifest.");
        if manifest.get('Specification-Title',"") != 'Bukkit':
            raise InvalidServerJar("Specification-Title %s != Bukkit" % (manifest.get("Specification-Title", "")))

    def get_plugin_dir(self, create=True):
        pdir = os.path.join(os.path.dirname(self.jarpath), "plugins")
        if create and not os.path.exists(pdir):
            os.mkdir(pdir)
        return pdir

    def get_root_dir(self):
        return os.path.dirname(self.jarpath)

    def find_plugins(self):
        plugins = []
        for f in os.listdir(self.get_plugin_dir()):
            try:
                plugins.append(PluginFile(os.path.join(self.get_plugin_update_dir(), f)))
            except InvalidPlugin:
                try:
                    plugins.append(PluginFile(os.path.join(self.get_plugin_dir(), f)))
                except InvalidPlugin:
                    pass
        return plugins

    def find_plugin(self, plugin_name):
        plugin = PluginFile(os.path.join(self.get_plugin_dir(), "%s.jar" % (plugin_name,)))
        return plugin

    def get_plugin_update_dir(self, create=True):
        pdir = os.path.join(self.get_plugin_dir(), 'update')
        if create and not os.path.exists(pdir):
            os.mkdir(pdir)
        return pdir

    def mark_plugin_for_removal(self, plugin):
        plugin = self.find_plugin(plugin)
        if not plugin:
            raise PluginNotFound()
        remdir = os.path.join(self.get_plugin_dir(), ".remove")
        if not os.path.exists(remdir):
            os.mkdir(remdir)
        try:
            os.symlink(
                os.path.relpath(plugin.jarpath, remdir),
                os.path.join(remdir, os.path.basename(plugin.jarpath))
            )
        except OSError:
            print "%s already marked for removal on %s" % (plugin.name, self.name,)


    def remove_pending_plugins(self):
        remdir = os.path.join(self.get_plugin_dir(), ".remove")
        if os.path.exists(remdir):
            for fn in os.listdir(remdir):
                if os.path.islink(os.path.join(remdir, fn)):
                    print "Removing %s from %s" % (fn,self.name)
                    linkpath = os.path.join(remdir, fn)
                    path = os.path.realpath(linkpath)
                    os.unlink(linkpath)
                    os.unlink(path)

    def update_all_plugins(self, library):
        for plugin in self.find_plugins():
            lib_plug = library.get_plugin(plugin.name)
            self.update_plugin(lib_plug)

    def update_plugin(self, plugin):
        try:
            orig = self.find_plugin(plugin.name)
        except InvalidPlugin:
            orig = None

        if orig and self.is_running():
            dest = self.get_plugin_update_dir()
        else:
            dest = self.get_plugin_dir()

        if orig is None or plugin.newer_than(orig):
            action = "Installing" if not orig else "Updating"
            print "%s %s" % (action, plugin)
            shutil.copy(plugin.jarpath, dest)

    def is_running(self):
        return os.path.exists(os.path.join(os.path.dirname(self.jarpath), ".PID"))


