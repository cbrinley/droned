###############################################################################
#   Copyright 2012 to the present, Orbitz Worldwide, LLC.
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

#required interfaces that we have to implement
from kitt.interfaces import IKittProcess, IKittLiveProcess, \
        IKittProcessSnapshot,IKittProcModule, implements, moduleProvides
moduleProvides(IKittProcModule)

import psutil
import re
import platform
import os

#special case optimization for file based proc
_special_case = {
    'Linux': '/proc',
    'SunOS': '/proc',
    'FreeBSD': '/proc'
}
_platform = platform.system()
#file based proc that is enabled and populated
if _platform in _special_case and os.listdir(_special_case[_platform]):
    HAS_PROC_DIR = True
    PROC_DIR = _special_case[_platform]
else:
    HAS_PROC_DIR = False
    PROC_DIR = None

__doc__ = """
Uses the psutil project to fill in other platform support

seems to work on psutil 0.3.0+

http://code.google.com/p/psutil/
"""

__author__ = "Justin Venus <justin.venus@orbitz.com>"

#TODO Exception handling

class Process(object):
    """provide a droned compatible interface by delegating
       the heavy work to ``psutil`` if it is available.

       see kitt.interfaces.process.IKittProcess for a
       full api description.
    """
    implements(IKittProcess)
    ps = property(lambda s: s._delegate)
    running = property(lambda s: s.isRunning())
    memory = property(lambda s: s.ps.get_memory_info().rss)
    inode = property(lambda s: s._saved_inode)
    fd_count = property(lambda s: len(s.getFD()))
    stats = property(lambda s: s.getStats())
    environ = property(lambda s: s.getEnv())

    cmdline = property(lambda s: s._cmdline)
    exe = property(lambda s: s._exe)
    uid = property(lambda s: s._uid)
    gid = property(lambda s: s._gid)
    pid = property(lambda s: s._pid)
    ppid = property(lambda s: s.ps.ppid) #could be reparented

    @property
    def threads(self):
        try: return self.ps.get_num_threads()
        except: return 1

    def _make_exe(self):
        """work around access errors"""
        try: return self.ps.exe
        except: #work around not having any args to guess at
            try: return self.cmdline[0] #next best guess
            except IndexError:
                return self.ps.name #totally making this up now

    def _make_inode(self):
        """may not be supported on all systems so we do it ourselves"""
        #on linux and solaris, we could just check the inode of the
        #process as os.stat(/proc/%(PID)d).st_ino, but this is obviously 
        #not portable, so we will just hash some static values from the
        #process and hope for the best. DroneD needs the inode to track
        #long running applications easily even if droned is down for
        #long periods of time.
        if HAS_PROC_DIR: #this is an optimization
            return os.stat(os.path.join(PROC_DIR,str(self.pid))).st_ino
        #this may use more IO than we like
        return hash((self.exe, self.pid, self.ps.create_time, self._name) + \
                tuple(self.ps.cmdline)) & 0xffffffff #make sure return is positive

    def __init__(self, pid):
        if type(pid) != int:
            raise ValueError('Pid must be an integer')
        self._delegate = psutil.Process(pid)
        #avoid looking these attr's up all of the time. 
        #IO is expensive and the following attr's should be
        #static anyhow.
        self._name = self.ps.name
        self._pid = self.ps.pid
        self._cmdline = self.ps.cmdline
        self._uid = self.ps.uids.real
        self._gid = self.ps.gids.real
        self._exe = self._make_exe()
        #save this for running tests
        self._saved_inode = self._make_inode()
        if not self.running:
            raise AssertionError("Invalid PID (%d)" % self.pid)

    def isRunning(self):
        """make sure not only the pid is running but it is the same process 
           we thought it was.  this is done naively with a simple hash.
        """
        if not self.ps.is_running():
            return False
        #make sure this is the same process we thought it was
        return bool(self._make_inode() == self.inode)

    def getEnv(self):
        """not portable so not implemented"""
        return {}

    def getFD(self):
        #every os has stdin, stdout, and stderr
        FDS = {0: None, 1: None, 2: None}
        try:
            FDS.update(dict((i.fd,i.path) for i in self.ps.get_open_files()))
        except: pass
        return FDS

    def getTasks(self):
        """get the thread id's"""
        try: return set(t.id for t in self.ps.get_threads())
        except: return set()

    def getStats(self):
        """not portable so not implemented"""
        return {}

    def memUsage(self):
        """get memory usage in bytes"""
        return self.memory

    def waitForDeath(self, timeout=10, delay=0.25):
        """wait for the process to die"""
        #delay isn't needed, but it is part of the interface
        #definition, so we'll leave it as a dummy.
        try: self.ps.wait(timeout)
        except: pass #not sure if it is needed
        return not self.running

    def __str__(self):
        return '%s(pid=%d)' % (self.__class__.__name__,self.pid)
    __repr__ = __str__


###############################################################################
# the other classes don't really do anything interesting.
###############################################################################
class LiveProcess(Process):
    implements(IKittLiveProcess)
    def __init__(self, pid, fast=False):
        """swallowing unused constructor arg"""
        Process.__init__(self, pid)

    def cpuUsage(self):
        cpu = self.ps.get_cpu_times()
        return {
            'user_util' : cpu.user,
            'sys_util' : cpu.system
        }


class ProcessSnapshot(Process):
    implements(IKittProcessSnapshot)
    def update(self): pass


###############################################################################
# Interface required module methods
###############################################################################
def listProcesses():
    """Returns a list of PID's"""
    if HAS_PROC_DIR:
        try: return [int(p) for p in os.listdir(PROC_DIR) if p.isdigit()]
        except: pass #rather be slow than blow up
    return psutil.get_pid_list()

def _findProcesses(s):
    regex = re.compile(s,re.I)
    #we are using listProcess b/c we may be optimized
    for pid in listProcesses():
        try: process = LiveProcess(pid)
        except: continue #handle unexpected death
        if _platform == 'Linux':
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
    try: return dict(_findProcesses)
    except return {}

def findThreadIds(s='.*'):
    """Finds Threads ID by pattern"""
    tids = set()
    try:
        for p,m in _findProcesses(s):
            tids.update(p.getTasks())
    except: pass
    return tids

#TODO
def cpuStats():
    return {}

#TODO
def cpuTotalTime():
    return float()

def isRunning(pid):
    """is a given process id running, returns Boolean"""
    if HAS_PROC_DIR: #yet another optimization
        return os.path.exists(os.path.join(PROC_DIR,str(pid)))
    try: return Process(int(pid)).running
    except: return False

#no new attributes, methods, or classes to expose
__all__ = []
