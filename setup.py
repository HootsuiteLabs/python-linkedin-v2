#!/usr/bin/env python
import os

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from linkedin_v2 import __version__


with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    long_description = readme.read()

setup(name='python-linkedin-v2',
      version=__version__,
      description='Python Interface to the LinkedIn API V2',
      long_description=long_description,
      long_description_content_type="text/markdown",
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Natural Language :: English',
      ],
      keywords='linkedin python',
      author='Rei Colina',
      author_email='reinaldo13+github@gmail.com',
      maintainer='Rei Colina',
      maintainer_email='reinaldo13+github@gmail.com',
      url='https://github.com/HootsuiteLabs/python-linkedin-v2',
      license='MIT',
      packages=['linkedin_v2'],
      install_requires=['requests>=1.1.0', 'requests-oauthlib>=0.3'],
      zip_safe=False
)
