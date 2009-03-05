# Copyright 2003-2009, Blue Dynamics Alliance - http://bluedynamics.com
# GNU General Public Licence Version 2 or later

from zope.interface import implements
from interfaces import IModelFactory

import logging
from zipfile import ZipFile
from xml.dom import minidom
import zargoparser

log = logging.getLogger('XMIparser')

class ModelFactory(object):
    
    implements(IModelFactory)
    
    def __call__(self,
                 xschemaFileName=None,
                 xschema=None,
                 packages=[],
                 profile_dir=None, **kw):
        global XMI
        profiles_directories = zargoparser.getProfilesDirectories()
        if profile_dir:
            profiles_directories[0:0] = [profile_dir]
        profile_docs = {}
        if profiles_directories:
            log.info("Directories to search for profiles: %s",
                     str(profiles_directories))
    
        log.info("Parsing...")
        if xschemaFileName:
            suff = os.path.splitext(xschemaFileName)[1].lower()
            if suff in ('.zargo', '.zuml', '.zip'):
                log.debug("Opening %s ..." % suff)
                zf = ZipFile(xschemaFileName)
                xmis = [n for n in zf.namelist() \
                        if os.path.splitext(n)[1].lower() in ('.xmi','.xml')]
                assert(len(xmis)==1)
    
                # search for profiles includes in *.zargo zipfile
                profile_files = {}
                profiles = [n for n in zf.namelist() \
                                if os.path.splitext(n)[1].lower() in ('.profile',)]
                if profiles:
                    assert(len(profiles)==1)
                    for fn in zargoparser.getProfileFilenames(zf.read(profiles[0])):
                        found = False
                        for profile_directory in profiles_directories:
                            profile_path = os.path.join(profile_directory, fn)
                            if os.path.exists(profile_path):
                                profile_files[fn] = profile_path
                                found = True
                                break
                        if not found:
                            raise IOError("Profile %s not found" % fn)
                    log.info("Profile files: '%s'" % str(profile_files))
                    for f, content in profile_files.items():
                        profile_docs[f] = minidom.parse(content)
    
                buf = zf.read(xmis[0])
                doc = minidom.parseString(buf)
            elif suff in ('.xmi', '.xml', '.uml'):
                log.debug("Opening %s ..." % suff)
                doc = minidom.parse(xschemaFileName)
            else:
                raise TypeError("Input file not of the following types: "
                                ".xmi, .xml, .uml, .zargo, .zuml, .zip")
        else:
            doc = minidom.parseString(xschema)
    
        try:
            xmi = doc.getElementsByTagName('XMI')[0]
            xmiver = str(xmi.getAttribute('xmi.version'))
            log.debug("XMI version: %s", xmiver)
            if xmiver >= "1.2":
                log.debug("Using xmi 1.2 parser.")
                XMI = XMI1_2(**kw)
            elif xmiver >= "1.1":
                log.debug("Using xmi 1.1 parser.")
                XMI = XMI1_1(**kw)
            else:
                log.debug("Using xmi 1.0 parser.")
                XMI = XMI1_0(**kw)
        except:
            log.debug("No version info found, taking XMI1_0.")
    
        root = buildHierarchy(doc, packages, profile_docs=profile_docs)
        log.debug("Created a root XMI parser.")
    
        return root