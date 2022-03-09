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
import logging, gettext, os, time, re, shutil
import addon_utils

from . import const, create, data, messages, rig, shape, util, weights
from .const import *
from bpy.props import *
from bl_operators.presets import AddPresetBase
from bpy.types import Menu, Operator
from mathutils import Matrix

log = logging.getLogger('karaage.bind')

translator = gettext.translation('karaage', LOCALE_DIR, fallback=True)
_          = translator.gettext

def get_basis_pose_from_armature(arm):
    dict = {}
    bones = arm.pose.bones
    for bone in bones:
        dict[bone.name] = bone.matrix_basis.copy()
    return dict

def read_basis_pose_from_textblock(bindname):
    text = bpy.data.texts[bindname]
    txt = text.as_string()
    dict = eval(txt)
    return dict

def set_bindpose_matrix(arm):
    dict = read_basis_pose_from_textblock(arm['bindpose'])
    bones = arm.pose.bones
    rig.set_bone_rotation_limit_state(arm, False, all=True)
    for bone in bones:
        name=bone.name
        mat = dict[name]
        bone.matrix_basis = mat

def set_invbindpose_matrix(arm):
    dict = read_basis_pose_from_textblock(arm['bindpose'])
    bones = arm.pose.bones
    rig.set_bone_rotation_limit_state(arm, False, all=True)
    for bone in bones:
        name=bone.name
        mat = dict[name]
        bone.matrix_basis = mat.inverted()

def write_basis_pose_to_textblock(arm, bindname):
    rig.set_bone_rotation_limit_state(arm, False, all=True)
    dict = get_basis_pose_from_armature(arm)
    if bindname in bpy.data.texts:
        text = bpy.data.texts[bindname]
        util.remove_text(text, do_unlink=True)
    text = bpy.data.texts.new(bindname)
    text.write(str(dict))
    arm['bindpose']=text.name
        
class KaraageStoreBindData(bpy.types.Operator):
    bl_idname      = "karaage.store_bind_data"
    bl_label       = "Set Bind Pose"
    bl_description = '''Apply Current Pose as Restpose.
This is only used to bind an object to a different pose!

Warning:  Meshes already bound to the Armature 
will revert to T-Pose. Also the appearence sliders
will be disabled!'''

    @classmethod
    def poll(self, context):
        obj=context.object
        if obj != None:
            arm = util.get_armature(obj)
            return arm != None
        return False

    def execute(self, context):
        obj=context.object
        arm = util.get_armature(obj)
        bindname = "posemats_%s" % arm.name
        write_basis_pose_to_textblock(arm, bindname)
        omode = None

        if obj != arm:
            omode = util.ensure_mode_is('OBJECT')
            active = context.active_object
            context.scene.objects.active = arm

        amode = util.ensure_mode_is('POSE')
        bpy.ops.pose.armature_apply()
        util.ensure_mode_is(amode)
        
        if obj != arm:
            context.scene.objects.active = active
            util.ensure_mode_is(omode)
        
        return{'FINISHED'}
     
class KaraageDisplayInRestpose(bpy.types.Operator):
    bl_idname      = "karaage.display_in_restpose"
    bl_label       = "Display Default Pose"
    bl_description = "Set Armature Pose to the default Karaage Pose for inspection\nNote: This operation neither changes the armature nor the object"

    @classmethod
    def poll(self, context):
        obj=context.object
        if obj != None:
            arm = util.get_armature(obj)
            if arm:
                return 'bindpose' in arm
        return False

    def execute(self, context):

        obj=context.object
        arm = util.get_armature(obj)
        set_invbindpose_matrix(arm)
        omode = None
        if obj != arm:
            omode = util.ensure_mode_is('OBJECT')
            active = context.active_object
            context.scene.objects.active = arm
        if obj != arm:
            context.scene.objects.active = active
            util.ensure_mode_is(omode)
        return{'FINISHED'}

