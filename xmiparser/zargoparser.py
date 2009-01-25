from xml.dom import minidom

def getProfileFilenames(xml_string):
    doc = minidom.parseString(xml_string)
    filenames = []
    for el in doc.getElementsByTagName('filename'):
        filenames.append(el.childNodes[0].data)
    return filenames
