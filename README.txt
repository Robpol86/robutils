========
robutils
========

robutils is a Python module that provides a handful of convenient classes mainly for command line applications, but
will work in any Python script. It is designed for **Python 2.7.3** on **Linux** systems, and may work on OS X and
other Unix-based systems. robutils may also work on other platforms and Python versions but this is not supported.

Some of the features of robutils are:

* Wrapper for executing external commands over SSH (paramiko) or locally (subprocess) with timeouts.
* Enforce single instances using locking PID files.
* Color text on Bash terminals, demonizing the main process, console redirects (for Altiris), logging, and email.
* Centralizing exit messages for different exit codes. Also useful for Altiris.
* Progress bar with ETA.

Installation
============

The following Python packages are required as prerequisites:

* `psutil <http://code.google.com/p/psutil>`_ >= 0.6.1
* `paramiko <http://pypi.python.org/pypi/paramiko>`_ >= 1.9.0
* `pandas <http://pypi.python.org/pypi/pandas>`_ >= 0.9.1

To install run one of the following commands::

    pip install robutils
    easy_install robutils
    git clone https://github.com/Robpol86/robutils.git; cp -r robutils/robutils /usr/lib/python2.7/site-packages/

Once installed, additional documentation is available within docstrings::

    >>> import robutils; help(robutils)

Quick links
===========

* `Home page <https://github.com/Robpol86/robutils>`_
* `Download <http://code.google.com/p/robutils/downloads/list>`_

Examples
========

|kjVlbuk|_

.. |kjVlbuk| image:: http://i.imgur.com/kjVlbukm.png
.. _kjVlbuk: http://i.imgur.com/kjVlbuk.png

|pPI3ePX|_

.. |pPI3ePX| image:: http://i.imgur.com/pPI3ePXm.png
.. _pPI3ePX: http://i.imgur.com/pPI3ePX.png

|Avdq73Y|_

.. |Avdq73Y| image:: http://i.imgur.com/Avdq73Ym.png
.. _Avdq73Y: http://i.imgur.com/Avdq73Y.png

|du2IWZ6|_

.. |du2IWZ6| image:: http://i.imgur.com/du2IWZ6m.png
.. _du2IWZ6: http://i.imgur.com/du2IWZ6.png

|uOQVrxB|_

.. |uOQVrxB| image:: http://i.imgur.com/uOQVrxBm.png
.. _uOQVrxB: http://i.imgur.com/uOQVrxB.png

Message
-------

1. Easy to use color syntax for Linux Bash terminals (.term() hides the class instance from the interactive console)::

    >>> from robutils.Message import Message
    >>> message = Message()
    >>> message('Sample text.')
    Sample text.
    <robutils.Message.Message instance at 0x107e4d0>
    >>> message('Colors: [red]red[/red] and [hiblue]multi[hired]colored[bgyellow]text[/all].').term()
    Colors: red and multicoloredtext.
    >>>

2. Print messages to stdout, stderr, and/or log to file (with colors)::

    >>> from robutils.Message import Message
    >>> message = Message(log_file='/tmp/test.log', log_level='error')
    >>> message('Regular stdout non-logged text.').term()
    Regular stdout non-logged text.
    >>> message('stderr non-logged text.', stderr=True).term()
    stderr non-logged text.
    >>> message('stdout and logged as info.').log().term()
    stdout and logged as info.
    >>> message('[red]only logged as error[/all].', quiet=True).log('error').term()
    >>> message('stdout, but not logged since debug < error').log('debug').term()
    stdout, but not logged since debug < error
    >>>

3. Centralize messages for different exit codes. Also supports terminating the script with different exit codes::

    [testuser@localhost ~]$ ~/python27/bin/python
    Python 2.7.3 (default, Nov 24 2012, 23:17:40)
    [GCC 4.4.6 20120305 (Red Hat 4.4.6-4)] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    >>> from robutils.Message import Message
    >>> message = Message()
    >>> message.retcodes[1] = 'An error occurred.'
    >>> message.retcodes[5] = 'Error doing x, check file y.'
    >>> message.retcodes[6] = 'Error doing a, check file b.'
    >>> message.quit(5)
    
    
    QUITTING: Error doing x, check file y.
    [testuser@localhost ~]$

4. Send email via SMTP or local sendmail. Supports a tail of the log and/or file attachments::

    >>> from robutils.Message import Message
    >>> message = Message(mail_smtp='smtp-server.austin.rr.com',
    ...     mail_from='test@gmail.com',
    ...     mail_to='robpol86@robpol86.com')
    >>> message.mail('Test Email', body='This is a test email.').term()
    >>>

5. Demonize scripts and/or redirect stdout/stderr to a file (useful for Altiris scripts)::

    from robutils.Message import Message
    message = Message(daemon=True, redirect='/tmp/redir.txt')
    message("[hiblue]This is a test[/all]")
    message.retcodes[1] = 'Exiting sample script.'
    message.quit(1)

ExternalCmd
-----------

