#!/usr/bin/env python -u
#
# Copyright (c) 2012, Robpol86
# This software is made available under the terms of the MIT License that can
# be found in the LICENSE.txt file.
#
"""
Executes external commands over SSH (paramiko) or locally (subprocess) with timeouts.

ExternalCmd provides the ExternalCmd class which is a wrapper for paramiko or subprocess. This class automatically
launches threads which poll the process in the background, populating the instance object with relevant data.

As a side note, when this module is imported, the function kill_children_on_exit() is registered with atexit. When the
main Python thread exits without being killed any external process launched by the parent Python process will be 
interrupted or killed (if SIGINT doesn't end the process).

For more information:
    * import robutils.ExternalCmd; help(robutils.ExternalCmd)
    * import robutils.ExternalCmd; help(robutils.ExternalCmd.kill_children_on_exit)
"""


__author__ = 'Robpol86 (http://robpol86.com)'
__copyright__ = 'Copyright 2012, Robpol86'
__license__ = 'MIT'
__all__ = ['ExternalCmd',]


import os, time, subprocess, threading, atexit
import psutil # http://code.google.com/p/psutil/
import paramiko # https://github.com/paramiko/paramiko


@atexit.register
def kill_children_on_exit():
    """
    This function isn't designed to be run manually!
    When ExternalCmd is imported, this function will automatically be added to atexit. This means when this python
    session exits (without being killed), all remaining processes launched by this python process will be killed and
    reaped (to avoid zombie processes).
    """
    for proc in psutil.Process(os.getpid()).get_children():
        try:
            proc.kill() # Kill child process.
        except psutil.NoSuchProcess:
            pass
        os.waitpid(proc.pid, os.WUNTRACED) # Avoid zombies.
    return None


class PollLocal(threading.Thread):
    """
    This class isn't designed to be used manually!
    When a local command is executed, ExternalCmd.run_local() launches an instance of this class in a thread to
    habitually poll the process until it exits or the main python thread exits. This is responsible for obtaining data
    from the external command.
    """
    
    _interrupt = False # See robutils/__init__.py: signal_threads_shutdown_imminent
    parent = None # The ExternalCmd class instance object.
    
    def __init__(self, parent):
        super(PollLocal, self).__init__()
        self.name = 'robutils.ExternalCmd.PollLocal' # Used by signal_threads_shutdown_imminent.
        self.parent = parent
        return None
    
    def run(self):
        leniency = 5 # Number of seconds to wait between SIGTERM and SIGKILL.
        sigterm = None # Time SIGTERM was sent.
        while self.parent._process.poll() == None:
            if self._interrupt: return None
            # Process still running.
            if self.parent.timeout and time.time() - self.parent.start_time >= self.parent.timeout:
                # Process timed out. There's an easy way and a hard way. The choice is yoouuurs.
                if not sigterm:
                    # Easy way.
                    sigterm = time.time()
                    try: self.parent._process.terminate()
                    except OSError: pass
                elif time.time() - sigterm >= leniency:
                    # Hard way.
                    try: self.parent._process.kill()
                    except OSError: break
            time.sleep(0.2)
        # Process is not running anymore.
        self.parent.code = self.parent._process.returncode
        self.parent.stdout, self.parent.stderr = self.parent._process.communicate()
        self.parent.end_time = time.time()
        return None


class PollRemote(threading.Thread):
    """
    This class isn't designed to be used manually!
    When a remote command is executed, ExternalCmd.run_remote() launches an instance of this class in a thread to
    habitually poll the paramiko session until it finishes or the main python thread exits. This is responsible for
    obtaining data from the SSH session.
    """
    
    _interrupt = False # See robutils/__init__.py: signal_threads_shutdown_imminent
    parent = None # The ExternalCmd class instance object.
    host = None # SSH remote hostname/IP.
    user = None # SSH username.
    key = None # SSH private key.
    port = None # SSH port on the remote host.
    
    def __init__(self, parent, host, user, key, port):
        super(PollRemote, self).__init__()
        self.name = 'robutils.ExternalCmd.PollRemote' # Used by signal_threads_shutdown_imminent.
        self.parent = parent
        self.host = host
        self.user = user
        self.key = key
        self.port = port
        return None
    
    def run(self):
        # Execute the command.
        self.parent.start_time = time.time()
        self.parent._process.connect(self.host, self.port, self.user, key_filename=self.key,
                                     timeout=self.parent.timeout) # Authenticate.
        self.parent._channel = self.parent._process.get_transport().open_session()
        self.parent._channel.exec_command(self.parent.command) # Execute the command on the remote host.
        self.parent.stdout = ''
        self.parent.stderr = ''
        while not self.parent._channel.exit_status_ready():
            if self._interrupt: return None
            # Read stdout/stderr.
            if self.parent._channel.recv_ready(): self.parent.stdout += self.parent._channel.recv(4096)
            if self.parent._channel.recv_stderr_ready(): self.parent.stderr += self.parent._channel.recv_stderr(4096)
            # Remote process still running.
            if self.parent.timeout and time.time() - self.parent.start_time >= self.parent.timeout:
                # Process timed out.
                self.parent._process.close() # Close the SSH session.
                break
            time.sleep(0.2)
        # Process is not running anymore.
        self.parent.code = self.parent._channel.recv_exit_status()
        while self.parent._channel.recv_ready(): self.parent.stdout += self.parent._channel.recv(4096)
        while self.parent._channel.recv_stderr_ready(): self.parent.stderr += self.parent._channel.recv_stderr(4096)
        self.parent._process.close()
        self.parent.end_time = time.time()
        return None


