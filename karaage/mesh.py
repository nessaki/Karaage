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
from math import pi, exp, degrees

from . import bind, const, create, data, util, rig, shape, bl_info, weights
from bpy.app.handlers import persistent
from .const import *
from .context_util import set_context

WEIGHTS_OK       = 0
NO_ARMATURE      = 1
MISSING_WEIGHTS  = 2

BoneDisplayDetails        = True
SkinningDisplayDetails    = False
ColladaDisplayAdvanced    = False
ColladaDisplayUnsupported = False
ColladaDisplayTextures    = False

translator = gettext.translation('karaage', LOCALE_DIR, fallback=True)
_ = translator.gettext

log_export = logging.getLogger('karaage.export')
log  = logging.getLogger('karaage.mesh')

def current_selection_can_export(context):
    try:
        if context.mode == 'OBJECT':
            for obj in [o for o in context.scene.objects if o.select]:
                if obj.type == 'MESH':
                    return True
    except (TypeError, AttributeError):
        pass
    return False

def create_collada_layout(data, context, layout, attached, targets, on_toolshelf=False):
    if not context.active_object:
        return

    ui_level = util.get_ui_level()
    sceneProps   = context.scene.SceneProp

    obox = layout.box()
    obox.enabled = len(targets) > 0
    obox.label(text=_("Export to Second Life"), icon='FILE_BLANK')
    
    use_sliders = False
    in_restpose = False
    has_meshes = current_selection_can_export(context) and len(targets) > 0
    can_export = has_meshes

    armobj = util.get_armature(context.active_object)
    if armobj:
        use_sliders = util.use_sliders(context)
        in_restpose = armobj.RigProps.restpose_mode
        
        if use_sliders and not sceneProps.collada_export_with_joints:
            jol = armobj.data.JointOffsetList
            can_export = has_meshes and (in_restpose or (jol == None or len(jol) == 0))

    if ui_level > UI_SIMPLE:
        box = obox.box()
        col = box.column(align=True)
        col.prop(data, "exportRendertypeSelection", toggle=False)

        icon = util.get_collapse_icon(ColladaDisplayTextures)
        box = obox#.box()
        col = obox.column(align=True)
        row = col.row(align=True)
        row.operator(ButtonColladaDisplayTextures.bl_idname, text="", icon=icon)
        row.operator(ButtonColladaDisplayTextures.bl_idname, text=_("Textures"), icon='TEXTURE')

    if ui_level > UI_SIMPLE:
        d = util.getAddonPreferences(data=data)
        if ColladaDisplayTextures:
            col = box.column(align=True)
            col.prop(data, "exportIncludeUVTextures", toggle=False)
            col.prop(data, "exportIncludeMaterialTextures", toggle=False)

            col=box.column(align=True)
            col.prop(d, "exportImagetypeSelection", text='', toggle=False, icon="IMAGE_DATA")
            t = "Use %s for all images" % d.exportImagetypeSelection
            col.prop(d, "forceImageType", text=t, toggle=False)
            col.prop(d, "useImageAlpha", text="Use RGBA", toggle=False)

        icon = util.get_collapse_icon(ColladaDisplayAdvanced)
        box = obox#.box()
        col = obox.column(align=True)
        row = col.row(align=True)
        row.operator(ButtonColladaDisplayAdvanced.bl_idname, text="", icon=icon)
        row.operator(ButtonColladaDisplayAdvanced.bl_idname, text=_("Advanced"), icon='MODIFIER')

        if ColladaDisplayAdvanced and ui_level > UI_SIMPLE:
            
            if use_sliders:
                col = box.column(align=True)
                col.prop(armobj.RigProps,"rig_use_bind_pose")

            if ui_level > UI_SIMPLE:
                col = box.column(align=True)
                col.prop(data, "applyScale", toggle=False)

                col = box.column(align=True)
                col.prop(data, "apply_mesh_rotscale", toggle=False)

                col = box.column(align=True)
                col.prop(data, "weld_normals", toggle=False)
                col.prop(data, "weld_to_all_visible", toggle=False)

                if ui_level > UI_STANDARD:
                    obox = obox#.box()
                    obox.label("Bone filters")
                    col = obox.column()
                    col.prop(sceneProps,"collada_export_with_joints")
                    col.enabled = sceneProps.target_system != 'RAWDATA'
                    col = obox.column()
                    col.prop(sceneProps,"collada_only_weighted")
                    col.prop(sceneProps,"collada_only_deform")
                    col.prop(sceneProps,"collada_full_hierarchy")
                    col.prop(sceneProps,"collada_export_boneroll")
                    col.prop(sceneProps,"collada_export_layers")
                    col.prop(sceneProps,"collada_blender_profile")
                    col.prop(sceneProps,"collada_export_rotated")
                    col.prop(sceneProps,"accept_attachment_weights")
                    col.prop(sceneProps,"use_export_limits")

        if d.enable_unsupported:
            icon = util.get_collapse_icon(ColladaDisplayUnsupported)
            box = obox#.box()
            col = obox.column(align=True)
            row = col.row(align=True)
            row.operator(ButtonColladaDisplayUnsupported.bl_idname, text="", icon=icon)
            row.operator(ButtonColladaDisplayUnsupported.bl_idname, text=_("Unsupported"), icon='ERROR')
            if ColladaDisplayUnsupported:   
                col = box.column(align=True)
                col.prop(data, "max_weight_per_vertex")
            
                col = box.column(align=True)

                if len(attached) == 1 and len(targets) == 1:
                    col.prop(data, "exportDeformerShape", toggle=False)

    txt = "Export to" if ui_level > UI_STANDARD else "Export"
    if on_toolshelf:
        if can_export:
            row = obox.row(align=True)
            row.operator(ButtonExportSLCollada.bl_idname, text=txt, icon="LIBRARY_DATA_DIRECT")
            txt = ''
            if ui_level > UI_STANDARD:
                row.prop(sceneProps,"target_system", text=txt)
        else:
            ibox = obox.box()
            ibox.alert=True            
            ibox.label("Export blocked", icon='ERROR')
            col = ibox.column(align=True)
            if has_meshes:
                col.label("Sliders Not in Neutral pose")
            else:
                col.label("No meshes selected")
            col.separator()
            if has_meshes:
                row = col.row(align=True)
                row.operator("karaage.reset_to_restpose", text="Set Sliders to Neutral")
                row.operator("karaage.reset_to_restpose", text='', icon='ARMATURE_DATA')

def displayShowBones(context, layout, active, armobj, with_bone_gui=False, collapsible=True):
    box = layout
    ui_level = util.get_ui_level()

    if ui_level > UI_SIMPLE:
        box.label(text=_("Bone Display Style"), icon='BONE_DATA')
        row = box.row(align=True)
        
        row.prop(armobj.RigProps,"draw_type", expand=True, toggle=False)

        row = box.row(align=True)
        row.alignment = 'LEFT'
        row.prop(armobj,"show_x_ray", text="X-Ray")
        row.prop(armobj.data,"show_bone_custom_shapes", text="Shape")
        row.prop(context.space_data, "show_relationship_lines", text="Limit")
        
        if active != armobj:
            row.prop(active.ObjectProp,"edge_display", text="Edges")

    col = box.column()
    col.label(text=_("Visibility"), icon='BONE_DATA')

    displayBoneDetails(context, box, armobj, ui_level)

def displayBoneDetails(context, box, armobj, ui_level):

    col = box.column(align=True)

    col.label("Animation Bone Groups")
    row = col.row(align=True)
    row.prop(armobj.data, "layers", index=B_LAYER_TORSO, toggle=True, text=_("Torso"), icon_value=visIcon(armobj, B_LAYER_TORSO, type='animation'))
    row.prop(armobj.data, "layers", index=B_LAYER_ORIGIN, toggle=True, text=_("Origin"), icon_value=visIcon(armobj, B_LAYER_ORIGIN, type='animation'))
    props     = util.getAddonPreferences()
    sceneProps = context.scene.SceneProp
    if armobj.RigProps.RigType == 'EXTENDED':
        row = col.row(align=True)
        row.prop(armobj.data, "layers", index=B_LAYER_HAND, toggle=True, text=_("Hands"),   icon_value=visIcon(armobj, B_LAYER_HAND, type='animation'))
        rig.create_ik_button(row, armobj, B_LAYER_IK_HAND)

    row = col.row(align=True)
    row.prop(armobj.data, "layers", index=B_LAYER_ARMS, toggle=True, text=_("Arms"),       icon_value=visIcon(armobj, B_LAYER_ARMS, type='animation'))
    rig.create_ik_button(row, armobj, B_LAYER_IK_ARMS)

    row = col.row(align=True)
    row.prop(armobj.data, "layers", index=B_LAYER_LEGS, toggle=True, text=_("Legs"), icon_value=visIcon(armobj, B_LAYER_LEGS, type='animation'))
    rig.create_ik_button(row, armobj, B_LAYER_IK_LEGS)

    if armobj.RigProps.RigType == 'EXTENDED':
        row = col.row(align=True)
        row.prop(armobj.data, "layers", index=B_LAYER_LIMB, toggle=True, text=_("Hinds"), icon_value=visIcon(armobj, B_LAYER_LIMB, type='animation'))
        rig.create_ik_button(row, armobj, B_LAYER_IK_LIMBS)

    col.separator()
    if armobj.RigProps.RigType == 'EXTENDED':
        col = col.column(align=True)
        row = col.row(align=True)
        row.prop(armobj.data, "layers", index=B_LAYER_FACE, toggle=True, text=_("Face"),    icon_value=visIcon(armobj, B_LAYER_FACE, type='animation'))
        row.prop(armobj.data, "layers", index=B_LAYER_WING, toggle=True, text=_("Wings"),  icon_value=visIcon(armobj, B_LAYER_WING, type='animation'))
        row = col.row(align=True)
        row.prop(armobj.data, "layers", index=B_LAYER_SPINE, toggle=True, text=_("Spine"),  icon_value=visIcon(armobj, B_LAYER_SPINE, type='animation'))
        row.prop(armobj.data, "layers", index=B_LAYER_TAIL, toggle=True, text=_("Tail"),   icon_value=visIcon(armobj, B_LAYER_TAIL, type='animation'))
        row.prop(armobj.data, "layers", index=B_LAYER_GROIN, toggle=True, text=_("Groin"), icon_value=visIcon(armobj, B_LAYER_GROIN, type='animation'))

    try:
        if armobj.pose.bones["EyeTarget"].bone.layers[B_LAYER_EYE_TARGET]:
            row = col.row(align=True)
            row.prop(armobj.data, "layers", index=B_LAYER_EYE_TARGET,     toggle=True, text=_("Eye Focus"), icon_value=visIcon(armobj, B_LAYER_EYE_TARGET, type='animation'))
            row.prop(armobj.IKSwitches, "Enable_Eyes", text='', icon = 'FILE_TICK' if armobj.IKSwitches.Enable_Eyes else 'BLANK1')
            if armobj.pose.bones["FaceEyeAltTarget"].bone.layers[B_LAYER_EYE_ALT_TARGET]:
                row.prop(armobj.data, "layers", index=B_LAYER_EYE_ALT_TARGET, toggle=True, text=_("Alt Focus"), icon_value=visIcon(armobj, B_LAYER_EYE_ALT_TARGET, type='animation'))
                row.prop(armobj.IKSwitches, "Enable_AltEyes", text='', icon = 'FILE_TICK' if armobj.IKSwitches.Enable_AltEyes else 'BLANK1')
    except:
        pass

    deformbone_count = len(data.get_deform_bones(armobj))

    col = box.column(align=True)
    col.label("Deform Bone Groups")

    row = col.row(align=True)
    row.prop(armobj.data, "layers", index=B_LAYER_SL,          toggle=True, text=_("SL Base"), icon_value=visIcon(armobj, B_LAYER_SL, type='deform'))
    row.prop(armobj.data, "layers", index=B_LAYER_VOLUME,      toggle=True, text=_("Volume"),  icon_value=visIcon(armobj, B_LAYER_VOLUME, type='deform'))
    
    if armobj.RigProps.RigType == 'EXTENDED':
        row = col.row(align=True)
        row.prop(armobj.data, "layers", index=B_LAYER_DEFORM_HAND, toggle=True, text=_("Hands"),   icon_value=visIcon(armobj, B_LAYER_DEFORM_HAND, type='deform'))
        row.prop(armobj.data, "layers", index=B_LAYER_DEFORM_LIMB,  toggle=True, text=_("Hinds"),   icon_value=visIcon(armobj, B_LAYER_DEFORM_LIMB, type='deform'))

        row = col.row(align=True)
        row.prop(armobj.data, "layers", index=B_LAYER_DEFORM_FACE, toggle=True, text=_("Face"),    icon_value=visIcon(armobj, B_LAYER_DEFORM_FACE, type='deform'))
        row.prop(armobj.data, "layers", index=B_LAYER_DEFORM_WING, toggle=True, text=_("Wings"),   icon_value=visIcon(armobj, B_LAYER_DEFORM_WING, type='deform'))

        row = col.row(align=True)
        row.prop(armobj.data, "layers", index=B_LAYER_DEFORM_SPINE, toggle=True, text=_("Spine"),   icon_value=visIcon(armobj, B_LAYER_DEFORM_SPINE, type='deform'))
        row.prop(armobj.data, "layers", index=B_LAYER_DEFORM_TAIL, toggle=True, text=_("Tail"),    icon_value=visIcon(armobj, B_LAYER_DEFORM_TAIL, type='deform'))
        row.prop(armobj.data, "layers", index=B_LAYER_DEFORM_GROIN, toggle=True, text=_("Groin"),  icon_value=visIcon(armobj, B_LAYER_DEFORM_GROIN, type='deform'))

    if ui_level == UI_SIMPLE:
        row = col.row(align=True)
        row.prop(armobj.data, "layers", index=B_LAYER_DEFORM, toggle=True, text=_("Deform Bones"), icon_value=visIcon(armobj, B_LAYER_DEFORM, type='deform'))
    else:
        nc = box.column(align=True)
        text="Deform Bones (%d)" % deformbone_count
        nc.label("Active Deform Bones")
        row = nc.row(align=True)
        row.prop(armobj.data, "layers", index=B_LAYER_DEFORM, toggle=True, text=text, icon_value=visIcon(armobj, B_LAYER_DEFORM, type='deform'))

        row.prop(armobj.ObjectProp, "filter_deform_bones", index=B_LAYER_DEFORM, toggle=True, text="", icon='FILTER')

        row = nc.row(align=True)
        row.prop(armobj.ObjectProp, "rig_display_type", expand=True, toggle=False)
        row.enabled = armobj.data.layers[B_LAYER_DEFORM] and armobj.ObjectProp.filter_deform_bones

    if ui_level > UI_SIMPLE:
        col = box.column(align=True)
        col.label("Special Bone Groups")
        col.prop(armobj.data, "layers", index=B_LAYER_EXTRA, toggle=True, text=_("Extra"), icon_value=visIcon(armobj, B_LAYER_EXTRA, type='animation'))
        col.prop(armobj.data, "layers", index=B_LAYER_ATTACHMENT, toggle=True, text=_("Attachment"), icon_value=visIcon(armobj, B_LAYER_ATTACHMENT, type='animation'))
        col.prop(armobj.data, "layers", index=B_LAYER_STRUCTURE, toggle=True, text=_("Structure"), icon_value=visIcon(armobj, B_LAYER_STRUCTURE, type='animation'))

    if deformbone_count == 0:
        ibox = box.box()
        ibox.label("All Deform Bones Disabled", icon='ERROR')

class PanelAvatarShapeIO(bpy.types.Panel):
    '''
    Control the avatar shape using SL drivers
    '''

    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_label = _("Avatar Shape IO")
    bl_idname = "karaage.panel_avatar_shape_io"
    bl_category    = "Skinning"

    @classmethod
    def poll(self, context):
        '''
        This panel will only appear if the object has a
        Custom Property called "karaage" (value doesn't matter)
        '''
        obj = context.active_object
        return obj and obj.type=='ARMATURE' and "karaage" in obj

    @staticmethod
    def draw_generic(op, context, arm, layout):

        box = layout.box()
        col = box.column(align=True)
        col.alignment='LEFT'
        col.operator("karaage.load_props", icon="IMPORT")
        split = col.split(percentage=0.6, align=True)
        split.operator("karaage.save_props",text="Save Shape to", icon="EXPORT")
        split.prop(context.scene.MeshProp, "save_shape_selection", text="", toggle=False)
        col.operator("karaage.refresh_character_shape", icon="FILE_REFRESH")
        col.operator("karaage.delete_all_shapes", icon="X")

    def draw_header(self, context):
        util.draw_info_header(self.layout.row(), KARAAGE_SHAPE, msg=panel_info_appearance)

    def draw(self, context):
        PanelAvatarShapeIO.draw_generic(self, context, context.active_object, self.layout)

CORRECTIVE_KEY_MAP = {
    "body_fat_637":"fat_torso_634",
    "squash_stretch_head_647":"squash_stretch_head_187",
    "torso_muscles_649":"muscular_torso_106",
    "breast_size_105":"big_chest_626",
    "love_handles_676":"love_handles_855",
    "belly_size_157":"big_belly_torso_104",
    "leg_muscles_652":"muscular_legs_152",
    "butt_size_795":"big_butt_legs_151",
    "saddlebags_753":"saddlebags_854",
    "bowed_legs_841":"bowed_legs_853"
    }
    
def get_corrective_key_name_for(pid):
    if pid in CORRECTIVE_KEY_MAP:
        return CORRECTIVE_KEY_MAP[pid]
    else:
        return pid

class ButtonBoneDisplayDetails(bpy.types.Operator):
    bl_idname = "karaage.bone_display_details"
    bl_label = _("")
    bl_description = _("Hide/Unhide advanced bone display")

    toggle_details_display = BoolProperty(default=True, name=_("Toggle Details"),
        description=_("Toggle Details Display"))

    def execute(self, context):
        global BoneDisplayDetails
        BoneDisplayDetails = not BoneDisplayDetails
        return{'FINISHED'}

class ButtonColladaDisplayTextures(bpy.types.Operator):
    bl_idname = "karaage.collada_display_textures"
    bl_label = _("")
    bl_description = _("Hide/Unhide textures panel")

    toggle_details_display = BoolProperty(default=False, name=_("Toggle Details"),
        description=_("Toggle Details Display"))

    def execute(self, context):
        global ColladaDisplayTextures
        ColladaDisplayTextures = not ColladaDisplayTextures
        return{'FINISHED'}

class ButtonColladaDisplayAdvanced(bpy.types.Operator):
    bl_idname = "karaage.collada_display_advanced"
    bl_label = _("")
    bl_description = _("Hide/Unhide advanced panel\n\nThis panel contains options which are not supported by Second Life\nHowever these options may be useful when you export for other virtual worlds.")

    def execute(self, context):
        global ColladaDisplayAdvanced
        ColladaDisplayAdvanced = not ColladaDisplayAdvanced
        return{'FINISHED'}

class ButtonColladaDisplayUnsupported(bpy.types.Operator):
    bl_idname = "karaage.collada_display_unsupported"
    bl_label = _("")
    bl_description = _("Hide/Unhide unsupported panel. WARNING: Second Life does not support these Options!")

    def execute(self, context):
        global ColladaDisplayUnsupported
        ColladaDisplayUnsupported = not ColladaDisplayUnsupported
        return{'FINISHED'}

BONE_CATEGORIES = ['Head', 'Arm', 'Torso', 'Leg']        
SORTED_BASIC_BONE_CATEGORIES = {
    'Head' :[['HEAD','NECK']],
    'Arm'  :[['L_CLAVICLE', 'L_UPPER_ARM', 'L_LOWER_ARM', 'L_HAND'],['R_CLAVICLE', 'R_UPPER_ARM', 'R_LOWER_ARM', 'R_HAND']],
    'Torso':[['PELVIS', 'BELLY', 'CHEST']],
    'Leg'  :[['L_UPPER_LEG', 'L_LOWER_LEG', 'L_FOOT'],['R_UPPER_LEG', 'R_LOWER_LEG', 'R_FOOT']]
    }
        
