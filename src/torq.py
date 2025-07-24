#
# Copyright (C) 2024 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import os

from .command import ProfilerCommand
from .config import (
   add_config_parser,
   verify_config_args,
   create_config_command,
   PREDEFINED_PERFETTO_CONFIGS
)
from .open import (
   add_open_parser,
   OpenCommand,
   verify_open_args
)
from .device import AdbDevice
from .utils import set_default_subparser
from .validate_simpleperf import verify_simpleperf_args
from .validation_error import ValidationError
from .vm import add_vm_parser, create_vm_command

# Add default parser capability to argparse
argparse.ArgumentParser.set_default_subparser = set_default_subparser

DEFAULT_DUR_MS = 10000
MIN_DURATION_MS = 3000
DEFAULT_OUT_DIR = "."


def create_parser():
  parser = argparse.ArgumentParser(prog='torq command',
                                   description=('Torq CLI tool for performance'
                                                ' tests.'))
  # Global options
  # NOTE: All global options must have the 'nargs' option set to an int.
  parser.add_argument('--serial', nargs=1,
                      help=(('Specifies serial of the device that will be'
                             ' used.')))

  # Subparsers
  subparsers = parser.add_subparsers(dest='subcommands', help='Subcommands')

  # Profiler options
  profiler_parser = subparsers.add_parser('profiler', help=('Profiler subcommand'
                                                            ' used to trace and'
                                                            ' profile Android'))
  profiler_parser.add_argument('-e', '--event',
                      choices=['boot', 'user-switch', 'app-startup', 'custom'],
                      default='custom', help='The event to trace/profile.')
  profiler_parser.add_argument('-p', '--profiler', choices=['perfetto', 'simpleperf'],
                      default='perfetto', help='The performance data source.')
  profiler_parser.add_argument('-o', '--out-dir', default=DEFAULT_OUT_DIR,
                      help='The path to the output directory.')
  profiler_parser.add_argument('-d', '--dur-ms', type=int,
                      help=('The duration (ms) of the event. Determines when'
                            ' to stop collecting performance data.'))
  profiler_parser.add_argument('-a', '--app',
                      help='The package name of the app we want to start.')
  profiler_parser.add_argument('-r', '--runs', type=int, default=1,
                      help=('The number of times to run the event and'
                            ' capture the perf data.'))
  profiler_parser.add_argument('-s', '--simpleperf-event', action='append',
                      help=('Simpleperf supported events to be collected.'
                            ' e.g. cpu-cycles, instructions'))
  profiler_parser.add_argument('--perfetto-config', default='default',
                      help=('Predefined perfetto configs can be used:'
                            ' %s. A filepath with a custom config could'
                            ' also be provided.'
                            % (", ".join(PREDEFINED_PERFETTO_CONFIGS.keys()))))
  profiler_parser.add_argument('--between-dur-ms', type=int, default=DEFAULT_DUR_MS,
                      help='Time (ms) to wait before executing the next event.')
  profiler_parser.add_argument('--ui', action=argparse.BooleanOptionalAction,
                      help=('Specifies opening of UI visualization tool'
                            ' after profiling is complete.'))
  profiler_parser.add_argument('--excluded-ftrace-events', action='append',
                      help=('Excludes specified ftrace event from the perfetto'
                            ' config events.'))
  profiler_parser.add_argument('--included-ftrace-events', action='append',
                      help=('Includes specified ftrace event in the perfetto'
                            ' config events.'))
  profiler_parser.add_argument('--from-user', type=int,
                      help='The user id from which to start the user switch')
  profiler_parser.add_argument('--to-user', type=int,
                      help='The user id of user that system is switching to.')
  profiler_parser.add_argument('--symbols',
                      help='Specifies path to symbols library.')

  # Config options
  add_config_parser(subparsers)

  # Open options
  add_open_parser(subparsers)

  # Configure perfetto in virtualized Android
  add_vm_parser(subparsers)

  # Set 'profiler' as the default parser
  parser.set_default_subparser('profiler')

  return parser

