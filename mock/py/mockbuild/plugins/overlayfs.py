# -*- coding: utf-8 -*-
# This file is part of overlayfs plugin for mock
# Copyright (C) 2018  Zdeněk Žamberský ( https://github.com/zzambers )
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.



# About this plugin:
#
# This plugin implements snapshot functionality using overlayfs. From user
# perspective it works similar to LVM plugin, but unlike LVM plugin there is no
# need for LVM volume. It only needs (base) directory, where internal data are
# stored (layers etc., see lower).
#
# Configuration:
# config_opts['plugin_conf']['root_cache_enable'] = False
# config_opts['plugin_conf']['overlayfs_enable'] = True
# config_opts['plugin_conf']['overlayfs_opts']['base_dir'] = /some/directory
# config_opts['plugin_conf']['overlayfs_opts']['touch_rpmdb'] = False
# config_opts['plugin_conf']['overlayfs_opts']['trace_hooks'] = False
#
# ( Plugin uses postinit snapshot, similary to LVM, root chache is pointless. )
#
# base_dir - directory where all plugin's data are stored. It includes data
#            asociated with snapshots (layers, refs etc., see lower for details)
#            It is further namespaced by configname so the same directory can be
#            used in multiple mock configs without problems.
# touch_rpmdb - automatically "touch" rpmdb files after each mount to copy
#               them to upper layer to overcome rpm/yum issue,
#               when calling them directly in chroot. See:
#                   https://bugzilla.redhat.com/show_bug.cgi?id=1213602
# pylint: disable=line-too-long
#                   https://docs.docker.com/storage/storagedriver/overlayfs-driver/#limitations-on-overlayfs-compatibility
# pylint: enable=line-too-long
#               ( Option is not required when installing using mock --install,
#               issue is work-arounded automatically there)
#               defult: False
# trace_hooks - print info messages about plugin's hooks being called,
#               default: False
#
# plugin's resources asociated with config can be released by:
#     mock -r <config> scrub all



