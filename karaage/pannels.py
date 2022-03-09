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

from . import animation, const, copyrig, create, data, mesh, messages, rig, shape, util, weights
from .const import *
from bpy.props import *

translator = gettext.translation('karaage', LOCALE_DIR, fallback=True)
_          = translator.gettext

log = logging.getLogger('karaage.pannels')

class PanelWorkflow(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = "Settings"
    bl_idname      = "karaage.panel_workflow"
    bl_category    = "Karaage"
    bl_options     = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_SKINNING, msg=panel_info_workflow)

    def draw(self, context):

        layout = self.layout
        scn    = context.scene
        active = context.object
        armobj = util.get_armature(active)
        box = layout
        col = box.column(align=True)
        col.label("User Interface", icon='UI')
        preferences = util.getAddonPreferences()
        last_preset = context.scene.SceneProp.panel_presets

        ui_level = util.get_ui_level()

        col.prop(preferences,'ui_complexity', expand=True)
        col.separator()
        col.label("Workflow Presets", icon='MENU_PANEL')

        row=col.row(align=True)
        row.operator("karaage.bone_preset_skin", text='', icon_value=const.custom_icons["mbones"].icon_id)
        row.operator("karaage.bone_preset_skin")
        if last_preset == 'SKIN':
            row.operator("karaage.bone_preset_skin", icon='LAYER_ACTIVE', text='')

        row=col.row(align=True)
        row.operator("karaage.bone_preset_animate", text='', icon_value=const.custom_icons["cbones"].icon_id)
        row.operator("karaage.bone_preset_animate")
        if last_preset == 'POSE':
            row.operator("karaage.bone_preset_animate", icon='LAYER_ACTIVE', text='')

        col = box.column(align=True)
        col.enabled = ui_level != UI_SIMPLE
        row=col.row(align=True)
        row.operator("karaage.bone_preset_retarget", text='', icon_value=const.custom_icons["retarget"].icon_id)
        row.operator("karaage.bone_preset_retarget")
        if last_preset == 'RETARGET':
            row.operator("karaage.bone_preset_retarget", icon='LAYER_ACTIVE', text='')

        row=col.row(align=True)
        row.operator("karaage.bone_preset_edit", text='', icon='OUTLINER_OB_ARMATURE')
        row.operator("karaage.bone_preset_edit")
        if last_preset == 'EDIT':
            row.operator("karaage.bone_preset_edit", icon='LAYER_ACTIVE', text='')

        col.separator()
        col = col.column(align=True)
        col.operator('karaage.pref_show')