class ButtonGenerateWeights(bpy.types.Operator):
    bl_idname = "karaage.generate_weights"
    bl_label = _("Update Weight Maps")
    bl_description = _("Create/Update Weight Maps for the selected Bones\nMore options might appear in the Operator Redo Panel at the bottom of Tool Shelf")
    bl_options = {'REGISTER', 'UNDO'}  

    focus  = FloatProperty(name="Focus", min=0.0, max=1.5, default=1.0, description="Bone influence offset (very experimental)")
    gain   = FloatProperty(name="Gain", min=0, max=10, default=1, description="Pinch Factor (level gain)")
    clean  = FloatProperty(name="Clean", min=0, max=1.0, description="remove weights < this value")
    all    = BoolProperty(name="All Bones", default=False, description = "Weight All Face Bones except eyes and Tongue" )
    limit  = BoolProperty(name="Limit to 4", default=True, description = "Limit Weights per vert to 4 (recommended)" )
    use_mirror_x = BoolProperty(name="X Mirror", default=True, description = "Use X-Mirror" )
    suppress_implode = BoolProperty(name="Suppress Implode", default=False, description = "Do not move the Bones back after weighting (for demonstration purposes only, please dont use!)" )

    def draw(self, context):
        props = context.scene.MeshProp
        type = props.weightSourceSelection
        layout = self.layout
        box = layout.box()

        if type == 'FACEGEN':
            box.label("Facegen Parameters")
            col = box.column(align=True)
            col.prop(self,"focus", text='Focus')
            col.prop(self,"gain",  text='Gain')
            col.prop(self,"clean", text='Clean')
            col.separator()
            col.prop(self, 'all')
            col.prop(self, 'limit')
            col.prop(self, 'use_mirror_x')
            col.prop(self, 'suppress_implode')
        else:
            armobj = util.get_armature(context.object)
            self.skin_preset_draw(armobj, props, context, box)

    @staticmethod
    def draw_fitting_section(context, layout):
        obj = context.object
        if not (obj and obj.type=='MESH') :
            return

        col = layout.column(align=True)
        armobj = obj.find_armature()
        if not armobj:
            return

        if not "karaage" in armobj or "avastar" in armobj:
            col.label("Object Not rigged to Karaage", icon='INFO')
            return

        if "karaage-mesh" in obj or 'avastar-mesh' in obj:
            col.operator(ButtonConvertShapeToCustom.bl_idname, icon="FREEZE")
            return

        bones = armobj.data.bones        

        last_select = bpy.types.karaage_fitting_presets_menu.bl_label
        row = col.row(align=True)
        row.menu("karaage_fitting_presets_menu", text=last_select )
        row.operator("karaage.fitting_presets_add", text="", icon='ZOOMIN')
        if last_select not in ["Fitting Presets", "Presets"]:
            row.operator("karaage.fitting_presets_update", text="", icon='FILE_REFRESH')
            row.operator("karaage.fitting_presets_remove", text="", icon='ZOOMOUT').remove_active = True

        if obj.ObjectProp.slider_selector=='NONE':
            box = layout.box()
            col = box.column(align=True)
            col.label("To see the Fitting Sliders")
            col.label("you need to enable")
            col.label("'SL Appearance'")
            col.label("in the Skinning Panel")

            return

        col = layout.column(align=True)
        col.prop(obj.FittingValues, "auto_update", text='Apply immediately', toggle=False)

        col = layout.column(align=True)
        col.label ("Physics Strength:")
        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("karaage.generate_physics")
        physics = obj['physics'] if 'physics' in obj else None

        if physics:
            row.operator("karaage.regenerate_physics", text="", icon='FILE_REFRESH')
            row.operator("karaage.delete_physics", text="", icon='X')

            row = col.row(align=True)
            row.prop(obj.FittingValues, "butt_strength"  , slider=True)
            selected = bones['BUTT'].select
            icon = 'FILE_TICK' if selected else 'BLANK1'
            p=row.operator("karaage.fitting_bone_selected_hint", text="", icon=icon)
            p.bone ='BUTT'
            p.bone2=''
            row.enabled = 'BUTT' in physics

            row = col.row(align=True)
            row.prop(obj.FittingValues, "pec_strength"   , slider=True)
            selected = bones['LEFT_PEC'].select or bones['RIGHT_PEC'].select
            icon = 'FILE_TICK' if selected else 'BLANK1'
            p = row.operator("karaage.fitting_bone_selected_hint", text="", icon=icon)
            p.bone ='RIGHT_PEC'
            p.bone2='LEFT_PEC'
            row.enabled = 'RIGHT_PEC' in physics or 'LEFT_PEC' in physics

            row = col.row(align=True)
            row.prop(obj.FittingValues, "back_strength"  , slider=True)
            selected = bones['LOWER_BACK'].select or bones['UPPER_BACK'].select
            icon = 'FILE_TICK' if selected else 'BLANK1'
            p=row.operator("karaage.fitting_bone_selected_hint", text="", icon=icon)
            p.bone ='UPPER_BACK'
            p.bone2='LOWER_BACK'
            row.enabled = 'UPPER_BACK' in physics or 'LOWER_BACK' in physics

            row = col.row(align=True)
            row.prop(obj.FittingValues, "handle_strength", slider=True)
            selected = bones['LEFT_HANDLE'].select or bones['RIGHT_HANDLE'].select
            icon = 'FILE_TICK' if selected else 'BLANK1'
            p=row.operator("karaage.fitting_bone_selected_hint", text="", icon=icon)
            p.bone ='RIGHT_HANDLE'
            p.bone2='LEFT_HANDLE'
            row.enabled = 'RIGHT_HANDLE' in physics or 'LEFT_HANDLE' in physics

        col = layout.column(align=True)
        col.label("Bone Fitting Strength:")
        col = layout.column(align=True)

        row = col.row(align=True)
        row.prop(obj.FittingValues,"boneSelection", expand=True)

        active_group = obj.vertex_groups.active
        for key in BONE_CATEGORIES:
            bone_sets = SORTED_BASIC_BONE_CATEGORIES[key]

            for set in bone_sets:

                for bname in set:

                    display = obj.FittingValues.boneSelection == 'ALL'
                    selected = bones[bname].select or bones[weights.get_bone_partner(bname)].select
                    active   = bones[bname] == bones.active or bones[weights.get_bone_partner(bname)] == bones.active
                    ansel    = active and selected
                    icon = 'LAYER_ACTIVE' if ansel else 'LAYER_USED' if selected else 'BLANK1'

                    if (not display) and (obj.FittingValues.boneSelection == 'SELECTED'):
                        display = selected
                    if (not display) and (obj.FittingValues.boneSelection == 'WEIGHTED'):
                        display = bname in obj.vertex_groups or weights.get_bone_partner(bname) in obj.vertex_groups
                    if (not display) and active_group:
                        display = (bname == active_group.name or bname == weights.get_bone_partner(active_group.name))
                    if display:
                        row = col.row(align=True)
                        row.prop(obj.FittingValues, bname, slider=True, text=weights.get_bone_label(bname))
                        p       = row.operator("karaage.fitting_bone_selected_hint", text="", icon=icon)
                        p.bone  = bname
                        p.bone2 = ''
                        
                        pgroup = weights.get_pgroup(obj, bname)
                        count  = len(pgroup) if pgroup != None else 0
                        icon   = 'LOAD_FACTORY' if count > 0 else 'BLANK1'
                        p      = row.operator("karaage.fitting_bone_delete_pgroup", text="", icon=icon)
                        p.bname = bname

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("karaage.distribute_weights", icon='SHAPEKEY_DATA')
        row.operator("karaage.smooth_weights", icon='MOD_SMOOTH')

    @staticmethod
    def skin_preset_draw(armobj, op, context, box):

        box.label("Weight Map Control", icon="SCRIPTWIN")
        col = box.column(align=True)
        col.prop(op, "weightSourceSelection", text="", toggle=True)
        col = box.column(align=True)
        col.operator(ButtonGenerateWeights.bl_idname)

        if op.weightSourceSelection not in ['EMPTY', 'NONE']:
            col.prop(op, "keep_groups", toggle=False)
            col = box.column(align=True)
            col.prop(op, "clearTargetWeights", toggle=False)
            col.prop(op, "copyWeightsSelected", toggle=False)

        if op.weightSourceSelection in ['COPY','KARAAGE', 'EXTENDED']:
            col = box.column(align=True)
            col.prop(op, "submeshInterpolation", toggle=False)
            
            if op.weightSourceSelection in ['EXTENDED', 'KARAAGE']:
                box = box.box()
                box.label(text=_("Weights from Karaage"), icon='GROUP_VERTEX')
                col = box.column(align=True)
                col.prop(op, "with_hair",       text="hair",       toggle=False)
                col.prop(op, "with_head",       text="head",       toggle=False)
                col.prop(op, "with_eyes",       text="eyes",       toggle=False)
                col.prop(op, "with_upper_body", text="upper body", toggle=False)
                col.prop(op, "with_lower_body", text="lower body", toggle=False)
                col.prop(op, "with_skirt",      text="skirt",      toggle=False)

    def with_meshes(self, context, type):
        if type in ['KARAAGE', 'EXTENDED']:
            result = []
            props = context.scene.MeshProp
            if props.with_hair:       result.append("hairMesh")
            if props.with_eyes:       result.extend(["eyeBallLeftMesh","eyeBallRightMesh"])
            if props.with_head:       result.append("headMesh")
            if props.with_lower_body: result.append("lowerBodyMesh")
            if props.with_upper_body: result.append("upperBodyMesh")
            if props.with_skirt     : result.append("skirtMesh")
        else:
            result = None

        return result

    def invoke(self, context, event):
        props = context.scene.MeshProp
        if props.weightSourceSelection == 'FACEGEN':
            armobj = util.get_armature(context.object)
            if armobj:
                pbone = armobj.data.bones.active
                if pbone:
                    self.focus  = pbone['focus'] if 'focus' in pbone else 1.0
                    self.gain   = pbone['gain']  if 'gain'  in pbone else 1.0
                    self.clean  = pbone['clean'] if 'clean' in pbone else 0.0
        return self.execute(context)

    def execute(self, context):
        status = None
        props = context.scene.MeshProp

        if props.weightSourceSelection == 'FACEGEN':
            status = rig.KaraageFaceWeightGenerator.generate(context, self.use_mirror_x, self.all, self.focus, self.gain, self.clean, self.limit, self.suppress_implode)
            armobj = util.get_armature(context.object)
            if armobj:
                pbone = armobj.data.bones.active
                if pbone:
                    pbone['focus']  = self.focus
                    pbone['gain']   = self.gain
                    pbone['clean']  = self.clean
            return status
        return self.execute_fitted(context)

    def execute_fitted(self, context):
        active = context.scene.objects.active
        selection = util.getKaraageArmaturesInScene(selection = context.selected_objects)
        props = context.scene.MeshProp

        karaage_meshes = self.with_meshes(context, props.weightSourceSelection)

        failed_armatures = 0
        failed_armature  = None

        for armobj in selection:
            if not armobj.is_visible(context.scene):
                failed_armatures += 1
                failed_armature = armobj
                continue

            context.scene.objects.active = armobj
            active_bone = armobj.data.bones.active
            arm_original_mode = util.ensure_mode_is("POSE", object=armobj)
            odata_layers = [armobj.data.layers[B_LAYER_VOLUME], armobj.data.layers[B_LAYER_SL], armobj.data.layers[B_LAYER_EXTENDED]]

            original_pose = armobj.data.pose_position
            armobj.data.pose_position="REST"
            util.ensure_mode_is("OBJECT", object=armobj)
            util.ensure_mode_is("POSE", object=armobj)

            active_pose_bone = armobj.data.bones.active
            try:
                active_vgroup     = active_pose_bone.name
                partner_vgroup    = weights.get_bone_partner(active_vgroup)
            except:
                partner_vgroup = None
            partner_pose_bone = armobj.data.bones[partner_vgroup] if partner_vgroup else active_pose_bone

            for obj in util.getCustomChildren(armobj, select=True, type='MESH'):
                print("Rigging %s:%s" % (armobj.name, obj.name) )
                original_mode = util.ensure_mode_is('WEIGHT_PAINT', object=obj)

                try:
                    active_vgroup = obj.vertex_groups.active.name
                except:
                    active_vgroup = None
                
                bone_names = util.getVisibleSelectedBoneNames(armobj)
                type       = props.weightSourceSelection
                if type == 'EXTENDED':
                    print("Generate EXTENDED weights for parts %s" % (karaage_meshes) )
                else:
                    if bone_names and len(bone_names) > 0:
                        print("Generate %s weights for %d selected bones: %s" % (type, len(bone_names), bone_names) )
                
                create_weight_groups(
                    self,
                    context,
                    target=obj,
                    bone_names=bone_names,
                    clearTargetWeights=props.clearTargetWeights,
                    submeshInterpolation=props.submeshInterpolation,
                    type=props.weightSourceSelection,
                    keep_empty_groups=props.keep_groups, 
                    selected=props.copyWeightsSelected, 
                    enforce_meshes=karaage_meshes
                )

                if not props.weightSourceSelection in ["EMPTY", "NONE"] and not props.keep_groups:
                    util.removeEmptyWeightGroups(obj)

                util.ensure_mode_is(original_mode, object=obj)
                weights.add_missing_mirror_groups(context, ob=obj)

                if partner_vgroup and partner_vgroup in obj.vertex_groups:
                    g = obj.vertex_groups[partner_vgroup]
                    obj.vertex_groups.active_index=g.index

            util.setSelectOption(armobj,[])
            #
            armobj.data.pose_position = original_pose
            context.scene.objects.active = armobj
            if partner_pose_bone:
                armobj.data.bones.active = partner_pose_bone

            util.ensure_mode_is("OBJECT", object=armobj)
            util.ensure_mode_is("POSE", object=armobj)
            util.ensure_mode_is(arm_original_mode, object=armobj)

            armobj.data.layers[B_LAYER_VOLUME]   = odata_layers[0]
            armobj.data.layers[B_LAYER_SL]       = odata_layers[1]
            armobj.data.layers[B_LAYER_EXTENDED] = odata_layers[2]
            if active_bone:
                armobj.data.bones.active = active_bone
        context.scene.objects.active = active

        if failed_armatures == 1:
            self.report({'ERROR'},_('Make Armature "%s" visible and try again') % failed_armature.name)
        elif failed_armatures > 1:
            self.report({'ERROR'},_("%d invisible armatures not processed")%failed_armatures)

        return{'FINISHED'}

class ButtonSmoothWeights(bpy.types.Operator):
    bl_idname = "karaage.smooth_weights"
    bl_label = _("Smooth Weights")
    bl_description = _("Smooth mesh by adjusting weights of selected bones")
    bl_options = {'REGISTER', 'UNDO'}

    count     = 1
    factor    = 0.5
    omode     = None
    all_verts = True
    workset   = None

    @classmethod
    def poll(self, context):
        obj = context.object
        if obj == None or obj.type != 'MESH': return False
        arm = obj.find_armature()
        if arm == None or not 'karaage' in arm:
            if not 'avastar' in arm:
                 return False
        if len([b for b in arm.data.bones if b.select]) < 1:      
            return False
        return True

    def invoke(self, context, event):
        obj = context.object
        print("Smooth %s:%s" % (obj.type, obj.name))
        if obj.type == 'ARMATURE':
            print("Need to select an object")
            return {'CANCELLED'}
        arm = util.get_armature(obj)
        if not arm:
            print("Need to be bound to an Armature")
            return {'CANCELLED'}

        self.omode = util.ensure_mode_is("OBJECT") if obj.mode == 'EDIT' else obj.mode

        selected_bone_names  = [b.name for b in arm.data.bones if b.select and b.use_deform]        
        groups = [weights.get_bone_group(obj, n) for n in selected_bone_names if weights.get_bone_partner(n)]
        self.workset = []
        for g in groups:
            name = g.name
            if weights.get_bone_partner_group(obj, name) not in self.workset:
                self.workset.append(g)

        if len(self.workset) == 0:
            bone_s = util.pluralize("bone", len(selected_bone_names))
            self.report({'ERROR'}, "Selected %s can not be smoothed by weights" % (bone_s))
            return {'CANCELLED'}

        self.all_verts = util.update_all_verts(obj, omode=self.omode)
        return self.execute(context)

    def execute(self, context):
        print("Execute...")
        obj   = context.object
        arm   = obj.find_armature()
        unsolved_weights = []
        bm = bmesh.new()

        for vgroup in self.workset:
            name    = vgroup.name
            partner = weights.get_bone_partner_group(obj, name)
            if not name.startswith('m'):
                vgroup, partner = partner, vgroup

            windices = weights.smooth_weights(context, obj, bm, vgroup, partner, all_verts=self.all_verts, count=self.count, factor=self.factor)
            unsolved_weights.extend(windices)
            bm.clear()

        misses = len(unsolved_weights)
        gcount = len(self.workset)
        bone_s = "bone "+ util.pluralize("pair", gcount)
        if misses == 0:
            self.report({'INFO'}, "Adjusted %d %s to Shape" % (gcount, bone_s))
        else:
            self.report({'WARNING'}, "Adjusted %d %s (ignored %d verts)" % (gcount, bone_s, misses))

        bm.free()
        util.ensure_mode_is(self.omode)
        print("Execute done")
        return{'FINISHED'}
        
class ButtonDistributeWeights(bpy.types.Operator):
    bl_idname = "karaage.distribute_weights"
    bl_label = _("Adjust Shape")
    bl_description = _("Optimize weights of selected Bones to match custom shape as good as possible (Needs at least one custom shapekey to define the target shape)")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        obj = context.object
        if obj == None or obj.type != 'MESH': return False
        arm = obj.find_armature()
        if arm == None or not 'karaage' in arm:
            if not 'avastar' in arm:
                 return False
        if len([b for b in arm.data.bones if b.select]) < 1:     
            return False

        sks = obj.data.shape_keys
        if sks and sks.key_blocks:
            for index, block in enumerate(sks.key_blocks.keys()):
                if index > 0 and not block in ['neutral_shape','bone_morph']:
                    return True
        return False

    def execute(self, context):
        obj = context.object
        print("Distribute in %s:%s" % (obj.type,obj.name))
        if obj.type == 'ARMATURE':
            print("Need to select an object")
            return {'CANCELLED'}
        arm = util.get_armature(obj)
        if not arm:
            print("Need to be bound to an Armature")
            return {'CANCELLED'}

        omode = util.ensure_mode_is("OBJECT") if obj.mode=='EDIT' else obj.mode

        selected_bone_names  = [b.name for b in arm.data.bones if b.select and b.use_deform]        
        groups = [weights.get_bone_group(obj, n) for n in selected_bone_names if weights.get_bone_partner(n)]
        workset = []
        for g in groups:
            if weights.get_bone_partner_group(obj, g.name) not in workset:
                workset.append(g)

        bone_s = util.pluralize("bone", len(selected_bone_names))
        if len(workset) == 0:
            self.report({'ERROR'}, "Selected %s can not be adjusted to Shape" % (bone_s))
            return {'CANCELLED'}

        unsolved_weights = []
        all_verts = util.update_all_verts(obj, omode)
        for vgroup in workset:
            partner = weights.get_bone_partner_group(obj, vgroup.name)
            if not vgroup.name.startswith('m'):
                vgroup, partner = partner, vgroup
            windices = weights.distribute_weights(context, obj, vgroup, partner, all_verts=all_verts)
            unsolved_weights.extend(windices)

        if len(unsolved_weights) == 0:
            self.report({'INFO'}, "Adjusted %d %s to Shape" % (len(workset), bone_s))
        else:
            for index in unsolved_weights:
                obj.data.vertices[index].select=True

            misses = len(unsolved_weights)
            self.report({'WARNING'}, "Adjusted %d %s (ignored %d verts)" % (len(workset), bone_s, misses))

        util.ensure_mode_is(omode)
        return{'FINISHED'}
        
