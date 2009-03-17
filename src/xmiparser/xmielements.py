# Copyright 2003-2009, BlueDynamics Alliance - http://bluedynamics.com
# GNU General Public License Version 2 or later

import os.path
import logging
from sets import Set
from zodict import zodict as odict
from stripogram import html2text
from zope.interface import implements
from xmiparser.utils import mapName
from xmiparser.utils import toBoolean
from xmiparser.utils import normalize
from xmiparser.utils import wrap as doWrap
from xmiparser.utils import clean_trans
from xmiparser.xmiutils import getElementByTagName
from xmiparser.xmiutils import getElementsByTagName
from xmiparser.interfaces import IXMIStateMachineContainer
from xmiparser.interfaces import IXMIElement
from xmiparser.interfaces import IXMIPackage
from xmiparser.interfaces import IXMIModel
from xmiparser.interfaces import IXMIClass
from xmiparser.interfaces import IXMIInterface
from xmiparser.interfaces import IXMIMethodParameter
from xmiparser.interfaces import IXMIMethod
from xmiparser.interfaces import IXMIAttribute
from xmiparser.interfaces import IXMIAssocEnd
from xmiparser.interfaces import IXMIAssociation
from xmiparser.interfaces import IXMIAssociationClass
from xmiparser.interfaces import IXMIAbstraction
from xmiparser.interfaces import IXMIDependency
from xmiparser.interfaces import IXMIStateMachine
from xmiparser.interfaces import IXMIStateTransition
from xmiparser.interfaces import IXMIAction
from xmiparser.interfaces import IXMIGuard
from xmiparser.interfaces import IXMIState
from xmiparser.interfaces import IXMICompositeState
from xmiparser.interfaces import IXMIDiagram
    
log = logging.getLogger('XMIparser')

allObjects = {} # XXX i dont like this concept of a global dict (jensens)

class PseudoElement(object):
    # urgh, needed to pretend a class
    # wtf - why is this needed?
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def getName(self):
        return self.__name__

    def getModuleName(self):
        return self.xminame