class PanelShaping(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = "Appearance"
    bl_idname      = "karaage.panel_shaping"
    bl_category    = "Karaage"
    bl_options     = {'DEFAULT_CLOSED'}
    
    @staticmethod
    def recalculate_bone_usage(context, arm, pids):
        isCollisionRig = rig.is_collision_rig(context.object)
        
        for pid in pids:
            P = arm.ShapeDrivers.DRIVERS.get(pid)
            if not P:
                continue        
            D = P[0]
            if pid in shape.SHAPE_FILTER[_("Extended")]:
                D['icon'] = 'OUTLINER_OB_META'
                D['hint'] = "karaage.shape_type_extended_hint"
            elif pid in shape.SHAPE_FILTER[_("Skeleton")]:
                D['icon'] = 'BONE_DATA'
                D['hint'] = "karaage.shape_type_bone_hint"
            else:
                if isCollisionRig and pid in shape.SHAPE_FILTER[_("Fitted")]:
                    D['icon'] = 'SNAP_ON'
                    D['hint'] =  "karaage.shape_type_fitted_hint"
                else:
                    D['icon'] = 'BLANK1'
                    D['hint'] = "karaage.shape_type_morph_hint"
    @staticmethod
    def draw_generic(op, context, arm, layout):
        from .util  import rescale
        from .shape import get_shapekeys, is_set_to_default

        scn = context.scene
        obj = context.active_object
        sceneProps = context.scene.SceneProp
        if not util.use_sliders(context):
            box = layout.box()
            box.alert=True
            box.label("Sliders disabled")
            return

        if 'dirty' in arm:
            if shape.has_enabled_sliders(context, arm):
                layout.enabled=False
            layout.alert=True
        
        if not hasattr(arm.ShapeDrivers, 'DRIVERS'):

            layout.operator("karaage.load_shape_ui")

        else:
            supports_shapes   = obj.ObjectProp.slider_selector!='NONE'
            supports_sparkles = 'toolset_pro' in dir(bpy.ops.sparkles)

            last_select = bpy.types.karaage_shape_presets_menu.bl_label
            row = layout.row(align=True)
            row.operator("karaage.reset_to_default", text="", icon='OUTLINER_OB_ARMATURE')
            row.operator("karaage.reset_to_restpose", text="", icon='ARMATURE_DATA')
            row.operator("karaage.shape_copy", text="", icon='COPYDOWN')
            row.operator("karaage.shape_paste", text="", icon='PASTEDOWN')

            row.menu("karaage_shape_presets_menu", text=last_select )
            row.operator("karaage.shape_presets_add", text="", icon='ZOOMIN')
            if last_select not in ["Shape Presets", "Presets"]:
                row.operator("karaage.shape_presets_update", text="", icon='FILE_REFRESH')
                row.operator("karaage.shape_presets_remove", text="", icon='ZOOMOUT').remove_active = True

            col = layout.column(align=True)
            col.prop(arm.RigProps,"rig_use_bind_pose")

            bones = arm.data.bones
            mSkull = bones.get('mSkull', None)
            Origin = bones.get('Origin', None)
            if mSkull and Origin:
                height = mSkull.head_local.z - Origin.head_local.z+0.13
                label  = "Male (Avatar Height: %.2fm)"%height
            else:
                label  = "Male (Height undefined)"

            P = arm.ShapeDrivers.DRIVERS.get("male_80")
            if P:
                col = layout.column(align=True)
                col.prop(arm.ShapeDrivers, "male_80", text=label, toggle=False)

            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(arm.ShapeDrivers, "Sections", text="")
            row.operator("karaage.reset_shape_section", text="", icon="LOAD_FACTORY" )

            try:
                male = arm.ShapeDrivers.male_80
            except:
                male = False

            pids = get_shapekeys(arm)
            PanelShaping.recalculate_bone_usage(context, arm, pids)
            for pid in pids:
                P = arm.ShapeDrivers.DRIVERS.get(pid)
                if not P:
                    continue

                D = P[0]
                s = D['sex']
                if pid=="male_80":
                    pass
                elif s is None or (s=='male' and male==True) or (s=='female' and male==False):
                    icon = D['icon']
                    opid = D['hint']
                    bones, joint_count = shape.get_driven_bones(arm.data.bones, arm.ShapeDrivers.DRIVERS, D)

                    sliderRow = col.row(align=True)
                    if joint_count > 0:
                        sliderRow.alert = True

                    try:
                        prop=sliderRow.operator(opid, text="", icon=icon)

                    except:
                        prop=sliderRow.operator(opid, text="", icon='BLANK1')
                    prop.pid=pid

                    sliderRow.prop(arm.ShapeDrivers, pid , slider=True, text = D['label'])

                    if supports_sparkles:
                        if supports_shapes and obj!=arm and icon=='SNAP_ON':
                            name = mesh.get_corrective_key_name_for(pid)
                            is_driven = obj.data.shape_keys and name in obj.data.shape_keys.key_blocks
                            icon = 'DRIVER' if is_driven else 'SHAPEKEY_DATA'
                            prop=sliderRow.operator("sparkles.create_corrective_shape_key",text='', icon=icon)
                            prop.name     = name
                            prop.relative = "neutral_shape"
                        else:
                            sliderRow.operator(opid, text="", icon='BLANK1')

                    icon='BLANK1' if is_set_to_default(arm,pid) else 'LOAD_FACTORY'
                    sliderRow.operator("karaage.reset_shape_slider", text="", icon=icon).pid=pid

                    if D.get('show',False):
                        if len(bones) > 0:
                            irow = col.box().row(align=True)
                            lcol = irow.column(align=True)
                            mcol = irow.column(align=True)
                            rcol = irow.column(align=True)

                            keys = sorted(bones.keys())
                            for key in keys:
                                val = bones[key]
                                lrow = lcol.row(align=True)
                                mrow = mcol.row(align=True)
                                mrow.alignment='RIGHT'
                                rrow = rcol.row(align=True)
                                rrow.alignment='RIGHT'
                                trans,scale = val

                                has_offset = util.has_head_offset(arm.data.bones[key]) or \
                                             util.has_head_offset(arm.data.bones.get('m'+key))
                                if  has_offset:
                                    prop=lrow.operator("karaage.armature_jointpos_remove", text='', icon='CANCEL', emboss=False)
                                    prop.affect_all_joints=False
                                    prop.keep_edit_joints=False
                                    prop.joint=key

                                else:
                                    lrow.label('', icon='FILE_TICK')
                                lrow.label(key)
                                mrow.label('Trans' if trans else '')
                                rrow.label('Scale' if scale else '')

            meshProps = bpy.context.scene.MeshProp
            col = layout.column(align=True)
            row = col.row(align=True)
            row.operator("karaage.bake_shape", text="Bake to Mesh", icon='SCRIPTWIN')
            if len(util.get_modifiers(context.object,'SHRINKWRAP')) > 0:
                row.prop    (meshProps, "apply_shrinkwap_to_mesh", text='', toggle=False)

    @classmethod
    def poll(self, context):
        p = util.getAddonPreferences()
        if not p.show_panel_appearance:
            return False
    
        obj = util.get_armature(context.active_object)
        return obj and obj.type=='ARMATURE' and "karaage" in obj

    def draw_header(self, context):
        sceneProps = context.scene.SceneProp
        row = self.layout.row(align=True)
        util.draw_info_header(row, KARAAGE_SHAPE, msg=panel_info_appearance, op=sceneProps, is_enabled="panel_appearance_enabled")

    def draw(self, context):
        armobj = util.get_armature(context.active_object)
        PanelShaping.draw_generic(self, context, armobj, self.layout)

def BoneRotationLockStates(armobj, constraint):
    try:
        deformBones       = rig.get_pose_bones(armobj, armobj.RigProps.ConstraintSet)
        constrainedBones  = [b for b in deformBones.values() if len( [c for c in b.constraints if c.type==constraint] ) > 0]
        mutedBones        = [b for b in deformBones.values() if len( [c for c in b.constraints if c.type==constraint and c.mute==True] ) > 0]
        all_count  = len(constrainedBones)
        mute_count = len(mutedBones)

        if mute_count==0:
            return 'Locked', 'Unlock'
        if mute_count == all_count:
            return 'Unlocked', 'Lock'
        return 'Partially locked', ''
    except:
        pass
    return '???', '???'

def BoneLocationLockStates(armobj):
    try:
        controlBones  = rig.get_pose_bones(armobj, armobj.RigProps.ConstraintSet)
        control_bones = [armobj.pose.bones[name[1:]] for name in controlBones.keys() if name[1:] in armobj.pose.bones]
        unmutedBones  = [b for b in control_bones if len( [c for c in b.constraints if c.type=='IK' and c.target==None and c.influence != 0] ) > 0]
        mutedBones    = [b for b in control_bones if len( [c for c in b.constraints if c.type=='IK' and c.target==None and c.influence == 0] ) > 0]
        unmuted_count = len(unmutedBones)
        mute_count    = len(mutedBones)

        if mute_count   == 0:
            return 'Locked', 'Unlock'
        if unmuted_count == 0:
            return 'Unlocked', 'Lock'

        return 'Partially locked', ''
    except:
        raise#pass
    return '???', '???'

def BoneVolumeLockStates(armobj):
    try:
        pose_bones = armobj.pose.bones
        mutedBones = []
        unmutedBones = []
        for name in SLVOLBONES:
            b = pose_bones.get(name)
            if not b:
                log.warning("Bone %s not in pose bones" % name)
                continue

            if b.lock_location[0] or b.lock_location[1] or b.lock_location[2]:
                unmutedBones.append(b)
            else:
                mutedBones.append(b)

        unmuted_count = len(unmutedBones)
        mute_count    = len(mutedBones)

        if mute_count   == 0:
            return 'Locked', 'Unlock'
        if unmuted_count == 0:
            return 'Unlocked', 'Lock'

        return 'Partially locked', ''
    except:
        raise#pass
    return '???', '???'

class PanelRigDisplay(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = _("Rig Display")
    bl_idname      = "karaage.panel_rig_display"
    bl_category    = "Karaage"
    bl_options     = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(self, context):

        try:
            if context.mode == 'OBJECT' or context.active_object is None:
                return True
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    return True
                elif 'karaage' in obj or 'Karaage' in obj:
                    return True
            return False
        except (TypeError, AttributeError):
            return False

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_RIGGING, msg=panel_info_rigging)

    def draw(self, context):

        layout = self.layout
        scn = context.scene

        currentSelection = util.getCurrentSelection(context)
        karaages         = currentSelection['karaages']
        attached         = currentSelection['attached']
        detached         = currentSelection['detached']
        weighttargets    = currentSelection['weighttargets']
        targets          = currentSelection['targets']
        active           = currentSelection['active']

        if active:
            if active.type=="ARMATURE":
                armobj = active
            else:
                armobj = active.find_armature()
        else:
            armobj = None

        if len(targets)>0:

            if context.mode in ['OBJECT','PAINT_WEIGHT', 'PAINT_VERTEX', 'EDIT_MESH']:
                all_attached   = (len(targets) > 0 and len(attached) == len(targets))            
                if all_attached or (len(karaages)==1 and (len(attached) > 0 or len(detached) > 0)):

                    skinning_label = ""
                    custom_meshes =  util.getSelectedCustomMeshes(attached)
                    fitted  =0
                    basic   =0
                    noconfig=0
                    if len(custom_meshes) > 0:
                        for ob in custom_meshes:
                           if 'weightconfig' in ob:
                               if ob['weightconfig'] == "BASIC": basic += 1
                               else: fitted += 1
                           else:
                               noconfig +=1

                        if noconfig   == len(custom_meshes): skinning_label = " (Basic)"
                        elif basic  == len(custom_meshes): skinning_label = " (Basic)"
                        elif fitted   == len(custom_meshes): skinning_label = " (Fitted)"

        if armobj is not None and (context.mode in ['PAINT_WEIGHT','OBJECT', 'EDIT_MESH', 'POSE', 'EDIT_ARMATURE']):
            if util.is_karaage(armobj) > 0:
                mesh.displayShowBones(context, layout, active, armobj, with_bone_gui=True)

class PanelRiggingConfig(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = _("Rig Config")
    bl_idname      = "karaage.panel_rig_config"
    bl_category    = "Karaage"
    bl_options     = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(self, context):
        ui_level = util.get_ui_level()
        try:
            if ui_level == UI_SIMPLE:
                return False
            if context.mode == 'OBJECT' or context.active_object is None:
                return True
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    return True
                elif 'karaage' in obj or 'Karaage' in obj:
                    return True
            return False
        except (TypeError, AttributeError):
            return False

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_RIGGING, msg=panel_info_rigging)

    def draw(self, context):

        def draw_vector(id, vec):
            s = "%s: % .3f % .3f % .3f" % (id, vec[0], vec[1], vec[2])
            return s

        layout = self.layout
        scn = context.scene

        currentSelection = util.getCurrentSelection(context)
        karaages         = currentSelection['karaages']
        attached         = currentSelection['attached']
        detached         = currentSelection['detached']
        weighttargets    = currentSelection['weighttargets']
        targets          = currentSelection['targets']
        active           = currentSelection['active']

        if active:
            if active.type=="ARMATURE":
                armobj = active
            else:
                armobj = active.find_armature()
        else:
            armobj = None

        if len(targets)>0:

            if context.mode in ['OBJECT','PAINT_WEIGHT', 'PAINT_VERTEX', 'EDIT_MESH']:
                all_attached   = (len(targets) > 0 and len(attached) == len(targets))            
                if all_attached or (len(karaages)==1 and (len(attached) > 0 or len(detached) > 0)):

                    skinning_label = ""
                    custom_meshes =  util.getSelectedCustomMeshes(attached)
                    fitted  =0
                    basic   =0
                    noconfig=0
                    if len(custom_meshes) > 0:
                        for ob in custom_meshes:
                           if 'weightconfig' in ob:
                               if ob['weightconfig'] == "BASIC": basic += 1
                               else: fitted += 1
                           else:
                               noconfig +=1

                        if noconfig   == len(custom_meshes): skinning_label = " (Basic)"
                        elif basic  == len(custom_meshes): skinning_label = " (Basic)"
                        elif fitted   == len(custom_meshes): skinning_label = " (Fitted)"

        ui_level = util.get_ui_level()
                
        if armobj is not None and (context.mode in ['PAINT_WEIGHT','OBJECT', 'EDIT_MESH', 'POSE', 'EDIT_ARMATURE']):

            if data.get_armature_rigtype(armobj) != 'BASIC':
                box = layout.box()
                box.label(text=_("Spine control"), icon='IPO_LINEAR')

                col = box.column(align=True)
                row = col.row(align=True)
                row.label("Unfold")
                row.prop(armobj.RigProps, "spine_unfold_lower", text='lower', toggle=True)
                row.prop(armobj.RigProps, "spine_unfold_upper", text='upper', toggle=True)

            if ui_level > UI_SIMPLE and context.mode in ['EDIT_MESH', 'PAINT_WEIGHT', 'POSE', 'EDIT_ARMATURE']:

                box = layout.box()
                box.label(text=_("Bone Deform Settings"), icon='MOD_ARMATURE')
                col = box.column()

                deform_current, deform_set = mesh.SLBoneDeformStates(armobj)
                if deform_current   == 'Enabled' : icon = "POSE_HLT"
                elif deform_current == 'Disabled': icon = "OUTLINER_DATA_ARMATURE"
                else                             : icon = "BLANK1"

                row = col.split(percentage=0.5, align=True )
                if deform_current=='':
                    row.label(text=_(""), icon=icon)
                else:
                    row.label(text=_("Deform"), icon=icon)
                    if deform_set != "Disable":
                        row.operator(mesh.ButtonDeformEnable.bl_idname, text="Enable Selected").set='SELECTED'
                    if deform_set != "Enable":
                        row.operator(mesh.ButtonDeformDisable.bl_idname, text="Disable Selected").set='SELECTED'
       
                col = box.column(align=True)                
                row = col.row(align=False)
                row.operator(mesh.ButtonDeformEnable.bl_idname, text= " SL", icon_value=const.custom_icons["mbones"].icon_id, emboss=False)
                row = row.row(align=True)
                row.operator(mesh.ButtonDeformEnable.bl_idname, text="Enable").set='BASIC'
                row.operator(mesh.ButtonDeformDisable.bl_idname, text="Disable").set='BASIC'

                col = box.column(align=True)
                row = col.row(align=False)
                row.operator(mesh.ButtonDeformEnable.bl_idname, text= " Ext", icon_value=const.custom_icons["ebones"].icon_id, emboss=False)
                row = row.row(align=True)
                row.operator(mesh.ButtonDeformEnable.bl_idname, text="Enable").set='EXTENDED'
                row.operator(mesh.ButtonDeformDisable.bl_idname, text="Disable").set='EXTENDED'

                col = box.column(align=True)                
                row = col.row(align=False)
                row.operator(mesh.ButtonDeformEnable.bl_idname, text= " Vol", icon='SNAP_ON', emboss=False)
                row = row.row(align=True)
                row.operator(mesh.ButtonDeformEnable.bl_idname, text="Enable").set='VOL'
                row.operator(mesh.ButtonDeformDisable.bl_idname, text="Disable").set='VOL'

        if ui_level > UI_STANDARD and armobj and context.mode != 'OBJECT' and len(karaages)==1:

            #

            #

            #

            #

            #

            if active in karaages:

                col = box.column(align=True)
                lock_state, mute_set = rig.SLBoneStructureRestrictStates(active)
                if lock_state   == 'Disabled': icon = "RESTRICT_SELECT_ON"
                elif lock_state == 'Enabled' : icon = "RESTRICT_SELECT_OFF"
                else                         : icon = "BLANK1"
                row = col.split(percentage=0.5, align=True )
                row.label(text=_("Structure"), icon=icon)
                if mute_set != 'Disable':
                    row.operator(mesh.ButtonArmatureAllowStructureSelect.bl_idname, text="Enable")
                if mute_set != 'Enable':
                    row.operator(mesh.ButtonArmatureRestrictStructureSelect.bl_idname, text="Disable")

class PanelRigJointOffsets(bpy.types.Panel):
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = 'data'
    bl_label       = "Joint Positions"
    bl_idname      = "karaage.panel_rig_joint_offsets"
    bl_category    = "Karaage"
    bl_options     = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(self, context):
        if not util.use_sliders(context):
            return False

        ui_level = util.get_ui_level()
        try:
            if ui_level == UI_SIMPLE:
                return False

            obj = context.active_object
            if context.active_object is None:
                return False

            if obj.type != 'ARMATURE':
                return False
            return 'karaage' in obj or 'Karaage' in obj

        except (TypeError, AttributeError):
            return False

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_RIGGING, msg=panel_info_rigging)

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        armobj = context.active_object
        joint_offset_list = armobj.data.JointOffsetList
        if len(joint_offset_list) > 0:
            row = layout.row()
            row.alignment='LEFT'
            row.prop(armobj.RigProps,"display_joint_heads")
            row.prop(armobj.RigProps,"display_joint_tails")
            row.label('Offsets, values in [mm]')
            col = layout.column()
            col.template_list('JointOffsetPropVarList',
                             'JointOffsetList',
                             armobj.data,
                             'JointOffsetList',
                             armobj.data.JointOffsetIndex,
                             'index',
                             rows=5)
                    
