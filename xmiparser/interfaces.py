# Copyright 2003-2009, Blue Dynamics Alliance - http://bluedynamics.com
# GNU General Public Licence Version 2 or later

from zope.interface import Interface
from zope.interface import Attribute
from zope.location.interfaces import ILocation
from zope.annotation.interfaces import IAttributeAnnotatable

class IModelFactory(Interface):
    """factory return IModel implementing instance.
    """
    
    def __call__(sourcepath):
        """Create and return IModel implementing instance.
        
        @param sourcepath: Source path of *.xmi, *.zargo, *.zuml
        """

class IElement(IAttributeAnnotatable, ILocation):
    """An XMI Element.
    """
    
    annotations = Attribute(u"The annotations of this element")

class IPackage(IElement):
    """An XMI Package.
    """
    
class IModel(IPackage):
    """An XMI Model.
    """