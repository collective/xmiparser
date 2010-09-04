import doctest
import unittest


def test_suite():
    suite = unittest.TestSuite()
    suite.addTests([
        doctest.DocFileSuite('xmiparser.txt'),
    ])
    return suite
