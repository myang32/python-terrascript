"""
terrascript/__init__.py

Base classes and functions that are used elsewhere in
this project.

"""

__author__ = 'Markus Juenemann <markus@juenemann.net>'
__version__ = '0.4.1'
__license__ = 'BSD 2-clause "Simplified" License'

INDENT = 2
"""JSON indentation level."""

SORT = True
"""Whether to sort keys when generating JSON."""

DEBUG = False
"""Set to enable some debugging."""

import logging 
import os
from collections import defaultdict, UserDict

logger = logging.getLogger(__name__)


class CONFIG(dict):
    def __getitem__(self, key):
        try:
            return super(CONFIG, self).__getitem__(key)
        except KeyError:
            if key in ['data', 'resource']:
                super(CONFIG, self).__setitem__(key, defaultdict(dict))
            elif key in ['variable', 'module', 'output', 'provider', 'terraform']:
                super(CONFIG, self).__setitem__(key, {})
            else:
                raise KeyError(key)
                
        return super(CONFIG, self).__getitem__(key)

    def dump(self):
        """Return the JSON representaion of config."""
        import json
        
        def _json_default(v):
            # How to encode non-standard objects
            if isinstance(v, UserDict):
                return v.data
            else:
                return str(v)

        # Work on copy of CONFIG but with unused top-level elements removed.
        #
        config = {k: v for k,v in self.items() if v}
        return json.dumps(config, indent=INDENT, sort_keys=SORT, default=_json_default)
        
        
    def validate(self):
        """Validate a Terraform configuration."""
        import tempfile
        import subprocess
    
        config = dump()
        tmpdir = tempfile.mkdtemp()
        tmpfile = tempfile.NamedTemporaryFile(mode='w', dir=tmpdir, suffix='.tf.json', delete=False)
    
        tmpfile.write(self.dump())
        tmpfile.flush()
    
        proc = subprocess.Popen(['terraform','validate'], cwd=tmpdir)
        proc.communicate()
        
        tmpfile.close()
        
        # if  DEBUG:
        #     logger.debug(tmpfile.name)
        # else:
        #     os.remove(tmpfile.name)
        #     os.rmdir(tmpdir)
        
        return proc.returncode == 0
            

config = CONFIG()
dump = config.dump
validate = config.validate


class _base(object):
    _class = None
    """One of 'resource', 'data', 'module', etc."""

    _type = None
    """The resource type, e.g. 'aws_instance'."""

    _name = None
    """The name of this resource, e.g. 'my_ec2_instance'."""

    def __init__(self, name_, **kwargs):
        if not self._type:
            self._type = self.__class__.__name__
        self._name = name_

        if self._class in ['resource', 'data']:
            config[self._class][self._type][self._name] = kwargs
        elif self._class in ['terraform']:
            config[self._class] = kwargs
        else:
            config[self._class][self._name] = kwargs

    def __getattr__(self, name):
        """References to attributes."""
        if self._class == 'resource':
            return '${{{}.{}.{}}}'.format(self._type, self._name, name)
        elif self._class == 'module':
            return '${{module.{}.{}}}'.format(self._name, name)
        else:
            return '${{{}.{}.{}.{}}}'.format(self._class, self._type, self._name, name)
            
    def __getitem__(self, i):
        if isinstance(i, int):
            # "${var.NAME[i]}"
            return '${{var.{}[{}]}}'.format(self._name, i)
        else:
            # "${var.NAME["i"]}"
            return "${{var.{}[\"{}\"]}}".format(self._name, i)

    def __repr__(self):
        """References to objects."""
        if self._class == 'variable':
            """Interpolated reference to a variable, e.g. ``${var.http_port}``."""
            return self.interpolated
        else:
            """Non-interpolated reference to a non-resource, e.g. ``module.http``."""
            return self.fullname
    
    @property    
    def interpolated(self):
        """The object in interpolated syntax: ``${...}``."""
        if self._class == 'variable':
            return '${{{}}}'.format(self.fullname)
        elif self._class == 'resources':
            return '${{{}}'.format(self._fullname)
        else:
            return '${{{}}'.format(self._fullname)
            
    @property
    def fullname(self):
        """The object's full name."""
        if self._class == 'variable':
            return 'var.{}'.format(self._name)
        elif self._class == 'resource':
            return '{}.{}'.format(self._type, self._name)
        else:
            return '{}.{}'.format(self._class, self._name)
        

class _resource(_base):
    """Base class for resources."""
    _class = 'resource'


class _data(_base):
    """Base class for data sources."""
    _class = 'data'

    # TODO: Work-around for https://github.com/mjuenema/python-terrascript/issues/3
    def __init__(self, name, **kwargs):
        if kwargs:
            if not 'type' in kwargs:
                kwargs['type'] = 'string'
            if not 'description' in kwargs:
                kwargs['description'] = ''
        super(_data, self).__init__(name, **kwargs)


class resource(_base):
    """Class for creating a resource for which no convenience wrapper exists."""
    _class = 'resource'
    
    def __init__(self, type_, name, **kwargs):
        self._type = type_
        super(resource, self).__init__(name, **kwargs)


class data(_base):
    """Class for creating a data source for which no convenience wrapper exists."""
    _class = 'data'
    
    def __init__(self, type_, name, **kwargs):
        self._type = type_
        super(data, self).__init__(name, **kwargs)


class module(_base):
    """Class for modules."""
    
    _class = 'module'


class variable(_base):
    """Class for variables."""
    
    _class = 'variable'
    
    
class output(_base):
    _class = 'output'
    

class provider(_base):
    _class = 'provider'
    
    
class terraform(_base):
    _class = 'terraform'
    def __init__(self, **kwargs):
        # Terraform does not have a name
        super(terraform, self).__init__(None, **kwargs)


class provisioner(UserDict):
    def __init__(self, name, **kwargs):
        self.data = {name: kwargs}


class connection(UserDict):
    def __init__(self,  **kwargs):
        self.data = kwargs


class backend(UserDict):
    def __init__(self,  name, **kwargs):
        self.data = {name: kwargs}


class _function(object):
    """Terraform function.
    
       >>> function.lookup(map, key)
       "${lookup(map, key)}"
    
    """
    
    class _function(object):
        def __init__(self, name):
            self.name = name
            
        def format(self, arg):
            """Format a function argument."""
            if isinstance(arg, _base):
                return arg.fullname
            elif isinstance(arg, str):
                return '"{}"'.format(arg)
            else:
                return arg
        
        def __call__(self, *args):
            return '${{{}({})}}'.format(self.name, ','.join([self.format(arg) for arg in args]))
    
    def __getattr__(self, name):
        return self._function(name)

f = fn = func = function = _function()
"""Shortcuts for `function()`."""


__all__ = ['config', 'dump', 'validate',
           'resource', 'data', 'module', 'variable',
           'output', 'terraform', 'provider', 
           'provisioner', 'connection', 'backend',
           'f', 'fn', 'func', 'function']
