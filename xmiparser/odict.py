# Copied from
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/107747
# which has the same license as Python (i.e. GPL compatible)

class odict(dict):
    def __init__(self, dict = None):
        dict.__init__(self, dict)
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
