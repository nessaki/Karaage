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

import bpy, bmesh, sys
from mathutils import Vector, Matrix
import  xml.etree.ElementTree as et
import xmlrpc.client
from bpy_extras.io_utils import ExportHelper
from bpy.props import *
import logging, gettext, os, time, re, shutil
from math import pi, exp
from bpy.types import Menu, Operator
from bl_operators.presets import AddPresetBase

from . import const, data, util, shape, bl_info
from .const  import *
from bpy.app.handlers import persistent

LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locale')
translator = gettext.translation('karaage', LOCALE_DIR, fallback=True)
_ = translator.gettext

log = logging.getLogger('karaage.weights')

def mirrorBoneWeightsFromOppositeSide(context, operator, use_topology=False, algorithm='BLENDER'):
    obj        = context.object
    armobj     = obj.find_armature()
    layer_indices = [i for i, l in enumerate(bpy.data.armatures[armobj.data.name].layers) if l]

    activeBone = armobj.data.bones.active
    counter = 0
    selectedBoneNames = []
    for bone in armobj.data.bones:
        if bone.select and not bone.hide :
            bone_layers = [i for i, l in enumerate(bone.layers) if l]
            is_visible  = bool(len([i for i in bone_layers if i in layer_indices]))
            if is_visible:
                mirror_name = util.get_mirror_name(bone.name)
                if mirror_name and mirror_name in obj.vertex_groups and not bone.name in selectedBoneNames:
                    selectedBoneNames.append(bone.name)
                    counter += 1

    if len(selectedBoneNames) > 0:
        if 'toolset_pro' in dir(bpy.ops.sparkles) and algorithm=='SMART':
            import sparkles.util
            print("Calling Sparkles Mirror weight groups")
            sparkles.util.smart_mirror_vgroup(context, armobj, obj, selectedBoneNames)
        else:
            print("Calling Karaage Mirror weight groups...")
            for bone_name in selectedBoneNames:
                mirror_name = util.get_mirror_name(bone_name)
                if mirror_name and mirror_name in obj.vertex_groups:
                    mirror_vgroup(context, armobj, obj, bone_name, mirror_name, use_topology)

    armobj.data.bones.active = activeBone
    return counter

def copyBoneWeightsToActiveBone(context, operator):
    obj        = context.object
    armobj     = obj.find_armature()
    activeBone = armobj.data.bones.active
    for bone in armobj.data.bones:
        if bone.select and not bone.hide and bone != activeBone:
            if bone.name not in obj.vertex_groups:
                raise util.Error(_('Source Bone "%s" has no Weightgroup to copy from')%(bone.name))
            if activeBone.name in obj.vertex_groups:
                obj.vertex_groups.remove(obj.vertex_groups[activeBone.name])
            armobj.data.bones.active = bone
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            bpy.ops.object.vertex_group_copy()
            copyName = armobj.data.bones.active.name + "_copy"
            vg = bpy.context.object.vertex_groups[copyName]
            vg.name = activeBone.name
            armobj.data.bones.active = activeBone
            break

MBONE_CVBONE_PAIRS = {
                'mHead'          : 'HEAD',
                'mNeck'          : 'NECK',
                'mChest'         : 'CHEST',

                'mTorso'         : 'BELLY',

                'mPelvis'        : 'PELVIS',

                'mCollarRight'   : 'R_CLAVICLE',
                'mShoulderRight' : 'R_UPPER_ARM',
                'mElbowRight'    : 'R_LOWER_ARM',
                'mWristRight'    : 'R_HAND',

                'mCollarLeft'    : 'L_CLAVICLE',
                'mShoulderLeft'  : 'L_UPPER_ARM',
                'mElbowLeft'     : 'L_LOWER_ARM',
                'mWristLeft'     : 'L_HAND',

                'mHipRight'      : 'R_UPPER_LEG',
                'mKneeRight'     : 'R_LOWER_LEG',
                'mAnkleRight'    : 'R_FOOT',

                'mHipLeft'       : 'L_UPPER_LEG',
                'mKneeLeft'      : 'L_LOWER_LEG',
                'mAnkleLeft'     : 'L_FOOT'
             }

MBONE_CVBONE_LABELS = {
                'mHead'          : 'Head',
                'mNeck'          : 'Neck',
                'mChest'         : 'Chest',
                'mTorso'         : 'Belly',
                'mPelvis'        : 'Pelvis',
                'mCollarRight'   : 'Right Clavicle',
                'mShoulderRight' : 'Right Upper Arm',
                'mElbowRight'    : 'Right Lower Arm',
                'mWristRight'    : 'Right Hand',
                'mCollarLeft'    : 'Left Clavicle',
                'mShoulderLeft'  : 'Left Upper Arm',
                'mElbowLeft'     : 'Left Lower Arm',
                'mWristLeft'     : 'Left Hand',
                'mHipRight'      : 'Right Upper Leg',
                'mKneeRight'     : 'Right Lower Leg',
                'mAnkleRight'    : 'Right Foot',
                'mHipLeft'       : 'Left Upper Leg',
                'mKneeLeft'      : 'Left Lower Leg',
                'mAnkleLeft'     : 'Left Foot',

                'HEAD'           : 'Head',
                'NECK'           : 'Neck',
                'CHEST'          : 'Chest',
                'BELLY'          : 'Belly',
                'PELVIS'         : 'Pelvis',
                'R_CLAVICLE'     : 'Right Clavicle',
                'R_UPPER_ARM'    : 'Right Upper Arm',
                'R_LOWER_ARM'    : 'Right Lower ArM',
                'R_HAND'         : 'Right Hand',
                'L_CLAVICLE'     : 'Left Clavicle',
                'L_UPPER_ARM'    : 'Left Upper Arm',
                'L_LOWER_ARM'    : 'Left Lower Arm',
                'L_HAND'         : 'Left Hand',
                'R_UPPER_LEG'    : 'Right Upper Leg',
                'R_LOWER_LEG'    : 'Right Lower Leg',
                'R_FOOT'         : 'Right Foot',
                'L_UPPER_LEG'    : 'Left Upper Leg',
                'L_LOWER_LEG'    : 'Left Lower Leg',
                'L_FOOT'         : 'Left Foot'
             }

BONE_PAIRS = dict (zip(MBONE_CVBONE_PAIRS.values(),MBONE_CVBONE_PAIRS.keys()))
BONE_PAIRS.update(MBONE_CVBONE_PAIRS)

def get_bone_label(name):
    try:
        return MBONE_CVBONE_LABELS[name]
    except:
        return None

def get_bone_partner(name):
    try:
        return BONE_PAIRS[name]
    except:
        return None

def is_weighted_pair(obj, bname):
    if get_bone_group(obj, bname, create=False):
        if get_bone_partner_group(obj, bname, create=False):

            return True
    return False

def get_bone_partner_group(obj, name, create=True):
    partner_name = get_bone_partner(name)
    pg = get_bone_group(obj, partner_name, create=create) if partner_name else None
    return pg

def get_bone_group(obj, name, create=True):
    group = None
    if obj and name:
        group = None
        if name in obj.vertex_groups:
            group =  obj.vertex_groups[name]
        if group == None and create:
            group = obj.vertex_groups.new(name)
            weights = util.get_weights(obj, group)
            log.info("Created group: %s:%s having %d entries" % (obj.name, name, len(weights)) )
    return group

class FittingValues(bpy.types.PropertyGroup):

    generate_weights = BoolProperty(default=False, name=_("Generate Weights"),
        description=_("For Fitted Mesh: Create weights 'automatic from bone' for BUTT, HANDLES, PECS and BACK") )
    auto_update = BoolProperty(default=True, name=_("Apply auto"),
        description=_("Apply Slider changes immediately to Shape (WARNING: This option needs a lot of computer resources, expect lag)") )
    selected_verts = BoolProperty(default=False, name=_("Only Selected"),
        description=_("Apply Slider changes only to selected vertices (when in edit mode or mask select mode)") )

    butt_strength   = FloatProperty(name = _("Butt"),   min = -1.0, soft_max = 1.0, default = 0,
        update = eval("lambda a,b:updateFittingStrength(a,b,'butt_strength')"),
        description ="Butt Strength")
    pec_strength    = FloatProperty(name = _("Pecs"),    min = -1.0, soft_max = 1.0, default = 0,
        update = eval("lambda a,b:updateFittingStrength(a,b,'pec_strength')"),
        description ="Pec Strength")
    back_strength   = FloatProperty(name = _("Back"),   min = -1.0, soft_max = 1.0, default = 0,
        update = eval("lambda a,b:updateFittingStrength(a,b,'back_strength')"),
        description ="Back Strength")
    handle_strength = FloatProperty(name = _("Handles"), min = -1.0, soft_max = 1.0, default = -1,
        update = eval("lambda a,b:updateFittingStrength(a,b,'handle_strength')"),
        description ="Handle Strength")

    boneSelection = EnumProperty(
        items=(
            ('SELECTED', _('Selected'), _('List Selected Deform Collision Volumes (Fitted Mesh Bones)')),
            ('WEIGHTED', _('Weighted'), _('List Deform Collision Volumes (Fitted Mesh Bones) which also have a weight groups')),
            ('ALL',      _('All'),      _('List all Deform Collision Volumes (Fitted Mesh Bones)'))),
        name=_("Selection"),
        description=_("The set of displayed strength sliders"),
        default='WEIGHTED')

