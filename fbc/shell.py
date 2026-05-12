import os
import shlex
import posixpath
import inspect
from .util import Shell, command, cast_value, require_attr
from .filebrowser import FileBrowser
from urllib.parse import urlsplit, quote, unquote, urlparse, urlunparse

__VERSION__ = "0.1.1"


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


class FileBrowserShell(Shell):

    def __init__(self, engine=None, prompt='fbc> '):
        Shell.__init__(self, engine, prompt)
        self.iniprompt = prompt
        self._reset()

    def _reset(self):
        self.verify_ssl = True
        self.cert = None
        self.token = None
        self.prompt = self.iniprompt
        self.scheme, self.username, self.host = '', '', ''

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

    @command(group='Remote')
    @require_attr('engine', 'You are not connected !!!')
    def cd(self, path="/"):
        """
        Change remote directory to 'path'
        """
        resolved = self._resolve_path(path)
        self.engine.list(resolved)
        self.cwd = resolved

    @command(group='Remote')
    @require_attr('engine', 'You are not connected !!!')
    def ls(self, path="."):
        """
        Display remote directory listing
        """
        resolved = self._resolve_path(path)
        data = self.engine.list(resolved)
        items = data.get("items", [])
        for item in items:
            name = item.get("name")
            if item.get("isDir"):
                print(f"[DIR]  {name}")
            else:
                size = item.get("size", 0)
                print(f"{size:>10}  {name}")

    @command(group='Remote', aliases=['upload',])
    @require_attr('engine', 'You are not connected !!!')
    def put(self, local_file, remote_path="."):
        """
        Upload file
        """
        resolved = self._resolve_path(remote_path)
        self.engine.upload(local_file, resolved)
        print("Upload OK")

    @command(group='Remote', aliases=['download',])
    @require_attr('engine', 'You are not connected !!!')
    def get(self, remote_file, local_file=None):
        """
        Download file
        """
        resolved = self._resolve_path(remote_file)
        if local_file is None:
            local_file = os.path.basename(resolved)
        self.engine.download(resolved, local_file)
        print("Download OK")

    @command(group='Remote', aliases=['del',])
    @require_attr('engine', 'You are not connected !!!')
    def rm(self, path):
        """
        Delete remote file
        """
        resolved = self._resolve_path(path)
        self.engine.delete(resolved)
        print("Deleted")

    @command(group='Remote')
    @require_attr('engine', 'You are not connected !!!')
    def mkdir(self, path):
        """
        Create remote directory
        """
        resolved = self._resolve_path(path)
        self.engine.mkdir(resolved)
        print("Directory created")
