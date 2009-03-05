# Copyright 2003-2009, Blue Dynamics Alliance - http://bluedynamics.com
# GNU General Public Licence Version 2 or later

import os.path
from xml.dom import minidom

def getProfileFilenames(xml_string):
    doc = minidom.parseString(xml_string)
    filenames = []
    for el in doc.getElementsByTagName('filename'):
        filenames.append(el.childNodes[0].data)
    return filenames

def getProfilesDirectories():
    profiles_directories = []
    argouml_config_filename = os.path.expanduser("~/.argouml/argo.user.properties")
    if os.path.exists(argouml_config_filename):
        try:
            argouml_config = open(argouml_config_filename)
            for line in argouml_config.xreadlines():
                if line.startswith('argo.profiles.directories='):
                    profiles_directories = line[26:].split('*')[:-1]
                    break
        finally:
            argouml_config.close()
    return profiles_directories
