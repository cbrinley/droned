###############################################################################
#   Copyright 2006 to the present, Orbitz Worldwide, LLC.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
###############################################################################

import os
import sys
import warnings
import platform
import traceback

__author__ = 'Justin Venus <justin.venus@orbitz.com>'
__doc__ = """Library to track processes. Used heavily by DroneD

This library makes use of a ``platform.system()`` loader to bring
in the proper components for a system.

If you are adding platform support you need to implement the
following methods and classes. If you are a consumer of this
library be mindful of the fact that this is all the library
guarentees.

  METHODS:
    def listProcesses():
        '''Returns a list of PID's
           @return (list)
        '''

    def findProcesses(s):
        '''Finds Process ID by pattern
           @return (dict) of LiveProcesses: regex
        '''
        

    def findThreadIds(s='.*'):
        '''Finds Threads ID by pattern
           @return (set)
        '''

    def isRunning(pid):
        '''is a given process id running

           @return (bool)
        '''

    def cpuStats():
        '''Returns a dictionary of cpu stats
           Note: stats will be platform specific
           @return (dict)
        '''

    def cpuTotalTime():
        '''Returns Total CPU Time Used in seconds
           @return (int)
        '''


  CLASSES:
    class Process(object):
        '''base class for processes'''
        implements(IKittProcess)

    class LiveProcess(Process):
        '''Get realtime access to process information'''
        implements(IKittLiveProcess)

    class ProcessSnapshot(Process):
        '''Snapshot of process information'''
        implements(IKittProcessSnapshot)

    #optionally implement, a platform agnostic implementation is provided
    class NullProcess(Process):
        '''Represents a non-existant process'''
        implements(IKittNullProcess)
"""

CPU_COUNT = os.sysconf('SC_NPROCESSORS_CONF')

class InvalidProcess(Exception): pass

from kitt.interfaces import IKittProcModule, IKittProcess, \
        IKittProcessSnapshot, IKittLiveProcess, IKittNullProcess, \
        IKittRemoteProcess, implements

#used by the platform loader at the end of this file
_process_interfaces = {
#    'Process': IKittProcess,
#    'ProcessSnapshot': IKittProcessSnapshot,
    'LiveProcess': IKittLiveProcess,
    'NullProcess': IKittNullProcess,
    'RemoteProcess': IKittRemoteProcess,
}

###############################################################################
# <PLATFORM specific=True>
# the following classes need a platform specific backend
###############################################################################
class Process(object):
    """Represents a process
       A platform specific backend should be developed
       The purpose of this class is to demonstrate
       a skeleton for the implementation of IKittProcess.
    """
    implements(IKittProcess)

    #expected attributes
    running = property(lambda s: s.isRunning())
    inode = property(lambda s: 0) #figure out how to get
    pid = property(lambda s: 0) #figure out how to get
    ppid = property(lambda s: 0) #figure out how to get
    exe = property(lambda s: None) #figure out how to get
    cmdline = property(lambda s: []) #figure out how to get
    memory = property(lambda s: s.memUsage())
    fd_count = property(lambda s: len(s.getFD()) or 3)
    stats = property(lambda s: s.getStats())
    environ = property(lambda s: s.getEnv())
    threads = property(lambda s: len(s.getTasks()))

    def __init__(self, pid):
        raise NotImplemented()
   
    def isRunning(self): return False
    def getEnv(self): return {}
    def getFD(self): return {}
    def getTasks(self): return {}
    def getStats(self): return {}
    def memUsage(self): return 0
    def cpuUsage(self): return {
        'user_util' : 0.0,
        'sys_util' : 0.0,
    }
    def __str__(self):
        return '%s(pid=%d)' % (self.__class__.__name__,self.pid)
    __repr__ = __str__


class LiveProcess(Process):
    """Get realtime access to process information"""
    implements(IKittLiveProcess)
    pass

class ProcessSnapshot(Process):
    """Snapshot of process information"""
    implements(IKittProcessSnapshot)
    pass
