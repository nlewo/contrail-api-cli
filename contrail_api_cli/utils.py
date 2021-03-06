from __future__ import unicode_literals
import sys
import json
import os.path
import hashlib
from uuid import UUID
from pathlib import PurePosixPath, _PosixFlavour
from six import string_types, text_type, b
import collections
import logging

from prompt_toolkit import prompt


logger = logging.getLogger(__name__)


class FQName(collections.Sequence):

    def __init__(self, init=None):
        if isinstance(init, string_types):
            self._data = init.split(':')
        elif isinstance(init, list):
            self._data = init
        else:
            self._data = []

    def __getitem__(self, idx):
        return self._data[idx]

    def __len__(self):
        return len(self._data)

    def __eq__(self, other):
        return self._data == other

    def __repr__(self):
        return repr(self._data)

    def __str__(self):
        return ':'.join(self._data)

    def __bytes__(self):
        return b(':'.join(self._data))

    def __lt__(self, b):
        return len(str(self)) < len(str(b))

    def __gt__(self, b):
        return not self.__lt__(b)


class Observable(object):

    def __new__(cls, *args, **kwargs):
        return super(Observable, cls).__new__(cls)

    @classmethod
    def register(cls, event, callback):
        logger.debug("registering %s to %s" % (event, callback))
        if not hasattr(cls, "observers"):
            cls.observers = {}
        if event not in cls.observers:
            cls.observers[event] = []
        cls.observers[event].append(callback)

    @classmethod
    def unregister(cls, event, callback):
        try:
            cls.observers[event].remove(callback)
        except (ValueError, KeyError):
            pass

    @classmethod
    def emit(cls, event, data):
        logger.debug("emiting event %s with %s" % (event, repr(data)))
        if not hasattr(cls, "observers"):
            cls.observers = {}
        [cbk(data)
         for evt, cbks in cls.observers.items()
         for cbk in cbks
         if evt == event]


class Singleton(type):
    def __init__(cls, name, bases, dict):
        super(Singleton, cls).__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls, *args, **kw):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kw)
        return cls.instance


class APIFlavour(_PosixFlavour):

    def parse_parts(self, parts):
        # Handle non ascii chars for python2
        parts = [p.encode('ascii', errors='replace').decode('ascii')
                 for p in parts]
        return super(APIFlavour, self).parse_parts(parts)


class Path(PurePosixPath):
    _flavour = APIFlavour()

    @classmethod
    def _from_parsed_parts(cls, drv, root, parts, init=True):
        if parts:
            parts = [root] + os.path.relpath(os.path.join(*parts),
                                             start=root).split(os.path.sep)
            parts = [p for p in parts if p not in (".", "")]
        return super(cls, Path)._from_parsed_parts(drv, root, parts, init)

    def __init__(self, *args):
        self.meta = {}

    @property
    def base(self):
        try:
            return self.parts[1]
        except IndexError:
            pass
        return ''

    @property
    def is_root(self):
        return len(self.parts) == 1 and self.root == "/"

    @property
    def is_resource(self):
        try:
            UUID(self.name, version=4)
        except (ValueError, IndexError):
            return False
        return True

    @property
    def is_collection(self):
        return self.base == self.name

    def relative_to(self, path):
        try:
            return PurePosixPath.relative_to(self, path)
        except ValueError:
            return self


class classproperty(object):

    def __init__(self, f):
        self.f = f

    def __get__(self, instance, klass):
        if instance:
            try:
                return self.f(instance)
            except AttributeError:
                pass
        return self.f(klass)


def continue_prompt(message=""):
    answer = False
    message = message + "\n'Yes' or 'No' to continue: "
    while answer not in ('Yes', 'No'):
        answer = prompt(message)
        if answer == "Yes":
            answer = True
            break
        if answer == "No":
            answer = False
            break
    return answer


def all_subclasses(cls):
    return cls.__subclasses__() + [g for s in cls.__subclasses__()
                                   for g in all_subclasses(s)]


def to_json(resource_dict, cls=None):
    return json.dumps(resource_dict,
                      indent=2,
                      sort_keys=True,
                      skipkeys=True,
                      cls=cls)


def md5(fname):
    hash = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash.update(chunk)
    return hash.hexdigest()


def to_unicode(value):
    if isinstance(value, string_types):
        return text_type(value)
    elif isinstance(value, collections.Mapping):
        return dict(map(to_unicode, list(value.items())))
    elif isinstance(value, collections.Iterable):
        return type(value)(map(to_unicode, value))
    return value


def printo(msg, encoding=None, errors='replace', std_type='stdout'):
    """Write msg on stdout. If no encoding is specified
    the detected encoding of stdout is used. If the encoding
    can't encode some chars they are replaced by '?'

    :param msg: message
    :type msg: unicode on python2 | str on python3
    """
    std = getattr(sys, std_type, sys.stdout)
    if encoding is None:
        try:
            encoding = std.encoding
        except:
            encoding = None
    # Fallback to ascii if no encoding is found
    if encoding is None:
        encoding = 'ascii'
    # https://docs.python.org/3/library/sys.html#sys.stdout
    # write in the binary buffer directly in python3
    if hasattr(std, 'buffer'):
        std = std.buffer
    std.write(msg.encode(encoding, errors=errors))
    std.write(b'\n')
    std.flush()