# Technical details:
#
# Overlayfs is special pseudo-filesystem (in kernel), which allows to place
# multiple directories as overlays on each other and combine them to single
# filesystem. It is done by supplying "lower" dir(s) and "upper" dir to
# the mount command. "Lower" dir(s) are read-only and all changes (writes)
# therefore go to the "upper" dir. Special files are used to mark deleted files.
#
# For more details about overlayfs see:
#   https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt
#
# So overlayfs itself does not have notion of snapshots, but snapshots can be
# implemented using overlayfs. This is what this plugin does.
#
# Several levels of abstraction are used to achieve this. These are:
#
# LAYERS ( yes, LAYERS represent single layer of abstraction ... :) )
# - layers represent individual layers (overlays) for overlayfs
# - layer consists of filesystem (actually directory supplied to overlayfs)
#   and metadata.
# - layers are uniquely identified by their layerId, which is currently string
#   with randomly generated UUID
# - Each layer has it's parent layer (with exception of "base" layer).
#   Parent layer is layer, on top of which layer was created and
#   which should be placed immediatly under it, when mounting it using
#   overlayfs. ( used to determine list of layers which should be mounted,
#   using overlayfs )
# - One layer can be parent to multiple layers, but can only have single parent.
# - Layers have reference counter to track how many times are referenced
#   (from other layers and REFs (see lower). When reference counter reaches
#   zero, layer is deleted.
# - Layer can be marked immutable, which means no more changes should be
#   done to it (to it's fs). That is, it is no longer allowed use it as "upper"
#   layer. This is one way change. New layer needs to be created on top of
#   immutable layer, if write access is needed.
#
# REFS
# - these are human readable names (aliases) for layers
# - when REF is created, reference counter of target layer is increased.
#   Reference counter of target layer is decreased when REF is deleted.
#   ( changing target actually means deleting REF and creating new one with
#     the same name)
# - layer may be target of zero or more REFs
# - refs are used to implement SNAPSHOTS (see lower)
# - refs starting with '.' are reserved for internal use (special)
# - special refs are:
#    .base - poits to "base" layer, which is direct or indirect parent of all
#            other layers (it is only layer without parent). This layer is both
#            empty (it's fs contains no files) and immutable.
#    .current - points to "current" layer, which is layer representing "current"
#               snapshot. It is also top-most layer from lower list when mount
#               (using overlayfs) is performed.
#    .upper - points to layer used as "upper", when mount is performed
#             (overlayfs). This layer is where all changes (writes) happen.
#             When .upper layer points to immutable layer ( e.g. after creating
#             snapshot), new layer, which has current .upper layer as parent
#             needs to be created and .upper REF updated to this new layer,
#             prior to mount.
#
# SNAPSHOTS
# - used to implement shapshots in mock
# - snapshots are implemented using REFs
# - snapsot names map directly to refs
# - operations on snapshots also involve operations on special REFs (see higher)
# - when snapshot is made it's layer is made immutable
#
# HOOKS
# - methods actually called by mock
# - they mostly call SNAPSHOTS methods and other internal methods
# - additional locking is performed, to make sure, they are not concurently used
#   in a way, which could lead to corruption of internal file structures.
# - I also tried to make these only methods, which contain mock specific code...
#
# CONCURRENCY / LOCKING STRATEGY
# - improper concurrent use of mock commands ( generally hooks calls ) could
#   cause corruption of internal data structures. Therefore plugin does
#   additional locking to prevent this corruption from happening.
# - locking should enforce following rules:
#   1. Snapshot operations are prevented when when other snapshot operation
#      is currently in progress
#   2. Snapshot oprations are prevented, when buildroot is mounted, be it
#      explicitly (mock --mount) or implicitly ( by mock --init, --shell,
#      --chroot, --install etc.)
#      implicit postinit snapshot is somewhat special case here
#      ( unmount and mount of buildroot is actually done in postinit hook,
#        relying on mock not to allow any other commands operationg
#        on buildroot, when init operation is in progress ).
#   3. Explicit mount fails, if buildroot is currently implicitly mounted by
#      mock command (mock --init, --shell, --chroot, --install etc.) and
#      buildroot will be unmounted after that command finishes
#   4. When buildroot is explicitly mounted other mock operations are not
#      permited until root is explicitly unmounted by mock --umount
#   5. Mount operations are prevented, when one is currently in progress
# - two locks are used to enforce rules listed higher:
#   snapshot lock - prevents concurrent running of snapshot operations
#                 - also prevens snapshot operations when root is mounted and
#                   root to be mounted implicitly and explicitly at the same
#                   time ( because lock is acquired prior to mount and released
#                   after umount )
#   mount lock - prevents running multiple mount operations (and some other
#                related operaions) concurrently. This is because mount
#                operations are actually composed of several operations,
#                so other mount operations must be prevented,
#                when one is already in progress.


import os
import os.path
import shutil
import subprocess
import uuid
import re

requires_api_version = "1.1"

def init(plugins, conf, buildroot):
    OverlayFsPlugin(plugins, conf, buildroot)

