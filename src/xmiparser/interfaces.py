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

class IXMIElement(IAttributeAnnotatable, ILocation):
    """An XMI Element.
    """
            
    XMI = Attribute(u"the current IXMIFlavor instance")
    
    cleanName = Attribute(u"the clean name consists only of [a..z A..Z 0..9 _]"
                          u"and does not start with [0..9]")
    
    children = Attribute(u"all children elements, also IXMIElement" 
                         u"implementations are expected")
    
    id = Attribute(u"XMI: identifier. string expected")

    maxOccurs = Attribute(u"UML: maximum occurencies. integer expected.")
    
    isComplex = Attribute(u"UML: complex or not. boolean expected")
    
    type = Attribute(u"UML/XMI: ???") # XXX which type? needs research
    
    subTypes = Attribute(u"UML/XMI: ??") # XXX which types? needs research
    
    attributeDefs = Attribute(u"UML: Attributes of this element. "
                              u"list dict expected")

    operationDefs = Attribute(u"UML: Operations of this element. "
                              u"list expected")
    
    tgvs = Attribute(u"UML: Tagged Values of this element. "
                     u"ordered dict expected")

    stereotypes = Attribute(u"UML: Stereotypes of this element. "
                            u"list expected")
    
    clientDependencies = Attribute(u"UML: ??Which dependency is this?") # XXX 
    
    

class IXMIPackage(IXMIElement):
    """An XMI Package.
    """
    
class IXMIModel(IXMIPackage):
    """An XMI Model.
    """