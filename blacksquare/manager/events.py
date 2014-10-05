from ..core.events import Event
from ..core.threadlocal import ThreadLocalMixin
from ..config.core import Config
from ..context import ContextTree

class DependenciesTrackerMixin:

    def __init__(self):
        self._dependencies = {}

    def add_patches(self, patches):
        tree = ContextTree.instance()
        for patch in patches:
            deps = patch.get_dependencies()
            if not deps:
                patch.on()
            for dep in deps:
                assert dep not in tree #FIXME turn on if dep is resolved !
                self._dependencies.setdefault(dep, set()).add(patch)

    def remove_dependency(self, name):
        patches = self._dependencies.get(name)
        if not patches:
            return
        tree = ContextTree.instance()
        for patch in patches:
            for dep in patch.get_dependencies():
                if dep not in tree:
                    break
            else:
                patch.on()


import collections

class ManagersStack(DependenciesTrackerMixin, ThreadLocalMixin):

    global_name = 'config.controller'

    StackItem = collections.namedtuple('StackItem', ['manager', 'patches'])

    def __init__(self):
        super(ManagersStack, self).__init__()
        self.managers = [] # stack

    def add_patches(self, patches, mgr=None):
        if not mgr:
            item = self.managers[-1]
            item.patches.extend(patches)
        else:
            item = self.StackItem(mgr, patches) # set?
            self.managers.append(item)
        super(ManagersStack, self).add_patches(patches)

    def manager_exit(self, mgr):
        top = self.managers.pop()
        assert mgr == top.manager
        for patch in top.patches:
            patch.off()


class GlobalPatches(DependenciesTrackerMixin, ThreadLocalMixin):

    global_name = 'config.controller'

    def __init__(self):
        super(GlobalPatches, self).__init__()
        self.patches = []
        self.root_manager = None

    def add_patches(self, patches, mgr=None):
        super(GlobalPatches, self).add_patches(patches)
        self.patches.extend( patches)
        if mgr and not self.root_manager:
            self.root_manager = mgr

    def manager_exit(self, mgr):
        if mgr != self.root_manager:
            return
        for patch in reversed(self.patches):
            patch.off()



class PatchesEnter(Event):
    
    @classmethod
    def handle(cls, patches, manager):
        ctrl = Config.instance().get_controller_class().instance()
        ctrl.add_patches(patches, manager)


class PatchesExit(Event):

    @classmethod
    def handle(cls, manager):
        ctrl = Config.instance().get_controller_class().instance()
        ctrl.manager_exit(manager)
