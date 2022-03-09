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

import os, logging, gettext
from math import pi, sin, cos, radians

import bpy
from bpy.props import *
from mathutils import Vector, Matrix
from . import const, rig, data, shape, weights, util, bl_info
from .const  import *
 
LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locale')
translator = gettext.translation('karaage', LOCALE_DIR, fallback=True)
_ = translator.gettext

log = logging.getLogger("karaage.create")

def add_material_for(armature_name, part_name, onlyMainCharacter, type, isUnique):

    type_abb = type[0].lower()
    if type_abb == 'n':
        mat_name="Material"
    else:
        if part_name in ["eyeBallLeftMesh", "eyeBallRightMesh"]:
            mat_name="eyeBalls"
        elif part_name in ["eyelashMesh","headMesh"]:
            mat_name="head"
        elif onlyMainCharacter==True and part_name == "hairMesh":
            return None
        else:
            mat_name= part_name[0:part_name.find("Mesh")]

        prep = "karaage"
        if isUnique == True:
          prep = armature_name
        mat_name = prep + ":mat:" + type_abb+ ':' + mat_name

    try:
        mat = bpy.data.materials[mat_name]
    except:
        mat = bpy.data.materials.new(mat_name)
    return mat

def set_karaage_materials(armat):
    print("Set materials for", armat.name)
    print("New material type is", armat.karaageMaterialProps.type)
    print("unique material   is", armat.karaageMaterialProps.unique)

    util.ensure_karaage_repository_is_loaded()
    parts = util.findKaraageMeshes(armat)
    for name in parts:
        part = parts[name]

        mat = add_material_for(armat.name, name, True, armat.karaageMaterialProps.type, armat.karaageMaterialProps.unique)
        if mat:
            part.active_material= mat
            print ("Set material(", name,")", mat.name)

def add_container(scn, arm_obj, name, hide=True):
    
    container = bpy.data.objects.new(name,None)    
    scn.objects.link(container)
    container.location    = arm_obj.location
    container.parent      = arm_obj
    container.hide        = hide
    container.select      = False
    container.hide_select = hide
    container.hide_render = hide
    return container

def add_eye_constraints(obj, scene, bname, arm_obj):
    bone_location = arm_obj.data.bones[bname].head_local
    active        = scene.objects.active
    cursor        = scene.cursor_location.copy()

    scene.objects.active  = obj
    scene.cursor_location = bone_location

    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    scene.cursor_location = cursor
    scene.objects.active = active

    c = obj.constraints.new("COPY_LOCATION")
    c.target       = arm_obj
    c.subtarget    = bname
    c = obj.constraints.new("COPY_ROTATION")
    c.target       = arm_obj
    c.subtarget    = bname
    c.target_space = 'LOCAL'
    c.use_x=False
    c.use_z=False
    c = obj.constraints.new("COPY_SCALE")
    c.target       = arm_obj
    c.subtarget    = bname

def addGeneratedWeights(context, arm, obj, part, rigType=None):
    if rigType == None:
        rigType = util.get_rig_type()

    if rigType == 'EXTENDED':

        arm_original_mode = util.ensure_mode_is("POSE", object=arm)

        if part in ['upperBodyMesh', 'headMesh']:
            from . import mesh
            mesh.get_extended_weights(context, arm, obj, part, vert_mapping='TOPOLOGY')

def createAvatar(context, name="Avatar", quads=False, use_restpose=False, no_mesh=False, rigType='EXTENDED', jointType='PIVOT', max_param_id=-1, use_welding=True):

    ousermode = util.set_operate_in_user_mode(False)
    
    rigType   = util.get_rig_type(rigType)
    jointType = util.get_joint_type(jointType)

    with_meshes = not no_mesh
    log.info("Create Avatar Name         : %s" % name)
    log.info("Create Avatar Polygon type : %s" % ( 'out mesh' if no_mesh else 'QUADS' if quads else 'TRIS') )
    log.info("Create Avatar Pose         : %s" % ("SL Restpose" if use_restpose else "SL Default Shape") )
    log.info("Create Avatar Rig Type     : %s" % rigType)
    log.info("Create Avatar Joint Type   : %s" % jointType)
    
    util.progress_begin(0,10000)
    progress = 10

    import time
    tic = time.time()

    scn = context.scene

    arm_data = bpy.data.armatures.new(name)
    arm_data.draw_type = 'STICK'
    arm_obj  = bpy.data.objects.new(name, arm_data)    

    scn.objects.link(arm_obj)
    scn.objects.active = arm_obj

    if with_meshes:
        meshes = add_container(scn, arm_obj, name+"_meshes")

    createCustomShapes()
    util.progress_update(progress, False)
    log.info("createAvatar: using rigtype: %s - jointtype: %s" %(rigType, jointType)) 
    SKELETON = data.getSkeletonDefinition(rigType,jointType)

    #
    arm_obj['karaage'] = KARAAGE_RIG_ID
    arm_obj['version'] = bl_info['version']
    arm_obj.RigProps.RigType   = rigType
    arm_obj.RigProps.JointType = jointType
    createArmature(context, arm_obj, arm_data, SKELETON, rigType)
    arm_obj.IKSwitches.Enable_Hands = 'FK'
    util.progress_update(progress, False)

    parts = {}
    if with_meshes:
        tic1 = time.time()
        MESHES = data.loadMeshes(rigType)
        toc = time.time()

        tic1 = time.time()
        shape.createMeshShapes(MESHES)
        util.progress_update(progress, False)
        
        toc = time.time()

        arm_obj.RigProps.Hand_Posture = '0'
        for i in range(0,32):
            arm_obj.data.layers[i] = (i in [B_LAYER_ORIGIN,B_LAYER_DEFORM])
        
        generated = {}
        util.ensure_karaage_repository_is_loaded()

        for mesh in MESHES.values():
            util.progress_update(progress, False)

            name = mesh['name']

            tic1 = time.time()
            obj = createMesh(context, name, mesh)
            parts[name]=obj

            obj["weight"]="locked"
            obj["karaage-mesh"]=1
            obj["mesh_id"]=name

            mat = add_material_for(arm_obj.name, name, True, arm_obj.karaageMaterialProps.type, arm_obj.karaageMaterialProps.unique)
            if mat:
                obj.active_material= mat

            obj.parent = meshes

            if 'skinJoints' in mesh:
                createMeshGroups(obj, mesh)

            for pid, morph in mesh['morphs'].items():
                createShapekey(obj, pid, morph, mesh)
            toc = time.time()

            mod = obj.modifiers.new("Armature", "ARMATURE")
            mod.object                     = arm_obj
            mod.use_bone_envelopes         = False
            mod.use_vertex_groups          = True

            mod.use_deform_preserve_volume = False

            if name in ["hairMesh", "skirtMesh"]:
                obj.hide        = True
                obj.hide_render = True
                obj.select      = False
            else:
                obj.hide        = False
                obj.hide_render = False

            if util.get_rig_type(rigType) == 'EXTENDED':
                if name in ['upperBodyMesh', #For the Hands
                            'headMesh'       #For the Face
                           ]:
                    generated[name] = obj

        for name, obj in generated.items():
            addGeneratedWeights(context, arm_obj, obj, name, rigType)

    else:
        arm_obj.data.show_bone_custom_shapes = False
        arm_obj.data.draw_type = 'STICK'
        arm_obj.show_x_ray     = True

    rig.reset_cache(arm_obj)
    toc = time.time()

    context.scene.objects.active = arm_obj

    DRIVERS = data.loadDrivers(rigType, max_param_id=max_param_id)
    shape.createShapeDrivers(DRIVERS)

    util.progress_update(progress, False)

    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

    shape.resetToRestpose(arm_obj, context)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    shape.adjustSupportRig(context, arm_obj)    
    rig.store_restpose_mats(arm_obj)

    arm_obj['sl_joints'] = {}

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    if not use_restpose:

        shape.resetToDefault(arm_obj, context)
    bpy.ops.object.select_all(action='DESELECT')
    arm_obj.select = True
    context.scene.objects.active = arm_obj

    context.scene.update()
    if with_meshes:
        if quads == True and 'quadify_avatar_mesh' in dir(bpy.ops.sparkles):
            for obj in meshes.children:
                try:
                    bpy.ops.sparkles.quadify_avatar_mesh(mesh_id=obj["mesh_id"], object_name=obj.name)
                except:
                    print("Can not invoke Sparkles quads conversion tool")
                    pass

        if util.get_blender_revision() >= 276200 and use_welding:
            add_welding(parts['headMesh'], parts['upperBodyMesh'])
            add_welding(parts['lowerBodyMesh'], parts['upperBodyMesh'])

    rig.armatureSpineFold(arm_obj)
    util.set_operate_in_user_mode(ousermode)

    return arm_obj

