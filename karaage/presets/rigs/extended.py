import bpy
import karaage
from karaage import shape, util

sceneProps  = bpy.context.scene.SceneProp
sceneProps.karaageMeshType   = 'TRIS'
sceneProps.karaageRigType    = 'EXTENDED'
sceneProps.karaageJointType  = 'PIVOT'
