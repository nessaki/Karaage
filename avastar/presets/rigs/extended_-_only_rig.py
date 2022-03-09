import bpy
import karaage
from karaage import shape, util

sceneProps  = bpy.context.scene.SceneProp
sceneProps.karaageMeshType   = 'NONE'
sceneProps.karaageRigType    = 'EXTENDED'
sceneProps.karaageJointType  = 'PIVOT'
