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


import bpy
import karaage
from karaage import shape, util

context = bpy.context
scene = context.scene
armobj = context.object
updateRigProp = scene.UpdateRigProp
sceneProps  = scene.SceneProp

armobj.data.pose_position = 'REST'
updateRigProp.srcRigType = 'MANUELLAB'
updateRigProp.tgtRigType = 'EXTENDED'
updateRigProp.handleTargetMeshSelection = 'DELETE'
updateRigProp.transferJoints = True
armobj.RigProps.JointType = 'PIVOT'
armobj.RigProps.rig_use_bind_pose = True
updateRigProp.sl_bone_ends = True
updateRigProp.sl_bone_rolls = True
updateRigProp.show_offsets = False
updateRigProp.attachSliders = True
updateRigProp.applyRotation = True
updateRigProp.is_male = False
updateRigProp.apply_pose = False
