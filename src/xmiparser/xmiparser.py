# GNU General Public License Version 2 or later

import string
import os.path
import logging
from zipfile import ZipFile
from sets import Set
from odict import odict
from xml.dom import minidom
from zope.interface import implements
from stripogram import html2text
from utils import mapName
from utils import toBoolean
from utils import normalize
from utils import wrap as doWrap
import xmiutils
from interfaces import IPackage, IModel
import zargoparser

log = logging.getLogger('XMIparser')

# Set default wrap width
default_wrap_width = 64

# Tag constants
clean_trans = string.maketrans(':-. /$', '______')


allObjects = {}

class PseudoElement(object):
    # urgh, needed to pretend a class
    # wtf - why is this needed?
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def getName(self):
        return self.__name__

    def getModuleName(self):
        return self.getName()

class XMIElement(object):

    __parent__ = None
    __name__ = None
    package = None

    def __init__(self, domElement=None, name='', *args, **kwargs):
        self.domElement = domElement
        self.__name__ = name
        self.cleanName = ''
        self.atts = {}
        self.children = []
        self.maxOccurs = 1
        self.complex = 0
        self.type = 'NoneType'
        self.attributeDefs = []
        self.methodDefs = []
        self.id = ''
        self.taggedValues = odict()
        self.subTypes = []
        self.stereoTypes = []
        self.clientDependencies = []
        # Space to store values by external access. Use annotate() to
        # store values in this dict, and getAnnotation() to fetch it.
        self.annotations = {}
        # Take kwargs as attributes
        self.__dict__.update(kwargs)
        if domElement:
            allObjects[domElement.getAttribute('xmi.id')] = self
            self._initFromDOM(domElement)
            self.buildChildren(domElement)

    def __str__(self):
        return '<%s %s>' % (self.__class__.__name__, self.getName())
    
    __repr__=__str__

    def getId(self):
        return self.id

    def getParent(self):
        return self.__parent__

    def setParent(self, parent):
        self.__parent__ = parent

    def parseTaggedValues(self):
        """Gather the tagnames and tagvalues for the element.
        """
        log.debug("Gathering the taggedvalues for element %s.", self.__name__)
        tgvsm = getElementByTagName(self.domElement, XMI.TAGGED_VALUE_MODEL,
                                    default=None, recursive=0)
        if tgvsm is None:
            log.debug("Found nothing.")
            return
        tgvs = getElementsByTagName(tgvsm, XMI.TAGGED_VALUE, recursive=0)
        for tgv in tgvs:
            try:
                tagname, tagvalue = XMI.getTaggedValue(tgv)
                log.debug("Found tag '%s' with value '%s'.", tagname, tagvalue)
                if self.taggedValues.has_key(tagname):
                    log.debug("Invoking Poseidon multiline fix for "
                              "tagname '%s'.", tagname)
                    self.taggedValues[tagname] += '\n'+tagvalue
                else:
                    self.taggedValues[tagname] = tagvalue
            except TypeError, e:
                log.warn("Broken tagged value in id '%s'.",
                         XMI.getId(self.domElement))
        log.debug("Found the following tagged values: %r.",
                  self.getTaggedValues())

    def setTaggedValue(self, k, v):
        self.taggedValues[k] = v

    def _initFromDOM(self, domElement):
        if not domElement:
            domElement = self.domElement

        if domElement:
            self.id = str(domElement.getAttribute('xmi.id'))
            self.__name__ = XMI.getName(domElement)
            log.debug("Initializing from DOM: name='%s', id='%s'.",
                      self.__name__, self.id)
            self.parseTaggedValues()
            self.calculateStereoType()
            mult = getElementByTagName(domElement, XMI.MULTIPLICITY, None)
            if mult:
                maxNodes = mult.getElementsByTagName(XMI.MULT_MAX)
                if maxNodes and len(maxNodes):
                    maxNode = maxNodes[0]
                    self.maxOccurs = int(getAttributeValue(maxNode))
                    if self.maxOccurs == -1:
                        self.maxOccurs = 99999
                    log.debug("maxOccurs = '%s'.", self.maxOccurs)
            domElement.xmiElement = self

    def addChild(self, element):
        self.children.append(element)

    def addSubType(self, st):
        self.subTypes.append(st)

    def getChildren(self):
        return self.children

    def getName(self, doReplace=False):
        if self.__name__:
            res = self.__name__
        else:
            res = self.id
        return normalize(res, doReplace)
    
    @property
    def classcategory(self):
        return "%s.%s" % (self.__class__.__module__, self.__class__.__name__)

    def getTaggedValue(self, name, default=''):
        log.debug("Getting value for tag '%s' (default=%s). "
                  "Note: we're not doing this recursively.",
                  name, default)
#===============================================================================
#        if not tgvRegistry.isRegistered(name, self.classcategory):
#            # The registry does the complaining :-)
#            pass
#===============================================================================
        res = self.taggedValues.get(name, default)
        log.debug("Returning value '%s',", res)
        return res

    def hasTaggedValue(self, name):
        return self.taggedValues.has_key(name)

    def hasAttributeWithTaggedValue(self, tag, value=None):
        """Return True if any attribute has a TGV 'tag'.

        If given, also check for a matching value.
        """
        log.debug("Searching for presence of an attribute with tag '%s'.", tag)
        if value:
            log.debug("But, extra condition, the value should be '%s'.", value)
        attrs = self.getAttributeDefs()
        for attr in attrs:
            if attr.hasTaggedValue(tag):
                log.debug("Yep, we've found an attribute with that tag.")
                if not value:
                    # We don't have to have a specific value
                    return True
                else:
                    # We need a specific value
                    if attr.getTaggedValue(tag, None) == value:
                        return True
                    else:
                        log.debug("But, alas, the value isn't right.")
        log.debug("No, found nothing.")
        return False

    def getTaggedValues(self):