class PanelSkinning(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = "Skinning Tools"
    bl_idname      = "karaage.panel_skinning"
    bl_category    = "Karaage"
    bl_options     = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(self, context):

        try:
            if context.active_object is None:
                return False
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    return True
                elif 'karaage' in obj or 'Karaage' in obj:
                    return True
            return None
        except (TypeError, AttributeError):
            return None
            
    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_SKINNING, msg=panel_info_skinning)

    def check_bindable(self, detached):
        state = 0
        for ob in detached:
            if any(s != 1 for s in ob.scale):
                state |= OB_SCALED
                if any(s<0 for s in ob.scale):
                    state |= OB_NEGSCALED
            if any(s!=0 for s in ob.rotation_euler):
                state |= OB_ROTATED
            if any(s!=0 for s in ob.rotation_euler):
                state |= OB_ROTATED
            if any(s!=0 for s in ob.location):
                state |= OB_TRANSLATED
        return state

    def draw(self, context):

        layout = self.layout
        scn = context.scene
        sceneProps = scn.SceneProp

        currentSelection = util.getCurrentSelection(context)
        karaages         = currentSelection['karaages']
        attached         = currentSelection['attached']
        detached         = currentSelection['detached']
        weighttargets    = currentSelection['weighttargets']
        targets          = currentSelection['targets']
        active           = currentSelection['active']

        if active:
            if active.type=="ARMATURE":
                armobj = active
            else:
                armobj = active.find_armature()
        else:
            armobj = None

        if context.mode in ['OBJECT','PAINT_WEIGHT', 'PAINT_VERTEX', 'EDIT_MESH', 'POSE']:
            all_attached   = (len(targets) > 0 and len(attached) == len(targets))
            if all_attached or (len(karaages)==1 and (len(attached) > 0 or len(detached) > 0)):

                skinning_label = ""
                custom_meshes =  util.getSelectedCustomMeshes(attached)
                fitted  =0
                basic   =0
                noconfig=0
                if len(custom_meshes) > 0:
                    for ob in custom_meshes:
                       if 'weightconfig' in ob:
                           if ob['weightconfig'] == "BASIC": basic += 1
                           else: fitted += 1
                       else:
                           noconfig +=1

                    if noconfig   == len(custom_meshes): skinning_label = " (Basic)"
                    elif basic  == len(custom_meshes): skinning_label = " (Basic)"
                    elif fitted   == len(custom_meshes): skinning_label = " (Fitted)"

                if len(detached) > 0:
                    arm = karaages[0]
                    box = layout.box()
                    col = box.column(align=True)
                    if len(detached) == 1:
                        label = "%s"%(mesh.ButtonParentArmature.bl_label)
                    else:
                        label = "%s (%d)"%(mesh.ButtonParentArmature.bl_label, len(detached))

                    bind_state = self.check_bindable(detached)
                    accept_bind = True
                    if bind_state > 1:
                        ibox = box.box()
                        col = ibox.column(align=True)
                        if bind_state & OB_NEGSCALED:
                            op=col.operator("karaage.generic_info_operator", text="Negative scales", icon="ERROR", emboss=False)
                            op.msg=messages.panel_info_negative_scales
                            accept_bind = False
                        elif bind_state & OB_SCALED:
                            op=col.operator("karaage.generic_info_operator", text="Scaled Items", icon="INFO", emboss=False)
                            op.msg=messages.panel_info_scales
                        if bind_state & OB_ROTATED:
                            op=col.operator("karaage.generic_info_operator", text="Rotated Items", icon="INFO", emboss=False)
                            op.msg=messages.panel_info_rotations
                        col = box.column()

                    if not accept_bind:
                        col.enabled=False
                        col.alert=True

                    col.operator(mesh.ButtonParentArmature.bl_idname, text=label)

                    col = box.column(align=True)
                    split=col.split(percentage=0.45)
                    split.label("Weight")
                    split.prop(scn.MeshProp, "skinSourceSelection", text="", toggle=False)

                    if not 'bindpose' in arm:
                        col = box.column(align=True)
                        col.prop(scn.MeshProp, "attachSliders", toggle=False)

                    if scn.MeshProp.skinSourceSelection not in ['EMPTY','NONE']:
                        col = box.column(align=True)
                        col.prop(scn.MeshProp, "clearTargetWeights", toggle=False)
                        col.prop(scn.MeshProp, "copyWeightsSelected", toggle=False)
                        col.prop(scn.MeshProp, "weight_eye_bones", toggle=False)

                    if scn.MeshProp.skinSourceSelection in ['COPY', 'KARAAGE']:
                        col = box.column(align=True)
                        col.prop(scn.MeshProp, "submeshInterpolation", toggle=False)

                    ui_level = util.get_ui_level()
                    if ui_level > UI_ADVANCED:
                        if not ('bindpose' in arm or util.always_alter_to_restpose()):
                            col = box.column(align=True)
                            col.prop(scn.MeshProp, "toTPose",         toggle=False)
                            col.enabled = not currentSelection['shapekeys']

                if len(attached) > 0:

                    if len(custom_meshes) >= 0:
                        arms, objs = util.getSelectedArmsAndObjs(context)
                        if arms and not 'bindpose' in arms[0]:
                            box=layout.column()
                            
                            attach_count = len ( [obj for obj in objs if obj.ObjectProp.slider_selector!='NONE'] )
                            detach_count = len ( objs ) - attach_count

                            row = box.row(align=True)

                            if util.use_sliders(context) and (attach_count > 0 or detach_count > 0):
                                bbox = box.box()
                                txt = "Appearance Control (%d/%d)"%(attach_count, len(objs))
                                bbox.label(txt, icon="UI")
                                col = bbox.column(align=True)
                                col.prop(context.object.ObjectProp, "slider_selector", expand=True)
                                col = bbox.column(align=True)
                                row=col.row(align=True)
                                
                            if attach_count == 0:
                                txt = "%s detached" % util.pluralize("Slider", count = detach_count)
                            elif attach_count == 1:
                                txt = "Apply Slider"
                            else:
                                txt = 'Apply Sliders (%d)' % attach_count
                            row.operator(mesh.ButtonApplyShapeSliders.bl_idname, text=txt, icon="ALIGN")
                            row.operator("karaage.refresh_character_shape", text="", icon="FILE_REFRESH")
                            if armobj:
                                row.enabled = attach_count > 0
                                box=layout.column()
                                bbox = box.box()
                                mesh.ButtonGenerateWeights.skin_preset_draw(armobj, scn.MeshProp, context, bbox)

                    layout.separator()
                    row = layout.row(align=True)
                    if len(attached) == 1:
                        label = "%s" % mesh.ButtonUnParentArmature.bl_label
                    else:
                        label = "%s (%d)"%(mesh.ButtonUnParentArmature.bl_label, len(attached))

                    prop = row.operator(mesh.ButtonUnParentArmature.bl_idname, text=label)
                    prop.freeze = active.ObjectProp.apply_armature_on_unbind
                    row.prop(active.ObjectProp, "apply_armature_on_unbind", text='', icon='FREEZE')

            elif len(karaages) ==1:

                if util.use_sliders(context) and not 'bindpose' in karaages[0]:
                    children = util.getCustomChildren(karaages[0], type='MESH')
                    if children:
                        attach_count = len ( [obj for obj in children if obj.ObjectProp.slider_selector!='NONE'] )
                        bbox = layout.box()
                        bbox.label("Appearance Control (%d/%d)"%(attach_count, len(children)), icon="UI")
                        col = bbox.column(align=True)
                        col.prop(context.object.ObjectProp, "slider_selector", expand=True)

                        if attach_count > 0:
                            col = bbox.column(align=True)
                            col.operator(mesh.ButtonApplyShapeSliders.bl_idname, text="Apply %d Sliders" % attach_count, icon="ALIGN")

