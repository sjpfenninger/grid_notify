#!/usr/bin/env python

import os
import sys
import subprocess
import argparse
import time
import ConfigParser
import pushnotify  # version >= 0.5


def read_configuration():
    config = ConfigParser.RawConfigParser()
    config.read('cluster-notify.conf')
    api = config.get('api', 'type')
    api_key = config.get('api', 'key')
    return (api, api_key)


def parse_return(string):
    assert string[0:4] == 'your'  # Because we have no clue what's going on if we're not getting 'your'
    identifier = string.split()[2]  # This could still be in the form 123.1-10:1 if it's a job-array
    task_id = identifier.split('.')[0]  # Gives us the task_id whether identifier was 123 or 123.1-10:1
    return int(task_id)  # Implicitly ensure that we're returning an int, or an exception will be raised


def make_path_absolute(path):
    if os.path.isabs(path):
        return path
    else:
        exec_name = path.split(' ')[0]
        if subprocess.call(['which', exec_name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) == 0:
            # If the executable is in path (findable by 'which'), don't need to make path absolute
            return path
        else:
            return os.path.join(os.getcwd(), path)


def run_and_get_task(script, print_output=True):
    p = subprocess.Popen(script.split(' '), stdout=subprocess.PIPE)
    string = p.stdout.readlines()[0]  # If all went well we get a single line with the qsub result
    if print_output:
        print string
    task_id = parse_return(string)
    return task_id


def setup_notifier(api, api_key):
    push_client = pushnotify.get_client(api, application='ChemEng Cluster')
    push_client.add_key(api_key)
    return push_client


def notify(notifier, task_id):
    current_time = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
    notifier.notify(description='Task {} done @ {}.'.format(task_id, current_time), event='Tasks complete.')


def monitor(task_id, user=None):
    if user is None:
        command = ['qstat']
    else:
        command = ['qstat', '-u', user]
    while True:
        time.sleep(30)
        p = subprocess.Popen(command, stdout=subprocess.PIPE)
        tasks = [s for s in p.stdout if (str(task_id) in s)]
        if tasks:
            continue
        else:
            return True


def _force_fork():
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit(1)


def daemonify():
    # Source: http://motoma.io/daemonizing-a-python-script/
    _force_fork()
    #os.chdir("/")
    os.setsid()
    os.umask(0)
    _force_fork()


def postprocess(script):
    processing_script = os.path.join(os.path.dirname(script), 'process_' + os.path.basename(script))
    if os.path.exists(processing_script):
        subprocess.call(processing_script)
    else:
        print 'No post-processing script found: {}'.format(processing_script)


if __name__ == '__main__':
    _api, _api_key = read_configuration()
    parser = argparse.ArgumentParser(description=os.path.basename(__file__))
    parser.add_argument('script', metavar='script', type=str, help='Grid Engine submission script to monitor.')
    parser.add_argument('-p', '--process', dest='process', action='store_const', const=True, default=False, help='Do post-processing by calling process_{script}.')
    args = parser.parse_args()
    script_path = make_path_absolute(args.script)
    task_id = run_and_get_task(script_path)
    daemonify()  # Push the script into the background so control is returned to terminal
    notifier = setup_notifier(_api, _api_key)
    user = os.environ['LOGNAME']
    monitor(task_id, user)  # This will return only once the tasks are complete
    if args.process:
        postprocess(script_path)
        task_id = str(task_id) + ' & post-processing'
    notify(notifier, task_id)
    subprocess.call(["echo", "-e", "\a"])  # Terminal bell