#===============================================================================
#        for tagname in self.taggedValues.keys():
#            if not tgvRegistry.isRegistered(tagname, self.classcategory, 
#                                            silent=True):
#                # The registry does the complaining :-)
#                pass
#===============================================================================
        return self.taggedValues

    def getDocumentation(self, striphtml=0, wrap=-1):
        """Return formatted documentation string.

        try to use stripogram to remove (e.g. poseidon) HTML-tags, wrap and
        indent text. If no stripogram is present it uses wrap and indent
        from own utils module.

        striphtml(boolean) -- use stripogram html2text to remove html tags

        wrap(integer) -- default: 60, set to 0: do not wrap,
                         all other >0: wrap with this value
        """

        log.debug("Trying to find documentation for this element.")
        #TODO: create an option on command line to control the page width
        log.debug("First trying a tagged value.")

        # tagged value documentation? Probably this gets the UML
        # documentation or so. I mean, having a tagged value for
        # this?!?
        # returning an empty string to get rid of the "unregistered
        # TGV" warnings.
        if True:
            return ''
        # The rest isn't executed.
        doc = self.getTaggedValue('documentation')
        if not doc:
            log.debug("Didn't find a tagged value 'documentation'. "
                      "Returning empty string.")
            return ''
        if wrap == -1:
            wrap = default_wrap_width
        doc = html2text(doc, (), 0, 1000000).strip()
        if wrap:
            log.debug("Wrapping the documenation.")
            doc = doWrap(doc, wrap)
        log.debug("Returning documenation '%r'.",
                  doc)
        return doc

    def getUnmappedCleanName(self):
        return self.unmappedCleanName

    def setName(self, name):
        log.debug("Setting our name to '%s' the hard way. "
                  "The automatic mechanism set it to '%s' already.",
                  name, self.getName())
        self.__name__ = name

    def getAttrs(self):
        return self.attrs

    def getMaxOccurs(self):
        return self.maxOccurs

    def getType(self):
        return self.type

    def isComplex(self):
        return self.complex

    def addAttributeDef(self, attrs, pos=None):
        if pos is None:
            self.attributeDefs.append(attrs)
        else:
            self.attributeDefs.insert(0, attrs)

    def getAttributeDefs(self):
        return self.attributeDefs

    def getRef(self):
        return None

    def getRefs(self):
        """Returns all referenced schema names."""
        return [str(c.getRef()) for c in self.getChildren() if c.getRef()]

    def show(self, outfile, level):
        showLevel(outfile, level)
        outfile.write('Name: %s  Type: %s\n' % (self.__name__, self.type))
        showLevel(outfile, level)
        outfile.write('  - Complex: %d  MaxOccurs: %d\n' % \
            (self.complex, self.maxOccurs))
        showLevel(outfile, level)
        outfile.write('  - Attrs: %s\n' % self.attrs)
        showLevel(outfile, level)
        outfile.write('  - AttributeDefs: %s\n' % self.attributeDefs)
        for key in self.attributeDefs.keys():
            showLevel(outfile, level + 1)
            outfile.write('key: %s  value: %s\n' % \
                (key, self.attributeDefs[key]))
        for child in self.getChildren():
            child.show(outfile, level + 1)

    def addMethodDefs(self, m):
        if m.getName():
            self.methodDefs.append(m)

    def getCleanName(self):
        # If there is a namespace, replace it with an underscore.
        if self.getName():
            self.unmappedCleanName = str(self.getName()).translate(clean_trans)
        else:
            self.unmappedCleanName = ''
        return mapName(self.unmappedCleanName)

    def isIntrinsicType(self):
        return str(self.getType()).startswith('xs:')

    def _buildChildren(self, domElement):
        pass

    def getMethodDefs(self, recursive=0):
        log.debug("Getting method definitions (recursive=%s)...", recursive)
        res = [m for m in self.methodDefs]
        log.debug("Our own methods: %r.", res)
        if recursive:
            log.debug("Also looking recursively to our parents...")
            parents = self.getGenParents(recursive=1)
            for p in parents:
                res.extend(p.getMethodDefs())
            log.debug("Our total methods: %r.", res)
        return res

    def calculateStereoType(self):
        return XMI.calculateStereoType(self)

    def setStereoType(self, st):
        self.stereoTypes = [st]

    def getStereoType(self):
        if self.stereoTypes:
            return self.stereoTypes[0]
        else:
            return None

    def addStereoType(self, st):
        log.debug("Adding stereotype '%s' to this element's internal list.", st)
        self.stereoTypes.append(st)

    def getStereoTypes(self):
        return self.stereoTypes

    def hasStereoType(self, stereotypes, umlprofile=None):
        log.debug("Looking if element has stereotype %r", stereotypes)
        if isinstance(stereotypes, (str, unicode)):
            stereotypes = [stereotypes]
        if umlprofile:
            for stereotype in stereotypes:
                found = umlprofile.findStereoTypes(entities=[self.classcategory])
                if found:
                    log.debug("Stereotype '%s' is registered.",
                              stereotype)
                else:
                    log.warn("DEVELOPERS: Stereotype '%s' isn't registered "
                             "for element '%s'.", stereotype, self.classcategory)
        for stereotype in stereotypes:
            if stereotype in self.getStereoTypes():
                return True
        return False

    def getFullQualifiedName(self):
        return self.getName()

    def getPackage(self):
        """Returns the package to which this object belongs."""
        if self.package is not None:
            return self.package
        if self.getParent():
            return self.getParent().getPackage()
        return None

    def getPath(self):
        return [self.getName()]

    def getModuleName(self, lower=False):
        """Gets the name of the module the class is in."""
        basename = self.getCleanName()
        return self.getTaggedValue('module') or \
               (lower and basename.lower() or basename)

    def annotate(self, key, value):
        self.annotations[key] = value

    def getAnnotation(self, name, default=[]):
        return self.annotations.get(name, default)

    def addClientDependency(self, dep):
        self.clientDependencies.append(dep)

    def getClientDependencies(self, includeParents=False,
                              dependencyStereotypes=None):
                                  
        res = list(self.clientDependencies)
        if includeParents:
            o = self.getParent()
            if o:
                res.extend(o.getClientDependencies(includeParents=includeParents))
                res.reverse()
        if dependencyStereotypes:
            res = [r for r in res if r.hasStereoType(dependencyStereotypes)]
        return res

    def getClientDependencyClasses(self, includeParents=False,
                                   dependencyStereotypes=None,
                                   targetStereotypes=None):
        res = [dep.getSupplier()
               for dep in self.getClientDependencies(
                   includeParents=includeParents,
                   dependencyStereotypes=dependencyStereotypes)
               if dep.getSupplier() and
                  dep.getSupplier().__class__.__name__
                  in ('XMIClass', 'XMIInterface')]

        if targetStereotypes:
            res = [r for r in res if r.hasStereoType(targetStereotypes)]

        return res

class StateMachineContainer(object):
    """Mixin class"""
    
    def __init__(self, el):
        self.statemachines = []

    def findStateMachines(self):
        log.debug("Trying to find statemachines...")
        try:
            ownedElement = getElementByTagName(self.domElement,
                                               [XMI.OWNED_ELEMENT,
                                                XMI.OWNED_BEHAVIOR],
                                               default=None)
        except:
            log.debug("Getting the owned element the normal way didn't work.")
            try:
                ownedElement = getElementByTagName(self.domElement,
                                                   [XMI.OWNED_BEHAVIOR],
                                                   default=None, recursive=1)
            except:
                log.debug("Getting the owned element the poseidon 3.1 "
                          "way also didn't work.")
                # BBB backward compatible with argouml's xmi1.0
                log.debug("Backward compatability mode for argouml's xmi1.0.")
                ownedElement = XMI.getOwnedElement(self.domElement)

        if not ownedElement:
            log.debug("Setting ownedElement to self.domElement as fallback.")
            ownedElement = self.domElement
        log.debug("We set the owned element as: %s.", ownedElement)

        statemachines = getElementsByTagName(ownedElement, XMI.STATEMACHINE)
        log.debug("Found the following statemachines: %r.", statemachines)
        return statemachines

    def buildStateMachines(self, recursive=1):
        res = {}
        statemachines = self.findStateMachines()
        for m in statemachines:
            sm = XMIStateMachine(m, parent=self)
            if sm.getName():
                # Determine the correct product where it belongs
                products = [c.getPackage().getProduct()
                            for c in sm.getClasses()]
                # Associate the WF with the first product
                if products:
                    product = products[0]
                else:
                    products = self
                product.addStateMachine(sm)
                res[sm.getName()] = sm
        if recursive:
            for p in self.getPackages():
                res.update(p.buildStateMachines())
        return res

    def addStateMachine(self, sm, reparent=0):
        if not sm in self.statemachines:
            self.statemachines.append(sm)
            if reparent:
                sm.setParent(self)
        if hasattr(self, 'isProduct') and not self.isProduct():
            self.getProduct().addStateMachine(sm, reparent=0)
        if not hasattr(self, 'isProduct'):
            self.getPackage().getProduct().addStateMachine(sm, reparent=0)

    def getStateMachines(self):
        return self.statemachines