###############################################################################
# </PLATFORM>
###############################################################################

###############################################################################
# Platform Agnostic Implemenation
###############################################################################
class NullProcess(Process):
    """Represents a non-existant process"""
    #   Note: you should not need to override
    #     this implemenation, but you can if you
    #     want too
    implements(IKittNullProcess)
    pid = property(lambda s: 0)
    ppid = property(lambda s: 0)
    inode = property(lambda s: 0)
    exe = property(lambda s: None)
    cmdline = property(lambda s: [])
    fd_count = property(lambda s: 0)

    def __init__(self, pid=0): self._pid = 0
    def isRunning(self): return False
    def getEnv(self): return {}
    def getFD(self): return {}
    def getStats(self): return {}
    def getTasks(self): return {}
    def memUsage(self): return 0
    def cpuUsage(self): return {
        'user_util' : 0.0,
        'sys_util' : 0.0,
    }

class RemoteProcess(NullProcess):
    """This is a remote process that looks like a live process"""
    implements(IKittRemoteProcess)
    pid = property(lambda s: s.info.get('pid', 0))
    inode = property(lambda s: s.info.get('inode', 0))
    ppid = property(lambda s: s.info.get('ppid', 0))
    memory = property(lambda s: s.info.get('memory', 0))
    fd_count = property(lambda s: s.info.get('fd_count', 0))
    stats = property(lambda s: s.info.get('stats', {}))
    threads = property(lambda s: s.info.get('threads', 0))
    exe = property(lambda s: s.info.get('exe', None))
    cmdline = property(lambda s: s.info.get('cmdline', []))
    environ = property(lambda s: s.info.get('environ', {}))
    def __init__(self, pid):
        self.info = {'pid': pid}
    def updateProcess(self, infoDict):
        self.info.update(infoDict)
    def isRunning(self): return bool(self.pid)
    def memUsage(self): return self.memory
    def getFD(self): return [ i for i in self.fd_count ]
    def getStats(self): return self.stats
    def getEnv(self): return self.environ
    def getTasks(self): return set([ i for i in self.threads ])
    def cpuUsage(self):
        return {
            'user_util': self.info.get('user_util', 0.0),
            'sys_util': self.info.get('sys_util', 0.0),
        }
    def __str__(self): return '%s(pid=%d)' % (self.__class__.__name__, self.pid)
    __repr__ = __str__

###############################################################################
# Platform Agnostic Implemenation
###############################################################################


###############################################################################
# <required_methods fatal=True default_throw_exceptions=True>
###############################################################################
def listProcesses():
    """Returns a list of PID's"""
    raise NotImplemented()

def findProcesses(s):
    """Finds Process ID by pattern"""
    raise NotImplemented()

def findThreadIds(s='.*'):
    """Finds Threads ID by pattern"""
    raise NotImplemented()

def isRunning(pid):
    """is a given process id running, returns Boolean"""
    raise NotImplemented()

def cpuStats():
    """Returns a dictionary of cpu stats
       Note: stats will be platform specific
    """
    raise NotImplemented()

def cpuTotalTime():
    """Returns Total CPU Time Used in seconds"""
    raise NotImplemented()
###############################################################################
# </required_methods>
###############################################################################

_required_methods = [
    'listProcesses',
    'findProcesses',
    'findThreadIds',
    'isRunning',
    'cpuStats',
    'cpuTotalTime',
]

#exportable interfaces
_EXPORTED = set(_process_interfaces.keys() + _required_methods)

