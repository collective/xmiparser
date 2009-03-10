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

log = logging.getLogger('XMIparser')

class ModelFactory(object):
    
    implements(IModelFactory)
      
    def __call__(self, sourcepath):
        profiles_directories = zargoparser.getProfilesDirectories()
        profile_docs = {}
        if profiles_directories:
            log.info("Directories to search for profiles: %s",
                     str(profiles_directories))
        XMI = None
    
        log.info("Parsing...")
        if sourcepath:
            suff = os.path.splitext(sourcepath)[1].lower()
            if suff in ('.zargo', '.zuml', '.zip'):
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
                self.XMI = XMI1_2(**kw)
            elif xmiver >= "1.1":
                log.debug("Using xmi 1.1 parser.")
                self.XMI = XMI1_1(**kw)
            else:
                log.debug("Using xmi 1.0 parser.")
                self.XMI = XMI1_0(**kw)
        except:
            log.debug("No version info found, taking XMI1_0.")
    
        root = self._buildHierarchy(doc, packages, XMI, 
                                    profile_docs=profile_docs)
        log.debug("Created a root XMI parser.")
        return root
    
    def _buildDataTypes(doc, profile=''):
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
    
        prefix = profile and profile + "#" or ''
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
    
    def _buildHierarchy(self, doc, packagenames, profile_docs=None):
        """Builds Hierarchy out of the doc."""
        self._datatypenames = ['int', 'void', 'string'] #XXX
        if profile_docs: 
            for profile_key, profile_doc in profile_docs.items():
                _buildDataTypes(profile_doc, profile=profile_key)
                _buildStereoTypes(profile_doc,profile=profile_key)
    
        datatypes = self._buildDataTypes(doc)
        stereotypes = self.buildStereoTypes(doc)
        res = XMIModel(doc)
    
        packageElements = doc.getElementsByTagName(self.XMI.PACKAGE)
        if packagenames: #XXX: TODO support for more than one package
            packageElements = doc.getElementsByTagName(self.XMI.PACKAGE)
            for p in packageElements:
                n = self.XMI.getName(p)
                if n in packagenames:
                    doc = p
                    break
    
        res.buildPackages()
        res.buildClassesAndInterfaces()
        res.buildStateMachines()
        res.buildDiagrams()
        res.associateClassesToStateMachines()
    
        for c in res.getClasses(recursive=1):
            if c.getName() in datatypenames and not \
               c.hasStereoType(self.XMI.generate_datatypes) and c.isEmpty():
                c.internalOnly = 1
                log.debug("Internal class (not generated): '%s'.", c.getName())
    
        self.XMI.buildRelations(doc, allObjects)
        self.XMI.buildGeneralizations(doc, allObjects)
        self.XMI.buildRealizations(doc, allObjects)
        self.XMI.buildDependencies(doc, allObjects)
    
        return res
        