class KaraageCleanupBinding(bpy.types.Operator):
    bl_idname      = "karaage.cleanup_binding"
    bl_label       = "Cleanup Binding Data"
    bl_description = "Generate Joint offsets from current binding\n\nNote:\nThis operation replaces the bind data by a list of Joint Offsets.\nThis is for now the preferred way to go until we have true bind pose support!"

    @classmethod
    def poll(self, context):
        obj=context.object
        if obj != None:
            arm = util.get_armature(obj)
            if arm:
                return 'bindpose' in arm
        return False

    def execute(self, context):
        armobj = util.get_armature(context.active_object)
        cleanup_binding(context, armobj)
        return{'FINISHED'}

class KaraageAlterToRestpose(bpy.types.Operator):
    bl_idname      = "karaage.alter_to_restpose"
    bl_label       = "Alter to Default Pose"
    bl_description = "Reset Armature back to the default Karaage Pose\nAfter Reverting the Appearance Sliders will be back in operation"
    
    @classmethod
    def poll(self, context):
        obj=context.object
        if obj != None:
            arm = util.get_armature(obj)
            if arm:
                return 'bindpose' in arm
        return False

    def execute(self, context):
        active      = context.active_object
        active_mode = util.ensure_mode_is('OBJECT')
        
        obj = context.object
        arm = util.get_armature(obj)
        set_invbindpose_matrix(arm)
        omode = None

        meshes = util.getCustomChildren(arm, type='MESH') if obj==arm else [obj]
        
        for obj in meshes:
            util.apply_armature_modifiers(context, obj, preserve_volume=True)

        context.scene.objects.active = arm
        amode = util.ensure_mode_is('POSE')
        bpy.ops.pose.armature_apply()
        util.ensure_mode_is(amode)
        
        for obj in meshes:
            mod = obj.modifiers.new(arm.name, 'ARMATURE')
            mod.use_vertex_groups  = True
            mod.use_deform_preserve_volume=True
            mod.use_bone_envelopes = False
            mod.object             = arm 

        set_bindpose_matrix(arm)
        arm['export_pose'] = arm['bindpose']
        del arm['bindpose']

        context.scene.objects.active = active
        util.ensure_mode_is(active_mode)
        
        return{'FINISHED'}

def add_bind_preset(context, filepath):
    arm    = util.get_armature(context.object)
    pbones = arm.pose.bones

    file_preset = open(filepath, 'w')
    file_preset.write(
    "import bpy\n"
    "import karaage\n"
    "from karaage import shape, util, bind\n"
    "from mathutils import Vector, Matrix\n"
    "\n"
    "arm    = util.get_armature(bpy.context.object)\n"
    "\n"
    )
    dict = get_basis_pose_from_armature(arm)
    file_preset.write("dict=" + str(dict) + "\n\n")
    file_preset.write(
    "bones = arm.pose.bones\n"
    "for bone in bones:\n"
    "    name=bone.name\n"
    "    mat = dict[name]\n"
    "    bone.matrix_basis = mat.inverted()\n"
    "\n"
    )
    
    file_preset.close()

class KARAAGE_MT_bind_presets_menu(Menu):
    bl_idname = "karaage_bind_presets_menu"
    bl_label  = "Bind Presets"
    bl_description = "Bind Presets for the Karaage Rig"
    preset_subdir = os.path.join("karaage","bindings")
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset

class KaraageAddPresetBind(AddPresetBase, Operator):
    bl_idname = "karaage.bind_presets_add"
    bl_label = "Add Bind Preset"
    bl_description = "Create new Preset from current Slider settings"
    preset_menu = "karaage_bind_presets_menu"

    preset_subdir = os.path.join("karaage","bindings")

    def invoke(self, context, event):
        log.info("Create new Bind Preset...")
        return AddPresetBase.invoke(self, context, event)

    def add(self, context, filepath):
        add_bind_preset(context, filepath)

class KaraageUpdatePresetBind(AddPresetBase, Operator):
    bl_idname = "karaage.bind_presets_update"
    bl_label = "Update Bind Preset"
    bl_description = "Store current Slider settings in last selected Preset"
    preset_menu = "karaage_bind_presets_menu"
    preset_subdir = os.path.join("karaage","bindings")

    def invoke(self, context, event):
        self.name = bpy.types.karaage_bind_presets_menu.bl_label
        log.info("Updating Preset", self.name)
        return self.execute(context)

    def add(self, context, filepath):
        add_bind_preset(context, filepath)

