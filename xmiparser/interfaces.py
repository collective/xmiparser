# Copyright 2003-2009, Blue Dynamics Alliance - http://bluedynamics.com
# GNU General Public Licence Version 2 or later

from zope.interface import Interface

class IModelFactory(Interface):
    """factory return IModel implementing instance.
    """
    
    def __call__(xschemaFileName=None,
                 xschema=None,
                 packages=[],
                 profile_dir=None,
                 **kw):
        """Create and return IModel implementing instance.
        
        XXX: get rid of generator reference.
        """

# below interfaces are currently just markers.
# XXX: Detailes interface definitions.

class IPackage(Interface):
    """Package UML Element containing classes.
    """
    
class IModel(IPackage):
    """Model UML Element containing classes, packages, ...
    """