def add_welding(from_obj, to_obj):
    if from_obj and to_obj:
        mod = from_obj.modifiers.new("weld", 'DATA_TRANSFER')
        mod.use_loop_data=True
        mod.data_types_loops = {'CUSTOM_NORMAL'}
        mod.use_max_distance=True
        mod.max_distance=0.01
        mod.object = to_obj

        if util.get_blender_revision() > 278100:

            from_obj.data.auto_smooth_angle = 1.570796
            from_obj.data.use_auto_smooth = True

        print("add_welding from [%s] to [%s]" % (from_obj.name, to_obj.name) )
    
def circle(r=0.5, h=0.5, axis=True, steps=30):
    '''
    Generate the vertices and edges for a circle
    '''

    v = []
    for q in range(0, steps):
        v.append((r*cos(q*2*pi/float(steps)), h, r*sin(q*2*pi/float(steps))))
    e = []
    for i in range(len(v)-1):
        e.append((i,i+1))
    e.append((i+1,0))

    if axis:
        v.append((0,0,0))
        v.append((0,1,0))
        e.append((i+2,i+3))

    return v,e

def createCustomShapes():
    #

    #

    name = "CustomShapes"
    if name in bpy.data.objects:
        customobj = bpy.data.objects[name]
    else:
        customobj = bpy.data.objects.new(name,None)

        customobj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        customobj.hide = True

    name = "CustomShape_Line"
    if name not in bpy.data.objects:
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        edges = [(0, 1)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True

    name = "CustomShape_Origin"
    if name not in bpy.data.objects:
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(-0.435, 0.435, 0.0), (-0.512, 0.342, 0.0), (-0.569, 0.235, 0.0), (-0.604, 0.120, 0.0), (-0.120, 0.604, 0.0), 
                 (-0.235, 0.569, 0.0),  (-0.342, 0.512, 0.0),  (-0.120, 0.788, 0.0), (-0.788, 0.120, 0.0), (-0.243, 0.788, 0.0), 
                 (-0.788, 0.243, 0.0), ( 0.000, 0.973, 0.0), (-0.973, 0.000, 0.0)]
        verts = [(3*v[0], 3*v[1], 3*v[2]) for v in verts]
        edges = [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6), (0, 6), (4, 7), (3, 8), (7, 9), (8, 10), (9, 11), (10, 12)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("Mirror", "MIRROR")
        mod.use_x = True
        mod.use_y = True

    name = "CustomShape_Head"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(-1.89, 1.1, -0.09), (-1.9, 0.8, -0.09), (-1.1, 0.8, -1.8), (0.92, 0.8, -1.8), 
                (1.7, 0.8, -0.09), (1.71, 1.1, -0.09), (1.7, 1.41, -0.09), (0.92, 1.41, -1.8), 
                (-1.1, 1.41, -1.8), (-1.89, 1.41, -0.09)] 
        edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (0, 9)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 2

    name = "CustomShape_Collar"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(1.52, 1.1, 0.0), (1.52, 0.92, 0.0), (0.85, 0.92, 1.44), (-0.85, 0.92, 1.44), 
                (-1.52, 0.92, 0.0), (-1.53, 1.1, 0.0), (-1.52, 1.29, 0.0), (-0.85, 1.29, 1.44), 
                (0.85, 1.29, 1.44), (1.52, 1.29, 0.0)] 
        edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (0, 9)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 2

    name = "CustomShape_COG"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(0.3, 1.54, 0.0), (0.29, 1.66, 0.06), (0.27, 1.54, 0.12), (0.24, 1.66, 0.18), 
        (0.2, 1.54, 0.22), (0.15, 1.66, 0.26), (0.09, 1.54, 0.29), (0.03, 1.66, 0.3), 
        (-0.03, 1.54, 0.3), (-0.09, 1.66, 0.29), (-0.15, 1.54, 0.26), (-0.2, 1.66, 0.22), 
        (-0.24, 1.54, 0.18), (-0.27, 1.66, 0.12), (-0.29, 1.54, 0.06), (-0.3, 1.66, 0.0), 
        (-0.29, 1.54, -0.06), (-0.27, 1.66, -0.12), (-0.24, 1.54, -0.18), (-0.2, 1.66, -0.22), 
        (-0.15, 1.54, -0.26), (-0.09, 1.66, -0.29), (-0.03, 1.54, -0.3), (0.03, 1.66, -0.3), 
        (0.09, 1.54, -0.29), (0.15, 1.66, -0.26), (0.2, 1.54, -0.22), (0.24, 1.66, -0.18), 
        (0.27, 1.54, -0.12), (0.29, 1.66, -0.06), (0.0, 0.0, 0.0), (0.0, 1.62, 0.0), 
        (0.29, 1.58, -0.06), (0.27, 1.7, -0.12), (0.24, 1.58, -0.18), (0.2, 1.7, -0.22), 
        (0.15, 1.58, -0.26), (0.09, 1.7, -0.29), (0.03, 1.58, -0.3), (-0.03, 1.7, -0.3), 
        (-0.09, 1.58, -0.29), (-0.15, 1.7, -0.26), (-0.2, 1.58, -0.22), (-0.24, 1.7, -0.18), 
        (-0.27, 1.58, -0.12), (-0.29, 1.7, -0.06), (-0.3, 1.58, 0.0), (-0.29, 1.7, 0.06), 
        (-0.27, 1.58, 0.12), (-0.24, 1.7, 0.18), (-0.2, 1.58, 0.22), (-0.15, 1.7, 0.26), 
        (-0.09, 1.58, 0.29), (-0.03, 1.7, 0.3), (0.03, 1.58, 0.3), (0.09, 1.7, 0.29), 
        (0.15, 1.58, 0.26), (0.2, 1.7, 0.22), (0.24, 1.58, 0.18), (0.27, 1.7, 0.12), 
        (0.29, 1.58, 0.06), (0.3, 1.7, 0.0), (0.0, 0.69, 0.0), (0.0, 1.53, 0.0)] 
        edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), 
        (10, 11), (11, 12), (12, 13), (13, 14), (14, 15), (15, 16), (16, 17), (17, 18), (18, 19), 
        (19, 20), (20, 21), (21, 22), (22, 23), (23, 24), (24, 25), (25, 26), (26, 27), (27, 28), 
        (28, 29), (0, 29), (32, 61), (32, 33), (33, 34), (34, 35), (35, 36), (36, 37), (37, 38), 
        (38, 39), (39, 40), (40, 41), (41, 42), (42, 43), (43, 44), (44, 45), (45, 46), (46, 47), 
        (47, 48), (48, 49), (49, 50), (50, 51), (51, 52), (52, 53), (53, 54), (54, 55), (55, 56), 
        (56, 57), (57, 58), (58, 59), (59, 60), (60, 61), (30, 62), (31, 63), (62, 63)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 2

    name = "CustomShape_Circle01"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts, edges = circle(r=0.1)
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True

    name = "CustomShape_Circle02"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.rotation_euler=(1.5708, 0, 0)

        obj.parent = customobj

        verts, edges = circle(r=0.2)
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True

    name = "CustomShape_Circle03"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts, edges = circle(r=0.3)
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True

    name = "CustomShape_Circle05"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts, edges = circle(r=0.5)
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True

    name = "CustomShape_Circle10"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts, edges = circle(r=1.0)
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True

    name = "CustomShape_Torso"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts, edges = circle(r=1.2)
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True

    name = "CustomShape_Neck"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts, edges = circle(r=1.3)
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True

    name = "CustomShape_Pelvis"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts, edges = circle(r=3.2)
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True

    name = "CustomShape_Target"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(0.2, 0.0, 0.0), (0.0, -0.2, 0.0), (0.0, 0.0, 0.2)]
        edges = [(0,1), (1,2), (2,0)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("Mirror", "MIRROR")
        mod.use_x = True
        mod.use_y = True
        mod.use_z = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 3

    name = "CustomShape_Volume"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(0.2, 0.0, 0.0), (0.0, -0.5, 0.0), (0.0, 0.0, 0.2)]
        edges = [(0,1), (1,2), (2,0)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("Mirror", "MIRROR")
        mod.use_x = True
        mod.use_y = True
        mod.use_z = True

    name = "CustomShape_Pinch"
    if name not in bpy.data.objects:
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [
                 (0.0, 0.0883883461356163, 0.0883883461356163),    (-0.08838833123445511, 0.0, 0.0883883461356163), 
                 (-0.04783540591597557, 0.0, 0.11548495292663574), (0.0, -0.0883883461356163, 0.0883883461356163), 
                 (0.0, 0.0, 0.125),                                (-0.047835420817136765, 0.11548493802547455, 0.0), 
                 (-0.08838833123445511, 0.0883883610367775, 0.0),  (-0.11548492312431335, 0.04783545061945915, 0.0), 
                 (0.0, 0.125, 0.0),                                (-0.047835420817136765, -0.11548493802547455, 0.0), 
                 (-0.08838833123445511, -0.0883883610367775, 0.0), (-0.11548492312431335, -0.04783545061945915, 0.0), 
                 (-0.125, 0.0, 0.0),                               (0.0, -0.125, 0.0)
                ]
        edges = [(4, 0), (2, 1), (5, 8), (6, 5), (7, 6), (12, 7), (2, 4), (1, 6), (0, 6), (0, 1), (3, 13), (4, 3), (10, 9), (11, 10), (12, 11), (13, 9), (1, 10), (3, 10), (3, 1), (0, 8), (1, 12)]
        faces = []#[(1, 0, 6), (0, 1, 2, 4), (9, 13, 3, 10), (1, 10, 3), (3, 4, 2, 1), (5, 6, 0, 8), (7, 12, 1, 6), (11, 10, 1, 12)]
        mesh.from_pydata(verts, edges, faces)
        mesh.update()
        obj.hide = True
        obj.show_wire = True
        mod = obj.modifiers.new("Mirror", "MIRROR")
        mod.use_x = True
        mod.use_y = True
        mod.use_z = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 1
    
    name = "CustomShape_Cube"
    if name not in bpy.data.objects:
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [( 0.1,  0.1, -0.1),
                 ( 0.1, -0.1, -0.1),
                 (-0.1, -0.1, -0.1),
                 (-0.1,  0.1, -0.1),
                 ( 0.1,  0.1,  0.1),
                 ( 0.1, -0.1,  0.1),
                 (-0.1, -0.1,  0.1),
                 (-0.1, 00.1,  0.1)
                ]
        edges = [(0, 1), (0, 3), (0, 4), (1, 2), (1, 5), (2, 3), (2, 6), (3, 7), (4, 5), (4, 7), (5, 6), (6, 7)]
        faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)]
        mesh.from_pydata(verts, edges, faces)
        mesh.update()
        obj.hide = True
        obj.show_wire = False
    
    name = "CustomShape_Lip"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(-1.2, -0.4, 0.0), (0.0, 0.12, -1.2), (-0.72, -0.08, -0.8), (-0.4, 0.04, -1.04), (-1.08, -0.24, -0.48)]
        edges = [(4, 0), (3, 2), (1, 3), (2, 4)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.hide = True
        obj.show_wire = True
        mod = obj.modifiers.new("Mirror", "MIRROR")
        mod.use_x = True
        mod.use_z = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 1

    name = "CustomShape_Hand"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(-0.52, 0.01, -0.23), (0.52, 0.01, -0.23), (-0.69, 1.0, -0.23), (0.71, 1.0, -0.23), 
                (-0.69, 2.12, -0.23), (-0.69, 0.32, 0.39), (0.71, 0.32, 0.39), (0.71, 2.12, -0.23), 
                (0.62, 2.03, -0.21), (0.62, 0.38, 0.33), (-0.6, 0.38, 0.33), (-0.6, 2.03, -0.21), 
                (0.62, 0.97, -0.21), (-0.6, 0.97, -0.21), (0.46, 0.1, -0.21), (-0.46, 0.1, -0.21)] 
        edges = [(0, 5), (0, 2), (1, 6), (1, 3), (2, 4), (3, 7), (4, 7), (5, 6), (9, 10), (8, 11), 
                (8, 12), (11, 13), (12, 14), (9, 14), (13, 15), (10, 15)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 3

    name = "CustomShape_Foot"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(0.8, 0.0, -2.58), (0.8, 0.0, 1.0), (-0.78, 0.0, 1.0), (-0.78, 0.0, -2.58), (0.8, 0.0, -1.46), 
                 (-0.78, 0.0, -1.46), (0.8, 0.0, 0.2), (-0.78, 0.0, 0.2), (-0.7, 0.0, 0.09), (0.72, 0.0, 0.09), 
                 (-0.7, 0.0, -1.39), (0.72, 0.0, -1.39), (-0.7, 0.0, -2.48), (-0.7, 0.0, 0.89), 
                 (0.72, 0.0, 0.89), (0.72, 0.0, -2.48)] 
        edges = [(1, 2), (0, 3), (0, 4), (3, 5), (4, 6), (1, 6), (5, 7), (2, 7), (8, 13), (8, 10), (9, 14), 
                 (9, 11), (10, 12), (11, 15), (12, 15), (13, 14)]    
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 3

    name = "CustomShape_FootPivot"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(-0.63, 0.0, -0.02), (-0.62, 0.0, -0.16), (0.62, 0.0, -0.16), (0.63, 0.0, -0.02), 
                (-0.71, -0.25, -0.09), (0.71, -0.25, -0.09), (-0.71, 0.0, -0.16), (0.71, 0.0, -0.16), 
                (0.71, 0.0, -0.02), (-0.71, 0.0, -0.02), (-0.0, 0.0, -0.02), (-0.0, 0.0, -0.16), (0.07, 0.0, -0.09), (-0.07, 0.0, -0.09)] 
        edges = [(1, 2), (0, 3), (1, 6), (4, 6), (2, 7), (5, 7), (3, 8), (5, 8), (0, 9), (4, 9), 
                (10, 12), (10, 13), (11, 12), (11, 13)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 2

    name = "CustomShape_EyeTarget"
    if name not in bpy.data.objects:    
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = customobj

        verts = [(1.0, 0.0, 0.0), (0.55, 0.44, -0.0), (0.12, 0.09, -0.0), (0.12, -0.09, 0.0), (0.55, -0.44, 0.0), 
                (0.55, -0.31, 0.0), (0.25, 0.0, 0.0), (0.55, 0.31, -0.0), (0.86, 0.0, 0.0), (0.0, 0.09, -0.0), 
                (0.0, -0.09, 0.0), (-0.86, 0.0, -0.0), (-0.55, 0.31, -0.0), (-0.25, 0.0, -0.0), (-0.55, -0.31, -0.0), 
                (-0.55, -0.44, -0.0), (-0.12, -0.09, -0.0), (-0.12, 0.09, -0.0), (-0.55, 0.44, -0.0), (-0.99, 0.0, -0.0)] 
        edges = [(2, 9), (3, 10), (5, 8), (5, 6), (6, 7), (7, 8), (1, 2), (0, 1), (0, 4), (3, 4), (15, 16), 
                (15, 19), (18, 19), (17, 18), (11, 12), (12, 13), (13, 14), (11, 14), (10, 16), (9, 17)]
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        obj.layers = [ii in [B_LAYER_VOLUME] for ii in range(20)]
        obj.hide = True
        mod = obj.modifiers.new("subsurf", 'SUBSURF')
        mod.levels = 2

def createMesh(context, name, llm_mesh):

    verts = [llm_mesh['baseCoords'][i] for i in llm_mesh['vertLookup']]
    faces = llm_mesh['faces'] # a list of face 3-tuples
    vt = llm_mesh['texCoords'] # vertex (x,y) coords
    normals = llm_mesh['baseNormals']
    if "noseams" in llm_mesh:
        noseams    = llm_mesh['noseams']
        extraseams = llm_mesh['extraseams']
        extrapins  = llm_mesh['extrapins']
    else:
        noseams    = []
        extraseams = []
        extrapins  = []

    meshFaces = []
    for f in faces:
        fv = [data.getVertexIndex(llm_mesh, v) for v in f]
        meshFaces.append(fv)
    
    bpy.ops.object.select_all(action="DESELECT")

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (0,0,0)

    context.scene.objects.link(obj)
    context.scene.objects.active = obj
    obj.select = True
    try:
        for ii in range(20): obj.layers[ii] = context.space_data.layers[ii]
    except:
        pass

    mesh.from_pydata(verts, [], meshFaces)
    mesh.update(calc_edges=True)

    for e in mesh.edges:
        if not e.index in noseams:
            a, b = e.vertices
            if e.index in extraseams \
               or ( llm_mesh['vertLookup'][a] in llm_mesh['vertexRemap'].values() and \
                    llm_mesh['vertLookup'][b] in llm_mesh['vertexRemap'].values()) :
                e.use_seam = True

    mesh.update(calc_edges=True)
    bpy.context.scene.update()

    bpy.ops.object.mode_set(mode='EDIT')
    oselect_modes = util.set_mesh_select_mode((True,True,False))

    try:
        bpy.ops.mesh.select_non_manifold(extend=False, use_wire=False, use_boundary=True, use_multi_face=False, use_non_contiguous=False, use_verts=False)
    except:
        bpy.ops.mesh.select_non_manifold(extend=False)

    bpy.ops.mesh.mark_seam(clear=False)
    bpy.ops.mesh.select_all(action='DESELECT')
    util.set_mesh_select_mode(oselect_modes)

    for v, normal in enumerate(normals):
        if v not in llm_mesh['vertexRemap']:
            mesh.vertices[data.getVertexIndex(llm_mesh, v)].normal = normal

    bpy.ops.mesh.select_all(action='DESELECT')
    util.ensure_mode_is("OBJECT")

    bpy.ops.object.shade_smooth()

    uv_layer_name="SLMap"
    uv = mesh.uv_textures.new(name=uv_layer_name)

    problemFaces = [
        ('upperBodyMesh',199),
        ('headMesh',1464),
        ('headMesh',1465),
        ('skirtMesh',200),
        ('skirtMesh',211),
        ('skirtMesh',217),
        ('eyeBallRightMesh',173),
        ('eyeBallLeftMesh',173),
        ('eyelashMesh',4),
        ('hairMesh',351),
        ]

    index    = mesh.uv_textures.keys().index(uv.name)
    uvloops  = mesh.uv_layers[index].data
    loops    = mesh.loops
    polygons = mesh.polygons
    for i, face in enumerate(faces):
        for j in range(3):
            loop = polygons[i].loop_indices[j]
            uvloops[loop].uv = vt[face[j]]
                    
    obj.shape_key_add("Basis")
    obj.data.update()
    obj.active_shape_key_index = 0
    
    obj.use_shape_key_edit_mode = True
    
    return obj

def createShapekey(obj, pid, morph, mesh):
    key = obj.shape_key_add(pid)
    
    key.slider_min = morph['value_min']
    key.slider_max = morph['value_max']
    key.value      = morph['value_default']
    
    for v in morph['vertices']:

        if v['vertexIndex'] in mesh['vertexRemap']:
            continue
        i = data.getVertexIndex(mesh, v['vertexIndex'])
        key.data[i].co = Vector(mesh['baseCoords'][v['vertexIndex']]) + Vector(v['coord'])

def createMeshGroups(obj, mesh):

    for joint in mesh['skinJoints']:
        group = obj.vertex_groups.new(joint)

    name = mesh['name']
    for ii in range(len( mesh['weights'] )):
        if ii in mesh['vertexRemap']:
            continue
        i = data.getVertexIndex(mesh, ii)
        b,w = mesh['weights'][ii]
        b1, b2 = data.WEIGHTSMAP[name][b]
        obj.vertex_groups[b1].add([i], 1.0-w, 'REPLACE')
        if b2 is not None and w!=0:
            obj.vertex_groups[b2].add([i], w, 'REPLACE')

def add_initial_rotation(pbone, delta):
    original_mode = pbone.rotation_mode
    pbone.rotation_mode = "QUATERNION"
    pbone.rotation_quaternion.z += delta
    pbone.rotation_mode = original_mode
    
def add_bone_group(arm, name, color_set):
    bpy.ops.pose.group_add()
    bg = arm.pose.bone_groups.active 
    bg.name = name
    bg.color_set = color_set

def add_bone_groups(arm):
    for group, val in BONEGROUP_MAP.items():
        colorset   = val[0]       
        add_bone_group(arm, group, colorset)

def createArmature(context, arm_obj, arm_data, SKELETON, rigtype):
    IR = 0.001
    scn = context.scene    

    scn.objects.active = arm_obj
    arm_obj.select = True

    try:
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    except:
        for ii in range(20):
            arm_obj.layers[ii] = context.space_data.layers[ii]
        print("Added object to layers", arm_obj.layers)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)

    createBoneRecursive(SKELETON["Origin"], None, arm_obj, rigtype)

    bpy.ops.object.mode_set(mode='POSE', toggle=False)
    add_bone_groups(arm_obj)

    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    rig.adjustBoneRoll(arm_obj)
    rig.adjustSLToRig(arm_obj) # Forces SL bones into exact Rest pose (adjust bone roll ?)

    bpy.ops.object.mode_set(mode='POSE', toggle=False)
    setCustomShapesRecursive(SKELETON["Origin"], arm_obj)

    createConstraints(arm_obj, SKELETON, rigtype)

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    util.Skeleton.get_toe_hover_z(arm_obj, reset=True)
    
    for pbone in arm_obj.pose.bones:

        pbone.lock_scale = [True, True, True] 

        BONE = SKELETON[pbone.name]
        if BONE == None:
            continue

        pbone.ik_stiffness_x = BONE.stiffness[0]
        pbone.ik_stiffness_y = BONE.stiffness[1]
        pbone.ik_stiffness_z = BONE.stiffness[2]

        if BONE.limit_rx is not None \
           or BONE.limit_ry is not None \
           or BONE.limit_rz is not None: 

            con = pbone.constraints.new("LIMIT_ROTATION")
            con.owner_space = 'LOCAL' 

            if BONE.limit_rx is not None:
                pbone.use_ik_limit_x = True
                pbone.ik_min_x = radians(BONE.limit_rx[0])
                pbone.ik_max_x = radians(BONE.limit_rx[1])
                con.min_x = radians(BONE.limit_rx[0])
                con.max_x = radians(BONE.limit_rx[1])
                con.use_limit_x = True
            if BONE.limit_ry is not None:
                pbone.use_ik_limit_y = True
                pbone.ik_min_y = radians(BONE.limit_ry[0])
                pbone.ik_max_y = radians(BONE.limit_ry[1])
                con.min_y = radians(BONE.limit_ry[0])
                con.max_y = radians(BONE.limit_ry[1])
                con.use_limit_y = True
            if BONE.limit_rz is not None:
                pbone.use_ik_limit_z = True
                pbone.ik_min_z = radians(BONE.limit_rz[0])
                pbone.ik_max_z = radians(BONE.limit_rz[1])
                con.min_z = radians(BONE.limit_rz[0])
                con.max_z = radians(BONE.limit_rz[1])
                con.use_limit_z = True

        if pbone.name in ["PelvisInv", "Pelvis"]:
            pbone.lock_location = [True, True, True]

        if "Link" in pbone.name or pbone.name == "Pelvis" or "Line" in pbone.name:
            pbone.lock_rotation = [True, True, True] 
            pbone.lock_rotation_w = True
            pbone.lock_location = [True, True, True]
            pbone.lock_ik_x = True
            pbone.lock_ik_y = True
            pbone.lock_ik_z = True

        B = SKELETON[pbone.name]
        if B.bonegroup in arm_obj.pose.bone_groups:
            pbone.bone_group = arm_obj.pose.bone_groups[B.bonegroup]
        else:            
            print("Bone group [%s : %s] does not exist" % (pbone.name, B.bonegroup) )

        if pbone.name == "ElbowRight":
            add_initial_rotation(pbone,IR)
        elif pbone.name == "ElbowLeft":
            add_initial_rotation(pbone,-IR)

    for layer in [0,1,3,5]:
        arm_obj.data.layers[layer] = True

    for pbone in arm_obj.pose.bones:

        if pbone.name[0] == "m" or "m"+pbone.name in arm_obj.pose.bones or pbone.name == 'PelvisInv':
            pbone['priority'] = NULL_BONE_PRIORITY

    for bname in sym_expand(arm_obj.data.bones.keys(), ['*Link.','*Line']):
        if bname in arm_obj.data.bones:
            arm_obj.data.bones[bname].hide_select = True

    for bname in data.get_volume_bones(only_deforming=False):
        if bname in arm_obj.pose.bones:
            arm_obj.pose.bones[bname].lock_rotation[0]=True
            arm_obj.pose.bones[bname].lock_rotation[1]=True
            arm_obj.pose.bones[bname].lock_rotation[2]=True
            arm_obj.pose.bones[bname].lock_location[0]=True
            arm_obj.pose.bones[bname].lock_location[1]=True
            arm_obj.pose.bones[bname].lock_location[2]=True

    for bone in arm_obj.data.bones:
        bone.layers[B_LAYER_DEFORM] = bone.use_deform
        B = SKELETON[bone.name]
        bone['b0head'] = B.b0head
        bone['b0tail'] = B.b0tail - B.b0head
        bone['b0dist'] = B.b0dist # distance to parent bone in SL restpose

