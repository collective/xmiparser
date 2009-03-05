from zope.interface import Interface

class IPackage(Interface):
    """Package UML Element containing classes.
    """
    
class IModel(IPackage):
    """Model UML Element containing classes, packages, ...
    """
