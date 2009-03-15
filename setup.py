# Copyright 2003-2009, BlueDynamics Alliance - http://bluedynamics.com
# GNU General Public License Version 2 or later

from setuptools import setup, find_packages
import sys, os

version = '2.0'
shortdesc = "XMI Parser (API for the UML XML representation specified by OMG)"
longdesc = open(os.path.join(os.path.dirname(__file__), 'README.txt')).read()
packages=find_packages(exclude=['ez_setup',])

setup(name='xmiparser',
      version=version,
      description=shortdesc,
      long_description=longdesc,
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
          'zope.interface',
          'stripogram',
          'zope.annotation',
          'zope.location',
          'cornerstone.model',
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
