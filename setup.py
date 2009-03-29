from setuptools import setup, find_packages
import sys, os

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

version = '1.4'
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
      ], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Philipp Auersperg, Jens Klein',
      author_email='dev@bluedynamics.com',
      url='http://pypi.python.org/pypi/xmiparser',
      license='General Public Licence',
      packages=packages,
      namespace_packages=[],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'zope.interface',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