def init_meta_data(blbone, BONE):

    is_structure = BONE.is_structure
    if is_structure is None:
        is_structure = False

    blbone['is_structure'] = is_structure
    if BONE.slname is not None or BONE.blname:
        blbone['scale']   = tuple(BONE.scale)
        blbone['offset']  = tuple(BONE.offset)
        blbone['relhead'] = tuple(BONE.relhead)
        blbone['reltail'] = tuple(BONE.reltail) if BONE.reltail is not None else tuple(Vector(blbone['relhead']) + Vector((0,0.1,0)))
        blbone['scale0']  = tuple(BONE.scale0)
        blbone['rot0']    = tuple(BONE.rot0)
        blbone['pivot0']  = tuple(BONE.pivot0)
        blbone['pos0']    = tuple(BONE.pos0)

        if BONE.slname is not None:
            blbone['slname'] = BONE.slname
        if BONE.bvhname is not None:
            blbone['bvhname'] = BONE.bvhname

def createBoneRecursive(BONE, parent, arm_obj, rigType):
    support = BONE.skeleton.upper()
    rigType = rigType.upper()
    blbone = parent

    if rigType != 'BASIC' or support != 'EXTENDED':

        name = BONE.blname
        blbone = arm_obj.data.edit_bones.new(name)
        h = Vector(BONE.head())
        t = Vector(BONE.tail())
        size = (t-h).magnitude

        blbone.parent = parent
        blbone.head   = h
        blbone.tail   = t
        blbone.layers = [ii in BONE.bonelayers for ii in range(32)]
        blbone.roll   = BONE.roll
        blbone.use_inherit_scale = False
        blbone.use_inherit_rotation = True
        blbone.use_local_location = True
        rig.set_connect(blbone, BONE.connected, "createBoneRecursive")
        if hasattr(BONE,'deform'):
            blbone.use_deform = BONE.deform
        else:
            blbone.use_deform = False

        init_meta_data(blbone, BONE)

    if len(BONE.children) > 0:
        keys = [child.blname for child in BONE.children] 

        for CHILD in BONE.children:

            blchild = createBoneRecursive(CHILD, blbone, arm_obj, rigType)
            blchild.parent = blbone

    return blbone
    