class XMIPackage(XMIElement, StateMachineContainer):
    
    implements(IPackage)

    project = None
    isroot = 0

    def __init__(self, el):
        super(XMIPackage, self).__init__(self, el)
        self.classes = []
        self.interfaces = []
        self.packages = []
        # outputDirectoryName is used when setting the output
        # directory on the command line. Effectively only used for
        # single products. Ignored when not set.
        self.outputDirectoryName = None

    def _initFromDOM(self, domElement=None):
        self.parentPackage = None
        super(XMIPackage, self)._initFromDOM(self, domElement)

    def getClasses(self, recursive=0, ignoreInternals=True):
        res = [c for c in self.classes]
        if ignoreInternals:
            res = [c for c in self.classes if not c.isInternal()]            
        if recursive:
            res = list(res)
            for p in self.getPackages():
                res.extend(p.getClasses(recursive=1,ignoreInternals=ignoreInternals))
        return res

    def getAssociations(self, recursive=0):
        classes = self.getClassesAndInterfaces(recursive=recursive)
        res = Set()
        for cl in classes:
            res.union_update(cl.getFromAssociations())
        return res

    def addClass(self, cl):
        self.classes.append(cl)
        cl.package = self

    def addInterface(self, cl):
        self.interfaces.append(cl)
        cl.package = self

    def getInterfaces(self, recursive=0):
        res = self.interfaces
        if recursive:
            res = list(res)
            for p in self.getPackages():
                res.extend(p.getInterfaces(recursive=1))
        return res

    def getClassesAndInterfaces(self, recursive=0):
        return self.getClasses(recursive=recursive) + \
               self.getInterfaces(recursive=recursive)

    def getChildren(self):
        return self.children + self.getClasses() + \
               self.getPackages() + self.getInterfaces()

    def addPackage(self, p):
        self.packages.append(p)
        p.parent = self

    def getPackages(self, recursive=False):
        res=self.packages

        if recursive:
            res = list(res)
            for p in self.packages:
                res.extend(p.getPackages(recursive=1))

        return res

    def buildPackages(self):
        packEls = XMI.getPackageElements(self.domElement)
        for p in packEls:
            if XMI.getName(p) == 'java':
                continue
            package = XMIPackage(p)
            self.addPackage(package)
            package.buildPackages()

    def buildClasses(self):
        ownedElement = XMI.getOwnedElement(self.domElement)
        if not ownedElement:
            log.warn("Empty package: '%s'.",
                     self.getName())
            return

        classes = getElementsByTagName(ownedElement, XMI.CLASS) + \
           getElementsByTagName(ownedElement, XMI.ASSOCIATION_CLASS)
        for c in classes:
            if c.nodeName == XMI.ASSOCIATION_CLASS:
                # maybe it was already instantiated (when building relations)?
                classId = c.getAttribute('xmi.id').strip()
                if allObjects.has_key(classId):
                    xc = allObjects[classId]
                    xc.setPackage(self)
                else:
                    xc = XMIAssociationClass(c, package=self)
            else:
                xc = XMIClass(c, package=self)
            if xc.getName():
                self.addClass(xc)

        for p in self.getPackages():
            p.buildClasses()

    def buildInterfaces(self):
        ownedElement = XMI.getOwnedElement(self.domElement)
        if not ownedElement:
            log.warn("Empty package: '%s'.",
                     self.getName())
            return

        classes = getElementsByTagName(ownedElement, XMI.INTERFACE)

        for c in classes:
            xc = XMIInterface(c, package=self)
            if xc.getName():
                self.addInterface(xc)

        for p in self.getPackages():
            p.buildInterfaces()

    def buildClassesAndInterfaces(self):
        self.buildInterfaces()
        self.buildClasses()

    def isRoot(self):
        # TBD Handle this through the stereotype registry
        return self.isroot or self.hasStereoType(['product', 'zopeproduct',
                                                  'Product', 'ZopeProduct'])

    isProduct = isRoot

    def getPath(self, includeRoot=1, absolute=0, parent=None):
        res = []
        o = self

        if self.isProduct():
            # Products are always handled as top-level
            if includeRoot:
                return [o]
            else:
                return []

        while True:
            if includeRoot:
                res.append(o)
            if o.isProduct():
                break
            if not o.getParent():
                break
            if o == parent:
                break
            if not includeRoot:
                res.append(o)
            o = o.getParent()

        res.reverse()
        return res

    def getFilePath(self, includeRoot=1, absolute=0):
        names = [p.getModuleNameForDirectoryName() for p in
                 self.getPath(includeRoot=includeRoot, absolute=absolute)]
        if not names:
            return ''
        res = os.path.join(*names)
        return res

    def getRootPackage(self):
        o = self
        while not o.isRoot():
            o = o.getParent()
        return o

    def getProduct(self):
        o = self
        while not o.isProduct():
            o = o.getParent()
        return o

    def getProductName(self):
        return self.getProduct().getCleanName()

    def getModuleNameForDirectoryName(self):
        outdir = self.getOutputDirectoryName()
        if outdir:
            return outdir
        else:
            return self.getModuleName()

    def getOutputDirectoryName(self):
        return self.outputDirectoryName

    def setOutputDirectoryName(self, name):
        self.outputDirectoryName = name

    def getProductModuleName(self):
        return self.getProduct().getModuleName()

    def isSubPackageOf(self, parent):
        o = self
        while o:
            if o == parent:
                return True
            o = o.getParent()
        return False

    def getQualifiedName(self, ref, includeRoot=True):
        """Returns the qualified name of that package.

        Depending of the reference package 'ref' it generates an absolute
        path or a relative path if the pack(self) is a subpack of 'ref'.
        """
        path = self.getPath(includeRoot=includeRoot, parent=ref)
        return ".".join([p.getName() for p in path])


