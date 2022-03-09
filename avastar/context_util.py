#
#
#
#
#
#
#

import bpy, logging
from . import util

log = logging.getLogger('karaage.context')

class set_context:
    def __init__(self, context, obj, mode):

        self.context = context
        self.active = self.context.active_object if context else None
        self.amode = self.active.mode if self.active else None
        self.asel = self.active.select if self.active else None
        
        self.obj = obj
        self.nmode = mode
        self.omode = self.obj.mode if self.obj else None
        self.osel = self.obj.select if self.obj else None

    def __enter__(self):
        if self.active:

            util.ensure_mode_is('OBJECT')

        if self.obj:

            if self.context.scene.objects.active != self.obj:
                self.context.scene.objects.active = self.obj
            util.ensure_mode_is(self.nmode)

        return self.obj

    def __exit__(self, type, value, traceback):
        if type or value or traceback:
            log.error("Exception type: %s" % type )
            log.error("Exception value: %s" % value)
            log.error("traceback: %s" % traceback)
            raise

        if self.obj:

            util.ensure_mode_is(self.omode)
            self.obj.select = self.osel

        if self.active:

            if self.context.scene.objects.active != self.active:
                self.context.scene.objects.active = self.active
            util.ensure_mode_is(self.amode)
            self.active.select=self.asel

        return True
