#!/usr/bin/env python

import os
import sys
import subprocess
import argparse
import time
import datetime
import ConfigParser
import pushnotify  # version >= 0.5


def read_configuration():
    """Read the configuration file and return a dict containing the settings"""
    script_path = os.path.dirname(os.path.realpath(__file__))
    config = ConfigParser.RawConfigParser()
    config.read(os.path.join(script_path, 'grid_notify.conf'))
    configdict = {}
    if config.has_option('general', 'title'):
        configdict['title'] = config.get('general', 'title')
    else:
        configdict['title'] = 'Grid engine notification'
    configdict['api'] = config.get('api', 'type')
    configdict['api_key'] = config.get('api', 'key')
    return configdict

def parse_return(string):
    """Parse the return string from qsub and get the task_id and name,
    returning them as a tuple"""
    assert string[0:4] == 'your'  # Because we have no clue what's going on if we're not getting 'your'
    identifier = string.split()[2]  # This could still be in the form 123.1-10:1 if it's a job-array
    task_id = identifier.split('.')[0]  # Gives us the task_id whether identifier was 123 or 123.1-10:1
    name = string.split()[3][2:-2]
    # Implicitly ensure that we're returning an int for task_id, or an exception will be raised
    return (int(task_id), name)


def make_path_absolute(path):
    """Helper function to rewrite a given executable path into an
    absolute path if necessary to find the executable"""
    if os.path.isabs(path):
        return path
    else:
        exec_name = path.split(' ')[0]
        if subprocess.call(['which', exec_name], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT) == 0:
            # If the executable is in path (findable by 'which'),
            # don't need to make path absolute
            return path
        else:
            return os.path.join(os.getcwd(), path)


def run_and_get_task(script, print_output=True):
    """Run a Grid Engine submission script via subprocess, and return
    a tuple of the resulting task_id and name

    Args:
        print_output : if True (default), print the output from the
                       submission script to standard out, otherwise,
                       be silent.

    """
    p = subprocess.Popen(script.split(' '), stdout=subprocess.PIPE)
    # If all went well we get a single line with the qsub result:
    string = p.stdout.readlines()[0]
    if print_output:
        print string
    task_id, name = parse_return(string)
    return (task_id, name)


def setup_notifier(api, api_key, title):
    """Set up a notifier with the given api, api_key and title; return
    a notifier instance"""
    push_client = pushnotify.get_client(api, application=title)
    push_client.add_key(api_key)
    return push_client


def _pretty_time_difference(start, end):
    """Return a string with nicely formatted time difference between the
    two UNIX time staps `start` and `end`"""
    elapsed = end - start
    secs = datetime.timedelta(seconds=elapsed)
    d = datetime.datetime(1, 1, 1) + secs
    elapsed_string = '{:02d}'.format(d.minute)
    elapsed_format = 'mins'
    if d.hour > 0:
        elapsed_string = '{:02d}:'.format(d.hour) + elapsed_string
        elapsed_format = 'hrs:mins'
    if d.day > 1:
        elapsed_string = '{:02d}:'.format(d.day - 1) + elapsed_string
        elapsed_format = 'days:hrs:mins'
    return elapsed_string + ' ' + elapsed_format


def notify(notifier, name, start=None):
    """ Send a notification via `notifier`

    Args:
        name : name of task, used in the event's name
        start : if given, assume it is a UNIX timestamp and also print
                time difference between start and current time

    """
    current_time = time.strftime("%Y-%m-%d %H:%M")
    descr = '{} done @ {}.'.format(name, current_time)
    if start:
        elapsed = _pretty_time_difference(start, time.time())
        descr += ' Duration: {}.'.format(elapsed)
    notifier.notify(description=descr,
                    event='{} completed.'.format(name))


def monitor(task_ids, user=None):
    """Check whether a given set of task_ids is completed
    every 30 seconds, and return True once it is

    Args:
        task_ids : an iterable of task_ids
        user : if given, only list the user's tasks when getting running
        tasks, which probably reduces the load on the machine..

    """
    if user is None:
        command = ['qstat']
    else:
        command = ['qstat', '-u', user]
    task_id = task_ids.pop(0)  # Take the first task
    while True:
        time.sleep(30)
        p = subprocess.Popen(command, stdout=subprocess.PIPE)
        tasks = [s for s in p.stdout if (str(task_id) in s)]
        if tasks:
            continue
        else:
            try:
                task_id = task_ids.pop(0)  # Take the next task
                continue
            # If no more tasks are around, we get an exception and so
            # return True
            except IndexError:
                return True


def _force_fork():
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit(1)


def daemonify():
    """Helper function to push the script into the background,
    returning control to the terminal"""
    # Source: http://motoma.io/daemonizing-a-python-script/
    _force_fork()
    #os.chdir("/")
    os.setsid()
    os.umask(0)
    _force_fork()


def postprocess(script):
    processing_script = os.path.join(os.path.dirname(script),
                                     'process_' + os.path.basename(script))
    if os.path.exists(processing_script):
        subprocess.call(processing_script)
    else:
        print 'No post-processing script found: {}'.format(processing_script)


if __name__ == '__main__':
    config = read_configuration()
    parser = argparse.ArgumentParser(description=os.path.basename(__file__))
    parser.add_argument('scripts', metavar='scripts', type=str,
                        help='Grid Engine submission script(s) to monitor.',
                        nargs='+')  # nargs='+' allows >=1 args
    parser.add_argument('-n', '--name', dest='name', type=str, default=None,
                        help=('Friendly name to use when sending notification '
                              '(if not given, uses the job\'s name).'))
    args = parser.parse_args()
    start_time = time.time()
    # Submit all tasks and get their task IDs
    running_tasks = []
    for script in args.scripts:
        script_path = make_path_absolute(script)
        task_id, name = run_and_get_task(script_path)
        running_tasks.append(task_id)
    # Push grid_notify into the background so control is returned to terminal
    daemonify()
    user = os.environ['LOGNAME']
    # monitor() will return only once the tasks are complete
    monitor(running_tasks, user)
    # Generate name of notification
    if args.name:
        name = args.name
    else:
        name = 'Tasks'
    # Send notification
    notifier = setup_notifier(api=config['api'], api_key=config['api_key'],
                              title=config['title'])
    notify(notifier, name=name, start=start_time)
    subprocess.call(["echo", "-e", "\a"])  # Terminal bell
