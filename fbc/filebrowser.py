import os
import requests
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning


class FileBrowserErrorNoPath(Exception):

    def __init__(self, path):
        super().__init__(f"Path {path} not found")
        self.path = path


class FileBrowserError(Exception):

    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class FileBrowser(requests.Session):

    def __init__(
        self,
        base_url,
        username=None,
        password=None,
        token=None,
        verify_ssl=True,
        cert=None,
        timeout=30,
        proxies=None,
        retries=3,
    ):
        super().__init__()
        if verify_ssl is False:
            disable_warnings(InsecureRequestWarning)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # SSL / Certificats
        self.verify = verify_ssl
        self.cert = cert

        # Proxies
        if proxies:
            self.proxies.update(proxies)

        # Retry automatique
        retry_strategy = Retry(
            total=retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)

        self.mount("http://", adapter)
        self.mount("https://", adapter)

        # Headers par défaut
        self.headers.update({
            "Accept": "application/json"
        })

        # Authentification
        if token:
            self.headers.update({
                "Authorization": f"Bearer {token}"
            })

        elif username and password:
            self.login(username, password)

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        try:
            response = super().request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            response = e.response
            try:
                data = response.json()
                message = (data.get("message") or data.get("error") or str(data))
            except Exception:
                message = response.text.strip()
            raise FileBrowserError(
                message,
                status_code=response.status_code,
                response=response
            )
        except requests.RequestException as e:
            raise FileBrowserError(
                str(e),
                status_code=response.status_code,
                response=response
            ) from e

    def login(self, username, password):
        url = f"{self.base_url}/api/login"

        response = self.post(
            url,
            json={
                "username": username,
                "password": password
            }
        )

        try:
            data = response.json()
            token = data.get("token")
        except requests.exceptions.JSONDecodeError:
            token = response.content.decode().strip()
            data = {"token": token}
        if token:
            self.headers.update({
                "X-Auth": token
            })
        return data

    def logout(self):
        try:
            url = f"{self.base_url}/api/logout"
            self.post(url)
        except FileBrowserError:
            pass
        self.headers.pop("X-Auth", None)
        self.headers.pop("Authorization", None)
        self.cookies.clear()
        return True

    def list(self, path="/"):
        encoded = quote(path)
        url = f"{self.base_url}/api/resources{encoded}"
        try:
            r = self.get(url)
        except FileBrowserError as e:
            if e.status_code == 404:
                raise FileBrowserErrorNoPath(path)
            raise e
        return r.json()

    def mkdir(self, path):
        encoded = quote(path)
        url = f"{self.base_url}/api/resources{encoded}/"
        self.post(url)
        return True

    def upload(self, local_file, remote_path):
        filename = os.path.basename(local_file)
        remote = remote_path.rstrip("/")
        encoded = quote(remote)
        url = f"{self.base_url}/api/resources{encoded}/{filename}"
        with open(local_file, "rb") as f:
            self.post(
                url,
                data=f,
                headers={
                    "Content-Type": "application/octet-stream"
                }
            )
        return True

    def download(self, remote_file, local_path):
        encoded = quote(remote_file)
        url = f"{self.base_url}/api/raw{encoded}"
        r = self.get(url, stream=True)
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return local_path

    def delete_request(self, url):
        return super().delete(url)

    def delete(self, remote_path):
        encoded = quote(remote_path)
        url = f"{self.base_url}/api/resources{encoded}"
        self.delete_request(url)
        return True

    def rename(self, old_path, new_name):
        encoded = quote(old_path)
        url = f"{self.base_url}/api/resources{encoded}"
        self.patch(
            url,
            json={
                "name": new_name
            }
        )
        return True

    def move(self, old_path, new_path):
        encoded = quote(old_path)
        url = f"{self.base_url}/api/resources{encoded}"
        self.patch(
            url,
            json={
                "destination": new_path
            }
        )
        return True
