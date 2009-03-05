from zope.interface import Interface

"""
This interfaces are currently just markers.

XXX: Detailes interface definitions.
"""

class IPackage(Interface):
    """Package UML Element containing classes.
    """
    
class IModel(IPackage):
    """Model UML Element containing classes, packages, ...
    """