class XMIModel(XMIPackage):
    implements(IModel)
    isroot = 1
    parent = None
    diagrams = {}
    diagramsByModel = {}

    def __init__(self, doc):
        self.document = doc
        self.content = XMI.getContent(doc)
        self.model = XMI.getModel(doc)
        XMIPackage.__init__(self, self.model)

    def findStateMachines(self):
        statemachines = getElementsByTagName(self.content, XMI.STATEMACHINE)
        statemachines.extend(getElementsByTagName(self.model, XMI.STATEMACHINE))
        log.debug("Found the following state machines: %r.", statemachines)
        ownedElement = XMI.getOwnedElement(self.domElement)
        statemachines.extend(getElementsByTagName(ownedElement,
                                                  XMI.STATEMACHINE))
        return statemachines

    def buildDiagrams(self):
        diagram_els = getElementsByTagName(self.content, XMI.DIAGRAM)
        for el in diagram_els:
            diagram = XMIDiagram(el)
            self.diagrams[diagram.getId()] = diagram
            self.diagramsByModel[diagram.getModelElementId()] = diagram

    def getAllStateMachines(self):
        res = []
        res.extend(self.getStateMachines())
        for p in self.getPackages():
            res.extend(p.getStateMachines())
        return res

    def associateClassesToStateMachines(self):
        sms = self.getAllStateMachines()
        smdict = {}
        for sm in sms:
            smdict[sm.getName()] = sm

        for cl in self.getClasses(recursive=1):
            uf = cl.getTaggedValue('use_workflow')
            if uf:
                wf = smdict.get(uf)
                if not wf:
                    log.debug('associated workflow does not exist: %s' % uf)
                    continue
                smdict[uf].addClass(cl)