class ExternalCmd:
    """
    Main class responsible for handling external commands. Each class instance may only be used once (not designed to
    run a second command without creating another class instance).
    
    Examples
    --------
    >>> cmd = ExternalCmd('echo "test1\\ntest2\\ntest3\\n" | grep test2')
    >>> cmd.run_local()
    >>> cmd.stdout
    'test2\\n'
    >>> cmd.code
    0
    >>> cmd = ExternalCmd('echo test1 && echo test2')
    >>> cmd.run_local()
    >>> cmd.stdout
    'test1\\ntest2\\n'
    >>> cmd = ExternalCmd(['ls', '-lahd', '/tmp'])
    >>> cmd.run_local()
    >>> cmd.stdout
    'drwxrwxrwt 4 root root 32K Nov 20 04:02 /tmp\\n'
    >>> 
    
    >>> cmd = ExternalCmd('echo first && sleep 10 && echo done')
    >>> cmd.run_remote('localhost')
    >>> (cmd.code, cmd.stdout)
    (None, '')
    >>> time.sleep(10)
    >>> (cmd.code, cmd.stdout)
    (0, 'first\\ndone\\n')
    >>> 
    """
    
    command = None # Command to run. If a list: shell=False; if a string: shell=True
    timeout = None # Terminate process if timeout value is reached.
    code = None # Command's exit code.
    stdout = None
    stderr = None
    pid = None
    start_time = None
    end_time = None
    _process = None # The subprocess/paramiko object.
    _channel = None # The paramiko channel object.
    ssh_error = None # Error string related to SSH (before command is executed).
    
    def __init__(self, command, timeout=0):
        """
        Creates new class instance for an external command. This is where the command itself and the optional timeout
        value (in seconds) is given.
        
        Parameters
        ----------
        command : list or string
            The command to execute. If this is a string, the command is executed in a new interactive shell. So you can
            pass the command "ls -lah /tmp >/dev/null" with expected results. If this is a list, each list item must be
            a dedicated parameter (e.g. ['ls', '-lah', '/tmp']). A new shell will not spawn if this is a list.
        timeout : integer, default 0
            Sets the timeout value in seconds. If > 0, the external command will be terminated or killed if it runs
            longer than the timeout period.
        """
        self.command = command
        if timeout: self.timeout = timeout
        return None
    
    def run_local(self, cwd=None):
        """
        Executes the command in the class instance locally. It is the developer's job to poll this class instance's
        code or end_time members to determine when the process ends (the class will take care of polling the process
        directly every 0.2 seconds).
        
        Parameters
        ----------
        cwd : string, default None
            Use this as the current working directory if set.
        """
        if cwd: os.listdir(cwd) # Check if directory exists. No need to write my own logic for this.
        shell = False if isinstance(self.command, list) else True
        self.start_time = time.time()
        self._process = subprocess.Popen(self.command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         shell=shell)
        self.pid = self._process.pid
        thread = PollLocal(self) # Monitor the process in the background.
        thread.daemon = True
        thread.start()
        return None
    
    def run_remote(self, host, user='', key=None, port=22):
        """
        Similar to run_local(), but runs the command over SSH on a remote host using public key authentication. The key
        must not be password protected.
        
        Parameters
        ----------
        host : string
            The IP address or host name of the remote host which will execute the command.
        user : string, default ''
            The SSH user name to use. Uses the user name which owns this running python process by default.
        key : list, default None
            The SSH key to use for this session. If a default key is installed on this system it will be used if this
            parameter is left blank. Otherwise authentication will fail.
        port : integer, default 22
            The SSH port to use.
        
        See also
        --------
        http://stackoverflow.com/questions/10745138/python-paramiko-ssh
        http://stackoverflow.com/questions/3562403/how-can-paramiko-get-ssh-command-return-code
        """
        if not user: user = psutil.Process(os.getpid()).username # If user not specified, use current user.
        if isinstance(self.command, list): self.command = ' '.join(self.command)
        self._process = paramiko.SSHClient()
        self._process.load_system_host_keys()
        if host not in _process._system_host_keys:
            self.ssh_error = 'Server not found in known_hosts'
            return None
        thread = PollRemote(self, host, user, key, port)
        thread.daemon = True
        thread.start()
        return None