class ButtonBonePresetSkin(bpy.types.Operator):
    bl_idname = "karaage.bone_preset_skin"
    bl_label = "Skin & Weight"
    bl_description = '''Prepare Rig for Skinning:

- Sets Armature to Pose Mode
- Display SL Bones (blue)
- If Active object is a Mesh and not in edit mode:
  Set Weight Paint Mode

Note: Use this Preset only for weighting tasks!
'''
    
    bl_options = {'REGISTER', 'UNDO'}  

    set_rotation_limits  = BoolProperty(name=_("Rotation Limits"), description=_("Enable rotation limits on selected bones"), default=False)
    set_x_ray            = BoolProperty(name=_("X-Ray"), description=_("Enable X-Ray Mode"), default=True)
    reset_bone_display   = BoolProperty(name=_("Reset Bone Display"), description=_("Reset Display to show the Classic bones"), default=True)

    @classmethod
    def poll(cls, context):
        if not context:
            return False
        active = context.active_object
        if not active:
            return False
        armobj = util.get_armature(active)
        return armobj != None

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        col.prop(self,"set_x_ray")
        col.prop(self,"set_rotation_limits")
        col.prop(self,"reset_bone_display")

    def invoke(self, context, event):
        armobj = util.get_armature(context.object)
        if armobj and 'dirty' in armobj:
             bind.ArmatureJointPosStore.exec_imp(self, context)
        
        return self.execute(context)
    
    def execute(self, context):
        active = context.object
        amode = util.ensure_mode_is("OBJECT", context=context)
        armobj = util.get_armature(active)

        armobj.show_x_ray=self.set_x_ray
        if self.reset_bone_display:
            rig.guess_deform_layers(armobj)
        rig.setSLBoneRotationMute(self, context, True, 'ALL')

        context.scene.objects.active=armobj
        bpy.ops.object.mode_set(mode="POSE")
        context.scene.objects.active=active
        if active == armobj:
            bpy.ops.karaage.armature_restrict_structure_select()
        else:

            mode = 'WEIGHT_PAINT' if amode != 'EDIT' else amode
            bpy.ops.object.mode_set(mode=mode)

            try:
                view = context.space_data
                view.viewport_shade      = 'SOLID'
                view.show_textured_solid = False
            except:
                pass

        context.scene.SceneProp.panel_presets = 'SKIN'
        return{'FINISHED'}    

guse_default_locks    = BoolProperty(name="Default Locks", description="Set Karaage default constraints and Bone connects", default=False)

class ButtonBonePresetAnimate(bpy.types.Operator):
    bl_idname = "karaage.bone_preset_animate"
    bl_label = "Pose & Animate"
    bl_description = '''Prepare rig for Posing and Animation
    Sets Armature to Pose Mode
    displays green control bones'''
    
    bl_options = {'REGISTER', 'UNDO'}  

    set_rotation_limits  = BoolProperty(name=_("Rotation Limits"), description=_("Enable rotation limits on selected bones"), default=False)
    set_x_ray            = BoolProperty(name=_("X-Ray"), description=_("Enable X-Ray Mode"), default=True)
    reset_bone_display   = BoolProperty(name=_("Reset Bone Display"), description=_("Reset Display to show the Classic bones"), default=True)
    use_default_locks    = guse_default_locks

    @classmethod
    def poll(cls, context):
        if not context:
            return False
        active = context.active_object
        if not active:
            return False
        armobj = util.get_armature(active)
        return armobj != None

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        col.prop(self,"set_x_ray")
        col.prop(self,"set_rotation_limits")
        col.prop(self,"reset_bone_display")
        col.prop(self,"use_default_locks")

    def invoke(self, context, event):
        armobj = util.get_armature(context.object)
        if armobj and 'dirty' in armobj:
             bind.ArmatureJointPosStore.exec_imp(self, context)
        
        return self.execute(context)

    def execute(self, context):
        active = context.object
        armobj = util.get_armature(active)

        util.ensure_mode_is("OBJECT", context=context)
        armobj.show_x_ray = self.set_x_ray
        if self.set_rotation_limits:
            rig.set_bone_rotation_limit_state(armobj, True, 'ALL')

        rig.setSLBoneRotationMute(self, context, False, 'ALL', with_reconnect=self.use_default_locks)
        if self.reset_bone_display:
            rig.guess_pose_layers(armobj)

        context.scene.objects.active=armobj
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.pose.transforms_clear()
        bpy.ops.pose.select_all(action='DESELECT')
        context.scene.SceneProp.panel_presets = 'POSE'

        return{'FINISHED'}

class ButtonBonePresetRetarget(bpy.types.Operator):
    bl_idname = "karaage.bone_preset_retarget"
    bl_label = "Retarget"
    bl_description = '''Prepare rig for for Retargetting
    Sets Armature to Object Mode'''
    
    bl_options = {'REGISTER', 'UNDO'}  

    preset = StringProperty()
    set_rotation_limits  = BoolProperty(name=_("Rotation Limits"), description=_("Enable rotation limits on selected bones"), default=False)
    set_x_ray            = BoolProperty(name=_("X-Ray"), description=_("Enable X-Ray Mode"), default=False)
    use_default_locks    = guse_default_locks

    @classmethod
    def poll(cls, context):
        if not context:
            return
        active = context.active_object
        if not active:
            return False
        armobj = util.get_armature(active)
        return armobj != None

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        col.prop(self,"set_x_ray")
        col.prop(self,"use_default_locks")
    
    def invoke(self, context, event):
        armobj = util.get_armature(context.object)
        if armobj and 'dirty' in armobj:
             bind.ArmatureJointPosStore.exec_imp(self, context)

        self.set_x_ray = True
        return self.execute(context)
        
    def execute(self, context):
        active = context.object
        amode = util.ensure_mode_is("OBJECT", context=context)
        armobj = util.get_armature(active)
            
        armobj.show_x_ray = self.set_x_ray
        armobj.data.show_bone_custom_shapes = False

        if self.set_rotation_limits:
            rig.set_bone_rotation_limit_state(armobj, True, 'ALL')

        rig.setSLBoneRotationMute(self, context, False, 'ALL', with_reconnect=self.use_default_locks)

        for i in range(0,B_LAYER_COUNT):
            armobj.data.layers[i] = (i in [B_LAYER_TORSO, B_LAYER_ARMS, B_LAYER_LEGS, B_LAYER_ORIGIN])
            
        bones = armobj.pose.bones
        for b in bones:
            for c in b.constraints:
                if c.type =='LIMIT_ROTATION':
                    c.influence = 0 
                    b.use_ik_limit_x = False
                    b.use_ik_limit_y = False
                    b.use_ik_limit_z = False

        context.scene.objects.active=armobj
        bpy.ops.object.mode_set(mode="OBJECT")
        context.scene.objects.active=active
        if active != armobj:
            util.ensure_mode_is(amode, context=context)
        context.scene.SceneProp.panel_presets = 'RETARGET'
        return{'FINISHED'}    

class ButtonBonePresetEdit(bpy.types.Operator):
    bl_idname = "karaage.bone_preset_edit"
    bl_label = "Joint Edit"
    bl_description = '''Prepare rig for Editing
    Sets armature to Edit mode
    enables select of structure Bones'''
    
    bl_options = {'REGISTER', 'UNDO'}  

    preset = StringProperty()
    set_rotation_limits  = BoolProperty(name=_("Rotation Limits"), description=_("Enable rotation limits on selected bones"), default=False)
    set_x_ray            = BoolProperty(name=_("X-Ray"), description=_("Enable X-Ray Mode"), default=False)

    @classmethod
    def poll(cls, context):
        if not context:
            return
        active = context.active_object
        if not active:
            return
        armobj = util.get_armature(active)
        return armobj != None

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        col.prop(self,"set_x_ray")
    
    def invoke(self, context, event):
        self.set_x_ray = True
        return self.execute(context)
        
    def execute(self, context):
        active = context.object
        amode = util.ensure_mode_is("OBJECT", context=context)
        armobj = util.get_armature(active)
            
        context.scene.objects.active=armobj
        bpy.ops.object.mode_set(mode="EDIT")
        armobj.show_x_ray = self.set_x_ray        
        rig.setSLBoneStructureRestrictSelect(armobj, False)
        for i in range(0,B_LAYER_COUNT):
            armobj.data.layers[i] = (i in [B_LAYER_TORSO, B_LAYER_ARMS, B_LAYER_LEGS, B_LAYER_ORIGIN, B_LAYER_STRUCTURE, B_LAYER_EYE_TARGET, B_LAYER_EXTRA, B_LAYER_SPINE])
        context.scene.SceneProp.panel_presets = 'EDIT'
        return{'FINISHED'}    

#

#

#

#
#

def set_active_shape_key(obj,shape_key_name):
    active_index = obj.active_shape_key_index
    index = 0
    try:
        while True:
            obj.active_shape_key_index = index
            if obj.active_shape_key.name == shape_key_name:
                print("Found shape key index", index)
                return
            index += 1
    except:
        obj.active_shape_key_index = active_index
        pass

def prepare_rebake_uv(context, obj):
    me=obj.data
    if len(me.uv_textures) == 0:
        return
    
    if not me.uv_textures.active.name.endswith("_rebake"):
        active_uv = me.uv_textures.active.name
        copy = me.uv_textures.new(name=active_uv+"_rebake")
        me.uv_textures.active = copy
        me.uv_textures.active.active_render = True

    seamed_edges = [edge.index for edge in me.edges if edge.use_seam]
        
    util.ensure_mode_is("EDIT")
    bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold(extend=True)
    util.select_edges(me, seamed_edges, seam=True, select=True)
    bpy.ops.mesh.mark_seam(clear=False)
    
    util.ensure_mode_is("OBJECT")
    for loop in me.loops:
        edge = me.edges[loop.edge_index]
        if edge.use_seam:
            me.uv_layers.active.data[loop.index].pin_uv=True

class ButtonRebakeUV(bpy.types.Operator):
    bl_idname = "karaage.rebake_uv"
    bl_label = _("Rebake UV Layout")
    bl_description = _('Constrained unwrap. For Karaage meshes: Similar to "Rebake textures" in world')
    bl_options = {'REGISTER', 'UNDO'}  

    @classmethod
    def poll(self, context):
        obj = context.object
        if obj and obj.type == 'MESH':
            me = obj.data
            if len(me.uv_textures) > 0:
                return True
        return False
        
    def execute(self, context):
        try:
            active_shape_key       = context.object.active_shape_key
            active_shape_key_index = context.object.active_shape_key_index
            mix_shape_key          = None
            obj = context.active_object
            original_mode = util.ensure_mode_is("OBJECT")
                        
            if active_shape_key:

                mix_shape_key = obj.shape_key_add(name="karaage_mix", from_mix=True)
                set_active_shape_key(obj,mix_shape_key.name)
                
            prepare_rebake_uv(context, obj)
            util.ensure_mode_is("EDIT")

            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.unwrap()
            
            if active_shape_key:
                util.ensure_mode_is("OBJECT")

                bpy.ops.object.shape_key_remove()
                context.object.active_shape_key_index = active_shape_key_index

            util.ensure_mode_is(original_mode, "OBJECT")
                        
            return{'FINISHED'}    
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}    

#

#

#

#

class ButtonFindDoubles(bpy.types.Operator):
    bl_idname = "karaage.find_doubles"
    bl_label = _("Doubles")
    bl_description = _("Find all double vertices in Mesh")
    bl_options = {'REGISTER', 'UNDO'}  
    
    distance = FloatProperty(  
       name="distance",  
       default=0.0001,  
       subtype='DISTANCE',  
       unit='LENGTH',
       soft_min=0.0000001,
       soft_max=0.01,
       precision=4,
       description="distance"  
       )

    @classmethod
    def poll(self, context):
        return context and context.object and context.object.type=='MESH'
        
    def execute(self, context):
        try:
            original_mode = util.ensure_mode_is("EDIT")
            count = util.select_all_doubles(context.object.data, dist=self.distance)
            util.ensure_mode_is(original_mode)
            if count > 0:
                self.report({'WARNING'},_("Object %s has %d duplicate Verts.") % (context.object.name,count))
            else:
                self.report({'INFO'},_("Object %s has no duplicate verts.") % context.object.name)
            return{'FINISHED'}    
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonFindUnweighted_old(bpy.types.Operator):
    bl_idname = "karaage.find_unweighted_old"
    bl_label = _("Find Unweighted")
    bl_description = _("Find any unweighted vertices in active mesh")

    def execute(self, context):
        try:
            obj = context.active_object
    
            unweighted, status = findUnweightedVertices(context, obj, use_sl_list=False)
            if status == NO_ARMATURE:
                raise util.Warning(_(msg_no_armature + 'find_unweighted')%obj.name)
            elif status == MISSING_WEIGHTS:
                self.report({'WARNING'},_("%d unweighted verts on %s")%(len(unweighted),obj.name))

                if len(unweighted)>0:

                    obj.data.use_paint_mask_vertex = True
                    bpy.ops.paint.vert_select_all(action='DESELECT')

                    for vidx in unweighted:
                        obj.data.vertices[vidx].select = True

            else:
                self.report({'INFO'},_("Object %s has all verts weighted.")%obj.name)

            return{'FINISHED'}    
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}    

class ButtonFindUnweighted(bpy.types.Operator):
    bl_idname = "karaage.find_unweighted"
    bl_label = _("Unweighted")
    bl_description = _("Find vertices not assigned to any deforming weightgroups")

    def execute(self, context):
        try:
            error_counter = 0
            weightpaint_candidate = None
            for obj in context.selected_objects:
                if obj.type != "MESH":
                    continue
          
                report = findWeightProblemVertices(context, obj, use_sl_list=False, find_selected_armature=True)
                
                if 'no_armature' in report['status']:
                    raise util.Warning(_(msg_no_armature + 'find_unweighted')%obj.name)
                
                elif 'unweighted' in report['status']:
                    error_counter += 1
                    weightpaint_candidate = obj
                    unweighted = report['unweighted']
                    self.report({'WARNING'},_("%d unweighted verts on %s")%(len(unweighted),obj.name))
                else:
                    self.report({'INFO'},_("Object %s has all verts weighted.")%obj.name)

            if error_counter == 1:

                context.scene.objects.active=weightpaint_candidate
                original_mode = util.ensure_mode_is('WEIGHT_PAINT')
                obj.data.use_paint_mask_vertex = True
                bpy.ops.paint.vert_select_all(action='DESELECT')
                
                for vidx in unweighted:
                    obj.data.vertices[vidx].select = True
                    
                util.ensure_mode_is(original_mode)
                    
            elif error_counter > 1:
                self.report({'WARNING'},_("%d of the selected Meshes have unweighted verts!")%(error_counter))

            return{'FINISHED'}    
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}    
        
class ButtonFindZeroWeights(bpy.types.Operator):
    bl_idname = "karaage.find_zeroweights"
    bl_label = _("Zero weights")
    bl_description = _("Find vertices with deforming weight_sum == 0")

    def execute(self, context):
        try:
            error_counter = 0
            weightpaint_candidate = None
            for obj in context.selected_objects:
            
                if obj.type != "MESH":
                    continue
       
                report = findWeightProblemVertices(context, obj, use_sl_list=False, find_selected_armature=True)
                
                if 'no_armature' in report['status']:
                    raise util.Warning(_(msg_no_armature + 'find_zeroweights')%obj.name)
                
                elif 'zero_weights' in report['status']:
                    error_counter += 1
                    weightpaint_candidate = obj
                    problems = report['zero_weights']
                    self.report({'WARNING'},_("%d zero-weight verts on %s")%(len(problems),obj.name))
                else:
                    self.report({'INFO'},_("Object %s has no deforming zero-weight vertex groups.")%obj.name)
              
            if error_counter == 1:
                context.scene.objects.active=weightpaint_candidate
                original_mode = context.object.mode
                bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
                obj.data.use_paint_mask_vertex = True
                bpy.ops.paint.vert_select_all(action='DESELECT')

                for vidx in problems:
                    obj.data.vertices[vidx].select = True
                    
                bpy.ops.object.mode_set(mode=original_mode)
                
            elif error_counter > 1:
                self.report({'WARNING'},_("%d of the selected Meshes have zero-weight verts!")%(error_counter))

            return{'FINISHED'}    
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}    
        
class ButtonFindTooManyWeights(bpy.types.Operator):
    bl_idname      = "karaage.find_toomanyweights"
    bl_label       = "> Weight limit"
    bl_description = _("Find verts with too many assigned weightgroups\n By default flag verts with > 4 weights assigned\nYou can change the parameters in the Redo Panel\nSee Bottom of the Tool Shelf after calling the Operator")
    bl_options     = {'REGISTER', 'UNDO'}

    max_weight  = IntProperty(default=4, min=0, name="Weight Limit", description="Report verts with more than this number of weights" )
    only_deform = BoolProperty(default=True, name="Deforming", description = "Take only deforming groups into account (mesh needs to be boiund to an armature)" )
    
    def execute(self, context):
        try:
            error_counter = 0
            wp_obj = None
            for obj in context.selected_objects:
            
                if obj.type != "MESH":
                    continue
   
                report = findWeightProblemVertices(context, obj, 
                         use_sl_list=False,
                         find_selected_armature=True,
                         max_weight=self.max_weight,
                         only_deform=self.only_deform )
                
                if 'too_many' in report['status']:
                    error_counter += 1
                    wp_obj = obj
                    problems = report['too_many']
                    self.report({'WARNING'},_("%d verts with more than %d%s weightgroups on %s")%(len(problems), self.max_weight, " deforming" if self.only_deform else " ", obj.name))

                else:
                    self.report({'INFO'},_("Object %s has no vertices with more than %d deforming weight groups.")% (obj.name, self.max_weight))

            if error_counter == 1:
                context.scene.objects.active=wp_obj
                original_mode = util.ensure_mode_is('WEIGHT_PAINT')
                wp_obj.data.use_paint_mask_vertex = True
                bpy.ops.paint.vert_select_all(action='DESELECT')

                for vidx in problems:
                    wp_obj.data.vertices[vidx].select = True

                context.scene.objects.active=wp_obj
                util.ensure_mode_is(original_mode)
            elif error_counter > 1:
                self.report({'WARNING'},_("%d of the selected Meshes have verts with too many deforming weight groups!")%(error_counter))

            return{'FINISHED'}    
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}    

def findWeightProblemVertices(context, obj, use_sl_list=True, armature=None, find_selected_armature=False, max_weight=4, only_deform=True):

    #

    #

    report = {'status':[], 'unweighted':[], 'zero_weights':[], 'too_many':[]}
    
    if only_deform and armature is None:
        armature = util.getArmature(obj)
        
        if armature is None and find_selected_armature:
            for tmp in context.selected_objects:
                if tmp.type == 'ARMATURE':
                    armature = tmp
                    break

        if armature is None:

            report['status'].extend(('no_armature','unweighted'))

    for v in obj.data.vertices:
        deforming = 0
        zero = 0  # :)
        if len(v.groups) == 0:
            report['unweighted'].append(v.index)
        else:
            for g in v.groups:
                try:
                    bonename = obj.vertex_groups[g.group].name
                    if armature == None or (bonename in armature.data.bones and armature.data.bones[bonename].use_deform):
                        deforming += 1 # count Number of deform bones for this vertex
                        if g.weight == 0:
                            zero += 1 # Count numberof zero weights for this vertex
                except:

                    pass
                    
            if deforming == 0:
                report['unweighted'].append(v.index)
            if deforming > max_weight:
                report['too_many'].append(v.index)
            if zero == deforming:

                report['zero_weights'].append(v.index)
        
    if len(report['unweighted']) > 0:
        report['status'].append('unweighted')
    if len(report['zero_weights']) > 0:
        report['status'].append('zero_weights')
    if len(report['too_many']) > 0:
        report['status'].append('too_many')
        
    return report

def findUnweightedVertices(context, obj, use_sl_list=True, arm=None):

    if arm is None:
        arm = util.getArmature(obj)

    if arm is None:
        return [v.index for v in obj.data.vertices], NO_ARMATURE 
    
    unweighted = []
    deform_bones = data.get_deform_bones(arm, exclude_volumes=False, exclude_eyes=False) if use_sl_list else []
    
    status = WEIGHTS_OK
    for v in obj.data.vertices:
        tot = 0.0
        for g in v.groups:
            bonename = obj.vertex_groups[g.group].name

            if bonename in arm.data.bones and arm.data.bones[bonename].use_deform:
                if use_sl_list:
                    if bonename in deform_bones:
                        tot += g.weight
                else:
                    tot += g.weight

        if tot==0:
            unweighted.append(v.index)
            status = MISSING_WEIGHTS

    return unweighted, status

class ButtonFreezeShape(bpy.types.Operator):
    bl_idname = "karaage.freeze_shape"
    bl_label = _("Freeze Selected")
    bl_description = _("Create a copy of selected mesh Objects with shapekeys and pose applied")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        with set_context(context, context.object, 'OBJECT'):
            freezeSelectedMeshes(context, self)
        return{'FINISHED'}

class ButtonConvertShapeToCustom(bpy.types.Operator):
    bl_idname = "karaage.convert_to_custom"
    bl_label = _("Convert to Custom")
    bl_description = _("Convert Selected Karaage Meshes to editable and fittable Custom Meshes (undo: CTRL-z)\n\nNotes:\nSelected Karaage Meshes are copied\nKaraage Originals are Deleted\nSliders are attached\nShape keys are removed")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            freezeSelectedMeshes(context, self, apply_pose=False, remove_weights=False, join_parts=False, attach_sliders=True, handle_source='HIDE')
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

