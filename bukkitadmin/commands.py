#!/usr/bin/env python
#PYTHON_ARGCOMPLETE_OK
from __future__ import absolute_import

import argparse
from collections import defaultdict
import os
import shutil
import sys
import yaml

import argcomplete
import feedparser

from . import __version__, servers, jenkins
from .plugins import InvalidPlugin, Library, NoPluginSource
from .servers import list_servers, get_servers_file, get_server, save_servers_file, ServerNotFound
from .util import download_file, format_as_kwargs, query_yes_no, chdir, get_request_session, feed_parse
from .runserver import run_server
from .servers import InvalidServerJar


class Option(object):
    """
    A simple wrapper for args, kwargs and a 'completer' option
    used to call add_argument on the provided parser.

    """
    def __init__(self, *args, **kwargs):
        self.args = args
        self.completer = kwargs.pop('completer', None)
        self.kwargs = kwargs

def plugin_completer(prefix, **kwargs):
    """
    argcomplete completion handler for registered plugins

    """
    lib = Library.get()
    return [p.name for p in lib.plugins if p.name.lower().startswith(prefix.lower())]

def plugin_source_completer(prefix, **kwargs):
    """
    argcomplete completion handler for registered plugin sources

    """
    lib = Library.get()
    return [s for s in lib.sources.keys() if s.lower().startswith(prefix.lower())]

def server_name_completer(prefix, **kwargs):
    """
    argcomplete completion handler for registered server names

    """
    return [s for s in list_servers() if s.lower().startswith(prefix.lower())]

class Command(object):
    """
    A base class for all commands to extend.

    this class provides functionality to automatically register options
    and subcommands.  implementations only need to specify a 'name' attribute,
    and either an execute(cls, options) classmethod or subcommands attribute.
    options may also be specified by adding a class-level options attribute
    containing an interable of Option instances.

    """
    @classmethod
    def register_command(cls, parsers):
        parser = parsers.add_parser(cls.name)
        for opt in getattr(cls, 'options', []):
            arg = parser.add_argument(*opt.args, **opt.kwargs)
            if opt.completer is not None:
                arg.completer = opt.completer

        subs = getattr(cls, 'subcommands', [])
        if subs:
            subparsers = parser.add_subparsers()
            for subcommand in subs:
                subcommand.register_command(subparsers)

        if hasattr(cls, 'execute') and hasattr(cls.execute, '__call__'):
            parser.set_defaults(func=cls.execute)


class ServerCreate(Command):

    name = 'create'

    options = (
        Option("--type", "-t", choices=['craftbukkit', 'spigot'], default='craftbukkit'),
        Option("--version", "-v", choices=['dev', 'beta', 'recommended'], default='recommended'),
        Option("--directory", "-d")
    )

    @classmethod
    def download_spigot_jar(cls, options):
        if options.version != 'recommended':
            print "Version Ignored -- Only using daily builds of Spigot."
        url = jenkins.PluginSource("md5", host="ci.md-5.net")._get_download_url("Spigot")
        return download_file(url)

    @classmethod
    def download_craftbukkit_jar(cls, options):
        versions = dict(dev='dev', beta='beta', recommended='rb')
        feed_url = "http://dl.bukkit.org/downloads/craftbukkit/feeds/latest-%s.rss" % (versions[options.version],)
        feed = feed_parse(feed_url)
        link = feed.entries[0].links[0]['href']
        parts = link.rsplit('/', 3)
        url = '/'.join([parts[0], 'get'] + parts[2:3] + ['craftbukkit.jar'])
        return download_file(url)


    @classmethod
    def download_server_jar(cls, options):
        if options.type == 'craftbukkit':
            return cls.download_craftbukkit_jar(options)
        elif options.type == 'spigot':
            return cls.download_spigot_jar(options)

    @classmethod
    def execute(cls, options):
        name = options.server
        try:
            if get_server(name) is not None:
                print "Server %s already exists" % (name,)
                return 1
        except ServerNotFound:
            pass

        if options.directory is None:
            options.directory = name

        if os.path.exists(options.directory):
            if os.listdir(options.directory):
                print "ERROR: Directory %s already exists and is not empty." % (options.directory,)
                return 1
        else:
            os.mkdir(options.directory)
        jarpath = os.path.join(options.directory, "%s.jar" % (options.type,))
        shutil.move(cls.download_server_jar(options), jarpath)
        server = servers.Server(name, jarpath)
        data = get_servers_file(create=True)
        data[name] = {'path': jarpath, 'type': options.type, 'version': options.version}
        save_servers_file(data)