class XMIClass(XMIElement, StateMachineContainer):
    package = None
    isinterface = 0
    # [Reinout] Doesn't this mean that there's just one class-wide
    # state machine? So: no way of having a per-class-instance state
    # machine? Bug?
    statemachine = None

    def __init__(self, *args, **kw):
        log.debug("Initialising class.")
        # ugh, setPackage(). Handle this with some more generic zope3
        # parent() relation. [reinout]
        self.setPackage(kw.get('package', None))
        log.debug("Package set to '%s'.", self.package.name)
        log.debug("Running StateMachineContainer's init...")
        StateMachineContainer.__init__(self)
        log.debug("Running XMIElement's init...")
        XMIElement.__init__(self, *args, **kw)
        self.assocsTo = []
        self.assocsFrom = []
        self.genChildren = []
        self.genParents = []
        self.realizationChildren = []
        self.realizationParents = []
        self.adaptationChildren = []
        self.adaptationParents = []
        self.internalOnly = 0
        self.type = self.__name__

    def setPackage(self, p):
        self.package = p

    def _initFromDOM(self, domElement):
        XMIElement._initFromDOM(self, domElement)
        XMI.calcClassAbstract(self)
        XMI.calcVisibility(self)
        XMI.calcOwnerScope(self)
        self.buildStateMachines(recursive=0)

    def isInternal(self):
        return self.internalOnly

    def isEmpty(self):
        return not self.getMethodDefs() and \
            not self.getAttributeDefs() and \
            not self.assocsTo and \
            not self.assocsFrom and \
            not self.genChildren and \
            not self.genParents and \
            not self.realizationChildren and \
            not self.realizationParents and \
            not self.adaptationChildren and \
            not self.adaptationParents

    def getVisibility(self):
        return self.visibility

    def addGenChild(self, c):
        self.genChildren.append(c)

    def addGenParent(self, c):
        self.genParents.append(c)

    def getAttributeNames(self):
        return [a.getName() for a in self.getAttributeDefs()]

    def hasAttribute(self, a):
        return a in self.getAttributeNames()

    def getGenChildren(self, recursive=0):
        """Return the generalization children."""
        log.debug("Finding this class's children...")
        res = [c for c in self.genChildren]
        if recursive:
            log.debug("Also looking recursively further down "
                      "the family tree.")
            for r in res:
                res.extend(r.getGenChildren(1))
        log.debug("Found: '%r'.", res)
        return res

    def getGenChildrenNames(self, recursive=0):
        """Returns the names of the generalization children."""
        return [o.getName() for o in self.getGenChildren(recursive=recursive)]

    def getGenParents(self, recursive = 0):
        """Returns generalization parents."""
        log.debug("Looking for this class's parents...")
        res = [c for c in self.genParents]
        if recursive:
            log.debug("Also looking recursively up the family tree.")
            for r in res:
                res.extend(r.getGenParents(1))
        log.debug("Found the following parents: '%r'.", res)
        return res

    def _buildChildren(self, domElement):

        for el in domElement.getElementsByTagName(XMI.ATTRIBUTE):
            att = XMIAttribute(el)
            att.setParent(self)
            self.addAttributeDef(att)
        for el in domElement.getElementsByTagName(XMI.METHOD):
            meth = XMIMethod(el)
            meth.setParent(self)
            self.addMethodDefs(meth)

        if XMI.getGenerationOption('default_field_generation'):
            log.debug("We are to generate the 'title' and 'id' fields for this class, "
                      "whether or not they are defined in the UML model.")
            if not self.hasAttribute('title'):
                title = XMIAttribute()
                title.id = 'title'
                title.name = 'title'
                title.setTaggedValue('widget:label_msgid', "label_title")
                title.setTaggedValue('widget:i18n_domain', "plone")
                title.setTaggedValue('widget:description_msgid', "help_title")
                title.setTaggedValue('searchable', 'python:True')
                title.setTaggedValue('accessor', 'Title')
                title.setParent(self)
                self.addAttributeDef(title, 0)

            if not self.hasAttribute('id'):
                id = XMIAttribute()
                id.id = 'id'
                id.name = 'id'
                id.setParent(self)
                id.setTaggedValue('widget:label_msgid', "label_short_name")
                id.setTaggedValue('widget:i18n_domain', "plone")
                id.setTaggedValue('widget:description_msgid', "help_short_name")
                self.addAttributeDef(id, 0)

    def isComplex(self):
        return True

    def addAssocFrom(self, a):
        """Adds association originating FROM this class."""
        self.assocsFrom.append(a)

    def addAssocTo(self, a):
        """Adds association pointing AT this class."""
        self.assocsTo.append(a)

    def getFromAssociations(self, aggtypes=['none'], aggtypesTo=['none']):
        """Returns associations that point from this class."""
        # This code doesn't seem to work with below isDependent method.
        log.debug("Finding associations originating at this class...")
        log.debug("Params: aggtypes='%r', aggtypesTo='%r'.",
                  aggtypes, aggtypesTo)
        result = [a for a in self.assocsFrom
                  if a.fromEnd.aggregation in aggtypes
                  and a.toEnd.aggregation in aggtypesTo]
        log.debug("Associations found: %r.", result)
        return result

    def getToAssociations(self, aggtypes=['none'], aggtypesTo=['none']):
        """Returns associations that point at this class."""
        # This code doesn't seem to work with below isDependent method.
        log.debug("Finding associations pointing at this class...")
        log.debug("Params: aggtypes='%r', aggtypesTo='%r'.",
                  aggtypes, aggtypesTo)
        result = [a for a in self.assocsTo
                  if a.fromEnd.aggregation in aggtypes
                  and a.toEnd.aggregation in aggtypesTo]
        log.debug("Associations found: %r.", result)
        return result

    def isDependent(self):
        """Return True if class is only accessible through composition.

        Every object to which only composite associations point
        shouldn't be created independently.

        To refresh the memory: an aggregation is an empty rhomb in
        UML, a composition is a filled rhomb. (Dutch: 'wybertje').
        """

        log.debug("Trying to figure out if the '%s' class is dependent.", self.getName())
        aggs = self.getToAssociations(aggtypes=['aggregate']) or self.getFromAssociations(aggtypesTo=['aggregate'])
        log.debug("Found aggregations that contain us: %r.", aggs)
        comps = self.getToAssociations(aggtypes=['composite']) or self.getFromAssociations(aggtypesTo=['composite'])
        log.debug("Found compositions that contain us: %r.", comps)

        if comps and not aggs:
            log.debug("We *are* part of a composition plus we are "
                      "not part of an aggregation, so we're stuck "
                      "inside whatever it is that 'compositions' us.")
            res = True
        else:
            log.debug("Our placing is not fixed, we're not dependent.")
            res = False
        log.debug("Check, though, if one of the parents is dependent."
                  "If True, count the class as dependent.")
        for p in self.getGenParents():
            if p.isDependent():
                log.debug("Yes, found a parent that is dependent. "
                          "So we are too.")
                res = True
        log.debug("End verdict: dependent = '%s'.", res)
        return res

    def isAbstract(self):
        return self.isabstract

    def getSubtypeNames(self, recursive=0, **kw):
        """Returns the non-intrinsic subtypes names."""
        res = [o.getName() for o in
               self.getAggregatedClasses(recursive=recursive, **kw)]
        return res

    def getAggregatedClasses(self, recursive=0,
                             filter=['class', 'associationclass', 'interface'], **kw):
        """Returns the non-intrinsic subtypes classes."""
        res = [o for o in self.subTypes if not o.isAbstract() ]
        if recursive:
            for sc in self.subTypes:
                res.extend([o for o in sc.getGenChildren(recursive=1)])
        res = [o for o in res if o.__class__.__name__.lower() in
               ['xmi'+f.lower() for f in filter]]
        return res

    def isI18N(self):
        """If at least one method is I18N the class has to be
        treated as I18N.
        """
        for a in self.getAttributeDefs():
            if a.isI18N():
                return True
        return False

    def getPackage(self):
        return self.package

    getParent = getPackage

    def getRootPackage(self):
        return self.getPackage().getRootPackage()

    def isInterface(self):
        return self.isinterface or self.getStereoType() == 'interface'

    def addRealizationChild(self, c):
        self.realizationChildren.append(c)

    def addRealizationParent(self, c):
        self.realizationParents.append(c)

    def addAdaptationChild(self, c):
        self.adaptationChildren.append(c)

    def addAdaptationParent(self, c):
        self.adaptationParents.append(c)

    def getRealizationChildren(self, recursive=0):
        """ Returns the list of realizations of this element
        
        @param recursive: recursively or not
        
        NB: here, recursively does not mean that it will also return the 
        realizations of the realizations of that interface, it rather means that
        it will also return the subclasses of the classes that realize this 
        interface.
        """
        res = [c for c in self.realizationChildren]
        if recursive:
            for r in res:
                res.extend(r.getGenChildren(1))
        return res

    def getRealizationChildrenNames(self, recursive=0):
        """Returns the names of the realization children."""
        return [o.getName() for o in
                self.getRealizationChildren(recursive=recursive)]

    def getRealizationParents(self):
        log.debug("Looking for this class's realization parents...")
        res = self.realizationParents
        log.debug("Realization parents found %r" % res)
        return res

    def getAdaptationParents(self, recursive=0):
        """ Returns the list of classes adapted by this adapter
        
        @param recursive: recursively or not
        
        NB: here, recursively does not mean that it will also return the 
        classes adapted by classes adapted by this adapter element ; it
        rather means that it will also return the subclasses of the classes
        adapted by this adapter element.
        """
        res = [c for c in self.adaptationParents]
        if recursive:
            for r in res:
                res.extend(r.getGenChildren(1))
        return res

    def getAdaptationParentNames(self, recursive=0):
        """Returns the names of the adapters of this element."""
        return [o.getName() for o in
                self.getAdaptationParents(recursive=recursive)]

    def getAdaptationChildren(self):
        log.debug("Looking for the adapters of this class...")
        res = self.adaptationChildren
        log.debug("Adapters found %r" % res)
        return res

    def getQualifiedModulePath(self, ref, pluginRoot='Products',
                               forcePluginRoot=0, includeRoot=1):
        """Returns the qualified name of the class.

        Depending of the reference package 'ref' it generates an absolute
        path or a relative path if the pack(self) is a subpack of 'ref'
        if it belongs to a different root package it even needs a 'Products.'
        """
        package = self.getPackage()
        if package == ref:
            path = package.getPath(includeRoot=includeRoot, parent=ref)
        else:
            if ref and self.package.getProduct() != ref.getProduct() or \
               forcePluginRoot:
                path = package.getPath(includeRoot=1, parent=ref)
                path.insert(0, PseudoElement(name=pluginRoot))
            else:
                path = package.getPath(includeRoot=includeRoot, parent=ref)

        if not self.getPackage().hasStereoType('module'):
            path.append(self)

        return path

    def getQualifiedModuleName(self, ref=None, pluginRoot='Products',
                               forcePluginRoot=0, includeRoot=1):
        path = self.getQualifiedModulePath(ref, pluginRoot=pluginRoot,
                                           forcePluginRoot=forcePluginRoot,
                                           includeRoot=includeRoot)
        res =  '.'.join([p.getModuleName() for p in path if p])
        return res

    def getQualifiedName(self, ref=None, pluginRoot='Products',
                         forcePluginRoot=0, includeRoot=1):
        name = self.getQualifiedModuleName(ref, pluginRoot=pluginRoot,
                                           forcePluginRoot=forcePluginRoot,
                                           includeRoot=includeRoot)
        res = name + '.' + self.getCleanName()
        return res

    def setStateMachine(self, sm):
        self.statemachine = sm

    def getStateMachine(self):
        return self.statemachine


class XMIInterface(XMIClass):
    isinterface = 1


class XMIMethodParameter(XMIElement):
    default = None
    has_default = 0

    def getDefault(self):
        return self.default

    def hasDefault(self):
        return self.has_default

    def findDefault(self):
        defparam = getElementByTagName(self.domElement, XMI.PARAM_DEFAULT, None)
        if defparam:
            default = XMI.getExpressionBody(defparam)
            if default :
                self.default = default
                self.has_default = 1

    def _initFromDOM(self, domElement):
        XMIElement._initFromDOM(self, domElement)
        if domElement:
            self.findDefault()

    def getExpression(self):
        """Returns the param name and param=default expr if a
        default is defined.
        """
        if self.getDefault():
            return "%s=%s" % (self.getName(), self.getDefault())
        else:
            return self.getName()