PHYSICS_GROUPS = {'butt_strength' :['BUTT'],
                 'pec_strength'   :['RIGHT_PEC','LEFT_PEC'],
                 'back_strength'  :['UPPER_BACK','LOWER_BACK',],
                 'handle_strength':['RIGHT_HANDLE','LEFT_HANDLE']
                 }

preset_fitting=False
update_fitting=True

class ButtonDeletePhysics(bpy.types.Operator):
    bl_idname = "karaage.delete_physics"
    bl_label = _("Delete physics")
    bl_description = _("Delete Physics weights (Armature rigging style must be 'Fitted Mesh')")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        obj = context.object
        return 'physics' in obj

    def execute(self, context):
        removePhysicsWeights(context.object)
        return {'FINISHED'}

def ShapekeyItemsCallback(scene, context):
    items=[]
    blocks = None
    try:
        blocks = context.object.data.shape_keys.key_blocks
    except:
        pass

    if blocks:
        for key in blocks:
            items.append(
                (key.name, key.name, "relative shapekey top be used")
            )

    return items

class ButtonRebaseShapekey(bpy.types.Operator):
    bl_idname = "karaage.rebase_shapekey"
    bl_label = _("Rebase Shapekey")
    bl_description = _("set relative_key of active Shapekey (set to  neutral_shape by default, change in operator panel)")
    bl_options = {'REGISTER', 'UNDO'}

    relative_key_name = EnumProperty(
        items=ShapekeyItemsCallback,
        name="Relative Key",
        description="Relative Key (shape key parent)"
    )

    @classmethod
    def poll(self, context):
        obj = context.object
        if obj.type != 'MESH': return False
        keys = obj.data.shape_keys
        if keys == None: return False
        blocks = keys.key_blocks
        return blocks != None and len(blocks) >1

    def invoke(self, context, event):
        active_key = context.object.active_shape_key
        if active_key == None:
            active_key = context.object.data.shape_keys.key_blocks[0]
        relative_key_name = active_key.relative_key.name
        return self.execute(context)

    def execute(self, context):
        obj          = context.object
        active_key   = obj.active_shape_key
        rebase_shapekey(context.object, active_key.name, self.relative_key_name)
        return{'FINISHED'}

class ButtonRegeneratePhysics(bpy.types.Operator):
    bl_idname = "karaage.regenerate_physics"
    bl_label = _("Update physics")
    bl_description = _("Update weights for Physics bones preserving physics Slider values (Armature rigging style must be 'Fitted Mesh')")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        status = ButtonGeneratePhysics.generate(self, context, reset=False)
        msg = "Updated Physic Bone Weights (using Bone Heat)"
        self.report({'INFO'},msg)
        return status

