#!/usr/bin/env python3
# encoding: utf-8

from package import Package
import pprint
from math import ceil, floor

class DebStatistics(object):

    def __init__(self, packages, top_level_packages):
        self.packages = packages
        self.top_level_packages = top_level_packages

    def print_top_level_packages(self, raw=False):
        parent_set = set()
        for package in self.packages:
            if package.filename in self.top_level_packages:
                parent_set.add(package)

        if raw:
            for package in sorted(list(parent_set)):
                print(package.name)

        else:
            print("Packages without parents :")
            for package in sorted(list(parent_set)):
                line = ""
                line += package.name + " " + package.version + " " + package.filename
                print(line)

    def print_packages_selection(self, filename = None):
        package_set = set()
        for package in self.packages:
            package_set.add(package.name)

        package_set = sorted(list(package_set))

        if filename:
            fd = open(filename, "w")

        k = 0
        for package in package_set:
            if len(package) > k:
                k = len(package)
        distance = ceil(k/8)
        for package in package_set:
            tab_number = ceil((distance*8-len(package))/8)+1
            line = str(package)
            for i in range(tab_number):
                line += "\t"
            line += "install"
            if filename:
                fd.write(line+"\n")
            else:
                print(line)
        if filename:
            fd.close()
