# Missing File Utilities
A python package to provide tools for finding missing files.

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
