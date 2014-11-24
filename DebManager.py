#!/usr/bin/env python3
# encoding: utf-8

import apt.debfile
import apt_pkg
import argparse
import glob
import re
import sys
import subprocess
from package import Package

apt_pkg.init_system()


def cmp_deb_version(x, y):
        x = re.findall('_(.*)_', x)
        y = re.findall('_(.*)_', y)
        return apt_pkg.version_compare(x[0], y[0])


def sort_file_list(file_list):
    file_list_tmp = list(file_list)

    for i in range(len(file_list_tmp)):
        index_min = i
        k = 0

        for j in range(i, len(file_list_tmp)):
            l = cmp_deb_version(file_list_tmp[index_min], file_list_tmp[j])
            if l < k:
                index_min = file_list_tmp.index(file_list_tmp[j])
                k = l

        if index_min != i:
            tmp = file_list_tmp[i]
            file_list_tmp[i] = file_list_tmp[index_min]
            file_list_tmp[index_min] = tmp

    return file_list_tmp


def get_dependencies(package_name, dependencies, informations, cache):

    for dependence in dependencies:
        dependence_name = dependence[0][0]
        if dependence_name in informations['required_dep']:
            continue
        else:
            filename = glob.glob("./{}_*.deb".format(dependence_name))
            if len(filename) > 1:
                filename = sort_file_list(filename)
            if len(filename) > 0:
                filename = filename[0]
                package = apt.debfile.DebPackage(filename, cache)
                informations['required_dep'].add(dependence_name)
                get_dependencies(package.pkgname, package.depends, informations, cache)
            else:
                informations['missing_dep'].setdefault(dependence_name, []).append(package_name)
                continue


def download_missing_deps(missing_package, cache, informations):

    if cache.is_virtual_package(missing_package):
        print("Package '" + missing_package + "' is virtual.")
    elif cache.has_key(missing_package):
        uri = cache[missing_package].candidate.uri

        print("Downloading '" + missing_package + "' :")
        subprocess.call(["curl", "-O", "-#", uri])

        filename = uri.split("/")[-1]

        package = apt.debfile.DebPackage(filename, cache)

        informations['required_dep'].add(missing_package)

        for dep in package.depends:
            dep = dep[0][0]
            if dep not in informations['required_dep']:
                download_missing_deps(dep, cache, informations)
    else:
        print("Package '" + missing_package + "' not found in cache.")


def update_deps(cache, informations):
    for dependence_name in informations['required_dep']:
        filename = glob.glob("./{}_*.deb".format(dependence_name))
        if len(filename) > 1:
            filename = sort_file_list(filename)
        if len(filename) > 0:
            filename = filename[0]
            package = apt.debfile.DebPackage(filename, cache)
            if cache.has_key(package.pkgname):
                status = package.compare_to_version_in_cache(use_installed=False)
                if status == 1:
                    uri = cache[package.pkgname].candidate.uri
                    print("Updating '" + package.pkgname + "' :")
                    subprocess.call(["curl", "-O", "-#", uri])
            else:
                print("Package '" + package.pkgname + "' not found in cache.")


def check_if_newer(package, package_list):
    latest_package = None

    for candidate in package_list:
        if candidate.name == package.name:
            if latest_package:
                if apt_pkg.version_compare(candidate.version, latest_package.version):
                    latest_package = candidate
            if apt_pkg.version_compare(candidate.version, package.version):
                latest_package = candidate

    if latest_package is None:
        return False

    return latest_package


def check_and_remove(package_list, cache):
    working_set = set(package_list)
    for package in working_set:
        to_remove = False
        latest = check_if_newer(package, package_list)
        if latest:
            for parent in package.parents:
                for candidate in package_list:
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
                                else:
                                    print("WARNING: Potential old dependencies still required : " + package.name)

        if to_remove:
            print("Removing old dep : " + package.filename)
            subprocess.call(["rm", package.filename])
            package_list.remove(package)