class KaraageRemovePresetBind(AddPresetBase, Operator):
    bl_idname = "karaage.bind_presets_remove"
    bl_label = "Remove Bind Preset"
    bl_description = "Remove last selected Preset from the list"
    preset_menu = "karaage_bind_presets_menu"
    preset_subdir = os.path.join("karaage","bindings")

def cleanup_binding(context, armobj, sync=True, with_ik_bones=False, with_joint_tails=True, delete_only=False, only_meta=False):
    if not armobj:
        return
    active = context.scene.objects.active
    amode = util.ensure_mode_is('OBJECT')

    context.scene.objects.active = armobj
    omode=util.ensure_mode_is('EDIT')

    bindname = armobj.get('bindpose', None)
    if bindname:
        del armobj['bindpose']
        text = bpy.data.texts.get(bindname)
        if text:
            util.remove_text(text, do_unlink=True)

    result = ArmatureJointPosStore.exec_imp( None, 
             context, 
             delete_only=delete_only, 
             with_ik_bones=with_ik_bones, 
             with_joint_tails=with_joint_tails,
             only_meta=only_meta)

    util.ensure_mode_is('POSE')
    util.ensure_mode_is(omode)

    context.scene.objects.active = active
    util.ensure_mode_is(amode)

def remove_binding(context, armobj, sync=True):
    if not armobj:
        return
    active = context.scene.objects.active
    active_mode = util.ensure_mode_is('OBJECT')

    context.scene.objects.active = armobj
    omode=util.ensure_mode_is('EDIT')

    bindname = armobj.get('bindpose', None)
    if bindname:
        del armobj['bindpose']
        text = bpy.data.texts.get(bindname)
        if text:
            util.remove_text(text, do_unlink=True)

    log.info("remove_binding from %s %s" % (armobj.type, armobj.name) )
    result = ArmatureJointPosRemove.exec_imp(
                None, 
                context, 
                keep_edit_joints=True, 
                affect_all_joints=True
             )

    util.ensure_mode_is('POSE')
    util.ensure_mode_is(omode)

    context.scene.objects.active = active
    util.ensure_mode_is(active_mode)

class ArmatureJointPosStore(bpy.types.Operator):
    bl_idname = "karaage.armature_jointpos_store"
    bl_label = "Store Joint Edits"
    bl_description = \
'''Calculate SL Joint Offsets for your Armature modifications
Call this function to inform the appearance Sliders about your changes.
Note: Only modified joints will be recorded!'''

    bl_options = {'REGISTER', 'UNDO'}

    sync = BoolProperty(
           name        = "Sync",
           description = "Sync",
           default     = False
           )

    delete_only = BoolProperty(
           name        = "Only Remove",
           description = "Only remove Joints\n(Only for debugging, Normally not needed)",
           default     = False
           )
           
    only_meta = BoolProperty(
           name        = "Only Meta",
           description = "Only create Metadata\n(Only for debugging, Normally not needed)",
           default     = False
           )
           
    vanilla_rig =  BoolProperty(
           name        = "Vanilla Rig",
           description = "Reset Rig Metadata\n(Only use when nothing else helps)",
           default     = False
           )

    snap_control_to_rig = BoolProperty(
           name        = "snap_control_to_rig",
           description = SceneProp_snap_control_to_rig_description,
           default     = False
           )

    def draw(self, context):
        layout = self.layout
        ob = context.object
        armobj = util.get_armature(ob)
        scn = context.scene

        col = layout.column()
        col.prop(self, "snap_control_to_rig")
        col.prop(armobj.RigProps, "generate_joint_tails")
        col.prop(armobj.RigProps, "generate_joint_ik")
        col.prop(self,"vanilla_rig")

        box = layout.box()
        box.label("Debugging options")
        col = box.column()
        col.prop(self, "sync")
        col.prop(self, "only_meta")
        col.prop(self, "delete_only")
        
    @staticmethod
    def exec_imp(op, 
                 context, 
                 delete_only=False, 
                 with_ik_bones=False, 
                 with_joint_tails=True,
                 only_meta=False,
                 vanilla_rig=False,
                 snap_control_to_rig=False):

        oumode = util.set_operate_in_user_mode(False)
        try:
            obj = context.object
            armobj = util.get_armature(obj)
            active = context.scene.objects.active
            amode = util.ensure_mode_is("OBJECT")

            context.scene.objects.active = armobj

            omode = util.ensure_mode_is("EDIT")
            use_mirror_x = armobj.data.use_mirror_x
            armobj.data.use_mirror_x = False

            ArmatureJointPosRemove.exec_imp(op, context, keep_edit_joints=True, affect_all_joints=True)
            reset_dirty_flag(armobj)
            if vanilla_rig: #False
                create.reset_rig(armobj)

            rig.autosnap_bones(armobj, snap_control_to_rig)

            armobj.update_from_editmode()
            
            if not delete_only: #not False
                log.debug("armature_jointpos_store: Calculate joint positions")
                joints = rig.calculate_offset_from_sl_armature(
                         context,
                         armobj,
                         all=True,
                         with_ik_bones=with_ik_bones, 
                         with_joint_tails=with_joint_tails)

                if not only_meta: #False
                    shape.update_tail_info(context, armobj)
                    shape.updateShape(op, context, refresh=True, msg="karaage.armature_jointpos_store")

            armobj.data.use_mirror_x = use_mirror_x
            reconfigure_rig_display(context, armobj, [obj])
            armobj.update_from_editmode()

            util.ensure_mode_is(omode)

            context.scene.objects.active = active
            util.ensure_mode_is(amode)
        except Exception as e:
            util.ErrorDialog.exception(e)
        finally:
            util.set_operate_in_user_mode(oumode)
        return {'FINISHED'}

    def invoke(self, context, event):
        obj     = context.object
        armobj = util.get_armature(obj)
        return self.execute(context)
        
    def execute(self, context):
        obj     = context.object
        armobj = util.get_armature(obj)
        result = ArmatureJointPosStore.exec_imp(
                     self,
                     context,
                     self.delete_only,
                     armobj.RigProps.generate_joint_ik,
                     armobj.RigProps.generate_joint_tails,
                     self.only_meta,
                     self.vanilla_rig,
                     self.snap_control_to_rig
                     )
        return result
        