class ButtonGeneratePhysics(bpy.types.Operator):
    bl_idname = "karaage.generate_physics"
    bl_label = _("Generate physics")
    bl_description = _("Generate weights for Physics bones (Butt, Pecs, Handles, Back)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        ButtonGeneratePhysics.generate(self, context, reset=True)
        status = ButtonGeneratePhysics.generate(self, context, reset=True)
        msg = "Generated Physic Bone Weights (using Bone Heat)"
        self.report({'INFO'},msg)
        return status

    @staticmethod
    def generate(self, context, reset=True):
        scene = context.scene
        obj   = context.object
        arm   = obj.find_armature()

        obj_mode = util.ensure_mode_is("OBJECT")
        arm.ObjectProp.rig_display_type ='MAP'
        active_bone = arm.data.bones.active

        scene.objects.active = arm
        arm_mode = util.ensure_mode_is("POSE")

        select_backup = util.setSelectOption(arm, SLSHAPEVOLBONES, exclusive=True)
        util.setDeformOption(arm, SLSHAPEVOLBONES, exclusive=False)
        util.ensure_mode_is("OBJECT")
        util.ensure_mode_is("POSE")

        scene.objects.active = obj
        util.createEmptyGroups(obj, names = SLSHAPEVOLBONES)
        util.ensure_mode_is("WEIGHT_PAINT")

        obj.data.use_paint_mask          = False
        obj.data.use_paint_mask_vertex   = False
        try:
            props = obj.FittingValues
            if "physics" in obj:
                del obj['physics']

            bpy.ops.paint.weight_from_bones() #Take care that the weight groups exist before calling this operator!
            util.ensure_mode_is("OBJECT")

            if reset:

                setPresetFitting(True)
                props.butt_strength   = 0
                props.pec_strength    = 0
                props.back_strength   = 0
                props.handle_strength = -1
                setPresetFitting(False)

            scale_level(obj, props.butt_strength,   ['BUTT'])
            scale_level(obj, props.pec_strength,    ['RIGHT_PEC','LEFT_PEC'])
            scale_level(obj, props.back_strength,   ['UPPER_BACK','LOWER_BACK'])
            scale_level(obj, props.handle_strength, ['RIGHT_HANDLE','LEFT_HANDLE'])

        except Exception as e:
            util.restoreSelectOption(arm, select_backup)
            bpy.context.scene.objects.active = obj
            util.ensure_mode_is(obj_mode, object=obj)
            util.ensure_mode_is(arm_mode, object=arm)
            print("Could not generate weights for Physic bones")
            util.ErrorDialog.exception(e)
            return{'CANCELLED'}

        if active_bone:
            if not active_bone.name in obj.vertex_groups:
                if get_bone_partner_group(obj, active_bone.name, create=False):
                    active_bone = arm.data.bones[get_bone_partner(active_bone.name)]
                else:
                    active_bone = None
        if active_bone:
            arm.data.bones.active=active_bone

        util.restoreSelectOption(arm, select_backup)
        util.ensure_mode_is(arm_mode, object=arm)

        bpy.context.scene.objects.active = obj
        util.ensure_mode_is("OBJECT", object=obj)
        util.ensure_mode_is(obj_mode, object=obj)

        return{'FINISHED'}

def add_fitting_preset(context, filepath):
    obj    = context.object

    file_preset = open(filepath, 'w')
    file_preset.write(
    "#Generated by Karaage %s with Blender %s\n"
    "import bpy\n"
    "import karaage\n"
    "from karaage import weights, shape\n"
    "\n"
    "context= bpy.context\n"
    "obj    = context.object\n"
    "armobj = obj.find_armature()\n"
    "weights.setUpdateFitting(False)\n"
    "\n"  % (util.get_addon_version(), bpy.app.version_string)
    )
    for key, val in obj.FittingValues.items():
        if key in ['boneSelection','auto_update']:
            continue
        file_preset.write("obj.FittingValues.%s=%s\n"%(key,val))

    file_preset.write(
    "\n"
    "weights.setUpdateFitting(True)\n"
    "boneNames = [bone.name for bone in armobj.data.bones]\n"
    "remove_only_empty_groups=True\n"
    "weights.removeBoneWeightGroupsFromSelectedBones(context.object, remove_only_empty_groups, boneNames)\n"
    "shape.refresh_shape(obj.find_armature(),obj, graceful=True)\n"
    "\n"
    )
    file_preset.close()

class KARAAGE_MT_fitting_presets_menu(Menu):
    bl_idname = "karaage_fitting_presets_menu"
    bl_label  = "Fitting Presets"
    bl_description = "Fitting Presets for custom attachments"
    preset_subdir = os.path.join("karaage","fittings")
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset

class KaraageAddPresetFitting(AddPresetBase, Operator):
    bl_idname = "karaage.fitting_presets_add"
    bl_label = "Add Fitting Preset"
    bl_description = "Create new Preset from current Fitting Slider settings"
    preset_menu = "karaage_fitting_presets_menu"

    preset_subdir = os.path.join("karaage","fittings")

    def invoke(self, context, event):
        print("Create new Preset...")
        return AddPresetBase.invoke(self, context, event)

    def add(self, context, filepath):
        add_fitting_preset(context, filepath)

class KaraageUpdatePresetFitting(AddPresetBase, Operator):
    bl_idname = "karaage.fitting_presets_update"
    bl_label = "Update Fitting Preset"
    bl_description = "Store current Slider settings in last selected Preset"
    preset_menu = "karaage_fitting_presets_menu"
    preset_subdir = os.path.join("karaage","fittings")

    def invoke(self, context, event):
        self.name = bpy.types.karaage_fitting_presets_menu.bl_label
        print("Updating Preset", self.name)
        return self.execute(context)

    def add(self, context, filepath):
        add_fitting_preset(context, filepath)

class KaraageRemovePresetFitting(AddPresetBase, Operator):
    bl_idname = "karaage.fitting_presets_remove"
    bl_label = "Remove Fitting Preset"
    bl_description = "Remove last selected Preset from the list"
    preset_menu = "karaage_fitting_presets_menu"
    preset_subdir = os.path.join("karaage","fittings")

def setPresetFitting(state):
    global preset_fitting
    preset_fitting = state

def setUpdateFitting(state):
    global update_fitting
    update_fitting = state

def updateFittingStrength(self, context, bone_name=None):
    global preset_fitting
    global update_fitting
    if preset_fitting:
        return
    obj   = context.object
    omode = obj.mode if obj.mode !='EDIT' else util.ensure_mode_is("OBJECT")
    original_group = obj.vertex_groups.active
    
    if bone_name in PHYSICS_GROUPS.keys():
        try:

            scale_level(obj, obj.FittingValues[bone_name],  PHYSICS_GROUPS[bone_name])
            active_group = get_bone_group(obj,PHYSICS_GROUPS[bone_name][0], create=False)

        except Exception as e:
            print("Could not generate weights for Physic bones")
            util.ErrorDialog.exception(e)
            return
    else:
        only_selected = util.update_only_selected_verts(obj, omode)
        percent       = getattr(obj.FittingValues, bone_name)
        active_group  = set_fitted_strength(context, obj, bone_name, percent, only_selected, omode)

    util.ensure_mode_is(omode)

    if active_group:
        obj.vertex_groups.active_index = active_group.index
    else:
        obj.vertex_groups.active_index = -1

    armobj  = obj.find_armature()
    if update_fitting and self.auto_update and obj.ObjectProp.slider_selector!='NONE':

        if active_group:
            bone_name = active_group.name
        elif armobj.data.bones.active:
            bone_name = armobj.data.bones.active.name
        else:
            bone_name = None

        if bone_name:
            b = armobj.data.bones[bone_name]
            pname = get_bone_partner(bone_name)
            b.use_deform=True
            if pname:
                c = armobj.data.bones[pname]
                c.use_deform=True

        shape.refresh_shape(obj.find_armature(),obj, graceful=True)
        if bone_name:
            armobj.data.bones.active = armobj.data.bones[bone_name]
        util.enforce_armature_update(context.scene,armobj)

    if armobj.ObjectProp.rig_display_type == 'MAP':

        armobj['rig_display_mesh_count'] = 0
    util.ensure_mode_is(omode)

def setup_fitting_values():
    for bname in MBONE_CVBONE_PAIRS.values():
        exist = getattr(FittingValues, bname, None)
        if exist is None:
            setattr(FittingValues, bname,
                    FloatProperty(name = bname,
                                  update = eval("lambda a,b:updateFittingStrength(a,b,'%s')"%bname),
                                  min      = 0, max      = 1.0,
                                  soft_min = 0, soft_max = 1.0,
                                  default = 1.0))

def classic_fitting_preset(obj):
    setPresetFitting(True)
    armobj = obj.find_armature()
    if armobj:
        for bone in MBONE_CVBONE_PAIRS.values():
            setattr(obj.FittingValues,bone,0)
    setPresetFitting(False)

def fitmesh_fitting_preset(obj):
    setPresetFitting(True)
    armobj = obj.find_armature()
    if armobj:
        for bone in MBONE_CVBONE_PAIRS.values():
            if bone in obj.vertex_groups:
                setattr(obj.FittingValues,bone,1)
            else:
                setattr(obj.FittingValues,bone,0)
    setPresetFitting(False)

def fittingInitialisation():
    bpy.types.Object.FittingValues  = PointerProperty(type = FittingValues)
    setup_fitting_values()

def moveDeform2Collision(obj, adjust_deform = False):
    armobj    = obj.find_armature()
    bones = [b.name for b in armobj.data.bones if b.name.startswith("m")]
    moveBones(obj, bones, adjust_deform)

def moveCollision2Deform(obj, adjust_deform = False):
    armobj    = obj.find_armature()
    bones = [b.name for b in armobj.data.bones if not b.name.startswith("m")]
    moveBones(obj, bones, adjust_deform)

def moveBones(obj, bones, adjust_deform = False):
    print("moveBones:",bones, "object=", obj.name, "type=", obj.type)
    active    = bpy.context.scene.objects.active
    armobj    = obj.find_armature()

    bpy.context.scene.objects.active=obj
    original_mode = util.ensure_mode_is("WEIGHT_PAINT")

    success   = 0

    for bone_name in bones:
        bone = armobj.data.bones[bone_name]
        if not bone.hide and bone.name in BONE_PAIRS and bone.name in obj.vertex_groups:
            pbone = armobj.data.bones[BONE_PAIRS[bone.name]]
            print("Move weights %s -> %s" % (bone.name, pbone.name))
            if pbone.name in obj.vertex_groups:
                util.removeWeightGroups(obj, [pbone.name])

            group      = obj.vertex_groups[bone.name]
            group.name = pbone.name
            success +=1
            if adjust_deform:
                bone.use_deform  = False
                bone.layers[B_LAYER_DEFORM]  = False
                bone.select      = False
            pbone.use_deform = True
            pbone.layers[B_LAYER_DEFORM] = True
            pbone.select     = True
            success  += 1

    if success > 0:
        util.ensure_mode_is('OBJECT')
        util.ensure_mode_is('WEIGHT_PAINT')
    util.ensure_mode_is(original_mode)

    bpy.context.scene.objects.active=active

def swapCollision2Deform(obj, adjust_deform = False, keep_groups=False):
    print("SwapCollision2Deform object=", obj.name, "type=", obj.type)
    active    = bpy.context.scene.objects.active
    armobj    = obj.find_armature()

    bpy.context.scene.objects.active=obj
    original_mode = util.ensure_mode_is("WEIGHT_PAINT")

    bones     = [b.name for b in armobj.data.bones if b.select]
    processed = []

    success   = 0
    noweights = 0
    nobone    = 0

    for bone_name in bones:
        bone = armobj.data.bones[bone_name]
        if not (bone.hide or bone.name in processed):

            if bone.name not in BONE_PAIRS:
                print(_('Bone "%s" has no paired bone')%(bone.name))
                nobone += 1
            else:
                pbone = armobj.data.bones[BONE_PAIRS[bone.name]]
                print("Processing %s - %s" % (pbone.name, bone.name))
                if bone.name not in obj.vertex_groups:
                    if pbone.name in obj.vertex_groups:
                        vgroup      = obj.vertex_groups[pbone.name]
                        vgroup.name = bone.name
                        if keep_groups:
                            obj.vertex_groups.new(pbone.name)
                        success +=1
                        if adjust_deform:
                            pbone.use_deform = False
                            pbone.layers[B_LAYER_DEFORM] = False
                        bone.use_deform  = True
                        bone.layers[B_LAYER_DEFORM]  = True
                        bone.select      = True
                        print ("moved weights from %s to %s" % (pbone.name, bone.name))
                    else:
                        noweights += 1
                elif pbone.name not in obj.vertex_groups:
                    if bone.name in obj.vertex_groups:
                        vgroup      = obj.vertex_groups[bone.name]
                        vgroup.name = pbone.name
                        if keep_groups:
                            obj.vertex_groups.new(bone.name)
                        success +=1
                        if adjust_deform:
                            bone.use_deform   = False
                            bone.layers[B_LAYER_DEFORM]   = False
                        pbone.use_deform  = True
                        pbone.layers[B_LAYER_DEFORM]  = True
                        pbone.select      = True
                        print ("moved weights from %s to %s" % (bone.name, pbone.name))
                    else:
                        noweights += 1
                else:
                    print ("swapping weights of %s <--> %s" % (bone.name, BONE_PAIRS[bone.name]))
                    from_group      = obj.vertex_groups[bone.name]
                    to_group        = obj.vertex_groups[pbone.name]
                    to_group.name   = to_group.name + "_tmp"
                    from_group.name = pbone.name
                    to_group.name   = bone.name
                    success +=1
                    bone.use_deform  = True
                    bone.layers[B_LAYER_DEFORM]  = True
                    pbone.use_deform = True
                    pbone.layers[B_LAYER_DEFORM] = True
                    bone.select      = True
                    pbone.select     = True

                processed.append(bone.name)
                processed.append(pbone.name)

    if success > 0:
        util.ensure_mode_is('OBJECT')
        util.ensure_mode_is('WEIGHT_PAINT')
    util.ensure_mode_is(original_mode)

    bpy.context.scene.objects.active=active
    return nobone

def mirror_vgroup(context, armobj, obj, bone_name, mirror_name, use_topology):

    if bone_name in obj.vertex_groups:
        obj.vertex_groups.remove(obj.vertex_groups[bone_name])
    original_select = armobj.data.bones[mirror_name].select

    armobj.data.bones.active = armobj.data.bones[mirror_name]
    armobj.data.bones.active.select = True
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    bpy.ops.object.vertex_group_copy()
    bpy.ops.object.vertex_group_mirror(use_topology=use_topology)
    bpy.ops.object.vertex_group_clean()
    vg = bpy.context.object.vertex_groups[mirror_name+"_copy"]
    vg.name = bone_name
    armobj.data.bones.active = armobj.data.bones[bone_name]
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    armobj.data.bones[mirror_name].select = original_select
    print("mirrored from %s -> %s"%(mirror_name,bone_name))

def getWeights(target_ob, source_ob, point, submesh = False, restrictTo=None):

    M = target_ob.matrix_world
    p = M.inverted()*point

    status, loc, face_normal, face_index = util.closest_point_on_mesh(target_ob, p)

    target_me = target_ob.data
    target_verts  = target_me.vertices

    target_poly= target_me.polygons[face_index]
    gdata = {}

    if submesh:
        dmin = (p-loc).length

        vw = interpolation(target_ob, target_poly, loc)

        for vidx, interpw in vw.items():

            v = target_verts[vidx]

            for grp in v.groups:
                grp_index = grp.group
                source_group = source_ob.vertex_groups[grp_index]
                if not source_group:
                    print ("Copy weights from %s.%s to %s failed" % (source_ob.name, grp.group, target_ob.name) )
                else:
                    gname = source_group.name
                    if  restrictTo==None or gname in restrictTo:
                        weight = grp.weight
                        oldweight = gdata.get(gname, 0)
                        gdata[gname] = oldweight + weight*interpw

    else:

        vtx = min(target_poly.vertices, key=lambda v: (p - target_verts[v].co).length)

        v = target_verts[vtx]
        dmin = (v.co-p).length

        for grp in v.groups:
            gname = source_ob.vertex_groups[grp.group].name
            if  restrictTo==None or gname in restrictTo:
                weight = grp.weight
                gdata[gname] = weight

    return dmin, gdata

def interpolation(obj, polygon, loc):

    SMALLEST_DISTANCE = 1e-5
    SMALLEST_WSUM     = 1e-8

    D = 0
    for v1idx in polygon.vertices:
        v1 = obj.data.vertices[v1idx]
        for v2idx in polygon.vertices:
            v2 = obj.data.vertices[v2idx]
            if v1idx!=v2idx:
                d = (v1.co-v2.co).length
                D = max(D,d)
    sigma = D

    on_vertex = None
    weights = {}
    N = 0
    for vidx in polygon.vertices:
        v = obj.data.vertices[vidx]
        d = (loc-v.co).length

        if d < SMALLEST_DISTANCE:
            on_vertex = vidx
            break
        else:
            w = exp(-(d/sigma)**2)
            weights[vidx] = w
            N += w

    if on_vertex is None and N < SMALLEST_WSUM:
        on_vertex = polygon.vertices[0]

    if on_vertex is None:
        for vidx in weights:
            weights[vidx] = weights[vidx]/N
    else:
        for vidx, w in weights.items():
            weights[vidx] = 0.0
        weights[on_vertex] = 1.0

    return weights

def copyBoneWeightsToSelectedBones(target, sources, selectedBoneNames, submeshInterpolation=True, allVerts=True, clearTargetWeights=True):
    context = bpy.context
    scene   = context.scene
    armobj = target.find_armature()
    original_mode = util.ensure_mode_is("WEIGHT_PAINT", object=target)
    if selectedBoneNames == None:
        selectedBoneNames = target.vertex_groups.keys()
        
    clones = []
    clean_target_groups = []
    print("Copy weights found %d animated mesh objects and %d target bones" % (len(sources), len(selectedBoneNames)) )
    for childobj in sources:
        if not childobj==target and not childobj.name.startswith('CustomShape_'):

            print("Found weight source [", childobj.name, "]")
            childmesh = childobj.to_mesh(scene, True, 'PREVIEW')
            childmesh.update(calc_tessface=True)
            childcopyobj = bpy.data.objects.new(childobj.name, childmesh)
            childcopyobj.matrix_world = childobj.matrix_world.copy()
            scene.objects.link(childcopyobj)
            clones.append((childcopyobj, childobj))

    if len(clones) == 0:
        raise "Please ensure that at least one part of the Karaage mesh is visible.\n Then try again."

    scene.update()

    M=target.matrix_world

    for vertex in target.data.vertices:
        if allVerts or vertex.select:
            vs = []
            pt = M*vertex.co

            for source in clones:

                d, gdata = getWeights(source[0], source[1], pt, submeshInterpolation, selectedBoneNames)
                vs.append((d,gdata))

            vmin = min(vs, key=lambda v: v[0])

            copied=[]
            for gn,w in vmin[1].items():
                if gn in selectedBoneNames:
                    copied.append(gn)
                    if clearTargetWeights and allVerts and gn in target.vertex_groups and gn not in clean_target_groups:
                        target.vertex_groups.remove(target.vertex_groups[gn])

                    if gn not in target.vertex_groups:
                        target.vertex_groups.new(gn)
                        clean_target_groups.append(gn)

                    target.vertex_groups[gn].add([vertex.index], w, 'REPLACE')

            if clearTargetWeights and not allVerts:
                gnames = [gn for gn in selectedBoneNames if gn in target.vertex_groups and gn not in copied]
                for gn in gnames:
                    target.vertex_groups[gn].remove([vertex.index])

    for childcopyobj, childobj in clones:
        scene.objects.unlink(childcopyobj)
        bpy.data.objects.remove(childcopyobj)

    util.ensure_mode_is("OBJECT", object=target)
    util.ensure_mode_is(original_mode, object=target)
    return len(selectedBoneNames)

def draw(op, context):
    layout = op.layout
    scn = context.scene

    box = layout.box()
    box.label(text=_("Weight Copy settings"))
    col = box.column(align=True)
    col.prop(op, 'submeshInterpolation')
    col.prop(op, 'cleanVerts')
    col.prop(op, 'allVisibleBones')
    col.prop(op, 'allHiddenBones')

def get_bones_from_armature(armobj, allVisibleBones, allHiddenBones):
    if allVisibleBones:
        boneNames = util.getVisibleBoneNames(armobj)
    else:
        boneNames = util.getVisibleSelectedBoneNames(armobj)
    if allHiddenBones:
        boneNames.extend(util.getHiddenBoneNames(armobj))
    return boneNames

def create_message(op, context, template):

    ss=" "
    if op.onlySelectedVerts:
        ss=" masked "

    tgt = "selected"
    if op.allVisibleBones and op.allHiddenBones:
       tgt = "all"
    elif op.allVisibleBones:
       tgt = "all visible"
    elif op.allHiddenBones:
       tgt += " + hidden"

    msg = template % (ss, tgt)
    return msg

def contains_weights(obj, vgroup):
    vertices = obj.data.vertices
    for v in vertices:
        for group in v.groups:
            if group.group == vgroup.index and group.weight > 0:
                return True
    return False

def removePhysicsWeights(obj):
    bone_names = []
    for names in PHYSICS_GROUPS.values():
        bone_names.extend(names)
    removeBoneWeightGroupsFromSelectedBones(obj, False, bone_names)
    if 'physics' in obj:
        del obj['physics']

def removeBoneWeightGroupsFromSelectedBones(obj, empty, bone_names, remove_nondeform=False):
    armobj        = obj.find_armature()
    c = 0

    if remove_nondeform:
        for name in [name for name in obj.vertex_groups.keys() if not name in armobj.data.bones.keys()]:
            group = obj.vertex_groups[name]
            obj.vertex_groups.active_index=group.index
            bpy.ops.object.vertex_group_remove()
            c+=1
            print("Removed non deforming Weight group",name)

    if bone_names:
        target_names = [name for name in bone_names if name in obj.vertex_groups]
    else:
        target_names = [g.name for g in obj.vertex_groups]

    for name in target_names:
        group = obj.vertex_groups[name]
        if (not empty or not contains_weights(obj, group)):
            obj.vertex_groups.active_index=group.index
            bpy.ops.object.vertex_group_remove()
            c += 1
    return c

def removeBoneWeightsFromSelectedBones(context, operator, allVerts, boneNames):
    obj           = context.object
    armobj        = obj.find_armature()
    activeBone    = armobj.data.bones.active
    original_mode = util.ensure_mode_is('EDIT')
    counter       = 0
    for bone in [b for b in armobj.data.bones if b.name in boneNames and b.name in obj.vertex_groups]:
        armobj.data.bones.active = bone
        bpy.ops.object.vertex_group_set_active(group=bone.name)
        if allVerts:
            bpy.ops.object.vertex_group_select()
        bpy.ops.object.vertex_group_remove_from()
        counter += 1

    armobj.data.bones.active = activeBone
    util.ensure_mode_is(original_mode)
    return counter

class ButtonCopyBoneWeights(bpy.types.Operator):
    bl_idname = "karaage.copy_bone_weights"
    bl_label = _("Copy Weights")
    bl_description = _("Various Copy tools operating on Bone weight groups")
    bl_options = {'REGISTER', 'UNDO'}

    weightCopyAlgorithm = StringProperty()

    weightCopyType = EnumProperty(
        items=(
            ('ATTACHMENT', _('from Attachments'),     _('Copy bone weights from same bones of other attachments')),
            ('MIRROR',     _('from Opposite Bones'),  _('Copy bone Weights from opposite bones of same object')),
            ('BONES',      _('selected to active'),   _('Copy bone weights from selected bone to active bone (needs exactly 2 selected bones) ')),
            ('CLEAR',      _('Clear selected bones'), _('remove bone weights from selected bones ')),
            ('SWAP',       _('Collision <-> SL'),     _('Exchange weights of selected Collision volumes with weights from associted SL Bones'))),
        name=_("Copy"),
        description=_("Method for Bone Weight transfer"),
        default='ATTACHMENT')

    submeshInterpolation = BoolProperty(default=True, name=_("Sub-mesh interpolation"),
        description=_("Interpolate the weight values from closests point on surface of reference mesh") )

    onlySelectedVerts = BoolProperty(default=False, name=_("Only selected vertices"),
        description=_("Copy weights only to selected vertices in the target mesh"))

    allVisibleBones = BoolProperty(default=False, name=_("Include all visible bones"),
        description=_("Copy Weights from all visbile Bones. If not set, then copy only from selected Bones"))

    allHiddenBones = BoolProperty(default=False, name=_("Include All hidden bones"),
        description=_("Copy Weights from all hidden Bones. If not set, then copy only from selected Bones"))

    cleanVerts = BoolProperty(default=False, name=_("Clean Targets"),
        description=_("Clean Target vertex Groups before performnig the copy action"))

    weight_eye_bones = BoolProperty(default=False, name=_("With Eye Bones"),
        description=_("Generate Weights also for Eye Bones") )

    def invoke(self, context, event):
        meshProps = context.scene.MeshProp
        submeshInterpolation = meshProps.submeshInterpolation
        ob = bpy.context.object
        me = ob.data
        if ob.mode=='EDIT' or me.use_paint_mask_vertex or me.use_paint_mask:
            self.onlySelectedVerts = True
        else:
            self.onlySelectedVerts = False
        return self.execute(context)

    def execute(self, context):
        meshProps = context.scene.MeshProp

        try:
            if self.weightCopyType == "BONES":
                copyBoneWeightsToActiveBone(context, self)
                self.report({'INFO'}, _("Copied Selected bone to Active bone"))

            elif self.weightCopyType =="SWAP":
                if bpy.context.selected_pose_bones is None:
                    self.report({'WARNING'}, _("Please select at least 1 bone"))
                else:
                    obj = context.object
                    c   = swapCollision2Deform(obj)
                    if c > 0:
                        self.report({'WARNING'}, _("Swap failed for %d bones" % (c)))

            else:
                obj       = context.object
                armobj    = obj.find_armature()
                boneNames = get_bones_from_armature(armobj, self.allVisibleBones, self.allHiddenBones)

                if self.weightCopyType == "CLEAR":
                    c = removeBoneWeightsFromSelectedBones(context, self, boneNames)
                    self.report({'INFO'},"Removed %d Groups from %s" %(c, armobj.name) )
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonClearBoneWeightGroups(bpy.types.Operator):
    bl_idname = "karaage.clear_bone_weight_groups"
    bl_label = _("Remove Weight Groups")
    bl_description = \
'''Remove Weight Maps from Active Object (or selection)

- If called in Object mode, all selected Mesh objects are affected.
- More selection options can be set in the Operator Redo Panel'''
    bl_options = {'REGISTER', 'UNDO'}

    allVisibleBones = BoolProperty(default=True, name=_("Include Visible bones"),
        description=_("Delete weight maps of all visible bones"))

    allHiddenBones = BoolProperty(default=True, name=_("Include Hidden bones"),
        description=_("Delete weight maps of all hidden bones"))

    allNonDeforming = BoolProperty(default=False, name=_("Remove non Deforming Weight Maps"),
        description=_("Delete all weight maps which do not belong to Defrom Bones"))

    empty = BoolProperty(default=True, name=_("Only Empty weightmaps"),
        description=_("Delete empty weight maps"))

    all_selected = BoolProperty(
        name = "Apply to Selected",
        default = False, 
        description = "Apply the Operator to the current selection" )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text=_("Weight Tools"), icon='WPAINT_HLT')

        obj       = context.object
        armobj    = obj.find_armature()
        if armobj:
            col = box.column()
            col.prop(self, "allVisibleBones")
            col.prop(self, "allHiddenBones")
            col.prop(self, "allNonDeforming")
            if context.mode == 'OBJECT':
                col.prop(self, "all_selected", text = 'All Selected Objects')

        col = box.column()
        col.prop(self, "empty")

    def execute(self, context):
        active = context.object
        armobj = active.find_armature()
        if context.mode == 'OBJECT':
            if self.all_selected:
                if armobj:
                    selection = util.get_animated_meshes(context, armobj, only_selected=True)
                else:
                    selection = [o for o in context.scene.objects if o.select and o.type=='MESH']
            else:
                selection = [active]
        else:
            selection = [active]

        if armobj:
            boneNames = get_bones_from_armature(armobj, self.allVisibleBones, self.allHiddenBones)
            target_name = armobj.name
        else:
            boneNames = None
            target_name = None

        for obj in selection:
            context.scene.objects.active = obj
            c = removeBoneWeightGroupsFromSelectedBones(obj, self.empty, boneNames, remove_nondeform=self.allNonDeforming)
            if c > 0:
                msg = "Removed %d weight maps from %s" % (c, obj.name)
            else:
                msg = "No maps removed from %s" % obj.name
            log.info(msg)
            self.report({'INFO'},msg)
        context.scene.objects.active = active
        return{'FINISHED'}

