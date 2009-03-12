# Copyright 2003-2009, BlueDynamics Alliance - http://bluedynamics.com
# GNU General Public License Version 2 or later

from zope.interface import implements
from interfaces import IDataReader
from interfaces import ITGV
from interfaces import IStereotype
from interfaces import IAnnotation
from dataacquirer import TaggedValueAcquirer
from dataacquirer import StereotypeAcquirer
from dataacquirer import AnnotationAcquirer

class DataReaderBase(object):
    
    implements(IDataReader)
    
    def __init__(self, context):
        self.context = context
        
    @property
    def aq(self):
        raise NotImplementedError(u"Abstract ``IDataReader`` does not "
                                   "provide ``aq`` attribute")
    
    def __getitem__(self, name):
        # XXX
        pass
    
    def __contains__(self, name):
        # XXX
        pass
    
    def get(self, name, default=None):
        # XXX
        pass
    
    def keys(self):
        # XXX
        pass

class TGV(DataReaderBase):
    
    implements(ITGV)
    
    @property
    def aq(self):
        if not hasattr(self, '_aq'):
            self._aq = TaggedValueAcquirer(self.context)
        return self._aq

class Stereotype(DataReaderBase):
    
    implements(IStereotype)
    
    @property
    def aq(self):
        if not hasattr(self, '_aq'):
            self._aq = StereotypeAcquirer(self.context)
        return self._aq

class Annotation(DataReaderBase):
    
    implements(IAnnotation)
    
    @property
    def aq(self):
        if not hasattr(self, '_aq'):
            self._aq = AnnotationAcquirer(self.context)
        return self._aq