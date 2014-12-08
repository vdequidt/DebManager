#!/usr/bin/env python3
# encoding: utf-8

import apt_pkg

apt_pkg.init_system()


class Package(object):

    def __init__(self, name, version, filename, parents=[], dependencies=[]):
        self.name = str(name)
        self.version = str(version)
        self.filename = str(filename)
        self.parents = list(parents)
        self.dependencies = list(dependencies)

    def __key(self):
        return(self.name, self.version)

    def __hash__(self):
        return hash(self.__key())

    def __str__(self):
        return self.name + " : " + self.version

    def __repr__(self):
        return self.name + " : " + self.version + ", " + str(self.parents)

    def __eq__(self, other):
        return self.name == other.name and self.version == other.version

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        if self.name == other.name:
            return apt_pkg.version_compare(self.version, other.version) > 0
        else:
            return self.name.__gt__(other.name)

    def __lt__(self, other):
        if self.name == other.name:
            return apt_pkg.version_compare(self.version, other.version) < 0
        else:
            return self.name.__lt__(other.name)

    def __ge__(self, other):
        if self.name == other.name:
            return apt_pkg.version_compare(self.version, other.version) >= 0
        else:
            return self.name.__ge__(other.name)

    def __le__(self, other):
        if self.name == other.name:
            return apt_pkg.version_compare(self.version, other.version) <= 0
        else:
            return self.name.__le__(other.name)
