import bpy
import karaage
from karaage import shape, util

context = bpy.context
scene = context.scene
armobj = context.object
updateRigProp = scene.UpdateRigProp
sceneProps  = scene.SceneProp

armobj.data.pose_position = 'POSE'
updateRigProp.srcRigType = 'SL'
updateRigProp.tgtRigType = 'BASIC'
updateRigProp.handleTargetMeshSelection = 'HIDE'
updateRigProp.transferJoints = True
armobj.RigProps.JointType = 'POS'
armobj.RigProps.rig_use_bind_pose = True
updateRigProp.sl_bone_ends = True
updateRigProp.sl_bone_rolls = True
updateRigProp.show_offsets = False
updateRigProp.attachSliders = True
updateRigProp.applyRotation = True
updateRigProp.is_male = False
updateRigProp.apply_pose = False