class ButtonClearBoneWeights(bpy.types.Operator):
    bl_idname = "karaage.clear_bone_weights"
    bl_label = _("Remove Weights")
    bl_description = _("Remove all weights from weight groups of selected bones")
    bl_options = {'REGISTER', 'UNDO'}

    submeshInterpolation = BoolProperty(default=True, name=_("Sub-mesh interpolation"),
        description=_("Interpolate the weight values from closests point on surface of reference mesh") )

    onlySelectedVerts = BoolProperty(default=False, name=_("Only selected vertices"),
        description=_("Copy weights only to selected vertices in the target mesh"))

    allVisibleBones = BoolProperty(default=False, name=_("Include all visible bones"),
        description=_("Copy Weights from all visbile Bones. If not set, then copy only from selected Bones"))

    allHiddenBones = BoolProperty(default=False, name=_("Include All hidden bones"),
        description=_("Copy Weights from all hidden Bones. If not set, then copy only from selected Bones"))

    cleanVerts = BoolProperty(default=False, name=_("Clean Targets"),
        description=_("Clean Target vertex Groups before performnig the copy action"))

    def invoke(self, context, event):
        meshProps = context.scene.MeshProp
        submeshInterpolation = meshProps.submeshInterpolation
        ob = bpy.context.object
        me = ob.data
        if ob.mode=='EDIT' or me.use_paint_mask_vertex or me.use_paint_mask:
            self.onlySelectedVerts = True
        else:
            self.onlySelectedVerts = False
        return self.execute(context)

    def execute(self, context):
        try:
            obj       = context.object
            armobj    = obj.find_armature()
            boneNames = get_bones_from_armature(armobj, self.allVisibleBones, self.allHiddenBones)

            c = removeBoneWeightsFromSelectedBones(context, self, not self.onlySelectedVerts, boneNames)
            if self.onlySelectedVerts:
                activeBone    = armobj.data.bones.active
            msg = create_message(self, context, _("Cleared%sweights in %s Bones"))
            self.report({'INFO'},msg)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonSwapWeights(bpy.types.Operator):
    bl_idname = "karaage.swap_bone_weights"
    bl_label = _("Swap Collision & Deform")
    bl_description = _("Swap weights of Collision Volumes and corresponding Classic Bones")
    bl_options = {'REGISTER', 'UNDO'}

    submeshInterpolation = BoolProperty(default=True, name=_("Sub-mesh interpolation"),
        description=_("Interpolate the weight values from closests point on surface of reference mesh") )

    onlySelectedVerts = BoolProperty(default=False, name=_("Only selected vertices"),
        description=_("Copy weights only to selected vertices in the target mesh"))

    allVisibleBones = BoolProperty(default=False, name=_("Include all visible bones"),
        description=_("Copy Weights from all visbile Bones. If not set, then copy only from selected Bones"))

    allHiddenBones = BoolProperty(default=False, name=_("Include All hidden bones"),
        description=_("Copy Weights from all hidden Bones. If not set, then copy only from selected Bones"))

    cleanVerts = BoolProperty(default=False, name=_("Clean Targets"),
        description=_("Clean Target vertex Groups before performnig the copy action"))

    def draw(self, context):
        draw(self, context)

    def invoke(self, context, event):
        meshProps = context.scene.MeshProp
        submeshInterpolation = meshProps.submeshInterpolation
        ob = bpy.context.object
        me = ob.data
        if ob.mode=='EDIT' or me.use_paint_mask_vertex or me.use_paint_mask:
            self.onlySelectedVerts = True
        else:
            self.onlySelectedVerts = False
        return self.execute(context)

    def execute(self, context):
        meshProps = context.scene.MeshProp

        try:
            if bpy.context.selected_pose_bones is None:
                self.report({'WARNING'}, _("Please select at least 1 bone"))
            else:
                obj = context.object
                c   = swapCollision2Deform(obj)
                if c > 0:
                    self.report({'WARNING'}, _("Swap failed for %d bones" % (c)))
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonMirrorBoneWeights(bpy.types.Operator):
    bl_idname = "karaage.mirror_bone_weights"
    bl_label = _("Mirror opposite Bones")
    bl_description = _("Mirror Weights from opposite side")
    bl_options = {'REGISTER', 'UNDO'}

    weightCopyAlgorithm = StringProperty()

    submeshInterpolation = BoolProperty(default=True, name=_("Sub-mesh interpolation"),
        description=_("Interpolate the weight values from closests point on surface of reference mesh") )

    onlySelectedVerts = BoolProperty(default=False, name=_("Only selected vertices"),
        description=_("Mirror weights only to selected vertices in the target mesh"))

    allVisibleBones = BoolProperty(default=False, name=_("Include all visible bones"),
        description=_("Mirror Weights from all visbile Bones. If not set, then mirror only from selected Bones"))

    allHiddenBones = BoolProperty(default=False, name=_("Include All hidden bones"),
        description=_("Mirror Weights from all hidden Bones. If not set, then mirror only from selected Bones"))

    cleanVerts = BoolProperty(default=False, name=_("Clean Targets"),
        description=_("Clean Target vertex Groups before performnig the mirror action"))

    def draw(self, context):
        layout = self.layout
        scn = context.scene

        box = layout.box()
        box.label(text=_("Weight Mirror settings"))
        col = box.column(align=True)
        col.prop(self, 'submeshInterpolation')
        col.prop(self, 'cleanVerts')
        col.prop(self, 'allVisibleBones')
        col.prop(self, 'allHiddenBones')

    def invoke(self, context, event):
        meshProps = context.scene.MeshProp
        submeshInterpolation = meshProps.submeshInterpolation
        ob = bpy.context.object
        me = ob.data
        if ob.mode=='EDIT' or me.use_paint_mask_vertex or me.use_paint_mask:
            self.onlySelectedVerts = True
        else:
            self.onlySelectedVerts = False
        return self.execute(context)

    def execute(self, context):
        meshProps = context.scene.MeshProp

        try:
            c = mirrorBoneWeightsFromOppositeSide(context, self, context.object.data.use_mirror_topology, algorithm=self.weightCopyAlgorithm)
            self.report({'INFO'}, _("Mirrored %d bones from Opposite" % (c)))
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonCopyWeightsFromRigged(bpy.types.Operator):
    bl_idname = "karaage.copy_weights_from_rigged"
    bl_label = _("Copy from Rigged")
    bl_description = _("Copy weights from other Mesh objects rigged to same Armature")
    bl_options = {'REGISTER', 'UNDO'}

    submeshInterpolation = BoolProperty(default=True, name=_("Sub-mesh interpolation"),
        description=_("Interpolate the weight values from closests point on surface of reference mesh") )

    onlySelectedVerts = BoolProperty(default=False, name=_("Only selected vertices"),
        description=_("Copy weights only to selected vertices in the target mesh"))

    allVisibleBones = BoolProperty(default=False, name=_("Include all visible bones"),
        description=_("Copy Weights from all visbile Bones. If not set, then copy only from selected Bones"))

    allHiddenBones = BoolProperty(default=False, name=_("Include All hidden bones"),
        description=_("Copy Weights from all hidden Bones. If not set, then copy only from selected Bones"))

    cleanVerts = BoolProperty(default=False, name=_("Clean Targets"),
        description=_("Clean Target vertex Groups before performnig the copy action"))

    def invoke(self, context, event):
        meshProps = context.scene.MeshProp
        self.submeshInterpolation = meshProps.submeshInterpolation
        ob = bpy.context.object
        me = ob.data
        if ob.mode=='EDIT' or me.use_paint_mask_vertex or me.use_paint_mask:
            self.onlySelectedVerts = True
        else:
            self.onlySelectedVerts = False
        return self.execute(context)

    def execute(self, context):
        meshProps = context.scene.MeshProp

        try:
            obj       = context.object
            armobj    = obj.find_armature()
            boneNames = get_bones_from_armature(armobj, self.allVisibleBones, self.allHiddenBones)
            sources = util.get_animated_meshes(context, armobj)
            copyBoneWeightsToSelectedBones(obj, sources, boneNames, self.submeshInterpolation, allVerts=not self.onlySelectedVerts, clearTargetWeights=self.cleanVerts)
            msg = create_message(self, context, _("Copied%sweights from visible siblings and %s Weight Groups"))
            self.report({'INFO'}, msg)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonCopyWeightsFromSelected(bpy.types.Operator):
    bl_idname = "karaage.copy_weights_from_selected"
    bl_label = _("Copy from Selected")
    bl_description = _("Copy weights from Selected Mesh objects.")
    bl_options = {'REGISTER', 'UNDO'}

    submeshInterpolation = BoolProperty(default=True, name=_("Sub-mesh interpolation"),
        description=_("Interpolate the weight values from closests point on surface of reference mesh") )

    onlySelectedVerts = BoolProperty(default=False, name=_("Only selected vertices"),
        description=_("Copy weights only to selected vertices in the target mesh"))

    allVisibleBones = BoolProperty(default=False, name=_("Include all visible bones"),
        description=_("Copy Weights from all visbile Bones. If not set, then copy only from selected Bones"))

    allHiddenBones = BoolProperty(default=False, name=_("Include All hidden bones"),
        description=_("Copy Weights from all hidden Bones. If not set, then copy only from selected Bones"))

    cleanVerts = BoolProperty(default=False, name=_("Clean Targets"),
        description=_("Clean Target vertex Groups before performnig the copy action"))

    def invoke(self, context, event):
        meshProps = context.scene.MeshProp
        self.submeshInterpolation = meshProps.submeshInterpolation
        ob = bpy.context.object
        me = ob.data
        if ob.mode=='EDIT' or me.use_paint_mask_vertex or me.use_paint_mask:
            self.onlySelectedVerts = True
        else:
            self.onlySelectedVerts = False
        return self.execute(context)

    def execute(self, context):
        meshProps = context.scene.MeshProp

        try:
            obj       = context.object
            armobj    = obj.find_armature()
            boneNames = get_bones_from_armature(armobj, self.allVisibleBones, self.allHiddenBones)
            sources = context.selected_objects
            copyBoneWeightsToSelectedBones(obj, sources, boneNames, self.submeshInterpolation, allVerts=not self.onlySelectedVerts, clearTargetWeights=self.cleanVerts)
            msg = create_message(self, context, _("Copied%sweights from visible siblings and %s Weight Groups"))
            self.report({'INFO'}, msg)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}
            
