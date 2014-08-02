************************************************
BukkitAdmin: A tool for mananging bukkit servers
************************************************

bukkitadmin provides a command line program called 'bukkit' which contains a number of subcommands related to managing servers, plugins, and plugin sources (CI Servers, etc).

Initialize the 'root' server / plugins director  (usually ./servers/)

    bukkit init ./
    
Add a few plugins to the plugin library

    bukkit plugin <plugin_name> add
    
Create the server

    bukkit server <server_name> create
    
Add standard plugin from bukkit to the server

    bukkit server <server_name> addplugin <plugin name can do multiple with spaces>
    
Add a plugin source (like jenkins)

    bukkit source mvm add --host ci.minevsmine.com -t jenkins
    
Add plugin from different source.

    bukkit plugin kiosk add --source mvm

