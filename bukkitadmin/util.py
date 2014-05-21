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
import feedparser
import pager
from progressbar import ProgressBar, ETA, FileTransferSpeed, Percentage, Bar
import requests
import yaml
from requests_cache import CachedSession


@contextlib.contextmanager
def chdir(dirname=None):
    curdir = os.getcwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)

def prompt_choices(choices_function, choice_formatter=None,
                   prompt="Your Choice [1-#/L=list] (or ctrl+c to quit): ",
                   header="Choices:"):

    def _choice_formatter(number, choice):
        return "%s) %s" % (number, choice)

    def _prompt(pagenum, linesleft):
        """
        Show default prompt to continue and process keypress.

        It assumes terminal/console understands carriage return \r character.
        """
        if linesleft > 1:
            return False
        prompt = "[Press esc or Q to stop listing, or any other key for more results... ] "
        pager.echo(prompt)
        try:
            if pager.getch() in [pager.ESC_, pager.CTRL_C_, 'q', 'Q']:
                pager.echo('\r' + ' '*(len(prompt)-1) + '\r')
                return False
        except KeyboardInterrupt:
            # pager is supposed to catch ctrl+c but it doesn't appear to
            sys.exit(0)
        pager.echo('\r' + ' '*(len(prompt)-1) + '\r')

    _counter = {'max': 0}
    def show_list():
        def gen():
            for num, c in enumerate(choices_function()):
                for line in choice_formatter(num+1, c):
                    yield line
        page(gen(), pagecallback=_prompt)

    if choice_formatter is None:
        choice_formatter = _choice_formatter

    show_list()

    while True:
        sys.stdout.write(prompt)
        try:
            choice = raw_input().lower()
        except KeyboardInterrupt:
            return None
        if 'list'.startswith(choice):
            show_list()
            continue
        try:
            val = int(choice)
            if 1 <= val:
                try:
                    return next(itertools.islice(choices_function(), val-1, val))
                except StopIteration:
                    raise ValueError("Invalid Choice?")
        except ValueError:
            pass
        print "%s is an invalid choice, please enter a number greater than 0 (or l to list the results again)" % (choice, )




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


_requests_session = None


def get_request_session():
    global _requests_session
    if _requests_session is None:
        _requests_session = CachedSession('.bukkadmin', backend='sqlite',expire_after=60*60, extension='cache')
    return _requests_session


def get_page_soup(url):

    resp = get_request_session().get(url)
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
    heading = "%s) %s " % (number, result['name'])

    if 'categories' in result and result['categories']:
        heading += "[%s] " % (", ".join(result['categories']),)

    if 'authors' in result and result['authors']:
        heading += "(author: %s) " % (", ".join(result['authors']),)

    right = ""

    if 'last_updated' in result:
        right += " Updated %s" % (result['last_updated'])

    if 'stage' in result:
        right += " [%s]" % (result['stage'],)
    heading += right.rjust(term_width - len(heading))

    lines = [heading, '']
    if 'summary' in result and result['summary']:
        lines += wrapper.wrap(result['summary'])
        lines.append('')
    return lines



def feed_parse(url):
    return feedparser.parse(get_request_session().get(url).text)

def page(content, pagecallback=None):
    """
    Output `content`, call `pagecallback` after every page with page
    number as a parameter. `pagecallback` may return False to terminate
    pagination.

    Default callback shows prompt, waits for keypress and aborts on
    'q', ESC or Ctrl-C.
    """
    width = pager.getwidth()
    height = pager.getheight()
    pagenum = 1
    print content.next()
    try:
        try:
            line = content.next().rstrip("\r\n")
        except AttributeError:
            # Python 3 compatibility
            line = content.__next__().rstrip("\r\n")
    except StopIteration:
        pagecallback(pagenum, height-1)
        return

    while True:     # page cycle
        linesleft = height-1 # leave the last line for the prompt callback
        while linesleft:
            linelist = [line[i:i+width] for i in range(0, len(line), width)]
            if not linelist:
                linelist = ['']
            lines2print = min(len(linelist), linesleft)
            for i in range(lines2print):
                print(linelist[i])
            linesleft -= lines2print
            linelist = linelist[lines2print:]

            if linelist: # prepare symbols left on the line for the next iteration
                line = ''.join(linelist)
                continue
            else:
                try:
                    try:
                        line = content.next().rstrip("\r\n")
                    except AttributeError:
                        # Python 3 compatibility
                        line = content.__next__().rstrip("\r\n")
                except StopIteration:
                    pagecallback(pagenum, linesleft)
                    return

        if pagecallback(pagenum, linesleft) == False:
            return
        pagenum += 1


