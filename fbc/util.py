import os
import sys
import shlex
import posixpath
import inspect
from functools import wraps
import configparser
from configparser import _UNSET, NoOptionError, NoSectionError
import logging
import functools
import time
import argparse
import getpass

__VERSION__ = "0.0.1"


# =====================================
# manage Logging
# =====================================

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"


def add_logging_level(level_name, level_num):
    logging.addLevelName(level_num, level_name)

    def log_for_level(self, message, *args, **kwargs):
        if self.isEnabledFor(level_num):
            self._log(level_num, message, args, **kwargs)

    def log_to_root(message, *args, **kwargs):
        logging.log(level_num, message, *args, **kwargs)

    setattr(logging.Logger, level_name.lower(), log_for_level)
    setattr(logging, level_name.lower(), log_to_root)


add_logging_level("ANALYZE", 15)
add_logging_level("AUDIT", 60)
add_logging_level("METRIC", 16)
add_logging_level("SECURITY", 80)


def metric_root(arg=None, *args, **kwargs):
    if callable(arg):
        func = arg

        @functools.wraps(func)
        def wrapper(*f_args, **f_kwargs):
            start = time.time()
            result = func(*f_args, **f_kwargs)
            logging.log(logging.getLevelName('METRIC'), f"{func.__name__.replace('_', ' ')} completed in {time.time() - start:.2f} seconds")
            return result

        return wrapper
    else:
        message = arg
        return logging.log(logging.getLevelName('METRIC'), message, *args, **kwargs)


logging.metric = metric_root


class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "ANALYZE": "\033[30m",   # black
        "INFO": "\033[32m",      # vert
        "WARNING": "\033[33m",   # jaune
        "ERROR": "\033[31m",     # rouge
        "CRITICAL": "\033[35m",  # violet
        "AUDIT": "\033[0m",      # system
        "METRICS": "\033[34m",   # bleu
        "SECURITY": "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        # level color
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname:<8}{self.RESET}"
        wrapped_lines = []
        for line in record.getMessage().splitlines():
            record.msg = f"{self.COLORS[levelname]}{line}{self.RESET}"
            record.args = ()
            wrapped_lines.append(super().format(record))
        return "\n".join(wrapped_lines)


# =====================================
# manage Shell
# =====================================

try:
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.completion import ThreadedCompleter
    import shlex

    class ShellCompleter(Completer):

        def __init__(self, shell):
            self.shell = shell

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            try:
                args = shlex.split(text)
            except ValueError:
                return
            if not args:
                for cmd in self.shell.cmds.keys():
                    yield Completion(cmd, start_position=0)
                return
            if len(args) == 1 and not text.endswith(" "):
                current = args[0]

                for cmd in self.shell.cmds.keys():
                    if cmd.startswith(current):
                        yield Completion(cmd, start_position=-len(current))
                return
            cmd = args[0]
            if cmd in self.shell.cmds:
                fn = self.shell.cmds[cmd]
                prefix = args[-1] if len(args) > 1 else ""
                if fn._command_completer is not None:
                    yield from fn._command_completer.get_completions(self.shell, document, complete_event)
                return

    has_prompt_toolkit = True
except:
    has_prompt_toolkit = False

def t(s):
    frame = inspect.currentframe().f_back
    context = frame.f_globals | frame.f_locals
    for elt in dir(context['self']):
        if elt not in ('prompt', '_prompt'):
            context[elt] = getattr(context['self'], elt)
    return s.format(**context)


def require_attr(attr_name, msg='{attr_name} is None', **kws):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if getattr(self, attr_name) is None:
                raise ValueError(msg.format(attr_name=attr_name, **kws))
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def command(name=None, aliases=None, group='', completer=None):
    if aliases is None:
        aliases = []

    def decorator(func):
        func._is_command = True
        func._command_name = name or func.__name__
        func._command_aliases = aliases
        func._command_group = group
        func._command_completer = completer
        return func

    return decorator