def _load_backend(_backend, _platform):
    """load a process backend"""
    name = None
    _has_all = False
    try:
        name = __name__ + '.' + _platform
        mod = __import__(name, {}, {}, [_platform])
        #validate the module interface
        if not IKittProcModule.providedBy(mod):
            e = ImportError("%s does not implement IKittProcModule interface" \
                    % name)
            raise e #throw exception as an import error
        if '__all__' in vars(mod):
            _EXPORTED.update(set(mod.__all__))
            _has_all = True
        for var, obj in vars(mod).items():
            if hasattr(obj, '__class__') and var in _process_interfaces:
                #demonstrate you at least read the implementation
                if not _process_interfaces[var].implementedBy(obj):
                    e = 'Class [%s] from %s does not match interface' % \
                            (var,name) 
                    warnings.warn(e)
                    continue
            #update our namespace
            globals().update({var: obj})
            if _has_all: continue
            #add to exported interfaces
            if not var.startswith('_'):
                _EXPORTED.add(var)
    except ImportError: raise
    except AssertionError: pass
    except: traceback.print_exc()

_success = False
#try to load backends
try:
    _platform = 'psutil_backend'
    #try import the generic backend, validate it and expose it
    _backend = os.path.join(
       os.path.abspath(os.path.dirname(__file__)), 
       _platform + '.py'
    )
    _load_backend(_backend, _platform)
    _success = True
except ImportError:
    _platform = platform.system()
    #try to import the platform specific backend, validate it and expose it
    _backend = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 
        _platform + '.py'
    )
    if os.path.exists(_backend):
        try:
            _load_backend(_backend, _platform)
            _success = True
        except ImportError: pass

if not _success:
    e = 'Platform %s is not supported, expect problems' % (platform.system(),)
    warnings.warn(e)


from kitt.decorators import raises, debugCall
class _Cache(type):
    """Trap exceptions when instantiating one of the providers. Cache process
       objects to avoid IO impact on some platforms. This also allows us to
       do some tricks with adapters in the higher levels to swap running
       representations of processes to no longer running in a seamless manor.
    """
    def __init__(klass, name, bases, members):
        super(_Cache, klass).__init__(name, bases, members)
        klass._cache = {}

    def delete(klass, instance):
        for instanceID, _instance in klass._cache.items():
            if _instance is instance:
                del klass._cache[ instanceID ]
                return

    def exists(klass, pid):
        return bool(pid in klass._cache)

    @raises(InvalidProcess)
    def __call__(klass, *args, **kwargs):
        instanceID = args[0] #must be the pid
        try: return klass._builder(*args, **kwargs)
        except KeyError: raise #already expired out
        except: #safety so we don't reference leak
            if instanceID in klass._cache:
                klass.delete(klass._cache[instanceID])
            raise #don't forget to re-raise

    def _builder(klass, *args, **kwargs):
        instanceID = args[0] #must be the pid
        if klass.exists(instanceID) and not \
                klass._cache[ instanceID ].isRunning():
            #expire on look up if no longer running
            klass.delete(klass._cache[instanceID])
            raise AssertionError('Invalid pid %d' % instanceID)
        if not klass.exists(instanceID):
            klass._cache[instanceID] = klass.__new__(klass, *args, **kwargs)
            klass._cache[instanceID].__init__(*args, **kwargs)
        #key error becomes invalid process
        return klass._cache[instanceID]

#basically wrap exceptions on instantiation and cache instances
#Process = _Cache('Process', (Process,), {})
LiveProcess = _Cache('LiveProcess', (LiveProcess,), {})
#ProcessSnapshot = _Cache('ProcessSnapshot', (ProcessSnapshot,), {})