class ServerImport(Command):

    name = 'import'

    options = (
        Option("server_jar", metavar="PATH_TO_JAR"),
    )

    @classmethod
    def execute(cls, options):
        name = options.server
        try:
            if get_server(name) is not None:
                print "Server %s already exists" % (name,)
                return 1
        except ServerNotFound:
            pass
        server = servers.Server(name, options.server_jar)
        sfile = get_servers_file(create=True)
        sfile[name] = dict(path=server.jarpath)
        save_servers_file(sfile)
        print "successfully imported new server %s" % (name,)


class ServerRun(Command):
    name = 'run'

    @classmethod
    def execute(cls, options):
        server = get_server(options.server)
        if server is None:
            print "unknown server %s" % (options.server,)
            return 1

        run_server(server)


class ServerRemove(Command):

    name = 'remove'

    options = (
        Option("--delete", "-d", help="delete the entire server directory.", action="store_true", default=False),
        Option("--yes", "-y", help="do not confirm deletion of files.", dest='noconfirm', action="store_true", default=False),
    )

    @classmethod
    def execute(cls, options):

        server = get_server(options.server)
        if server is None:
            print "unknown server %s" % (options.server,)
            sys.exit(1)

        servers = get_servers_file()
        del servers[server.name]
        save_servers_file(servers)
        print "server %s removed from registry." % (server.name,)
        if options.delete:
            if server.is_running():
                print "Cannot delete server files while server is running."
                sys.exit(1)
            if options.noconfirm or query_yes_no(
                    "Are you sure you wish to permanently delete all files in %s" % (
                        os.path.abspath(server.get_root_dir()),
                    ), default="no"):
                print "Permanently deleting all files in %s" % (server.get_root_dir(),)
                shutil.rmtree(server.get_root_dir())
        else:
            print "server files were NOT deleted.  You will not be able to create a server with the same name until you (re)move the %s directory" % (server.name,)


class ServerInfo(Command):
    name = 'info'

    options = (
        Option('--verbose', '-v', action='count'),
    )

    @classmethod
    def execute(cls, options):
        server = get_server(options.server)
        print "Server", server.name
        print "=" * (len(server.name) + 7)
        print "Running: %s" % (server.is_running(),)
        print "Server Jar: %s" % (os.path.relpath(os.path.abspath(server.jarpath)))

        if options.verbose:
            if options.verbose >= 3:
                keys = list(server.manifest.keys())
            elif options.verbose >= 2:
                keys = ['Implementation-Title', 'Implementation-Version',
                        "Implementation-Vendor", "Build-Jdk", "Specification-Title", "Specification-Version"]
            else:
                keys = ['Implementation-Title', 'Implementation-Version']

            for k in keys:
                print "    %s: %s" % (k, server.manifest[k])

        print "Plugins:"
        for plugin in server.find_plugins():
            print "    %s %s" % (plugin, "" if plugin.is_live() else "(pending restart)")