class XMIElement(object):
    implements(IXMIElement)
    __parent__ = None
    __name__ = None
    __XMI__ = None
        
    def __init__(self, parent, domElement=None, name='', *args, **kwargs):
        self.domElement = domElement
        self.__name__ = name
        self.__parent__ = parent
        self.id = ''
        self.cleanName = ''
        self.children = []
        self.maxOccurs = 1
        self.isComplex = False
        self.type = 'NoneType'
        self.subTypes = []
        self.attributeDefs = []
        self.operationDefs = []
        self.tgvs = odict()
        self.stereotypes = []
        self.clientDependencies = []
        # Take kwargs as attributes
        self.__dict__.update(kwargs)
        if domElement:
            allObjects[domElement.getAttribute('xmi.id')] = self
            self._initFromDOM()           

    def __str__(self):
        return '<%s %s)>' % (self.__class__.__name__, self.xminame)
    
    __repr__ = __str__
    
    def __iter__(self):
        for child in self.children:
            yield child
    
    @property 
    def XMI(self):
        if self.__XMI__:
            return self.__XMI__
        if self.__parent__:
            return self.__parent__.__XMI__
        raise AttributeError, 'No XMI flavor given' 

    def getParent(self):
        return self.__parent__

    def _parseTaggedValues(self):
        """Gather the tagnames and tagvalues for the element.
        """
        log.debug("Gathering the taggedvalues for element %s.", self.__name__)
        tgvsm = getElementByTagName(self.domElement, self.XMI.TAGGED_VALUE_MODEL,
                                    default=None, recursive=0)
        if tgvsm is None:
            log.debug("Found nothing.")
            return
        tgvs = getElementsByTagName(tgvsm, self.XMI.TAGGED_VALUE, recursive=0)
        for tgv in tgvs:
            try:
                tagname, tagvalue = self.XMI.getTaggedValue(tgv)
                log.debug("Found tag '%s' with value '%s'.", tagname, tagvalue)
                if self.tgvs.has_key(tagname):
                    log.debug("Invoking Poseidon multiline fix for "
                              "tagname '%s'.", tagname)
                    self.tgvs[tagname] += '\n'+tagvalue
                else:
                    self.tgvs[tagname] = tagvalue
            except TypeError, e:
                log.warn("Broken tagged value in id '%s'.",
                         self.XMI.getId(self.domElement))
        log.debug("Found the following tagged values: %r.",
                  self.tgvs)

    def _initFromDOM(self):
        domElement = self.domElement
        if not domElement:
            return 

        self.id = str(domElement.getAttribute('xmi.id'))
        self.__name__ = self.XMI.getName(domElement)
        log.debug("Initializing from DOM: name='%s', id='%s'.",
                  self.__name__, self.id)
        self._parseTaggedValues()
        self._calculateStereotype()
        mult = getElementByTagName(domElement, self.XMI.MULTIPLICITY, None)
        if mult:
            maxNodes = mult.getElementsByTagName(self.XMI.MULT_MAX)
            if maxNodes and len(maxNodes):
                maxNode = maxNodes[0]
                self.maxOccurs = int(getAttributeValue(maxNode))
                if self.maxOccurs == -1:
                    self.maxOccurs = 99999
                log.debug("maxOccurs = '%s'.", self.maxOccurs)
        domElement.xmiElement = self
        self._buildChildren(domElement)

    @property
    def name(self):
        if self.__name__:
            normalize(self.__name__)
        else:
            normalize(self.id)
        return normalize(res)
    
    @property
    def classcategory(self):
        return "%s.%s" % (self.__class__.__module__, self.__class__.__name__)

    def hasAttributeWithTaggedValue(self, tag, value=None):
        """Return True if any attribute has a TGV 'tag'.

        If given, also check for a matching value.
        """
        # XXX nice convinience, but should be moved outside xmiparser
        log.debug("Searching for presence of an attribute with tag '%s'.", tag)
        if value:
            log.debug("But, extra condition, the value should be '%s'.", value)
        attrs = self.getAttributeDefs()
        for attr in attrs:
            if tag in self.tgvs:
                log.debug("Yep, we've found an attribute with that tag.")
                if not value:
                    # We don't have to have a specific value
                    return True
                else:
                    # We need a specific value
                    if attr.tgvs.get(tag, None) == value:
                        return True
                    else:
                        log.debug("But, alas, the value isn't right.")
        log.debug("No, found nothing.")
        return False

    def getDocumentation(self, striphtml=0, wrap=-1):
        """Return formatted documentation string.

        try to use stripogram to remove (e.g. poseidon) HTML-tags, wrap and
        indent text. If no stripogram is present it uses wrap and indent
        from own utils module.

        striphtml(boolean) -- use stripogram html2text to remove html tags

        wrap(integer) -- default: 60, set to 0: do not wrap,
                         all other >0: wrap with this value
        """

        log.debug("Not Implemented: Trying to find documentation for element.")

        # XXX TODO: fetch UML documentation? 
        return ''

        # The rest isn't executed.
        doc = documentation_of_element #todo
        if not doc:
            log.debug("Didn't find a 'documentation'. "
                      "Returning empty string.")
            return ''
        if wrap == -1:
            wrap = 64
        doc = html2text(doc, (), 0, 1000000).strip()
        if wrap:
            log.debug("Wrapping the documenation.")
            doc = doWrap(doc, wrap)
        log.debug("Returning documenation '%r'.",
                  doc)
        return doc

    def getUnmappedCleanName(self):
        return self.unmappedCleanName

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
        return [str(c.getRef()) for c in self.children if c.getRef()]

    def show(self, outfile, level):
        showLevel(outfile, level)
        outfile.write('Name: %s  Type: %s\n' % (self.__name__, self.type))
        showLevel(outfile, level)
        outfile.write('  - Complex: %d  MaxOccurs: %d\n' % \
            (self.isComplex, self.maxOccurs))
        showLevel(outfile, level)
        outfile.write('  - Attrs: %s\n' % self.attrs)
        showLevel(outfile, level)
        outfile.write('  - AttributeDefs: %s\n' % self.attributeDefs)
        for key in self.attributeDefs.keys():
            showLevel(outfile, level + 1)
            outfile.write('key: %s  value: %s\n' % \
                (key, self.attributeDefs[key]))
        for child in self.children:
            child.show(outfile, level + 1)

    def addOperationDefs(self, m):
        if m.xminame:
            self.operationDefs.append(m)

    def getCleanName(self):
        # If there is a namespace, replace it with an underscore.
        if self.xminame:
            self.unmappedCleanName = str(self.xminame).translate(clean_trans)
        else:
            self.unmappedCleanName = ''
        return mapName(self.unmappedCleanName)

    @property
    def isIntrinsicType(self):
        return str(self.type).startswith('xs:')

    def _buildChildren(self, domElement):
        pass

    def getOperationDefs(self, recursive=0):
        log.debug("Getting method definitions (recursive=%s)...", recursive)
        res = [m for m in self.operationDefs]
        log.debug("Our own methods: %r.", res)
        if recursive:
            log.debug("Also looking recursively to our parents...")
            parents = self.getGenParents(recursive=1)
            for p in parents:
                res.extend(p.getOperationDefs())
            log.debug("Our total methods: %r.", res)
        return res

    def _calculateStereotype(self):
        return self.XMI.calculateStereotype(self)

    def hasStereotype(self, stereotypes):
        log.debug("Looking if element has stereotype %r", stereotypes)
        if isinstance(stereotypes, (str, unicode)):
            stereotypes = [stereotypes]
        return bool(Set(stereotypes).intersection(Set(self.stereotypes)))

    def getFullQualifiedName(self):
        return self.xminame

    @property
    def acquirePackage(self):
        """Acquires the package to which this object belongs."""
        if self.package is not None:
            return self.package
        if self.getParent():
            return self.getParent().package
        return None

    def getPath(self):
        return [self.xminame]

    def getModuleName(self, lower=False):
        """Gets the name of the module the class is in."""
        name = self.tgvs.get('module', self.cleanName)
        return name.lower() if lower else name 

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
            res = [r for r in res if r.hasStereotype(dependencyStereotypes)]
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
            res = [r for r in res if r.hasStereotype(targetStereotypes)]

        return res