def bake_t_pose(self, context):

    M = None
    bname = None
    M_pose = None
    M_data = None
    print("bake_t_pose: Start a t-pose bake")
    try:
        scn = context.scene
    
        currentSelection = util.getCurrentSelection(context)
        karaages         = currentSelection['karaages']
        targets          = currentSelection['targets']
        detached         = currentSelection['detached']
        others           = currentSelection['others']
        active           = currentSelection['active']

        if len(karaages)>1:
            raise util.Error(_("bake_t_pose: More than one armature selected.|Make sure you select a single armature.|bake_t_pose"))
        arm = karaages[0]
        
        print("bake_t_pose: Armature is in %s_Position" % arm.data.pose_position)

        AMW  = arm.matrix_world
        AMWI = AMW.inverted()

        for target in detached:

            report = findWeightProblemVertices(context, target, use_sl_list=False, find_selected_armature=True)                
            if 'unweighted' in report['status']:
                print("bake_t_pose: Found unweighted verts in %s" % target.name)
                unweighted = report['unweighted']
                raise util.MeshError(_(msg_unweighted_verts)%(len(unweighted), target.name))
            if 'zero_weights' in report['status']:
                print("bake_t_pose: Found zero weights in %s" % target.name)
                zero_weights = report['zero_weights']
                raise util.MeshError(_(msg_zero_verts)%(len(zero_weights), target.name))        
            
        deform_bones = data.get_deform_bones(arm, exclude_volumes=True, exclude_eyes=True)
        for target in detached:
            print("bake_t_pose: Alter [%s] to Rest Pose" % (target.name) )
            
            TMW  = target.matrix_world
            TMWI = TMW.inverted()

            failed_vert_transforms = 0
            for v in target.data.vertices:

                totw = 0
                for g in v.groups:
                    bname = target.vertex_groups[g.group].name
                    if bname in deform_bones:
                        totw+=g.weight

                M = Matrix(((0,0,0,0),(0,0,0,0),(0,0,0,0),(0,0,0,0)))
                matrix_populated = False
                if totw > 0:
                    for g in v.groups:
                        bname = target.vertex_groups[g.group].name
                        if bname in deform_bones:
                            w = g.weight

                            M_pose = arm.pose.bones[bname].matrix
                            M_data = arm.data.bones[bname].matrix_local

                            M = M + w/totw*TMWI*AMW*M_pose*M_data.inverted()*AMWI*TMW
                            matrix_populated = True
                if matrix_populated:
                    v.co = M.inverted()*v.co
                else:
                    failed_vert_transforms += 1                
            if failed_vert_transforms > 0:
                print("Failed to convert %d  of %d vertices in Object %s" % (failed_vert_transforms, len(target.data.vertices), target.name ))
            else:
                print("Converted all %d vertices in Object %s" % (len(target.data.vertices), target.name ))

        print("bake_t_pose: reparenting targets...")
        
        parent_armature(self, context, arm)    

        context.scene.objects.active=active
        print("bake_t_pose: Alter to restpose finished.")
        
    except Exception as e:
        print ("Exception in bake_t_pose")
        print ("bone was:", bname)
        print ("M:", M)
        print ("M_pose:", M_pose)
        print ("M_data:", M_data)
        util.ErrorDialog.exception(e)

def get_keyblock_values(ob):
    print("Get keyblock values for [",ob,"]")
    if ob.data.shape_keys and ob.data.shape_keys.key_blocks:
        key_values = [b.value for b in ob.data.shape_keys.key_blocks]
    else:
        key_values = []
    return key_values
    
def revertShapeSlider(obj):
    success_armature_name = None

    if obj.ObjectProp.slider_selector!='NONE':
        arm=obj.find_armature()
        if arm and "karaage" in arm:

            shape_filename = arm.name #util.get_shape_filename(name)
            if shape_filename in bpy.data.texts:
                shape.ensure_drivers_initialized(arm)
                shape.loadProps(arm, shape_filename, pack=True)
                success_armature_name = arm.name
            shape.detachShapeSlider(obj)
        if arm and "avastar" in arm:

            shape_filename = arm.name #util.get_shape_filename(name)
            if shape_filename in bpy.data.texts:
                shape.ensure_drivers_initialized(arm)
                shape.loadProps(arm, shape_filename, pack=True)
                success_armature_name = arm.name
            shape.detachShapeSlider(obj)
    return success_armature_name

class ButtonApplyShapeSliders(bpy.types.Operator):
    bl_idname = "karaage.apply_shape_sliders"
    bl_label = _("Detach")
    bl_description = _("Apply Slider settings and Detach Meshes from Sliders. Caution! This operation will apply and remove all shape keys from your attached Custom Objects")
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def exec_imp(context, arms, objs):
        util.set_disable_update_slider_selector(True)
        for ob in objs:
            if ob.ObjectProp.slider_selector != 'NONE':
                omode = ob.mode
                dupobj = freezeMeshObject(context, ob)
                dupobj.ObjectProp.slider_selector = 'NONE'
                util.ensure_mode_is(omode, object=dupobj)
        for arm in arms:
            if arm.name in bpy.data.texts:
                objs = [child for child in util.getCustomChildren(arm, type='MESH') if child.ObjectProp.slider_selector != 'NONE']
                if len(objs) == 0:
                    text = bpy.data.texts[arm.name]
                    util.remove_text(text, do_unlink=True)
                    arm.ObjectProp.slider_selector = 'NONE'
        util.set_disable_update_slider_selector(False)

    def execute(self, context):
        arms, objs = util.getSelectedArmsAndObjs(context)
        ButtonApplyShapeSliders.exec_imp(context, arms, objs)
        return{'FINISHED'}

class ButtonUnParentArmature(bpy.types.Operator):
    bl_idname = "karaage.unparent_armature"
    bl_label = _("Unbind from Armature")
    bl_description = _("Convenience method to remove armature modifier (and parenting) from selected")
    bl_options = {'REGISTER', 'UNDO'}

    freeze = BoolProperty(
             default     = False,
             name        = "With Apply Pose",
             description = "Apply the current Pose to the Mesh (Apply Armature Modifier)")
    #
    def execute(self, context):
        try:
            currentSelection = util.getCurrentSelection(context)
            attached         = currentSelection['attached']
            unparent_armature(context, self, attached, self.freeze)
            return {'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

def unparent_armature(context, operator, attached, freeze=False):
    if len(attached) == 0:
        return None 

    active = context.scene.objects.active
    amode = util.ensure_mode_is("OBJECT")

    bpy.ops.object.select_all(action='DESELECT')
    if freeze:
        for target in attached:
            target.select=True
        result = freezeSelectedMeshes(context, operator, apply_pose=True, remove_weights=False, join_parts=False, handle_source='DELETE')
    else:    

        for target in attached:
            target.select=False

        for target in attached:
            context.scene.objects.active=target
            target.select=True
            omode = util.ensure_mode_is("OBJECT")
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            for mod in [ mod for mod in target.modifiers if mod.type=='ARMATURE']:
                bpy.ops.object.modifier_remove(modifier=mod.name)
            target.select=False
            util.ensure_mode_is(omode)

        result = attached

    for target in attached:
        target.select=True
    context.scene.objects.active=active
    util.ensure_mode_is(amode)

    return result

def create_weight_groups(
        operator,
        context, 
        target, 
        bone_names, 
        clearTargetWeights,
        submeshInterpolation,
        type=None, 
        keep_empty_groups=False, 
        selected=False, 
        enforce_meshes=None,
        weight_eye_bones=False
    ):

    active = context.scene.objects.active
    context.scene.objects.active = target
    original_mode = util.ensure_mode_is("OBJECT")
    
    if type == 'EMPTY':
        util.createEmptyGroups(target)
        
    elif type in ['AUTOMATIC','ENVELOPES']:

        generateWeightsFromBoneSet(target, bone_names, type=type, clear=clearTargetWeights, selected=selected)

        if not keep_empty_groups:

            c = util.removeEmptyWeightGroups(target)

    elif type in ['KARAAGE', 'COPY']:

        armobj = util.get_armature(target)
        weight_sources = util.getChildren(armobj, type="MESH")
        copy_type = None if type == 'COPY' else type
        copyBoneWeights(operator, context, target, weight_sources, clearTargetWeights, submeshInterpolation, enforce_meshes=enforce_meshes, copy_type = copy_type)
    
    elif type == 'EXTENDED':

        util.ensure_karaage_repository_is_loaded()
        armobj = util.get_armature(target)
        for part in enforce_meshes:
            get_extended_weights(context, armobj, target, part, vert_mapping='POLYINTERP_VNORPROJ')
    
    elif type == 'SWAP':
        weights.swapCollision2Deform(target, keep_groups=keep_empty_groups)

    util.ensure_mode_is(original_mode)
    context.scene.objects.active = active

def parent_armature(self, context, armature, type=None, clear=False, keep_empty_groups=False, selected=False, weight_eye_bones=False, enforce_meshes=None):
    print("Parent to Armature %s using %s" % (armature.name, type) )

    currentSelection = util.getCurrentSelection(context)
    karaages         = currentSelection['karaages']
    targets          = currentSelection['targets']
    detached         = currentSelection['detached']
    others           = currentSelection['others']
    active           = currentSelection['active']

    context.scene.objects.active=armature
    bpy.ops.object.select_all(action='DESELECT')
    armature.select=True

    meshProps = context.scene.MeshProp

    parented_count = 0

    exclude_volumes = True
    if type == None or type == 'NONE':
        for target in detached:
            print("Checking fitted mesh for %s to %s" % (target.name, armature.name) )
            if target.vertex_groups:
                vnames = [g.name for g in target.vertex_groups if g.name in SLVOLBONES]
                if len(vnames) > 0:
                    print("Target %s uses fitted mesh maps" % (target.name) )
                    weights.setDeformingBones(armature, data.get_volume_bones(only_deforming=False), replace=False)
                    exclude_volumes = False
                    break

    for target in detached:
        parented_count += 1
        target.select=True
        util.transform_origins_to_target(context, armature, [target])
        bpy.ops.object.parent_set(type='OBJECT', keep_transform=False)

        preserve_volume = target.get('use_deform_preserve_volume', False)
        if preserve_volume:
            mods = [mod for mod in target.modifiers if mod.type=='ARMATURE']
            for mod in mods:
                mod.use_deform_preserve_volume = preserve_volume
                print("restored %s.mod.use_deform_preserve_volume = %s" % ( target.name, target['use_deform_preserve_volume']))

        amc = 0
        for mod in [ mod for mod in target.modifiers if mod.type=='ARMATURE' and mod.object==armature]:
            mod.use_vertex_groups  = True
            mod.use_bone_envelopes = False
            amc += 1

        if amc == 0:

            mod = target.modifiers.new(armature.name, 'ARMATURE')
            mod.use_vertex_groups  = True
            mod.use_bone_envelopes = False
            mod.object             = armature
            mod.use_deform_preserve_volume = preserve_volume

        weighted_bones = data.get_deform_bones(target, exclude_volumes=exclude_volumes, exclude_eyes=(not weight_eye_bones))
        deform_state={}
        for bone_name in SL_ALL_EYE_BONES:
            if bone_name in armature.data.bones:
                deform_state[bone_name] = armature.data.bones[bone_name].use_deform
                armature.data.bones[bone_name].use_deform = weight_eye_bones

        if weight_eye_bones:
            weighted_bones.extend(SL_ALL_EYE_BONES)

        create_weight_groups(
            self,
            context, 
            target, 
            weighted_bones, 
            meshProps.clearTargetWeights,
            meshProps.submeshInterpolation,
            type=type, 
            keep_empty_groups=keep_empty_groups, 
            selected=selected, 
            enforce_meshes=enforce_meshes
        )                             

        for bone_name in deform_state:
            armature.data.bones[bone_name].use_deform = deform_state[bone_name]
        weights.classic_fitting_preset(target)
        target.select=False

    print("Cleaning up %s" % armature.name)
    for o in targets + others:
        o.select=True

    context.scene.objects.active=active

    if parented_count == 0:
        raise util.Warning("All Meshes already parented.|ACTION: If you want to reparent a Mesh, then do:\n  1.) Remove the armature modifer (from the modifier stack)\n  2.) Unparent the armature: Object -> Parent -> Clear.\nThen try again.|parent_armature")
    else:
        print("Parented %d Objects to Armature %s" % (parented_count, armature.name))

class ButtonParentArmature(bpy.types.Operator):
    bl_idname = "karaage.parent_armature"
    bl_label = _("Bind to Armature")
    bl_description = _("Convenience method to add armature modifier")
    bl_options = {'REGISTER', 'UNDO'}

    type          = StringProperty(name="Parent Type", default='KEEP')
    clear         = BoolProperty(name="Clear", default=True)
    selected      = BoolProperty(name="Only Selection", default=True)
    with_eyebones = BoolProperty(name="With Eyes", default=False)
    to_tpose      = BoolProperty(name="Alter To Restpose", default=False)
    with_sliders  = BoolProperty(name="Attach Sliders", default=False)

    def invoke(self, context, event):
        print("Invoked parent_armature")
        ui_level = util.get_ui_level()
        meshProps          = context.scene.MeshProp

        self.type          = meshProps.skinSourceSelection
        self.clear         = meshProps.clearTargetWeights
        self.selected      = meshProps.copyWeightsSelected
        self.with_eyebones = meshProps.weight_eye_bones
        self.to_tpose      = ui_level > UI_ADVANCED and (util.always_alter_to_restpose() or meshProps.toTPose)
        self.with_sliders  = meshProps.attachSliders
        return self.execute(context)

    def execute(self, context):
        with set_context(context, context.object, 'OBJECT'):
            currentSelection = util.getCurrentSelection(context)
            karaages         = currentSelection['karaages']
            targets          = currentSelection['targets']
            detached         = currentSelection['detached']
            others           = currentSelection['others']
            active           = currentSelection['active']

            if len(karaages)>1:
                raise util.Error("More than one armature selected.|Make sure you select a single armature.|parent_armature")

            if len(targets) == 0:
                msg = "No Meshes selected to bind to"
                log.warning(msg)
                self.report({'INFO'},(msg))
                return {'FINISHED'}

            meshProps = context.scene.MeshProp

            if self.type == 'KARAAGE':
                enforce_meshes = ["headMesh", "lowerBodyMesh", "upperBodyMesh"]
            else:
                enforce_meshes = None

            arm = karaages[0]

            parent_armature(self, context, arm, type=self.type,
                clear    = self.clear,
                selected = self.selected,
                weight_eye_bones= self.with_eyebones,
                enforce_meshes = enforce_meshes )

            if not 'bindpose' in arm:
                if self.to_tpose:

                    unparent_armature(context, self, targets)
                    bake_t_pose(self, context)

                if self.with_sliders:

                    arm.ObjectProp.slider_selector = 'SL'
                else:

                    arm.ObjectProp.slider_selector = 'NONE'
                context.scene.objects.active=active
                bpy.types.karaage_fitting_presets_menu.bl_label='Fitting Presets'

        return {'FINISHED'}

#

#
#

#

#

#

#

#

def SLBoneDeformStates(armobj):
    try:
        selected_bones = util.getVisibleSelectedBones(armobj)
        if len(selected_bones) == 0:
            return '', ''
        deform_count = len([b for b in selected_bones if b.use_deform == True])
        all_count  = len(selected_bones)
        if deform_count==0:
            return 'Disabled', 'Enable'
        if deform_count == all_count:
            return 'Enabled', 'Disable'
        return 'Partial', ''
    except:
        pass
    return "", ""

class ButtonArmatureAllowStructureSelect(bpy.types.Operator):
    bl_idname = "karaage.armature_allow_structure_select"
    bl_label = _("Allow Structure Bone Select")
    bl_description = _("Allow Selecting Structure bones")

    def execute(self, context):
    
        active, armobj = rig.getActiveArmature(context)
        if armobj is None:
            self.report({'WARNING'},_("Active Object %s is not attached to an Armature")%active.name)
        else:
            mode = active.mode
            bpy.ops.object.mode_set(mode='POSE', toggle=True)
        
            try:
                rig.setSLBoneStructureRestrictSelect(armobj, False)
            except Exception as e:
                util.ErrorDialog.exception(e)
                
            bpy.ops.object.mode_set(mode=mode, toggle=True)  
                
        return{'FINISHED'}    
        
class ButtonArmatureRestrictStructureSelect(bpy.types.Operator):
    bl_idname = "karaage.armature_restrict_structure_select"
    bl_label = _("Restrict Structure Bone Select")
    bl_description = _("Restrict Selecting Structure bones")

    def execute(self, context):

        active, armobj = rig.getActiveArmature(context)
        if armobj is None:
            self.report({'WARNING'},_("Active Object %s is not attached to an Armature")%active.name)
        else:
            mode = active.mode
            bpy.ops.object.mode_set(mode='POSE', toggle=True)

            try:
                rig.setSLBoneStructureRestrictSelect(armobj, True)
            except Exception as e:
                util.ErrorDialog.exception(e)
                
            bpy.ops.object.mode_set(mode=mode, toggle=True)  
                
        return{'FINISHED'}

def draw_constraint_set(op, context):
        col = op.layout.column()
        col.prop(op,"ConstraintSet")

class ButtonArmatureUnlockLocation(bpy.types.Operator):
    bl_idname      = "karaage.armature_unlock_loc"
    bl_label       = "Unlock Locations"
    bl_description = '''Unlock Control Bones for unconstrained animation.
    Can be helpful for face animations.
    
    Warning: This mode overrides the Appearance sliders for custom meshes!
    You might see shape changes on the Face and hands!
    '''
    bl_options = {'REGISTER', 'UNDO'}

    reset_pose = BoolProperty(
            name        = "Reset to Restpose",
            description = "Reset the pose to Restpose before locking",
            default     = True)    

    def execute(self, context):
        armobj = util.get_armature(context.object)
        try:
            omode = util.ensure_mode_is('POSE')
            rig.setSLBoneLocationMute(self, context, True, armobj.RigProps.ConstraintSet)
            if self.reset_pose:
                bpy.ops.pose.transforms_clear()
            util.ensure_mode_is(omode)
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}    
        
class ButtonArmatureUnlockVolume(bpy.types.Operator):
    bl_idname = "karaage.armature_unlock_vol"
    bl_label = "Lock Volumes"
    bl_description = "Unlock Volume Bone locations for unconstrained animation."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armobj = util.get_armature(context.object)
        try:
            rig.setSLBoneVolumeMute(self, context, False, armobj.RigProps.ConstraintSet)
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}    
        
class ButtonArmatureUnlockRotation(bpy.types.Operator):
    bl_idname = "karaage.armature_unlock_rot"
    bl_label = _("Unlock Rotations")
    bl_description = '''Unlock SL Base bone rotations from Control Bone rotations
    Helpful only for Weighting tasks.
    
    Warning: NEVER(!) use this for animating the base bones!
    Use the Pose preset (in the rigging display panel) for animating your Rig'''
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armobj = util.get_armature(context.object)
        try:
            rig.setSLBoneRotationMute(self, context, True, armobj.RigProps.ConstraintSet)
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}    
        
class ButtonArmatureLockRotation(bpy.types.Operator):
    bl_idname = "karaage.armature_lock_rot"
    bl_label = _("Lock Rotations")
    bl_description = _("Synchronize Deform bone rotations to Control Bone rotations\nPlease use this setup for posing and animating.")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armobj = util.get_armature(context.object)
        try:
            rig.setSLBoneRotationMute(self, context, False, armobj.RigProps.ConstraintSet)
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}    
        
class ButtonArmatureLockLocation(bpy.types.Operator):
    bl_idname = "karaage.armature_lock_loc"
    bl_label = _("Lock Locations")
    bl_description = _("Lock Control Bone locations (to allow only the animation of bone rotations)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armobj = util.get_armature(context.object)
        try:
            omode = util.ensure_mode_is('POSE')
            rig.setSLBoneLocationMute(self, context, False, armobj.RigProps.ConstraintSet)
            util.ensure_mode_is(omode)            
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}    
        
class ButtonArmatureLockVolume(bpy.types.Operator):
    bl_idname = "karaage.armature_lock_vol"
    bl_label = "Lock Volumes"
    bl_description = "Lock Volume Bone locations (to allow only the animation of bone rotations)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armobj = util.get_armature(context.object)
        try:
            rig.setSLBoneVolumeMute(self, context, True, armobj.RigProps.ConstraintSet)
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}    
        