def setCustomShapesRecursive(bone, arm_ob):
    if bone.shape is not None:
        arm_ob.pose.bones[bone.blname].custom_shape = bpy.data.objects[bone.shape]
        arm_ob.data.bones[bone.blname].show_wire = bone.wire
        try:
            if bone.shape_scale is not None:
                arm_ob.pose.bones[bone.blname].custom_shape_scale = bone.shape_scale
        except:
            print("WARN: This version of Blender does not support scaling of Custom shapes")
            print("      Ignoring Custom Shape Scale for bone [%s]" % (bone.blname))

    for child in bone.children: 
        setCustomShapesRecursive(child, arm_ob)

def add_bone_constraint(type, pbone, name=None, space='LOCAL', influence=1.0, target=None, subtarget=None):
    con = pbone.constraints.new(type)
    try:
        con.owner_space  = space
        con.target_space = space
    except:
        pass
    
    if target:
        con.target=target
    if subtarget:
        con.subtarget=subtarget
    
    con.influence = influence
    if name:
        con.name=name
    return con

def set_constraint_limit(con, states, values):
    if con.type=='LIMIT_ROTATION':
        con.use_limit_x = states[0]
        con.min_x       = values[0][0]
        con.max_x       = values[0][1]
        
        con.use_limit_y = states[1]
        con.min_y       = values[1][0]
        con.max_y       = values[1][1]
        
        con.use_limit_z = states[2]
        con.min_z       = values[2][0]
        con.max_z       = values[2][1]

    elif con.type=='LIMIT_LOCATION':
        con.use_min_x = states[0]
        con.use_max_x = states[0]
        con.min_x       = values[0][0]
        con.max_x       = values[0][1]
        
        con.use_min_y = states[0]
        con.use_max_y = states[0]
        con.min_y       = values[1][0]
        con.max_y       = values[1][1]
        
        con.use_min_z = states[0]
        con.use_max_z = states[0]
        con.min_z       = values[2][0]
        con.max_z       = values[2][1]

