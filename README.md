# File Browser Client

fbc is a client of [File Browser](https://filebrowser.org/index.html)

[File Browser](https://filebrowser.org/index.html) is an open source web-based file managing.
It's like your personal cloud drive 


## install

install by [pypi](https://pypi.org/project/nocp/)

> pip install fbc

## usage

> fbc --help

add shorcut for connection

> fbc server new

view or change parameter

> fbc defaults
> fbc default show global
> fbc default set global prompt ">>>"

add or change connection

> fbc servers
> fbc server show <name_connection>
> fbc server set <name_connection> ssl true

connection

> fbc http://<username>@<password>:<domain of filebrowser>.com
> fbc <name_connection>


You can change your prompt with dynamic value.

> fbc <name_connection>
> fbc> set prompt "{red}{username}{reset}@{blue}{host}{reset}:{green}{cwd}{reset} "
> user@tutu.fr:/

You can use keyword:

- colors: green, red, blue, violet, magenta, cyan, yellow, black, reset
- cwd current path remote
- connect information: username, host, scheme

List of action in shell

> help

```
Available commands
?                                        Display this help text
bye                                      Quit
env                                      display parameter shell
exit                                     Quit
help                                     Display this help text
history                                  Show history command
quit                                     Quit
set <attr> [value]                       config prompt, cert, token and verify_ssl
version                                  Show FileBrowserClient version

Local:
! <args>                                 Execute 'command' in local shell
lcd  [path]                              Change local directory to 'path'
lcmd <args>                              Execute 'command' in local shell
lls  [path]                              Display local directory listing
lpwd                                     Display local working directory

Remote:
cd  [path]                               Change remote directory to 'path'
connect <url>                            Connect remote
del <path>                               Delete remote file
download <remote_file> [local_file]      Download file
get <remote_file> [local_file]           Download file
login <url>                              Connect remote
logout                                   Disconnect remote
ls  [path]                               Display remote directory listing
mkdir <path>                             Create remote directory
put <local_file> [remote_path]           Upload file
pwd                                      Display remote working directory
rm <path>                                Delete remote file
upload <local_file> [remote_path]        Upload file
```


## development

Before propose your merge

> flake8

for push on pypi

> python -m build

> twine upload dist/*


## todo

- use https://github.com/prompt-toolkit/python-prompt-toolkit
- add systrace in log file
- add synchro functionnality
- use file=sys.stderr for error shell
- can color sys.stderr
