# Copyright 2003-2009, Blue Dynamics Alliance - http://bluedynamics.com
# GNU General Public Licence Version 2 or later

# Origninal code:
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/107747
# which has the same license as Python (i.e. GPL compatible)

# XXX
# This code might have bugs, note that the implementation in the
# cookbook looks very different now. Maybe we should use another 
# implementation? (moldy)

class odict(dict):
    def __init__(self, mapping=None):
        if mapping is None:
            mapping = dict()
        dict.__init__(self, mapping)
        self._keys = []

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self._keys.remove(key)

    def __setitem__(self, key, item):
        dict.__setitem__(self, key, item)
        if key not in self._keys: self._keys.append(key)

    def __iter__(self):
        return iter(self._keys)

    def clear(self):
        dict.clear(self)
        self._keys = []

    def copy(self):
        newInstance = odict()
        newInstance.update(self)
        return newInstance

    def items(self):
        return zip(self._keys, self.values())

    def keys(self):
        return self._keys[:]

    def popitem(self):
        try:
            key = self._keys[-1]
        except IndexError:
            raise KeyError('dictionary is empty')

        val = self[key]
        del self[key]

        return (key, val)

    def setdefault(self, key, failobj = None):
        dict.setdefault(self, key, failobj)
        if key not in self._keys: self._keys.append(key)

    def update(self, dict):
        for (key, val) in dict.items():
            self[key] = val

    def values(self):
        return map(self.get, self._keys)