class ServerAddPlugin(Command):
    name = 'addplugin'

    options = (
        Option("plugin", metavar="PLUGIN_NAME", nargs="+", completer=plugin_completer),
    )

    @classmethod
    def execute(cls, options):
        try:
            server = get_server(options.server)
        except ServerNotFound:
            print "unknown server %s" % (options.server,)
            return 1
        lib = Library.get()
        plugins = [lib.get_plugin(p) for p in options.plugin]
        cls.install_plugins(server, lib, plugins)

    @classmethod
    def install_plugins(cls, server, library, plugins):

        additional = set()
        installing = set()

        for plugin in plugins:
            try:
                existing = server.find_plugin(plugin.name)
                if existing.shasum != plugin.shasum:
                    print "%s will be upgraded to %s." % (repr(existing), plugin.version)
                    installing.add(plugin)
            except InvalidPlugin:
                installing.add(plugin)


            for depname in plugin.dependencies:
                if depname.lower() in [p.name.lower() for p in plugins]:
                    continue
                try:
                    plugin = server.find_plugin(depname)
                    continue
                except InvalidPlugin:
                    dep = library.get_plugin(depname)
                    additional.add(dep)

        if not installing:
            print "No plugins to install."
            return 0

        print "Installing %s" % (", ".join([repr(i) for i in installing]),)
        if additional:
            print "The following dependencies will also be installed:", ", ".join([repr(i) for i in additional])
        if query_yes_no("Install %s new plugins?" % (len(installing) + len(additional),), default="yes"):
            for plugin in installing:
                server.update_plugin(plugin)
            for plugin in additional:
                server.update_plugin(plugin)


class ServerUpdate(Command):

    name = 'update'

    @classmethod
    def execute(cls, options):
        try:
            server = get_server(options.server)
        except ServerNotFound:
            print "unknown server %s" % (options.server,)
            return 1
        print "Scanning for plugins to update..."
        plugins = []
        lib = Library.get()
        for plugin in server.find_plugins():
            print "Checking %s..." % (repr(plugin),),
            existing = lib.get_plugin(plugin.name)
            if existing.newer_than(plugin):
                print "will update to %s" % (existing.version,)
                plugins.append(existing)
            else:
                print "up to date."
        if not plugins:
            print "Nothing to update."
        ServerAddPlugin.install_plugins(server, lib, plugins)


class Servers(Command):

    name = 'servers'

    options = (
        Option("--verbose", "-v", action='count'),
    )

    @classmethod
    def execute(cls, options):
        all_servers = servers.list_servers()
        if not all_servers:
            print "No registered servers."
            return 1

        for servername in list_servers():
            server = get_server(servername, validate=False)
            print servername,
            if not options.verbose:
                print
                continue
            print "(%srunning)" % ("" if server.is_running() else "not ",)


class Server(Command):

    name = 'server'

    options = (
        Option("server", metavar="SERVER_NAME", completer=server_name_completer),
    )

    subcommands = (
        ServerInfo,
        ServerRemove,
        ServerRun,
        ServerImport,
        ServerCreate,
        ServerAddPlugin,
        ServerUpdate,
    )


class PluginRemove(Command):

    name = 'remove'

    @classmethod
    def execute(cls, options):
        lib = Library.get()
        plugin = lib.get_plugin(options.plugin)
        if plugin is None:
            print "Unknown plugin %s" % (options.plugin,)
            return 1

        removed = lib.unregister_plugin(plugin.name, clean_unused_dependencies=None)

        in_use = defaultdict(list)
        all_servers = [get_server(s, validate=False) for s in list_servers()]
        for rem in removed:
            for serv in all_servers:
                try:
                    plugin = serv.find_plugin(rem.name)
                    in_use[rem.name].append(serv)
                except InvalidPlugin:
                    pass

        if in_use:
            print "Some servers are still using plugins that were removed from the registry: "
            for k, v in in_use.iteritems():
                print "%s is installed on servers: " % (k,)
                for s in v:
                    print " ",s.name
            if not query_yes_no("Uninstall these plugins from all servers?"):
                return 0
            for k, v in in_use.iteritems():
                for server in v:
                    server.mark_plugin_for_removal(k)
                    if not server.is_running():
                        server.remove_pending_plugins()





class PluginUpdate(Command):

    name = 'update'

    @classmethod
    def execute(cls, options):
        lib = Library.get()

        plugin = lib.get_plugin(options.plugin)
        if plugin is None:
            print "unknown plugin %s" % (options.plugin,)
            return 1

        print "Checking for updates to %s" % (repr(plugin),)
        try:
            if not lib.update_plugin(plugin):
                print "No update found for %s" % (repr(plugin),)
                return 1
        except NoPluginSource:
            print plugin, "has no valid plugin source, cannot update."
            return 1

        used_by = []
        for server in list_servers():
            server = get_server(server, validate=False)
            try:
                sp = server.find_plugin(plugin.name)
                used_by.append(server)
            except InvalidPlugin:
                continue

        if used_by:
            print "%s is installed on the following servers: %s" % (plugin.name, ", ".join([s.name for s in used_by]),)
            if not query_yes_no("Do you want to update them as well?"):
                return 1
            for server in used_by:
                server.update_plugin(plugin)


