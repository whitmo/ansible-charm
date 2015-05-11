#!/usr/bin/env python
import os
from setuptools import setup
from setuptools import find_packages

PROJECT = u'AnsibleCharm'
VERSION = '0.1'
URL = "https://blog.juju.solutions"
AUTHOR = u'Whit Morriss <whit.morriss@canonical.com>'
AUTHOR_EMAIL = u'whit.morriss@canonical.com'
DESC = "Python library for charming with ansible"


def read_file(file_name):
    file_path = os.path.join(
        os.path.dirname(__file__),
        file_name
        )
    with open(file_path) as fp:
        return fp.read()

setup(
    name=PROJECT,
    version=VERSION,
    description=DESC,
    long_description=read_file('README.md'),
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    license=read_file('LICENSE'),
    packages=find_packages(exclude=['examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "path.py",
        "charmhelpers"
    ],
#    entry_points="""
#    """,
    classifiers=[
        'License :: OSI Approved',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        "Programming Language :: Python",
    ],
)
