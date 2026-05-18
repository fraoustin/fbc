import os
import shlex
import posixpath
import inspect
from pathlib import Path
from .util import Shell, command, cast_value, require_attr
from .filebrowser import FileBrowser
from urllib.parse import urlsplit, quote, unquote, urlparse, urlunparse
import readline
import subprocess

__VERSION__ = "0.3.1"


def build_url(url, username, password):
    parsed = urlparse(url)

    auth = username
    if password != '':
        auth += f':{password}'

    netloc = f'{auth}@{parsed.netloc}'

    return urlunparse((
        parsed.scheme,
        netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))


def parse_url(url):
    scheme, rest = url.split("://", 1)
    if "@" in rest:  # manage encoded password
        auth, host = rest.rsplit("@", 1)
        if ":" in auth:
            username, password = auth.split(":", 1)
            password = quote(password, safe="")
            rest = f"{username}:{password}@{host}"
    parsed = urlsplit(f"{scheme}://{rest}")
    target = parsed.hostname or ""
    if parsed.port:
        target += f":{parsed.port}"
    if parsed.path:
        target += parsed.path
    if parsed.query:
        target += f"?{parsed.query}"
    if parsed.fragment:
        target += f"#{parsed.fragment}"
    return parsed.scheme + "://", parsed.username or None, unquote(parsed.password) if parsed.password else None, target


try:
    from prompt_toolkit.completion import Completion

    def pathlocal_completer(shell, prefix, only_dirs=False):
        if prefix.startswith("/"):
            full_prefix = prefix
        else:
            full_prefix = os.path.join(shell.lcwd, prefix)
        base = os.path.dirname(full_prefix)
        typed = os.path.basename(full_prefix)

        try:
            entries = os.listdir(base)
        except (FileNotFoundError, PermissionError):
            return

        for name in entries:
            full_path = os.path.join(base, name)

            if not name.startswith(typed):
                continue

            if only_dirs:
                if not os.path.isdir(full_path):
                    continue

            suffix = "/" if os.path.isdir(full_path) else ""

            yield Completion(
                full_path + suffix,
                start_position=-len(prefix),
                display=name + suffix
            )

    def pathlocaldir_completer(shell, prefix):
        return pathlocal_completer(shell, prefix, only_dirs=True)

    def pathremote_completer(shell, prefix, only_dirs=False):
        if prefix.startswith("/"):
            full_prefix = prefix
        else:
            full_prefix = os.path.join(shell.cwd, prefix)
        base = os.path.dirname(full_prefix)
        typed = os.path.basename(full_prefix)

        try:
            entries = shell.engine.list(base).get("items", [])
        except Exception:
            return
        for item in entries:
            name = item.get("name")
            if not name.startswith(typed):
                continue
            if only_dirs:
                if not item.get("isDir"):
                    continue
            suffix = "/" if item.get("isDir") else ""
            yield Completion(
                name + suffix,
                start_position=-len(prefix),
                display=name + suffix
            )

    def pathremotedir_completer(shell, prefix):
        return pathremote_completer(shell, prefix, only_dirs=True)

except Exception:

    def pathremotedir_completer(shell, prefix):
        pass

    def pathremote_completer(shell, prefix, only_dirs=False):
        pass

    def pathlocaldir_completer(shell, prefix):
        pass

    def pathlocal_completer(shell, prefix, only_dirs=False):
        pass


