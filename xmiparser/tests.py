# -*- coding: utf-8 -*-

import unittest
import doctest


DOCTEST_FILES = [
        'xmiparser.txt',
]


def test_suite():
    suite = unittest.TestSuite()

    for testfile in DOCTEST_FILES:
        suite.addTest(doctest.DocFileSuite(testfile))

    return suite

