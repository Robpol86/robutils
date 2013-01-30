#!/usr/bin/env python -u
#
# Copyright (c) 2012, Robpol86
# This software is made available under the terms of the MIT License that can
# be found in the LICENSE.txt file.
#
"""
Guarantees a single instance of the python application using a locking PID file.

Instance provides the Instance class which handles creating a user-defined PID file and implementing an exclusive file
lock to guarantee a single process is running. The main thread's PID is written to the file.

For more information:
    * import robutils.Instance; help(robutils.Instance)
    * import robutils.Instance; help(robutils.Instance.Instance._delete_pid_file_on_exit)
"""


__author__ = 'Robpol86 (http://robpol86.com)'
__copyright__ = 'Copyright 2012, Robpol86'
__license__ = 'MIT'


import os, fcntl, time, atexit
import psutil # http://code.google.com/p/psutil/


class Instance:
    """
    Main class responsible for creating and enforcing the PID file lock. Meant to be instantiated at the beginning of
    the script. If the script is supposed to demonize, use this class after demonizing.
    
    Examples
    --------
    >>> instance = Instance('/var/tmp/example_script.pid')
    >>> if not instance.single_instance_success:
    ...     if instance.old_pid_exists: print 'Another instance is running.'
    ...     if not instance.pdir_exists: print "PID file parent dir doesn't exist."
    ...     if not instance.can_write: print 'No write permissions.'
    ... 
    >>> 
    """
    
    pid = os.getpid()
    pid_file = ''
    pdir_exists = False # If parent directory exists.
    file_exists = False # If PID file already exists.
    can_write = False # If pid_file exists, if process can write to file. If not exists, if process can create file.
    old_pid_exists = False # True if old PID is running.
    single_instance_success = False # True if successfully obtained PID file lock and this is the only instance.
    _file = None # File object of PID file (build-in open() object).
    
    def __init__(self, pid_file, timeout=0):
        """
        Provide the path to the PID file and the optional timeout value (in seconds) during instantiation. If timeout
        is set, instantiation will block so many seconds waiting for the PID file to be unlocked by the running
        instance.
        
        Parameters
        ----------
        pid_file : string
            The PID file to use.
        timeout : integer, default 0
            If > 0, class instantiation will block this many number of seconds waiting for the previous instance to
            finish
        """
        # Check basics.
        self.pid_file = pid_file
        if os.path.isdir(os.path.dirname(pid_file)): self.pdir_exists = True
        if os.path.isfile(pid_file): self.file_exists = True
        if self.file_exists and os.access(pid_file, os.W_OK|os.R_OK):
            self.can_write = True
        elif self.pdir_exists and os.access(os.path.dirname(pid_file), os.W_OK):
            self.can_write = True
        # Look for previous instance.
        if self.file_exists and self.can_write:
            old_pid = ''
            with open(pid_file) as f: old_pid = f.read().strip()
            if old_pid.isdigit() and int(old_pid) in psutil.get_pid_list(): self.old_pid_exists = True
        # Wait previous instance to quit.
        if self.old_pid_exists and timeout:
            start_time = time.time()
            while int(old_pid) in psutil.get_pid_list() and time.time() - start_time < timeout:
                time.sleep(0.5)
            self.old_pid_exists = True if int(old_pid) in psutil.get_pid_list() else False
        # Bail if another instance is running.
        if self.old_pid_exists or not self.can_write: return None
        # Looks like PID file lock is guaranteed.
        self._file = open(pid_file, 'w')
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX)
        except IOError:
            # Lost the race, or something happened.
            self._file.close()
            return None
        # We're good. Writing to disk.
        self._file.write(str(self.pid))
        self._file.flush()
        os.fsync(self._file.fileno())
        self.single_instance_success = True
        atexit.register(self._delete_pid_file_on_exit) # Clean up PID file when this instance exits.
        return None
    
    def _delete_pid_file_on_exit(self):
        """
        This method isn't designed to be run manually!
        If the PID file is locked successfully, this method will be registered with atexit. When the main python therad
        shuts down, this method is called, which releases the PID file lock, deletes the file, and closes the file
        descriptor.
        """
        fcntl.flock(self._file.fileno(), fcntl.LOCK_UN) # Unlock file.
        os.remove(self._file.name) # Delete PID file.
        self._file.close() # Close the file descriptor.
        return None

