from __future__ import absolute_import

import os
import struct
import sys
import fcntl
import termios
import pexpect

from .servers import get_server

PROC = None
def sigwinch_passthrough (sig, data):
    s = struct.pack("HHHH", 0, 0, 0, 0)
    a = struct.unpack('hhhh', fcntl.ioctl(sys.stdout.fileno(),
                              termios.TIOCGWINSZ , s))
    global PROC
    PROC.setwinsize(a[0],a[1])


# Dual licensed under the MIT and GPL licenses.

class PidFile(object):
    """Context manager that locks a pid file.  Implemented as class
    not generator because daemon.py is calling .__exit__() with no parameters
    instead of the None, None, None specified by PEP-343."""
    # pylint: disable=R0903

    def __init__(self, path, pid):
        self.path = path
        self.pidfile = None
        self.pid = pid

    def __enter__(self):
        self.pidfile = open(self.path, "a+")
        try:
            fcntl.flock(self.pidfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise SystemExit("Already running according to " + self.path)
        self.pidfile.seek(0)
        self.pidfile.truncate()
        self.pidfile.write(str(self.pid))
        self.pidfile.flush()
        self.pidfile.seek(0)
        return self.pidfile

    def __exit__(self, exc_type=None, exc_value=None, exc_tb=None):
        try:
            self.pidfile.close()
        except IOError as err:
            # ok if file was just closed elsewhere
            if err.errno != 9:
                raise
        os.remove(self.path)



def run_server(server):
    old_dir = os.getcwd()
    os.chdir(os.path.dirname(server.jarpath))
    PROC = pexpect.spawn("java -jar %s" % (os.path.basename(server.jarpath)))

    with PidFile(".PID", PROC.pid) as pidfile:
        try:
            PROC.interact(escape_character=chr(3))
        except OSError:
            pass
        else:
            PROC.sendline("%sstop" % (chr(21),))
            PROC.expect(pexpect.EOF)
            print PROC.before

    # return to the parent directory
    os.chdir(old_dir)
    # fetch the server again in case the files moved somehow
    server = get_server(server.name)
    server.remove_pending_plugins()

