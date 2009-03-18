# Copyright 2003-2009, BlueDynamics Alliance - http://bluedynamics.com
# GNU General Public License Version 2 or later

import os
import logging
from zipfile import ZipFile
from xml.dom import minidom
from zope.interface import implements
from interfaces import IModelFactory
import zargoparser
import xmiutils
import xmielements
import flavors

log = logging.getLogger('XMIparser')

class ModelFactory(object):
    
    implements(IModelFactory)
      
    def __call__(self, sourcepath):
        log.info("Parsing...")
        self.XMI = None
        profile_docs = {}
        suff = os.path.splitext(sourcepath)[1].lower()
        if suff in ('.xmi', '.xml', '.uml'):
            log.debug("Opening %s ..." % suff)
            doc = minidom.parse(sourcepath)
        elif suff in ('.zargo', '.zuml', '.zip'):
            if suff == '.zargo':
                profiles_directories = zargoparser.getProfilesDirectories()
                if profiles_directories:
                    log.info("Directories to search for profiles: %s",
                             str(profiles_directories))
            log.debug("Opening %s ..." % suff)
            zf = ZipFile(sourcepath)
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
        else:
            raise ValueError("Input file not of the following types: "
                            ".xmi, .xml, .uml, .zargo, .zuml, .zip")
    
        xmi = doc.getElementsByTagName('XMI')[0]
        try:
            xmiver = str(xmi.getAttribute('xmi.version'))
        except:
            xmiver = '1.0'
            log.warn("No version info found, taking XMI1_0.")
        log.debug("Detected XMI version: %s", xmiver)
        if xmiver >= "1.2":
            log.debug("Using xmi 1.2 flavor.")
            self.XMI = flavors.xmi1_2.XMI1_2()
        elif xmiver >= "1.1":
            log.debug("Using xmi 1.1 flavor.")
            self.XMI = flavors.xmi1_1.XMI1_1()
        else:
            log.debug("Using xmi 1.0 flavor.")
            self.XMI = flavors.xmi1_0.XMI1_0()

#        if profile_docs: 
#            for profile_key, profile_doc in profile_docs.items():
#                datatype = self._buildDataTypes(profile_doc, profile=profile_key)
#                self._buildStereoTypes(profile_doc,profile=profile_key)
#        datatypes = self._buildDataTypes(doc) #XXX unused
#        stereotypes = self._buildStereoTypes(doc) #XXX unused
        root = xmielements.XMIModel(doc, self.XMI)
        root.__xmi__ = self.XMI
        log.debug("Created XMI Model.")
        return root
        
    def _buildDataTypes(self, doc, profile=''):
        datatypes = {}
        if profile:
            log.debug("DataType profile: %s", profile)
            getId = lambda e: profile + "#" + str(e.getAttribute('xmi.id'))
        else:
            getId = lambda e: str(e.getAttribute('xmi.id'))
    
        dts = doc.getElementsByTagName(self.XMI.DATATYPE)
        for dt in dts:
            datatypes[getId(dt)] = dt

        classes = [c for c in doc.getElementsByTagName(self.XMI.CLASS)]    
        for dt in classes:
            datatypes[getId(dt)] = dt
    
        interfaces = [c for c in doc.getElementsByTagName(self.XMI.INTERFACE)]
        for dt in interfaces:
            datatypes[getId(dt)] = dt
    
        interfaces = [c for c in doc.getElementsByTagName(self.XMI.ACTOR)]
        for dt in interfaces:
            datatypes[getId(dt)] = dt
    
        prefix = profile + "#" if profile else ''
        self.XMI.collectTagDefinitions(doc, prefix=prefix)
        return datatypes
    
    def _buildStereoTypes(self, doc, profile=''):
        stereotypes = {}
        if profile:
            log.debug("Stereotype profile: %s", profile)
            getId = lambda e: profile + "#" + str(e.getAttribute('xmi.id'))
        else:
            getId = lambda e: str(e.getAttribute('xmi.id'))
        
        sts = doc.getElementsByTagName(self.XMI.STEREOTYPE)
    
        for st in sts:
            id = st.getAttribute('xmi.id')
            if not id:
                continue
            stereotypes[getId(st)] = st
        return stereotypes
    