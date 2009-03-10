# Copyright 2003-2009, BlueDynamics Alliance - http://bluedynamics.com
# GNU General Public License Version 2 or later

def getSubElements(domElement):
    return [e for e in domElement.childNodes if e.nodeType == e.ELEMENT_NODE]

def getSubElement(domElement, default=_marker, ignoremult=0):
    els = getSubElements(domElement)
    if len(els) > 1 and not ignoremult:
        raise TypeError, 'more than 1 element found'
    try:
        return els[0]
    except IndexError:
        if default == _marker:
            raise
        else:
            return default

def getAttributeValue(domElement, tagName=None, default=_marker, recursive=0, 
                      doReplace=False):
    el = domElement
    if tagName:
        try:
            el = getElementByTagName(domElement, tagName, recursive=recursive)
        except IndexError:
            if default == _marker:
                raise
            else:
                return default
    elif el.hasAttribute('xmi.value'):
        return el.getAttribute('xmi.value')
    elif not el.firstChild and default != _marker:
        return default
    return el.firstChild.nodeValue

def getAttributeOrElement(domElement, name, default=_marker, recursive=0):
    """Tries to get the value from an attribute, if not found, it tries
    to get it from a subelement that has the name {element.name}.{name}.
    """
    val = domElement.getAttribute(name)
    if not val:
        val = getAttributeValue(domElement, domElement.tagName+'.'+name,
                                default, recursive)
    return val

def getElementsByTagName(domElement, tagName, recursive=0):
    """Returns elements by tag name.

    The only difference from the original getElementsByTagName is
    the optional recursive parameter.
    """
    if isinstance(tagName, basestring):
        tagNames = [tagName]
    else:
        tagNames = tagName
    if recursive:
        els = []
        for tag in tagNames:
            els.extend(domElement.getElementsByTagName(tag))
    else:
        els = [el for el in domElement.childNodes
               if str(getattr(el, 'tagName', None)) in tagNames]
    return els

def getElementByTagName(domElement, tagName, default=_marker, recursive=0):
    """Returns a single element by name and throws an error if more
    than one exists.
    """
    els = getElementsByTagName(domElement, tagName, recursive=recursive)
    if len(els) > 1:
        raise TypeError, 'more than 1 element found'
    try:
        return els[0]
    except IndexError:
        if default == _marker:
             raise
        else:
            return default

def hasClassFeatures(domClass):
    return len(domClass.getElementsByTagName(XMI.FEATURE)) or \
                len(domClass.getElementsByTagName(XMI.ATTRIBUTE)) or \
                len(domClass.getElementsByTagName(XMI.METHOD))


#----------------------------------------------------------