def set_source_range(con, source, values):
    con.map_from = source
    if source == 'LOCATION':
        con.from_min_x = values[0][0]
        con.from_max_x = values[0][1]
        con.from_min_y = values[1][0]
        con.from_max_y = values[1][1]
        con.from_min_z = values[2][0]
        con.from_max_z = values[2][1]
    elif source == 'ROTATION':
        con.from_min_x_rot = values[0][0]*DEGREES_TO_RADIANS
        con.from_max_x_rot = values[0][1]*DEGREES_TO_RADIANS
        con.from_min_y_rot = values[1][0]*DEGREES_TO_RADIANS
        con.from_max_y_rot = values[1][1]*DEGREES_TO_RADIANS
        con.from_min_z_rot = values[2][0]*DEGREES_TO_RADIANS
        con.from_max_z_rot = values[2][1]*DEGREES_TO_RADIANS
    elif source == 'SCALE':
        con.from_min_x_scale = values[0][0]
        con.from_max_x_scale = values[0][1]
        con.from_min_y_scale = values[1][0]
        con.from_max_y_scale = values[1][1]
        con.from_min_z_scale = values[2][0]
        con.from_max_z_scale = values[2][1]
    
def set_destination (con, dest,   values):
    con.map_to = dest
    
    if dest == 'LOCATION':
        con.to_min_x = values[0][0]
        con.to_max_x = values[0][1]
        con.to_min_y = values[1][0]
        con.to_max_y = values[1][1]
        con.to_min_z = values[2][0]
        con.to_max_z = values[2][1]
    elif dest == 'ROTATION':
        con.to_min_x_rot = values[0][0]*DEGREES_TO_RADIANS
        con.to_max_x_rot = values[0][1]*DEGREES_TO_RADIANS
        con.to_min_y_rot = values[1][0]*DEGREES_TO_RADIANS
        con.to_max_y_rot = values[1][1]*DEGREES_TO_RADIANS
        con.to_min_z_rot = values[2][0]*DEGREES_TO_RADIANS
        con.to_max_z_rot = values[2][1]*DEGREES_TO_RADIANS
    elif dest == 'SCALE':
        con.to_min_x_scale = values[0][0]
        con.to_max_x_scale = values[0][1]
        con.to_min_y_scale = values[1][0]
        con.to_max_y_scale = values[1][1]
        con.to_min_z_scale = values[2][0]
        con.to_max_z_scale = values[2][1]
    