def verify_profiler_args(args):
  if args.out_dir != DEFAULT_OUT_DIR and not os.path.isdir(args.out_dir):
    return None, ValidationError(
        ("Command is invalid because --out-dir is not a valid directory"
         " path: %s." % args.out_dir), None)

  if args.dur_ms is not None and args.dur_ms < MIN_DURATION_MS:
    return None, ValidationError(
        ("Command is invalid because --dur-ms cannot be set to a value smaller"
         " than %d." % MIN_DURATION_MS),
        ("Set --dur-ms %d to capture a trace for %d seconds."
         % (MIN_DURATION_MS, (MIN_DURATION_MS / 1000))))

  if args.from_user is not None and args.event != "user-switch":
    return None, ValidationError(
        ("Command is invalid because --from-user is passed, but --event is not"
         " set to user-switch."),
        ("Set --event user-switch --from-user %s to perform a user-switch from"
         " user %s." % (args.from_user, args.from_user)))

  if args.to_user is not None and args.event != "user-switch":
    return None, ValidationError((
        "Command is invalid because --to-user is passed, but --event is not set"
        " to user-switch."),
        ("Set --event user-switch --to-user %s to perform a user-switch to user"
         " %s." % (args.to_user, args.to_user)))

  if args.event == "user-switch" and args.to_user is None:
    return None, ValidationError(
        "Command is invalid because --to-user is not passed.",
        ("Set --event %s --to-user <user-id> to perform a %s."
         % (args.event, args.event)))

  # TODO(b/374313202): Support for simpleperf boot event will
  #                    be added in the future
  if args.event == "boot" and args.profiler == "simpleperf":
    return None, ValidationError(
        "Boot event is not yet implemented for simpleperf.",
        "Please try another event.")

  if args.app is not None and args.event != "app-startup":
    return None, ValidationError(
        ("Command is invalid because --app is passed and --event is not set"
         " to app-startup."),
        ("To profile an app startup run:"
         " torq --event app-startup --app <package-name>"))

  if args.event == "app-startup" and args.app is None:
    return None, ValidationError(
        "Command is invalid because --app is not passed.",
        ("Set --event %s --app <package> to perform an %s."
         % (args.event, args.event)))

  if args.runs < 1:
    return None, ValidationError(
        ("Command is invalid because --runs cannot be set to a value smaller"
         " than 1."), None)

  if args.runs > 1 and args.ui:
    return None, ValidationError(("Command is invalid because --ui cannot be"
                                  " passed if --runs is set to a value greater"
                                  " than 1."),
                                 ("Set torq -r %d --no-ui to perform %d runs."
                                  % (args.runs, args.runs)))

  if args.simpleperf_event is not None and args.profiler != "simpleperf":
    return None, ValidationError(
        ("Command is invalid because --simpleperf-event cannot be passed"
         " if --profiler is not set to simpleperf."),
        ("To capture the simpleperf event run:"
         " torq --profiler simpleperf --simpleperf-event %s"
         % " --simpleperf-event ".join(args.simpleperf_event)))

  if (args.simpleperf_event is not None and
      len(args.simpleperf_event) != len(set(args.simpleperf_event))):
    return None, ValidationError(
        ("Command is invalid because redundant calls to --simpleperf-event"
         " cannot be made."),
        ("Only set --simpleperf-event cpu-cycles once if you want"
         " to collect cpu-cycles."))

  if args.perfetto_config != "default":
    if args.profiler != "perfetto":
      return None, ValidationError(
          ("Command is invalid because --perfetto-config cannot be passed"
           " if --profiler is not set to perfetto."),
          ("Set --profiler perfetto to choose a perfetto-config"
           " to use."))

  if (args.perfetto_config not in PREDEFINED_PERFETTO_CONFIGS and
      not os.path.isfile(args.perfetto_config)):
    return None, ValidationError(
        ("Command is invalid because --perfetto-config is not a valid"
         " file path: %s" % args.perfetto_config),
        ("Predefined perfetto configs can be used:\n"
         "\t torq --perfetto-config %s\n"
         "\t A filepath with a config can also be used:\n"
         "\t torq --perfetto-config <config-filepath>"
         % ("\n\t torq --perfetto-config"
            " ".join(PREDEFINED_PERFETTO_CONFIGS.keys()))))

  if args.between_dur_ms < MIN_DURATION_MS:
    return None, ValidationError(
        ("Command is invalid because --between-dur-ms cannot be set to a"
         " smaller value than %d." % MIN_DURATION_MS),
        ("Set --between-dur-ms %d to wait %d seconds between"
         " each run." % (MIN_DURATION_MS, (MIN_DURATION_MS / 1000))))

  if args.between_dur_ms != DEFAULT_DUR_MS and args.runs == 1:
    return None, ValidationError(
        ("Command is invalid because --between-dur-ms cannot be passed"
         " if --runs is not a value greater than 1."),
        "Set --runs 2 to run 2 tests.")

  if args.excluded_ftrace_events is not None and args.profiler != "perfetto":
    return None, ValidationError(
        ("Command is invalid because --excluded-ftrace-events cannot be passed"
         " if --profiler is not set to perfetto."),
        ("Set --profiler perfetto to exclude an ftrace event"
         " from perfetto config."))

  if (args.excluded_ftrace_events is not None and
      len(args.excluded_ftrace_events) != len(set(
          args.excluded_ftrace_events))):
    return None, ValidationError(
        ("Command is invalid because duplicate ftrace events cannot be"
         " included in --excluded-ftrace-events."),
        ("--excluded-ftrace-events should only include one instance of an"
         " ftrace event."))

  if args.included_ftrace_events is not None and args.profiler != "perfetto":
    return None, ValidationError(
        ("Command is invalid because --included-ftrace-events cannot be passed"
         " if --profiler is not set to perfetto."),
        ("Set --profiler perfetto to include an ftrace event"
         " in perfetto config."))

  if (args.included_ftrace_events is not None and
      len(args.included_ftrace_events) != len(set(
          args.included_ftrace_events))):
    return None, ValidationError(
        ("Command is invalid because duplicate ftrace events cannot be"
         " included in --included-ftrace-events."),
        ("--included-ftrace-events should only include one instance of an"
         " ftrace event."))

  if (args.included_ftrace_events is not None and
      args.excluded_ftrace_events is not None):
    ftrace_event_intersection = sorted((set(args.excluded_ftrace_events) &
                                        set(args.included_ftrace_events)))
    if len(ftrace_event_intersection):
      return None, ValidationError(
          ("Command is invalid because ftrace event(s): %s cannot be both"
           " included and excluded." % ", ".join(ftrace_event_intersection)),
          ("\n\t ".join("Only set --excluded-ftrace-events %s if you want to"
                        " exclude %s from the config or"
                        " --included-ftrace-events %s if you want to include %s"
                        " in the config."
                        % (event, event, event, event)
                        for event in ftrace_event_intersection)))

  if args.profiler == "simpleperf" and args.simpleperf_event is None:
    args.simpleperf_event = ['cpu-cycles']

  if args.ui is None:
    args.ui = args.runs == 1

  if args.profiler == "simpleperf":
    args, error = verify_simpleperf_args(args)
    if error is not None:
      return None, error
  else:
    args.scripts_path = None

  return args, None