class PanelPosing(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = _("Posing")
    bl_idname      = "karaage.panel_posing"
    bl_category    = "Karaage"
    bl_options     = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(self, context):

        ui_level = util.get_ui_level()
        if ui_level== UI_SIMPLE:
            return False

        try:
            armobj = util.get_armature(context.object)
            return armobj!=None and context.mode in ['OBJECT','PAINT_WEIGHT', 'PAINT_VERTEX', 'EDIT_MESH', 'POSE', 'EDIT_ARMATURE']

        except (TypeError, AttributeError):
            return False

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_SKINNING, msg=panel_info_posing)

    def draw(self, context):

        layout = self.layout
        scn    = context.scene
        active = context.object
        armobj = util.get_armature(active)

        rigtype         = armobj.RigProps.RigType
        joints          = rig.get_joint_cache(armobj)
        is_in_edit_mode = context.mode in ['EDIT_ARMATURE']
        has_joints      = joints and len(joints) > 0
        ui_level        = util.get_ui_level()

        if has_joints:
            mod="edited"
            msg=panel_info_edited_joints
        else:
            mod = "unchanged"
            msg=panel_info_clean_joints
        rts = rigtype[0].upper() + rigtype[1:].lower()
        label ="%s (%s)" % (rts,mod)
        row = layout.row(align=True)
        util.draw_info_header(row, KARAAGE_TOOLS, msg=msg)
        row.label(label)

        if ui_level > UI_SIMPLE:
            row = layout.row(align=True)
            row.prop(armobj.data,"pose_position", expand=True)

        if ui_level >= UI_ADVANCED and has_joints:
            row = layout.row(align=True)
            row.operator('karaage.draw_offsets')

        if ui_level > UI_ADVANCED:
            layout.separator()
            sceneProps  = scn.SceneProp
            last_select = bpy.types.karaage_armature_presets_menu.bl_label
            row = layout.row(align=True)
            row.prop(sceneProps, "armature_preset_apply_as_Restpose", text='', icon='FREEZE')
            row.prop(sceneProps, "armature_preset_apply_all_bones",   text='', icon='GROUP_BONE')
            if not sceneProps.armature_preset_apply_as_Restpose:
                row.prop(sceneProps, "armature_preset_adjust_tails",   text='', icon='LINKED')
            row.menu("karaage_armature_presets_menu", text=last_select )
            row.operator("karaage.armature_presets_add", text="", icon='ZOOMIN')
            if last_select not in ["Armature Presets", "Presets"]:
                row.operator("karaage.armature_presets_update", text="", icon='FILE_REFRESH')
                row.operator("karaage.armature_presets_remove", text="", icon='ZOOMOUT').remove_active = True

        if util.use_sliders(context) and (ui_level >= UI_ADVANCED or has_joints):
            layout.separator()
            col = layout.column(align=True)
            col.prop(armobj.RigProps,"rig_use_bind_pose")

        if ui_level > UI_STANDARD and armobj and context.mode != 'OBJECT' and 'karaage' in armobj:

            box = layout.box()

            col = box.column(align=True)
            row=col.row()

            row.label(text="Bone Constraints", icon='MOD_ARMATURE')
            row.prop(armobj.RigProps,"ConstraintSet", text="")
            
            col = box.column(align=True)
            lock_state, mute_set = BoneRotationLockStates(armobj, COPY_ROTATION)
            if lock_state   == 'Locked'  : icon_value = get_cust_icon('mlock')
            elif lock_state == 'Unlocked': icon_value = get_cust_icon('munlock')
            else                         : icon_value = get_sys_icon('BLANK1')

            row = col.split(percentage=0.5, align=True )
            row.alignment='LEFT'
            row.label(text='SL Bone Rot', icon_value=icon_value)
            if mute_set != "Lock":
                row.operator(mesh.ButtonArmatureUnlockRotation.bl_idname, text="Unlock")
            if mute_set != "Unlock":
                row.operator(mesh.ButtonArmatureLockRotation.bl_idname, text="Lock")

            col = box.column(align=True)
            lock_state, mute_set = BoneLocationLockStates(armobj)
            if lock_state   == 'Locked'  : icon_value = get_cust_icon('alock')
            elif lock_state == 'Unlocked': icon_value = get_cust_icon('aunlock')
            else                         : icon_value = get_sys_icon('BLANK1')

            row = col.split(percentage=0.5, align=True )
            row.alignment='LEFT'
            row.label(text='Anim Bone Trans', icon_value=icon_value)
            if mute_set != "Lock":
                row.operator(mesh.ButtonArmatureUnlockLocation.bl_idname, text="Unlock")
            if mute_set != "Unlock":
                row.operator(mesh.ButtonArmatureLockLocation.bl_idname, text="Lock")
            
            col = box.column(align=True)
            lock_state, mute_set = BoneVolumeLockStates(armobj)
            if lock_state   == 'Locked'  : icon = "LOCKED"
            elif lock_state == 'Unlocked': icon = "UNLOCKED"
            else                         : icon = "BLANK1"

            row = col.split(percentage=0.5, align=True )
            row.alignment='LEFT'
            row.label(text='Vol Bone Trans', icon=icon)
            if mute_set != "Lock":
                row.operator(mesh.ButtonArmatureUnlockVolume.bl_idname, text="Unlock")
            if mute_set != "Unlock":
                row.operator(mesh.ButtonArmatureLockVolume.bl_idname, text="Lock")
            
        if active and active.type in ['ARMATURE','MESH']:

            meshProps = scn.MeshProp
            sceneProps = scn.SceneProp
            box = layout.box()
            msg = "Rig Modify Tools"
            box.label(text=msg, icon='GROUP_BONE')

            col = box.column(align=True)

            if context.mode not in ['EDIT_ARMATURE', 'POSE']:
                col.label("Only available for Armatures")
                col.label("in POSE mode or Edit mode")
            else:
            
                if ui_level >= UI_ADVANCED :
                    row = col.row(align=True)

                    if context.mode == 'POSE':

                        prop = row.operator(mesh.ButtonArmatureBake.bl_idname, icon="OUTLINER_OB_ARMATURE")
                        prop.apply_armature_on_snap_rig  = armobj.ObjectProp.apply_armature_on_snap_rig
                        prop.handleBakeRestPoseSelection = 'ALL'

                        row.prop(armobj.RigProps,"generate_joint_tails", text='', icon='FORCE_CURVE')
                        row.prop(armobj.RigProps,"generate_joint_ik", text='', icon='CONSTRAINT_BONE')
                        row.prop(armobj.ObjectProp,"apply_armature_on_snap_rig", text='', icon='FREEZE')
                        col = box.column()
                        col.prop(meshProps, "adjustPoleAngle")

                    elif context.mode == 'EDIT_ARMATURE' and ui_level >= UI_EXPERIMENTAL:
                        label = "Snap Rig to Base" if scn.UpdateRigProp.base_to_rig else "Snap Base to Rig"
                        prop = row.operator(mesh.ButtonArmatureBoneSnapper.bl_idname, text=label, icon="SNAP_ON")

                        row.prop(scn.UpdateRigProp, "base_to_rig", text='', icon='ARROW_LEFTRIGHT')
                        prop.base_to_rig = scn.UpdateRigProp.base_to_rig

                    if copyrig.ButtonCopyKaraage.sliders_allowed(context) and \
                        (has_joints or (is_in_edit_mode and 'dirty' in armobj) or ui_level >= UI_EXPERIMENTAL):
                        box.separator()
                        col = box.column(align=True)
                        col.label(text="Joint Positions", icon='MOD_ARMATURE')

                        if is_in_edit_mode and 'dirty' in armobj or ui_level >= UI_EXPERIMENTAL:
                            row=col.row(align=True)
                            op = row.operator("karaage.armature_jointpos_store",  icon="FILE")
                            row.prop(sceneProps, "snap_control_to_rig", text='', icon='ARROW_LEFTRIGHT')

                            op.sync = False
                            op.snap_control_to_rig = sceneProps.snap_control_to_rig

                        if has_joints:
                            bones = util.get_modify_bones(armobj)
                            row = col.row(align=True)
                            prop = row.operator("karaage.armature_jointpos_remove", icon="X")
                            row.prop(armobj.RigProps,"keep_edit_joints", text='', icon="FREEZE")

                            prop.keep_edit_joints  = armobj.RigProps.keep_edit_joints
                            prop.affect_all_joints = True#armobj.RigProps.affect_all_joints

