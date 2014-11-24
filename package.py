#!/usr/bin/env python3
# encoding: utf-8


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
