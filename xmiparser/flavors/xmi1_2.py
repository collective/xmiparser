# Copyright 2003-2009, BlueDynamics Alliance - http://bluedynamics.com
# GNU General Public License Version 2 or later

from xmi1_1 import XMI1_1 

class XMI1_2(XMI1_1):
    TAGGED_VALUE_VALUE = "UML:TaggedValue.dataValue"
    # XMI version specific stuff goes there

    def isAssocEndAggregation(self, el):
        # Sig: AFAIK non-folderish items can't be turned into folderish items at run time (e.g. via an adapter)
        # therefore, if an assocEnd ends at a flavor, it should never be considered as an aggregation end
        # unless we know how to let ContentFlavor folderize that item
        isFlavorEnd = False
        if hasattr(el,"hasStereotype"):
            isFlavorEnd = el.hasStereotype('flavor')
        return str(el.getAttribute('aggregation')) in self.aggregates \
               and not isFlavorEnd

    def getAssocEndAggregation(self, el):
        return str(el.getAttribute('aggregation'))

    def getMultiplicity(self, el, multmin=0, multmax=-1):
        min = getElementByTagName(el, self.MULTRANGE, default=None, recursive=1)
        max = getElementByTagName(el, self.MULTRANGE, default=None, recursive=1)
        mult_min = int(min.getAttribute('lower')) if min else multmin
        mult_max = int(max.getAttribute('upper')) if max else multmax
        return (mult_min, mult_max)

    def getTaggedValue(self, el):
        log.debug("Getting tagname/tagvalue pair from tag. "
                  "Looking recursively for that taggedvalue.")
        tdef = getElementByTagName(el, self.TAG_DEFINITION, default=None,
                                   recursive=1)
        if tdef is None:
            # Fix for http://plone.org/products/archgenxml/issues/62
            return None, None 
        # Fetch the name from the global tagDefinitions (weird)
        id = self.getIdRefOrHrefId(tdef)
        tagname = normalize(self.tagDefinitions[id].getAttribute('name'))
        tagvalue = normalize(getAttributeValue(el, self.TAGGED_VALUE_VALUE,
                                               default=None))
        return tagname, tagvalue

    def collectTagDefinitions(self, el, prefix=''):
        tagdefs = el.getElementsByTagName(self.TAG_DEFINITION)
        if self.tagDefinitions is None:
            self.tagDefinitions = {}
        for t in tagdefs:
            if t.hasAttribute('name'):
                self.tagDefinitions[prefix + t.getAttribute('xmi.id')] = t

    def calculateStereoType(self, o):
        # In xmi its weird, because all objects to which a stereotype
        # applies are stored in the stereotype while in xmi 1.2 its opposite

        sts = getElementsByTagName(o.domElement, self.STEREOTYPE_MODELELEMENT,
                                   recursive=0)
        for st in sts:
            strefs = getSubElements(st)
            for stref in strefs:
                id = self.getIdRefOrHrefId(stref)
                if id:
                    st = stereotypes[id]
                    o.addStereoType(self.getName(st).strip())
                    log.debug("Stereotype found: id='%s', name='%s'.",
                              id, self.getName(st))
                else:
                    log.warn("Empty stereotype id='%s' for class '%s'",
                             o.getId(), o.getName())

    def calcClassAbstract(self, o):
        o.isabstract = o.domElement.hasAttribute('isAbstract') and \
                       o.domElement.getAttribute('isAbstract') == 'true'

    def calcVisibility(self, o):
        o.visibility = o.domElement.hasAttribute('visibility') and \
                       o.domElement.getAttribute('visibility')

    def calcOwnerScope(self, o):
        o.ownerScope = o.domElement.hasAttribute('ownerScope') and \
                       o.domElement.getAttribute('ownerScope')

    def calcDatatype(self, att):
        global datatypes
        typeinfos = att.domElement.getElementsByTagName(self.TYPE) + \
                    att.domElement.getElementsByTagName(self.UML2TYPE)
        if len(typeinfos):
            classifiers = [cn for cn in typeinfos[0].childNodes
                           if cn.nodeType == cn.ELEMENT_NODE]
            if len(classifiers):
                typeid = self.getIdRefOrHrefId(classifiers[0])
                try:
                    typeElement = datatypes[typeid]
                except KeyError:
                    raise ValueError, 'datatype %s not defined' % typeid
                att.type = self.getName(typeElement)
                # Collect all datatype names (to prevent pure datatype
                # classes from being generated)
                if att.type not in datatypenames:
                    datatypenames.append(att.type)