class ButtonArmatureBake(bpy.types.Operator):
    bl_idname = "karaage.armature_bake"
    bl_label = _("Convert to Bind Pose")
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = \
'''Permanently apply current pose as new Rest pose.

Caution: Take care to choose between the following Options:
- Enable 'Use Bind Pose' in this panel(see above), or
- Enable 'With Joint Positions' when you import your meshes to SL.'''

    handleBakeRestPoseSelection = EnumProperty(
        items=(
            ('SELECTED',_('Selected'), _('Bake selected Bones')),
            ('VISIBLE', _('Visible'),  _('Bake visible Bones')),
            ('ALL',     _('All'),      _('Bake all Bones'))),
        name=_("Scope"),
        description=_("Which bones are affected by the Bake"),
        default='VISIBLE')
        
    apply_armature_on_snap_rig = BoolProperty(
       default     = True,
       name        = "Snap Mesh",
       description = \
'''Apply the current Pose to all bound meshes before snapping the rig to pose

The snap Rig to Pose operator modifies the Restpose of the Armature.
When this flag is enabled, the bound objects will be frozen and reparented to the new restpose

Note: When this option is enabled, the operator deletes all Shape keys on the bound objects!
Handle with Care!'''
    )

    adjust_stretch_to  = BoolProperty(name=_("Adjust IK Line Bones"),  description=_("Adjust IK Line Bones to the Pole Target and the coresponding Bones"), default=True)
    adjust_pole_angles = BoolProperty(name=_("Adjust IK Pole Angles"), description=_("Recalculate IK Pole Angle for minimal distortion"), default=True)
    
    PV = {'USE_MODIFIER':None, 'TRUE':True, 'FALSE':False}
    preserve_volume = EnumProperty(
    items=(
        ('USE_MODIFIER', _('As is'), _('Keep preserve volume as defined in the Armature modifier(s) of the selected meshes')),
        ('TRUE',         _('Yes'),   _('Enable  Preserve Volume for all selected Meshes')),
        ('FALSE',        _('No'),    _('Disable Preserve Volume for all selected Meshes'))),
    name=_("Preserve Volume"),
    description=_("Preserve the Mesh Volume while Baking meshes"),
    default='USE_MODIFIER'
    )

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        box = layout.box()
        box.label("Pose Bake Options:", icon="BONE_DATA")
        col = box.column()

        col.prop(self,'apply_armature_on_snap_rig')
        col.prop(self,'preserve_volume')
        col.prop(self,'handleBakeRestPoseSelection')
        col = box.column()        
        col.prop(self,"adjust_stretch_to")
        col.prop(self,"adjust_pole_angles")

    def execute(self, context):
        oactive = context.object
        active = util.get_armature(oactive)
        if not active:
            msg = "armature_bake: Object [%s] has no armature to bake to(Cancel)." % (context.object.name)
            print(msg)
            self.report({'ERROR'},(msg))
            return {'CANCEL'}

        context.scene.objects.active = active
        omode  = util.ensure_mode_is('OBJECT')
        meshProps = context.scene.MeshProp

        frozen = []
        selected = util.remember_selected_objects(context)
        if self.apply_armature_on_snap_rig:
            selection = util.get_animated_meshes(context, active, with_karaage=True, only_selected=False)
            for ob in context.scene.objects:
                ob.select = ob in selection
            print("armature_bake: Freezing %d Meshes" % (len(selection)) )
            preserve_volume = self.PV[self.preserve_volume]
            frozen = freezeSelectedMeshes(context, 
                             self, 
                             apply_pose=True, 
                             remove_weights=False, 
                             join_parts=False, 
                             attach_sliders=False, 
                             handle_source='DELETE', 
                             preserve_volume=preserve_volume)

        util.ensure_mode_is('POSE')
        print("armature_bake: Apply new Restpose to Skeleton...")
        selection = []
        ebones = util.get_modify_bones(active)
        pbones = active.pose.bones
        if self.handleBakeRestPoseSelection=="ALL":
            selection = util.Skeleton.bones_in_hierarchical_order(active, order='BOTTOMUP')
        else:
            for name in util.Skeleton.bones_in_hierarchical_order(active, order='BOTTOMUP'):
                bone = ebones[name]
                if not bone.hide and len([id for id,layer in enumerate(bone.layers) if bone.layers[id] and active.data.layers[id]]):
                    selection.append(name)
            if self.handleBakeRestPoseSelection=="SELECTED":
                selection = [name for name in selection if ebones[name].select]

        print("armature_bake: Bake Rest Pose for %s bones(%d):" % (self.handleBakeRestPoseSelection, len(selection)))

        linebones = rig.get_line_bone_names(pbones, selection)
        polebones = rig.get_pole_bone_names(pbones, selection)

        posed_bones = rig.get_posed_bones(active)
        rig.set_rotation_limit(posed_bones, False)
        
        bpy.ops.pose.armature_apply()
        util.ensure_mode_is('OBJECT')
        util.Skeleton.get_toe_hover_z(active, reset=True)

        if self.adjust_stretch_to:

            util.ensure_mode_is('POSE')
            rig.fix_stretch_to(active, linebones)
            util.ensure_mode_is('EDIT')
        if self.adjust_pole_angles:

            rig.fix_pole_angles(active, polebones)

        util.ensure_mode_is('POSE')

        print("armature_bake: Calculate joint offsets...")
        bpy.ops.karaage.armature_jointpos_store()

        util.set_disable_update_slider_selector(True)
        for ob in frozen:
            ob.ObjectProp.slider_selector='SL'
            util.fix_modifier_order(context, ob)
        util.set_disable_update_slider_selector(False)
        active.ObjectProp.slider_selector='SL'

        if self.apply_armature_on_snap_rig:
            print("armature_bake: Parent frozen objects to armature...")
            util.ensure_mode_is('OBJECT')
            active.select=True
            bpy.ops.karaage.parent_armature()
            print("armature_bake: Parent armature done...")
            util.restore_selected_objects(context, selected)

        context.scene.objects.active = oactive
        util.ensure_mode_is(omode)
        return{'FINISHED'}    

def set_spine_controlls(armobj, val):
    old = armobj.get('spine_unfold', val)
    if val == 'upper' and old in ['lower', 'all']:
        val = 'all'
    if val == 'lower' and old in ['upper', 'all']:
        val = 'all'
    armobj['spine_unfold'] = val

class ArmatureSpineUnfoldUpper(bpy.types.Operator):
    bl_idname = "karaage.armature_spine_unfold_upper"
    bl_label = _("Unfold Upper")
    bl_description = _("Unfold the upper Spine Bones into a linear sequence of bones")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj    = context.object
            arm    = util.get_armature(obj)
            set_spine_controlls(arm, 'upper')
            active = obj

            context.scene.objects.active = arm
            omode = util.ensure_mode_is('EDIT')

            rig.armatureSpineUnfoldUpper(arm)

            util.ensure_mode_is(omode)
            context.scene.objects.active = active
        except:
            print("Could not linearise Avatar spine")
            raise
        return{'FINISHED'}
        
class ArmatureSpineUnfoldLower(bpy.types.Operator):
    bl_idname = "karaage.armature_spine_unfold_lower"
    bl_label = _("Unfold Lower")
    bl_description = _("Unfold the lower Spine Bones into a linear sequence of bones")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj    = context.object
            arm    = util.get_armature(obj)
            set_spine_controlls(arm, 'lower')
            active = obj

            context.scene.objects.active = arm
            omode  = util.ensure_mode_is('EDIT')

            rig.armatureSpineUnfoldLower(arm)

            util.ensure_mode_is(omode)
            context.scene.objects.active = active
        except:
            print("Could not linearise Avatar spine")
            raise
        return{'FINISHED'}

class ArmatureSpineUnfold(bpy.types.Operator):
    bl_idname = "karaage.armature_spine_unfold"
    bl_label = _("Unfold")
    bl_description = _("Unfold all Spine Bones into a linear sequence of bones")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj    = context.object
            arm    = util.get_armature(obj)
            set_spine_controlls(arm, 'all')
            active = obj

            context.scene.objects.active = arm
            omode  = util.ensure_mode_is('EDIT')

            rig.armatureSpineFold(arm)
            rig.armatureSpineUnfoldLower(arm)
            rig.armatureSpineUnfoldUpper(arm)

            util.ensure_mode_is(omode)
            context.scene.objects.active = active
        except:
            print("Could not linearise Avatar spine")
            raise
        return{'FINISHED'}
        
class ArmatureSpinefold(bpy.types.Operator):
    bl_idname = "karaage.armature_spine_fold"
    bl_label = _("Fold")
    bl_description = _("Fold the Spine Bones into their default position\nThis is compatible to the SL legacy Skeleton.")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj    = context.object
            arm    = util.get_armature(obj)
            set_spine_controlls(arm, 'none')
            active = obj

            context.scene.objects.active = arm
            omode  = util.ensure_mode_is('EDIT')

            rig.armatureSpineFold(arm)

            util.ensure_mode_is(omode)
            context.scene.objects.active = active
        except:
            print("Could not linearise Avatar spine")
            raise
        return{'FINISHED'}
        
class ButtonArmatureBoneSnapper(bpy.types.Operator):
    bl_idname = "karaage.armature_adjust_base2rig"
    bl_label = _("Snap Base to Rig")
    bl_description =\
'''Propagate Control Bone edits to corresponding SL-Base-bones.

You use this function after you have edited the Control rig.
Then this function synchronizes your deform bones (SL Base Bones)
to the edited Control Rig.'''

    bl_options = {'REGISTER', 'UNDO'}
    
    fix_base_bones       = BoolProperty(name=_("Snap SL Base"),           description=_("Propagate changes to the SL Base Bones"),      default=True)
    fix_ik_bones         = BoolProperty(name=_("Snap IK Bones"),          description=_("Propagate changes to the IK Bones"),           default=True)
    fix_volume_bones     = BoolProperty(name=_("Snap Volume Bones"),      description=_("Propagate changes to the Volume Bones"),       default=False)
    fix_attachment_bones = BoolProperty(name=_("Snap Attachment Points"), description=_("Propagate changes to the Attachment Points"),  default=False)
    base_to_rig          = BoolProperty(name=_("Reverse Snap"),           description=_("Reverse the snapping direction: Adjust the Rig bones to the Base bones. "),  default=False)
    adjust_pelvis        = BoolProperty(name="Adjust Pelvis",             description = UpdateRigProp_adjust_pelvis_description,        default = False)
    sync                 = BoolProperty(name="Sync",                      description = "Synchronized joint store (debug)", default     = False)    

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        box = layout.box()
        box.label("Snap Options", icon="BONE_DATA")
        col = box.column(align=True)    
        col.prop(self,"adjust_pelvis")
        col.prop(self,"sync")
        col.prop(self,"fix_base_bones")
        col.prop(self,"fix_ik_bones")
        col.prop(self,"fix_volume_bones")
        col.prop(self,"fix_attachment_bones")
        col.prop(self,"base_to_rig")

    def execute(self, context):
        oumode = util.set_operate_in_user_mode(False)
        try:    
            active = context.active_object 
            rig.reset_cache(active, full=True)
            if "karaage" in active or "avastar" in active:
                if self.adjust_pelvis and rig.needPelvisInvFix(active):
                    rig.matchPelvisInvToPelvis(context, active, alignToDeform=False)
            
            if self.fix_base_bones:
                rig.adjustRigToSL(active) if self.base_to_rig else rig.adjustSLToRig(active)
            if self.fix_ik_bones:
                rig.adjustIKToRig(active)
            if self.fix_volume_bones:
                log.info("fix_volume_bones ...")
                rig.adjustVolumeBonesToRig(active)
            if self.fix_attachment_bones:
                log.info("adjustAttachmentBonesToRig ...")
                rig.adjustAttachmentBonesToRig(active)
                
            log.warning("Snap Base to Rig: Calculate joint offsets...")
            bpy.ops.karaage.armature_jointpos_store()
        except Exception as e:
            util.ErrorDialog.exception(e)
        finally:
            util.set_operate_in_user_mode(oumode)
        return{'FINISHED'}    

#

#

#

#

#

#

#

#

#

#

#

#

class ButtonAlphaMaskBake(bpy.types.Operator):
    bl_idname = "karaage.alphamask_bake"
    bl_label = _("Bake Mask")
    bl_description = _("Create an Alpha_Mask from the given weight group")

    def execute(self, context):

        try:
            active = context.active_object 
            create_bw_mask(active, active.karaageAlphaMask, "karaage_alpha_mask")
        except Exception as e:
            util.ErrorDialog.exception(e)
        return {'FINISHED'}    

def get_deform_subset(armobj, subtype, only_deforming=None):
    if subtype == 'BASIC':
        bones = data.get_base_bones(armobj, only_deforming=only_deforming)
    elif subtype == 'VOL':
        bones = data.get_volume_bones(armobj, only_deforming=only_deforming)
    elif subtype == 'EXTENDED':
        bones = data.get_extended_bones(armobj, only_deforming=only_deforming)
    else:
        bones = util.getVisibleSelectedBoneNames(armobj)
    return bones

class ButtonDeformUpdate(bpy.types.Operator):
    bl_idname = "karaage.armature_deform_update"
    bl_label = "Update deform"
    bl_description = "Update Deform layer for display purposes"

    @classmethod
    def poll(self, context):
        arm = util.get_armature(context.object)
        return arm is not None

    def execute(self, context):
        armobj = util.get_armature(context.object)
        bones = util.get_modify_bones(armobj)
        dbones = [b for b in bones if b.use_deform]
        log.warning("Found %d deform bones" % (len(dbones)) )
        bind.fix_bone_layers(lazy=False, force=True)
        return {'FINISHED'}    

class ButtonDeformEnable(bpy.types.Operator):
    bl_idname = "karaage.armature_deform_enable"
    bl_label = _("Enable deform")
    #
    bl_description = _("Enable Deform option for bones (Either Selected bones, SL Base Bones, Volume Bones, or Extended Bones)")

    set = StringProperty()
    
    def execute(self, context):

        try:
            armobj = util.get_armature(context.object)
            bones = get_deform_subset(armobj, self.set, only_deforming=False)
            weights.setDeformingBones(armobj, bones, replace=False)
            bind.fix_bone_layers(lazy=False, force=True)
            log.warning("Enabled %d %s Deform Bones" % (len(bones), self.set) )

        except:
            self.report({'WARNING'},_("Could not enable deform for bones in %s")%context.object.name)
            raise
        return {'FINISHED'}    

class ButtonDeformDisable(bpy.types.Operator):
    bl_idname = "karaage.armature_deform_disable"
    bl_label = _("Disable deform")
    bl_description = _("Disable Deform option for bones (Either Selected bones, SL Base Bones, Volume Bones, or Extended Bones)")
    bl_options = {'REGISTER', 'UNDO'}
    set = StringProperty()
    
    def execute(self, context):

        try:
            armobj = util.get_armature(context.object)
            bones = get_deform_subset(armobj, self.set, only_deforming=False)
            weights.disableDeformingBones(armobj, bones , replace=False)
            bind.fix_bone_layers(lazy=False, force=True)
            log.warning("Disabled %d %s Deform Bones" % (len(bones), self.set))
            
        except:
            self.report({'WARNING'},_("Could not disable deform for bones in %s")%context.object.name)
            raise
        return {'FINISHED'}    

class ButtonImportKaraageShape(bpy.types.Operator):
    bl_idname = "karaage.import_shape"  
    bl_label =  _("Shape as Karaage(.xml)")
    bl_description = _('Create anKaraage character and apply the imported inworld Shape (.xml)')
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".xml"
    filepath = StringProperty(name=_('Shape filepath'),
        subtype='FILE_PATH')

    filter_glob = StringProperty(
        default="*.xml",
        options={'HIDDEN'},
    )

    with_quads = BoolProperty(name=_('Use Quads'),
        default = False,
        description = "If enabled: Create an Karaage with Quads, If disabled:Create a triangulated Karaage" )

    def draw(self, context):
        layout = self.layout
        obj = context.object
        if obj and obj.select and obj.type == 'ARMATURE' and 'karaage' in obj:
            box = layout.box()
            col=box.column(align=True)
            col.label("Apply Shape to")
            col.label("Armature: [%s]" % obj.name)
        else:
            col = layout.column()
            col.prop(context.scene.UpdateRigProp,'tgtRigType')
            if 'quadify_avatar_mesh' in dir(bpy.ops.sparkles):
                col.prop(self,'with_quads')

    def execute(self, context):
        obj = context.object

        if obj and obj.select and obj.type == 'ARMATURE' and 'karaage' in obj:
            armobj = obj
        else:
            armobj = create.createAvatar(context, quads = self.with_quads, rigType=context.scene.UpdateRigProp.tgtRigType)
            context.scene.objects.active = armobj
            util.ensure_mode_is("OBJECT")

        print("import from [%s]"%(self.filepath))
        shape.loadProps(armobj, self.filepath)
        return{'FINISHED'}    
    
    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)

        return {'RUNNING_MODAL'}