class XMIMethod (XMIElement):
    params = []

    def findParameters(self):
        self.params = []
        parElements = self.domElement.getElementsByTagName(XMI.METHODPARAMETER)
        for p in parElements:
            self.addParameter(XMIMethodParameter(p))
            log.debug("Params of the method: %r.",
                      self.params)

    def _initFromDOM(self, domElement):
        XMIElement._initFromDOM(self, domElement)
        XMI.calcVisibility(self)
        XMI.calcOwnerScope(self)
        if domElement:
            self.findParameters()

    def getVisibility(self):
        return self.visibility

    def isStatic(self):
        return self.ownerScope == 'classifier'

    def getParams(self):
        return self.params

    def getParamNames(self):
        return [p.getName() for p in self.params]

    def getParamExpressions(self):
        """Rturns the param names or paramname=default for each
        param in a list.
        """
        return [p.getExpression() for p in self.params]

    def addParameter(self, p):
        if p.getName() != 'return':
            self.params.append(p)

    def testmethodName(self):
        """Returns the generated name of test method.

        userCannotAdd => test_userCannotAdd
        user_cannot_add => test_user_cannot_add
        """
        # The olde way was a bit longish. Something like
        # testTestmyclassnameTestfoldercontainssomething().
        # old = 'test%s%s' % (self.getParent().getCleanName().capitalize(),
        #                     self.getCleanName().capitalize())
        # The new version starts with 'test_' with the unmodified name
        # after it.
        name = 'test_%s' % self.getCleanName()
        return name

class XMIAttribute (XMIElement):
    default = None
    has_default = 0

    def getDefault(self):
        return self.default

    def hasDefault(self):
        return self.has_default

    def calcType(self):
        return XMI.calcDatatype(self)

    def findDefault(self):
        initval = getElementByTagName(self.domElement,
                                      XMI.ATTRIBUTE_INIT_VALUE, None)
        if initval:
            default = XMI.getExpressionBody(initval)
            if default :
                self.default = default
                self.has_default = 1

    def _initFromDOM(self, domElement):
        XMIElement._initFromDOM(self, domElement)
        XMI.calcVisibility(self)
        if domElement:
            self.calcType()
            self.findDefault()
            self.mult = XMI.getMultiplicity(domElement, 1, 1)
        else:
            log.debug("There is no domElement, so for instance "
                      "'self.mult' hasn't been set.")

    def isI18N(self):
        """With a stereotype 'i18N' or the taggedValue 'i18n' with a
        true value, an attribute is treated as i18n.
        """
        return self.getStereoType() == 'i18n' or \
               toBoolean(self.getTaggedValue('i18n'))

    def getVisibility(self):
        return self.visibility

    def getMultiplicity(self):
        try:
            return self.mult
        except:
            log.debug("Ouch, self.mult hasn't been set for '%s' (%s).",
                      self.__name__, self)
            return (1, 1) # not sure if its good to have default here (jensens)

    def getLowerBound(self):
        return self.getMultiplicity()[0]

    def getUpperBound(self):
        return self.getMultiplicity()[1]


class XMIAssocEnd (XMIElement):

    def getName(self,ignore_cardinality=0):
        name = str(self.__name__)
        if name:
            return name
        else:
            if self.getTarget():
                res=self.getTarget().getName().lower()
                if self.getUpperBound != 1 and not ignore_cardinality:
                    res+='s'
                return res
            else:
                return self.getId()

    def _initFromDOM(self, el):
        XMIElement._initFromDOM(self, el)
        navigable = 'isNavigable'
        val = el.getAttribute(navigable) 
        if not val:
            val = getAttributeValue(el, el.tagName+'.'+navigable, 0, 0)
        self.isNavigable = toBoolean(val)
        pid = XMI.getAssocEndParticipantId(el)
        if pid:
            self.obj = allObjects[pid]
            self.mult = XMI.getMultiplicity(el)
            self.aggregation = XMI.getAssocEndAggregation(el)
        else:
            log.debug("Association end missing for association end: '%s'.",
                      self.getId())

    def getTarget(self):
        return self.obj

    def getMultiplicity(self):
        try:
            return self.mult
        except:
            log.debug("Ouch, self.mult hasn't been set for '%s' (%s).",
                      self.__name__, self)
            return 1

    def getLowerBound(self):
        return self.getMultiplicity()[0]

    def getUpperBound(self):
        return self.getMultiplicity()[1]

class XMIAssociation (XMIElement):
    fromEnd = None
    toEnd = None

    def getName(self):
        log.debug("Getting name for association...")
        name = str(self.__name__)
        if self.__name__:
            log.debug("self.__name__ is set to '%s', returning it.", name)
            return name
        log.debug("self.__name__ isn't set.")
        if self.fromEnd:
            fromname = self.fromEnd.getName(ignore_cardinality=1)
            log.debug("Getting fromname from the startpoint: '%s'.",
                      fromname)
        else:
            fromname = self.getId()
            log.debug("Getting fromname from our id: '%s'.", fromname)
        if self.toEnd:
            toname = self.toEnd.getName(ignore_cardinality=1)
            log.debug("Getting toname from the endpoint: '%s'.", toname)
        else:
            toname = self.getId()
            log.debug("Getting toname from our id: '%s'.", toname)
        res = '%s_%s' % (fromname, toname)
        log.debug("Combining that fromname and toname to form our "
                  "relation name: '%s'.", res)
        if isinstance(res, basestring):
            res = res.strip().lower()
            log.debug("Making it lowercase for good measure: '%s'.", res)
        return res

    def getInverseName(self):
        log.debug("Getting name for association...")
        name = self.getTaggedValue('inverse_relation_name',None)
        if name:
            log.debug("self.inverse_name is set to '%s', returning it.", name)
            res = name
        else:
            log.debug("self.inverse_name isn't set.")
            if self.fromEnd:
                fromname = self.fromEnd.getName(ignore_cardinality=1)
                log.debug("Getting fromname from the startpoint: '%s'.",
                          fromname)
            else:
                fromname = self.getId()
                log.debug("Getting fromname from our id: '%s'.", fromname)
            if self.toEnd:
                toname = self.toEnd.getName(ignore_cardinality=1)
                log.debug("Getting toname from the endpoint: '%s'.", toname)
            else:
                toname = self.getId()
                log.debug("Getting toname from our id: '%s'.", toname)
            res = '%s_%s' % (toname, fromname)
            log.debug("Combining that fromname and toname to form our "
                      "relation name: '%s'.", res)
            if isinstance(res, basestring):
                res = res.strip().lower()
                log.debug("Making it lowercase for good measure: '%s'.", res)
        return res

    def _initFromDOM(self, domElement=None):
        XMIElement._initFromDOM(self, domElement)
        self.calcEnds()

    def calcEnds(self):
        ends = self.domElement.getElementsByTagName(XMI.ASSOCEND)
        self.fromEnd = XMIAssocEnd(ends[0])
        self.toEnd = XMIAssocEnd(ends[1])
        self.fromEnd.setParent(self)
        self.toEnd.setParent(self)

    def getParent(self):
        if self.fromEnd:
            return self.fromEnd.getTarget()

