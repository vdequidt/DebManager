#!/usr/bin/env python3
# encoding: utf-8

import apt.debfile
import apt_pkg
import argparse
import glob
import re
import subprocess
from package import Package

apt_pkg.init_system()


class DebManager(object):

    def __init__(self, cache_dir="./cache", deb_dir="./"):

        self.cache = apt.cache.Cache(rootdir=cache_dir)
        self.deb_dir = deb_dir
        self.packages = set()
        self.top_level_packages = set()
        self.status = dict()
        self.status['required_dep'] = set()
        self.status['missing_dep'] = dict()

    def update_cache(self):
        print("Updating apt cache...")

        self.cache.update()
        self.cache.open()

        print("DONE!")

    def build_package_list(self):
        package_list = glob.glob(self.deb_dir + "/*.deb")  # TODO use os.path
        self.packages = set()
        for package in package_list:
            name, version = re.findall('.*/(.*)_(.*)_', package)[0]
            debfile = apt.debfile.DebPackage(package, self.cache)
            self.packages.add(Package(debfile.pkgname,
                                      version,
                                      package,
                                      dependencies=debfile.depends))
        self._refresh_parents()

        self.top_level_packages = set()
        for package in self.packages:
            if len(package.parents) == 0:
                self.top_level_packages.add(package.filename)

        self.top_level_packages = sorted(list(self.top_level_packages))

    def _refresh_parents(self):
        for package in self.packages:
            for dependency in package.dependencies:
                for candidate in self.packages:
                    if candidate.name == dependency[0][0]:
                        if dependency[0][2] == '=':
                            if apt_pkg.version_compare(candidate.version, dependency[0][1]) == 0:
                                candidate.parents.append((package.name, package.version))
                        elif dependency[0][2] == '>=':
                            if apt_pkg.version_compare(candidate.version, dependency[0][1]) >= 0:
                                candidate.parents.append((package.name, package.version))
                        elif dependency[0][2] == '<=':
                            if apt_pkg.version_compare(candidate.version, dependency[0][1]) <= 0:
                                candidate.parents.append((package.name, package.version))
                        elif dependency[0][2] == '':
                            candidate.parents.append((package.name, package.version))

    def update_dependencies(self, filename=None):
        # TODO : feed the update with a file containing packages, and only
        #        download top level packages
        if filename:
            with open(filename, 'r') as f:
                packages_list = f.read().split("\n")
                packages_list.pop()
            self._get_missing_packages(packages_list)
            self.build_package_list()

        packages_to_update = self.top_level_packages

        for deb_filename in packages_to_update:
            debfile = apt.debfile.DebPackage(deb_filename, self.cache)

            self._recursive_update(debfile.depends)

        self._refresh_parents()

    def _recursive_update(self, dependencies):
        packages_list = set()
        for candidate in self.packages:
            packages_list.add(candidate.name)

        for dependency in dependencies:
            # If not present, download and recurse
            if dependency[0][0] not in packages_list:
                filename = self._download_single_deb(dependency[0][0])
                if filename:
                    version = re.findall('.*_(.*)_', filename)[0]
                    debfile = apt.debfile.DebPackage(self.deb_dir + filename, self.cache)
                    self.packages.add(Package(debfile.pkgname,
                                              version,
                                              self.deb_dir + filename,
                                              dependencies=debfile.depends))
                    self._recursive_update(debfile.depends)
            # If present, update and recurse
            # Beware of multiple versions
            else:
                working_set = set()
                latest = None
                for package in self.packages:
                    if package.name == dependency[0][0]:
                        if self.cache.has_key(package.name):
                            working_set.add(package)
                        else:
                            print("Package '" + package.name + "' not found in cache.")
                if len(working_set) > 0:
                    for package in working_set:
                        if latest is None:
                            latest = package
                        else:
                            if apt_pkg.version_compare(package.version, latest.version) > 0:
                                latest = package

                    debfile = apt.debfile.DebPackage(latest.filename, self.cache)
                    status = debfile.compare_to_version_in_cache(use_installed=False)
                    if status == 1:
                        uri = self.cache[latest.name].candidate.uri
                        print("Updating '" + latest.name + "' from " + latest.version + " to " + self.cache[latest.name].candidate.version + " :")
                        subprocess.call(["curl", "-O", "-#", uri])
                        filename = uri.split("/")[-1]
                        updated_debfile = apt.debfile.DebPackage(self.deb_dir + filename, self.cache)
                        self.packages.add(Package(updated_debfile.pkgname,
                                                  self.cache[latest.name].candidate.version,
                                                  self.deb_dir + filename,
                                                  dependencies=updated_debfile.depends))
                        self._recursive_update(updated_debfile.depends)

    def _get_missing_packages(self, package_list):
        deb_list = glob.glob(self.deb_dir + "/*.deb")  # TODO use os.path

        for deb_file in deb_list:
            name, version = re.findall('.*/(.*)_(.*)_', deb_file)[0]
            if name in package_list:
                package_list.remove(name)

        for package in package_list:
            self._download_single_deb(package)

    def _download_single_deb(self, package_name):
        if self.cache.is_virtual_package(package_name):
            print("Package '" + package_name + "' is virtual.")
            deps = self.cache.get_providing_packages(package_name)
            for dep in deps:
                uri = dep.candidate.uri
                print("Downloading '" + dep.name + "' in version " + dep.candidate.version + " for virtual package :")
                subprocess.call(["curl", "-O", "-#", uri])
                filename = uri.split("/")[-1]
                debfile = apt.debfile.DebPackage(filename, self.cache)
                self._recursive_update(debfile.depends)
            return False
        elif self.cache.has_key(package_name):
            uri = self.cache[package_name].candidate.uri

            print("Downloading '" + package_name + "' in version " + self.cache[package_name].candidate.version + " :")

            subprocess.call(["curl", "-O", "-#", uri])

            return uri.split("/")[-1]
        else:
            print("Package '" + package_name + "' not found in cache.")
            return False

    def cleanup_old_packages(self):
        working_set = set(self.packages)
        for package in working_set:
            to_remove = False
            latest = None
            for other_package in working_set:
                if package.name == other_package.name:
                    if latest:
                        if apt_pkg.version_compare(other_package.version, latest.version) > 0:
                            latest = other_package
                    elif apt_pkg.version_compare(other_package.version, package.version) > 0:
                        latest = other_package
            if latest and len(package.parents) == 0:
                to_remove = True
            elif latest:
                for parent in package.parents:
                    for candidate in self.packages:
                        if candidate.name == parent[0] and candidate.version == parent[1]:
                            for parent_dep in candidate.dependencies:
                                if parent_dep[0][0] == package.name:
                                    if parent_dep[0][2] == '=':
                                        if apt_pkg.version_compare(latest.version, parent_dep[0][1]) == 0:
                                            to_remove = True
                                    elif parent_dep[0][2] == '>=':
                                        if apt_pkg.version_compare(latest.version, parent_dep[0][1]) >= 0:
                                            to_remove = True
                                    elif parent_dep[0][2] == '<=':
                                        if apt_pkg.version_compare(latest.version, parent_dep[0][1]) <= 0:
                                            to_remove = True
                                    elif parent_dep[0][2] == '':
                                        to_remove = True
                                    else:
                                        print(package.name + "_" + package.version + " has been kept back because of " + parent[0])

            if to_remove:
                print("Removing old dep : " + package.filename)
                subprocess.call(["rm", package.filename])
                self.packages.remove(package)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Repository updater")

    parser.add_argument("--update-everything",
                        action="store_true",
                        default=False,
                        help="Update everything in the current directory.")

    parser.add_argument("--cleanup",
                        action="store_true",
                        default=False,
                        help="Cleanup old packages in the current directory.")

    parser.add_argument("--basefile",
                        action="store",
                        type=str,
                        help="Update according to a file containing a list of packages.")

    arguments = parser.parse_args()

    dm = DebManager()

    dm.update_cache()

    dm.build_package_list()

    if arguments.basefile:
        dm.update_dependencies(arguments.basefile)
    elif arguments.update_everything:
        dm.update_dependencies()

    if arguments.cleanup:
        dm.cleanup_old_packages()
