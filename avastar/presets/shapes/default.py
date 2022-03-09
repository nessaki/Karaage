import bpy
import karaage
from karaage import shape, util

arm    = util.get_armature(bpy.context.object)

dict={}
shape.resetToDefault(arm)
shape.fromDictionary(arm,dict)