class ButtonWeldWeightsFromRigged(bpy.types.Operator):
    bl_idname = "karaage.weld_weights_from_rigged"
    bl_label = _("Weld to Rigged")
    bl_description = _("Adjust weights adjacent to other Mesh objects (rigged to same Armature)")
    bl_options = {'REGISTER', 'UNDO'}

    submeshInterpolation = BoolProperty(default=True, name=_("Sub-mesh interpolation"),
        description=_("Interpolate the weight values from closests point on surface of reference mesh") )

    onlySelectedVerts = BoolProperty(default=True, name=_("Only selected vertices"),
        description=_("Copy weights only to selected vertices in the target mesh"))

    allVisibleBones = BoolProperty(default=True, name=_("Include all visible bones"),
        description=_("Copy Weights from all visbile Bones. If not set, then copy only from selected Bones"))

    allHiddenBones = BoolProperty(default=False, name=_("Include All hidden bones"),
        description=_("Copy Weights from all hidden Bones. If not set, then copy only from selected Bones"))

    cleanVerts = BoolProperty(default=True, name=_("Clean Targets"),
        description=_("Clean Target vertex Groups before performnig the copy action"))

    def get_boundary_verts(self, context, obj, exportRendertypeSelection="NONE", apply_mesh_rotscale = True):
        bmsrc  = bmesh.new()
        target_copy           = util.visualCopyMesh(context, obj, apply_pose = False)
        target_copy_data      = target_copy.data
        target_copy_data.name += "(frozen)"

        bmsrc.from_mesh(target_copy_data)    
        verts = [vert for vert in bmsrc.verts if vert.is_boundary]
        for vert in verts:
            co = obj.matrix_world*(vert.co)

            vert.co = co
        context.scene.objects.unlink(target_copy)
        bpy.data.objects.remove(target_copy)

        return verts
        
    def execute(self, context):
        meshProps = context.scene.MeshProp

        try:
            obj       = context.object
            armobj    = obj.find_armature()
            
            self.submeshInterpolation = True
            self.allVisibleBones      = True
            self.allHiddenBones       = True
            self.allNonDeforming      = False
            self.empty                = False
            
            boneNames = get_bones_from_armature(armobj, self.allVisibleBones, self.allHiddenBones)
            omode     = util.ensure_mode_is('EDIT')
            sources = util.get_animated_meshes(context, armobj)
            copyBoneWeightsToSelectedBones(obj, sources, boneNames, self.submeshInterpolation, allVerts=not self.onlySelectedVerts, clearTargetWeights=self.cleanVerts)
            msg = create_message(self, context, _("Copied%sweights from visible siblings and %s Weight Groups"))
            self.report({'INFO'}, msg)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

