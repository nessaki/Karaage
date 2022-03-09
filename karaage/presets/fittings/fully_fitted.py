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

deforming_bones = data.get_volume_bones(arm, only_deforming=False) + data.get_base_bones(arm, only_deforming=False) + data.get_extended_bones(arm, only_deforming=False) 
weights.setDeformingBones(arm, deforming_bones, replace=True)
obj.FittingValues.R_FOOT=1.0
obj.FittingValues.R_LOWER_LEG=1.0
obj.FittingValues.R_LOWER_ARM=1.0
obj.FittingValues.PELVIS=1.0
obj.FittingValues.R_CLAVICLE=1.0
obj.FittingValues.L_UPPER_LEG=1.0
obj.FittingValues.L_LOWER_ARM=1.0
obj.FittingValues.L_UPPER_ARM=1.0
obj.FittingValues.NECK=1.0
obj.FittingValues.L_FOOT=1.0
obj.FittingValues.L_LOWER_LEG=1.0
obj.FittingValues.L_HAND=1.0
obj.FittingValues.HEAD=1.0
obj.FittingValues.R_UPPER_ARM=1.0
obj.FittingValues.BELLY=1.0
obj.FittingValues.R_HAND=1.0
obj.FittingValues.R_UPPER_LEG=1.0
obj.FittingValues.L_CLAVICLE=1.0
obj.FittingValues.CHEST=1.0

bone_names = [b.name for b in arm.data.bones if b.use_deform]
weights.removeBoneWeightGroupsFromSelectedBones(obj, True, bone_names) #remove empty groups
weights.add_missing_mirror_groups(context)

arm.ObjectProp.slider_selector=selector if selector != 'NONE' else 'SL'

weights.setUpdateFitting(True)
shape.refresh_shape(arm, obj, graceful=True)
