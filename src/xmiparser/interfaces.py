# Copyright 2003-2009, Blue Dynamics Alliance - http://bluedynamics.com
# GNU General Public Licence Version 2 or later

from zope.interface import Interface
from zope.interface import Attribute
from zope.interface.common.mapping import IReadMapping
from zope.interface.common.mapping import IWriteMapping
from zope.location.interfaces import ILocation
from zope.annotation.interfaces import IAttributeAnnotatable

###############################################################################   
# Interfaces to move.
# target not defined yet. maybe ``cornerstone.model``
###############################################################################

class INode(ILocation):
    """A node.
    
    Same signature as ``agx.core.interfaces.INode``.
    """
    
    nodetype = Attribute(u"Type of this node as string.")
    
    children = Attribute(u"Children of this node.")
    
    def __iter__():
        """children iteration.
        """

###############################################################################   
# Interfaces to delete. -> moved to ``agx.transform.uml2fs.interfaces``
###############################################################################

class IDataAcquirer(IReadMapping):
    """Interface for acquiring data from ``zope.location.interfaces.ILocation``
    implementing objects.
    
    The implementation are supposed to acquire informations like:
      * tagged values
      * stereotypes
      * annotations
    """
    
    def __getitem__(name):
        """Acquire data from element.
        
        @param name: key of requested data.
        """
    
    def get(name, default=None, aggregate=False, depth=-1, breaktype=None):
        """Acquire data from object.
        
        @param name: key of requested data.
        @param default: default return value.
        @param aggregate: Flag wether to aggregate requested value.
        @param depth: recurion depth. default ``-1`` is recurion until root.
        @param breaktype: ``agx.core.interfaces.INode.nodetype`` defining
                          the acquisition break point.
        """

class IDataReader(IReadMapping):
    """Convenience reader interface.
    
    The implementation are supposed to read informations like:
      * tagged values
      * stereotypes
      * annotations
    """
    
    aq = Attribute(u"``IDataAcquirer`` implementation")
    
    def keys():
        """Return available keys.
        """

class ITGV(IDataReader):
    """Promised to be an adapter for ``xmiparser.interfaces.IXMIElement`` to
    read tagged values.
    """

class IStereotype(IDataReader):
    """Promised to be an adapter for ``xmiparser.interfaces.IXMIElement`` to
    read stereotypes.
    """

class IAnnotation(IDataReader):
    """Promised to be an adapter for ``xmiparser.interfaces.IXMIElement`` to
    read annotations.
    """

###############################################################################   
# Factories and Accessors
###############################################################################

class IModelFactory(Interface):
    """Factory for ``IXMIModel`` implementing instance.
    """
    
    def __call__(sourcepath):
        """Create and return ``IXMIModel`` implementing instance.
        
        @param sourcepath: Source path of *.xmi, *.zargo, *.zuml
        """

###############################################################################   
# XMI Version
###############################################################################

class IXMIFlavor(Interface):
    """Holds all information relevant to the different flavors of XMI, such as 
    its versions: 1.0, 1.1, 1.2
    
    The details need to be researched, such as which methods are meant public 
    and which private and so on. A reverse-engineering task.
    """ 

###############################################################################   
# Helpers
###############################################################################

class IXMIStateMachineContainer(Interface):
    """XXX
    """

###############################################################################   
# Elements
###############################################################################

class IXMIElement(IAttributeAnnotatable, INode):
    """An XMI Element.
    """
            
    XMI = Attribute(u"the current IXMIFlavor instance")
    
    cleanName = Attribute(u"the clean name consists only of [a..z A..Z 0..9 _]"
                          u"and does not start with [0..9]")
    
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

class IXMIPackage(IXMIElement, IXMIStateMachineContainer):
    """An XMI Package.
    """
    
class IXMIModel(IXMIPackage):
    """An XMI Model.
    """

class IXMIClass(IXMIElement, IXMIStateMachineContainer):
    """XXX
    """

class IXMIInterface(IXMIClass):
    """XXX
    """

class IXMIMethodParameter(IXMIElement):
    """XXX
    """

class IXMIMethod(IXMIElement):
    """XXX
    """

class IXMIAttribute(IXMIElement):
    """XXX
    """

class IXMIAssocEnd(IXMIElement):
    """XXX
    """

class IXMIAssociation(IXMIElement):
    """XXX
    """

class IXMIAssociationClass(IXMIClass, IXMIAssociation):
    """XXX
    """

class IXMIAbstraction(IXMIElement):
    """XXX
    """

class IXMIDependency(IXMIElement):
    """XXX
    """

class IXMIStateMachine(IXMIElement):
    """XXX
    """

class IXMIStateTransition(IXMIElement):
    """XXX
    """

class IXMIAction(IXMIElement):
    """XXX
    """

class IXMIGuard(IXMIElement):
    """XXX
    """

class IXMIState(IXMIElement):
    """XXX
    """

class IXMICompositeState(IXMIState):
    """XXX
    """

class IXMIDiagram(IXMIElement):
    """XXX
    """