class PluginSetSource(Command):

    name = 'setsource'

    options = (
        Option("source", metavar="SOURCE_NAME", completer=plugin_source_completer),
    )

    @classmethod
    def execute(cls, options):
        lib = Library.get()
        plugin = lib.get_plugin(options.plugin)
        if plugin is None:
            print "unknown plugin %s" % (options.plugin,)
            return 1
        source = lib.sources.get(options.source.lower(), None)
        if not source:
            print "unknown source %s" % (options.source,)
            return 1
        meta = plugin.get_meta()
        if source.source_type == 'bukkitdev':
            del meta['source']
        else:
            meta['source'] = source.name
        plugin.set_meta(meta)
        print "%s now using source %s" % (plugin, source.name)

class PluginAdd(Command):

    name = 'add'

    options = (
        Option("--source", "-s", default='bukkitdev', completer=plugin_source_completer),
    )

    @classmethod
    def execute(cls, options):
        lib = Library.get()

        existing = lib.get_plugin(options.plugin)
        if existing:
            print "Plugin %s already installed." % (existing.name,)
            return 1

        lib.register_new_plugin(options.plugin, source=options.source)


class PluginInfo(Command):

    name = 'info'

    options = (
        Option("--verbose", "-v", action='count'),
    )

    @classmethod
    def execute(cls, options):
        lib = Library.get()
        plugin = lib.get_plugin(options.plugin)
        if plugin is None:
            print "unknown plugin %s" % (options.plugin,)
            return 1
        print plugin.name
        print "=" * len(plugin.name)
        print "Version: %s" % (plugin.version,)
        if 'website' in plugin._plugin_yml:
            print "Website: %s" % (plugin._plugin_yml['website'],)
        if 'description' in plugin._plugin_yml:
            print "Description: %s" % (plugin._plugin_yml['description'],)

        print "Source: %s" % (lib.get_plugin_source(plugin).name,)
        if options.verbose:
            print "Author(s): %s" % (", ".join(plugin.authors,),)
            print "File: %s" % (os.path.relpath(plugin.jarpath,))
            for k, v in (("Dependencies", plugin.dependencies),
                         ("Soft-Dependencies", plugin._plugin_yml.get('softdepend', None))):
                if v:
                    print "%s: %s" % (k, ", ".join(v),)


class Plugins(Command):

    name = 'plugins'

    options = (
        Option("--verbose", '-v', action='count'),
    )

    @classmethod
    def execute(cls, options):
        lib = Library.get()
        if not lib.plugins:
            print "No plugins found."
            return 1

        for plugin in lib.plugins:
            if options.verbose >= 2:
                suboptions = parser.parse_args(['plugin', plugin.name, 'info', '-v'])
                PluginInfo.execute(suboptions)
                print ""
            elif options.verbose:
                print plugin
            else:
                print plugin.name


class Plugin(Command):

    name = 'plugin'

    options = (
        Option("plugin", metavar="PLUGIN_NAME", completer=plugin_completer),
    )

    subcommands = (
        PluginAdd,
        PluginInfo,
        PluginUpdate,
        PluginRemove,
        PluginSetSource
    )


class SourceRemove(Command):

    name = 'remove'

    @classmethod
    def execute(cls, options):
        lib = Library.get()
        source = lib.sources.get(options.source.lower(), None)
        if source is None:
            print "unknown plugin source %s" % (options.source,)
            return 1
        in_use_by = []
        for plugin in lib.plugins:
            if lib.get_plugin_source(plugin) == source:
                in_use_by.append(plugin)

        if in_use_by:
            print "Plugin source %s is used by the following plugins: %s" % (options.source, ", ".join([repr(p) for p in in_use_by]),)
            if not query_yes_no("Are you sure you wish to permanently remove this plugin source?"):
                return 1

        lib.remove_source(options.source.lower())
        lib.save_sources()