def set_mapping(con, x, y, z):
    con.map_to_x_from=x
    con.map_to_y_from=y
    con.map_to_z_from=z
    
def create_face_controllers(arm, group):

    pbones    = arm.pose.bones
    try:
        lipmaster = pbones['ikFaceLipShapeMaster']
        lipshape  = pbones['ikFaceLipShape']
    except:
        print("No face controllers defined for this Skeleton")
        return

    for symmetry in ["Left", "Right"]:
        ikCornerName = 'ikFaceLipCorner%s' % symmetry
        for handle in(["FaceLipCorner","FaceLipUpper", "FaceLipLower"]):
            pbone = pbones["%s%s" % (handle,symmetry)]
            con   = pbone.constraints.new("COPY_TRANSFORMS")
            con.target       = arm
            con.subtarget    = ikCornerName
            con.target_space = 'LOCAL'
            con.owner_space  = 'LOCAL'
            con.influence    = 1 if "Corner" in handle else 0.25
            con.mute         = False

        ikCornerName = 'ikFaceEyebrowCenter%s' % symmetry
        for handle in(["FaceEyebrowInner","FaceEyebrowCenter", "FaceEyebrowOuter"]):
            pbone = pbones["%s%s" % (handle,symmetry)]
            con   = pbone.constraints.new("COPY_TRANSFORMS")
            con.target       = arm
            con.subtarget    = ikCornerName
            con.target_space = 'LOCAL'
            con.owner_space  = 'LOCAL'
            con.influence    = 1 if "Center" in handle else 0.25
            con.mute         = False

        sign = 1 if symmetry=='Left' else -1
        pbone = pbones['FaceLipUpper%s' % symmetry]

        con = add_bone_constraint('TRANSFORM', pbone, name="Location",       target=arm, subtarget = lipshape.name, influence=0.6)
        set_source_range(con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],      [0.5,1.50]] )
        set_mapping(con, 'X', 'X', 'Z')
        set_destination (con, 'LOCATION', [[0.005*sign,-0.005*sign],    [0.005,-0.005], [0.0,0.01]] )

        con = add_bone_constraint('TRANSFORM', pbone, name="Rotation",       target=arm, subtarget = lipmaster.name)
        set_source_range(con, 'ROTATION',    [[-20, 20],    [-20, 20],      [-20, 20]] )
        set_mapping(con, 'X', 'Y', 'X')
        set_destination (con, 'LOCATION', [[0.00,-0.00],    [0.00,-0.00], [-0.005,0.005]] )

        pbone = pbones['FaceLipLower%s' % symmetry]
        con = add_bone_constraint('COPY_TRANSFORMS', pbone, name="Copy Transformns", influence = 0.25, target=arm, subtarget = 'ikFaceLipCorner%s' % symmetry)

        con = add_bone_constraint('TRANSFORM', pbone, name="Location",       target=arm, subtarget = lipshape.name)
        set_source_range(con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],      [0.5,1.50]] )
        set_mapping(con, 'X', 'X', 'Z')
        set_destination (con, 'LOCATION', [[0.005*sign,-0.005*sign],    [0.005,-0.005], [0.0,-0.01]] )

        con = add_bone_constraint('TRANSFORM', pbone, name="Rotation",       target=arm, subtarget = lipmaster.name)
        set_source_range(con, 'ROTATION',    [[-20, 20],    [-20, 20],      [-20, 20]] )
        set_mapping(con, 'X', 'Y', 'X')
        set_destination (con, 'LOCATION', [[0.00,-0.00],    [0.00,-0.00], [-0.005,0.005]] )

        pbone = pbones['FaceLipCorner%s' % symmetry]
        con = add_bone_constraint('COPY_TRANSFORMS', pbone, name="Copy Transformns", influence = 0.25, target=arm, subtarget = 'ikFaceLipCorner%s' % symmetry)

        con = add_bone_constraint('TRANSFORM', pbone, name="Location",       target=arm, subtarget = lipshape.name, influence=0.75)
        set_source_range(con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],      [0.5,1.50]] )
        set_mapping(con, 'X', 'X', 'Z')
        set_destination (con, 'LOCATION', [[0.015*sign,-0.015*sign],    [0.015,-0.015], [0.0,-0.0]] )

        con = add_bone_constraint('TRANSFORM', pbone, name="Rotation",       target=arm, subtarget = lipmaster.name)
        set_source_range(con, 'ROTATION',    [[-20, 20],    [-20, 20],      [-20, 20]] )
        set_mapping(con, 'X', 'Y', 'X')
        set_destination (con, 'LOCATION', [[0.00,-0.00],    [0.00,-0.00], [-0.02,0.02]] )

        try:
            pbone = pbones['FaceCheekLower%s' % symmetry]
            con = add_bone_constraint('TRANSFORM', pbone, name="Rotation",       target=arm, subtarget = lipshape.name)
            set_source_range(con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],      [0.5,1.50]] )
            set_mapping(con, 'X', 'X', 'Z')
            set_destination (con, 'LOCATION', [[0.015*sign,-0.015*sign],    [0.005,-0.005], [0.0,0.01]] )
        except:
            pass

        pbone = pbones['FaceNose%s' % symmetry]
        con = add_bone_constraint('TRANSFORM', pbone, name="Location",       target=arm, subtarget = lipshape.name)
        set_source_range(con, 'SCALE',    [[0.5,1.5], [0.5,1.5], [0.5,1.50]] )
        set_mapping(con, 'X', 'X', 'Z')
        set_destination (con, 'LOCATION', [[0,0],     [0,0],     [0.0,0.002]] )

    con = add_bone_constraint('LIMIT_ROTATION', lipmaster)
    set_constraint_limit(con, [False, True, True], [[ 0.000, 0.000], [ 0.000,0.000], [ 0.000, 0.000]])
    con = add_bone_constraint('LIMIT_LOCATION', lipmaster)
    set_constraint_limit(con, [True, True, True],  [[-0.012, 0.020], [-0.03, 0.030], [-0.010, 0.010]])
    
    con = add_bone_constraint('TRANSFORM', lipshape, name="Scale",    target=arm, subtarget = lipmaster.name)
    set_source_range(con, 'LOCATION', [[-0.01, 0.01],[-0.01, 0.01],[ 0.00, 0.01]])
    set_destination (con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],    [0.5,1.5]]    )
    set_mapping(con, 'Y', 'Y', 'Z')
    
    con = add_bone_constraint('TRANSFORM', lipshape, name="Location", target=arm, subtarget = lipmaster.name)
    set_source_range(con, 'LOCATION', [[-0.03, 0.03],[-0.0, 0.0], [ 0.00, 0.0]])
    set_destination(con,  'LOCATION', [[0,0],        [-0.03,0.03],[0,0]       ])
    set_mapping(con, 'X', 'X', 'Z')
    
    try:
        pbone = pbones['FaceLipUpperCenter']
        con = add_bone_constraint('TRANSFORM', pbone, name="Location",    target=arm, subtarget = lipshape.name, influence=0.75)
        set_source_range(con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],      [0.5,1.50]] )
        set_destination (con, 'LOCATION', [[0.0,0.0],    [0.005,-0.005], [0.0,0.02]] )

        pbone = pbones['FaceLipLowerCenter']
        con = add_bone_constraint('TRANSFORM', pbone, name="Location",    target=arm, subtarget = lipshape.name)
        set_source_range(con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],      [0.5,1.50]] )
        set_destination (con, 'LOCATION', [[0.0,0.0],    [0.005,-0.005], [0.0,-0.02]] )
    except:
        pass

    pbone = pbones['FaceNoseCenter']
    con = add_bone_constraint('TRANSFORM', pbone, name="Location",    target=arm, subtarget = lipshape.name)
    set_source_range(con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],    [0.5,1.50]]  )
    set_destination (con, 'LOCATION', [[0.0,0.0],    [0.00,-0.0],  [0.0,0.004]] )

    pbone = pbones['FaceJaw']
    con = add_bone_constraint('TRANSFORM', pbone, name="Location",    target=arm, subtarget = lipshape.name)
    set_source_range(con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],    [0.5,1.50]]  )
    set_destination (con, 'ROTATION', [[0.0,-10.0],  [0.00,-0.0],  [0.0,0.0]] )
    set_mapping(con, 'Z', 'Y', 'X')

    pbone = pbones['FaceTeethLower']
    con = add_bone_constraint('TRANSFORM', pbone, name="Location",    target=arm, subtarget = lipshape.name)
    set_source_range(con, 'SCALE',    [[0.5,1.5],    [0.5,1.5],    [0.5,1.50]]  )
    set_destination (con, 'ROTATION', [[0.0,-20.0],  [0.00,-0.0],  [0.0,0.0]] )
    set_mapping(con, 'Z', 'Y', 'X')