from kitt.decorators import deferredAsThread
from twisted.internet import defer
from twisted.python.failure import Failure
import time
class ProcessSnapshot(object):
    """Snapshot of process information"""
    implements(IKittProcessSnapshot)
    info = property(lambda s: s._data)
    pid = property(lambda s: s._pid)
    inode = property(lambda s: s.info.get('inode', 0))
    ppid = property(lambda s: s.info.get('ppid', 0))
    memory = property(lambda s: s.memUsage())
    fd_count = property(lambda s: len(s.getFD()) or 3)
    stats = property(lambda s: s.getStats())
    threads = property(lambda s: s.info.get('threads', 0))
    exe = property(lambda s: s.info.get('exe', None))
    environ = property(lambda s: s.getEnv())
    cmdline = property(lambda s: s.info.get('cmdline', []))
    running = property(lambda s: s.isRunning())
    uid = property(lambda s: s.info.get('uid', 0))
    gid = property(lambda s: s.info.get('gid', 0))

    def __init__(self, pid):
        self.deferred = defer.succeed(None)
        self._lastupdate = 0
        self._pid = pid
        self._data = {}
        try:
            LiveProcess(pid) #warm the cache
            from twisted.internet import reactor
            reactor.callLater(1.0, self.update)
        except InvalidProcess:
            self.__class__.delete(self)

    def isRunning(self):
        try: return LiveProcess(self.pid).running
        except: #destroy stats on death
            self.__class__.delete(self)
            self._data = {}
            return False

    @defer.deferredGenerator
    def update(self):
        result = {}
        try:
            if not self.deferred.called:
                wfd = defer.waitForDeferred(self.deferred)
                yield wfd
                result = wfd.getResult()
            elif (time.time() - self._lastupdate) < 10:
                result = self._data #throttle scans
            else:
                self._lastupdate = time.time()
                self.deferred = self._get_updates()
                wfd = defer.waitForDeferred(self.deferred)
                yield wfd
                self._data.update(wfd.getResult())
                result = self._data
        except:
            self.__class__.delete(self)
            self._data = {} #destroy stats on death
            result = Failure()
        yield result

    def getTasks(self):
        return self.info.get('getTasks', set())

    def getStats(self):
        return self.info.get('getStats', {})

    def getFD(self):
        return self.info.get('getFD', {})

    def getEnv(self):
        return self.info.get('getEnv', {})

    def memUsage(self):
        return self.info.get('memUsage', 0)

    def cpuUsage(self):
        return self.info.get('cpuUsage', {'user_util': 0.0, 'sys_util': 0.0})

    @deferredAsThread
    def _get_updates(self):
        """lots of io in here on most platforms"""
        #each look will keep the process honest
        return {
            'getTasks': LiveProcess(self.pid).getTasks(),
            'getStats': LiveProcess(self.pid).getStats(),
            'memUsage': LiveProcess(self.pid).memUsage(),
            'cpuUsage': LiveProcess(self.pid).cpuUsage(),
            'getFD': LiveProcess(self.pid).getFD(),
            'getEnv': LiveProcess(self.pid).getEnv(),
            'ppid': LiveProcess(self.pid).ppid,
            'cmdline': LiveProcess(self.pid).cmdline,
            'exe': LiveProcess(self.pid).exe,
            'uid': LiveProcess(self.pid).uid,
            'gid': LiveProcess(self.pid).gid,
            'inode': LiveProcess(self.pid).inode,
            'threads': LiveProcess(self.pid).threads
        }

    def __str__(self):
        return '%s(pid=%d)' % (self.__class__.__name__,self.pid)
    __repr__ = __str__
ProcessSnapshot = _Cache('ProcessSnapshot', (ProcessSnapshot,), {})


import re
def _findProcesses(s):
    regex = re.compile(s,re.I)
    #we are using listProcess b/c we may be optimized
    for pid in listProcesses():
        try: process = LiveProcess(pid, fast=True)
        except: continue #handle unexpected death
        if platform.system() == 'Linux':
            #skip children of the kernel and kthreadd
            if process.ppid in (0, 2): continue
        cmd = ' '.join(process.cmdline)
        if not cmd: continue
        match = regex.search(cmd)
        if not match: continue
        #no point in creating yet another object
        yield (process, match)

def findProcesses(s):
    """Finds Process ID by pattern"""
    return dict(_findProcesses(s))

def findThreadIds(s='.*'):
    """Finds Threads ID by pattern"""
    tids = set()
    try:
        for p,m in _findProcesses(s):
            tids.update(p.getTasks())
    except: pass
    return tids


#export public attributes, methods, and classes
__all__ = list(_EXPORTED)
