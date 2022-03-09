import bpy
import karaage
from karaage import shape, util

sceneProps  = bpy.context.scene.SceneProp
sceneProps.karaageMeshType   = 'NONE'
sceneProps.karaageRigType    = 'BASIC'
sceneProps.karaageJointType  = 'PIVOT'