def create_chain_controllers(arm, group):
    pbones = arm.pose.bones
    for pbone in [b for b in pbones if b.name.startswith(group) and (b.name.endswith("Left") or b.name.endswith("Right"))]:
        name = pbone.name
        symmetry = "Left" if name.endswith("Left") else "Right"
        part     = name[len(group):-len(symmetry)-1]
        sindex   = name[-len(symmetry)-1]

        if sindex == None: continue # Should never happen
        if not name.endswith("0"+symmetry):
            con = pbone.constraints.new("LIMIT_ROTATION")
            con.use_limit_x = True
            con.min_x = -90 * DEGREES_TO_RADIANS
            con.max_x =  15 * DEGREES_TO_RADIANS

            min = -30 if name.startswith("HandThumb1") else -10
            max =  30 if name.startswith("HandThumb1") else  10
            con.use_limit_y = True
            con.min_y = min * DEGREES_TO_RADIANS
            con.max_y = max * DEGREES_TO_RADIANS

            min = -30
            max = 50 if name.startswith("HandPinky") else 40 if name.startswith("HandThumb1") else 20
            con.use_limit_z = True
            con.min_z = min * DEGREES_TO_RADIANS
            con.max_z = max * DEGREES_TO_RADIANS
            con.owner_space = 'LOCAL'
            con.influence = 1

        index = int(sindex)
        if index == 1:
            for i in range(0,3):pbone.lock_location[i]=True
            pbone.lock_rotation[1]=False if name.startswith("HandThumb1") else  True
            pbone.lock_rotation_w=True
            pbone.lock_rotations_4d=True
            continue

        if index == 3: #disable IK constraints for now (set back to index == 3 top reactivate)
            try:
                solver          = pbones["ik%sSolver%s" % (part,symmetry)]
                target          = pbones["ik%sTarget%s" % (part,symmetry)]
                con             = solver.constraints.new("IK")
                con.target      = arm
                con.subtarget   = target.name
                con.chain_count = 3
                con.use_tail    = False
                con.mute        = True
                con.name        = 'Grab'
                con.influence   = 0

                if part in ['Thumb','Index']:
                    target          = pbones["ikIndexPinch%s" % (symmetry)]
                    con             = solver.constraints.new("IK")
                    con.target      = arm
                    con.subtarget   = target.name
                    con.chain_count = 3
                    con.use_tail    = False
                    con.mute        = False
                    con.name        = 'Pinch'
                    con.influence   = 0

            except:

                pass

        if not name.endswith("0"+symmetry):
            con = pbone.constraints.new("COPY_ROTATION")
            con.target = arm
            con.subtarget = pbone.parent.name
            con.use_offset = True
            con.target_space = 'LOCAL'
            con.owner_space = 'LOCAL'
            con.influence = 1

            con.use_y = False
            con.use_z = False

        pbone.use_ik_limit_x = True
        pbone.ik_min_x = -90 * DEGREES_TO_RADIANS
        pbone.ik_max_x = 0
        pbone.lock_ik_y = True
        pbone.lock_ik_z = True

