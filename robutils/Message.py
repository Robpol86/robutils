#!/usr/bin/env python -u
#
# Copyright (c) 2012, Robpol86
# This software is made available under the terms of the MIT License that can
# be found in the LICENSE.txt file.
#
"""
Uses simple bbcode-style formatting for displaying color text in Bash (or similar) shells.

Message primarily provides an easy to use syntax for displaying color text in Bash and other shells which use the same
escape codes. In addition to color text/backgrounds, the Message class provides the following features:
    * Demonizing the main process.
    * Console redirects: redirect stderr and stdout to a file (useful for Altiris)
    * Logging and sending email (with attachments or a tail of the log).
    * Centralizing exit messages for different exit codes (also useful for Altiris).

For more information:
    * import robutils.Message; help(robutils.Message)
    * import robutils.Message; help(robutils.Message.Message.special.keys())
"""


__author__ = 'Robpol86 (http://robpol86.com)'
__copyright__ = 'Copyright 2012, Robpol86'
__license__ = 'MIT'


import os, sys, re, time, logging, collections, email, mimetypes, smtplib, subprocess, socket, atexit, datetime
import psutil # http://code.google.com/p/psutil/


class Message:
    """
    Main class responsible for color text/backgrounds, demonization, console redirecting, logging, emailing, and exit
    messages.
    
    Examples
    --------
    >>> message = Message()
    >>> message('Sample text.')
    Sample text.
    <robutils.Message.Message instance at 0x107e4d0>
    >>> message('Colors: [red]red[/red] and [hiblue]multi[hired]colored[bgyellow]text[/all].').term()
    Colors: red and multicoloredtext.
    >>> 
    
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
    
    >>> message = Message(mail_smtp='smtp-server.austin.rr.com',
    ...     mail_from='test@gmail.com',
    ...     mail_to='robpol86@robpol86.com')
    >>> message.mail('Test Email', body='This is a test email.').term()
    >>> 
    
    #!/home/testuser/python27/bin/python -u
    from robutils.Message import Message
    message = Message(daemon=True, redirect='/tmp/redir.txt')
    message("[hiblue]This is a test[/all]")
    message.retcodes[1] = 'Exiting sample script.'
    message.quit(1)
    """
    
    # http://www.understudy.net/custom.html http://wiki.bash-hackers.org/scripting/terminalcodes
    # http://en.wikipedia.org/wiki/ANSI_escape_code
    special = dict(b=1, i=3, u=4, flash=5, outline=6, negative=7, invis=8, strike=9)
    special.update({'/all':0, '/attr':10, '/b':22, '/i':23, '/u':24, '/flash':25, '/outline':26, '/negative':27,
        '/strike':29, '/fg':39, '/bg':49})
    special.update(dict(black=30, red=31, green=32, brown=33, blue=34, purple=35, cyan=36, gray=37))
    special.update(dict(bgblack=40, bgred=41, bggreen=42, bgbrown=43, bgblue=44, bgpurple=45, bgcyan=46, bggray=47))
    special.update(dict(hiblack=90, hired=91, higreen=92, hibrown=93, hiblue=94, hipurple=95, hicyan=96, higray=97))
    special.update(dict(hibgblack=100, hibgred=101, hibggreen=102, hibgbrown=103, hibgblue=104, hibgpurple=105,
        hibgcyan=106, hibggray=107))
    special.update(dict(pink=95, yellow=93, white=97, bgyellow=103, bgpink=105, bgwhite=107))

    log_levels = dict(critical=logging.CRITICAL, error=logging.ERROR, warning=logging.WARNING, info=logging.INFO,
        debug=logging.DEBUG)
    greeting = time.localtime(psutil.Process(os.getpid()).create_time)
    greeting = ' Script Started on {0} '.format(time.strftime('%Y-%m-%d %H:%M:%S %Z', greeting)).center(79, '=')
    valediction = ''
    retcodes = {} # Example: {0:'Script ran successfully', 1:'Unknown error occurred, check log'}
    
    _s = None
    _quiet = None
    _log_file = None
    _log_level = None
    _mail_smtp = None
    _mail_from = None
    _mail_to = []
    
    def __init__(self, quiet=False, daemon=False, redirect='', log_file='', log_level='info',
                 mail_smtp='', mail_from='', mail_to=[]):
        """
        Simplifies printing color text to bash terminals. Also handles terminating the script with exit codes, printing
        custom messages depending on the code used (so you can organize all of the exit messages at the top of the
        script). Other tasks are logging, emailing, console redirection, and demonization.
        
        Parameters
        ----------
        quiet : boolean, default False
            If set to true, nothing will print to stdout/stderr. Used when logging is desired without printing (debug
            messages, etc).
        daemon : boolean, default False
            If true, will demonize the script on instantiation and return the user to the shell. Leaves all file
            descriptors intact (see redirect below).
        redirect : string or None, default ''
            If set will redirect both stdout and stderr to this file if writable. Useful with the daemon parameter,
            and also useful for Altiris scripts. If None, redirects stdout and stderr to os.devnull.
        log_file : string, default ''
            Enables logging if set to a writable path.
        log_level : string, deault 'info'
            The default log level (hides lower levels from file). Valid options: critical, error, warning, info, debug.
        mail_smtp : string, default ''
            SMTP server to use. Uses sendmail if not set, unless sendmail isn't installed.
        mail_from : string, default ''
            Email address to use as the sender. This is required to send email.
        mail_to : string or list, default []
            Can be a single email address as a string or list, or multiple email addresses in a python list.
        """
        self._quiet = quiet if isinstance(quiet, bool) else None
        if daemon or redirect != '': self._daemon(daemon, redirect)
        if log_file: self._logging(log_file, log_level)
        if not mail_from: mail_from = socket.gethostname().replace('.', '@', 1)
        if isinstance(mail_from, str) and '@' in mail_from: self._mail_from = mail_from
        if isinstance(mail_to, tuple) or isinstance(mail_to, list):
            for to in mail_to:
                if '@' in to: self._mail_to.append(to)
        elif isinstance(mail_to, str) and '@' in mail_to: self._mail_to.append(mail_to)
        if isinstance(mail_smtp, str) and mail_smtp: self._mail_smtp = mail_smtp
        return None
    
    def _timer(self, log=False, echo=False):
        """
        Called by atexit.register() when the script exits (unless killed with signal 9). Generates a valediction to be
        logged or printed (in the case of console redirect) indicating when the script exited. Saves this in the class
        instance to keep the exit time consistent between logging and console redirected output.
        
        Parameters
        ----------
        log : boolean, default False
            If valediction should be logged.
        echo : boolean, default False
            If valediction should be sent to stdout.
        
        See also
        --------
        _logging() and _daemon() : The two methods which use _timer().
        """
        if not self.valediction:
            time_start = psutil.Process(os.getpid()).create_time # Time script started.
            length = time.time() - time_start # Number of seconds this script ran for.
            valediction = ' Script Ended After {0} (HMS) '.format(datetime.timedelta(seconds=int(length)))
            self.valediction = valediction.center(79, '*')
        if log: self(self.valediction, quiet=True).log('info').term()
        if echo: self(self.valediction).term()
        return None
    
    def _daemon(self, demonize, redirect):
        """
        Demonizes this process and/or redirects stdout and stderr to a file (the same file) if the path is writable.
        Called during instantiation if daemon or redirect are set in __init__(). If demonize is True and redirect is
        empty or not writable, stdout and stderr are set to null. All other open file descriptors are closed regardless
        of redirect so it's best to instantiate this class at the beginning of the script!
        
        Parameters
        ----------
        demonize : boolean
            If True the script will be demonized and all open file descriptors will be closed. stdin, stderr, and
            stdout will be set to os.devnull.
        redirect : string
            If set to a writable path (writable file or writable directory if file doesn't exist) the script's stdout
            and stderr will be redirected to this file. If demonize is True, this is done after demonization so both
            parameters may be used simultaneously.
        
        See also
        --------
        http://code.activestate.com/recipes/278731-creating-a-daemon-the-python-way/
        """
        # If redirect is not an empty string, then the user wanted to either redirect to a file or to null (None).
        # If None, leave it. If string, verify it is a file and is writable. If not, change to None.
        if redirect not in ('', None):
            if os.path.isdir(redirect):
                # Cannot redirect output to a directory.
                redirect = None
            elif os.path.isfile(redirect) and not os.access(redirect, os.W_OK):
                # File exists but no permission to write.
                redirect = None
            elif not os.path.exists(redirect) and not os.access(os.path.dirname(redirect), os.W_OK):
                # File does not exists but cannot write to the parent directory.
                redirect = None
            # If we get here, then desired file is writable!
            # redirect is either '' (no redirect), None (redirect to null), or valid file.
        if demonize:
            if os.fork() != 0: os._exit(0) # This is the parent (original process).
            os.setsid() # Become session leader.
            if os.fork() != 0: os._exit(0) # Fork a second child and exit the first.
        # Set console redirects.
        if redirect != '':
            if redirect == None: fd = os.open(os.devnull, os.O_RDWR)
            else: fd = os.open(redirect, os.O_RDWR|os.O_APPEND|os.O_CREAT, 0640)
            os.dup2(fd, 1) # stdout
            os.dup2(fd, 2) # stderr
            os.close(fd) # No need for temporary file descriptor anymore.
        self(self.greeting).term()
        atexit.register(self._timer, echo=True)
        return None
    
    def _convert(self, s):
        """
        Replaces valid [bracketed] tags to Bash escape codes for colors and text formatting. This method searches for
        "[key]" where key is a python dictionary key in the Message.special class member. If the key is in the dict the
        entire bracketed tag will be replaced by a Bash escape code using the value in the dict. For example, "This
        text is [red]red[/red] while [blue]this is blue[/all]." becomes "This text is \\033[31mred\\033[39m while
        \\033[34mthis is blue\\033[0m.".
        
        Parameters
        ----------
        s : string
            The text to be parsed.
        
        Returns
        -------
        string : Parsed text.
        """
        if s == None: return s
        for k, v in self.special.viewitems():
            s = s.replace('[{0}]'.format(k), "\033[{0}m".format(v))
            # Extra closing codes.
            if '/' in k or v < 30: continue # No double forward slashes. All colors are above 30.
            if 'bg' in k: s = s.replace('[/{0}]'.format(k), "\033[{0}m".format(self.special['/bg']))
            else: s = s.replace('[/{0}]'.format(k), "\033[{0}m".format(self.special['/fg']))
        # Merge consecutive codes.
        while True:
            s_subbed = re.sub(r"\033\[([\d;]+)m\033\[([\d;]+)m", r"\033[\1;\2m", s)
            if s_subbed == s: break
            s = s_subbed
        return s
    
    def _logging(self, log_file, log_level):
        """Sets up logging during class instantiation. See __init__.__doc__ for more information."""
        log_file = os.path.abspath(log_file)
        if os.path.exists(log_file) and os.access(log_file, os.W_OK):
            self._log_file = log_file
        elif os.access(os.path.dirname(log_file), os.W_OK):
            self._log_file = log_file
        else: return None
        log_level = log_level.lower()
        self._log_level = self.log_levels[log_level] if log_level in self.log_levels else self.log_levels['info']
        # Start logging.
        logging.basicConfig(
            filename=self._log_file,
            level=self._log_level,
            format='%(asctime)s %(levelname)-8s %(process)d %(message)s',
            filemode='a')
        logging.info(self.greeting) # Log start time.
        atexit.register(self._timer, log=True) # Log end time.
        return None
    
    def log(self, log_level='info'):
        """
        Logs the message to the log file. If no log file is set, nothing is logged and nothing happens (doesn't throw an
        exception).
        
        Parameters
        ----------
        log_level : string, default ''
            The log level to use. If left empty, uses 'info'.
            See __init__.__doc__ for more information.
        
        Returns
        -------
        self : Returns this class instance (so methods can be chained, e.g. message('Text').log().quit())
        """
        log_level = log_level.lower()
        if None in (self._s, self._log_file, self._log_level): return self
        if log_level in self.log_levels:
            level = self.log_levels[log_level]
        else:
            level = logging.Logger.getEffectiveLevel(logging.getLogger())
        logging.log(level, self._s)
        return self
    
    def mail(self, subject, body='', log_tail=0, attach=[], html=False):
        """
        Sends email through an SMTP server or through the local sendmail program. Optionally includes a tail of the log
        and file attachments.
        
        Parameters
        ----------
        subject : string
            The subject to use for the email being sent.
        body : string, default ''
            The optional body of the message.
        log_tail : integer, default 0
            If > 0 includes the last specified number of lines of the log file in the body of the email (inline).
        attach : list, default []
            Files to attach to the email being sent (absolute local path as a string for each list item).
        html : boolean, default False
            Send emails as HTML instead of plain text.
        
        Returns
        -------
        self : Returns this class instance (so methods can be chained, e.g. message('Text').log().quit())
        """
        if not self._mail_from or not self._mail_to:
            if self._log_file: logging.debug('Cannot send email: from or to addresses not set.')
            return self
        if log_tail and self._log_file and len(logging.getLogger().handlers) > 0:
            if body: body + "\r\n\r\n" + ('-' * 79) + "\r\n"
            f = open(self._log_file, 'r')
            body += collections.deque(f, log_tail)
            f.close()
        msg = email.MIMEMultipart.MIMEMultipart('alternative')
        msg['From'] = self._mail_from
        msg['To'] = ', '.join(self._mail_to)
        msg['Subject'] = subject
        msg.attach(email.MIMEText.MIMEText(body, 'html' if html else 'plain'))
        for path in attach:
            if not os.access(path, os.R_OK):
                if self._log_file: logging.debug('Cannot read '+path)
                continue
            ctype, encoding = mimetypes.guess_type(path) # Guess the content type based on the file's extension.
            if not ctype or encoding: ctype = 'application/octet-stream' # No guess could be made, might be encoded.
            types = {'text/':email.MIMEText.MIMEText, 'image/':email.MIMEImage.MIMEImage,
                'audio/':email.MIMEAudio.MIMEAudio}
            payload = None
            for t in types:
                if ctype.startswith(t): payload = types[t](file(path).read(), ctype.split('/', 1)[1])
            if not payload:
                payload = email.MIMEBase.MIMEBase(*ctype.split('/', 1))
                payload.set_payload(open(path).read())
                encoders.encode_base64(payload)
            payload.add_header('Content-Disposition', 'attachment', filename=os.path.basename(path))
            msg.attach(payload)
        if self._log_file: logging.debug('Sending email to {0}. Subject: {1}'.format(msg['To'], msg['Subject']))
        if self._mail_smtp:
            try:
                session = smtplib.SMTP(self._mail_smtp)
                session.sendmail(msg['From'], msg['To'], msg.as_string())
                session.quit()
            except (smtplib.socket.error, smtplib.SMTPSenderRefused) as err:
                if self._log_file: logging.error('Failed to send email: {0}'.format(err))
            else:
                if self._log_file: logging.debug('Successfully sent email.')
        elif os.path.exists('/usr/sbin/sendmail'):
            p = subprocess.Popen(['/usr/sbin/sendmail', '-t'], stdin=subprocess.PIPE)
            p.communicate(msg.as_string())
        else:
            if self._log_file: logging.error('Failed to send email: no SMTP host and no sendmail')
        return self
    
    def quit(self, code=1):
        """
        Terminates the script with the specified exit code. Supports custom exit messages if set in the class member
        "retcode". See the example below.

        Parameters
        ----------
        code : integer, default 1
            The exit code to use.
        """
        if code in self.retcodes:
            self('\n', stderr=True).term()
            self('QUITTING: ' + self.retcodes[code], stderr=True).log('error').term()
        sys.exit(code)
        return None
    
    def term(self):
        """
        Dummy method used to avoid printing class objects to the interactive terminal while debugging.
        """
        return None
    
    def __call__(self, s=None, stderr=False, quiet=False):
        """
        Prints messages to stdout or stderr. Converts [bracketed] tags to Bash escaped color codes using the
        Message._convert method. Saves the converted string to Message._s to be used by the Message.log() method. If
        the \\r character is found, this method will print and immediately flush.
        
        Parameters
        ----------
        s : string, default None
            The string to convert and print. If None, nothing is printed or converted.
        stderr : boolean, default False
            Print to stderr instead of stdout.
        quiet : boolean, default False
            Only convert, don't print.
        
        Returns
        -------
        self : Returns this class instance (so methods can be chained, e.g. message('Text').log().quit())
        """
        self._s = self._convert(s)
        if self._quiet or quiet or self._s == None: return self
        outdev = sys.stdout
        if stderr: outdev = sys.stderr
        if '\r' in self._s:
            outdev.write(self._s)
            outdev.flush()
            return self
        print >> outdev, self._s
        return self

