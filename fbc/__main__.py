import argparse
import os
import sys
import logging
from util import ConfigParser, cast_value, LOG_FORMAT, Subcommand, GenericModel
from filebrowser import FileBrowser
from shell import FileBrowserShell, build_url

DEFAULT_CONFIG_PATH = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), ".fbc", "config.ini")
DEFAULT_CONFIG = {
    "default.server": {
        "base_url": "",
        "username": "None",
        "password": "******",
        "token": "None",
        "ssl": "false",
        "prompt": "fb> ",
        "cert": "None"
    },
    "default.global": {
        "not_save_default_value": "true",
        "prompt": "fb> "
    }
}


def check_config(config):
    for key in DEFAULT_CONFIG:
        if not config.has_section(key):
            config.add_section(key)
        for subkey in DEFAULT_CONFIG[key]:
            if config.get(key, subkey, fallback=None) is None:
                config.set(key, subkey, DEFAULT_CONFIG[key][subkey])
    config.write()


def main():
    try:
        parser = argparse.ArgumentParser(description="Files Browser Console", exit_on_error=False)
        parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="configuration file")
        parser.add_argument("--log_level", choices=[logging.getLevelName(level) for level in sorted(set(logging._nameToLevel.values()))], default="INFO", help="log level")
        subparsers = parser.add_subparsers(dest="command")
        defaults = Subcommand('default', new=False, delete=False)
        defaults.register(subparsers)
        servers = Subcommand('server', struct='default.server')
        servers.register(subparsers)
        args = parser.parse_args()
    except argparse.ArgumentError as e:  # manage url in argparse without action
        if not str(e).startswith("argument command"):
            print(e)
            sys.exit(2)
        try:
            argvs = sys.argv[1:]
            args = GenericModel(action=None, config=DEFAULT_CONFIG_PATH, log_level='INFO', url='', command=None)
            if '--config' in argvs:
                args.config = argvs[argvs.index('--config')+1]
                del argvs[argvs.index('--config')+1]
                argvs.remove('--config')
            if '--log_level' in argvs:
                args.log_level = argvs[argvs.index('--log_level')+1]
                del argvs[argvs.index('--log_level')+1]
                argvs.remove('--log_level')
            if args.log_level not in [logging.getLevelName(level) for level in sorted(set(logging._nameToLevel.values()))]:
                raise Exception('error level log')
            if len(argvs) > 1:
                raise Exception()
            args.url = argvs[0]
        except Exception as e:
            print(e)
            parser.print_help()
            sys.exit(2)
    os.makedirs(os.path.dirname(args.config), exist_ok=True)
    path_log = os.path.join(os.path.dirname(args.config), 'fbc.log')
    root = logging.getLogger()
    root.setLevel(getattr(logging, args.log_level))
    handler = logging.FileHandler(path_log)
    handler.setLevel(args.log_level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, "%Y-%m-%d %H:%M:%S"))
    root.addHandler(handler)
    config = ConfigParser()
    config.read(args.config, encoding="utf-8")
    check_config(config)
    if args.command is None:
        shell = FileBrowserShell()
        if 'url' in dir(args):
            url = args.url
            try:
                if config.has_section(f"server.{url}"):
                    shell.cmd(f"set verify_ssl {config.get('server.' + url, 'ssl')}")
                    shell.cmd(f"set cert {config.get('server.'+url, 'cert')}")
                    shell.cmd(f"set token {config.get('server.'+url, 'token')}")
                    shell.cmd(f"set prompt \"{config.get('server.'+url, 'prompt')}\"")
                    shell.cmd(f"connect {build_url(config.get('server.'+url, 'base_url'), config.get('server.'+url, 'username'), config.get('server.'+url, 'password'))}")
                else:
                    shell.cmd(f"connect {url}")
            except Exception as e:
                print(e)
                sys.exit(2)
        shell.run()
    else:
        defaults.not_save_default_value = cast_value(config.get('default.global', 'not_save_default_value'))
        defaults.dispatch(args, config)
        servers.not_save_default_value = cast_value(config.get('default.global', 'not_save_default_value'))
        servers.dispatch(args, config)


if __name__ == "__main__":
    main()