class ButtonExportSLCollada(bpy.types.Operator):
    bl_idname = "karaage.export_sl_collada"  
    bl_label =  _("Collada (Karaage) (.dae)")
    bl_description = _('Export the selection as Collada-1.4.1 (.dae) with compatibility with SL, OpenSim and similar worlds')

    filename_ext = ".dae"

    filter_glob = StringProperty(
        default="*.dae",
        options={'HIDDEN'},
    )
    
    check_existing = BoolProperty(
                name="Check Existing",
                description="Check and warn on overwriting existing files",
                default=True,
                options={'HIDDEN'},
                )
    
    filepath = StringProperty(

                default="//",
                subtype='FILE_PATH',
                )    

    def draw(self, context):
        meshProps = context.scene.MeshProp
        layout = self.layout  
        currentSelection = util.getCurrentSelection(context)
        attached         = currentSelection['attached']
        targets          = currentSelection['targets']
        create_collada_layout(meshProps, context, layout, attached, targets)

    @classmethod
    def poll(cls, context):
        if not context:
            return False
        if context.mode != 'OBJECT':
            return False

        ob = context.object
        if not ob:
            return False
        return True
        arm = util.get_armature(ob)
        if arm:
            visible = util.object_is_visible(context, arm)
            log.debug("Armature %s is visible? %s" % (arm.name, visible))
            return visible

        return True

    def invoke(self, context, event):
        selected_objects = util.get_selected_objects(context)
        matcount, material_warnings = util.get_highest_materialcount(selected_objects)
        try:

            for obj in [ob for ob in selected_objects if ob.type == 'MESH']:
                arm = util.getArmature(obj)
                if arm is not None:
                    report = findWeightProblemVertices(context, obj, use_sl_list=False, find_selected_armature=True)
                    if 'unweighted' in report['status']:
                        unweighted = report['unweighted']
                        msg = _(msg_unweighted_verts)%(len(unweighted), obj.name)
                        self.report({'WARNING'},msg)
                        raise util.Error(msg)

                    if 'zero_weights' in report['status']:
                        zero_weights = report['zero_weights']
                        msg = _(msg_zero_verts)%(len(zero_weights), obj.name) 
                        self.report({'WARNING'},msg)
                        raise util.Error(msg)

            meshProps = context.scene.MeshProp
            print("Current filepath is [%s]" % (bpy.data.filepath) )

            self.filepath = bpy.path.ensure_ext(bpy.data.filepath, self.filename_ext)
            self.filepath = self.filepath.replace(".blend","")

            currentSelection = util.getCurrentSelection(context)
            attached         = currentSelection['attached']
            targets          = currentSelection['targets']

            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'RUNNING_MODAL'}

    def execute(self, context):
        preferences = util.getAddonPreferences(data=self)
        sceneProps = context.scene.SceneProp
        meshProps = context.scene.MeshProp
        active = context.scene.objects.active
        omode = active.mode

        self.filepath = bpy.path.ensure_ext(self.filepath, self.filename_ext)
        try:
            print("Karaage: Collada export to file [",self.filepath,"]")
            armobjs = util.get_armatures(context.selected_objects)
            if util.use_sliders(context):
                if len(armobjs) > 0:
                    armobj=list(armobjs)[0]

                    use_bind_pose = armobj.RigProps.rig_use_bind_pose
                else:
                    use_bind_pose = False
            else:
                use_bind_pose = False

            good, mesh_count, export_warnings = exportCollada(context, 
                self.filepath,
                meshProps.exportRendertypeSelection,
                preferences.exportImagetypeSelection,
                preferences.forceImageType,
                preferences.useImageAlpha,
                meshProps.exportArmature,
                meshProps.exportDeformerShape,
                meshProps.exportOnlyActiveUVLayer,
                meshProps.exportIncludeUVTextures,
                meshProps.exportIncludeMaterialTextures,
                meshProps.exportCopy,
                meshProps.applyScale,
                meshProps.apply_mesh_rotscale,
                meshProps.weld_normals,
                meshProps.weld_to_all_visible,
                meshProps.max_weight_per_vertex,
                sceneProps.target_system,
                use_bind_pose,
                sceneProps.collada_export_with_joints
                )

            if good:
                if len(export_warnings) > 0:
                    msg = _(msg_export_warnings)%(len(export_warnings), ''.join(export_warnings))

                    raise util.Warning(msg)
                self.report({'INFO'},"Exported %d %s"% (mesh_count, util.pluralize("Mesh", 1)))
                status = {'FINISHED'}
            else:
                status = {'CANCELLED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            status = {'CANCELLED'}

        context.scene.objects.active = active
        util.ensure_mode_is(omode)

        return status

class UpdateKaraagePopup(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "karaage.update_karaage"
    bl_label = "Karaage Rig Version Mismatch"
    bl_options = {'REGISTER', 'UNDO'}

    armature_name = StringProperty()
    executing = False

    def check(self, context):
        return not self.executing
    
    def invoke(self, context, event):
        self.executing = True
        width = 400 * context.user_preferences.system.pixel_size

        status = context.window_manager.invoke_props_dialog(self, width=width)

        print("karaage.update_karaage: invoke_props_dialog returned status:", status)
        return status

    def draw(self, context):
        obj     = context.object
        if not obj:
            print("UpdateKaraagePopup: No Context Object set (aborting)")
            return

        layout = self.layout
        armatures = util.getKaraageArmaturesInScene(context=context)

        if len(armatures) == 0:
            print("Karaage popup: No Armature found for %s" % (context.object.name) )
            return

        props = util.getAddonPreferences()
        col   = layout.column(align=True)

        row=col.row(align=True)
        row.alignment='RIGHT'
        col_arm  = row.column(align=True)
        col_vers = row.column(align=True)
        col_rig  = row.column(align=True)
        col_bone = row.column(align=True)
        col_stat = row.column(align=True)

        col_arm .label("Armature")
        col_vers.label("Karaage")
        col_rig.label("Rig")
        col_bone.label("Bones")
        col_stat.label("State")
        sep = layout.separator()
        for armobj in armatures:
            karaage_version, rig_version, rig_id, rig_type = util.get_version_info(armobj)
            if rig_version == None:
                rig_version = "unknown"
            col_arm.column().label(armobj.name)
            col_vers.column().label(rig_version)
            col_rig.column().label(str(rig_id))
            joint_count = len(armobj.get('sl_joints',[]))
            col_bone.column().label("%d" % joint_count)

            if rig_id != KARAAGE_RIG_ID and karaage_version != rig_version:
                col_stat.column().label("Update recommended")
            else:
                col_stat.column().label("Update optional")

        sep = layout.separator()
        col = layout.column(align=True)
        col.label("Please perform the recommended updates before")
        col.label("you do any further editing in this blend file.")
        col.label("You find the Karaage Rig Update Tool")
        col.label("in the Karaage Tool Shelf")

    def execute(self, context):
        self.executing = True

        return {'FINISHED'}

#

#

#

#

#

#

#

#

#

class BakeShapeOperator(bpy.types.Operator):
    bl_idname      = "karaage.bake_shape"
    bl_label       = _("Bake Shape")
    bl_description = _("Bake Visual shape into Mesh (WARNING: This operation applies ALL custom shape keys!)")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context and context.object and context.object.type=='MESH'

    def execute(self, context):
        ob = context.object
        omode=util.ensure_mode_is("OBJECT", object=ob)
        slider_type = str(ob.ObjectProp.slider_selector)

        if slider_type != 'NONE':
            meshProps = context.scene.MeshProp
            dupobj = freezeMeshObject(context, ob, apply_shape_modifiers=meshProps.apply_shrinkwap_to_mesh)
            dupobj.ObjectProp.slider_selector = 'SL'
            util.ensure_mode_is(omode, object=dupobj)

        return{'FINISHED'}

def freezeMeshObject(context, obj, apply_shape_modifiers=False, preserved_shape_keys=None, filter=None, preserve_volume=None):
    final_active = context.active_object
    name         = obj.name

    dupobj = util.visualCopyMesh(context,
            obj,
            apply_pose           = False,
            remove_weights       = False,
            apply_shape_modifiers= apply_shape_modifiers,
            preserved_shape_keys = preserved_shape_keys,
            filter               = filter,
            preserve_volume      = preserve_volume)
            
    dupobj.hide   = obj.hide
    dupobj.layers = obj.layers

    arm = obj.find_armature()
    if arm is not None and dupobj.parent != arm:
        dupobj.parent = arm

    dupobj.select = obj.select
    obj.select = False
    if final_active == obj:
        final_active = dupobj

    mode=util.ensure_mode_is("OBJECT", object=obj)
    context.scene.objects.unlink(obj)
    bpy.data.objects.remove(obj)
    dupobj.name = name
    util.ensure_mode_is(mode, object=dupobj)

    if final_active is not None:
        context.scene.objects.active = final_active

    return dupobj

def freezeSelectedMeshes(context, operator, apply_pose=None, remove_weights=None, join_parts=None, attach_sliders=None, handle_source=None, preserve_volume=None):
    scn = context.scene
    if apply_pose == None:
        apply_pose = scn.MeshProp.standalonePosed
    if remove_weights == None:
        remove_weights = scn.MeshProp.removeWeights
    if join_parts == None:
        join_parts = scn.MeshProp.joinParts
    if attach_sliders == None:
        attach_sliders = scn.MeshProp.attachSliders
    if handle_source == None:
        handle_source = scn.MeshProp.handleOriginalMeshSelection

    currentSelection = util.getCurrentSelection(context)
    karaages         = currentSelection['karaages']
    targets          = currentSelection['targets']
    others           = currentSelection['others']
    active           = currentSelection['active']

    dupobj = None
    final_active = active
   
    frozen = {}
    arms = set()
    for target in targets:
        name = target.name
        print("Freezing %s %s (use_deform_preserve_volume=%s)" % (target.type, name, target.get('use_deform_preserve_volume','none')))

        dupobj = util.visualCopyMesh(context,
                target,
                apply_pose = apply_pose,
                remove_weights = remove_weights,
                preserve_volume=preserve_volume)

        if 'karaage-mesh'      in dupobj: del dupobj['karaage-mesh']
        if 'avastar=mesh'      in dupobj: del dupobj['avastar-mesh']
        if 'weight'            in dupobj: del dupobj['weight']
        if 'ShapeDrivers'      in dupobj: del dupobj['ShapeDrivers']
         
        if apply_pose:

            dupobj.parent_type = 'OBJECT'

            try:
                del dupobj['karaage-mesh']
                
            except:
                pass
                
            try:
                del dupobj['avastar-mesh']
                
            except:
                pass
            dupobj.parent = None
            dupobj.matrix_world = target.matrix_world.copy()
        
        if handle_source == 'HIDE':
            target.hide = True
        if not apply_pose:
            arm = target.find_armature()
            if arm:
                util.ensure_mode_is('OBJECT')
                util.parent_selection(context, arm, [dupobj], keep_transform=True)
                arms.add(arm)
        if target == active:
            final_active = dupobj # make clone of active part the new active

        target.select = False
        dupobj.select = True

        frozen[name]=[target,dupobj]

    result = []

    if len(frozen) > 0:
        if len(arms) > 0:
            arm = next(iter(arms)) #to have an existing context object
            context.scene.objects.active = arm
        omode = util.ensure_mode_is("OBJECT")
        bpy.ops.object.select_all(action='DESELECT') 

        for target,dupobj in frozen.values():
            dupobj.select=True
            for mod in dupobj.modifiers:
                ob = getattr(mod,"object", None)
                if ob and ob.name in frozen:
                    mod.object = frozen[ob.name][1]

        result = []
        for target,dupobj in frozen.values():
            if handle_source == 'DELETE':
                name = target.name
                util.ensure_mode_is('OBJECT', object=target)
                context.scene.objects.unlink(target)
                try:
                    bpy.data.objects.remove(target,  do_unlink=True)
                except:

                    bpy.data.objects.remove(target)
                dupobj.name = name
            result.append(dupobj)
        del frozen
        util.ensure_mode_is(omode)

        tc = len(targets)

        context.scene.objects.active = final_active

        if join_parts:
            bpy.ops.object.join()
            tc = 1
            if scn.MeshProp.removeDoubles:
                original_mode = util.ensure_mode_is("EDIT")
                me = final_active.data
                bme  = bmesh.from_edit_mesh(me)
                bm=bmesh.new()
                target_verts = util.get_boundary_verts(bm, context, final_active)

                try:
                    bme.verts.ensure_lookup_table()
                except:
                    pass

                for v in target_verts:
                   bme.verts[v.index].select=True
                bmesh.update_edit_mesh(me)
                bpy.ops.mesh.remove_doubles()
                util.ensure_mode_is(original_mode)
                bm.clear()
                bm.free()
                result = [final_active]

        if attach_sliders:
            log.warning("Attaching Sliders ...")
            for arm in arms:
                shape.destroy_shape_info(context, arm)
                log.warning("Destroyed Sliders for %s" % (arm.name) )
            for arm in arms:
                arm.ObjectProp.slider_selector='SL'
                log.warning("Atttached Sliders for %s" % (arm.name) )
        else:
            log.warning("Slider attachment not Selected")

        meshes = util.pluralize("mesh", tc)
        operator.report({'INFO'},_("Created %d frozen %s")%(tc, meshes))

    return result

def remove_verts_from_all_vgroups(obj, index_list):
    print("remove verts from groups", *index_list)
    util.ensure_mode_is('EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    util.ensure_mode_is('OBJECT')
    me = obj.data
    for i in index_list:
        me.vertices[i].select=True

    util.ensure_mode_is('EDIT')
    bpy.ops.object.vertex_group_remove_from(use_all_groups=True)
    bpy.ops.mesh.select_all(action='DESELECT')
        
def add_verts_to_vgroup(obj, index_list, group_name):
    print("add verts to group", group_name, ":", *index_list)
    util.ensure_mode_is('EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    util.ensure_mode_is('OBJECT')
    me = obj.data
    for i in index_list:
        me.vertices[i].select=True
    obj.vertex_groups.active_index=obj.vertex_groups[group_name].index

    util.ensure_mode_is('EDIT')
    bpy.ops.object.vertex_group_assign()
    bpy.ops.mesh.select_all(action='DESELECT')

def weld_vertex_weights(obj, index_list):
    print("weld seam weights:", *index_list)
    util.ensure_mode_is('EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    util.ensure_mode_is('OBJECT')
    me = obj.data
    for i in index_list:
        me.vertices[i].select=True    
    util.ensure_mode_is('EDIT')
    bpy.ops.karaage.weld_weights_from_rigged()

def generate_face_weights(context, arm, obj):
    print("Generate face weights for %s:%s" % (arm.name, obj.name) )
    dbones = arm.data.bones
    for b in dbones:
        b.select=False
 
    bones = [b for b in dbones if b.name.startswith('mFace') or b.name.startswith('mHead')]
    for b in bones:
        b.select=True
        if b.name in SL_ALL_EYE_BONES:
            b.use_deform = False

    print("Weighting %d Face bones" % (len(bones)) )
    context.scene.objects.active = obj
    util.ensure_mode_is('WEIGHT_PAINT')
    bpy.ops.paint.weight_from_bones(type='AUTOMATIC')

    seam        = [0, 1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 106, 107, 110, 111, 112, 114, 336, 338]
    weld_vertex_weights(obj, seam)

    for b in bones:
        b.select=False
        if b.name in SL_ALL_EYE_BONES:
            b.use_deform = True

    upper_teeth = [42, 45, 46, 47, 86, 87, 201, 300, 395, 413, 665, 666, 720, 748]
    lower_teeth = [37, 38, 39, 79, 81, 139, 203, 210, 298, 394, 396, 661, 662, 664]
    
    util.ensure_mode_is('OBJECT')
    remove_verts_from_all_vgroups(obj, upper_teeth+lower_teeth)
    add_verts_to_vgroup(obj, lower_teeth, 'mFaceJaw')
    add_verts_to_vgroup(obj, upper_teeth, 'mHead')
    util.ensure_mode_is('OBJECT')

def get_extended_mesh(context, part, copy=True):
    extended_name = "%s_extended" % part

    ob = bpy.data.objects.get(extended_name, None)
    if ob and copy:
        me = ob.data.copy()
        ob = ob.copy()
        ob.data = me
        context.scene.objects.link(ob)

    return ob

def copy_weights(armobj, src, tgt, vert_mapping):
    util.ensure_mode_is('OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    src.select  = True
    tgt.select  = True
    bpy.context.scene.objects.active = tgt

    limit = vert_mapping != 'TOPOLOGY'

    try:
        bpy.ops.object.data_transfer(
            use_reverse_transfer=True,
            use_create=True,
            vert_mapping=vert_mapping,
            data_type='VGROUP_WEIGHTS',
            layers_select_src='NAME',
            layers_select_dst='ALL',
            mix_mode='REPLACE')
    except:
        try:
            bpy.ops.object.data_transfer(
                use_reverse_transfer=True,
                use_create=True,
                vert_mapping=vert_mapping,
                data_type='VGROUP_WEIGHTS',
                layers_select_dst='NAME',
                layers_select_src='ALL',
                mix_mode='REPLACE')
        except:

            selectedBoneNames = weights.get_bones_from_armature(armobj, True, True)
            weights.copyBoneWeightsToSelectedBones(tgt, [src], selectedBoneNames, submeshInterpolation=False, allVerts=True, clearTargetWeights=True)
            limit = True

    if limit:
        bpy.ops.object.vertex_group_limit_total(group_select_mode='BONE_SELECT')

def generate_hand_weights(context, arm, obj):

    dbones = arm.data.bones
    for b in dbones:
        b.select=False
    
    bones = [b for b in dbones if b.name.startswith('mHand') or b.name.startswith('mWrist')]
    for b in bones:
        b.select=True

    print("Create Hand Rig            : Generate Weights for %d Hand bones (automatic from Bones)" % (len(bones)) )
    context.scene.objects.active = obj
    util.ensure_mode_is('WEIGHT_PAINT')
    bpy.ops.paint.weight_from_bones(type='AUTOMATIC')
    util.ensure_mode_is('OBJECT')

    for b in bones:
        b.select=False

def get_extended_weights(context, armobj, tgt, part, vert_mapping='TOPOLOGY'):
    extended_src = get_extended_mesh(context, part)
    if extended_src:

        copy_weights(armobj, extended_src, tgt, vert_mapping)

        try:

            bpy.ops.object.vertex_group_clean(group_select_mode='BONE_DEFORM') # to remove zero entries in weight maps
        except:

            bpy.ops.object.vertex_group_clean(group_select_mode='ALL')         # to remove zero entries in weight maps

        print("Create Rig                : Transfered %d Weight Maps from Karaage template %s" % (len(extended_src.vertex_groups), extended_src.name ))

        context.scene.objects.unlink(extended_src)
        bpy.data.objects.remove(extended_src)
    else:
        print("No extended Weight source defined for part [%s]" % (part) )
        if part == 'upperBodyMesh':
            generate_hand_weights(context, armobj, tgt)
            return
        elif part == 'headMesh':
            generate_face_weights(context, armobj, tgt)
            return
        print("No Weight Generator defined for part %s" % (part) )

def copyBoneWeights(operator, context, obj, weight_sources, clearTargetWeights, submeshInterpolation, enforce_meshes=None, copy_type = None):
    print("Called copyBoneWeights with copy_type %s" % (copy_type))
    if enforce_meshes:
        print("enforce copy from system messhes %s" % (enforce_meshes))

    currentSelection = util.getCurrentSelection(context)
    karaages         = currentSelection['karaages']
    targets          = currentSelection['targets']
    others           = currentSelection['others']
    active           = currentSelection['active']
    if obj and obj.type=='MESH':
        weighttargets    = [obj]
    else:
        weighttargets    = currentSelection['weighttargets']
            
    logging.debug(_("Bone weight targets: %s"), repr([t.name for t in weighttargets]))

    if len(karaages) == 0:
        if obj and obj.type == "MESH":
            armobj = obj.find_armature()
        else:
            operator.report({'WARNING'},_("%s is not a Mesh target") % obj.name)
            return
    else:
        armobj = karaages[0]

    sources = []
    tempobj = []
    other_mesh_count = 0
    for childobj in weight_sources:
        other_mesh_count += 1
        enforce_usage = enforce_meshes and ("karaage-mesh" in childobj or 'avastar-mesh' in childobj) and any(childobj.name.startswith(x) for x in enforce_meshes)
        if enforce_usage:
            print("Force include [%s] in Weight Copy" % (childobj.name))
        if copy_type == 'EXTENDED' or enforce_usage or (not enforce_meshes and not childobj.hide and not childobj.name.startswith('CustomShape_') \
            and True in [x and y for x,y in zip(childobj.layers,context.scene.layers)]
            and childobj not in weighttargets):

            if len(childobj.data.vertices) == 0:
                operator.report({'WARNING'},_("Mesh %s with 0 vertices can't be used as weight source")%(childobj.name))
                continue
                
            if copy_type == 'EXTENDED':
                part = childobj.name.split('.')[0]
                nob = get_extended_mesh(context, part)
                if nob:
                    print("Get extended weights from %s" % (nob.name) )
                    tempobj.append(nob)
                    childobj = nob
                else:
                    continue

            print("Adding child object %s " % childobj.name)
            childmesh = childobj.to_mesh(context.scene, True, 'PREVIEW')
            childmesh.update(calc_tessface=True)
            childcopyobj = bpy.data.objects.new(childobj.name, childmesh)
            childcopyobj.matrix_world = childobj.matrix_world.copy()
            context.scene.objects.link(childcopyobj)
            tempobj.append(childcopyobj)
            
            print("Created baked version of child mesh as %s" % childcopyobj.name)
            
            sources.append((childcopyobj, childobj))

    if len(sources) == 0:
        if obj:
            obname="[%s]"%obj.name
        else:
            obname="your current Selection"
            
        if other_mesh_count == 0:
            msg = msg_no_objects_to_copy_from % (obname, armobj.name)
        else:
            msg = msg_no_weights_to_copy_from % (obname, armobj.name)

        log.warning(msg)
        return
        
    context.scene.update()

    logging.debug(_("Bone weight sources: %s"), repr([s[1].name for s in sources]))
    for target in weighttargets:

        M=target.matrix_world
        clean_target_groups = []

        nv = 0 # track number of vertices for reporting
        fv = 0 # track number of verts which could not receive a weight
        for vertex in target.data.vertices:

            if context.scene.MeshProp.copyWeightsSelected and not vertex.select:
                continue

            vs = []

            pt = M*vertex.co

            for source in sources:

                if source[1].name != target.name:

                    d, gdata = weights.getWeights(source[0],source[1],pt, submeshInterpolation)
                    vs.append((d,gdata))
                
            if len(vs) == 0:
                fv += 1
            else:
                vmin = min(vs, key=lambda v: v[0])
                for gn,w in vmin[1].items():
                    if clearTargetWeights and gn in target.vertex_groups and gn not in clean_target_groups:
                        target.vertex_groups.remove(target.vertex_groups[gn])

                    if gn not in target.vertex_groups:
                        target.vertex_groups.new(gn)
                        clean_target_groups.append(gn)
                    target.vertex_groups[gn].add([vertex.index], w, 'REPLACE')

                nv+=1  

        if nv > 0:
            operator.report({'INFO'},_("Copied bone weights to %d/%d vertices in %s")%(nv,len(target.data.vertices),target.name))
        if fv > 0:
            if fv == len(target.data.vertices):
                operator.report({'WARNING'},_("Could not find any weights for %s")%(target.name))
            else:
                operator.report({'WARNING'},_("No weights copied for %d/%d verts of %s")%(fv,len(target.data.vertices),target.name))

    for ob in tempobj:
        context.scene.objects.unlink(ob)
        bpy.data.objects.remove(ob)

    context.scene.objects.active = active

def generateWeightsFromBoneSet(obj, bone_names, type='AUTOMATIC', clear=False, selected=False):
    if obj.type=='MESH':

        armobj = obj.find_armature()
        if armobj:

            active = bpy.context.scene.objects.active
            if bone_names==None or len(bone_names) == 0:
                bone_names = [bone.name for bone in armobj.data.bones if bone.use_deform]
                if len(bone_names) == 0:
                    bone_names = data.get_deform_bones(obj, exclude_volumes=TRue, exclude_eyes=True)
            if clear:

                if selected:
                    util.removeWeightsFromSelected(obj,bone_names)
                else:
                    util.removeWeightGroups(obj,bone_names)

            if type == 'FACEGEN':
                bpy.ops.karaage.face_weight_generator('EXEC_DEFAULT')
            else:

                layer_visibility = {i:layer for i,layer in enumerate(armobj.data.layers) if i in [B_LAYER_SL, B_LAYER_VOLUME, B_LAYER_DEFORM, B_LAYER_EXTENDED]}
                armobj.data.layers[B_LAYER_SL]       = True #ensure the deform bone are visible
                armobj.data.layers[B_LAYER_EXTENDED] = True #ensure the deform bone are visible
                armobj.data.layers[B_LAYER_VOLUME]   = True #ensure the deform bone are visible
                armobj.data.layers[B_LAYER_DEFORM]   = True #ensure the deform bone are visible

                util.setSelectOption(armobj, bone_names)
                bpy.context.scene.objects.active = obj
                original_mode = util.ensure_mode_is("WEIGHT_PAINT")

                deform_backup = util.setDeformOption(armobj, bone_names+data.get_deform_bones(obj, exclude_volumes=True, exclude_eyes=True))
                if selected:
                    obj.data.use_paint_mask=True
                    obj.data.use_paint_mask_vertex=True

                else:
                    obj.data.use_paint_mask=False
                    obj.data.use_paint_mask_vertex=False

                bpy.ops.paint.weight_from_bones(type=type)

                unweighted = [v.index for v in obj.data.vertices if len(v.groups)==0]

                for layer in layer_visibility.keys():
                    armobj.data.layers[layer] = layer_visibility[layer]

                util.restoreDeformOption(armobj, deform_backup)
                util.ensure_mode_is(original_mode)
                bpy.context.scene.objects.active = active
        else:
            print("No Armature assigned to Object", obj)
    else:
        print("Do not generate weights for Object %s of type %s" % (obj.name,obj.type))

def get_uv_material_image_assoc(obj, mat_images, active_uv_layer_only=True):

    if (obj.type !='MESH'):
        logging.warn(_('Object of type %s has no uv textures'), obj.type)
    else:

        mesh = obj.data
        mesh.update(calc_tessface=True)
        uv_layers = mesh.uv_layers
        
        missing_images = {}
        for index in range(len(uv_layers)):
            layer = uv_layers[index]
            if active_uv_layer_only==False or layer == uv_layers.active:
                for polygon in mesh.polygons:
                    image = mesh.uv_textures[index].data[polygon.index].image
                    if image:
                        mat_index=polygon.material_index
                        if not  ( (mat_index, image) in mat_images or image.name in missing_images):
                            try:
                                mat = mesh.materials[mat_index]
                                mat_images[mat_index,image] = (mat, image)
                                print("UV: Added mat:%d %s image:%s" % (mat_index, mat.name, image.name) )
                            except Exception as e:
                                print(e)
                                missing_images[image.name] = image
                                logging.warn(_('Image "%s" is assigned to non existing material index %d')%(image.name,mat_index))
    return mat_images

def get_material_image_assoc(obj, mat_images):
    mat_slots = obj.material_slots
    for mat_index in range (len(mat_slots)):
        material_slot = mat_slots[mat_index]
        material = material_slot.material
        for texture_slot in material.texture_slots:
            if texture_slot and texture_slot.texture:
                texture = texture_slot.texture
                if texture.image:
                    if (not (material, texture.image) in mat_images):
                        mat_images[mat_index, texture.image] = (material, texture.image)
                        print("MA: Added mat:%d %s image:%s" % (mat_index, material.name, texture.image.name) )
    return mat_images

#
def get_images_for_material(mat_images, material):
    images=[]
    for key in mat_images:
        if mat_images[key][0] == material:
            images.append(mat_images[key][1])
    return images
    
def create_libimages(root, base, mat_images, exportCopy, preferred_image_format, force_image_format, useImageAlpha, warnings):

    libimages = subx(root, 'library_images')
    saved    = []

    original_color_mode = bpy.context.scene.render.image_settings.color_mode
    if useImageAlpha:
       cm = 'RGBA'
    else:
       cm = 'RGB'
    bpy.context.scene.render.image_settings.color_mode = cm
    
    for key in mat_images:
        material, image = mat_images[key]
        
        if image in saved: #Take care to process each image only once.
            continue
        saved.append(image)

        original_format     = image.file_format
        
        if image.source == 'GENERATED' or force_image_format:
            format = preferred_image_format
        else:
            format = original_format
            
        file_extension = format.lower()
        if file_extension == "jpeg":
            file_extension = "jpg"
        if file_extension == "targa":
            file_extension = "tga"
        file_extension = '.' + file_extension
        try:
            image.file_format = format
        except:
            msg = _("The image [%s] has an unsupported file fromat [%s].|\n\n" \
                  "YOUR ACTION:\nPlease disable export of UV tectures or switch \n"\
                  "to another file format and try again." % (image.name,format))
            logging.error(msg)
            raise util.Warning(msg)            
        collada_key = colladaKey(image.name) 
        imgx = subx(libimages, 'image', id=collada_key, name=collada_key)
        
        collada_path = bpy.path.ensure_ext(collada_key, file_extension )

        image_on_disk = True
        if image.is_dirty or image.packed_file or image.source == 'GENERATED':

            dest = os.path.join(base,collada_path)
            dest = os.path.abspath(dest)
            image.save_render(dest)
            logging.info(_("Generated image %s"), collada_path)
        elif exportCopy:

            dest   = os.path.join(base,collada_path)
            dest   = os.path.abspath(dest)
            if image.filepath_raw is None or "":
                logging.warn(_("Source Image [%s] is not available on disk. (Please check!) ")%(image.name))
                warnings.append("Image [%s] from material [%s]: not found on disk\n" %
                    (
                        util.shorten_text(image.name),
                        util.shorten_text(material.name)
                    )
                )
                image_on_disk = False
            else:
                source = bpy.path.abspath(image.filepath_raw)
                source = os.path.abspath(source)
                
                if source == dest:
                    logging.info(_("Image %s Reason: Image already in place.")%(collada_path))
                else:
                    try:
                        shutil.copyfile(source, dest)
                        logging.info(_("Copied image %s"), collada_path)
                    except Exception as e:
                        print(e)
                        print("image   :",image.name)
                        print("filename: [",image.filepath_raw,"]")
                        print("source  :", source)
                        print("dest    :", dest)
                        logging.warn(_('Can not copy Image from [%s] to [%s]')%(source, dest))
                        warnings.append("%s: Can't copy source [%s] for material[%s]\n" %
                            (
                                util.shorten_text(image.name),
                                util.shorten_text(source, 16, cutbegin=True),
                                util.shorten_text(material.name)
                            )
                        )
                        image_on_disk = False
                        
        else:

            if image.filepath_raw is None or "":
                logging.warn(_("Image %s is not available on disk. (Please check!) ")%(image.name))
                warnings.append("%s: Source for material [%s] not found on disk)\n" %
                    (
                        util.shorten_text(image.name),
                        util.shorten_text(material.name)
                    )
                )
                image_on_disk = False
            else:
                source = bpy.path.abspath(image.filepath_raw)
                source = os.path.abspath(source)
                collada_path = source
                logging.info(_("Refer to image %s"), source)
        if image_on_disk:
            subx(imgx,'init_from', text=collada_path)
        
        image.file_format = original_format
        
    bpy.context.scene.render.image_settings.color_mode = original_color_mode
    return libimages
    
def get_normal_index(n, normals, normalsd):
    normal = (round(n.x,6), round(n.y,6), round(n.z,6)) 
    try:
        nidx = normalsd[normal]
    except:
        nidx = len(normals)
        normals.append(normal)
        normalsd[normal]=nidx
    return nidx

def create_polylists(mesh, welded_normals, progress):
    current_time = time.time()
    begin_time   = current_time
    #

    #

    polygons = mesh.polygons
    uvexists = len(mesh.uv_layers)>0
    if uvexists:
        uv_data = mesh.uv_layers.active.data

    polylists= {}
    normals  = []
    normalsd = {}
    uv_array = []
    uvidx = 0
    
    last_mat_index = -1
    vcount = []
    ps     = []
    lc     = 0    
    
    pcounter = 0
    
    for p in polygons:
    
        pcounter += 1
        if pcounter % 1000 == 0:
            util.progress_update(1, absolute=False)            

        mat_index = p.material_index
        if mat_index != last_mat_index:

            if last_mat_index != -1:

                polylists[last_mat_index]=(vcount, ps, lc)

            last_mat_index = mat_index
            try:
                vcount = polylists[mat_index][0]
                ps     = polylists[mat_index][1]
                lc     = polylists[mat_index][2]

            except:
                vcount = []
                ps     = []
                lc     = 0
                polylists[mat_index]=(vcount, ps, lc)

        vlen=len(p.vertices)
        vcount.append(str(vlen))
        lc += vlen
        
        if p.use_smooth:

            fixcount = 0
            for vidx,v in enumerate(p.vertices):
                x=0
                if welded_normals and v in welded_normals:
                    n = welded_normals[v]
                    fixcount +=1
                else:
                    n = mesh.loops[p.loop_indices[vidx]].normal
                
                nidx = get_normal_index(n, normals, normalsd)
                if uvexists:
                    ps.extend((str(v),str(nidx),str(uvidx)+" "))
                    
                    uv = uv_data[p.loop_indices[vidx]].uv
                    uv_array.extend(("%g"%round(uv[0],6), "%g  "%round(uv[1],6)))
                    uvidx +=1
                else:
                    ps.extend((str(v),str(nidx)+" "))

        else:

            n = p.normal
            nidx = get_normal_index(n, normals, normalsd)
            
            for vidx, v in enumerate(p.vertices):
                if uvexists:
                    ps.extend((str(v),str(nidx),str(uvidx)+" "))
                    
                    uv = uv_data[p.loop_indices[vidx]].uv
                    
                    uv_array.extend(("%g"%round(uv[0],6), "%g  "%round(uv[1],6)))
                    uvidx +=1
                else:
                    ps.extend((str(v),str(nidx)+" "))
                
        ps.append("  ")

    if last_mat_index != -1:
        polylists[last_mat_index]=(vcount, ps, lc)

    print("Created %d UV faces and %d polylists in %.0f milliseconds" % (uvidx, len(polylists), 1000*(time.time()-begin_time)))
    return polylists, normals, uv_array

def colladaKey(key):

    result = re.sub("[^\w-]","_",key)
    return result

def add_material_list(tech, mesh, uv_count):
    materials = mesh.data.materials
    has_uv_layout = uv_count > 0
    for material in materials:
        if material is None:

            continue
            
        collada_material = colladaKey(material.name + "-material")
        inst = subx(tech, "instance_material", symbol=collada_material, target="#"+collada_material)
        if has_uv_layout:
            try:
                semantic = mesh.data.uv_layers.active.name
            except:

                semantic = mesh.data.uv_textures.active.name
            subx(inst, "bind_vertex_input", semantic=semantic, input_semantic="TEXCOORD", input_set="0")

def attachment_name(bone_name):
    return bone_name[1:].replace(" ", "_")

def exportCollada(context,
                  path,
                  exportRendertypeSelection,
                  preferred_image_format,
                  force_image_format,
                  useImageAlpha,
                  export_armature,
                  export_deformer_shape,
                  exportOnlyActiveUVLayer,
                  exportIncludeUVTextures,
                  exportIncludeMaterialTextures,
                  exportCopy,
                  applyScale,
                  apply_mesh_rotscale,
                  weld_normals,
                  weld_to_all_visible,
                  max_weight_per_vertex,
                  target_system,
                  use_bind_pose,
                  with_joints
                  ):

    def get_bind_joint_array(array, rcount):
        indent = "\n          "
        text = indent.join([" ".join(array[i:i + rcount]) for i in range(0, len(array), rcount)])
        return indent + text + indent

    def get_export_bone_set(arm, sceneProps, target_system, dbones):
        export_bones = []
        for bone_name in dbones:
            if bone_name in export_bones:

                continue

            if bone_name in arm.data.bones:
                b=arm.data.bones[bone_name]
                if b.use_deform or not sceneProps.collada_only_deform:
                    if target_system != 'BASIC' or bone_name in SLALLBONES:

                        if (bone_name[0] == 'a' and sceneProps.accept_attachment_weights) or bone_name[0] == 'm' or bone_name in SLVOLBONES:
                            export_bones.append(bone_name)
                            log_export.info("export_bone_set: Appended deform bone [%s]" % bone_name)
                            p = b.parent
                            while p:
                                if p.name not in export_bones:
                                    if util.has_head_offset(p) or sceneProps.collada_full_hierarchy:
                                        if p.use_deform:
                                            export_bones.append(p.name)
                                            log_export.info("export_bone_set: Appended parent bone [%s]" % p.name)
                                    p = p.parent
                                else:
                                    break
            else:
                log_export.warning("export_bone_set: Bone %s is missing in the armature. (Treat as non deforming)" % (bone_name) )

        if target_system == 'BASIC': #or not sceneProps.collada_only_weighted:

            for bone_name in SLBASEBONES:
                if bone_name not in export_bones:
                    export_bones.append(bone_name)
                    log_export.info("export_bone_set: Added mandatory SL Base bone [%s]" %bone_name)
                
        return export_bones
    
    sceneProps  = context.scene.SceneProp
    with_rot    = sceneProps.collada_export_rotated

    log_export.info("Export Karaage Collada for Target system[%s]" % (target_system) )
    pathbase, ext = os.path.splitext(path)
    base,filename = os.path.split(pathbase)

    enumerated_objects = []
    armatures = []
    mesh_objects = []
    mat_images = {}

    complexity_warnings = []

    util.progress_begin(0,10000)
    progress = 0
    util.progress_update(progress)

    selected_objects = util.get_selected_objects(context)
    for index, obj in enumerate(selected_objects):
        if obj.type == 'MESH':

            if exportIncludeUVTextures:
                mat_images = get_uv_material_image_assoc(obj, mat_images, exportOnlyActiveUVLayer)
            if exportIncludeMaterialTextures:
                mat_images = get_material_image_assoc(obj, mat_images)

            if export_armature:

                arm = util.getArmature(obj)

                if arm is not None and arm not in armatures:
                    if 'karaage' in arm or 'avastar' in arm:
                        armatures.append(arm)
                    else:
                        msg = "%s : Armature [%s] not an Karaage Rig (i can't export the mesh)\n" % (
                                util.shorten_text(obj.name),
                                util.shorten_text(arm.name)
                            )
                        complexity_warnings.append(msg)
                        print("Warning: %s" % msg )
                        continue

            enumerated_objects.append((index, obj.name))
            mesh_objects.append(obj)

    enumerated_objects.sort(key=lambda name: name[1])

    if weld_normals:
        if weld_to_all_visible:
            mobs = [ob for ob in context.visible_objects if ob.is_visible(context.scene) and ob.type=="MESH"]
        else:
            mobs = mesh_objects
        try:
            adjusted_normals = util.get_adjusted_vertex_normals(context, mobs, exportRendertypeSelection, apply_mesh_rotscale)
        except:
            adjusted_normals = None

    else:
        adjusted_normals = None
    #

    #
    root = et.Element('COLLADA', attrib={'xmlns':'http://www.collada.org/2005/11/COLLADASchema', 'version':'1.4.1'})  
    root.tail = os.linesep
    xml = et.ElementTree(root)
    
    asset = subx(root, 'asset')

    contributor = subx(asset, 'contributor')
    subx(contributor, 'author', text = "Karaage User")    
    karaage_version = "%d-%s-%d"%bl_info['version']
    subx(contributor, 'authoring_tool', text = 'Karaage %s on Blender %s'%(karaage_version,bpy.app.version_string))    
    tstamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    subx(asset, 'created',  text=tstamp)    
    subx(asset, 'modified', text=tstamp)    
    subx(asset, 'unit',     name='meter', meter='1')    
    subx(asset, 'up_axis',  text="Z_UP")    
    
    subx(root, 'library_cameras')    
    subx(root, 'library_lights')

    if len(mat_images) > 0:

        libimages = create_libimages(
                                     root,
                                     base,
                                     mat_images,
                                     exportCopy,
                                     preferred_image_format,
                                     force_image_format,
                                     useImageAlpha,
                                     complexity_warnings)

    libeffects   = subx(root, 'library_effects')
    libmaterials = subx(root, 'library_materials')

    libgeo = subx(root, 'library_geometries')
    libcon = subx(root, 'library_controllers')
    libvis = subx(root, 'library_visual_scenes')
    visual_scene = subx(libvis, 'visual_scene', id='Scene', name='Scene')   
    arm_roots = {}

    active = context.object
    omode  = util.ensure_mode_is("OBJECT", context=context)
    
    for arm in armatures:
        logging.debug(_("Export armature %s"), arm.name)
        aid = colladaKey(arm.name)
        node = subx(visual_scene, 'node', id=aid, name=aid, type='NODE')
        subx(node, 'translate', sid='location', text='0 0 0')
        subx(node, 'rotate', sid='rotationZ', text='0 0 1 0')
        subx(node, 'rotate', sid='rotationY', text='0 1 0 0')
        subx(node, 'rotate', sid='rotationX', text='1 0 0 0')
        subx(node, 'scale', sid='scale', text='1 1 1')

        selection = util.get_animated_meshes(context, arm, only_selected=True)
        if target_system == 'BASIC':
            export_bone_set = None # export all bones
        else:
            dbones = util.get_weight_group_names(selection)
            if sceneProps.collada_full_hierarchy:
                export_bone_set = get_export_bone_set(arm, sceneProps, target_system, dbones)
            elif sceneProps.collada_only_weighted:
                export_bone_set = dbones
            else:
                export_bone_set = None # export all bones

        print("Exporting armature %s" % (arm.name) )
        rigstates = {}

        context.scene.objects.active=arm
        vl= [l for l in context.scene.layers]
        context.scene.layers = [True]*20
        ohide = arm.hide
        arm.hide=False
        amode   = util.ensure_mode_is("EDIT", context=context)

        arm_roots[arm.name] = bonetoxml(arm, node, 'mPelvis', applyScale, target_system, export_bone_set, rigstates, sceneProps, is_root=True, with_joints=with_joints)
        util.ensure_mode_is(amode, context=context)
        context.scene.layers = vl

        print("Exporting Armature: %s" % (arm.name))
        print("Root bones:")
        roots = arm_roots[arm.name]
        for key in roots:
            print("    %s" % (key) )
        print("Exported child bones:")
        for key, val in rigstates.items():
            if len(val) > 0:
                if key in ['avatar_pos']:
                    print("    %3d %s bones" % (len(val), key))
                else:
                    print("    %3d %s bones:" % (len(val), key))
                    for vkey, m in val.items():
                        t = m.translation
                        print("        [% .3f % .3f % .3f] (%s)" % (t[0], t[1], t[2], vkey) )

        if export_deformer_shape:
            shape_file_path = pathbase + '.xml'
            shape.saveProperties(arm, shape_file_path, normalize=True)
        arm.hide = ohide

    util.ensure_mode_is(omode, context=context)
    context.scene.objects.active=active
    
    created_materials = {}

    geometry_name = None
    for index, obj_name in (enumerated_objects):
        mesh = selected_objects[index]

        progress += 100
        util.progress_update(progress)

        try:
            assert ( obj_name == mesh.name )
        except:
            logging.error("Error in ordering the selection by object name.")

        mesh_data_copy = util.getMesh(
                              context, 
                              mesh, 
                              exportRendertypeSelection, 
                              apply_mesh_rotscale=apply_mesh_rotscale, 
                              apply_armature=use_bind_pose)

        log.warning("Export: recaclulate normals after getMesh()")

        logging.debug(_("Export mesh %s"), mesh.name)

        geometry_name = mesh.name
        mid = colladaKey(mesh.name)
        geo = subx(libgeo, 'geometry', id=mid+'-mesh', name=geometry_name)
        mx = subx(geo, 'mesh')

        #

        #

        for midx, mat in enumerate(mesh.data.materials):
            if mat is None:

                continue
                
            material_name = colladaKey(mat.name)
            
            if created_materials.get(material_name) is not None:
                continue
            created_materials[material_name]=material_name
            
            effect_id     = material_name+"-effect"
            material_id   = material_name+"-material"
            
            effect = subx(libeffects, "effect", id=effect_id)
            prof = subx(effect, "profile_COMMON")
            
            images = get_images_for_material(mat_images, mat)
            if len(images) > 0:
                image=images[0]
                if len(images) > 1:
                    print("%d images assigned to material %s, take only %s" % (len(images), material_name, image.name))
            else:
                image = None
                
            if image is not None:
                collada_name = colladaKey(image.name)

                newparam = subx(prof, "newparam", sid=collada_name+'-surface')
                surface = subx(newparam, "surface", type="2D")
                initfrom = subx(surface, "init_from", text=collada_name)
           
                newparam = subx(prof, "newparam", sid=collada_name+'-sampler')
                sampler2d = subx(newparam, "sampler2D")
                source = subx(sampler2d, "source", text=collada_name+"-surface")
            
            tech = subx(prof, "technique", sid="common")
            phong = subx(tech, "phong")
            
            wrap = subx(phong, "emission")
            e = mat.emit
            col = subx(wrap, "color", sid="emission", text="%g %g %g 1"%(e,e,e))
           
            wrap = subx(phong, "ambient")
            col = subx(wrap, "color", sid="ambient", text="0 0 0 1")
            
            wrap = subx(phong, "diffuse")
            if image is not None:
                semantic = mesh.data.uv_layers.active.name
                texture = subx(wrap, "texture", texture=collada_name+'-sampler', texcoord=semantic)
            else:
                i = mat.diffuse_intensity
                c = ["%g"%(j*i) for j in mat.diffuse_color]

                if mat.use_transparency:
                    c.append("%g"%mat.alpha) 
                else:
                    c.append("1") 
                col = subx(wrap, "color", sid="diffuse", text=" ".join(c))
            
            wrap = subx(phong, "specular")
            i = mat.specular_intensity
            c = ["%g"%(j*i) for j in mat.specular_color]
            if mat.use_transparency:
                c.append("%g"%mat.specular_alpha)
            else:
                c.append("1")
            col = subx(wrap, "color", sid="specular", text=" ".join(c))
            
            wrap = subx(phong, "shininess")
            col = subx(wrap, "float", sid="shininess", text="%g"%mat.specular_hardness)
           
            if mat.raytrace_mirror.use:
                wrap = subx(phong, "reflective")
                c = ["%g"%j for j in mat.mirror_color]
                c.append("1")
                col = subx(wrap, "color", sid="reflective", text=" ".join(c))
                
                wrap = subx(phong, "reflectivity")
                col = subx(wrap, "float", sid="reflectivity", text="%g"%mat.raytrace_mirror.reflect_factor)
            
            if mat.use_transparency:
                wrap = subx(phong, "transparency")
                col = subx(wrap, "float", sid="transparency", text="%g"%mat.alpha)
            
            wrap = subx(phong, "index_of_refraction")
            col = subx(wrap, "float", sid="index_of_refraction", text="1.0")
            
            material = subx(libmaterials, "material", id=material_id, name=mat.name)
            subx(material, "instance_effect", url="#"+effect_id)
            
        #

        #
        
        source = subx(mx, 'source', id=mid+'-mesh-positions') 
        positions = []
        for v in mesh_data_copy.vertices:
            p = v.co
            positions.append("%g"%round(p.x,6))
            positions.append("%g"%round(p.y,6))
            positions.append("%g  "%round(p.z,6))          
            
        pos = subx(source, 'float_array', id=mid+'-mesh-positions-array', 
                   count=str(len(positions)))
        pos.text = " ".join(positions)
        
        tech = subx(source, 'technique_common')
        accessor = subx(tech, 'accessor', source='#'+mid+'-mesh-positions-array',
                            stride='3', count=str(int(len(positions)/3)))
        subx(accessor, 'param', name='X', type='float') 
        subx(accessor, 'param', name='Y', type='float') 
        subx(accessor, 'param', name='Z', type='float') 
    
        welded_normals = None
        if adjusted_normals and mesh.name in adjusted_normals:
            welded_normals = adjusted_normals[mesh.name]
        try:

            mesh_data_copy.calc_normals_split()
            log.warning("Export: Recalculate Vertex Normals.")
        except:
            log.warning("Export: This Blender release does not support Custom Normals.")

        polylists, normals, uv_array = create_polylists(mesh_data_copy, welded_normals, progress)
        
        #

        #
        
        normals_array = []        
        for n in normals:
            normals_array.append("%g"%n[0])
            normals_array.append("%g"%n[1])
            normals_array.append("%g  "%n[2])
                        
        source = subx(mx, 'source', id=mid+'-mesh-normals') 
        pos = subx(source, 'float_array', id=mid+'-mesh-normals-array',
                            count=str(len(normals_array))) 
        pos.text = " ".join(normals_array)
            
        tech = subx(source, 'technique_common')
        accessor = subx(tech, 'accessor', source='#'+mid+'-mesh-normals-array',
                            stride='3', count=str(int(len(normals_array)/3)))
        subx(accessor, 'param', name='X', type='float') 
        subx(accessor, 'param', name='Y', type='float') 
        subx(accessor, 'param', name='Z', type='float') 
            
        #

        #

        if len(uv_array) > 0:
            source = subx(mx, 'source', id=mid+'-mesh-map-0') 
            pos = subx(source, 'float_array', id=mid+'-mesh-map-0-array',
                                count=str(len(uv_array))) 
            pos.text = " ".join(uv_array)
                
            tech = subx(source, 'technique_common')
            accessor = subx(tech, 'accessor', source='#'+mid+'-mesh-map-0-array',
                                stride='2', count=str(int(len(uv_array)/2)))
            subx(accessor, 'param', name='S', type='float') 
            subx(accessor, 'param', name='T', type='float') 
        
        #

        #
        vert = subx(mx, 'vertices', id=mid+'-mesh-vertices')
        subx(vert, 'input', semantic='POSITION', source='#'+mid+'-mesh-positions')

        for mat_index in polylists:
            vcount = polylists[mat_index][0]
            ps     = polylists[mat_index][1]
            lc     = polylists[mat_index][2]
            try:
                material = mesh.data.materials[mat_index]
                collada_material = colladaKey(material.name+"-material")
            except:
                material = None
            
            face_count = util.get_tri_count(len(vcount), lc)
            if material is not None:
                mat_name = material.name
                polylist = subx(mx, 'polylist', count=str(face_count), material=collada_material)
            else:
                mat_name = "Default Material"
                polylist = subx(mx, 'polylist', count=str(face_count))

            prefs=util.getAddonPreferences()
            if 0 < prefs.maxFacePerMaterial < face_count:
                msg = "%s : High Tricount %d in material face [%s]" % (mesh.name, face_count, mat_name)
                complexity_warnings.append(msg)
                print("Warning: %s" % msg )
                
            subx(polylist, 'input', source='#'+mid+'-mesh-vertices', 
                                    semantic='VERTEX', offset='0') 
            subx(polylist, 'input', source='#'+mid+'-mesh-normals', 
                                    semantic='NORMAL', offset='1') 

            if len(uv_array) > 0:
                subx(polylist, 'input', source='#'+mid+'-mesh-map-0', 
                                        semantic='TEXCOORD', offset='2', set='0') 
            subx(polylist, 'vcount', text=' '.join(vcount))
            subx(polylist, 'p', text=' '.join(ps))
           
        extra = subx(geo, 'extra')
        tech = subx(extra, 'technique', profile='MAYA')
        subx(tech, 'double_sided', text='1')
           
        node = subx(visual_scene, 'node', id=mid, name=mid, type='NODE')
        
        #

        #

        arm = util.getArmature(mesh)
        if arm is not None:
            context.scene.objects.active=arm
            aid = colladaKey(arm.name)
            controler = subx(libcon, 'controller', name=aid, id=aid+"_"+mid+'-skin')
            skin = subx(controler, 'skin', source='#'+mid+'-mesh')  
            
            #

            #

            bsm = rig.calculate_bind_shape_matrix(arm, mesh, with_rot=with_rot)
            bsm = " ".join(["%g"%round(bsm[ii][jj],6) for ii in range(4) for jj in range(4)]) 
            subx(skin, 'bind_shape_matrix', text=bsm)
            
            #

            #
            source = subx(skin, 'source', id=aid+"_"+mid+"-skin-joints") 
            dbones = [g.name for g in mesh.vertex_groups]# if sceneProps.collada_only_weighted else arm.data.bones.keys()
            
            export_bones = get_export_bone_set(arm, sceneProps, target_system, dbones)

            renamed_groups = []
            for bone_name in export_bones:
                if bone_name[0] == 'a':
                    fname = attachment_name(bone_name)
                    renamed_groups.append(fname)
                else:
                    renamed_groups.append(bone_name)
            
            if len(export_bones) > MAX_EXPORT_BONES and sceneProps.use_export_limits:
                    msg = "The Mesh %s uses %d Bones while SL limit is %d Bones per Mesh." % (mesh.name, len(export_bones), MAX_EXPORT_BONES)
                    complexity_warnings.append(msg)
            
            subx(source, 'Name_array', id=aid+"_"+mid+'-skin-joints-array',
                                    count=str(len(export_bones)), 
                                    text = get_bind_joint_array(renamed_groups, 10))
            tech = subx(source, 'technique_common')
            accessor = subx(tech, 'accessor', 
                                source='#'+aid+'_'+mid+'-skin-joints-array',
                                stride='1',
                                count=str(len(export_bones)))
            subx(accessor, 'param', name='JOINT', type='name') 
            
            #

            #
            source = subx(skin, 'source', id=aid+"_"+mid+"-skin-bind_poses") 
            poses = []
            rig.reset_cache(arm)
            counter = 0
            ohide = arm.hide
            arm.hide=False
            omode = util.ensure_mode_is('POSE', context=context)
            log_export.debug("Export inverse bind pose matrix (use bind pose)")

            for bone_name in export_bones:
                counter += 1
                dbone = arm.data.bones[bone_name]
                Minv = rig.calculate_inverse_bind_matrix(arm, dbone, applyScale, with_sl_rot=with_rot, use_bind_pose=use_bind_pose)
                mat  = rig.matrixToStringArray(Minv, 6)
                if not (counter % 10):
                    mat[-1] = mat[-1]+"\n\n\n"
                poses.extend(mat)
            util.ensure_mode_is(omode, context=context)
            arm.hide = ohide

            subx(source, 'float_array', id=aid+"_"+mid+'-skin-bind_poses-array',
                                        count=str(len(poses)),
                                        text = "\n"+" ".join(poses))
            tech = subx(source, 'technique_common')
            accessor = subx(tech, 'accessor', 
                                source='#'+aid+'_'+mid+'-skin-bind_poses-array',
                                stride='16',
                                count=str(int(len(poses)/16)))
            subx(accessor, 'param', name='TRANSFORM', type='float4x4') 
                
            #

            #
            ws = []
            vcount = []
            vs = []
            source = subx(skin, 'source', id=aid+"_"+mid+"-skin-weights")
            truncated_vcount = 0
            zero_weight_count = 0
            vcounter = 0            
            for v in mesh_data_copy.vertices:
                vcounter += 1
                if vcounter % 1000 == 0:
                    progress += 1
                    util.progress_update(progress)         
            
                weights = []
                for g in v.groups:

                    bonename = const.get_export_bonename(mesh.vertex_groups, g.group, target_system)
                    if bonename and bonename in arm.data.bones:
                        b = arm.data.bones[bonename]
                        if b.use_deform:

                            gidx = export_bones.index(bonename)
                            weights.append([g.weight, gidx])
                            
                weights.sort(key=lambda x: x[0], reverse=True)
                
                if max_weight_per_vertex > 0 and len(weights)>max_weight_per_vertex:
                    if truncated_vcount < 10:
                        logging.warn(_("found vertex with %d deform weights in %s. Truncating to %d."%(len(weights), mesh.name, max_weight_per_vertex)))
                    weights = weights[:max_weight_per_vertex]
                    truncated_vcount += 1 
                
                tot = 0
                for w,g in weights:
                    tot+=w
                if tot > 0:
                    for wg in weights:
                        wg[0]=wg[0]/float(tot)
                else:
                    zero_weight_count += 1                    
                    
                for weight,group in weights:
                    widx = len(ws)
                    ws.append("%g"%weight)
                    vs.append(str(group)) 
                    vs.append(str(widx)+" ")
                vs.append(" ")
                vcount.append(str(len(weights)))
                
            if zero_weight_count > 0:
               logging.warn(_("Found %d zero weighted vertices in %s"%(zero_weight_count, mesh.name)))
               
            if truncated_vcount > 10:
               logging.warn(_("Truncated %d more Vertices to a weight count of 4 in %s"%(truncated_vcount - 10, mesh.name)))
                
            subx(source, 'float_array', id=aid+"_"+mid+'-skin-weights-array',
                                        count=str(len(ws)),
                                        text = " ".join(ws))
            tech = subx(source, 'technique_common')
            accessor = subx(tech, 'accessor', 
                                source='#'+aid+'_'+mid+'-skin-weights-array',
                                stride='1',
                                count=str(len(ws)))
            subx(accessor, 'param', name='WEIGHT', type='float') 
            joints = subx(skin, 'joints')
            subx(joints, 'input', semantic='JOINT', source='#'+aid+'_'+mid+'-skin-joints')
            subx(joints, 'input', semantic='INV_BIND_MATRIX', 
                                source='#'+aid+'_'+mid+'-skin-bind_poses')
            vweights = subx(skin, 'vertex_weights', count=str(len(vcount)))
            subx(vweights, 'input', semantic='JOINT',
                                    source='#'+aid+'_'+mid+'-skin-joints',
                                    offset='0') 
            subx(vweights, 'input', semantic='WEIGHT',
                                    source='#'+aid+'_'+mid+'-skin-weights',
                                    offset='1') 
            subx(vweights, 'vcount', text=" ".join(vcount))
            subx(vweights, 'v', text=" ".join(vs))
            
            #

            #
            subx(node, 'translate', sid='location', text='0 0 0')   
            subx(node, 'rotate', sid='rotationZ', text='0 0 1 0')   
            subx(node, 'rotate', sid='rotationY', text='0 1 0 0')   
            subx(node, 'rotate', sid='rotationX', text='1 0 0 0')   
            subx(node, 'scale', sid='scale', text='1 1 1')   
   
            con = subx(node, 'instance_controller', url='#'+aid+'_'+mid+'-skin')   
            
            if arm in armatures:
                rootnames = arm_roots.get(arm.name,None)
                if rootnames:
                    for rootname in rootnames:
                        subx(con, 'skeleton', text= "#%s" % rootname) 
                else:
                    subx(con, 'skeleton', text='#mPelvis')

            else:

                subx(con, 'skeleton', text='#Origin') 
                
            if len(mesh.data.materials) > 0:
                bind = subx(con, "bind_material")
                tech = subx(bind, "technique_common")
                add_material_list(tech, mesh, len(uv_array) )

        else:

            loc = '%g %g %g'%tuple(mesh.location)
            subx(node, 'translate', sid='location', text=loc)

            if apply_mesh_rotscale:
                subx(node, 'rotate', sid='rotationZ', text='0 0 1 0')
                subx(node, 'rotate', sid='rotationY', text='0 1 0 0')
                subx(node, 'rotate', sid='rotationX', text='1 0 0 0')
                subx(node, 'scale', sid='scale', text='1 1 1')
            else:
                mat = ["%f %f %f %f"% (v[0], v[1], v[2], v[3]) for v in mesh.matrix_world]
                subx(node, 'matrix', sid='transform', text=" ".join(mat))

            con = subx(node, 'instance_geometry', url='#'+mid+'-mesh')   

            if len(mesh.data.materials) > 0:
                bind = subx(con, "bind_material")
                tech = subx(bind, "technique_common")
                add_material_list(tech, mesh, len(uv_array) )

        bpy.data.meshes.remove(mesh_data_copy)

    scene = subx(root, 'scene')
    subx(scene, 'instance_visual_scene', url='#Scene')

    indentxml(root)

    status = False
    try:
        xml.write(path, xml_declaration=True, encoding="utf-8")
        logging.info(_("Exported to: %s"), path)
        status = True
    except Exception as e:
        msg = _("The file %s could not be written to the specified location.|\n" \
              "This is the reported error: %s\n" \
              "Please check the file permissions and try again." % (path,e))
        logging.error(msg)
        raise util.Warning(msg)
    finally:
        util.progress_end()
        
    return status, len(enumerated_objects), complexity_warnings

def subx(parent, tag, **attrib):

    attrib2 = {}
    for key,value in attrib.items():
        if key!='text':
            attrib2[key]=value
    sub = et.SubElement(parent, tag, attrib=attrib2)
    if 'text' in attrib:
        sub.text = attrib['text']
    return sub    

def bonetoxml(arm, parent, bonename, applyScale, target_system, weight_maps, rigstates, sceneProps, is_root=False, with_joints=False):

    node          = parent #preset
    only_deform   = sceneProps.collada_only_deform
    only_weighted = sceneProps.collada_only_weighted
    with_roll     = sceneProps.collada_export_boneroll
    with_layers   = sceneProps.collada_export_layers
    use_blender   = sceneProps.collada_blender_profile
    with_rot      = sceneProps.collada_export_rotated
    jointtype     = 'POS'
    bones         = util.get_modify_bones(arm)

    roots = set()
    if not (target_system != 'BASIC' or bonename in SLALLBONES):
        print("bonetoxml: discard %s:%s (invalid name)" % (arm.name, bonename))
        return roots
        
    bone = bones.get(bonename, None)
    if bone == None:
        return roots

    fbonename = bonename
    if bone.use_deform or not only_deform:

        if bonename[0] == 'a':
            if sceneProps.accept_attachment_weights:
                fbonename = attachment_name(bonename)
            else:

                return roots

        if not weight_maps or bonename in weight_maps or util.has_head_offset(bone):
            if with_layers:
                layers = [str(e) for e,l in enumerate(bone.layers) if e < 31 and l]
                node = subx(parent, 'node', id=fbonename, name=fbonename, sid=fbonename, type='JOINT', layer=" ".join(layers))
            else:
                node = subx(parent, 'node', id=fbonename, name=fbonename, sid=fbonename, type='JOINT')

            if is_root:
                roots.add(bonename)
                is_root = False

            M, p, bone_type = rig.calculate_pivot_matrix(bpy.context, arm, bone, bones, with_rot, with_joints, jointtype=jointtype)
            mat = rig.matrixToStringArray(M, 6, p)

            subx(node, 'matrix', sid='transform', text=" ".join(mat))

            if use_blender: #export with blender profile
                extra = subx(node, 'extra')
                tech  = subx(extra, 'technique', profile='blender')

                layer = subx(tech, 'layer', text=" ".join(layers))

                conn = subx(tech, 'connect', text="1" if bone.use_connect else "0" )

                ebone = arm.data.edit_bones[bonename]
                if with_roll:
                    if ebone.roll != 0:
                        subx(tech, 'roll', text="%f"%ebone.roll)

                if True or not util.Skeleton.has_connected_children(bone):
                    tail = ebone.tail - ebone.head
                    if with_rot:

                        tail = [-tail[1], tail[0], tail[2]]

                    x = subx(tech, 'tip_x', text="%f"%tail[0])
                    y = subx(tech, 'tip_y', text="%f"%tail[1])
                    z = subx(tech, 'tip_z', text="%f"%tail[2])

            subset = rigstates.get(bone_type, None)
            if not subset:
                subset = {}
                rigstates[bone_type] = subset
            subset[bone.name] = M

    for b in bone.children:

        r = bonetoxml(arm, node, b.name, applyScale, target_system, weight_maps, rigstates,  sceneProps, is_root, with_joints)
        if len(r) > 0:
            roots |= r

    return roots

def indentxml(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indentxml(e, level+1)
            if not e.tail or not e.tail.strip():
                e.tail = i + "  "
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def create_bw_mask(obj, vgroup, mask_name):
    me         = obj.data
    polygons   = me.polygons
    vertices   = me.vertices
    groupIndex = obj.vertex_groups[vgroup].index
    
    try:

        vcol = me.vertex_colors[mask_name]
    except:
        vcol = me.vertex_colors.new(name=mask_name)
 
    for p in polygons:
        for index in p.loop_indices:
            v = vertices[me.loops[index].vertex_index]
            vcol.data[index].color=(0,0,0)
            for g in v.groups:
                if g.group == groupIndex:
                    vcol.data[index].color=(1,1,1)
                    break

    original_mode = obj.mode
    bpy.ops.object.editmode_toggle()
    bpy.ops.object.mode_set(mode=original_mode)