class XMIAssociationClass (XMIClass, XMIAssociation):
    isAssociationClass = 1

    def _initFromDOM(self, domElement=None):
        XMIClass._initFromDOM(self, domElement)
        self.calcEnds()

class XMIAbstraction(XMIElement):
    pass


class XMIDependency(XMIElement):
    client = None
    supplier = None

    def getSupplier(self):
        return self.supplier

    def getClient(self):
        return self.client

    def _initFromDOM(self, domElement=None):
        XMIElement._initFromDOM(self, domElement)
        self.calcEnds()

    def calcEnds(self):
        client_el = getElementByTagName(self.domElement, XMI.DEP_CLIENT)
        clid = XMI.getIdRef(getSubElement(client_el))
        self.client = self.allObjects[clid]
        supplier_el = getElementByTagName(self.domElement, XMI.DEP_SUPPLIER)
        suppid = XMI.getIdRef(getSubElement(supplier_el))
        self.supplier = self.allObjects[suppid]
        self.client.addClientDependency(self)

    def getParent(self):
        ''' '''
        if self.client:
            return self.client

#-----------------------------------
# Workflow support
#-----------------------------------

class XMIStateMachine(XMIElement):
    
    def __init__(self, *args, **kwargs):        
        self.states = []    
        self.transitions = []
        self.classes = []
        super(XMIStateMachine, self).__init__(self, *args, **kwargs)
        self.setParent(kwargs.get('parent', None))
        log.debug("Created statemachine '%s'.", self.getId())

    def _initFromDOM(self, domElement=None):
        self._buildTransitions()
        self._buildStates()
        self._associateClasses()

    def addState(self, state):
        self.states.append(state)
        state.setParent(self)

    def getStates(self, no_duplicates=None):
        ret = []
        for s in self.states:
            if no_duplicates:
                flag_exists = 0
                for r in ret:
                    if s.getName() == r.getName():
                        flag_exists = 1
                        break
                if flag_exists:
                    continue
            ret.append(s)
        return ret

    def getStateNames(self, no_duplicates=None):
        return [s.getName() for s in
                self.getStates(no_duplicates=no_duplicates) if s.getName()]

    def getCleanStateNames(self, no_duplicates=None):
        return [s.getCleanName() for s in
                self.getStates(no_duplicates=no_duplicates) if s.getName()]


    def _associateClasses(self):
        context = getElementByTagName(self.domElement,
                                      XMI.STATEMACHINE_CONTEXT, None)
        if context:
            clels = getSubElements(context)
            for clel in clels:
                clid = XMI.getIdRef(clel)
                cl = allObjects[clid]
                self.addClass(cl)
        else:
            self.addClass(self.getParent())

    def addTransition(self, transition):
        self.transitions.append(transition)
        transition.setParent(self)

    def getTransitions(self, no_duplicates=None):
        if not no_duplicates:
            return self.transitions
        tran = {}
        for t in self.transitions:
            if not t.getCleanName():
                continue
            if not t.getCleanName() in tran.keys():
                tran.update({t.getCleanName():t})
                log.debug("Added transition '%s' with properties %r.",
                          t.getCleanName(), t.getProps())
                continue
            for tname in tran:
                if t.getCleanName() == tname and t.hasStereoType('primary'):
                    tran.update({tname:t})

        return [tran[tname] for tname in tran]

    def getTransitionNames(self, no_duplicates=None):
        return [t.getName() for t in
                self.getTransitions(no_duplicates=no_duplicates)
                if t.getName()]

    def _buildStates(self):
        log.debug("Building states...")
        sels = getElementsByTagName(self.domElement, XMI.SIMPLESTATE,
                                    recursive=1)
        log.debug("Found %s simple states.", len(sels))
        for sel in sels:
            state = XMIState(sel)
            self.addState(state)

        sels = getElementsByTagName(self.domElement, XMI.PSEUDOSTATE,
                                    recursive=1)
        log.debug("Found %s pseudo states (like initial states).", len(sels))
        for sel in sels:
            state = XMIState(sel)
            if getAttributeValue(sel, XMI.PSEUDOSTATE_KIND, None) == 'initial' \
               or sel.getAttribute('kind') == 'initial':
                log.debug("Initial state: '%s'.", state.getCleanName())
                state.isinitial = 1
            self.addState(state)

        sels = getElementsByTagName(self.domElement, XMI.FINALSTATE,
                                    recursive=1)
        for sel in sels:
            state = XMIState(sel)
            self.addState(state)

    def _buildTransitions(self):
        tels = getElementsByTagName(self.domElement, XMI.TRANSITION,
                                    recursive=1)
        for tel in tels:
            tran = XMIStateTransition(tel)
            self.addTransition(tran)

    def getClasses(self):
        return self.classes

    def getClassNames(self):
        return [cl.getName() for cl in self.getClasses()]

    def addClass(self, cl):
        self.classes.append(cl)
        cl.setStateMachine(self)

    def getInitialState(self):
        states = self.getStates()
        for s in states:
            if s.isInitial():
                return s
        for s in states:
            for k, v in s.getTaggedValues().items():
                # XXX eeek, this is very specific and need to move to generator
                if k == 'initial_state':
                    return s
        return states[0]

    def getAllTransitionActions(self):
        res = []
        for t in self.getTransitions():
            if t.getAction():
                res.append(t.getAction())
        return res

    def getTransitionActionByName(self, name):
        for t in self.getTransitions():
            if t.getAction():
                if t.getAction().getBeforeActionName() == name or \
                   t.getAction().getAfterActionName() == name:
                    return t.getAction()
        return None

    def getAllTransitionActionNames(self, before=True, after=True):
        actionnames = Set()
        actions = self.getAllTransitionActions()
        for action in actions:
            if before and action.getBeforeActionName():
                actionnames.add(action.getBeforeActionName())
            if after and action.getAfterActionName():
                actionnames.add(action.getAfterActionName())
        return list(actionnames)




