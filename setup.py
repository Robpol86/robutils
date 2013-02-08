#!/usr/bin/env python -u
#
# Copyright (c) 2012, Robpol86
# This software is made available under the terms of the MIT License that can
# be found in the LICENSE.txt file.
#

import distribute_setup
distribute_setup.use_setuptools()

from setuptools import setup, find_packages

execfile('robutils/version.py')

setup(
    name='robutils',
    version='{0}.{1}.{2}'.format(*__version__),
    author='Robpol86',
    author_email='robpol86@robpol86.com',
    packages=find_packages(),
    package_data={'':['*.txt', '*.rst']},
    scripts=['distribute_setup.py',],
    url='http://code.google.com/p/robutils/',
    license='MIT',
    description='Convenience classes for CLI Python applications.',
    long_description=open('README.rst').read(),
    install_requires=[
        'psutil >= 0.6.1',
        'paramiko >= 1.9.0',
        'pandas >= 0.9.1',
    ],
)

