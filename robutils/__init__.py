#!/usr/bin/env python -u
#
# Copyright (c) 2012, Robpol86
# This software is made available under the terms of the MIT License that can
# be found in the LICENSE.txt file.
#
"""
Convenience classes for CLI Python applications.

robutils is a module providing a handful of convenient classes designed for use in command line python applications.
It is designed for Python 2.7.3+ on Linux. Included are the following features:
    * Wrapper for executing external commands over SSH (paramiko) or locally (subprocess) with timeouts.
    * Enforce single instances using locking PID files.
    * Color text on Bash terminals, demonizing the main process, console redirects (for Altiris), logging, and email.
    * Centralizing exit messages for different exit codes. Also useful for Altiris.
    * Progress bar with ETA.

The following Python packages are required:
    * psutil >= 0.6.1 <http://code.google.com/p/psutil>
    * paramiko >= 1.9.0 <http://pypi.python.org/pypi/paramiko>
    * pandas >= 0.9.1 <http://pypi.python.org/pypi/pandas>

For more information, documentation, and examples:
    * Visit https://github.com/Robpol86/robutils
    * import robutils; help(robutils)
    * import robutils.ExternalCmd; help(robutils.ExternalCmd)
    * import robutils.Instance; help(robutils.Instance)
    * import robutils.Message; help(robutils.Message)
    * import robutils.Progress; help(robutils.Progress)
"""


__author__ = 'Robpol86 (http://robpol86.com)'
__copyright__ = 'Copyright 2012, Robpol86'
__license__ = 'MIT'
__all__ = []


import atexit, threading, time


@atexit.register
def signal_threads_shutdown_imminent():
    """
    This function isn't designed to be run manually!
    All threads created by robutils have the word "robutils" set somewhere in the thread_object.name class member. Each
    thread also has thread_object._interrupt = False. When the main Python thread exits, this function will be called
    which will set _interrupt = True on all robutils threads, and give them about one second to clean up before the 
    main thread shuts down.
    """
    if threading.active_count() <= 1: return None # No threading threads running.
    for thread in [t for t in threading.enumerate() if 'robutils' in t.name]: thread._interrupt = True
    for s in [0.10, 0.20, 0.35, 0.35]:
        # Wait 1 second for threads to shutdown.
        if not len([t for t in threading.enumerate() if 'robutils' in t.name]): break
        time.sleep(s)
    return None