class FileBrowserShell(Shell):

    def __init__(self, engine=None, prompt='fbc> '):
        Shell.__init__(self, engine, prompt)
        self.iniprompt = prompt
        self._reset()
        self.lcwd = os.getcwd()

    def _resolve_path(self, path, cwd):
        if not path:
            return cwd
        # absolu
        if path.startswith("/"):
            resolved = path
        # relatif
        else:
            resolved = posixpath.join(cwd, path)
        resolved = posixpath.normpath(resolved)
        if not resolved.startswith("/"):
            resolved = "/" + resolved
        return resolved

    def _reset(self):
        self.verify_ssl = True
        self.cert = None
        self.token = None
        self.prompt = self.iniprompt
        self.scheme, self.username, self.host = '', '', ''
        self.cwd = '/'

    @command()
    def set(self, attr, value=''):
        """
        config prompt, cert, token and verify_ssl
        """
        if attr not in ('cert', 'token', 'prompt', 'verify_ssl'):
            raise ValueError("attr not in this list: cert, token, prompt or verify_ssl")
        if attr == 'verify_ssl' and cast_value(value) not in (True, False):
            value = "false"
        setattr(self, attr, cast_value(value))

    @command()
    def env(self):
        """
        display parameter shell
        """
        env = {key: getattr(self, key) for key in ['cert', 'token', 'prompt', 'verify_ssl']}
        ln = max([len(key) for key in env])
        for key in env:
            print(f"{key:{ln+1}s}: {env[key]}")

    @command(aliases=['connect',], group='Remote')
    def login(self, url):
        """
        Connect remote
        """
        try:
            scheme, username, password, host = parse_url(url)
            fb = FileBrowser(
                base_url=scheme + host,
                username=username,
                password=password,
                verify_ssl=self.verify_ssl,
                token=self.token,
                cert=self.cert,
                timeout=10,
            )
            self.engine = fb
            self.scheme, self.username, self.host = scheme, username, host
        except Exception as e:
            self._reset()
            raise e

    @command(group='Remote')
    @require_attr('engine', 'You are not connected !!!')
    def logout(self):
        """
        Disconnect remote
        """
        self.engine.logout()
        print(f"Disconnect {self.engine.base_url}")
        self.engine = None
        self.reset()

    @command(group='Remote')
    @require_attr('engine', 'You are not connected !!!')
    def pwd(self):
        """
        Display remote working directory
        """
        print(f"Remote working directory: {self.cwd}")

    @command(group='Remote', completer=pathremotedir_completer)
    @require_attr('engine', 'You are not connected !!!')
    def cd(self, path="/"):
        """
        Change remote directory to 'path'
        """
        resolved = self._resolve_path(path, self.cwd)
        self.engine.list(resolved)
        self.cwd = resolved

    @command(group='Remote', completer=pathremotedir_completer)
    @require_attr('engine', 'You are not connected !!!')
    def ls(self, path="."):
        """
        Display remote directory listing
        """
        resolved = self._resolve_path(path, self.cwd)
        data = self.engine.list(resolved)
        items = data.get("items", [])
        for item in items:
            name = item.get("name")
            if item.get("isDir"):
                print(f"[DIR]  {name}")
            else:
                size = item.get("size", 0)
                print(f"{size:>10}  {name}")

    @command(group='Remote', aliases=['upload',], completer=pathlocal_completer)
    @require_attr('engine', 'You are not connected !!!')
    def put(self, local_file, remote_path="."):
        """
        Upload file
        """
        resolved = self._resolve_path(remote_path, self.cwd)
        self.engine.upload(self._resolve_path(local_file, self.lcwd), resolved)
        print("Upload OK")

    @command(group='Remote', aliases=['download',], completer=pathremote_completer)
    @require_attr('engine', 'You are not connected !!!')
    def get(self, remote_file, local_file=None):
        """
        Download file
        """
        resolved = self._resolve_path(remote_file, self.cwd)
        if local_file is None:
            local_file = os.path.basename(resolved)
        self.engine.download(resolved, self._resolve_path(local_file, self.lcwd))
        print("Download OK")

    @command(group='Remote', aliases=['del',], completer=pathremote_completer)
    @require_attr('engine', 'You are not connected !!!')
    def rm(self, path):
        """
        Delete remote file
        """
        resolved = self._resolve_path(path, self.cwd)
        self.engine.delete(resolved)
        print("Deleted")

    @command(group='Remote')
    @require_attr('engine', 'You are not connected !!!')
    def mkdir(self, path):
        """
        Create remote directory
        """
        resolved = self._resolve_path(path, self.cwd)
        self.engine.mkdir(resolved)
        print("Directory created")

    @command(group='Local')
    def lpwd(self):
        """
        Display local working directory
        """
        print(f"Local working directory: {self.lcwd}")

    @command(group='Local', completer=pathlocaldir_completer)
    def lcd(self, path="/"):
        """
        Change local directory to 'path'
        """
        resolved = self._resolve_path(path, self.lcwd)
        if Path(resolved).exists() and Path(resolved).is_dir():
            self.lcwd = resolved
            return
        raise ValueError(f"{path} doesn't exist")

    @command(group='Local', completer=pathlocaldir_completer)
    def lls(self, path="."):
        """
        Display local directory listing
        """
        resolved = self._resolve_path(path, self.lcwd)
        for path in [path for path in Path(resolved).iterdir() if path.is_dir()]:
            print(f"[DIR]  {path.name}")
        for path in [path for path in Path(resolved).iterdir() if path.is_file()]:
            size = path.stat().st_size
            print(f"{size:>10}  {path.name}")

    @command(group='Local', aliases=['!',])
    def lcmd(self, *args):
        """
        Execute 'command' in local shell
        """
        result = subprocess.run(args, capture_output=True, text=True)
        for ret in [result.stdout, result.stderr]:
            if len(ret) > 0:
                print(ret)