def reset_dirty_flag(armobj):
    if 'dirty' in armobj:
        was_dirty = True
        del armobj['dirty']
        bones = util.get_modify_bones(armobj)
        for b in [b for b in bones if 'bone_roll' in b]:
            del b['bone_roll']
    else:
        was_dirty = False
    return was_dirty

class ArmatureJointPosRemove(bpy.types.Operator):
    bl_idname = "karaage.armature_jointpos_remove"
    bl_label = _("Remove Joint Edits")
    bl_description = _("Remove Joint Offset\n\nThe Bone Joint Data is deleted and the bone is moved back to its default location.")
    bl_options = {'REGISTER', 'UNDO'}

    keep_edit_joints = BoolProperty(
        name = "Keep edits",
        default = True, 
        description = "Keep skeleton as is but remove joint offset records"
    )

    affect_all_joints = BoolProperty(
        name    = "All Joints",
        default = True,
        description = "- Disabled: Affect selected Bones (caution, can give unexpected results!)\n- Enabled: Affect all Bones (please use this!)"
    )

    joint = StringProperty(default="")

    @staticmethod
    def exec_imp(op, context, keep_edit_joints, affect_all_joints):
        oumode = util.set_operate_in_user_mode(False)
        was_dirty = False
        obj     = context.object
        armobj = util.get_armature(obj)
        try:
            active  = obj
            log.info("Remove Joint Positions from armature [%s]" % armobj.name)

            context.scene.objects.active = armobj
            omode = util.ensure_mode_is("OBJECT")
            use_mirror_x = armobj.data.use_mirror_x
            armobj.data.use_mirror_x = False

            log.info("%s edited joint locations" % "Keep" if keep_edit_joints else "Remove")
            delete_joint_info = not keep_edit_joints
            all = affect_all_joints

            util.ensure_mode_is("EDIT")
            rig.del_offset_from_sl_armature(context, armobj, delete_joint_info, all=all)
            shape.update_tail_info(context, armobj, remove=affect_all_joints)

            if not context.scene.SceneProp.panel_appearance_enabled:
                shape.destroy_shape_info(context, armobj)

            if delete_joint_info:
                shape.updateShape(op, context, refresh=True, msg="karaage.armature_jointpos_remove")

            armobj.data.use_mirror_x = use_mirror_x
            armobj.update_from_editmode()

            reset_dirty_flag(armobj)

            util.ensure_mode_is(omode)
            context.scene.objects.active = active
            reconfigure_rig_display(context, armobj, [obj])
        except Exception as e:
            util.ErrorDialog.exception(e)
        finally:
            util.set_operate_in_user_mode(oumode)
            if keep_edit_joints:
                armobj['dirty'] = True

    def execute(self, context):
        ArmatureJointPosRemove.exec_imp(self, context, self.keep_edit_joints, self.affect_all_joints)
        return{'FINISHED'}

