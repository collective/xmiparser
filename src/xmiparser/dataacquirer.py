# Copyright 2003-2009, BlueDynamics Alliance - http://bluedynamics.com
# GNU General Public License Version 2 or later

# XXX move me to ``agx.transform.uml2fs``

from zope.interface import implements
from zope.location.location import LocationIterator
from interfaces import IDataAcquirer

class DataAcquirerBase(object):
    
    implements(IDataAcquirer)
    
    def __init__(self, context):
        self.context = context
    
    def __getitem__(self, name):
        # XXX
        pass
    
    def get(self, name, default=None, aggregate=False):
        # XXX
        pass
    
    def __contains__(self, name):
        # XXX
        pass

class AnnotationAcquirer(DataAcquirerBase):
    """XXX
    """

class TaggedValueAcquirer(DataAcquirerBase):
    """XXX
    """

class StereotypeAcquirer(DataAcquirerBase):
    """XXX
    """
    