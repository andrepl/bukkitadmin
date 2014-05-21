import contextlib
import difflib
import hashlib
import os
import shutil
import sys
import tempfile
from textwrap import TextWrapper
import zipfile

from bs4 import BeautifulSoup
import itertools
import pager
from progressbar import ProgressBar, ETA, FileTransferSpeed, Percentage, Bar
import requests
import yaml

@contextlib.contextmanager
def chdir(dirname=None):
    curdir = os.getcwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)

def prompt_choices(choices, choice_formatter=None,
                   prompt="Your Choice [1-%s/L=list] (or ctrl+c to quit): ",
                   header="Choices:"):

    def _choice_formatter(number, choice):
        return "%s) %s" % (number, choice)

    def _prompt(pagenum):
        """
        Show default prompt to continue and process keypress.

        It assumes terminal/console understands carriage return \r character.
        """
        prompt = "[Press esc or Q to stop listing, or any other key for more results...] "
        pager.echo(prompt)

        if pager.getch() in [pager.ESC_, pager.CTRL_C_, 'q', 'Q']:
            pager.echo('\r' + ' '*(len(prompt)-1) + '\r')
            return False
        pager.echo('\r' + ' '*(len(prompt)-1) + '\r')


    choices = list(choices)
    count = len(choices)

    def show_list():
        pager.page(itertools.chain([header],
            *(choice_formatter(i+1, c) for i, c in enumerate(choices))), pagecallback=_prompt)

    if choice_formatter is None:
        choice_formatter = _choice_formatter

    show_list()

    while True:
        sys.stdout.write(prompt % (count, ))
        choice = raw_input().lower()
        if 'list'.startswith(choice):
            show_list()
            continue
        try:
            val = int(choice)
            if 1 <= val <= count:
                return choices[val-1]
        except ValueError:
            pass
        print "%s is an invalid choice, please enter a value between 1 and %s (or l to list the results again)" % (choice, count,)




def prompt_number(min_, max_, prompt="Choice"):
    while True:
        sys.stdout.write("%s [%s-%s]: " % (prompt, min_, max_))
        choice = raw_input().lower()
        try:
            val = int(choice)
            if not (min_ <= val <= max_):
                raise ValueError("out of range")
            return val
        except ValueError:
            print "Invalid choice, please enter a number between %s and %s" % (min_, max_)


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    """
    valid = {"yes":True,   "y":True,  "ye":True,
             "no":False,     "n":False}
    if default == None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' " \
                             "(or 'y' or 'n').\n")

def format_as_kwargs(kwargs, priority_keys=None):
    priority_keys = priority_keys or []
    keys = list(kwargs.keys())
    for pk in reversed(priority_keys):
        if pk in keys:
            key = keys.pop(keys.index(pk))

            keys.insert(0, key)
    return ", ".join("%s=%s" % (k, repr(kwargs.get(k))) for k in keys)

def download_file(url, use_progressbar=True, destination=None):

    r = requests.get(url, stream=True)
    outfile, fname = tempfile.mkstemp()
    if use_progressbar:
        name = os.path.splitext(url.split('/')[-1])[0]
        widgets = widgets = ['%s: ' % (name,), Percentage(), ' ', Bar(),
                             ' ', ETA(), ' ', FileTransferSpeed()]
        size = int(r.headers['Content-Length'].strip())
        pbar = ProgressBar(widgets=widgets, maxval=size).start()

    with os.fdopen(outfile, 'wb') as f:
        bytes = 0
        for chunk in r.iter_content(chunk_size=1024):
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
                bytes += len(chunk)
                if use_progressbar:
                    pbar.update(bytes)
        if use_progressbar:
            pbar.finish()
    if destination:
        shutil.move(fname, destination)

    return fname


def get_page_soup(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text)
    return soup


def extract_plugin_info(jarpath):
    try:
        zf = zipfile.ZipFile(open(jarpath))
        pyml = zf.read("plugin.yml")
        return yaml.load(pyml)
    except (KeyError, IOError):
        return None


def hashfile(fileobj=None, path=None):
    opened = False
    if fileobj is None:
        opened = True
        fileobj = open(path)

    try:
        buf = fileobj.read(65536)
        hasher = hashlib.sha256()
        while len(buf) > 0:
            hasher.update(buf)
            buf = fileobj.read(65535)
    finally:
        if opened:
            fileobj.close()
    return hasher.digest()


def normalize_string(s):
    return s.lower().replace(' ', '').replace('-', '').replace(' ', '')

def string_diff(s1, s2):
    s1 = normalize_string(s1)
    s2 = normalize_string(s2)
    return difflib.SequenceMatcher(None, s1, s2).ratio()

def terminal_size():
    import fcntl, termios, struct
    h, w, hp, wp = struct.unpack('HHHH',
                                 fcntl.ioctl(0, termios.TIOCGWINSZ,
                                             struct.pack('HHHH', 0, 0, 0, 0)))
    return w, h


def smart_truncate(content, length=100, suffix='...'):
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length+1].split(' ')[0:-1]) + suffix

def format_search_result(number, result):
    term_width = terminal_size()[0]
    if term_width > 8:
        term_width = term_width - 8
    wrapper = TextWrapper(initial_indent="    ", subsequent_indent="    ", width=term_width)
    return ["%s) %s" % (number, result['name'])] + wrapper.wrap(result['summary'])


