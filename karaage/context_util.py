### Copyright     2011-2013 Magus Freston, Domino Marama, and Gaia Clary
### Copyright     2014-2015 Gaia Clary
### Copyright     2015      Matrice Laville
### Copyright     2021      Machinimatrix
### Copyright     2022      Nessaki
###
### Contains code from Machinimatrix Avastar™ product.
###
### This file is part of Karaage.
###

### The module has been created based on this document:
### A Beginners Guide to Dual-Quaternions:
### http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.407.9047
###

### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


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