def add_missing_mirror_groups(context, ob=None):

    active_object = context.scene.objects.active
    if ob:
        context.scene.objects.active = ob
        obj = ob
    else:
        obj = active_object

    scene    = context.scene
    groups   = {}
    me       = obj.to_mesh(context.scene, True, 'PREVIEW')
    vertices = me.vertices

    groups = {}
    for group in obj.vertex_groups:
        groups[group.name]= group

    missing_group_count = 0
    for key, group in groups.items():
        mkey = util.get_mirror_name(key)
        if mkey and not mkey in groups:
            missing_group_count += 1
            obj.vertex_groups.new(name=mkey)
    if missing_group_count > 0:
        print("Added %d missing Mirrored groups" % missing_group_count)

    original_mode = util.ensure_mode_is('OBJECT')
    bpy.ops.object.editmode_toggle()
    util.ensure_mode_is(original_mode)
    if ob:
        context.scene.objects.active = active_object

class ButtonEnsureMirrorGroups(bpy.types.Operator):
    bl_idname = "karaage.ensure_mirrored_groups"
    bl_label = _("Add missing Mirror Groups")
    bl_description = _("Create empty mirror Vertex Groups if they not yest exist")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        add_missing_mirror_groups(context)
        return{'FINISHED'}

class ButtonRemoveGroups(bpy.types.Operator):
    bl_idname = "karaage.remove_empty_groups"
    bl_label = _("Remove Groups")
    bl_description = _("Remove all Groups with no weights assigned")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        obj      = context.object
        scene    = context.scene
        groups   = {}
        me       = obj.to_mesh(context.scene, True, 'PREVIEW')
        vertices = me.vertices

        for v in vertices:
            for group in v.groups:
                if not group.group in groups:
                    groups[group.group] = group

        for group in [ group for group in obj.vertex_groups if group.index not in groups.keys()]:
            obj.vertex_groups.active_index=group.index
            bpy.ops.object.vertex_group_remove()

        return{'FINISHED'}