class PanelFitting(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = _("Fitting")
    bl_idname      = "karaage.panel_fitting"
    bl_category    = "Karaage"
    bl_options     = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(self, context):
        obj = context.object
        return obj and obj.type=='MESH' and not "karaage" in obj

    def draw(self, context):
        mesh.ButtonGenerateWeights.draw_fitting_section(context, self.layout)

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_FITTING, msg=panel_info_fitting)

class PanelAvatarShape(bpy.types.Panel):
    '''
    Control the avatar shape using SL drivers
    '''

    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_label = _("Avatar Appearance")
    bl_idname = "karaage.panel_avatar_shape"
    bl_category    = "Skinning"
    bl_options     = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(self, context):
        '''
        This panel will only appear if the object has a
        Custom Property called "karaage" (value doesn't matter)
        '''
        obj = context.active_object
        return obj and obj.type=='ARMATURE' and "karaage" in obj and (not 'bindpose' in obj)

    def draw_header(self, context):
        row = self.layout.row()
        obj = context.active_object
        if 'dirty' in obj:
            row.alert = 'dirty' in obj
            icon = 'ERROR'
            msg = panel_warning_appearance
        else:
            icon = 'NONE'
            msg = panel_info_appearance
        util.draw_info_header(row, KARAAGE_SHAPE, msg=msg, icon=icon)

    def draw(self, context):
        PanelShaping.draw_generic(self, context, context.active_object, self.layout)

class ButtonCheckMesh(bpy.types.Operator):
    bl_idname = "karaage.check_mesh"
    bl_label = _("Report")
    bl_description = _("Report statistics and potential problems with selected items to Console")

    def execute(self, context):

        try:
            original_mode = context.active_object.mode
            bpy.ops.object.mode_set(mode='OBJECT')
    
            targets = []
            for obj in context.selected_objects:
                if obj.type=='MESH':
                    targets.append(obj)
    
            report = analyseMeshes(context, targets)

            logging.info(report)
            self.report({'INFO'},_("%d Object report(s) on Console")%len(targets))

            bpy.ops.object.mode_set(mode=original_mode)
            return{'FINISHED'}    
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}    

def analyseMeshes(context, targets):
    
    scn = context.scene    
    
    report = ["--------------------Mesh Check----------------------------"]
    report.append('Number of meshes to examine: %d'%len(targets))
    report.append('')
    
    for obj in targets:
        report.append("MESH: '%s'"%obj.name)

        me = obj.to_mesh(scn, True, 'PREVIEW') 
        nfaces = len(obj.data.polygons)
        nfacesm = len(me.polygons)
        uvs = me.uv_layers
        
        #

        #
        report.append("\tNumber of vertices: %d, with modifiers applied: %d"%(len(obj.data.vertices),len(me.vertices))) 
        report.append("\tNumber of faces: %d, with modifiers applied: %d"%(nfaces, nfacesm)) 
        
        #

        #
        armature = util.getArmature(obj)
        if armature is not None:
            report.append("\tControlling armature: %s"%armature.name)
        else:
            report.append("\tFound no controlling armature so mesh will be static")
        
        #

        #
        groups = [group.name for group in obj.vertex_groups]
        unknowns=[]
        nondeform = []
        deform = []
        deform_bones = data.get_deform_bones(armature, exclude_volumes=False, exclude_eyes=False)
        for group in groups:
            if group not in deform_bones:
                if group not in unknowns:
                    unknowns.append(group)
            if armature is not None:
                if group in armature.data.bones:
                    if armature.data.bones[group].use_deform:
                        deform.append(group)
                    else:
                        nondeform.append(group)
        
        report.append("\tVertex groups present: {%s}"%",".join(groups))
        if len(unknowns) > 0:
            report.append("\tWARNING: unrecognized vertex groups (removed on export): {%s}"%",".join(unknowns))
            
        if armature is not None:
            if len(deform) > 0:
                report.append("\tDeforming bone weight groups: {%s}"%",".join(deform))
            else:
                report.append("\tPROBLEM: armature modifier but no deforming weight groups present")
                
            if len(nondeform) > 0:
                report.append("\tWARNING: Non-deforming bone weight groups (removed on export): {%s}"%",".join(nondeform))
                
        #

        #

        v_report = mesh.findWeightProblemVertices(context, obj, use_sl_list=False, find_selected_armature=True)
        
        if 'no_armature' in v_report['status']:
            report.append("\tPROBLEM: Object %s is not assigned to an Armature"%obj.name)
        else:
            if 'unweighted' in v_report['status']:
                unweighted = v_report['unweighted']
                report.append("\tPROBLEM: Found %d vertices that have zero weight"%len(unweighted))
            if 'too_many' in v_report['status']:
                problems = v_report['too_many']
                report.append("\tWARNING: there are %d vertices with more that 4 vertex groups defined"%len(problems))            
            
        #

        #
        if len(uvs)>0:
            report.append("\tUV map present")
        else:
            report.append("\tWARNING: no UV map present")
            
        report.append('')
        
    return "\n".join(report)

