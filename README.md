# Missing File Utilities
A python package to provide utilities for finding missing files.

## Description

## Platforms
 
## Installation

### 1. Install from GitHub

```bash
pip install git+https://github.com/lkoepsel/py_cli#egg=py_cli
```

### 2. Commands Installed
* **ch - Check Hash:** - read existing hash.json file and confirm results of file
* **fhc -  Folder Hash Compare:** Compare two folders by examining the hash file for each of its subfolders.
* **hw - Hash Write:** Write hash of each file in folder to a hashes.json file in folder.
* **mf - Missing File:** Compare two folders using hash of each file for comparison.
* **mfp - Missing File multi-Processing:** Compare two folders using hash of each file for comparison, uses multiprocessing for speed.



### 3. 

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
1. Upgrade locally using filename of wheel
```bash
pip install --upgrade dist/py_cli-0.6-py3-none-any.whl
```