class OverlayFsPlugin(object):

    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.configName = buildroot.shared_root_name
        self.pluginBaseDir = conf.get('base_dir')
        if not self.pluginBaseDir:
            raise Exception("base_dir is not configured")
        self.rootDir = buildroot.rootdir
        if not self.rootDir:
            raise Exception("Failed to get root dir")
        self.traceHooks = conf.get('trace_hooks')
        if not self.traceHooks:
            self.traceHooks = False
        self.touchRpmdbEnabled = conf.get('touch_rpmdb')
        if not self.touchRpmdbEnabled:
            self.touchRpmdbEnabled = False
        # variables used to correctly handle explicit mounts
        self.mountHookCalled = False
        self.preinitHookCalled = False
        self.failedMount = False
        plugins.add_hook("make_snapshot", self.hook_make_snapshot)
        plugins.add_hook("remove_snapshot", self.hook_remove_snapshot)
        plugins.add_hook("rollback_to", self.hook_rollback_to)
        plugins.add_hook("list_snapshots", self.hook_list_snapshots)
        plugins.add_hook("mount_root", self.hook_mount_root)
        plugins.add_hook("umount_root", self.hook_umount_root)
        plugins.add_hook("postumount", self.hook_postumount)
        plugins.add_hook("postinit", self.hook_postinit)
        plugins.add_hook("postclean", self.hook_postclean)
        plugins.add_hook("scrub", self.hook_scrub)
        plugins.add_hook("preyum", self.hook_preyum)
        plugins.add_hook("preinit", self.hook_preinit)

    ################
    #    FILES    #
    ################

    # directory where rootfs for current mock config should be mounted
    def getRootDir(self):
        return self.rootDir


    # directory which contains all data asocied with this plugin
    def getPluginBaseDir(self):
        return self.pluginBaseDir

    # directory which contains all data asocied with this intance of plugin
    # ( takes mock config name into account )
    def getPluginInstanceDir(self):
        return os.path.join(self.getPluginBaseDir(), self.configName)


    # directory where layers are stored
    def getLayersDir(self):
        return os.path.join(self.getPluginInstanceDir(), "layers")

    # directory with all data asocied with specific layer
    def getLayerDir(self, layerId):
        return os.path.join(self.getLayersDir(), layerId)

    # file which stores name of parent layer of layer with layerId
    def getLayerParentFile(self, layerId):
        return os.path.join(self.getLayerDir(layerId), "parent")

    # file which acts as referece couner of layer with layerId
    def getLayerRefCounterFile(self, layerId):
        return os.path.join(self.getLayerDir(layerId), "refcounter")

    # directory which contains actual filesystem (layer) mounted using overlayfs
    def getLayerFsDir(self, layerId):
        return os.path.join(self.getLayerDir(layerId), "fs")

    # file to mark layer should be treated as immutable (used for snapshots)
    def getLayerImmutableFlagFile(self, layerId):
        return os.path.join(self.getLayerDir(layerId), "immutable")


    # directory which holds references (human redable names) for layers
    def getRefsDir(self):
        return os.path.join(self.getPluginInstanceDir(), "refs")

    # file which contains layerId of layer referenced by name
    def getRefFile(self, name):
        return os.path.join(self.getRefsDir(), name)


    # directory with lock files
    def getLocksDir(self):
        return os.path.join(self.getPluginInstanceDir(), "locks")

    # lock file for snapshot locking
    def getSnapshotLockFile(self):
        return os.path.join(self.getLocksDir(), "snapshot.lock")

    # lock file for mount locking
    def getMountLockFile(self):
        return os.path.join(self.getLocksDir(), "mount.lock")


    # directory used as workdir for overlayfs
    def getWorkDir(self):
        return os.path.join(self.getPluginInstanceDir(), "workdir")

    def rootMountFlagFile(self):
        return os.path.join(self.getPluginInstanceDir(), ".root-mounted")


    # file operations

    @staticmethod
    def readFile(filename):
        with open(filename) as fileObj:
            value = fileObj.read()
            return value

    @staticmethod
    def writeFile(filename, value):
        with open(filename, "w") as fileObj:
            fileObj.write(value)


    ################
    #    LAYERS    #
    ################

    # ref counter

    def getLayerRefcount(self, layerId):
        layerCounterFile = self.getLayerRefCounterFile(layerId)
        return int(self.readFile(layerCounterFile))

    def setLayerRefCount(self, layerId, count):
        layerCounterFile = self.getLayerRefCounterFile(layerId)
        self.writeFile(layerCounterFile, str(count))

    def refLayer(self, layerId):
        counter = self.getLayerRefcount(layerId)
        counter += 1
        self.setLayerRefCount(layerId, counter)
        return counter

    def unrefLayer(self, layerId):
        counter = self.getLayerRefcount(layerId)
        if counter <= 0:
            # should not happen
            errMsg = "refcounter is already <= 0: {} !".format(layerId)
            raise Exception(errMsg)
        counter -= 1
        self.setLayerRefCount(layerId, counter)
        return counter

    # layer operations

    def layerExists(self, layerId):
        layerDir = self.getLayerDir(layerId)
        return os.path.exists(layerDir)

    @staticmethod
    def isSameLayer(layerId1, layerId2):
        return layerId1 == layerId2


    def getParentLayer(self, layerId):
        layerDir = self.getLayerDir(layerId)
        parentFile = os.path.join(layerDir, "parent")
        if os.path.exists(parentFile):
            return self.readFile(parentFile)
        return None

    def setParentLayer(self, layerId, parentLayerId):
        parentFile = self.getLayerParentFile(layerId)
        self.writeFile(parentFile, parentLayerId)

    def setLayerImmutable(self, layerId):
        if not self.isLayerImmutable(layerId):
            immutableFile = self.getLayerImmutableFlagFile(layerId)
            self.writeFile(immutableFile, "")

    def isLayerImmutable(self, layerId):
        immutableFile = self.getLayerImmutableFlagFile(layerId)
        return os.path.exists(immutableFile)


    def createLayer(self, parentLayerId):
        newLayerId = str(uuid.uuid4())
        if self.layerExists(newLayerId):
            # paranoia... :)
            errMsg = "Layer already exists: {} !".format(newLayerId)
            raise Exception(errMsg)

        # create directory for the new layer
        newLayerDir = self.getLayerDir(newLayerId)
        os.mkdir(newLayerDir)

        # crete reference counter for the new layer and set it to zero
        layerCounterFile = self.getLayerRefCounterFile(newLayerId)
        self.writeFile(layerCounterFile, str(0))

        # create directory containg actual filesystem
        newLayerFsDir = self.getLayerFsDir(newLayerId)
        os.mkdir(newLayerFsDir)

        # all layers hase parent except for bottom most base layer
        if not parentLayerId is None:
            # create file with name of "parent" layer in the new layer
            self.setParentLayer(newLayerId, parentLayerId)
            # increase ref counter of parent layer
            self.refLayer(parentLayerId)
        return newLayerId


    def unrefOrDeleteLayer(self, layerId):
        if not self.layerExists(layerId):
            errMsg = "Layer does not exist: {} !".format(layerId)
            raise Exception(errMsg)
        counter = self.unrefLayer(layerId)
        if not counter > 0:
            parentLayerId = self.getParentLayer(layerId)
            layerDir = self.getLayerDir(layerId)
            shutil.rmtree(layerDir)
            self.unrefOrDeleteLayer(parentLayerId)


    ##############
    #    REFS    #
    ##############

    # special refs

    @staticmethod
    def getBaseLayerRef():
        return ".base"

    @staticmethod
    def getCurrentLayerRef():
        return ".current"

    @staticmethod
    def getUpperLayerRef():
        return ".upper"

    @staticmethod
    def getPostinitLayerRef():
        return "postinit"

    # operations on refs

    def getLayerFromRef(self, name):
        if not self.refExists(name):
            errMsg = "Ref does not exist: {} !".format(name)
            raise Exception(errMsg)
        refFile = self.getRefFile(name)
        return self.readFile(refFile)

    def createRef(self, name, layerId):
        if self.refExists(name):
            errMsg = "Ref already exists: {} !".format(name)
            raise Exception(errMsg)
        refFile = self.getRefFile(name)
        self.writeFile(refFile, layerId)
        self.refLayer(layerId)

    def deleteRef(self, name):
        refFile = self.getRefFile(name)
        layerId = self.getLayerFromRef(name)
        os.remove(refFile)
        self.unrefOrDeleteLayer(layerId)

    def refExists(self, name):
        refFile = self.getRefFile(name)
        return os.path.exists(refFile)

    def createLayerAndRef(self, name, parentLayerId):
        if self.refExists(name):
            errMsg = "Ref already exists: {} !".format(name)
            raise Exception(errMsg)
        newLayerId = self.createLayer(parentLayerId)
        self.createRef(name, newLayerId)
        return newLayerId

    # creates ref if necessary, changes ref if it already exists
    def setLayerRef(self, name, layerId):
        if self.refExists(name):
            currentLayerId = self.getLayerFromRef(name)
            if not self.isSameLayer(currentLayerId, layerId):
                self.deleteRef(name)
                self.createRef(name, layerId)
        else:
            self.createRef(name, layerId)

    def listRefs(self, includeSpecial):
        refsDir = self.getRefsDir()
        allRefsList = os.listdir(refsDir)
        if not includeSpecial:
            refsList = []
            for ref in allRefsList:
                if not ref.startswith( '.' ):
                    refsList.append(ref)
        else:
            refsList = allRefsList
        return refsList


    ###################
    #    SNAPSHOTS    #
    ###################

    # snapshot operations

    def createSnapshot(self, snapshotName):
        upperLayerId = self.getLayerFromRef(self.getUpperLayerRef())
        self.createRef(snapshotName, upperLayerId)
        self.setLayerImmutable(upperLayerId)
        currentLayerRef = self.getCurrentLayerRef()
        self.setLayerRef(currentLayerRef, upperLayerId)

    def restoreSnapshot(self, snapshotName):
        upperLayerRef = self.getUpperLayerRef()
        snapshotLayerId = self.getLayerFromRef(snapshotName)
        self.setLayerRef(upperLayerRef, snapshotLayerId)
        currentLayerRef = self.getCurrentLayerRef()
        self.setLayerRef(currentLayerRef, snapshotLayerId)

    def deleteSnapshot(self, snapshotName):
        self.deleteRef(snapshotName)

    def listSnapshots(self):
        return self.listRefs(False)

    @staticmethod
    def checkSnapshotName(snapshotName):
        snapshotNamePattern = "[A-Za-z0-9_-][A-Za-z0-9_.-]*"
        if not re.match(snapshotNamePattern, snapshotName):
            formatStr = "Invalid snapshot name:  {}, needs to has form of: {} !"
            errMsg = formatStr.format(snapshotName, snapshotNamePattern)
            raise Exception(errMsg)


    #######################
    #    OTHER INTERNAL   #
    #######################

    # create basic directory structure
    def basicInit(self):
        pluginBaseDir = self.getPluginBaseDir()
        if not os.path.exists(pluginBaseDir):
            os.mkdir(pluginBaseDir)
        dataBaseDir = self.getPluginInstanceDir()
        if not os.path.exists(dataBaseDir):
            os.mkdir(dataBaseDir)
        layersDir = self.getLayersDir()
        if not os.path.exists(layersDir):
            os.mkdir(layersDir)
        refsDir = self.getRefsDir()
        if not os.path.exists(refsDir):
            os.mkdir(refsDir)
        locksDir = self.getLocksDir()
        if not os.path.exists(locksDir):
            os.mkdir(locksDir)

    # init basic refs/layers setup (create special layers/refs)
    def initLayers(self):
        baseLayerRef = self.getBaseLayerRef()
        if not self.refExists(baseLayerRef):
            self.createLayerAndRef(baseLayerRef, None)
            self.setLayerImmutable(self.getLayerFromRef(baseLayerRef))
        upperLayerRef = self.getUpperLayerRef()
        if not self.refExists(upperLayerRef):
            self.createRef(upperLayerRef, self.getLayerFromRef(baseLayerRef))
        currentLayerRef = self.getCurrentLayerRef()
        if not self.refExists(currentLayerRef):
            self.createRef(currentLayerRef, self.getLayerFromRef(baseLayerRef))

    # this makes sure nothing is written to snapshot layers
    # ( once snapshot is done it's layer becomes read only )
    def prepareLayersForMount(self):
        upperLayerRef = self.getUpperLayerRef()
        upperLayer = self.getLayerFromRef(upperLayerRef)
        # if upperLayerRef points to layer, which is marked immutable
        # we cannot use that layer as upper layer, we need to create new one
        # which has current upperLayer as parent and set it as upperLayer
        if self.isLayerImmutable(upperLayer):
            newLayerId = self.createLayer(upperLayer)
            self.deleteRef(upperLayerRef)
            self.createRef(upperLayerRef, newLayerId)

    # create list of layer and all its parents
    # (used when mounting it as overlayfs)
    def createLayerList(self, layerId):
        layerList = []
        self.createLayerList2(layerList,layerId)
        return layerList

    def createLayerList2(self, layerList,layerId):
        parentLayerId = self.getParentLayer(layerId)
        layerList.append(layerId)
        if parentLayerId is not None:
            self.createLayerList2(layerList,parentLayerId)

    # mount root: upperLayer (+ its parents) using overlayfs
    def mountRoot(self):
        self.prepareLayersForMount()

        upperLayerRef = self.getUpperLayerRef()
        upperLayerId = self.getLayerFromRef(upperLayerRef)

        lowerTopLayerId = self.getParentLayer(upperLayerId)
        lowerList = self.createLayerList(lowerTopLayerId)

        workDir = self.getWorkDir()
        if os.path.exists(workDir):
            shutil.rmtree(workDir)
        os.mkdir(workDir)

        # make sure kernel has required module loaded
        modprobeCmds = ["modprobe", "overlay"]
        subprocess.check_call(modprobeCmds)

        mountCmds = []
        mountCmds.append("mount")
        mountCmds.append("-t")
        mountCmds.append("overlay")
        mountCmds.append("overlay")

        optionsArg="-olowerdir="

        firstLower=True
        for lowerId in lowerList:
            if not firstLower:
                optionsArg += ":"
            firstLower = False
            optionsArg += self.getLayerFsDir(lowerId)

        optionsArg += ",upperdir=" + self.getLayerFsDir(upperLayerId)
        optionsArg += ",workdir=" + workDir

        mountCmds.append(optionsArg)
        mountCmds.append(self.getRootDir())
        subprocess.check_call(mountCmds)

        self.recordRootMounted(True)


    # unmount root
    def unmountRoot(self):
        if self.isRootMounted():
            umountCmds = []
            umountCmds.append("umount")
            umountCmds.append(self.getRootDir())
            subprocess.check_call(umountCmds)

            self.recordRootMounted(False)
            workDir = self.getWorkDir()
            if os.path.exists(workDir):
                shutil.rmtree(workDir)


    def recordRootMounted(self, mounted):
        rootMountFlagFile = self.rootMountFlagFile()
        if mounted:
            self.writeFile(rootMountFlagFile, "")
        else:
            os.remove(rootMountFlagFile)


    def isRootMounted(self):
        rootMountFlagFile = self.rootMountFlagFile()
        isRootMounted = os.path.exists(rootMountFlagFile)
        return isRootMounted

    # lock on snapshot operations ( used to prevent concurent modification of
    # refs/layers by mock )
    def snapshotLock(self):
        snapshotLockFile = self.getSnapshotLockFile()
        try:
            os.mkdir(snapshotLockFile)
        except OSError:
            raise Exception("Failed to obtain snapshot lock !")

    def snapshotUnlock(self):
        snapshotLockFile = self.getSnapshotLockFile()
        if os.path.exists(snapshotLockFile):
            os.rmdir(snapshotLockFile)

    # lock on mount operations
    def mountLock(self):
        mountLockFile = self.getMountLockFile()
        try:
            os.mkdir(mountLockFile)
        except OSError:
            raise Exception("Failed to obtain mount lock !")

    def mountUnlock(self):
        mountLockFile = self.getMountLockFile()
        os.rmdir(mountLockFile)

    def traceHook(self, name):
        if self.traceHooks:
            debugMsg = "Overalyfs pluin: {}".format(name)
            self.buildroot.root_log.info(debugMsg)

    # touch rpmdb files to make overlayfs copy them to upper layer to overcome
    # yum/rpm problems, due to overlayfs limitations. For more details see
    # documentation of touch_rpmdb option documentation on begining
    # of this file.
    def touchRpmdb(self):
        rpmDbDir = os.path.join(self.rootDir, "var", "lib", "rpm")
        if os.path.exists(rpmDbDir):
            rpmDbFileNames = os.listdir(rpmDbDir)
            for rpmDbFileName in rpmDbFileNames:
                rpmDbFile = os.path.join(rpmDbDir, rpmDbFileName)
                with open(rpmDbFile, "ab") as _rpmDbFileObj:
                    pass

    # Methods needed to implement explicit mount support
    # ( to decide if buildroot should be unmounted at the end )

    def isMountFail(self):
        # mount hook was called but failed
        return self.mountHookCalled and self.failedMount

    def isExplicitMount(self):
        if not self.mountHookCalled:
            # hook was not called at all -> not an explicit mount
            return False
        if self.preinitHookCalled:
            # if preinit hook was called, mount was implicit
            return False
        # othervise mount should be explicit one
        return True

    ###############
    #    HOOKS    #
    ###############

    # These are methods ( hooks ) actually called by mock

    # snapshots

    def hook_make_snapshot(self, name):
        self.traceHook("hook_make_snapshot")
        self.checkSnapshotName(name)
        self.basicInit()
        self.snapshotLock()
        try:
            self.initLayers()
            self.createSnapshot(name)
        finally:
            self.snapshotUnlock()

    def hook_remove_snapshot(self, name):
        self.traceHook("hook_remove_snapshot")
        self.checkSnapshotName(name)
        self.basicInit()
        self.snapshotLock()
        try:
            self.initLayers()
            self.deleteSnapshot(name)
        finally:
            self.snapshotUnlock()

    def hook_rollback_to(self, name):
        self.traceHook("hook_rollback_to")
        self.checkSnapshotName(name)
        self.basicInit()
        self.snapshotLock()
        try:
            self.initLayers()
            self.restoreSnapshot(name)
        finally:
            self.snapshotUnlock()

    def hook_list_snapshots(self):
        self.traceHook("hook_list_snapshots")
        self.basicInit()
        self.snapshotLock()
        try:
            self.initLayers()
            snapshots = self.listSnapshots()
            currentRef = self.getCurrentLayerRef()
            currentLayer = self.getLayerFromRef(currentRef)
            for snapshot in snapshots:
                snapshotLayer = self.getLayerFromRef(snapshot)
                if self.isSameLayer(currentLayer, snapshotLayer):
                    print('* ' + snapshot)
                else:
                    print('  ' + snapshot)
        finally:
            self.snapshotUnlock()

    # mounting

    def hook_mount_root(self):
        self.traceHook("hook_mount_root")
        # mount is considered fail until buildroot successfully mounted
        self.failedMount = True
        self.mountHookCalled = True
        self.basicInit()
        self.mountLock()
        try:
            # prevent snapshot operations (by mock) while root is mounted
            self.snapshotLock()
            self.initLayers()
            self.mountRoot()
            self.failedMount = False
            if self.touchRpmdbEnabled:
                self.touchRpmdb()
        finally:
            self.mountUnlock()

    def hook_umount_root(self):
        self.traceHook("hook_umount_root")
        pluginInstanceDir = self.getPluginInstanceDir()
        # pluginInstance dir exists -> it does not follow scub
        if os.path.exists(pluginInstanceDir):
            self.basicInit()
            self.mountLock()
            try:
                self.buildroot.mounts.umountall()
                self.unmountRoot()
                # again allow snapshot operations (by mock) after unmount
                self.snapshotUnlock()
            finally:
                self.mountUnlock()

    def hook_postumount(self):
        self.traceHook("hook_postumount")
        pluginInstanceDir = self.getPluginInstanceDir()
        # pluginInstance dir exists -> it does not follow scub
        if os.path.exists(pluginInstanceDir):
            self.basicInit()
            self.mountLock()
            try:
                # Do not unmount buildroot if mount was attempted and failed,
                # it is either as result of some error and buildroot should not
                # be mounted or maybe was already explicitly mounted previously,
                # in which case we do not want to unmount it
                if self.isMountFail():
                    return
                # Do not umount buildroot on the end if mount was
                # done explicitly
                if self.isExplicitMount():
                    return
                self.buildroot.mounts.umountall()
                self.unmountRoot()
                # again allow snapshot operations (by mock) after unmount
                self.snapshotUnlock()
            finally:
                self.mountUnlock()

    # mock init / clean / scrub

    # this one is tricky it is called with mounted fiesystems
    # (root + managed mounts), but to do snapshot root cannot be mounted
    def hook_postinit(self):
        self.traceHook("hook_postinit")
        self.basicInit()
        self.mountLock()
        try:
            if self.isRootMounted():
                # we do not acquire snapshot lock here, because fact that root
                # is mounted means it was already acquired by mount_root hook

                postinitSnapshotName = self.getPostinitLayerRef()
                # if postinit snapshot was not created yet...
                if not self.refExists(postinitSnapshotName):
                    # unmount everything, so we can do snapshot
                    self.buildroot.mounts.umountall()
                    self.unmountRoot()
                    # do snapshot
                    self.initLayers()
                    self.createSnapshot(postinitSnapshotName)
                    # mount everything again
                    self.mountRoot()
                    self.buildroot.mounts.mountall_managed()
                    if self.touchRpmdbEnabled:
                        self.touchRpmdb()
        finally:
            self.mountUnlock()

    def hook_postclean(self):
        self.traceHook("hook_postclean")
        pluginInstanceDir = self.getPluginInstanceDir()
        # pluginInstance dir exists -> it does not follow scub
        if os.path.exists(pluginInstanceDir):
            self.basicInit()
            self.snapshotLock()
            try:
                self.initLayers()
                currentSnapshotName = self.getCurrentLayerRef()
                self.restoreSnapshot(currentSnapshotName)
            finally:
                self.snapshotUnlock()

    def hook_scrub(self, what):
        self.traceHook("hook_scrub")
        self.basicInit()
        self.snapshotLock()
        try:
            self.initLayers()
            if what in ("all", "overlayfs"):
                baseSnapshotName = self.getBaseLayerRef()
                self.restoreSnapshot(baseSnapshotName)
                postinitSnapshotName = self.getPostinitLayerRef()
                if self.refExists(postinitSnapshotName):
                    self.deleteSnapshot(postinitSnapshotName)
                for snapshot in self.listSnapshots():
                    self.deleteSnapshot(snapshot)
                pluginInstanceDir = self.getPluginInstanceDir()
                shutil.rmtree(pluginInstanceDir)
        finally:
            self.snapshotUnlock()

    def hook_preyum(self):
        self.traceHook("hook_preyum")
        self.basicInit()
        self.mountLock()
        try:
            if self.isRootMounted():
                self.touchRpmdb()
        finally:
            self.mountUnlock()

    def hook_preinit(self):
        self.traceHook("hook_preinit")
        # used as mechanism to detect implicit mount
        self.preinitHookCalled = True