def createConstraints(armobj, SKELETON, rigType):

    pbones = armobj.pose.bones
    #

    #
    pbone = pbones['ElbowLeft'] 
    pbone.lock_ik_y = True
    pbone.lock_ik_x = True
    con = pbone.constraints.new("IK")
    con.use_tail = True
    con.use_stretch = False
    con.target = armobj
    con.subtarget = "ikWristLeft"
    con.pole_target = armobj
    con.pole_subtarget = "ikElbowTargetLeft"   
    con.chain_count = 2
    con.pole_angle = pi # different from right, go figure.
    con.influence = 0

    pbone = pbones['ElbowRight'] 
    pbone.lock_ik_y = True
    pbone.lock_ik_x = True
    con = pbone.constraints.new("IK")
    con.use_tail = True
    con.use_stretch = False
    con.target = armobj
    con.subtarget = "ikWristRight"
    con.pole_target = armobj
    con.pole_subtarget = "ikElbowTargetRight"   
    con.chain_count = 2
    con.pole_angle = 0
    con.influence = 0

    pbone = pbones['KneeLeft'] 

    pbone.lock_ik_z = True
    con = pbone.constraints.new("IK")
    con.use_tail = True
    con.use_stretch = False
    con.target = armobj
    con.subtarget = "ikAnkleLeft"
    con.pole_target = armobj
    con.pole_subtarget = "ikKneeTargetLeft"   
    con.chain_count = 2
    con.pole_angle = radians(-90)
    con.influence = 0

    pbone = pbones['KneeRight'] 

    pbone.lock_ik_z = True
    con = pbone.constraints.new("IK")
    con.use_tail = True
    con.use_stretch = False
    con.target = armobj
    con.subtarget = "ikAnkleRight"
    con.pole_target = armobj
    con.pole_subtarget = "ikKneeTargetRight"   
    con.chain_count = 2
    con.pole_angle = radians(-90)
    con.influence = 0

    pbone = pbones.get('HindLimb2Right')
    if pbone:

        pbone.lock_ik_z = True
        con = pbone.constraints.new("IK")
        con.use_tail = True
        con.use_stretch = False
        con.target = armobj
        con.subtarget = "ikHindLimb3Right"
        con.pole_target = armobj
        con.pole_subtarget = "ikHindLimb2TargetRight"   
        con.chain_count = 2
        con.pole_angle = radians(-90)
        con.influence = 0

    pbone = pbones.get('HindLimb2Left')
    if pbone:

        pbone.lock_ik_z = True
        con = pbone.constraints.new("IK")
        con.use_tail = True
        con.use_stretch = False
        con.target = armobj
        con.subtarget = "ikHindLimb3Left"
        con.pole_target = armobj
        con.pole_subtarget = "ikHindLimb2TargetLeft"   
        con.chain_count = 2
        con.pole_angle = radians(-90)
        con.influence = 0

    #

    #
    create_ik_linebone_cons(armobj, 'Elbow', 'Left')
    create_ik_linebone_cons(armobj, 'Elbow', 'Right')
    create_ik_linebone_cons(armobj, 'Knee', 'Left')
    create_ik_linebone_cons(armobj, 'Knee', 'Right')
    create_ik_linebone_cons(armobj, 'HindLimb2', 'Left')
    create_ik_linebone_cons(armobj, 'HindLimb2', 'Right')

    con = pbones["mPelvis"].constraints.new("COPY_LOCATION")
    con.target = bpy.context.active_object
    con.subtarget = "Pelvis"
    con.influence = 1

    LArm  = ['mCollarLeft', 'mShoulderLeft','mElbowLeft','mWristLeft']
    RArm  = ['mCollarRight', 'mShoulderRight','mElbowRight','mWristRight']
    LLeg  = ['mHipLeft','mKneeLeft','mAnkleLeft', 'mFootLeft', 'mToeLeft']
    RLeg  = ['mHipRight','mKneeRight','mAnkleRight', 'mFootRight', 'mToeRight']
    LLimb = ['mHindLimb1Left','mHindLimb2Left','mHindLimb3Left', 'mHindLimb4Left']
    RLimb = ['mHindLimb1Right','mHindLimb2Right','mHindLimb3Right', 'mHindLimb4Right']
    Torso = ['mPelvis', 'mTorso', 'mChest', 'mNeck', 'mHead', 'mSkull', 'mEyeLeft', 'mEyeRight', 
             'mFaceEyeAltLeft', 'mFaceEyeAltRight'
            ]

    #
    Custom  = util.bone_category_keys(pbones, "mWing")
    Custom += util.bone_category_keys(pbones, "mTail")
    Custom += util.bone_category_keys(pbones, "mFace")
    Custom += util.bone_category_keys(pbones, "mHand")
    Custom += util.bone_category_keys(pbones, "mGroin")
    Custom += util.bone_category_keys(pbones, "mHind")
    Custom += util.bone_category_keys(pbones, "mSpine")

    for b in [b for b in LArm+RArm+LLeg+RLeg+LLimb+RLimb+Torso+Custom if b in pbones]:
        con = pbones[b].constraints.new("COPY_ROTATION")
        con.target = bpy.context.active_object
        con.subtarget = b[1:]
        con.influence = 1

        con = pbones[b].constraints.new("COPY_LOCATION")
        con.target = bpy.context.active_object
        con.subtarget = b[1:]
        con.target_space = 'WORLD'
        con.owner_space = 'WORLD'
        con.influence = 1
        
    for b1,b2 in [
        ("WristLeft","ikWristLeft"),
        ("WristRight","ikWristRight"),
        ("AnkleLeft","ikAnkleLeft"),
        ("AnkleRight","ikAnkleRight"),
        ("HindLimb3Left","ikHindLimb3Left"),
        ("HindLimb3Right","ikHindLimb3Right"),
        ]:
        pbone = pbones.get(b1)
        if pbone:
            con = pbone.constraints.new("COPY_ROTATION")
            con.target = bpy.context.active_object
            con.subtarget = b2

            con.influence = 1

            fcurve = con.driver_add('influence')
            driver = fcurve.driver
            driver.type = 'MIN'

            v1 = driver.variables.new()
            v1.type = 'SINGLE_PROP'
            v1.name = 'hinge'

            t1 = v1.targets[0]
            t1.id = armobj

            v2 = driver.variables.new()
            v2.type = 'SINGLE_PROP'
            v2.name = 'ik'

            t2 = v2.targets[0]
            t2.id = armobj

            if b1 == "WristLeft":
                t1.data_path = 'IKSwitches.IK_Wrist_Hinge_L'
                t2.data_path = 'pose.bones["ElbowLeft"].constraints["IK"].influence'
            elif b1 == "WristRight":
                t1.data_path = 'IKSwitches.IK_Wrist_Hinge_R'
                t2.data_path = 'pose.bones["ElbowRight"].constraints["IK"].influence'
            elif b1 == "AnkleLeft":
                t1.data_path = 'IKSwitches.IK_Ankle_Hinge_L'
                t2.data_path = 'pose.bones["KneeLeft"].constraints["IK"].influence'
            elif b1 == "AnkleRight":
                t1.data_path = 'IKSwitches.IK_Ankle_Hinge_R'
                t2.data_path = 'pose.bones["KneeRight"].constraints["IK"].influence'
            elif b1 == "HindLimb3Left":
                t1.data_path = 'IKSwitches.IK_HindLimb3_Hinge_L'
                t2.data_path = 'pose.bones["HindLimb2Left"].constraints["IK"].influence'
            elif b1 == "HindLimb3Right":
                t1.data_path = 'IKSwitches.IK_HindLimb3_Hinge_R'
                t2.data_path = 'pose.bones["HindLimb2Right"].constraints["IK"].influence'
    
    chains =  {'CollarLeft':4, 'ShoulderLeft':2,'ElbowLeft':3,'WristLeft':4,
            'CollarRight':4, 'ShoulderRight':2,'ElbowRight':3,'WristRight':4,
            'HipLeft':4,'KneeLeft':2,'AnkleLeft':3, 'FootLeft':4, 'ToeLeft':5,
            'HipRight':4,'KneeRight':2,'AnkleRight':3, 'FootRight':4, 'ToeRight':5,
            'HindLimb1Left':4,'HindLimb2Left':2,'HindLimb3Left':3, 'HindLimb4Left':4,
            'HindLimb1Right':4,'HindLimb2Right':2,'HindLimb3Right':3, 'HindLimb4Right':4,
            'PelvisInv':2, 'Torso':2, 'Chest':2, 'Neck':3, 'Head':4, 'Skull':5
            }
    boneset = SKELETON.bones
    roots = data.get_ik_roots(boneset, rigType)
    for root in roots:
        if not root.blname in chains.keys():
            ik_end = root.ik_end
            log.debug("Found IK chain %s o--(%d)--o %s (rigtype:%s)" % (root.blname, root.ik_len, ik_end.blname, rigType))
            ik_element = root.ik_end
            ik_len     = root.ik_len
            while ik_element:
                olen = chains[ik_element.blname] if ik_element.blname in chains else 0
                chains[ik_element.blname] = max(olen, ik_len)
                ik_len -= 1
                if ik_len < 1: break
                ik_element = ik_element.parent

    for b,l in chains.items():
        bone = pbones.get(b, None)
        if bone:
            if  bone.name.startswith("Hand"):
                continue # discard targetless IK for fingers
            con = bone.constraints.new("IK")
            con.name = "TargetlessIK"
            con.use_tail = True
            con.use_stretch = False
            con.chain_count = l
            con.influence = 1
        else:
            print("Bone %s is not in pbones of armature %s" % (b, armobj.name))

    basic_eyes = ["Eye"]
    extended_eyes = ["Eye", "FaceEyeAlt"]
    eye_chains = basic_eyes if rigType=='BASIC' else extended_eyes
    for b in eye_chains:
        for symmetry in ["Left", "Right"]:
            name = "%s%s" % (b,symmetry)
            bone = pbones[name] if name in pbones else None
            if bone:
                con = bone.constraints.new("DAMPED_TRACK")
                con.target     = bpy.context.active_object
                con.subtarget  = "%sTarget" % b
                con.track_axis = "TRACK_Y"
                con.head_tail  = 0.0
            else:
                print("EyeBone %s is not in pbones of armature %s" % (name,armobj.name))

    if rigType == 'EXTENDED':
        create_chain_controllers(armobj, "Hand")
        create_face_controllers(armobj, "Face")

def create_ik_linebone_cons(armobj, bname, side):
    pbones = armobj.pose.bones
    linebone = pbones.get('ik%sLine%s'%(bname,side))
    if linebone:
        con = linebone.constraints.new("COPY_LOCATION")
        con.target = bpy.context.active_object
        con.subtarget = "m%s%s" % (bname, side)
        con.influence = 1.0

        con = linebone.constraints.new("STRETCH_TO")
        con.target = armobj
        con.subtarget = "ik%sTarget%s" % (bname, side)
        con.influence = 1.0

def reset_rig(armobj):
    rigType = bpy.context.object.RigProps.RigType
    jointType = bpy.context.object.RigProps.JointType
    SKELETON = data.getSkeletonDefinition(rigType,jointType)
    BONES = SKELETON.bones
    omode = util.ensure_mode_is('EDIT')
    for b in armobj.data.edit_bones:
        for key in b.keys():
            del b[key]
        BONE = BONES.get(b.name)
        if BONE:
            init_meta_data(b, BONE)
        else:
            log.warning("No Metadata for bone %s" % b.name)        
    
if __name__ == '__main__':

    pass