1. Run external commands on the local machine::

    >>> from robutils.ExternalCmd import ExternalCmd
    >>> cmd = ExternalCmd('echo "test1\ntest2\ntest3\n" | grep test2')
    >>> cmd.run_local()
    >>> cmd.stdout
    'test2\n'
    >>> cmd.code
    0
    >>> cmd = ExternalCmd('echo test1 && echo test2')
    >>> cmd.run_local()
    >>> cmd.stdout
    'test1\ntest2\n'
    >>> cmd = ExternalCmd(['ls', '-lahd', '/tmp'])
    >>> cmd.run_local()
    >>> cmd.stdout
    'drwxrwxrwt 4 root root 32K Nov 20 04:02 /tmp\n'
    >>> 

2. Run external commands on a remote host using SSH::

    >>> from robutils.ExternalCmd import ExternalCmd
    >>> cmd = ExternalCmd('echo first && sleep 10 && echo done')
    >>> cmd.run_remote('localhost')
    >>> (cmd.code, cmd.stdout)
    (None, '')
    >>> time.sleep(10)
    >>> (cmd.code, cmd.stdout)
    (0, 'first\ndone\n')
    >>> 

Progress
--------

1. Create a progress bar and manually display the summary periodically::

    >>> from robutils.Progress import Progress
    >>> from robutils.Message import Message
    >>> message = Message()
    >>> progress = Progress(43)
    >>> while progress.total_percent < 80:
    ...     time.sleep(1)
    ...     progress.inc_pass() if random.randint(1, 5) < 5 else progress.inc_fail()
    >>> message(progress.summary())
      81% (35/43) [########################      ] eta 0:00:06 - 14% ( 5/35) failed
    >>> message(progress.summary(hide_failed=True))
      81% (35/43) [#######################################          ] eta 0:00:03 \
    >>> message(progress.summary(max_width=70))
      81% (35/43) [################    ] eta 0:00:01 | 14% ( 5/35) failed
    >>> message(progress.summary(hide_failed=True, eta_countdown=False))
      81% (35/43) [#################################        ] eta 11:45:30 PM CST /
    >>> while progress.total_percent < 100: progress.inc_pass()
    >>> message(progress.summary())
     100% (43/43) [##############################] eta 0:00:00 - 11% ( 5/43) failed
    >>> 

2. Have the progress bar print periodically in the provided threaded method::

    >>> from robutils.Progress import Progress
    >>> from robutils.Message import Message
    >>> message = Message()
    >>> progress = Progress(43)
    >>> progress.threaded_summary(message, hide_failed=True)
    >>> while progress.total_percent < 100:
    ...     time.sleep(1)
    ...     progress.inc_pass() if random.randint(1, 5) < 5 else progress.inc_fail()
    >>> print
     100% (43/43) [#################################################] eta 0:00:00 /

Instance
--------
::

    >>> from robutils import Instance
    >>> instance = Instance('/var/tmp/example_script.pid')
    >>> if not instance.single_instance_success:
    ...     if instance.old_pid_exists: print 'Another instance is running.'
    ...     if not instance.pdir_exists: print "PID file parent dir doesn't exist."
    ...     if not instance.can_write: print 'No write permissions.'


Supplemental Installation Steps
===============================

This section details how I setup my custom Python environment, which includes packages unrelated to robutils.

CentOS 6.3
----------

Run this as a non-root user::

    sudo yum install gcc gcc-c++ autoconf automake make
    sudo yum install sqlite-devel bzip2-devel tk-devel readline-devel ncurses-devel openssl-devel gdbm-devel
    sudo yum install libxslt-devel atlas-devel gcc-gfortran
    mkdir -p Python27_Build/python27 && cd Python27_Build
    curl http://python.org/ftp/python/2.7.3/Python-2.7.3.tar.bz2 |tar --strip-components=1 -xj
    vim Modules/_sqlite/connection.c # CentOS, http://bugs.python.org/issue14572
    ./configure --prefix="$(pwd)/python27" && make clean && make
    make install
    wget "http://pypi.python.org/packages/2.7/s/setuptools/setuptools-0.6c11-py2.7.egg"
    (export PATH=/bin:/usr/bin:$(pwd)/python27/bin; sh setuptools-0.6c11-py2.7.egg)
    ./python27/bin/easy_install pip
    ./python27/bin/pip install nose docutils distribute NumPy
    ./python27/bin/pip install SciPy pandas
    ./python27/bin/pip install pytz lxml psutil paramiko mutagen winpdb robutils
    find ./python27 \( -name '*.pyc' -o -name '*.pyo' \) -exec rm {} \;
    find ./python27 -name *egg-info* -exec rm -r {} \;
    tar -czf python27-$(date +%Y%m%d).tar.gz python27

Windows 7/8
-----------

This is out of scope for this project since Windows is not supported, but I left it here for future reference::

    rem Root: %localappdata%\python27
    rem http://www.enthought.com/products/epd_free.php (includes Python)
    rem http://www.wxpython.org/download.php#binaries
    easy_install pip pytz pygments
    easy_install http://pypi.python.org/packages/source/p/python-dateutil/python-dateutil-1.5.tar.gz
    pip install winpdb
    rem http://pypi.python.org/pypi/pandas
    ipython notebook --pylab=inline

