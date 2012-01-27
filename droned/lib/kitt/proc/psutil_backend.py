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

from kitt.decorators import safe

import psutil
import re

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
    running = property(lambda s: s.ps.is_running())
    pid = property(lambda s: s.ps.pid)
    ppid = property(lambda s: s.ps.ppid)
    exe = property(lambda s: s.ps.exe)
    cmdline = property(lambda s: s.ps.cmdline)
    memory = property(lambda s: s.ps.get_memory_info().rss)
    fd_count = property(lambda s: len(s.getFD()) or 3)
    stats = property(lambda s: s.getStats())
    environ = property(lambda s: s.getEnv())
    uid = property(lambda s: s.ps.uids.real)
    gid = property(lambda s. s.ps.gids.real)

    @property
    @safe(1)
    def threads(self):
        return self.ps.get_num_threads()

    @property
    def inode(self):
        """may not be supported on all systems so we do it ourselves"""
        #on linux and solaris, we could just check the inode of the
        #as os.stat(/proc/%(PID)d).st_ino, but this is obviously not
        #portable, so we will just hash some static values from the
        #process and hope for the best. DroneD needs the inode to track
        #long running applications easily even if droned is down for
        #long periods of time.
        return hash((self.exe, self.pid, self.ps.create_time, self.running) + \
                tuple(self.cmdline)) & 0xffffffff #make sure return is positive

    def __init__(self, pid):
        """I can either create a L{psutil.Process}
           as an informal adapter or an int as a pid
           and delagate methods to a L{psutil.Process}

           @param pid C{int} or L{psutil.Process}
        """
        if isinstance(pid, psutil.Process):
            self._delegate = pid
        elif type(pid) == int:
            self._delegate = psutil.Process(pid)
        else: #next statement isn't true but ... see findProcess way below
            raise ValueError('Pid must be an integer')

    def isRunning(self):
        return self.running

    def getEnv(self):
        """not portable so not implemented"""
        return {}

    @safe({1: None, 2: None, 3: None})
    def getFD(self):
        FDS = dict((i.fd,i.path) for i in self.ps.get_open_files())
        #every os has stdin, stdout, and stderr
        FDS.update({1: None, 2: None, 3: None})
        return FDS

    @safe(set())
    def getTasks(self):
        return set(t.id for t in self.ps.get_threads())

    def getStats(self):
        """not portable so not implemented"""
        return {}

    def memUsage(self):
        return self.memory

    def waitForDeath(self, timeout=10, delay=0.25):
        #delay isn't needed, but it is part of the interface
        #definition, so we'll leave it as a dummy.
        try: self.ps.wait(timeout)
        except: pass #not sure if it is needed
        return not self.running

###############################################################################
# the other classes don't really do anything interesting.
###############################################################################
class LiveProcess(Process):
    implements(IKittLiveProcess)
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
    return psutil.get_pid_list()

@safe({})
def findProcesses(s):
    """Finds Process ID by pattern"""
    regex = re.compile(s,re.I)
    def _inner():
        for process in psutil.process_iter():
            cmd = ' '.join(process.cmdline)
            match = regex.search(cmd)
            if not match: continue
            #no point in creating yet another object
            yield (LiveProcess(process), match)
    return dict(_inner())

def findThreadIds(s='.*'):
    """Finds Threads ID by pattern"""
    tids = set()
    for p in findProcesses(s).keys():
        tids.update(p.getTasks())
    return tids

#TODO
def cpuStats():
    return {}

#TODO
def cpuTotalTime():
    return float()

@safe(False)
def isRunning(pid):
    """is a given process id running, returns Boolean"""
    return Process(int(pid)).running

#no new attributes, methods, or classes to expose
__all__ = []
