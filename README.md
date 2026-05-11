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

> fbc servers
> fbc server show <name_connection>
> fbc server set <name_connection> ssl true

connection

> fbc http://<username>@<password>:<domain of filebrowser>.com
> fbc <name_connection>


## development

Before propose your merge

> flake8

for push on pypi

> python -m build

> twine upload dist/*


## todo

- add systrace in log file
- add local command
- add synchro functionnality
- prompt dynamical
