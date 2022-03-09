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
from karaage import data, util, shape, weights

context = bpy.context
obj     = context.object
arm     = obj.find_armature()

weights.setUpdateFitting(False)
selector = arm.ObjectProp.slider_selector
if selector != 'NONE':
    arm.ObjectProp.slider_selector='NONE'

deforming_bones = data.get_base_bones(arm, only_deforming=False) + data.get_extended_bones(arm, only_deforming=False)    
weights.setDeformingBones(arm, deforming_bones, replace=True)
obj.FittingValues.R_FOOT=0.0
obj.FittingValues.R_LOWER_LEG=0.0
obj.FittingValues.R_LOWER_ARM=0.0
obj.FittingValues.PELVIS=0.0
obj.FittingValues.R_CLAVICLE=0.0
obj.FittingValues.L_UPPER_LEG=0.0
obj.FittingValues.L_LOWER_ARM=0.0
obj.FittingValues.L_UPPER_ARM=0.0
obj.FittingValues.NECK=0.0
obj.FittingValues.L_FOOT=0.0
obj.FittingValues.L_LOWER_LEG=0.0
obj.FittingValues.L_HAND=0.0
obj.FittingValues.HEAD=0.0
obj.FittingValues.R_UPPER_ARM=0.0
obj.FittingValues.BELLY=0.0
obj.FittingValues.R_HAND=0.0
obj.FittingValues.R_UPPER_LEG=0.0
obj.FittingValues.L_CLAVICLE=0.0
obj.FittingValues.CHEST=0.0

bone_names = [b.name for b in arm.data.bones if b.use_deform]
weights.removeBoneWeightGroupsFromSelectedBones(obj, True, bone_names)
weights.add_missing_mirror_groups(context)

arm.ObjectProp.slider_selector=selector if selector != 'NONE' else 'SL'

weights.setUpdateFitting(True)
shape.refresh_shape(arm, obj, graceful=True)