class SourceAdd(Command):

    name = 'add'

    options = (
        Option("--type", "-t", choices=['jenkins'], default='jenkins'),
        Option("--host", "-H", help="Hostname of plugin source."),
    )

    @classmethod
    def execute(cls, options):
        lib = Library.get()
        lowerkeys = [k.lower() for k  in lib.sources.keys()]
        if options.source in lowerkeys:
            print "source %s is already registered."
            return 1
        if options.type.lower() == 'jenkins':
            if options.host is None:
                print "Jenkins sources require a --host option"
                return 1
            kwargs = {'host': options.host}
        lib.add_source(options.source, type=options.type, **kwargs)
        lib.save_sources()
        print "Successfully registered new plugin source %s" % (options.source,)



class Source(Command):

    name = 'source'

    options = (
        Option("source", metavar="SOURCE_NAME"),
    )
    subcommands = (
        SourceRemove,
        SourceAdd,
    )


class Sources(Command):

    name = 'sources'

    @classmethod
    def execute(cls, options):
        lib = Library.get()
        for source in lib.sources.values():
            if source.name == 'bukkitdev':
                print "bukkitdev [default]"
            else:
                print source.name,"(%s)" % (format_as_kwargs(source.serialize(), priority_keys=['type']),)



class Init(Command):

    name = 'init'

    options = (
        Option('target_dir', metavar="DIRECTORY", nargs = '?'),
        Option("--import", "-i", dest="do_import", action="store_true", default=False),
        Option("--plugins", "-p", action='store_true', default=False)
    )

    @classmethod
    def import_root(cls, options):
        old_dir = os.getcwd()
        with chdir(options.target_dir):
            if not os.path.exists("plugin-library"):
                os.mkdir("plugin-library")

            for e in os.listdir("."):
                if not os.path.isdir(e):
                    continue
                if e == 'plugin-library':
                    continue
                _serv = None
                for f in os.listdir(e):
                    if f.endswith(".jar"):
                        try:
                            _serv = servers.Server(e, os.path.join(e,f), validate=True)
                            break
                        except InvalidServerJar:
                            continue
                if _serv is None:
                    print "No server jar found in %s" % (e,)
                    continue
                print "Imported server %s" % (_serv.name,)

                data = get_servers_file(create=True)
                data[e] = dict(path=_serv.jarpath)
                save_servers_file(data)
                if options.plugins:
                    lib = Library.get()
                    for plugin in _serv.find_plugins():
                        existing = lib.get_plugin(plugin.name)
                        if existing:
                            continue

                        lib.register_new_plugin(plugin.name, jarpath=plugin.jarpath)
                        print "Imported plugin %s" % (lib.get_plugin(plugin.name),)



    @classmethod
    def execute(cls, options):
        if not options.target_dir:
            options.target_dir = os.getcwd()
        if os.path.exists(options.target_dir):
            if os.listdir(options.target_dir):
                if options.do_import:
                    return cls.import_root(options)
                print "%s exists, and is not empty (use --import to import servers and plugins)" % (options.target_dir)
                return 1
        else:
            os.makedirs(options.target_dir)

        with chdir(options.target_dir):
            with open("servers.yml", 'w') as ymlfile:
                yaml.dump({}, ymlfile)

            os.mkdir("plugin-library")
            print "new bukkitadmin root created at %s" % (options.target_dir,)


parser = argparse.ArgumentParser(version=__version__)
subparsers = parser.add_subparsers()

Server.register_command(subparsers)
Plugin.register_command(subparsers)
Source.register_command(subparsers)
Plugins.register_command(subparsers)
Servers.register_command(subparsers)
Sources.register_command(subparsers)
Init.register_command(subparsers)

def main():
    argcomplete.autocomplete(parser)
    opts = parser.parse_args()
    sys.exit(opts.func(opts))

if __name__ == '__main__':
    main()