def configure_edge_display(props, context):
    obj = context.object
    if not obj: return
    arm = util.get_armature(obj)

    obj.show_wire      = obj.ObjectProp.edge_display
    obj.show_all_edges = obj.ObjectProp.edge_display

def reconfigure_rig_display(context, arm, objs, verbose=True, force=False):
    if force or arm.ObjectProp.filter_deform_bones==False:
        final_set = bone_set = data.get_deform_bones(arm)

        type = 'DEFORM'
    else:
        type = arm.ObjectProp.rig_display_type
        for e in range(0,32):
                arm.data.layers[e] = e==B_LAYER_DEFORM

        final_set = set()
        if type == 'VOL':
            final_set = bone_set = data.get_volume_bones(arm, only_deforming=True)
        elif type == 'SL':
            final_set = bone_set = data.get_base_bones(arm, only_deforming=True)
        elif type == 'EXT':
            final_set = bone_set = data.get_extended_bones(arm, only_deforming=True)
        elif type == 'POS':

            final_set = bone_set  = rig.get_bone_names_with_jointpos(arm)
        elif type == 'MAP':
            bone_set = data.get_deform_bones(arm)

            for obj in objs:

                vgroups = obj.vertex_groups
                for g in vgroups:
                    if g.name in bone_set:
                        final_set.add(g.name)

            final_set = list(final_set)
        else:
            final_set = bone_set = data.get_deform_bones(arm)

    log.warning("configure_rig_display for %d %s bones" % (len(bone_set), type) )

    weights.setDeformingBoneLayer(arm, final_set, bone_set)

def configure_rig_display(props, context):
    obj = context.object
    if obj:
        arm = util.get_armature(obj)
        if arm:
            rig.deform_display_reset(arm)
            objs = util.get_animated_meshes(context, arm, with_karaage=True, only_selected=True)
            arm['rig_display_type_set'] = ''
            reconfigure_rig_display(context, arm, objs)
            arm.data.layers[B_LAYER_DEFORM]   = True
            arm.data.layers[B_LAYER_SL]       = False
            arm.data.layers[B_LAYER_EXTENDED] = False
            arm.data.layers[B_LAYER_VOLUME]   = False

last_armobj = None
def fix_bone_layers(dummy=None, lazy=True, force=False):
    global last_armobj

    context = bpy.context
    if context is None: return
    
    context.scene.ticker.tick
    if lazy and not context.scene.ticker.fire:
        return

    if context.object is None:
        return

    try:
        arm = util.get_armature(context.object)
        if arm and 'karaage' in arm:
            log.debug("Fix Bone Layers for %s  rigtype:%s filter:%s ..." % ( \
                        arm.name,
                        arm.ObjectProp.rig_display_type,
                        arm.ObjectProp.filter_deform_bones)
                        )
            adt = arm.data.draw_type
            dt  = arm.RigProps.draw_type
            if adt in ['OCTAHEDRAL','STICK']:
                if len(dt) == 0 or next(iter(dt)) != adt:
                    arm.RigProps.draw_type = set([adt])
            elif len(dt) > 0:
                arm.RigProps.draw_type = set()

            objs = util.get_animated_meshes(context, arm, with_karaage=True, only_selected=True)
            display_changed = rig.deform_display_changed(context, arm, objs)
            armobj_changed = last_armobj != arm
            if display_changed or armobj_changed:
                last_armobj = arm
                log.warning("dc:%s ac:%s" % (display_changed, armobj_changed) )
                reconfigure_rig_display(context, arm, objs, verbose=True, force=force)

    except:
        print("Force fixing bone layers failed...")
        raise