class PanelKaraageTool(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label = _("Tools")
    bl_idname = "karaage.tools"
    bl_category    = "Karaage"
    bl_options     = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(self, context):
        return True

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_TOOLS, msg=panel_info_tools)
        
    def draw(self, context):

        layout = self.layout
        scn    = context.scene

        meshProps      = scn.MeshProp

        currentSelection = util.getCurrentSelection(context)
        karaages         = currentSelection['karaages']
        armatures        = currentSelection['armatures']
        attached         = currentSelection['attached']
        detached         = currentSelection['detached']
        weighttargets    = currentSelection['weighttargets']
        targets          = currentSelection['targets']
        active           = currentSelection['active']

        if active:
            if active.type=="ARMATURE":
                armobj = active
            else:
                armobj = active.find_armature()
        else:
            armobj = None

        view = context.space_data
        if view and not view.lock_camera_and_layers:
            col = layout.box()
            col.alert=True
            col.label("Scene Layers disabled",icon='ERROR')
            col.label("Tools might fail")
            row=col.row(align=True)
            row.label("Enable Scene Layers here:")
            row.prop(view,"lock_camera_and_layers", text="")
        
        if armobj and armobj.is_visible(scn) and armobj.select:
            karaage_version, rig_version, rig_id, rig_type = util.get_version_info(armobj)
            if True:#karaage_version != rig_version or len(karaages)>1 or (len(armatures)>0 and len(karaages)>0):
                col = layout.column(align=True)
                ctargets = [arm for arm in bpy.context.selected_objects if arm.type=='ARMATURE' and 'karaage' in arm and arm != armobj]
                copyrig.ButtonCopyKaraage.draw_generic(None, context, layout, armobj, ctargets, repair=(karaage_version == rig_version) )

        if len(targets)>0:

            if len(targets) > 0:

                box = layout.box()
                box.label(text=_("Vertex Tools"), icon='WPAINT_HLT')
                obj = context.active_object
                col = box.column(align=True)
                col.operator(mesh.ButtonFindDoubles.bl_idname)
                col.operator(mesh.ButtonFindTooManyWeights.bl_idname)
                if len(armatures) > 0 or len(karaages) == 1:
                    col.operator(mesh.ButtonFindUnweighted.bl_idname)
                    col.operator(mesh.ButtonFindZeroWeights.bl_idname)

                box = layout.box()
                box.label(text=_("UV Tools"), icon='GROUP_UVS')
                col = box.column(align=False)

                col.operator(mesh.ButtonRebakeUV.bl_idname)

        if active and active.type in ['ARMATURE','MESH']:

            layout.separator()
            col = layout.column(align=True)
            msg = _("Weight Tools")
            col.label(text=msg, icon='GROUP_BONE')
            meshes = util.get_animated_meshes(context, armobj) if armobj else []
            sourceCount = len(meshes)
 
        resume=False
        if armobj is not None and (context.mode in ['PAINT_WEIGHT','OBJECT', 'POSE', 'EDIT_ARMATURE', 'EDIT_MESH']):
            is_karaage = util.is_karaage(armobj)
            if context.mode in ['PAINT_WEIGHT','EDIT_MESH']:
                col = layout.column(align=True)

                if context.mode == 'PAINT_WEIGHT':
                    col.operator(weights.ButtonCopyBoneWeights.bl_idname, icon="GROUP_BONE", text="Selected to Active Bone").weightCopyType="BONES"
                    split=col.split(percentage=0.7, align=True)

                    prop = split.operator(weights.ButtonMirrorBoneWeights.bl_idname, icon="MOD_MIRROR", text="Mirror opposite Bones")
                    prop.weightCopyAlgorithm = meshProps.weightCopyAlgorithm
                    split.prop(meshProps, "weightCopyAlgorithm", text="")

                    col.operator(weights.ButtonSwapWeights.bl_idname, icon="ARROW_LEFTRIGHT", text="Swap Collision with Deform")

                col.operator(weights.ButtonClearBoneWeights.bl_idname,   icon='X', text="Remove Weights")
                resume = True

        if active and active.type in ['ARMATURE','MESH']:
            row = col.row(align=True)
            op = row.operator("karaage.clear_bone_weight_groups", 
                 icon='X', 
                 text="Clean Weightmaps"
                 )
            row.prop(meshProps,"all_selected", text='', icon='GROUP_BONE')
            op.all_selected = meshProps.all_selected

        if resume:
            col.operator(weights.ButtonEnsureMirrorGroups.bl_idname, icon='POSE_DATA', text="Add missing Mirror Groups")
            if sourceCount > 1:
                label = "Copy from rigged (%d)" % (sourceCount-1)
                col.operator(weights.ButtonCopyWeightsFromRigged.bl_idname, icon="BONE_DATA", text=label)
                selcount = len(context.selected_objects)
                if selcount > 1:
                    label = "Copy from selected (%d)" % (selcount - 1)
                    col.operator(weights.ButtonCopyWeightsFromSelected.bl_idname, icon="BONE_DATA", text=label)
                col.operator(weights.ButtonWeldWeightsFromRigged.bl_idname, icon="BONE_DATA", text="Weld to rigged")

        if len(targets)>0:
            if context.mode in ['OBJECT','PAINT_WEIGHT', 'PAINT_VERTEX', 'EDIT_MESH']:

                has_shapekeys = util.selection_has_shapekeys(targets)
                if  has_shapekeys or len(armatures) > 0 or len(karaages) == 1:
                    box = layout.box()
                    box.label(text=_("Freeze Shape"), icon='EDIT')
                    meshProps = bpy.context.scene.MeshProp
                    col = box.column(align=True)
                    split = col.split(percentage=0.4)
                    split.label("Original:")
                    split.prop(meshProps, "handleOriginalMeshSelection", text="", toggle=False)

                    col = box.column(align=True)
                    col.prop(scn.MeshProp, "standalonePosed", toggle=False)
                    col = col.column(align=True)
                    if scn.MeshProp.standalonePosed:
                        col.prop(scn.MeshProp, "removeWeights", toggle=False)
                        col.enabled=scn.MeshProp.standalonePosed
                    else:
                        col.prop(scn.MeshProp, "attachSliders", toggle=False)
                        
                    if len(targets) > 1:
                        col = box.column(align=True)
                        col.prop(scn.MeshProp, "joinParts", toggle=False)
                        if scn.MeshProp.joinParts:
                            col = col.column(align=True)
                            col.prop(scn.MeshProp, "removeDoubles", toggle=False)
                            col.enabled=scn.MeshProp.joinParts

                    col = box.column(align=True)
                    op = col.operator(mesh.ButtonFreezeShape.bl_idname, icon="FREEZE")

        #

class PanelCustomExport(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = _("Collada")
    bl_idname      = "karaage.custom_collada"
    bl_options     = {'DEFAULT_CLOSED'}
    bl_category    = "Karaage"

    @classmethod
    def poll(self, context):
        p = util.getAddonPreferences()
        if not p.show_panel_collada:
            return False
        try:
            if context.mode == 'OBJECT':
                return True
            return False
        except (TypeError, AttributeError):
            return False

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_COLLADA, msg=panel_info_collada)

    def draw(self, context):
        layout = self.layout
        scn = context.scene

        currentSelection = util.getCurrentSelection(context)
        attached         = currentSelection['attached']
        targets          = currentSelection['targets']
        mesh.create_collada_layout(scn.MeshProp, context, layout, attached, targets, on_toolshelf=True)