def build_package_list(cache):
    package_list = glob.glob("./*.deb")
    result = set()
    for package in package_list:
        name, version = re.findall('.*/(.*)_(.*)_', package)[0]
        debfile = apt.debfile.DebPackage(package, cache)
        result.add(Package(debfile.pkgname,
                           version,
                           package,
                           dependencies=debfile.depends))
    for package in result:
        for dependency in package.dependencies:
            for candidate in result:
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
                    else:
                            candidate.parents.append((package.name, package.version))

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Repository updater")

    parser.add_argument("deb_package",
                        type=str,
                        help=".deb package.")

    parser.add_argument("-m",
                        "--list-missing",
                        action="store_true",
                        default=False,
                        help="List missing dependencies for the given package.")

    parser.add_argument("-d",
                        "--list-dependencies",
                        action="store_true",
                        default=False,
                        help=("List dependencies present in the repository "
                              "for the given package."))

    parser.add_argument("-a",
                        action="store_true",
                        default=False,
                        help="Print all informations for the given package")

    parser.add_argument("-r",
                        "--raw-output",
                        action="store_true",
                        default=False,
                        help="Create a raw output for dependencies.")

    parser.add_argument("--download-missing",
                        action="store_true",
                        default=False,
                        help="Download all missing dependencies for a given package.")

    parser.add_argument("--update-everything",
                        action="store_true",
                        default=False,
                        help="Update everything in the current directory.")

    arguments = parser.parse_args()

    if arguments.a:
        arguments.list_dependencies = True
        arguments.list_missing = True

    if arguments.raw_output and arguments.list_dependencies and arguments.list_missing:
        sys.exit("Can't raw output both missing and present dependencies in repository.")

    print("Updating apt cache...")
    cache = apt.Cache(rootdir="./cache")

    cache.update()

    cache.open()
    print("DONE!")

    all_packages = build_package_list(cache)

    top_level_packages = set()

    for package in all_packages:
        if len(package.parents) == 0:
            top_level_packages.add(package.filename)

    top_level_packages = sorted(list(top_level_packages))

    informations = dict()
    informations['required_dep'] = set()
    informations['missing_dep'] = dict()

    if arguments.update_everything:
        for debfile in top_level_packages:
            inst = apt.debfile.DebPackage(debfile, cache)
            pkgname = inst.pkgname
            depends = inst.depends
            del inst

            get_dependencies(pkgname, depends, informations, cache)
    else:
        inst = apt.debfile.DebPackage(arguments.deb_package, cache)
        pkgname = inst.pkgname
        depends = inst.depends
        del inst

        get_dependencies(pkgname, depends, informations, cache)

    if arguments.list_dependencies:
        if arguments.raw_output:
            dep_str = ""
            for dep in sorted(list(informations['required_dep'])):
                dep_str += dep + " "
            print(dep_str)
        else:
            print("\n'" + pkgname + "' need the following recursive dependencies :")
            dep_str = "\t"
            for dep in sorted(list(informations['required_dep'])):
                if len(dep_str + dep) > 72:
                    print(dep_str)
                    dep_str = "\t"
                dep_str += dep + " "
            print(dep_str)

    if arguments.list_missing:
        if arguments.raw_output:
            dep_str = ""
            for dep, parents in informations['missing_dep'].items():
                dep_str += dep + " "
            print(dep_str)
        else:
            print("\n#########################################################")
            print("######### MISSING DEPENDENCIES IN REPOSITORY ############")
            print("#########################################################")

            for dep, parents in informations['missing_dep'].items():
                print("'" + dep + "' for package(s) :")
                parent_str = "\t"
                for parent in parents:
                    if len(parent_str + parent) > 72:
                        print(parent_str)
                        parent_str = "\t"
                    parent_str += parent + " "
                print(parent_str)

    if arguments.download_missing or arguments.update_everything:
        update_deps(cache, informations)
        for missing_package in informations['missing_dep']:
            download_missing_deps(missing_package, cache, informations)
        all_packages = build_package_list(cache)
        check_and_remove(all_packages, cache)
