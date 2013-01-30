#!/usr/bin/env python -u
#
# Copyright (c) 2012, Robpol86
# This software is made available under the terms of the MIT License that can
# be found in the LICENSE.txt file.
#
"""
Creates a progress bar wih an optional ETA.

Progress provides the Progress class which handles creating a progress bar to display to the user. An ETA is also
created as well as percentages and counts, all of this optional.

For more information:
    * import robutils.Progress; help(robutils.Progress)
"""


__author__ = 'Robpol86 (http://robpol86.com)'
__copyright__ = 'Copyright 2012, Robpol86'
__license__ = 'MIT'


import time, datetime, itertools, struct, fcntl, termios, threading, re
import pandas # http://pandas.pydata.org/


class Progress:
    """
    Main class responsible for creating a progress bar and other data.
    
    Examples
    --------
    >>> message = Message()
    >>> progress = Progress(43)
    >>> while progress.total_percent < 80:
    ...     time.sleep(1)
    ...     progress.inc_pass() if random.randint(1, 5) < 5 else progress.inc_fail()
    >>> message(progress.summary())
      81% (35/43) [########################      ] eta 0:00:06 - 14% ( 5/35) failed
    >>> message(progress.summary(hide_failed=True))
      81% (35/43) [#######################################          ] eta 0:00:03 \\
    >>> message(progress.summary(max_width=70))
      81% (35/43) [################    ] eta 0:00:01 | 14% ( 5/35) failed
    >>> message(progress.summary(hide_failed=True, eta_countdown=False))
      81% (35/43) [#################################        ] eta 11:45:30 PM CST /
    >>> while progress.total_percent < 100: progress.inc_pass()
    >>> message(progress.summary())
     100% (43/43) [##############################] eta 0:00:00 - 11% ( 5/43) failed
    >>> 
    
    >>> message = Message()
    >>> progress = Progress(43)
    >>> progress.threaded_summary(message, hide_failed=True)
    >>> while progress.total_percent < 100:
    ...     time.sleep(1)
    ...     progress.inc_pass() if random.randint(1, 5) < 5 else progress.inc_fail()
    >>> print
     100% (43/43) [#################################################] eta 0:00:00 /
    """
    
    _spinner = itertools.cycle(['|','/','-','\\']) # Use print self.spinner.next()
    _history = pandas.DataFrame([{'seconds':0, 'percent':0}], index=[time.time()])
    _lock = threading.Lock()
    pass_count = 0
    fail_count = 0
    total_count = 0
    fail_percent = 0.0 # Percent failed out of all done items (not total items).
    total_percent = 0.0
    summary_finished = False # Set to true once self.summary() returns 100% (to avoid displaying 99% when done).
    
    def __init__(self, total_count):
        """
        Provide the expected total count during instantiation. Currently indefinite progress bars are not supported.
        
        Parameters
        ----------
        total_count : integer
        """
        self.total_count = total_count
        return None
    
    def _calculate_eta(self):
        """
        Calculates the ETA based entirely on data in the _history pandas.DataFrame object. ETA is calculated using an
        exponentially weighted moment function provided by pandas. As the total_percent approaches 100% this method
        will put more weight on the more recent data for its estimation.
        
        Returns
        -------
        None if len(_history) < 5
        float : Projected arrival date (Unix epoch)
        
        See also
        --------
        http://pandas.pydata.org/pandas-docs/stable/computation.html#exponentially-weighted-moment-functions
        """
        if len(self._history) < 5: return None # Wait until we have enough data to calculate an ETA.
        history_diff = self._history.diff()
        history_rate = history_diff.percent.div(history_diff.seconds)
        span = max(min(100 - float(self._history.tail(1).percent), 30), 1)
        (timestamp, rate) = pandas.ewma(history_rate, span=span).tail(1).to_dict().items()[0]
        return ((100 - float(self._history.tail(1).percent)) / rate) + timestamp
    
    def increment(self, fail=False):
        """
        Use inc_pass() or inc_fail() instead of calling this directly for more readable code.

        Increments the pass or fail counters until the sum of them equals the total_count. After incrementing the
        percentage members are updated and data is appended to the _history pandas.DataFrame object (used to calculate
        the ETA).
        
        Parameters
        ----------
        fail : boolean, default False
            Increments the pass_count counter by default. If true, increments the fail_count.
        """
        if self.total_percent >= 100: return None
        with self._lock:
            if fail: self.fail_count += 1
            else: self.pass_count += 1
            self.fail_percent = self.fail_count / float(self.pass_count + self.fail_count) * 100
            self.total_percent = (self.pass_count + self.fail_count) / float(self.total_count) * 100
            t = time.time()
            s = t - float(self._history.head(1).index)
            df = pandas.DataFrame([{'seconds':s, 'percent':self.total_percent}], index=[t])
            self._history = self._history.append(df)
        return None
    
    def inc_pass(self):
        """Calls increment(fail=False)."""
        return self.increment()
    
    def inc_fail(self):
        """Calls increment(fail=True)."""
        return self.increment(fail=True)
    
    def summary(self, hide_failed=False, max_width=99999, eta_countdown=True):
        """
        Builds the progress bar and other data to be displayed to the user. The summary is color-coded in a syntax
        compatible with robutils.Message.
        
        Parameters
        ----------
        hide_failed : boolean, default False
            If fail_count > 0, the summary will include the fail_count and fail_percent in red. Setting this to True
            will prevent this from being included in the summary.
        max_width : integer, default 99999
            The summary uses up the entire terminal's width by default. The summary's line length is the lesser of two
            values: terminal width or max_width. Setting max_width to less than the terminal width/columns gives the
            developer control over the summary line length.
        eta_countdown : boolean, default True
            By default the ETA is displayed as the number of hours:minutes:seconds remaining. If this is set to False,
            ETA will be displayed as the exact time (and date if > 1 day).

        Returns
        -------
        string : Summary of progress, including progress bar, percentages, counts, and ETA.
        
        See also
        --------
        robutils.Message : More information about the color syntax this method uses.
        """
        summary_finished = True if self.total_percent == 100 else False
        data = {
                'tp' : '{0:3d}%'.format(int(self.total_percent)), # Total percent.
                'fp' : '{0}%'.format(int(self.fail_percent)), # Fail percent.
                'tc' : str(self.total_count), # Total count.
                'eta' : self._calculate_eta(), # ETA float. Projected EPOCH time (not seconds remaining).
                'eta_str' : '-:--:--', # ETA string.
                'width' : min(struct.unpack('hh', fcntl.ioctl(0, termios.TIOCGWINSZ, '0000'))[1], max_width),
                'spinner' : self._spinner.next(),
                }
        data['dc'] = str(self.pass_count + self.fail_count).rjust(len(data['tc'])) # Done count.
        data['fc'] = str(self.fail_count).rjust(len(data['tc'])) # Fail count.
        if data['eta'] == None:
            pass
        elif eta_countdown:
            data['eta_str'] = str(datetime.timedelta(seconds=int(max(data['eta'] - time.time(), 0))))
        else:
            lt = time.localtime(data['eta'])
            if lt.tm_mday == time.localtime().tm_mday: fmt = '%I:%M:%S %p %Z'
            elif lt.tm_mday == time.localtime().tm_mday + 1: fmt = 'Tomorrow %I:%M:%S %p %Z'
            else: fmt = '%Y-%m-%d %I:%M:%S %p %Z'
            data['eta_str'] = time.strftime(fmt, lt)
        # 20% (18/87) [######                       ] eta 0:00:39 /  33% ( 6/18) failed
        summary = list(['', '', '', ' ']) # Summary in four parts (for resizable bar): total, bar, eta, failed.
        summary[0] = ' [hicyan]%(tp)s[/all] (%(dc)s/%(tc)s)'%data
        if data['eta'] != None and 0 < data['eta'] <= 10:
            summary[2] = ' eta [higreen]%(eta_str)s[/all] %(spinner)s'%data
        else:
            summary[2] = ' eta %(eta_str)s %(spinner)s'%data
        if self.fail_count and not hide_failed: summary[3] = ' [hired]%(fp)s (%(fc)s/%(dc)s) failed[/all] '%data
        bar_size = data['width'] - len(re.sub('\[[\w/]+\]', '', ''.join(summary))) - 3
        if bar_size >= 3:
            bar_fill = int(self.total_percent / 100.0 * bar_size)
            summary[1] = ' [hiblue][[yellow]{0}[hiblue]{1}][/all]'.format('#' * bar_fill, ' ' * (bar_size - bar_fill))
        if summary_finished: self.summary_finished = True
        return ''.join(summary)
    
    def threaded_summary(self, message, *args, **kwargs):
        """
        Calls summary() and passes all of this method's args (except the first one) to it. Runs summary() in a thread
        every 0.25 seconds until summary() indicates that it has reached 100%.
        
        Parameters
        ----------
        message : robutils.Message
            Class instance of robutils.Message.
        *args, **kwargs : Same arguments as summary().
        
        Returns
        -------
        threading.Thread : Threading instance, in case your application wants control of it.
        
        See also
        --------
        summary() : Method in this class.
        """
        class SummaryThread(threading.Thread):
            """Temporary threading class used for periodically printing the progress to stdout."""
            _interrupt = False # See robutils/__init__.py: signal_threads_shutdown_imminent
            parent = None # The Progress class instance object.
            message = None # The Message class instance object.
            def __init__(self, parent, message):
                super(SummaryThread, self).__init__()
                self.name = 'robutils.Progress.threaded_summary.SummaryThread'
                self.parent = parent
                self.message = message
                return None
            def run(self):
                while not self.parent.summary_finished:
                    if self._interrupt:
                        print
                        return None
                    self.message('\r' + self.parent.summary(*args, **kwargs)).term()
                    time.sleep(0.25)
                return None
        thread = SummaryThread(self, message)
        thread.daemon = True
        thread.start()
        return thread