class ArmatureInfo(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = _("Armature Info")
    bl_idname      = "karaage.armature_info"
    bl_options     = {'DEFAULT_CLOSED'}
    bl_category    = "Karaage"
    
    @classmethod
    def poll(self, context):
        armobj = context.object
        try:
            result = armobj.type=='ARMATURE'
        except:
            result = False
        return result
        
    def draw(self, context):

        layout = self.layout
        scn    = context.scene
        armobj = context.object
        box    = layout.box()
        joint_count = rig.get_joint_offset_count(armobj)
        box.label(text=_("Armature Info"), icon='ARMATURE_DATA')

        col = box.column(align=True)
        col.label("Name: %s" % armobj.name)
        
        col = box.column(align=True)
        col.label("Rig type   : %s" % (armobj.RigProps.RigType))
        col.label("Joint type : %s" % (armobj.RigProps.JointType))
        if joint_count > 0 and 'dirty' in armobj and util.use_sliders(context):
            col.label("Unsaved Joint Offsets", icon='ERROR')

        karaage_version, rig_version, rig_id, rig_type = util.get_version_info(armobj)

        col    = box.column(align=True)
        row    = col.row(align=True)       
        row.operator("karaage.display_version_operator", text="Karaage", emboss=False)
        row.operator("karaage.display_version_operator", text="%s(%s)" %(karaage_version, KARAAGE_RIG_ID), emboss=False)

        if rig_version != None:
            row    = col.row(align=True)
            row.operator("karaage.display_rigversion_operator", text="Rig", emboss=False)
            row.operator("karaage.display_rigversion_operator", text="%s(%s)" %(rig_version, rig_id), emboss=False)
        
        if rig_version != karaage_version:
            row    = col.row(align=True)
            row.operator("karaage.version_mismatch", icon="QUESTION", emboss=False)
        
        custom_meshes = util.getCustomChildren(armobj, type='MESH')
        if len(custom_meshes) > 0:
            bbox = box.box()
            col = bbox.column(align=True)
            col.label("Custom Mesh table")
            for cm in custom_meshes:
                col = col.column(align=True)
                op = col.operator("karaage.object_select_operator", text=cm.name, icon="OBJECT_DATA")
                op.name=cm.name
        else:
            col = box.column(align=True)
            col.label(_("no Custom Mesh"))
        
        col    = box.column(align=True)
        row    = col.row(align=True)
        
        bone_count = len(animation.find_animated_bones(armobj))
        if bone_count == 0:
            row.label(_("No Animation"))
        else:
            row.label(text="", icon="FILE_TICK")
            row.label("%d Animated Bones" % bone_count)
            
MIN_MESH_INFO_DELAY = 0.5
MIN_SIZE  = 2

nvertices = 0
nvnormals = 0
nfaces    = 0
nmat      = 0
ntris     = 0
nuvs      = 0

maxtris   = 0

radius     = 0
nvc_lowest = 0
nvc_low    = 0
nvc_mid    = 0
nvc_high   = 0

nwc_effective = []
nwc_discarded = []

last_object = None
last_mode = None
last_timestamp = time.time()
no_uv_layers = 0

def init_mesh_info_panel(context):

    global last_object
    global last_mode
    global last_timestamp

    ob = context.object
    if ob == None or ob.type != 'MESH':
        return False
        
    if context.object == last_object and context.mode == last_mode and time.time() - last_timestamp < MIN_MESH_INFO_DELAY:
        return False
        
    global nvertices, nvnormals, nfaces, nmat, ntris, nuvs, no_uv_layers, maxtris, radius, nvc_lowest, nvc_low, nvc_mid, nvc_high

    nvertices      = 0
    nvnormals      = 0
    nfaces         = 0
    nmat           = 0
    ntris          = 0
    nuvs           = 0
    no_uv_layers    = 0

    maxtris        = 0

    radius         = 0
    nvc_lowest     = 0
    nvc_low        = 0
    nvc_mid        = 0
    nvc_high       = 0
    
    nwc_effective = []
    nwc_discarded = []
    
    last_object    = context.object
    last_mode      = context.mode
    last_timestamp = time.time()

    return True

class PanelMeshInfo(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label       = _("Mesh Info")
    bl_idname      = "karaage.mesh_info"
    bl_options     = {'DEFAULT_CLOSED'}
    bl_category    = "Karaage"

    @classmethod
    def poll(self, context):
        for obj in context.selected_objects:
           if obj.type=='MESH':
               return True
        return False
        
    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_RIGGING, msg=panel_info_mesh)

    def draw(self, context):
    
        layout = self.layout
        scn = context.scene

        try:
            if len ([obj for obj in context.selected_objects if obj.type == 'MESH']) == 0:
                row = layout.row()
                row.label(text=_("No Mesh selected"), icon='INFO')
                return
        except (TypeError, AttributeError):
            return
        
        currentSelection = util.getCurrentSelection(context)
        targets          = currentSelection['targets']
        active           = currentSelection['active']

        global no_uv_layers

        if len(targets) > 0:
        
            global nvertices
            global nvnormals
            global nfaces
            global nmat
            global emat
            global ntris
            global nuvs

            global maxtris

            global radius
            global nvc_lowest
            global nvc_low
            global nvc_mid
            global nvc_high
            
            global nwc_effective
            global nwc_discarded

            if init_mesh_info_panel(context):
                nmat = 0
                emat = 0
                nwc_effective = []
                nwc_discarded = []
                no_uv_layers  = 0
                
                for meshobj in targets:
                    arm = meshobj.find_armature()
                    
                    if arm and len(meshobj.vertex_groups) > 0 :
                        weighted_bones = [v for v in meshobj.vertex_groups if v.name in arm.data.bones]
                        for v in weighted_bones:
                            wbl = "%s : %s" % (meshobj.name, v.name)
                            if arm.data.bones[v.name].use_deform:
                                nwc_effective.append(wbl)
                            else:
                                nwc_discarded.append(wbl)
                    
                    me = meshobj.to_mesh(scn, True, 'PREVIEW') 
                    vertex_count = len(me.vertices)
                    uv_count = None
                    normals_count = 0

                    faces    = len(me.polygons)
                    loops    = len(me.loops)
                    flat_face_normals   = [poly.loop_total for poly in me.polygons if not poly.use_smooth]
                    smooth_face_normals = [poly.loop_total for poly in me.polygons if poly.use_smooth]
                    normals_count =  max(sum(flat_face_normals),vertex_count)
                    uv_active=me.uv_layers.active
                    if uv_active:
                        uv_count = util.get_uv_vert_count(me)

                    nvnormals += normals_count 
                    nfaces    += faces
                    nvertices += vertex_count
                    if uv_count is None:
                        uv_count = 0
                        no_uv_layers += 1
                    else:
                        nuvs      += uv_count
                        
                    tris = util.get_tri_count(faces, loops)
                    if faces > 0:
                        tris = int(((loops / faces) - 2) * faces + 0.5)

                    ntris += tris;
                    mat, warns = util.get_highest_materialcount([meshobj])
                    mate = int(tris / 21844)
                    if mat + mate  > nmat:
                        nmat = mat
                        emat = mate
                    if tris > maxtris: maxtris = tris
                    
                    radius, vc_lowest, vc_low, vc_mid, vc_high = util.get_approximate_lods(meshobj, vertex_count, normals_count, uv_count, tris)

                    nvc_lowest += vc_lowest
                    nvc_low    += vc_low
                    nvc_mid    += vc_mid
                    nvc_high   += vc_high
                    
                    bpy.data.meshes.remove(me)

            meshsize_icon     = "FILE_TICK"
            high_tris         = False
            high_tricount_msg = None
            if maxtris > 65536:
                meshsize_icon="ERROR"
                high_tris = True
                high_tricount_msg = messages.msg_mesh_tricount % maxtris
            elif maxtris > 21844:
                meshsize_icon = "INFO"
                high_tris = True
                high_tricount_msg = messages.msg_face_tricount % maxtris
                
            box = layout.box()
            box.label(text=_("Mesh Info"), icon='OBJECT_DATAMODE')
            col = box.column(align=True)
            
            row = col.row(align=True)
            if len(targets) == 1 and context.active_object == targets[0]:
                row.label(_("%s:")%targets[0].name)
            else:
                row.label(_("Meshes:"))
                row.label("%d"%len(targets))

            row = col.row(align=True)
            row.alignment='LEFT'
            op=row.operator("karaage.generic_info_operator", text=" Verts:", icon="BLANK1", emboss=False)
            op.msg="Sum of all vertices in All selected meshes"
            row.label("%d"%nvertices)

            row = col.row(align=True)
            row.alignment='LEFT'
            op=row.operator("karaage.generic_info_operator", text="Faces:", icon="BLANK1", emboss=False)
            op.msg="Sum of all faces in All selected meshes"
            row.label("%d"%nfaces)

            if high_tris:
                row = col.row(align=True)
                row.alignment='LEFT'
                op = row.operator("karaage.tris_info_operator", text="   Tris:", icon=meshsize_icon, emboss=False)
                op.msg  = high_tricount_msg
                op.icon = meshsize_icon
                row.label("%d"%ntris)
            else:
                row = col.row(align=True)
                row.alignment='LEFT'
                op=row.operator("karaage.generic_info_operator", text="   Tris:", icon=meshsize_icon, emboss=False)
                op.msg="Sum of all Triangles in All selected meshes"
                row.label("%d"%ntris)
            
            if nuvs > 0:
                row = col.row(align=True)
                row.alignment='LEFT'
                op=row.operator("karaage.generic_info_operator", text="   UVs:", icon="BLANK1", emboss=False)
                op.msg="Sum of all UV Faces in All selected meshes"
                row.label("%d"%nuvs)
                                  
            row = col.row(align=True)
            row.alignment='LEFT'
            icon = 'FILE_TICK'
            if nmat == 0:
                mat_label = "n.a."
                op=row.operator("karaage.generic_info_operator", text="Mats:", icon=icon, emboss=False)
                op.msg="No Materials defined"
            else:
                if emat > 0:
                    mat_label = "%d + %d"%(nmat,emat)
                    icon = 'ERROR'
                    msg = "Detected Material Split (triangle count on texture face > 21844)"
                else:
                    mat_label = "%d"%nmat
                    msg = "Material Count of Mesh with most defined Materials"
                op=row.operator("karaage.generic_info_operator", text="Mats:", icon=icon, emboss=False)
                op.msg=msg
            row.label(mat_label)
            
            ld = len(nwc_discarded) 
            le = len(nwc_effective)
            if ld + le > 0:        
                
                if le > 0:
                    row = col.row(align=True)
                    op = row.operator("karaage.weightmap_info_operator", text="", icon="INFO", emboss=False)
                    msg= messages.msg_identified_weightgroups % len(nwc_effective)
                    for v in nwc_effective:
                        msg += v+"\n"
                    op.msg=msg
                    op.icon="INFO"
                    row.label("Using %d Weight Maps"%le)
                if ld > 0:
                    col = box.column(align=True)
                    col.label("Deforming Weight Maps")
                
                    row = col.row(align=True)
                    op = row.operator("karaage.weightmap_info_operator", text="", icon="ERROR", emboss=False)
                    msg= messages.msg_discarded_weightgroups % len(nwc_discarded)
                    for v in nwc_discarded:
                        msg += v+"\n"
                    op.msg=msg
                    op.icon="WARNING"
                    row.label("ignored %d Weight Maps"%ld)
                    
            if no_uv_layers > 0:
                label = "Missing %d %s" % (no_uv_layers, util.pluralize("UV-Map",no_uv_layers ))
                msg = util.missing_uv_map_text(targets)
                col    = box.column(align=True)
                row    = col.row(align=True)
                op     = row.operator("karaage.uvmap_info_operator", text="", icon="ERROR", emboss=False)
                op.msg = msg
                op.icon="WARNING"
                row.label(label)
               
            if len(targets)>0:
                icol = box.column()
                icol.label(text=_("Estimates:"))
                ibox = box.box()
                icol = ibox.column(align=True)
                
                row = icol.row(align=True)
                row.label(_("LOD"))
                row.label("Tris")
                row.label("Verts")

                row = icol.row(align=True)
                row.label(_("High"))
                row.label("%d"%ntris)
                row.label("%d"%nvc_high)
 
                row = icol.row(align=True)
                row.label(_("Medium"))
                row.label("%d"%max(MIN_SIZE, int(ntris/4)))
                row.label("%d"%int(nvc_mid))
                                       
                row = icol.row(align=True)
                row.label(_("Low"))
                row.label("%d"%max(MIN_SIZE, int(ntris/16)))
                row.label("%d"%int(nvc_low))

                row = icol.row(align=True)
                row.label(_("Lowest"))
                row.label("%d"%max(MIN_SIZE, int(ntris/32)))
                row.label("%d"%int(nvc_lowest))

                icol = ibox.column(align=True)
                
                row = icol.row(align=True)
                row.label(_("Server Costs"))
                row.label("%.1f"%(0.5*len(targets)))
                        
            col = box.column(align=True)
            col.operator(ButtonCheckMesh.bl_idname, icon="QUESTION")

class PanelKaraageUpdate(bpy.types.Panel):
    from . import bl_info
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label    = "Maintenance"
    bl_idname   = "karaage.update_migrate"
    bl_category = "Karaage"
    bl_options  = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(self, context):
        return True

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_DOWNLOAD, msg=panel_info_register)

    def draw(self, context):

        layout = self.layout
        addonProps     = util.getAddonPreferences()

        url = RELEASE_INFO + "?myversion=" + util.get_addon_version() + "&myblender=" + str(util.get_blender_revision())
        box   = layout.box()
        box.label(text="My Products")
        col = box.column(align=True)
        if addon_utils.check("karaage")[0]:
            import karaage
            info = karaage.bl_info
            row = col.row()
            row.label( info['name']    )
            row.label( str(info['version']) )

        if addon_utils.check("sparkles")[0]:
            import sparkles
            info = sparkles.bl_info
            row = col.row()
            row.label( info['name']    )
            row.label( str(info['version']) )

        if addon_utils.check("primstar")[0]:
            import primstar
            info = primstar.bl_info
            row = col.row()
            row.label( info['name']    )
            row.label( str(info['version']) )

        can_report   = True
        is_logged_in = True
        if addonProps.update_status=='CANUPDATE':
            opn   = 'karaage.check_for_updates'
            label = 'Login to Get %s' % addonProps.version
            can_report   = False
            is_logged_in = False
        elif addonProps.update_status=='UPDATE':
            opn   = 'karaage.download_update'
            label = 'Download Karaage-%s' % addonProps.version
        elif addonProps.update_status=='ONLINE':
            opn   = 'karaage.check_for_updates'
            label = 'Redo Check for updates'
        elif addonProps.update_status=='READY_TO_INSTALL':
            opn   = 'karaage.download_install'
            label = 'Install Karaage-%s' % addonProps.version
        elif addonProps.update_status=='ACTIVATE':
            opn   = 'karaage.download_reload'
            label = 'Reload Addon to Activate'
        else:
            opn   = 'karaage.check_for_updates'
            label = 'Check for updates' if addonProps.username == '' or addonProps.password == '' else 'Login at Machinimatrix'
            can_report   = False
            is_logged_in = False
        
        if can_report:
            box   = layout.box()
            box.label(text="Support Request")

            col = box.column(align=True)
            col.prop(addonProps, "ticketTypeSelection")
            col = box.column(align=True)
            col.prop(addonProps, "productName" )

            col = box.column(align=True)
            col.prop(addonProps, "addonVersion")
            col.prop(addonProps, "blenderVersion")
            col.prop(addonProps, "operatingSystem")
            col.enabled = False
            col = box.column(align=True)
            col.operator('karaage.send_report', text="Create Report", icon="RADIO")        
        
        box   = layout.box()
        box.label(text="My account")
        col = box.column(align=True)
        row = col.row(align=True)
        
        wlabel = "Welcome, %s" % addonProps.user.replace("+"," ") if addonProps.user != '' else "My Machinimatrix Account"
        
        row.operator("wm.url_open", text=wlabel, icon='NONE', emboss=False).url=KARAAGE_DOWNLOAD
        row.operator("wm.url_open", text="",icon='INFO',emboss=False).url=KARAAGE_DOWNLOAD
        
        col = box.column(align=True)
        col.prop(addonProps,"username",  emboss = not is_logged_in)
        col.prop(addonProps,"password",  emboss = not is_logged_in)
        
        if not is_logged_in:
            row = box.row(align=True)
            row.alignment='RIGHT'
            row.prop(addonProps,"keep_cred", emboss = not is_logged_in)

        row=box.row(align=True)
        row.operator(opn, text=label, icon="URL")
        row.operator("karaage.download_reset", text='', icon="X")

        col = box.column(align=True)
        if addonProps.update_status=='CANUPDATE':
            col.label("Update available after login", icon="ERROR")
        elif addonProps.update_status=='UPDATE':
            split = col.split(percentage=0.2)
            split.label("Server:")
            split.alignment='RIGHT'
            split.label(addonProps.server)

        else:
            split = col.split(percentage=0.2, align=True)
            split.label("Status:")
            split.alignment='RIGHT'
            label = addonProps.update_status
            if label == 'ONLINE':
                label = "You are up to date"
                split.label(label)
            else:
                split.prop(addonProps, "update_status", text='', emboss=False)
                split.alignment='RIGHT'
                split.enabled=False
        
