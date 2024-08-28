# Missing File Utilities
A python package to provide tools for finding missing files.
 
## Installation

### 1. Install from GitHub

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
### Simple Editing/Running
If in the folder and env is activated, editing the file will be reflected in the execution. Once everything has been resolved to satisfaction for an update, use instructions below.

### To update package
1. Increase version number
```toml
version = "0.6"
```
1. Delete previous build artifacts:
```bash
rm -rf build dist __pycache__ *.egg-info
```
1. Build package
```bash
python -m build
```
1. Upgrade locally using filename of wheel, *confirm new name of wheel based on version number.*
```bash
pip install --upgrade dist/py_cli-0.6-py3-none-any.whl
```