def verify_args(args):
  match args.subcommands:
    case "profiler":
      return verify_profiler_args(args)
    case "config":
      return verify_config_args(args)
    case "open":
      return verify_open_args(args)
    case "vm":
      return args, None
    case _:
      raise ValueError("Invalid command type used")

def create_profiler_command(args):
  return ProfilerCommand("profiler", args.event, args.profiler, args.out_dir,
                         args.dur_ms,
                         args.app, args.runs, args.simpleperf_event,
                         args.perfetto_config, args.between_dur_ms,
                         args.ui, args.excluded_ftrace_events,
                         args.included_ftrace_events, args.from_user,
                         args.to_user, args.scripts_path, args.symbols)

def get_command(args):
  match args.subcommands:
    case "profiler":
      return create_profiler_command(args)
    case "config":
      return create_config_command(args)
    case "open":
      return OpenCommand(args.file_path, args.use_trace_processor)
    case "vm":
      return create_vm_command(args)
    case _:
      raise ValueError("Invalid command type used")


def print_error(error):
  print(error.message)
  if error.suggestion is not None:
    print("Suggestion:\n\t", error.suggestion)


def run():
  parser = create_parser()
  args = parser.parse_args()
  args, error = verify_args(args)
  if error is not None:
    print_error(error)
    return
  command = get_command(args)
  serial = args.serial[0] if args.serial else None
  device = AdbDevice(serial)
  error = command.execute(device)
  if error is not None:
    print_error(error)
    return