class PanelRigLayers(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_label =_("Mesh display")
    bl_idname = "karaage.rig_layers"
    bl_category    = "Rigging"

    @classmethod
    def poll(self, context):
        try:
            return "karaage" in context.active_object
        except TypeError:
            return None

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        armobj = util.get_armature(obj)
        box = layout.box()
        box.label(text=_("Animation Bone Style:"), icon='POSE_HLT')
        col = box.column(align=True)
        col.operator("karaage.use_custom_shapes", icon='OUTLINER_OB_CURVE')
        col.operator("karaage.use_stick_shapes", icon='BONE_DATA')

        box = layout.box()
        box.label(text=_("Hide Mesh:"), icon='MESH_DATA')
        col = box.column(align=True)

        meshes = util.findKaraageMeshes(obj)
        if "hairMesh" in meshes: col.prop(meshes["hairMesh"], "hide", toggle=True, text=_("Hair"))
        if "headMesh" in meshes:col.prop(meshes["headMesh"], "hide", toggle=True, text=_("Head"))
        if "eyelashMesh" in meshes:col.prop(meshes["eyelashMesh"], "hide", toggle=True, text=_("Eyelashes"))
        row = col.row(align=True)
        if "eyeBallLeftMesh" in meshes:row.prop(meshes["eyeBallLeftMesh"], "hide", toggle=True, text=_("Eye L"))
        if "eyeBallRightMesh" in meshes:row.prop(meshes["eyeBallRightMesh"], "hide", toggle=True, text=_("Eye R"))
        if "upperBodyMesh" in meshes:col.prop(meshes["upperBodyMesh"], "hide", toggle=True, text=_("Upper Body"))
        if "lowerBodyMesh" in meshes:col.prop(meshes["lowerBodyMesh"], "hide", toggle=True, text=_("Lower Body"))
        if "skirtMesh" in meshes:col.prop(meshes["skirtMesh"], "hide", toggle=True, text=_("Skirt"))
