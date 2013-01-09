# grid-notify -- a notification script for Oracle Grid Engine #

Grid-notify is a wrapper around the standard `qsub` script or your custom grid submission script. It will wait in the background until your job has completed, then send a push notification to your smartphone.

Use: Instead of running `qsub your_command`, you run `grid-notify.py "qsub your_command"`. If you have a custom submission script, run `grid-notify.py your-custom-script.sh`. The only requirement is that your custom script returns the standard `qsub` output: "your job [...] has been submitted".

## Installation and configuration ##

Requirements:

* Python 2.7 (for `argparse`).
* [pushnotify](http://pypi.python.org/pypi/pushnotify) >= 0.5.

A `grid-notify.conf` file must exist in the same directory as the script itself. Copy `grid-notify.conf.example` to `grid-notify.conf` and fill in your settings:

* `type`: Either `growl`, `nma`, or `pushover` (see [pushnotify documentation](http://packages.python.org/pushnotify/) for details).
* `key`: A valid API key for your chosen API.

## Credits ##

Author: [Stefan Pfenninger](http://pfenninger.org)

The code is released into the public domain as [CC0](https://creativecommons.org/publicdomain/zero/1.0/) and comes with no express or implied warranty.