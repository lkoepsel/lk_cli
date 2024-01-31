from setuptools import setup, find_packages

setup(
    name='mf',
    version='0.4',
    # This tells setuptools to include any directories, and subdirectories,
    # which include an __init__.py file
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "xxhash"
    ],
    entry_points={
        'console_scripts': [
            'mf = mf:mf',
            'mfp = mfp:mf',
            'hw = hw:hw',
            'ch = ch:ch',
        ],
    },
    # Metadata
    author='Lief Koepsel',
    author_email='lkoepsel@wellys.com',
    description='Missing file utilities',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    # Use the URL to the github repo or wherever your code is hosted
    url='https://github.com/lkoepsel/py_cli',
    # Descriptive keywords to help find your package
    keywords='Python missing files',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        # Pick a topic relevant for your package
        'Topic :: Software Development :: Communications',
        'License :: OSI Approved :: MIT License',  # Again, pick a license
        # Specify the Python versions you support here
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.12',
    ],
)