class Shell:
    COLORS = {
        "cyan": "\033[36m" if has_prompt_toolkit is False else "<ansicyan>",
        "black": "\033[30m" if has_prompt_toolkit is False else "",
        "green": "\033[32m" if has_prompt_toolkit is False else "<ansigreen>",
        "yellow": "\033[33m" if has_prompt_toolkit is False else "<ansiyellow>",
        "red": "\033[31m" if has_prompt_toolkit is False else "<ansired>",
        "violet": "\033[35m" if has_prompt_toolkit is False else "",
        "reset": "\033[0m" if has_prompt_toolkit is False else "",
        "blue": "\033[34m" if has_prompt_toolkit is False else "<ansiblue>",
        "magenta": "\033[35m" if has_prompt_toolkit is False else "<ansimagenta>",
        "/cyan": "\033[0m" if has_prompt_toolkit is False else "</ansicyan>",
        "/black": "\033[0m" if has_prompt_toolkit is False else "",
        "/green": "\033[0m" if has_prompt_toolkit is False else "</ansigreen>",
        "/yellow": "\033[0m" if has_prompt_toolkit is False else "</ansiyellow>",
        "/red": "\033[0m" if has_prompt_toolkit is False else "</ansired>",
        "/violet": "\033[0m" if has_prompt_toolkit is False else "",
        "/reset": "\033[0m" if has_prompt_toolkit is False else "",
        "/blue": "\033[0m" if has_prompt_toolkit is False else "</ansiblue>",
        "/magenta": "\033[0m" if has_prompt_toolkit is False else "</ansimagenta>",
    }

    def __init__(self, engine=None, prompt="> "):
        self.engine = engine
        self.prompt = prompt
        self.cmds = {}
        self._historys = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if callable(attr) and getattr(attr, "_is_command", False) is True:
                name = attr._command_name
                self.cmds[name] = attr
                for alias in attr._command_aliases:
                    self.cmds[alias] = attr
        for color in self.COLORS:
            setattr(self, color, self.COLORS[color])

    @property
    def prompt(self):
        try:
            return t(self._prompt)
        except Exception:
            return '>'

    @prompt.setter
    def prompt(self, value):
        self._prompt = value

    @command(aliases=['bye', 'quit'])
    def exit(self):
        """
        Quit
        """
        pass

    def usage(self, cmd):
        fn = self.cmds[cmd]
        sig = inspect.signature(fn)
        args = [arg for arg, param in sig.parameters.items() if param.default is inspect._empty]
        args_opt = [arg for arg, param in sig.parameters.items() if param.default is not inspect._empty]
        usage = cmd + " " + ''.join(f'<{x}>' for x in args) + " " + ''.join(f'[{x}]' for x in args_opt)
        return f"{usage.strip():<40} {fn.__doc__.strip()}"

    @command(aliases=['?',])
    def help(self):
        """
        Display this help text
        """
        print("Available commands")
        groups = list(set([fn._command_group for fn in [self.cmds[cmd] for cmd in self.cmds.keys()]]))
        for group in sorted(groups):
            if len(group) > 0:
                print(f"\n{group}:")
            for cmd in [cmd for cmd in sorted(self.cmds.keys()) if self.cmds[cmd]._command_group == group]:
                print(self.usage(cmd))

    @command()
    def version(self):
        """
        Show FileBrowserClient version
        """
        try:
            print(self.__module__.__VERSION__)
        except Exception:
            print(__VERSION__)

    @command()
    def history(self):
        """
        Show history command
        """
        for history in self._historys:
            print(history)

    def run(self):
        if has_prompt_toolkit is True:
            completer = ThreadedCompleter(ShellCompleter(self))
        while True:
            try:
                if has_prompt_toolkit is False:
                    cmdline = input(self.prompt).strip()
                else:
                    cmdline = prompt(HTML(self.prompt), completer=completer).strip()                
                self._historys.append(cmdline)
                if not cmdline:
                    continue
                args = shlex.split(cmdline)
                cmd = args[0]
                if cmd in [cmd for cmd in self.cmds if self.cmds[cmd] == self.exit]:
                    break
                if cmd in self.cmds.keys():
                    self.cmds[cmd](*args[1:])
                else:
                    print("Unknown command", file=sys.stderr)
                    self.help()
            except TypeError as e:
                if cmd in self.cmds.keys():
                    print("Error synthax", file=sys.stderr)
                    print(self.usage(cmd), file=sys.stderr)
                else:
                    raise e
            except KeyboardInterrupt:
                print()
            except Exception as e:
                print(e, file=sys.stderr)

    def cmd(self, cmdline=''):
        self._historys.append(cmdline)
        args = shlex.split(cmdline)
        cmd = args[0]
        if cmd in [cmd for cmd in self.cmds if self.cmds[cmd] == self.exit]:
            return True
        if cmd in self.cmds.keys():
            self.cmds[cmd](*args[1:])
            return True
        else:
            raise ValueError("Unknown command")


