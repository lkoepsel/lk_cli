# Missing File Utilities
A python package to provide tools for finding missing files.

## Documentation
```bash

           Utilities and Their Descriptions:
           (run hlp to see this list again)


ch:

    ch: check hash - read existing hash.json and .hashes.josn files
    and confirm hashes for files have not changed. Use to ensure
    hash files are in-sync with folder contents.


fhc:

    fhc: Folder Hash Compare (by subfolders)
    Compare two folders by examining the hash files for each of the
    folders, subfolders.

    The process is:

    1. For both folders, 'hw subfolders'. This is preferably performed
    at a much earlier date.

    2. Run fhc folder1 folder2



hc:

    hc: Hash Compare (by specific folders)
    Compare two folders by examining the hashes of the files in each folder

    The process is:

    1. For both folders, 'hw folder'. This is preferably performed
    at a much earlier date.

    2. Run hc folder1 folder2



hlp:

    hlp: help command
    Lists all installed CLI utilities and their descriptions.


hp:

    hp: hash print
    Print hash of each specified file to the screen.
    Uses xxHash64 for speed.


hw:

    hw: hash write
    Write hash of each file in folder to a hashes.json
    file in folder. Uses multiprocessing and xxHash64 for speed.



mf:

    mf: missing files
    Very fast! Compare two folders using hashes. Uses multiprocessing and
    xxHash64 for speed.



mfs:

    mfs: missing files, sequential
    Uses sequential processing to
    compare two folders using hash of each file for comparison.
    Use mf for higher performance, this version retained for checking.

```

## Installation

### 1. Install from GitHub
#### Preferred Install using uv
This version installs uv then using *uv* to install *py_cli*, using *uv* is my new preferred method of adding python tools and packages
```bash
cd
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
uv tool install --from git+https://github.com/lkoepsel/py_cli.git py_cli
```

#### Standard Install
```bash
venv py_cli_env
source .venv/bin/activate
source .venv/bin/Activate.fish
pip install git+https://github.com/lkoepsel/py_cli.git
```

### 2. Tools Installed
* **ch - Check Hash:** - read existing hash.json and .hashes.json files and confirm results of files
* **fhc -  Folder Hash Compare:** Compare two folders by examining the hash file for each of its subfolders.
* **hw - Hash Write:** Write hash of each file in folder to a hashes.json file in folder.
* **mf - Missing File:** Compare two folders using hash of each file for comparison, uses multiprocessing for speed.
* **mfs - Missing File Sequential:** Compare two folders using hash of each file for comparison. Sequential version, retained for checking against *mf*.

## Notes

## Using uv to install

The general sequence of commands are:
```bash
# to install latest version
rm -rf build/ dist/ *.egg-info/  # start with a clean build
uv pip install --upgrade -e .

# to edit files (be sure to increase version number in pyproject.toml)
uvx ruff format
uvx ruff check
# make required fixes
git add -A
git commit -m "message"
git push
# to install latest version
uv pip install --upgrade git+https://github.com/lkoepsel/py_cli.git
```