class XMIStateTransition(XMIElement):
    targetState = None
    sourceState = None
    action = None
    guard = None

    def _initFromDOM(self, domElement=None):
        XMIElement._initFromDOM(self, domElement)
        self.buildEffect()
        self.buildGuard()

    def buildEffect(self):
        el = getElementByTagName(self.domElement, XMI.TRANSITION_EFFECT, None)
        if not el:
            return
        actel = getSubElement(el)
        self.action = XMIAction(actel)
        self.action.setParent(self)

    def buildGuard(self):
        el = getElementByTagName(self.domElement, XMI.TRANSITION_GUARD,
                                 default=None)
        if not el:
            return
        guardel = getSubElement(el)
        self.guard = XMIGuard(guardel)

    def setSourceState(self, state):
        self.sourceState = state

    def getSourceState(self):
        return self.sourceState

    def getSourceStateName(self):
        if self.getSourceState():
            return self.getSourceState().getName()
        else:
            return None

    def setTargetState(self, state):
        self.targetState = state

    def getTargetState(self):
        return self.targetState

    def getTargetStateName(self):
        if self.getTargetState():
            return self.getTargetState().getName()
        else:
            return None

    def getAction(self):
        return self.action

    def getActionName(self):
        if self.action:
            return self.action.getName()

    def getBeforeActionName(self):
        if self.action:
            return self.action.getBeforeActionName()

    def getAfterActionName(self):
        if self.action:
            return self.action.getAfterActionName()

    def getActionExpression(self):
        if self.action:
            return self.action.getExpression()

    def getProps(self):
        result = {}
        d_expr = {
            'guard_permissions': self.getGuardPermissions(),
            'guard_roles': self.getGuardRoles(),
            'guard_expr': self.getGuardExpr(),
        }
        for key, value in d_expr.items():
            guard = value.strip()
            if guard:
                result[key] = guard
        return repr(result)

    def getGuardRoles(self):
        if not self.guard:
            return ''
        geb = self.guard.getExpressionBody()
        for ge in geb.split('|'):
            ge = ge.strip()
            if ge.startswith('guard_roles:'):
                return str(ge[12:]).replace(',',';')
        return ''

    def getGuardPermissions(self):
        if not self.guard:
            return ''
        geb = self.guard.getExpressionBody()
        for ge in geb.split('|'):
            ge = ge.strip()
            if ge.startswith('guard_permissions:'):
                return str(ge[18:])
        return ''

    def getGuardExpr(self):
        if not self.guard:
            return ''
        geb = self.guard.getExpressionBody()
        for ge in geb.split('|'):
            ge = ge.strip()
            if ge.startswith('guard_expr:'):
                return str(ge[11:])
        return ''

    def getTriggerType(self):
        """Returns the Trigger Type, following what is defined by DCWorkflow:
        0: Automatic
        1: User Action (default)
        2: Workflow Method
        """
        trigger_types = {
            'automatic': 'AUTOMATIC',
            'user action': 'USER',
            'workflow method': 'WORKFLOWMETHOD',
            }
        default = 'user action'
        trigger_type = self.getTaggedValue('trigger_type', default)
        trigger_type = trigger_types.get(trigger_type, trigger_type)
        return trigger_type


class XMIAction(XMIElement):
    expression = None
    def _initFromDOM(self, domElement=None):
        XMIElement._initFromDOM(self, domElement)
        self.expression = XMI.getExpressionBody(self.domElement,
                                                tagname=XMI.ACTION_EXPRESSION)

    def getExpressionBody(self):
        return self.expression

    def getSplittedName(self, padding=1):
        """When the name contains a semicolon the name specifies two actions:
        the one before the transition and the one after the transition.
        """
        res = self.getName().split(';')
        if len(res) == 1 and padding:
            return ['', res[0]]
        else:
            return res

    def getBeforeActionName(self):
        return self.getSplittedName()[0]

    def getAfterActionName(self):
        return self.getSplittedName()[1]

    def getUsedActionNames(self):
        """Return just the used action names.

        Used by templates/create_workflow.py, filters out the empty ones.
        """
        result = []
        before = self.getBeforeActionName()
        after = self.getAfterActionName()
        if before:
            result.append(before)
        if after:
            result.append(after)
        return result


class XMIGuard(XMIElement):
    expression = None
    def _initFromDOM(self, domElement=None):
        XMIElement._initFromDOM(self, domElement)
        self.expression = XMI.getExpressionBody(self.domElement,
                                                tagname=XMI.BOOLEAN_EXPRESSION)

    def getExpressionBody(self):
        return self.expression


class XMIState(XMIElement):
    isinitial = 0

    def __init__(self, *args, **kwargs):
        self.incomingTransitions = []
        self.outgoingTransitions = []
        XMIElement.__init__(self, *args, **kwargs)

    def _initFromDOM(self, domElement=None):
        XMIElement._initFromDOM(self, domElement)
        self.associateTransitions()

    def associateTransitions(self):

        vertices = getElementByTagName(self.domElement,
                                       XMI.STATEVERTEX_OUTGOING,
                                       default=None)
        if vertices:
            for vertex in getSubElements(vertices):
                trid = XMI.getIdRef(vertex)
                tran = allObjects[trid]
                self.addOutgoingTransition(tran)

        vertices = getElementByTagName(self.domElement,
                                       XMI.STATEVERTEX_INCOMING,
                                       default=None)
        if vertices:
            for vertex in getSubElements(vertices):
                trid = XMI.getIdRef(vertex)
                tran = allObjects[trid]
                self.addIncomingTransition(tran)

    def addIncomingTransition(self, tran):
        self.incomingTransitions.append(tran)
        tran.setTargetState(self)

    def addOutgoingTransition(self, tran):
        self.outgoingTransitions.append(tran)
        tran.setSourceState(self)

    def getIncomingTransitions(self):
        return self.incomingTransitions

    def getOutgoingTransitions(self):
        return self.outgoingTransitions

    def getTaggedValues(self):
        return self.taggedValues

    def isInitial(self):
        return self.isinitial

    def getDescription(self):
        """Return the description for a state.

        It looks the description at the TGV 'description'.
        """
        return self.getTaggedValue('description', '')

    def getTitle(self, striphtml=0):
        """ Return the title for a state

        The original is in the templates/create_workflow.py:
        <dtml-var "_['sequence-item'].getDocumentation(striphtml=generator.atgenerator.striphtml) or _['sequence-item'].getName()">

        This method mimics that, but also looks at the TGV 'label'
        """
        fromDocumentation = self.getDocumentation(striphtml=striphtml)
        fromTaggedValue = self.getTaggedValue('label', None)
        default = self.getName()
        return fromTaggedValue or fromDocumentation or default

class XMICompositeState(XMIState):
    def __init__(self, *args, **kwargs):
        XMIState.__init__(self, *args, **kwargs)
        XMIStateMachine.init(self)


# Necessary for Poseidon because in Poseidon we cannot assign a name
# to a statemachine, so we have to pull the name of the statemachine
# from the diagram :(
diagrams = {}
diagramsByModel = {}

class XMIDiagram(XMIElement):
    modelElement = None

    def _initFromDOM(self, domElement=None):
        XMIElement._initFromDOM(self, domElement)
        self.buildSemanticBridge()

    def buildSemanticBridge(self):
        ownerel = getElementByTagName(self.domElement, XMI.DIAGRAM_OWNER,
                                      default=None)
        if not ownerel:
            print 'no ownerel'
            return

        model_el = getElementByTagName(ownerel,
                                       XMI.DIAGRAM_SEMANTICMODEL_BRIDGE_ELEMENT,
                                       default=None, recursive=1)
        if not model_el:
            print 'no modelel'
            return

        el = getSubElement(model_el)
        idref = XMI.getIdRef(el)
        self.modelElement = allObjects.get(idref, None)

        # Workaround for the Poseidon problem
        if issubclass(self.modelElement.__class__, XMIStateMachine):
            self.modelElement.setName(self.getName())

    def getModelElementId(self):
        if self.modelElement:
            return self.modelElement.getId()

    def getModelElement(self):
        return self.modelElement