# =====================================
# manage ConfigParser
# =====================================

class GenericModel():

    def __init__(self, **kw):
        for key in kw:
            self.__setattr__(key, kw[key])


def cast_value(v):
    if v.lower() == "none":
        return None
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        if "." in v:
            return float(v)
        return int(v)
    except Exception:
        try:
            return json.loads(v)
        except Exception:
            return v


class SectionProxyHeritage:

    def __init__(self, section, inherited='from'):
        self._section = section
        self._inherited = inherited

    def __getattr__(self, name):
        return getattr(self._section, name)

    def items(self):
        items = set(self._section.items())
        keys = [k for k, v in items]
        if self._inherited in keys:
            for k, v in self.parser[self.get(self._inherited)].items():
                if k not in keys:
                    items.add((k, v))
                    keys.append(k)
        return items


class ConfigParser(configparser.ConfigParser):

    def __init__(self, inherited="from", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._inherited = inherited
        self._filename = None
        self._filename_encoding = None

    def get(self, section, option, *, raw=False, vars=None, fallback=_UNSET):
        try:
            if not self.has_section(section):
                raise NoSectionError(section)
            if option in self._sections[section]:
                return super().get(section, option, raw=raw, vars=vars, fallback=_UNSET)
            raise NoOptionError(option, section)
        except NoOptionError as err:
            if self.has_option(section, self._inherited) is True and self.has_section(self.get(section, self._inherited)) is True:
                return self.get(self.get(section, self._inherited), option, raw=raw, vars=vars, fallback=fallback)
            else:
                if option in [k for k in self._proxies[self.default_section].keys()]:
                    return super().get(section, option, raw=raw, vars=vars, fallback=_UNSET)
                if fallback != _UNSET:
                    return fallback
            raise err

    def __getitem__(self, key):
        return SectionProxyHeritage(super().__getitem__(key))

    def read(self, filenames, encoding=None):
        if isinstance(filenames, (str, bytes, os.PathLike)):
            self._filename = filenames
            self._filename_encoding = encoding
        configparser.ConfigParser.read(self, filenames, encoding)

    def write(self, *args, **kws):
        if len(args) == 0 and len(kws) == 0:
            if self._filename is None:
                raise Exception("no read from file")
            with open(self._filename, "w", encoding=self._filename_encoding) as fh:
                self.write(fh)
        else:
            configparser.ConfigParser.write(self, *args, **kws)

    def options(self, section):
        inherited = []
        if self.has_option(section, self._inherited) is True and self.has_section(self.get(section, self._inherited)) is True:
            inherited = self.options(self.get(section, self._inherited))
        local = super().options(section)
        return list(dict.fromkeys(local + inherited))

    def items(self, section=_UNSET, raw=False, vars=None):
        inherited = []
        if self.has_option(section, self._inherited) is True and self.has_section(self.get(section, self._inherited)) is True:
            inherited = self.items(self.get(section, self._inherited), raw, vars)
        local = super().items(section, raw, vars)
        seen = set()
        result = []
        for item in local + inherited:
            key = item[0]
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

# =====================================
# manage Command
# =====================================


def _prompt_field(label, default):
    if default:
        prompt = f"{label} [{default}]: "
    else:
        prompt = f"{label}: "
    if default == "******":
        secret = True
    else:
        secret = False
    while True:
        if secret:
            value = getpass.getpass(prompt)
        else:
            value = input(prompt).strip()

        if value:
            return value
        if default is not None:
            return default
        print("⚠  This parameter is required")


class Subcommand:

    def __init__(self, command, shows=True, show=True, new=True, setter=True, delete=True, struct=None, not_save_default_value=False):
        self.command = command
        self.cmd_shows = shows
        self.cmd_show = show
        self.cmd_new = new
        self.cmd_set = setter
        self.cmd_del = delete
        self.struct = struct
        self.not_save_default_value = not_save_default_value

    def register(self, subparsers):
        if self.cmd_shows:
            subparsers.add_parser(f"{self.command}s", help=f"List of {self.command}")
        if self.cmd_show or self.cmd_new or self.cmd_set or self.cmd_del:
            self.cmd_parser = subparsers.add_parser(f"{self.command}", help=f"Manage {self.command}")
            account_sub = self.cmd_parser.add_subparsers(dest="action")
            if self.cmd_new:
                account_sub.add_parser("new", help=f"Create new {self.command}")
            if self.cmd_show:
                show_parser = account_sub.add_parser("show", help=f"Show configuration of {self.command}")
                show_parser.add_argument("name", help=f"Name of {self.command}")
            if self.cmd_set:
                set_parser = account_sub.add_parser("set", help=f"Change configuration {self.command}")
                set_parser.add_argument("name", help=f"Name of {self.command}")
                set_parser.add_argument("field", help="Paramater")
                set_parser.add_argument("value", help="New value")
            if self.cmd_del:
                del_parser = account_sub.add_parser("del", help=f"Delete {self.command}")
                del_parser.add_argument("name", help=f"Name of {self.command}")

    def act_shows(self, config, args):
        for category in [s for s in config.sections() if s.startswith(f"{self.command}.")]:
            print(f"> {category[len(self.command)+1:]}")
        return 0

    def act_show(self, config, args):
        if not config.has_section(f"{self.command}.{args.name}"):
            print(f"{self.command} category « {args.name} » doesn't exist")
            return 1
        ln = max([len(key) for key in config[f"{self.command}.{args.name}"].keys()])
        for key in [key for key in config.options(f"{self.command}.{args.name}") if key != 'from']:
            val = config.get(f"{self.command}.{args.name}", key)
            print(f"{key:{ln+1}s}: {val}")
        return 0

    def act_del(self, config, args):
        if not config.has_section(f"{self.command}.{args.name}"):
            print(f"{self.command} category « {args.name} » doesn't exist")
            return 1
        config.remove_section(f"{self.command}.{args.name}")
        config.write()
        return 0

    def act_set(self, config, args):
        name = args.name
        field = args.field
        value = args.value
        if not config.has_section(f"{self.command}.{name}"):
            print(f"{self.command} category « {name} » doesn't exist")
            return 1
        if field not in config.options(f"{self.command}.{name}"):
            valid = ", ".join(config.options(f"{self.command}.{name}"))
            print(f"Parameter « {field} » doesn't exist. Parameter checked : {valid}")
            return 1

        struct = {}
        if isinstance(self.struct, str):
            if config.has_section(self.struct):
                struct = {key: value for key, value in config.items(self.struct) if key != 'from'}
        value_ini = struct.get(field, '')
        config.remove_option(f"{self.command}.{name}", field)
        if self.not_save_default_value is False or value_ini != value:
            print("change value", self.not_save_default_value, value_ini, value)
            config.set(f"{self.command}.{name}", field, value)
        config.write()
        return 0

    def act_new(self, config, args):
        name = input(f"Name of {self.command}: ").strip()
        if not name:
            print("Name is null, stop")
            return 1

        if config.has_section(f"{self.command}.{name}"):
            print(f"Category « {account_name} » exist already")
            if self.cmd_set:
                print("Use `{self.command} set {name} <field> <value>` for change.")
            return 1

        config.add_section(f"{self.command}.{name}")
        if isinstance(self.struct, list):
            struct = [(st, '') for st in struct]
        elif isinstance(self.struct, str):
            if config.has_section(self.struct):
                struct = [(key, value) for key, value in config.items(self.struct) if key != 'from']
                config.set(f"{self.command}.{name}", "from", self.struct)
            else:
                raise Exception(f"{self.struct} doesn't exist")
        else:
            raise Exception("no structure")
        for key, value_ini in struct:
            value = _prompt_field(key, value_ini)
            if len(value) == 0 and value_ini == "None":
                value = "None"
            if self.not_save_default_value is False or value_ini != value:
                config.set(f"{self.command}.{name}", key, value)
        config.write()
        return 0

    def dispatch(self, args, config):
        command = getattr(args, "command", None)
        if command == f"{self.command}s":
            return self.act_shows(config, args)

        if command == f"{self.command}":
            action = getattr(args, "action", None)
            if action is None:
                self.cmd_parser.print_help()
                return 1
            if action == "new":
                return self.act_new(config, args)
            if action == "show":
                return self.act_show(config, args)
            if action == "set":
                return self.act_set(config, args)
            if action == "del":
                return self.act_del(config, args)
        return None
