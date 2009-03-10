# Copyright 2003-2009, Blue Dynamics Alliance - http://bluedynamics.com
# GNU General Public Licence Version 2 or later

from zope.interface import Interface
from zope.interface import Attribute
from zope.location.interfaces import ILocation
from zope.annotation.interfaces import IAttributeAnnotatable

class IXMIFlavor(Interface):
    """Holds all information relevant to the different flavors of XMI, such as 
    its versions: 1.0, 1.1, 1.2
    
    The details need to be researched, such as which methods are meant public 
    and which private and so on. A reverse-engineering task.
    """ 

class IModelFactory(Interface):
    """factory return IModel implementing instance.
    """
    
    def __call__(sourcepath):
        """Create and return IModel implementing instance.
        
        @param sourcepath: Source path of *.xmi, *.zargo, *.zuml
        """
##########    
# ELEMENTS

class IElement(IAttributeAnnotatable, ILocation):
    """An XMI Element.
    """
    
    XMI = Attribute(u"the current IXMIFlavor instance")
    
    annotations = Attribute(u"The annotations of this element")

class IPackage(IElement):
    """An XMI Package.
    """
    
class IModel(IPackage):
    """An XMI Model.
    """