class StateMachineContainer(object):
    """Mixin to be a statemachine container.
    """
    implements(IXMIStateMachineContainer)
       
    def __init__(self, pa, el):
        self.statemachines = []

    def findStateMachines(self):
        log.debug("Trying to find statemachines...")
        try:
            ownedElement = getElementByTagName(self.domElement,
                                               [XMI.OWNED_ELEMENT,
                                                self.XMI.OWNED_BEHAVIOR],
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
                ownedElement = self.XMI.getOwnedElement(self.domElement)

        if not ownedElement:
            log.debug("Setting ownedElement to self.domElement as fallback.")
            ownedElement = self.domElement
        log.debug("We set the owned element as: %s.", ownedElement)

        statemachines = getElementsByTagName(ownedElement, self.XMI.STATEMACHINE)
        log.debug("Found the following statemachines: %r.", statemachines)
        return statemachines

    def _buildStateMachines(self, recursive=1):
        res = {}
        statemachines = self.findStateMachines()
        for m in statemachines:
            sm = XMIStateMachine(m, parent=self)
            if sm.xminame:
                # Determine the correct product where it belongs
                products = [c.package.getProduct()
                            for c in sm.getClasses()]
                # Associate the WF with the first product
                if products:
                    product = products[0]
                else:
                    products = self
                product.addStateMachine(sm)
                res[sm.xminame] = sm
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
            self.package.getProduct().addStateMachine(sm, reparent=0)

    def getStateMachines(self):
        return self.statemachines

class XMIPackage(StateMachineContainer, XMIElement):
    implements(IXMIPackage)
    project = None
    isroot = 0

    def __init__(self, parent, el):
        self.classes = []
        self.interfaces = []
        self.packages = []
        super(XMIPackage, self).__init__(parent, el)

    def _initFromDOM(self):
        self.parentPackage = None
        super(XMIPackage, self)._initFromDOM()
        self._buildPackages()
        self._buildStateMachines()
        self._buildInterfaces()
        self._buildClasses()
        self.children += self.getClasses()
        self.children += self.getPackages()
        self.children += self.getInterfaces()


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

    def addPackage(self, p):
        self.packages.append(p)

    def getPackages(self, recursive=False):
        res=self.packages

        if recursive:
            res = list(res)
            for p in self.packages:
                res.extend(p.getPackages(recursive=1))

        return res

    def _buildPackages(self):
        packEls = self.XMI.getPackageElements(self.domElement)
        for p in packEls:
            if self.XMI.getName(p) == 'java':
                continue
            package = XMIPackage(self, p)
            self.addPackage(package)
            package.buildPackages()

    def _buildClasses(self):
        ownedElement = self.XMI.getOwnedElement(self.domElement)
        if not ownedElement:
            log.warn("Empty package: '%s'.",
                     self.xminame)
            return

        classes = getElementsByTagName(ownedElement, self.XMI.CLASS) + \
           getElementsByTagName(ownedElement, self.XMI.ASSOCIATION_CLASS)
        for c in classes:
            if c.nodeName == self.XMI.ASSOCIATION_CLASS:
                # maybe it was already instantiated (when building relations)?
                classId = c.getAttribute('xmi.id').strip()
                if allObjects.has_key(classId):
                    xc = allObjects[classId]
                    xc.setPackage(self)
                else:
                    xc = XMIAssociationClass(c, package=self)
            else:
                xc = XMIClass(c, package=self)
            if xc.xminame:
                self.addClass(xc)

        for p in self.getPackages():
            p.buildClasses()

    def _buildInterfaces(self):
        ownedElement = self.XMI.getOwnedElement(self.domElement)
        if not ownedElement:
            log.warn("Empty package: '%s'.",
                     self.xminame)
            return

        classes = getElementsByTagName(ownedElement, self.XMI.INTERFACE)

        for c in classes:
            xc = XMIInterface(c, package=self)
            if xc.xminame:
                self.addInterface(xc)

        for p in self.getPackages():
            p.buildInterfaces()

    def isRoot(self):
        # TBD Handle this through the stereotype registry
        return self.isroot or self.hasStereotype(['product', 'zopeproduct',
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
        return ".".join([p.xminame for p in path])

class XMIModel(XMIPackage):
    implements(IXMIModel)
    isroot = 1
    parent = None
    diagrams = {}
    diagramsByModel = {}

    def __init__(self, doc, XMI):
        self.document = doc
        self.__XMI__ = XMI
        self.content = self.XMI.getContent(doc)
        self.model = self.XMI.getModel(doc)
        super(XMIModel, self).__init__(None, self.model)
        
    def _initFromDOM(self):
        self._buildDiagrams()
        self._associateClassesToStateMachines()
        for c in self.getClasses(recursive=1):
            if c.xminame in ['int', 'void', 'string'] and not \
               c.hasStereotype(self.XMI.generate_datatypes) and c.isEmpty():
                c.internalOnly = 1
                log.debug("Internal class (not generated): '%s'.", c.xminame)
        self.XMI.buildRelations(doc, allObjects)
        self.XMI.buildGeneralizations(doc, allObjects)
        self.XMI.buildRealizations(doc, allObjects)
        self.XMI.buildDependencies(doc, allObjects)

    def findStateMachines(self):
        statemachines = getElementsByTagName(self.content, self.XMI.STATEMACHINE)
        statemachines.extend(getElementsByTagName(self.model, self.XMI.STATEMACHINE))
        log.debug("Found the following state machines: %r.", statemachines)
        ownedElement = self.XMI.getOwnedElement(self.domElement)
        statemachines.extend(getElementsByTagName(ownedElement,
                                                  self.XMI.STATEMACHINE))
        return statemachines

    def _buildDiagrams(self):
        diagram_els = getElementsByTagName(self.content, self.XMI.DIAGRAM)
        for el in diagram_els:
            diagram = XMIDiagram(self, el)
            self.diagrams[diagram.id] = diagram
            self.diagramsByModel[diagram.getModelElementId()] = diagram

    def getAllStateMachines(self):
        res = []
        res.extend(self.getStateMachines())
        for p in self.getPackages():
            res.extend(p.getStateMachines())
        return res

    def _associateClassesToStateMachines(self):
        sms = self.getAllStateMachines()
        smdict = {}
        for sm in sms:
            smdict[sm.xminame] = sm

        for cl in self.getClasses(recursive=1):
            uf = cl.tgvs.get('use_workflow')
            if uf is None:
                continue
            wf = smdict.get(uf)
            if not wf:
                log.debug('associated workflow does not exist: %s' % uf)
                continue
            smdict[uf].addClass(cl)

class XMIClass(XMIElement, StateMachineContainer):
    implements(IXMIClass)
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
        log.debug("Package set to '%s'.", self.package.xminame)
        log.debug("Running Parents's init...")
        super(XMIClass, self).__init__(*args, **kw)
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

    def _initFromDOM(self):
        XMIElement._initFromDOM(self)
        self.XMI.calcClassAbstract(self)
        self.XMI.calcVisibility(self)
        self.XMI.calcOwnerScope(self)
        self.buildStateMachines(recursive=0)
        self.isComplex = True

    def isInternal(self):
        return self.internalOnly

    def isEmpty(self):
        return not self.getOperationDefs() and \
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
        return [a.xminame for a in self.getAttributeDefs()]

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
        return [o.xminame for o in self.getGenChildren(recursive=recursive)]

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
            att = XMIAttribute(parent, el)
            att.setParent(self)
            self.addAttributeDef(att)
        for el in domElement.getElementsByTagName(XMI.METHOD):
            meth = XMIMethod(parent, el)
            meth.setParent(self)
            self.addOperationDefs(meth)

# XXX: this is stuff for the generator!
#        if self.XMI.getGenerationOption('default_field_generation'):
#            log.debug("We are to generate the 'title' and 'id' fields for this class, "
#                      "whether or not they are defined in the UML model.")
#            if not self.hasAttribute('title'):
#                # XXX: EEEEKKKKK
#                title = XMIAttribute()
#                title.id = 'title'
#                title.name = 'title'
#                title.setTaggedValue('widget:label_msgid', "label_title")
#                title.setTaggedValue('widget:i18n_domain', "plone")
#                title.setTaggedValue('widget:description_msgid', "help_title")
#                title.setTaggedValue('searchable', 'python:True')
#                title.setTaggedValue('accessor', 'Title')
#                title.setParent(self)
#                self.addAttributeDef(title, 0)
#
#            if not self.hasAttribute('id'):
#                # XXX: EEEEKKKKK again
#                id = XMIAttribute()
#                id.id = 'id'
#                id.name = 'id'
#                id.setParent(self)
#                id.setTaggedValue('widget:label_msgid', "label_short_name")
#                id.setTaggedValue('widget:i18n_domain', "plone")
#                id.setTaggedValue('widget:description_msgid', "help_short_name")
#                self.addAttributeDef(id, 0)

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

        log.debug("Trying to figure out if the '%s' class is dependent.", self.xminame)
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
        res = [o.xminame for o in
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


    def getPackage(self):
        return self.package

    getParent = getPackage

    def getRootPackage(self):
        return self.package.getRootPackage()

    def isInterface(self):
        return self.isinterface or 'interface' in self.stereotypes

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
        return [o.xminame for o in
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
        return [o.xminame for o in
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
        package = self.package
        if package == ref:
            path = package.getPath(includeRoot=includeRoot, parent=ref)
        else:
            if ref and self.package.getProduct() != ref.getProduct() or \
               forcePluginRoot:
                path = package.getPath(includeRoot=1, parent=ref)
                path.insert(0, PseudoElement(name=pluginRoot))
            else:
                path = package.getPath(includeRoot=includeRoot, parent=ref)

        if not self.package.hasStereotype('module'):
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
    implements(IXMIInterface)
    isinterface = 1

class XMIMethodParameter(XMIElement):
    implements(IXMIMethodParameter)
    default = None
    has_default = 0

    def getDefault(self):
        return self.default

    def hasDefault(self):
        return self.has_default

    def _buildDefault(self):
        defparam = getElementByTagName(self.domElement, self.XMI.PARAM_DEFAULT, None)
        if not defparam:
            return
        default = self.XMI.getExpressionBody(defparam)
        if default:
            self.default = default
            self.has_default = 1

    def _initFromDOM(self, domElement):
        super(XMIMethodParameter, self)._initFromDOM()
        self.buildDefault()

    def getExpression(self):
        """Returns the param name and param=default expr if a
        default is defined.
        """
        if self.getDefault():
            return "%s=%s" % (self.xminame, self.getDefault())
        else:
            return self.xminame

class XMIMethod (XMIElement):
    implements(IXMIMethod)
    params = []

    def _buildParameters(self):
        self.params = []
        parElements = self.domElement.getElementsByTagName(XMI.METHODPARAMETER)
        for p in parElements:
            self.addParameter(XMIMethodParameter(p))
            log.debug("Params of the method: %r.",
                      self.params)

    def _initFromDOM(self):
        super(XMIMethod, self)._initFromDOM()
        self.XMI.calcVisibility(self)
        self.XMI.calcOwnerScope(self)
        self._buildParameters()

    def getVisibility(self):
        return self.visibility

    def isStatic(self):
        return self.ownerScope == 'classifier'

    def getParams(self):
        return self.params

    def getParamNames(self):
        return [p.xminame for p in self.params]

    def getParamExpressions(self):
        """Rturns the param names or paramname=default for each
        param in a list.
        """
        return [p.getExpression() for p in self.params]

    def addParameter(self, p):
        if p.xminame != 'return':
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
    implements(IXMIAttribute)
    default = None
    has_default = 0

    def getDefault(self):
        return self.default

    def hasDefault(self):
        return self.has_default

    def _findDefault(self):
        initval = getElementByTagName(self.domElement,
                                      self.XMI.ATTRIBUTE_INIT_VALUE, None)
        if initval:
            default = self.XMI.getExpressionBody(initval)
            if default :
                self.default = default
                self.has_default = 1

    def _initFromDOM(self):
        super(XMIAttribute, self)._initFromDOM()
        self.XMI.calcVisibility(self)
        self.XMI.calcDatatype(self)
        self._findDefault()
        self.mult = self.XMI.getMultiplicity(domElement, 1, 1)

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
    implements(IXMIAssocEnd)

    def associationEndName(self, ignore_cardinality=0):
        name = str(self.__name__)
        if name:
            return name
        else:
            if self.getTarget():
                res=self.getTarget().xminame.lower()
                if self.getUpperBound != 1 and not ignore_cardinality:
                    res+='s'
                return res
            else:
                return self.id

    def _initFromDOM(self):
        super(XMIAssocEnd, self)._initFromDOM()
        navigable = 'isNavigable'
        val = el.getAttribute(navigable) 
        if not val:
            val = getAttributeValue(el, el.tagName+'.'+navigable, 0, 0)
        self.isNavigable = toBoolean(val)
        pid = self.XMI.getAssocEndParticipantId(el)
        if pid:
            self.obj = allObjects[pid]
            self.mult = self.XMI.getMultiplicity(el)
            self.aggregation = self.XMI.getAssocEndAggregation(el)
        else:
            log.debug("Association end missing for association end: '%s'.",
                      self.id)

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
    implements(IXMIAssociation)
    fromEnd = None
    toEnd = None

    @property
    def xminame(self):
        log.debug("Getting xminame for association...")
        name = str(self.__name__)
        if self.__name__:
            log.debug("self.__name__ is set to '%s', returning it.", name)
            return name
        log.debug("self.__name__ isn't set.")
        if self.fromEnd:
            fromname = self.fromEnd.associationEndName(True)
            log.debug("Getting fromname from the startpoint: '%s'.",
                      fromname)
        else:
            fromname = self.id
            log.debug("Getting fromname from our id: '%s'.", fromname)
        if self.toEnd:
            toname = self.toEnd.associationEndName(True)
            log.debug("Getting toname from the endpoint: '%s'.", toname)
        else:
            toname = self.id
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
        name = self.tgvs.get('inverse_relation_name')
        if name is not None:
            log.debug("self.inverse_name is set to '%s', returning it.", name)
            return name
        log.debug("self.inverse_name isn't set.")
        if self.fromEnd:
            fromname = self.fromEnd.associationEndName(True)
            log.debug("Getting fromname from the startpoint: '%s'.",
                      fromname)
        else:
            fromname = self.id
            log.debug("Getting fromname from our id: '%s'.", fromname)
        if self.toEnd:
            toname = self.toEnd.associationEndName(True)
            log.debug("Getting toname from the endpoint: '%s'.", toname)
        else:
            toname = self.id
            log.debug("Getting toname from our id: '%s'.", toname)
        res = '%s_%s' % (toname, fromname)
        log.debug("Combining that fromname and toname to form our "
                  "relation name: '%s'.", res)
        if isinstance(res, basestring):
            res = res.strip().lower()
            log.debug("Making it lowercase for good measure: '%s'.", res)
        return res

    def _initFromDOM(self):
        super(XMIAssociation, self)._intFromDOM()
        self._buildEnds()

    def _buildEnds(self):
        ends = self.domElement.getElementsByTagName(XMI.ASSOCEND)
        self.fromEnd = XMIAssocEnd(ends[0])
        self.toEnd = XMIAssocEnd(ends[1])
        self.fromEnd.setParent(self)
        self.toEnd.setParent(self)

    def getParent(self):
        # XXX ?
        if self.fromEnd:
            return self.fromEnd.getTarget()

class XMIAssociationClass(XMIClass, XMIAssociation):
    implements(IXMIAssociationClass)
    isAssociationClass = 1

class XMIAbstraction(XMIElement):
    implements(IXMIAbstraction)

class XMIDependency(XMIElement):
    implements(IXMIDependency)
    client = None
    supplier = None

    def getSupplier(self):
        return self.supplier

    def getClient(self):
        return self.client

    def _initFromDOM(self):
        super(XMIDependency, self)._initFromDOM(self)
        self.buildEnds()

    def _buildEnds(self):
        client_el = getElementByTagName(self.domElement, self.XMI.DEP_CLIENT)
        clid = self.XMI.getIdRef(getSubElement(client_el))
        self.client = self.allObjects[clid]
        supplier_el = getElementByTagName(self.domElement, self.XMI.DEP_SUPPLIER)
        suppid = self.XMI.getIdRef(getSubElement(supplier_el))
        self.supplier = self.allObjects[suppid]
        self.client.addClientDependency(self)

    def getParent(self):
        ''' '''
        # XXX ?
        if self.client:
            return self.client

class XMIStateMachine(XMIElement):
    implements(IXMIStateMachine)
    
    def __init__(self, *args, **kwargs):        
        self.states = []    
        self.transitions = []
        self.classes = []
        super(XMIStateMachine, self).__init__(*args, **kwargs)
        self.setParent(kwargs.get('parent', None))
        log.debug("Created statemachine '%s'.", self.id)

    def _initFromDOM(self):
        super(XMIStateMachine, self)._initFromDOM()
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
                    if s.xminame == r.xminame:
                        flag_exists = 1
                        break
                if flag_exists:
                    continue
            ret.append(s)
        return ret

    def getStateNames(self, no_duplicates=None):
        return [s.xminame for s in
                self.getStates(no_duplicates=no_duplicates) if s.xminame]

    def getCleanStateNames(self, no_duplicates=None):
        return [s.getCleanName() for s in
                self.getStates(no_duplicates=no_duplicates) if s.xminame]


    def _associateClasses(self):
        context = getElementByTagName(self.domElement,
                                      self.XMI.STATEMACHINE_CONTEXT, None)
        if context:
            clels = getSubElements(context)
            for clel in clels:
                clid = self.XMI.getIdRef(clel)
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
                if t.getCleanName() == tname and t.hasStereotype('primary'):
                    tran.update({tname:t})

        return [tran[tname] for tname in tran]

    def getTransitionNames(self, no_duplicates=None):
        return [t.xminame for t in
                self.getTransitions(no_duplicates=no_duplicates)
                if t.xminame]

    def _buildStates(self):
        log.debug("Building states...")
        sels = getElementsByTagName(self.domElement, self.XMI.SIMPLESTATE,
                                    recursive=1)
        log.debug("Found %s simple states.", len(sels))
        for sel in sels:
            state = XMIState(sel)
            self.addState(state)

        sels = getElementsByTagName(self.domElement, self.XMI.PSEUDOSTATE,
                                    recursive=1)
        log.debug("Found %s pseudo states (like initial states).", len(sels))
        for sel in sels:
            state = XMIState(sel)
            if getAttributeValue(sel, self.XMI.PSEUDOSTATE_KIND, None) == 'initial' \
               or sel.getAttribute('kind') == 'initial':
                log.debug("Initial state: '%s'.", state.getCleanName())
                state.isinitial = 1
            self.addState(state)

        sels = getElementsByTagName(self.domElement, self.XMI.FINALSTATE,
                                    recursive=1)
        for sel in sels:
            state = XMIState(sel)
            self.addState(state)

    def _buildTransitions(self):
        tels = getElementsByTagName(self.domElement, self.XMI.TRANSITION,
                                    recursive=1)
        for tel in tels:
            tran = XMIStateTransition(tel)
            self.addTransition(tran)

    def getClasses(self):
        return self.classes

    def getClassNames(self):
        return [cl.xminame for cl in self.getClasses()]

    def addClass(self, cl):
        self.classes.append(cl)
        cl.setStateMachine(self)

    def getInitialState(self, use_tgv='initial_state'):
        states = self.getStates()
        for state in states:
            if state.isInitial():
                return state
        for state in states:
            for key, value in state.tgvs.items():
                if key == use_tgv:
                    return state
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
    implements(IXMIStateTransition)
    targetState = None
    sourceState = None
    action = None
    guard = None

    def _initFromDOM(self):
        super(XMIStateTransition, self)._initFromDOM()
        self._buildEffect()
        self._buildGuard()

    def _buildEffect(self):
        el = getElementByTagName(self.domElement, self.XMI.TRANSITION_EFFECT, None)
        if not el:
            return
        actel = getSubElement(el)
        self.action = XMIAction(actel)
        self.action.setParent(self)

    def _buildGuard(self):
        el = getElementByTagName(self.domElement, self.XMI.TRANSITION_GUARD,
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
            return self.getSourceState().xminame
        else:
            return None

    def setTargetState(self, state):
        self.targetState = state

    def getTargetState(self):
        return self.targetState

    def getTargetStateName(self):
        if self.getTargetState():
            return self.getTargetState().xminame
        else:
            return None

    def getAction(self):
        return self.action

    def getActionName(self):
        if self.action:
            return self.action.xminame

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
        trigger_type = self.tgvs.get('trigger_type', default)
        trigger_type = trigger_types.get(trigger_type, trigger_type)
        return trigger_type

class XMIAction(XMIElement):
    implements(IXMIAction)
    expression = None
    
    def _initFromDOM(self):
        super(XMIAction, slef)._initFromDOM()
        self.expression = self.XMI.getExpressionBody(self.domElement,
                                                tagname=XMI.ACTION_EXPRESSION)

    def getExpressionBody(self):
        return self.expression

    def getSplittedName(self, padding=1):
        """When the name contains a semicolon the name specifies two actions:
        the one before the transition and the one after the transition.
        """
        res = self.xminame.split(';')
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
    implements(IXMIGuard)
    expression = None
    
    def _initFromDOM(self):
        super(XMIGuard, self)._initFromDOM()
        self.expression = self.XMI.getExpressionBody(self.domElement,
                                                tagname=XMI.BOOLEAN_EXPRESSION)

    def getExpressionBody(self):
        return self.expression

class XMIState(XMIElement):
    implements(IXMIState)
    isinitial = 0

    def __init__(self, *args, **kwargs):
        self.incomingTransitions = []
        self.outgoingTransitions = []
        super(XMIState, self).__init__(*args, **kwargs)

    def _initFromDOM(self):
        super(XMIState, self)._initFromDOM()
        self._associateTransitions()

    def _associateTransitions(self):

        vertices = getElementByTagName(self.domElement,
                                       self.XMI.STATEVERTEX_OUTGOING,
                                       default=None)
        if vertices:
            for vertex in getSubElements(vertices):
                trid = self.XMI.getIdRef(vertex)
                tran = allObjects[trid]
                self.addOutgoingTransition(tran)

        vertices = getElementByTagName(self.domElement,
                                       self.XMI.STATEVERTEX_INCOMING,
                                       default=None)
        if vertices:
            for vertex in getSubElements(vertices):
                trid = self.XMI.getIdRef(vertex)
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

    def isInitial(self):
        return self.isinitial

    def getDescription(self):
        """Return the description for a state.

        It looks the description at the TGV 'description'.
        """
        return self.tgvs.get('description', '')

    def getTitle(self, striphtml=0):
        """ Return the title for a state

        The original is in the templates/create_workflow.py:
        <dtml-var "_['sequence-item'].getDocumentation(striphtml=generator.atgenerator.striphtml) or _['sequence-item'].xminame">

        This method mimics that, but also looks at the TGV 'label'
        """
        # XXX this is generator specific!! move it away from in xmiparser
        fromDocumentation = self.getDocumentation(striphtml=striphtml)
        fromTaggedValue = self.tgvs.get('label')
        default = self.xminame
        return fromTaggedValue or fromDocumentation or default

class XMICompositeState(XMIState):
    implements(IXMICompositeState)

# Necessary for Poseidon because in Poseidon we cannot assign a name
# to a statemachine, so we have to pull the name of the statemachine
# from the diagram :(
diagrams = {}
diagramsByModel = {}

class XMIDiagram(XMIElement):
    implements(IXMIDiagram)
    modelElement = None

    def _initFromDOM(self):
        super(XMIDiagram, self)._initFromDOM()
        self._buildSemanticBridge()

    def _buildSemanticBridge(self):
        ownerel = getElementByTagName(self.domElement, self.XMI.DIAGRAM_OWNER,
                                      default=None)
        if not ownerel:
            print 'no ownerel'
            return

        model_el = getElementByTagName(ownerel,
                                       self.XMI.DIAGRAM_SEMANTICMODEL_BRIDGE_ELEMENT,
                                       default=None, recursive=1)
        if not model_el:
            print 'no modelel'
            return

        el = getSubElement(model_el)
        idref = self.XMI.getIdRef(el)
        self.modelElement = allObjects.get(idref, None)

        # Workaround for the Poseidon problem
        if issubclass(self.modelElement.__class__, XMIStateMachine):
            self.modelElement.__name__ = self.xminame

    def getModelElementId(self):
        if self.modelElement:
            return self.modelElement.id

    def getModelElement(self):
        return self.modelElement