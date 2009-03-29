# Copyright 2003-2009, BlueDynamics Alliance - http://bluedynamics.com
# GNU General Public License Version 2 or later

from setuptools import setup, find_packages
import sys, os

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

version = '2.0'
shortdesc = "XMI Parser (API for the UML XML representation specified by OMG)"
packages=find_packages(exclude=['ez_setup',])

long_description = (
    read('README.txt')
    + '\n' +
    read('CHANGES.txt')
    + '\n' +
    'Download\n'
    '========\n'
    )

setup(name='xmiparser',
      version=version,
      description=shortdesc,
      long_description=long_description,
      classifiers=[
            'Programming Language :: Python',
            'License :: OSI Approved :: GNU General Public License (GPL)',
            'Operating System :: OS Independent',
      ],
      keywords='uml, xmi, parser',
      author='Philipp Auersperg, Jens Klein, Robert Niederreiter, et al',
      author_email='dev@bluedynamics.com',
      url='https://svn.plone.org/svn/collective/xmiparser',
      license='GNU General Public Licence',
      packages=find_packages('src'),
      package_dir = {'': 'src'},
      namespace_packages=[],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'zodict',
          'stripogram',
          'zope.interface',
          'zope.annotation', # this will propably be removed
          'zope.location',
          'zodict',
      ],
      extras_require = dict(
          test=[
            'interlude',
            'zope.component',
            'zope.configuration',
            'zope.security',
            'zope.testing',
          ]
      ),
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
