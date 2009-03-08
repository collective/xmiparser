# Copyright 2003-2009, BlueDynamics Alliance - http://bluedynamics.com
# GNU General Public License Version 2 or later

import unittest
import zope.component
from pprint import pprint
from interlude import interact
from zope.testing import doctest
from zope.configuration.xmlconfig import XMLConfig

import xmiparser

optionflags = doctest.NORMALIZE_WHITESPACE | \
              doctest.ELLIPSIS | \
              doctest.REPORT_ONLY_FIRST_FAILURE

TESTFILES = [
#    '../xmiparser.txt',
    '../factory.txt',
]

def test_suite():
    XMLConfig('meta.zcml', zope.component)()
    XMLConfig('configure.zcml', xmiparser)()
    
    return unittest.TestSuite([
        doctest.DocFileSuite(
            file, 
            optionflags=optionflags,
            globs={'interact': interact,
                   'pprint': pprint},
        ) for file in TESTFILES
    ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite') 