def get_weight_distribution(v, from_group, to_group):
    fg = None
    tg = None

    for g in v.groups:
        if g.group == from_group.index:
            fg = g
        elif g.group == to_group.index:
            tg = g

    fw = fg.weight if fg else 0
    tw = tg.weight if tg else 0

    return fw, tw

def set_weight(v, fg, fw, tg, tw):
    if fg: fg.add([v.index], fw, 'REPLACE')
    if tg: tg.add([v.index], tw, 'REPLACE')

def distribute_weight(v, fg, tg, percent, threshold, pgroup=None, dbg=""):
    if percent < 0 or percent > 1:
        print(dbg,"percent out of range:", v.index, fg.name, tg.name, percent)
        percent=max(0,percent)
        percent=min(1,percent)
    fw, tw = get_weight_distribution(v, fg, tg)
    sum = fw + tw

    if  sum > threshold:
        fw = sum * percent
        tw = sum - fw

        set_weight(v, fg, fw, tg, tw)
        if pgroup is not None:
            pgroup[str(v.index)] = fw

    return fw, tw

def set_shapekey_mute(tgt, mute, only_active=False):
    mute_state = {}
    if only_active:
        sk = tgt.active_shape_key
        if sk:
            mute_state[sk.name]=sk.mute
            sk.mute=mute
    else:
        for index, sk in enumerate(tgt.data.shape_keys.key_blocks):
            if index > 0 and sk.name not in ["neutral_shape","bone_morph"]:
                mute_state[sk.name]=sk.mute
                sk.mute=mute
    return mute_state

def restore_shapekey_mute(tgt, keys):
    for key in keys.keys():
        kb, is_new = get_key_block_by_name(tgt, key, readonly=True)
        if kb:
            kb.mute = keys[key]

def get_shapekey_data(obj,block):
    block_data  = [0.0]*3*len(obj.data.vertices)
    block.data.foreach_get('co',block_data)
    return block_data

def rebase_shapekey(obj, key_name, relative_name):
    skeys = obj.data.shape_keys
    blocks = skeys.key_blocks
    sk = blocks[key_name]
    rk = blocks[relative_name]
    from_data   = get_shapekey_data(obj, sk.relative_key)
    to_data     = get_shapekey_data(obj, rk)
    block_data  = get_shapekey_data(obj, sk)

    print("Rebase %s from %s to %s" % (sk.name, sk.relative_key.name, rk.name) )

    for i in range(len(obj.data.vertices)):
        for c in range(3):
            ii = 3*i+c
            block_data[ii] += to_data[ii] - from_data[ii]
    sk.data.foreach_set('co',block_data)
    sk.relative_key = rk

def rebase_shapekeys(obj, from_name, to_name):
    try:
        skeys = obj.data.shape_keys
        blocks = skeys.key_blocks
        from_relative = blocks[from_name]
        to_relative   = blocks[to_name]
    except:
        return None

    from_data     = get_shapekey_data(obj, from_relative)
    to_data       = get_shapekey_data(obj, to_relative)

    keys = []
    for index, sk in enumerate(blocks):
         if index > 0 and sk.relative_key == from_relative and sk != to_relative:
            rebase_shapekey(obj, sk.name, to_name)
            keys.append(sk.name)
    return keys

def get_key_block_by_name(tgt, key_block_name, readonly=False):
    skeys = tgt.data.shape_keys
    if skeys and skeys.key_blocks and key_block_name in skeys.key_blocks:
        sk = skeys.key_blocks[key_block_name]
        is_new = False
    elif readonly:
        sk = None
        is_new = True
    else:
        sk = tgt.shape_key_add(key_block_name)
        is_new = True
    return sk, is_new

def get_closest_point_of_path(obj, p, p0, p1, stepcount=50):
    loc = None
    nor = None
    i   = -1

    path    = p1-p0

    mindist = None
    minloc  = None
    mini    = -1

    close_to_shape_dist = None
    close_to_shape_loc  = None
    close_to_shape_mini = -1

    for f in range(stepcount+1):
        probe = p0+(f/stepcount) * path
        status, loc, nor, i = util.closest_point_on_mesh(obj, probe)
        if i != -1:
            dist    = (probe-loc).magnitude
            cs_dist = (p-loc).magnitude
            if mindist == None or dist < mindist:
                mindist = dist
                minloc  = probe
                mini    = i

            if close_to_shape_dist == None or cs_dist < close_to_shape_dist:
                close_to_shape_dist = cs_dist
                close_to_shape_loc  = probe
                close_to_shape_mini = i

    return minloc, mini, close_to_shape_loc, close_to_shape_mini

def smooth_weights(context, obj, bm, from_group, to_group, count=1, factor=0.5, threshold=0.00001, all_verts=True, rendertype='RAW'):
    arm = obj.find_armature()
    OM = obj.matrix_world

    shaped_mesh = util.getMesh(context, obj, rendertype, apply_mesh_rotscale=False, apply_armature=True)
    shaped_mesh.name = "T_shaped"
    
    shape_cos = {}
    original_weights = {}
    for v in [v for v in shaped_mesh.vertices if all_verts or v.select]:
        fw, tw = get_weight_distribution(v, from_group, to_group)
        original_weights[v.index]=[fw,tw]
        if  fw+tw > threshold:
            shape_cos[v.index] = v.co.copy()
            distribute_weight(v, from_group, to_group, 0, threshold, dbg="1")

    shape.refresh_shape(arm,obj,graceful=True)
    start_mesh = util.getMesh(context, obj, rendertype, apply_mesh_rotscale=False, apply_armature=True)
    start_mesh.name="T_start"
    start_cos = {}
    for index in shape_cos.keys():
        v = start_mesh.vertices[index]
        start_cos[v.index] = v.co.copy()
        distribute_weight(v, from_group, to_group, 1, threshold, dbg="2")

    shape.refresh_shape(arm,obj,graceful=True)
    end_mesh = util.getMesh(context, obj, rendertype, apply_mesh_rotscale=False, apply_armature=True)
    end_cos = {}
    for index in shape_cos.keys():
        v = end_mesh.vertices[index]
        end_cos[v.index] = v.co.copy()
        fw, tw = original_weights[v.index]
        set_weight(v, from_group, fw, to_group, tw)

    shape.refresh_shape(arm,obj,graceful=True)
    
    bm.from_mesh(shaped_mesh)
    verts = [v for v in bm.verts if all_verts or v.select]

    for d in range(count):
        bmesh.ops.smooth_vert(bm, verts=verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    target_cos   = {v.index:v.co.copy() for v in verts}

    bpy.context.scene.update()
    unsolved_verts = []
    pgroup = get_pgroup(obj, to_group.name, create=True)
    for index, co in shape_cos.items():
        v  = start_mesh.vertices[index]

        p  = Vector(target_cos[index])
        p0 = Vector(start_cos[index])
        p1 = Vector(end_cos[index])
        l  = (p1-p0).magnitude

        if l > 0.001:
            fr       = (p-p0).project(p1-p0)
            fraction = fr.magnitude/l # Vector projection
            fw, tw = distribute_weight(v, from_group, to_group, fraction, threshold, pgroup=pgroup, dbg="3")
        else:
            unsolved_verts.append(index)

    shape.refresh_shape(arm,obj,graceful=True)
    bpy.data.meshes.remove(start_mesh)
    bpy.data.meshes.remove(end_mesh)
    bpy.data.meshes.remove(shaped_mesh)

    return unsolved_verts

def distribute_weights(context, obj, from_group, to_group, threshold=0.00001, all_verts=True, rendertype='RAW'):
    arm = obj.find_armature()

    shaped_mesh = util.getMesh(context, obj, rendertype, apply_mesh_rotscale=False)
    shaped_mesh.name = "T_shaped"

    original_keys      = rebase_shapekeys(obj,"neutral_shape","bone_morph")
    original_key_mutes = set_shapekey_mute(obj, True)

    shape_cos = {}
    original_weights = {}
    for v in [v for v in shaped_mesh.vertices if all_verts or v.select]:
        fw, tw = get_weight_distribution(v, from_group, to_group)
        original_weights[v.index]=[fw,tw]

        if  fw+tw > threshold:
            shape_cos[v.index] = v.co.copy()
            distribute_weight(v, from_group, to_group, 0, threshold, dbg="1")

    shape.refresh_shape(arm,obj,graceful=True)

    start_mesh = util.getMesh(context, obj, rendertype, apply_mesh_rotscale=False)
    start_mesh.name="T_start"
    start_cos = {}
    for index in shape_cos.keys():
        v = start_mesh.vertices[index]
        start_cos[v.index] = v.co.copy()

        distribute_weight(v, from_group, to_group, 1, threshold, dbg="2")

    shape.refresh_shape(arm,obj,graceful=True)

    end_mesh = util.getMesh(context, obj, rendertype, apply_mesh_rotscale=False)
    end_mesh.name="T_end"
    end_cos = {}
    for index in shape_cos.keys():
        v = end_mesh.vertices[index]
        end_cos[v.index] = v.co.copy()
        fw, tw = original_weights[v.index]
        set_weight(v, from_group, fw, to_group, tw)

    restore_shapekey_mute(obj, original_key_mutes)
    shape.refresh_shape(arm,obj,graceful=True)

    unsolved_verts = []
    pgroup = get_pgroup(obj, to_group.name, create=True)

    for index, co in shape_cos.items():
        v = start_mesh.vertices[index]
        p  = Vector(shape_cos[index])
        p0 = Vector(start_cos[index])
        p1 = Vector(end_cos[index])

        l = (p1-p0).magnitude
        if l > 0.001:
            status, loc, nor, i = util.ray_cast(obj, p0, p1)

            if i > -1:
                f = (loc-p0).magnitude
                fraction = f/l
                fw, tw = distribute_weight(v, from_group, to_group, fraction, threshold, pgroup=pgroup, dbg="3")

            else:
                print("no solution for vertex %d not fitted l:%f" % (index, l))

        else:
            unsolved_verts.append(index)
            print("vertex %d not fitted" % index)

    shape.refresh_shape(arm,obj,graceful=True)
    for key in original_keys:
        rebase_shapekey(obj, key, "neutral_shape")

    return unsolved_verts

def prepare_physics_weights(obj, bone_names):
    if not "physics" in obj:
        obj['physics'] = {}
    physics = obj['physics']
    for name in bone_names:
        vgroup = get_bone_group(obj, name, create=True)
        if not name in physics:
            physics[name]= get_weight_set(obj, vgroup, clear=True)

def scale_level(obj, strength, bone_names):
    scale = strength+1
    prepare_physics_weights(obj, bone_names)
    physics = obj['physics']
    pinch = 1
    if scale > 1:
        pinch = scale*scale
        scale = 1

    omode = util.ensure_mode_is("OBJECT", object=obj)
    for name in bone_names:
        vgroup = get_bone_group(obj, name, create=True)
        ggroup = physics[name]
        pgroup = get_weight_set(obj, vgroup, clear=False)
        keys = pgroup.keys() if len(pgroup)>0 else ggroup.keys()
        for index in keys:

            try:
                gw = ggroup[index]
            except:
                ggroup[index]=0
                gw = 0
            try:
                pw = pgroup[index]
            except:
                pgroup[index]=0
                pw = 0

            w = gw + pw
            pw = min(max((scale*w)**pinch,0),1)
            gw = min(max(w - pw, 0),1)
            vgroup.add([int(index)], pw, 'REPLACE')
            ggroup[index] = gw

    if scale == 0:
        util.removeWeightGroups(obj, bone_names)

    util.ensure_mode_is(omode, object=obj)

def get_weight_set(ob, vgroup, clear=False):
    weights = {}
    if vgroup:
        for index, vert in enumerate(ob.data.vertices):
            for group in vert.groups:
                if group.group == vgroup.index:
                    weights[str(index)] = group.weight if not clear else 0
    return weights

def get_pgroup(obj, cgroup_name, create=False):
    if not "fitting" in obj:
        if not create: return None
        obj['fitting'] = {}
    fitting = obj['fitting']
    if not cgroup_name in fitting:
        if not create: return None
        fitting[cgroup_name] = {}
    pgroup = fitting[cgroup_name]
    return pgroup

def set_fitted_strength(context, obj, cgroup_name, percent, only_selected, omode):

    selected_verts = obj.mode=='EDIT'
    cgroup       = get_bone_group(obj, cgroup_name, create=False)
    mgroup       = get_bone_partner_group(obj, cgroup_name, create=False)
    pgroup       = get_pgroup(obj, cgroup_name, create=True)
    active_group = obj.vertex_groups.active

    if active_group not in [mgroup,cgroup]:
        active_group  = cgroup
        
    mgroup_set  = get_weight_set(obj, mgroup)
    cgroup_set  = get_weight_set(obj, cgroup)

    vertices = obj.data.vertices
    for index, cw in cgroup_set.items():
        mw = mgroup_set[index] if index in mgroup_set else 0
        pw = pgroup[index]     if index in pgroup else 0
        sum = min(cw + mw,1)
        v = vertices[int(index)]

        mgroup_set[index] = sum

        if only_selected and v.select:
            pgroup[index]     = (1-percent) * sum

    if percent != 0 and cgroup == None:
        cgroup = get_bone_group(obj, cgroup_name, create=True)
    if percent != 1 and mgroup == None:
        mgroup = get_bone_partner_group(obj, cgroup_name, create=True)

    mg_counter = 0
    for index, w in mgroup_set.items():
        v = vertices[int(index)]
        if v.select or not only_selected:
            cw = w * percent
            mw = w - cw
            pw = pgroup[index] if index in pgroup else 0
            if pw != 0:

                cw = percent*(w - pw)
                mw = w - cw
                mg_counter += 1

            set_weight(v, mgroup, mw, cgroup, cw)

    if only_selected:
        if omode != 'OBJECT':
            obj.update_from_editmode()
    else:
        if percent == 0 and cgroup and len(pgroup) == 0:
            obj.vertex_groups.active_index=cgroup.index
            bpy.ops.object.vertex_group_remove()
        elif percent == 1 and mgroup and len(pgroup) == 0:
            obj.vertex_groups.active_index=mgroup.index
            bpy.ops.object.vertex_group_remove()
    return active_group

def setDeformingBones(armobj, bone_names, replace=False):
    print("setDeformingBones")
    bones = util.get_modify_bones(armobj)
    for bone in bones:
        if replace or bone.name in bone_names:
            bone.use_deform = bone.name in bone_names
        bone.layers[B_LAYER_DEFORM] = bone.use_deform

def disableDeformingBones(armobj, bone_names, replace=False):
    bones = util.get_modify_bones(armobj)
    for bone in bones:
        if replace or bone.name in bone_names:
            bone.use_deform = False
        bone.layers[B_LAYER_DEFORM] = bone.use_deform

def setDeformingBoneLayer(armobj, final_set, initial_set):

    bones = util.get_modify_bones(armobj)
    for name in initial_set:
        bones[name].layers[B_LAYER_DEFORM] =False
    for bone in bones:
        bone.layers[B_LAYER_DEFORM] = bone.name in final_set

def update_fitting_panel(obj, vidx):
    print("Update fitting panel for %s:%s" % (obj.name, vidx) )

def find_active_vertex(bm):
    return None
    elem = bm.select_history.active
    print("elem is:",elem)
    if elem and isinstance(elem, bmesh.types.BMVert):
        return elem
    return None

edited_object       = None
active_vertex_index = None
active_group_index  = None

@persistent
def edit_object_change_handler(scene):

    global edited_object
    global active_vertex_index
    global active_group_index

    context = bpy.context

    if not context.scene.ticker.fire: return

    try:
        obj=context.edit_object
        if obj and obj.type=="MESH" and context.mode=="EDIT_MESH":
            me = obj.data

            #

            if obj.is_updated_data:
                bpy.context.object.update_from_editmode()
        else:
            edited_object       = None
            active_vertex_index = None
            active_group_index  = None
    except:
        pass