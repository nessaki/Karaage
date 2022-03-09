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


import bpy, bmesh, sys, logging
from bpy.props import *
from bpy.types import Menu, Operator
from bl_operators.presets import AddPresetBase

from bpy.app.handlers import persistent
from . import context_util, const, bind, create, data, mesh, rig, shape, util
from .const import *
from .context_util import *
from .util import PVector, get_blender_revision

CONST_NAMES_MAP = {}
CONST_NAMES_MAP['TrackTo']='Track To'

BONE_DATA_NAME   = 0 # "name"
BONE_DATA_HEAD   = 1 # "head"
BONE_DATA_TAIL   = 2 # "tail"
BONE_DATA_SELECT = 3 # "select"
BONE_DATA_DEFORM = 4 # "deform"
BONE_DATA_ROLL   = 5 # "roll"
BONE_DATA_MATRIX = 6 # "matrix"
BONE_DATA_PARENT = 7 # Parent name, or None if no parent
BONE_POSE_GROUP  = 8 # Name of associated bone group, or None if no group assigned to Bone
BONE_POSE_COLORSET   = 9 # Name of associated colorset, or None if no color set assigned to Bone group
BONE_DATA_CONNECT    = 10 # Bone Connect state
BONE_DATA_CONSTRAINT = 11 # Bone Constraint data [type,influence,mute]
BONE_DATA_IKLIMITS   = 12 # Bone IK Limits: bone.use_ik_limit_x/y/z

log=logging.getLogger("karaage.copyrig")

def is_animated_mesh(obj, src_armature):

    if obj.type != 'MESH': return False
    has_modifier=False
    for mod in [mod for mod in obj.modifiers if mod.type=='ARMATURE']:

        if mod.object == src_armature:

            return True

    return False

def get_joint_data(armobj):
    joint_data = [armobj.get('sl_joints'),
                  armobj.data.JointOffsetList
                 ]
    return joint_data

def copy_collection(toCollection, fromCollection):
    toCollection.clear()
    for elem in fromCollection:
        item = toCollection.add()
        for k, v in elem.items():
            item[k] = v

def set_joint_data(armobj, joint_data):
    sl_joints = joint_data[0]
    JointOffsetList = joint_data[1]
    
    if sl_joints:
        armobj['sl_joints'] = sl_joints
    if JointOffsetList:
        copy_collection(armobj.data.JointOffsetList, JointOffsetList)

def copy_karaage(self,
        context,
        rigtype,
        active_obj,
        src_armature,
        bone_repair,
        mesh_repair
        ):

    log.info("+=========================================================================")
    log.info("| copy: Starting a %s Karaage copy from \"%s\"" % (rigtype, src_armature.name))
    log.info("+=========================================================================")

    no_mesh = not mesh_repair
    jointType = src_armature.RigProps.JointType
    
    active_is_arm = active_obj == src_armature
    selected = [ob for ob in context.selected_objects]
    actsel = active_obj.select
    scene = context.scene
    scene.objects.active = src_armature
    util.ensure_mode_is('OBJECT')
    
    action = src_armature.animation_data.action
    shape_data = shape.asDictionary(src_armature, full=False)
    joint_data = get_joint_data(src_armature)

    if self.applyRotation:
        log.info("|  Apply Rot&Scale on [%s]" % scene.objects.active.name)
        log.info("|  copy: Apply Visual transforms, Rotation and Scale to %s" % src_armature.name)
        old_state = util.select_hierarchy(src_armature) # All of them!
        bpy.ops.object.visual_transform_apply() #To get around some oddities with the apply tool (possible blender bug?)
        try:
            bpy.ops.object.transform_apply(rotation=True, scale=True)
        except Exception as e:
            log.error("|! Can not apply Object transformations to linked objects (Ignoring)")

        util.restore_hierarchy(old_state)
        scene.update()

    util.ensure_mode_is("POSE")
    use_restpose = src_armature.data.pose_position
    src_armature.data.pose_position = 'POSE'
    bpy.ops.pose.select_all(action="SELECT")
    log.info("|  copy pose from %s to pose buffer" % (src_armature.name) )
    bpy.ops.pose.copy()
    src_armature.data.pose_position = 'REST'
    util.ensure_mode_is('OBJECT')

    log.info("+=========================================================================")
    self.copy_skeletons(context, src_armature, selected, self.targets, rigtype, transfer_joints=True, sync=False)
    log.info("+=========================================================================")

    if active_is_arm:
        active_obj = self.targets[0]

    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected:
        obj.select=True

    util.set_disable_update_slider_selector(True)

    tgt_armatures=[]

    for arm in self.targets:
        log.info("|  Post actions on armature [%s]" % (arm.name) )
        scene.objects.active = arm

        if arm.RigProps.rig_use_bind_pose != src_armature.RigProps.rig_use_bind_pose:
            log.info("| Set use bind pose to %s" % src_armature.RigProps.rig_use_bind_pose)
            arm.RigProps.rig_use_bind_pose = src_armature.RigProps.rig_use_bind_pose

        if shape_data:

            log.info("| transfer shape data to %s" % arm.name)
            shape.fromDictionary(arm, shape_data, update=False)

        set_joint_data(arm, joint_data)

        if self.transferMeshes:
            log.info("| Copy Meshes from [%s] to [%s]" % (src_armature.name, arm.name) )
            self.move_objects_to_target(context, self.sources, arm, self.srcRigType)  # copy from Karaage to Karaage

        if self.attachSliders:
            log.info("| Attach Sliders to Armature [%s]" % (arm.name) )
            arm.ObjectProp.slider_selector = 'SL'

        scene.objects.active = arm
        util.enforce_armature_update(context.scene,arm)
        tgt_armatures.append(arm)

    util.set_disable_update_slider_selector(False)
    scene.objects.active = active_obj
    active_obj.select   = actsel

    if action:
        active_obj.animation_data.action = action
        log.info("| Assigned Action %s to %s" % (action.name, active_obj.name) )

    log.info("+=========================================================================")
    util.ensure_mode_is(self.active_mode)
    return tgt_armatures

def convert_to_karaage(self,
        context,
        rigtype,
        active_obj,
        src_armature,
        inplace_transfer,
        bone_repair,
        mesh_repair,
        transfer_joints=True
        ):

    log.info("+=========================================================================")
    log.info("| convert: Starting a %s Karaage conversion from \"%s\"" % (rigtype, src_armature.name))
    log.info("+=========================================================================")

    no_mesh = not mesh_repair
    jointType = src_armature.RigProps.JointType
    
    active_is_arm = active_obj == src_armature
    selected = [ob for ob in context.selected_objects]
    actsel = active_obj.select
    scene = context.scene
    scene.objects.active = src_armature
    util.ensure_mode_is('OBJECT')
    action = src_armature.animation_data.action

    if inplace_transfer:
        if self.applyRotation:
            log.warning("convert_to_karaage: Apply Visual transforms, Rotation and Scale to %s" % src_armature.name)
            old_state = util.select_hierarchy(src_armature) # All of them!
            bpy.ops.object.visual_transform_apply() #To get around some oddities with the apply tool (possible blender bug?)

            try:
                bpy.ops.object.transform_apply(rotation=True, scale=True)
            except Exception as e:
                log.error("Can not apply Object transformations to linked objects (Ignoring)")

            util.restore_hierarchy(old_state)
            bpy.context.scene.update()

        util.ensure_mode_is("POSE")
        use_restpose = src_armature.data.pose_position
        src_armature.data.pose_position = 'POSE'
        bpy.ops.pose.select_all(action="SELECT")
        bpy.ops.pose.copy()
        log.warning("copyrig-convert-karaage: copy pose from %s to pose buffer" % (src_armature.name) )
        src_armature.data.pose_position = 'REST'
        util.ensure_mode_is('OBJECT')

        tgt_armature = create.createAvatar(context, quads=True, use_restpose=use_restpose, rigType=rigtype, jointType=jointType, no_mesh=no_mesh)
        tgt_armature.ShapeDrivers.male_80 = self.is_male
        self.targets.append(tgt_armature)

    self.copy_skeletons(context, src_armature, selected, self.targets, rigtype, transfer_joints, sync=False)
    if active_is_arm:
        active_obj = self.targets[0]

    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected:
        obj.select=True

    is_fitted=False
    util.set_disable_update_slider_selector(True)

    for arm in self.targets:
        log.debug("3:target_armature has %d bones" % len(arm.data.bones))
        scene.objects.active = arm
        if self.sl_bone_rolls:
            rig.restore_source_bone_rolls(arm)
        arm.RigProps.rig_use_bind_pose = util.use_sliders(context) and src_armature.RigProps.rig_use_bind_pose

        self.move_objects_to_target(context, self.sources, arm, self.srcRigType) # Convert to karaage

        if self.attachSliders:

            arm.ObjectProp.slider_selector = 'SL'

        for child in util.get_animated_meshes(context, arm, with_karaage=False):

            if self.attachSliders:

                scene.objects.active             = child
                child.ObjectProp.slider_selector = 'SL'
            if not is_fitted:
                for key in child.vertex_groups.keys():
                    if key in data.get_volume_bones():
                        is_fitted = True
                        arm.select=True
                        scene.objects.active = arm
                        bpy.ops.karaage.armature_deform_enable(set='VOL')
                        break

        if not inplace_transfer:
            scene.objects.active = arm

            bpy.ops.karaage.apply_shape_sliders()

            util.enforce_armature_update(context.scene,arm)

    util.set_disable_update_slider_selector(False)
    scene.objects.active = active_obj
    active_obj.select   = actsel
    if action:
        active_obj.animation_data.action = action
        log.warning("copyrig-convert-karaage: Assigned Action %s to %s" % (action.name, active_obj.name) )

    util.ensure_mode_is('POSE')
    bpy.ops.pose.select_all(action="SELECT")
    src_armature.data.pose_position = 'POSE'
    bpy.ops.pose.paste()  
    log.warning("copyrig-convert-karaage: paste pose from pose buffer to %s" % (active_obj.name) )

    util.ensure_mode_is(self.active_mode)
    return active_obj

def update_karaage(self,
        context,
        rigtype,
        active_obj,
        src_armature,
        bone_repair,
        mesh_repair,
        transfer_joints=True
        ):
        
    oselection = util.remember_selected_objects(context)
    armature_name = src_armature.name
    log.info("+========================================================================")
    log.info("| update: Starting a %s Rig Update of \"%s\"" % (rigtype, armature_name))
    log.info("+========================================================================")

    no_mesh = not mesh_repair
    jointType = src_armature.RigProps.JointType
    
    active_is_arm = active_obj == src_armature
    selected = [ob for ob in context.selected_objects]
    actsel = active_obj.select
    scene = context.scene
    scene.objects.active = src_armature
    util.ensure_mode_is('OBJECT')
    if not src_armature.animation_data:
        src_armature.animation_data_create()
    action = src_armature.animation_data.action

    shape_data = shape.asDictionary(src_armature, full=False)

    if self.applyRotation:
        log.warning("Apply Rot&Scale on [%s]" % scene.objects.active.name)
        log.info("update_karaage: Apply Visual transforms, Rotation and Scale to %s" % src_armature.name)
        old_state = util.select_hierarchy(src_armature) # All of them!
        bpy.ops.object.visual_transform_apply() #To get around some oddities with the apply tool (possible blender bug?)
        try:
            bpy.ops.object.transform_apply(rotation=True, scale=True)
        except Exception as e:
            log.error("Can not apply Object transformations to linked objects (Ignoring)")

        util.restore_hierarchy(old_state)
        scene.update()

    util.ensure_mode_is("POSE")
    use_restpose = src_armature.data.pose_position
    src_armature.data.pose_position = 'POSE'
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.copy()
    log.info("update: copy pose from %s to pose buffer" % (src_armature.name) )
    src_armature.data.pose_position = 'REST'
    util.ensure_mode_is('OBJECT')
    tgt_armature = create.createAvatar(context, quads=True, use_restpose=False, rigType=rigtype, jointType=jointType, no_mesh=no_mesh)

    ofreeze = tgt_armature.ShapeDrivers.Freeze
    tgt_armature.ShapeDrivers.Freeze = True
    tgt_armature.ShapeDrivers.male_80 = self.is_male
    tgt_armature.ShapeDrivers.Freeze = ofreeze
    
    self.targets.append(tgt_armature)
    if shape_data:

        shape.fromDictionary(tgt_armature, shape_data, update=True)
    self.copy_skeletons(context, src_armature, selected, [tgt_armature], rigtype, transfer_joints, sync=False)
    
    src_armature.name = 'del_' + armature_name
    tgt_armature.name = armature_name

    util.ensure_mode_is('OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected:
        obj.select=True

    scene.objects.active = tgt_armature

    is_fitted=False
    util.set_disable_update_slider_selector(True)
    log.debug("update: target_armature has %d bones" % len(tgt_armature.data.bones))

    arm = tgt_armature
    if True:
        scene.objects.active = arm
        if self.sl_bone_rolls:
            rig.restore_source_bone_rolls(arm)
        
        use_bind_pose = util.use_sliders(context) and src_armature.RigProps.rig_use_bind_pose
        if arm.RigProps.rig_use_bind_pose != use_bind_pose:
            arm.RigProps.rig_use_bind_pose = use_bind_pose

        arm.show_x_ray = src_armature.show_x_ray
        arm.data.show_bone_custom_shapes = src_armature.data.show_bone_custom_shapes

        self.move_objects_to_target(context, self.sources, arm, self.srcRigType) # update karaage

        if self.attachSliders:

            arm.ObjectProp.slider_selector = 'SL'

            shape.destroy_shape_info(context, arm)

        log.info("update: Checking Custom meshes of %s" % arm.name)

        for child in util.get_animated_meshes(context, arm, with_karaage=False):
            log.info("update: Checking Mesh %s" % child.name)

            if not is_fitted:
                for key in child.vertex_groups.keys():
                    if key in data.get_volume_bones():
                        is_fitted = True
                        arm.select=True
                        scene.objects.active = arm
                        bpy.ops.karaage.armature_deform_enable(set='VOL')
                        break

    util.set_disable_update_slider_selector(False)
    scene.objects.active = tgt_armature

    tgt_armature.select   = actsel
    if action:
        tgt_armature.animation_data.action = action
        log.info("update: Assigned Action %s to %s" % (action.name, tgt_armature.name) )

    if self.apply_pose and self.sources:

        util.parent_selection(context, tgt_armature, self.sources, keep_transform=True)
    
    util.restore_selected_objects(context, oselection)
    util.ensure_mode_is('POSE')
  
    bpy.ops.pose.select_all(action="SELECT")
    tgt_armature.data.pose_position = 'POSE'
    bpy.ops.pose.paste()  
    log.info("update: paste pose from pose buffer to %s" % (tgt_armature.name) )
    if not active_is_arm:
        scene.objects.active = active_obj
        active_obj.select = actsel
        util.ensure_mode_is(self.active_mode)
    return tgt_armature

def convert_sl(self,
        context,
        rigtype,
        active_obj,
        src_armature,
        inplace_transfer,
        bone_repair,
        mesh_repair,
        transfer_joints=True
        ):

    log.info("=========================================================================")
    if inplace_transfer:
        log.info("convert: Starting an %s Inplace Rig Migration of '%s'" % (rigtype, src_armature.name))
    else:
        log.info("convert: Starting a %s Rig Transfer Copy from '%s'" % (rigtype, src_armature.name))
    log.info("=========================================================================")

    active_is_arm = active_obj == src_armature

    selected = [ob for ob in context.selected_objects]

    updateRigProp = self #context.scene.UpdateRigProp
    scene  = context.scene
    scene.objects.active = src_armature
    ob = scene.objects.active

    no_mesh = self.srcRigType == MANUELMAP
    jointType = src_armature.RigProps.JointType

    actsel      = active_obj.select

    omode = util.ensure_mode_is("OBJECT", object=src_armature)

    if inplace_transfer:
        selected_source_bones = [b.name for b in src_armature.data.bones if b.select]
        if self.applyRotation:

            scene.objects.active = src_armature
            old_state = util.select_hierarchy(src_armature) # All of them!
            log.warning("convert_sl: Apply Visual transforms, Rotation and Scale to %s" % src_armature.name)
            bpy.ops.object.visual_transform_apply() #To get around some oddities with the apply tool (possible blender bug?)
            bpy.ops.object.transform_apply(rotation=True, scale=True)
            util.restore_hierarchy(old_state)
            scene.update()

        use_restpose = (self.attachSliders)
        tgt_armature = create.createAvatar(context, quads=True, use_restpose=use_restpose, rigType=rigtype, jointType=jointType, no_mesh=no_mesh)

        tgt_armature.ShapeDrivers.male_80 = self.is_male

        shape.updateShape(None, context, target="", scene=context.scene, refresh=True, msg="convert inplace")

        self.targets.append(tgt_armature)

    if not inplace_transfer:
        for arm in self.targets:
            scene.objects.active = arm
            bpy.ops.karaage.store_bind_data()

    self.copy_skeletons(context, src_armature, selected, self.targets, self.srcRigType, transfer_joints, sync=True)
    if active_is_arm:
        active_obj = self.targets[0]

    util.ensure_mode_is('OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected:
        obj.select=True

    is_fitted=False
    util.set_disable_update_slider_selector(True)

    for arm in self.targets:
        scene.objects.active = arm
        if self.sl_bone_rolls:
            rig.restore_source_bone_rolls(arm)
        arm.RigProps.rig_use_bind_pose = util.use_sliders(context) and src_armature.RigProps.rig_use_bind_pose
        self.move_objects_to_target(context, self.sources, arm, self.srcRigType) # convert SL

        if self.attachSliders:

            arm.ObjectProp.slider_selector = 'SL'

        for child in util.get_animated_meshes(context, arm, with_karaage=False):

            if self.attachSliders:

                scene.objects.active             = child
                child.ObjectProp.slider_selector = 'SL'
            if not is_fitted:
                for key in child.vertex_groups.keys():
                    if key in data.get_volume_bones():
                        is_fitted = True
                        arm.select=True
                        scene.objects.active = arm
                        bpy.ops.karaage.armature_deform_enable(set='VOL')
                        break

        if not inplace_transfer:
            scene.objects.active = arm

            bpy.ops.karaage.apply_shape_sliders()

            util.enforce_armature_update(context.scene,arm)

            bpy.ops.karaage.alter_to_restpose()

    util.set_disable_update_slider_selector(False)
    scene.objects.active = active_obj
    active_obj.select   = actsel
    util.ensure_mode_is(self.active_mode)
    return active_obj

def print_on_bone_tail_change(bone, msg=''):
    if '_bt' in bone:
        bt = Vector(bone['_bt'])
        t = Vector(bone.tail)
        has_changed = t != bt
    else:
        has_changed = True
    if has_changed:
        print("%s: %s head is now %s" % (msg, bone.name, bone.head) )
        print("%s: %s tail is now %s" % (msg, bone.name, bone.tail) )
        bone['_bt'] = bone.tail

def get_avatar_mesh_container(scene, armobj, msg=""):
    for c in armobj.children:
        if c.type == 'Empty' and '_meshes' in c.name:
            log.info("%sFound mesh container %s" % (msg, c.name) )
            return c

    log.warning("%sGenerate missing Mesh container for %s" % (msg, armobj.name) )
    c = create.add_container(scene, armobj, armobj.name + '_meshes')
    return c
        
class ButtonCopyKaraage(bpy.types.Operator):
    '''
    Convert/Update/Cleanup Rigs
    '''
    bl_idname = "karaage.copy_rig"
    bl_label  = "Copy Rig"
    bl_description = '''Convert/Update/Cleanup Rigs

- Single Rig: convert/Update to Karaage
- Multiple Rigs: Copy active to selected
- If rig is up to date: fix Missing bones,
  synchronize Control rig to Deform Rig,
  Align pole angles, ...'''

    transferMeshes = BoolProperty(default=False, name="Transfer Meshes",
        description="Migrate Child Meshes from Source armature to target Armature")

    transferJoints = BoolProperty(
        name = "Transfer Joints",
        default=True,
        description = \
'''Migrate Joint positions from Source armature to target Armature
and calculate the joint offsets for the Rig.

Note:
The current slider settings and the current Skeleton both are taken 
into account. You may optionally want to set the sliders to SL Restpose 
(white stickman icon in appearance panel) to get reproducible results.''',
    )

    attachSliders = BoolProperty(default=True, name="Attach Sliders",
        description="Attach the Appearance Sliders after binding")

    applyRotation = BoolProperty(default=True, name="Apply Rot&Scale",
        description="Apply Rotation before converting (use if Rig contains meshes with inconsistent rotations and scales)")

    is_male = BoolProperty(default=False, name="Male",
        description="Use the Male skeleton for binding")

    srcRigType = EnumProperty(
        items=(
            (SLMAP,      SLMAP,      'Second Life Base Rig\n\nWe assume the character looks towards positive X\nwhich means it looks to the right side when in front view'),
            (MANUELMAP,  MANUELMAP,  'Manuel Bastioni Rig\n\nWe assume the character has been imported directly from Manuellab and has not changed.'),
            (GENERICMAP, GENERICMAP, 'Generic Rig\n\nWe assume the character looks towards negative Y\nwhich means it looks at you when in Front view'),
            (KARAAGEMAP, KARAAGEMAP, 'Karaage Rig\n\nThe character is already rigged to an Karaage Rig\nNote: Do not use this option unless you have been instructed to set it'),
        ),
        name="Source Rig",
        description="Rig Type of the active Object, can be KARAAGE, MANUELLAB, SL or Generic",
        default='SL')

    tgtRigType = EnumProperty(
        items=(
            ('BASIC',       'Basic', 'Second Life Base Rig\n\nWe only create the 26 legacy bones, the volume bones and the attachment bones, all for the old fashioned "classic" Rig'),
            ('EXTENDED', 'Extended', 'Second Life Extended Rig\n\nCreate a rig compatibvle to the new SL boneset (Bento)')
        ),
        name="Target Rig",
        description="Rig Type of the target Object\n\nBasic: 26 Bones + 26 Volume bones (the classic SL rig)\nExtended: The full Boneset of the new SL Bento Rig",
        default='EXTENDED')

    adjust_origin = EnumProperty(
        items=(
            ('ROOT_TO_ORIGIN',   'Armature', UpdateRigProp_adjust_origin_armature),
            ('ORIGIN_TO_ROOT',   'Rootbone', UpdateRigProp_adjust_origin_rootbone)
        ),
        name="Origin",
        description=UpdateRigProp_adjust_origin,
        default='ROOT_TO_ORIGIN'
    )

    bone_repair     = BoolProperty(
        name        = "Rebuild missing Bones",
        description = UpdateRigProp_bone_repair_description,
        default     = True
    )
    
    adjust_pelvis   = BoolProperty(
        name        = "Adjust Pelvis",
        description = UpdateRigProp_adjust_pelvis_description,
        default     = True
    )
    adjust_rig   = BoolProperty(
        name        = "Synchronize Rig",
        description = UpdateRigProp_adjust_rig_description,
        default     = True
    )
    mesh_repair     = BoolProperty(
        name        = "Rebuild Karaage Meshes",
        description = "Reconstruct all missing Karaage Meshes.\nThis applies when Karaage meshes have been removed from the original rig\n\nCAUTION: If your character has modified joints then the regenerated Karaage meshes may become distorted!",
        default     = False
    )
    
    show_offsets      = BoolProperty(
        name="Show Offsets",
        description = "Draw the offset vectors by using the Grease pencil.\nThe line colors are derived from the related Karaage Bone group colors\nThis option is only good for testing when something goes wrong during the conversion",
        default     = False
    )
    sl_bone_ends = BoolProperty(
        name="Enforce SL Bone ends",
        description = "Ensure that the bone ends are defined according to the SL Skeleton Specification\nYou probably need this when you import a Collada devkit\nbecause Collada does not maintain Bone ends (tricky thing)\n\nHint: \nDisable this option\n- when you transfer a non human character\n- or when you know you want to use Joint Positions",
        default     = True
    )

    sl_bone_rolls = const.sl_bone_rolls
    align_to_deform = EnumProperty(
        items=(
            ('DEFORM_TO_ANIMATION',   'Pelvis', 'Move mPelvis to Pelvis'),
            ('ANIMATION_TO_DEFORM',   'mPelvis', 'Move Pelvis to mPelvis')
        ),
        name="Align to",
        description = UpdateRigProp_align_to_deform_description,
        default='ANIMATION_TO_DEFORM'
    )
    align_to_rig = EnumProperty(
        items=(
            ('DEFORM_TO_ANIMATION',   'Green Animation Rig', 'Move Deform Bones to Animation Bone locations'),
            ('ANIMATION_TO_DEFORM',   'Blue Deform Rig', 'Move Animation Bones to Deform Bone Locations')
        ),
        name="Align to",
        description = UpdateRigProp_align_to_rig_description,
        default='ANIMATION_TO_DEFORM'
    )
    
    snap_collision_volumes = BoolProperty(
        name        = "Snap Volume Bones",
        description = UpdateRigProp_snap_collision_volumes_description,
        default     = True
    )
    snap_attachment_points = BoolProperty(
        name        = "Snap Attachment Bones",
        description = UpdateRigProp_snap_attachment_points_description,
        default     = True
    )

    apply_pose = BoolProperty(
        name="Apply Pose",
        default=True, 
        description="Apply pose of source rig to character mesh(es) before Transfering the rig.\n\nYou want to enable this option only if you\nintend to use the current pose as the new restpose.\nIn that case joint offsets will be generated as well!"
        )

    handleTargetMeshSelection = EnumProperty(
        items=(
            ('KEEP',   'Keep', 'Keep Karaage Meshes in Target Armature(s)'),
            ('HIDE',   'Hide', 'Hide Karaage meshes in Target Armature(s)'),
            ('DELETE', 'Delete', 'Delete Karaage Meshes from Target Armature(s)')),
        name="Original",
        description="How to treat the Karaage Meshes in the Target Armature(s)",
        default='KEEP')

    inplace_transfer = False
    src_armature     = None
    selected         = None
    targets          = None
    active           = None
    active_mode      = None
    sources          = None
    use_all_sources  = False

    def draw(self, context):
        if self.inplace_transfer == False or self.srcRigType != 'KARAAGE':
            ButtonCopyKaraage.draw_generic(self, context, self.layout, self.src_armature, self.targets)

    @staticmethod
    def sliders_allowed(context):
        scene = context.scene
        with_sliders = scene.SceneProp.panel_appearance_enabled and util.use_sliders(context)
        return with_sliders

    @staticmethod
    def draw_generic(op, context, layout, src_armature, targets, repair=False):
        scene = context.scene
        all_mesh = util.get_animated_meshes(context, src_armature, with_karaage=True, only_selected=False, return_names=False)
        custom_mesh = util.get_animated_meshes(context, src_armature, with_karaage=False, only_selected=False, return_names=False)
        all_count = len(all_mesh)
        custom_count = len(custom_mesh)
        system_count = len(all_mesh) - len(custom_mesh)
        joint_count = rig.get_joint_offset_count(src_armature)
        
        if op:
            updateRigProp = op
        else:
            updateRigProp = scene.UpdateRigProp

        if "karaage"  in src_armature:
            title = "Update Tool"
            srcRigType = 'KARAAGE'
            need_pelvis_fix = rig.needPelvisInvFix(src_armature)
            need_rig_fix = rig.needRigFix(src_armature)
        else:
            title = "Transfer Tool"
            need_pelvis_fix = need_rig_fix = False
            srcRigType = updateRigProp.srcRigType
            create_transfer_preset(layout)
            
        box   = layout.box()
        box.label(text=title)
        
        if not context.active_object or context.active_object.type != 'ARMATURE':
            box.label("Only for Armatures",icon='INFO')
            return
            
        row = box.row(align=True)
        row.prop(src_armature.data,"pose_position", expand=True)
        box.separator()
        
        armobj = context.active_object
        col = box.column(align=True)
        if 'karaage' in armobj:
            col.label("Source Rig: KARAAGE")
        else:
            col.prop(updateRigProp, "srcRigType")

        if srcRigType =='KARAAGE' and not 'karaage' in armobj:
            col   = box.column(align=True)
            col.label("Source rig is not Karaage",icon='ERROR')
            col.label("You Reimport an Karaage?", icon='BLANK1')
            col.label("Then use Source Rig: SL", icon='BLANK1')
            return
        
        if len(targets) == 0:

            col.prop(updateRigProp, "tgtRigType")
            col   = box.column()

        if op or len(targets) > 0 or srcRigType!='KARAAGE':
        
            if True:#len(targets) == 0:

                split = col.split(percentage=0.52)
                split.label("Dummies:")
                split.prop(updateRigProp, "handleTargetMeshSelection", text="", toggle=False)
                col  = box.column()

            if srcRigType == 'KARAAGE':
                col.prop(updateRigProp, "transferMeshes")
            else:
                ibox = col.box()
                bcol = ibox.column(align=True)
                brow = bcol.row(align=True)
                brow.prop(updateRigProp, "transferJoints", text="with Joints")
                brow.prop(src_armature.RigProps, "JointType", text="")

                bcol = ibox.column(align=True)
                if ButtonCopyKaraage.sliders_allowed(context):
                    bcol.prop(src_armature.RigProps,"rig_use_bind_pose")
                bcol.prop(updateRigProp, "sl_bone_ends")
                bcol.prop(updateRigProp, "sl_bone_rolls")
                bcol.enabled = updateRigProp.transferJoints
                
                if util.get_ui_level() > UI_ADVANCED:
                    bcol = ibox.column(align=True)
                    bcol.prop(updateRigProp, "show_offsets")
                    bcol.enabled = get_blender_revision() > 277000

                col = col.column(align=True)
                
                if ButtonCopyKaraage.sliders_allowed(context):
                    col.prop(updateRigProp, "attachSliders")
                col.prop(updateRigProp, "applyRotation")
                col.prop(updateRigProp, "is_male")

        if not op:
            nicon = None
            note = None
            if len(targets) == 0:
                if "karaage" in src_armature:
                    karaage_version, rig_version, rig_id, rig_type = util.get_version_info(src_armature)

                    if repair:
                        label = "Cleanup Rig"
                        nicon = 'INFO'
                    else:
                        label = "Update Rig"
                        nicon = 'ERROR'

                    if rig_version != None:
                        note = "%s %s(%s)" %("Rig Version " if repair else "Outdated Rig", rig_version, rig_id, )
                    else:
                        note = None

                    bones  = util.get_modify_bones(src_armature)
                    origin = bones.get("Origin")

                    if origin and Vector(origin.head).magnitude > MIN_JOINT_OFFSET:
                        col.alert=True

                        col.prop(updateRigProp, "adjust_origin", expand=False )

                    abox = None
                    if need_pelvis_fix:
                        abox = box.box()
                        abox.label("Alignment Options", icon='ALIGN')
                        col = abox.column(align=True)
                        col.alert = not updateRigProp.adjust_pelvis
                        icon = 'CHECKBOX_HLT' if updateRigProp.adjust_pelvis else 'CHECKBOX_DEHLT'
                        row = col.row(align=True)

                        row.alert = not updateRigProp.adjust_pelvis #mark red if adjustment is disabled
                        row.prop(updateRigProp, "adjust_pelvis",text="COG Align to", icon = icon)
                        row.prop(updateRigProp, "align_to_deform", text='')
                    if need_rig_fix:
                        if not abox:
                            abox = box.box()
                            abox.label("Alignment Options", icon='ALIGN')
                        col = abox.column(align=True)
                        col.alert = not updateRigProp.adjust_rig
                        icon = 'CHECKBOX_HLT' if updateRigProp.adjust_rig else 'CHECKBOX_DEHLT'
                        row = col.row(align=True)

                        row.prop(updateRigProp, "adjust_rig",text="Rig Align to", icon = icon)
                        row.prop(updateRigProp, "align_to_rig", text='')
                        if util.get_ui_level() > UI_ADVANCED:
                            col.prop(updateRigProp, "snap_collision_volumes")
                            col.prop(updateRigProp, "snap_attachment_points")

                    if abox:
                        col  = box.column()

                    col.alert=False                    
                    col.separator()
                    col.prop(updateRigProp, "sl_bone_rolls")
                    if ButtonCopyKaraage.sliders_allowed(context):
                        col.prop(updateRigProp, "attachSliders")
                    col.prop(updateRigProp, "applyRotation")
                    col.prop(updateRigProp, "bone_repair")
                    col.prop(updateRigProp, "mesh_repair")

                    if ButtonCopyKaraage.sliders_allowed(context):
                        if joint_count == 0:
                            text = "Check for Joint edits"
                        else:
                            text = "Keep Joint Edits"

                        col = box.column(align=True)
                        col.prop(updateRigProp, "transferJoints", text=text)

                        col = box.column(align=True)
                        if updateRigProp.transferJoints:
                            row=col.row(align=True)
                            row.label(text='',icon='BLANK1')
                            row.prop(src_armature.RigProps, "generate_joint_ik")
                            row=col.row(align=True)
                            row.label(text='',icon='BLANK1')
                            row.prop(src_armature.RigProps, "generate_joint_tails")
                        
                        if util.get_ui_level() > UI_ADVANCED:
                            col = box.column(align=True)
                            col.prop(updateRigProp, "show_offsets")
                            col.enabled = get_blender_revision() > 277000

                else:
                    label = "Convert to Karaage Rig"
            else:
                if ButtonCopyKaraage.sliders_allowed(context):
                    col.prop(updateRigProp, "attachSliders")
                col.prop(updateRigProp, "applyRotation")
                label="Copy to Karaage Rig"

            col = box.column(align=True)
            row = col.row(align=True)

            props = row.operator(ButtonCopyKaraage.bl_idname, text=label)
            row.prop(updateRigProp,"apply_pose", icon='FREEZE', text='')

            if "karaage" in src_armature:
                pass
            else:
                props.srcRigType    = updateRigProp.srcRigType

            props.tgtRigType    = updateRigProp.tgtRigType
            props.apply_pose    = updateRigProp.apply_pose
            props.adjust_origin = updateRigProp.adjust_origin
            props.bone_repair   = updateRigProp.bone_repair
            props.mesh_repair   = updateRigProp.mesh_repair
            props.show_offsets  = updateRigProp.show_offsets if get_blender_revision() > 277000 else False
            props.sl_bone_ends  = updateRigProp.sl_bone_ends
            props.sl_bone_rolls = updateRigProp.sl_bone_rolls
            
            if util.is_linked_hierarchy([src_armature]) or util.is_linked_hierarchy(all_mesh):
                row.enabled = False
                col = box.column(align=True)
                col.label("Linked parts", icon='ERROR')

            if note:
                col = box.column(align=True)
                col.label(note, icon=nicon)
                
            col = box.column(align=True)
            if len(targets) > 0:

                def list_arm(context, arm, col):
                    if arm == context.object:
                        icon = 'OUTLINER_OB_ARMATURE'
                        text = "Source: %s " % arm.name
                    else:
                        icon = 'ARMATURE_DATA'
                        text = "Target: %s" % arm.name
                    col.label (text, icon=icon)

                list_arm(context, src_armature, col)
                for arm in targets:
                    list_arm(context, arm, col)

            col.label ("Custom mesh  : %d" % custom_count, icon='BLANK1')
            col.label ("System mesh  : %d" % system_count, icon='BLANK1')
            col.label ("Joint offsets: %d" % joint_count, icon='BLANK1')

    def roll_neutral_rotate(self, context, arm, rot, srot):
            print("Transfer(sl): Rotate Armature: [%s] %s (preserving boneroll)" % (arm.name, srot))

            arm.matrix_world *= rot
            bpy.ops.object.select_all(action='DESELECT')
            arm.select=True
            bpy.ops.object.transform_apply(rotation=True)

            util.ensure_mode_is("OBJECT")
            context.scene.update()

    def rig_rotate(self, context, arm, rot, srot):
            log.debug("Transfer(sl): Rotate Armature: [%s] %s " % (arm.name, srot))

            arm.matrix_world *= rot
            bpy.ops.object.select_all(action='DESELECT')
            arm.select=True
            bpy.ops.object.transform_apply(rotation=True)

    def freeze_armature(self, context, armobj):
        log.debug("Transfer(sl): Freeze bound meshes to current pose (%s)" % armobj.name)
        objs = util.get_animated_meshes(context, armobj)
        log.info("| Freezing %d animated meshes" % len(objs))
        objs = mesh.unparent_armature(context, self, objs, freeze=True)
        if objs:
            log.info("| Unparented %d animated meshes" % len(objs))
        else:
            log.info("| No meshes selected for Unparent")
        log.info("| Apply Source armature pose as new restpose (%s)" % armobj.name)
        context.scene.objects.active = armobj
        omode = util.ensure_mode_is("POSE")
        bpy.ops.pose.armature_apply()
        util.ensure_mode_is(omode)
        return objs

    def extract_bone_data(self, context, armature, armature_type):
        log.debug("Transfer(sl): Extract Source bone data")
        bone_store = []
        context.scene.objects.active = armature
        src_mode = util.ensure_mode_is("OBJECT")

        if self.transferJoints and armature_type == SLMAP:
            roll_neutral_rotate(armature, Rz90)

        util.ensure_mode_is("POSE")

        bone_names = util.Skeleton.bones_in_hierarchical_order(armature)
        pbones = armature.pose.bones
        for name in bone_names:

            pbone = pbones[name]
            constraints = [[c.type,c.influence,c.mute] for c in pbone.constraints]
            iklimits = [ pbone.use_ik_limit_x, pbone.use_ik_limit_y, pbone.use_ik_limit_z ]
            use_deform = pbone.bone.use_deform

            bone_store.append([
                name,
                pbone.head,
                pbone.tail,
                pbone.bone.select,
                use_deform,
                0,#ebone.roll (should be in the matrix, see below)
                pbone.matrix,
                pbone.parent.name if pbone.parent else None,
                pbone.bone_group.name if pbone.bone_group else None,
                pbone.bone_group.color_set if pbone.bone_group else None,
                pbone.bone.use_connect,
                constraints,
                iklimits
                ]
            )

        return bone_store

    def copy_skeletons(self, context, src_armature, selected, target_armatures, armature_type, transfer_joints=True, sync=True):

        log.info("| Transfer from %s armature [%s] to %d target armatures" 
              % (src_armature.RigProps.RigType, src_armature.name,len(target_armatures)))

        for tgt_armature in target_armatures:
            if self.handleTargetMeshSelection in ["HIDE","DELETE"]:
                self.prepare_karaage_meshes(context, tgt_armature)
            self.copy_skeleton(context, src_armature, selected, tgt_armature, armature_type, transfer_joints, sync)

    def prepare_karaage_meshes(self, context, tgt_armature):
        if self.handleTargetMeshSelection =='DELETE':
            log.info("| Delete children from [%s]" % (tgt_armature.name) )
            util.remove_children(tgt_armature, context)
        else:
            log.info("| Hide children in %s" % (tgt_armature.name) )
            for obj in util.getChildren(tgt_armature, type=None, visible=True):
                obj.hide=True

    def cleanup_slider_info(self, context, subset, tgt_armature):
        log.warning("cleanup_slider_info: process %d objects" % (len(subset)) )
        scene = context.scene
        arms = [tgt_armature]
        objs = []
        for obj in subset:
            if not obj.data.shape_keys:
                log.warning("Object %s has no shape keys" % (obj.name) )
                continue

            keyblocks = obj.data.shape_keys.key_blocks
            if len(keyblocks) == 0:
                log.warning("Object %s has no key_blocks" % (obj.name) )
                continue

            if 'neutral_shape' in keyblocks or \
               'bone_morph' in keyblocks:
                objs.append(obj)

        if len(objs) > 0:
            log.warning("Apply Sliders to %d Custom objects" % (len(objs)) )
            mesh.ButtonApplyShapeSliders.exec_imp(context, arms, objs)
    
    def move_objects_to_target(self, context, sources, tgt_armature, armature_type):
        scene = context.scene
        custom_set = [s for s in sources if 'karaage-mesh' not in s] if sources else []
        system_set = [s for s in sources if 'karaage-mesh' in s] if sources else []
        if len(custom_set) > 0:
            log.info("|  Move %d Custom meshes to %s %s" % (len(custom_set), tgt_armature.type, tgt_armature.name) )
            self.move_subset_to_target(context, custom_set, tgt_armature, armature_type, tgt_armature)
            self.cleanup_slider_info(context, custom_set, tgt_armature)

        if len(system_set) > 0:
            container = get_avatar_mesh_container(scene, tgt_armature)
            log.info("|  Move %d Karaage meshes to %s %s" % (len(system_set), tgt_armature.type, container.name) )

            chide = container.hide 
            cselect = container.select
            chselect = container.hide_select
            chrender = container.hide_render

            container.hide        = False
            container.select      = False
            container.hide_select = False
            container.hide_render = False           

            self.move_subset_to_target(context, system_set, tgt_armature, armature_type, container)

            container.hide        = chide
            container.select      = cselect
            container.hide_select = chselect
            container.hide_render = chrender           

    def move_subset_to_target(self, context, sources, tgt_armature, armature_type, parent):
        with set_context(context, tgt_armature, 'OBJECT'):
            
            scene = context.scene
            curloc = scene.cursor_location.copy()
            scene.cursor_location = tgt_armature.location

            log.info("|  Move %d Objects to %s %s" % (len(sources), armature_type, parent.name) )

            bpy.ops.object.select_all(action='DESELECT')
            select_states = util.get_select_and_hide(sources, select=False, hide_select=False, hide=False)

            newsources = []
            for object in sources:
                obj = object

                oparent = obj.parent
                if not self.inplace_transfer:
                    log.info("|- Copy Source [%s]" % (obj.name) )

                    dupobj = obj.copy()
                    dupobj.data = obj.data.copy()

                    scene.objects.link(dupobj)
                    obj = dupobj

                    for mod in [mod for mod in dupobj.modifiers if mod.type=='ARMATURE']:
                        mod.object=tgt_armature

                scene.objects.active = obj
                obj.select = True
                hidden = obj.hide
                obj.hide = False
                
                if oparent:
                    OMWI = oparent.matrix_world.inverted()
                    obj.matrix_world = OMWI * obj.matrix_world * tgt_armature.matrix_world
                    newsources.append(obj)
                    loc = obj.location
                    log.info("|- Parenting object %s to %s at %s" % (obj.name, parent.name, loc) )
                
                bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                obj.hide = hidden

                if armature_type == MANUELMAP:
                    log.info("|- (manuel) Converting Weight Groups...")
                    rig.convert_weight_groups(tgt_armature, obj, armature_type=MANUELMAP)
                if self.apply_pose:
                    mod = obj.modifiers.new("Armature", "ARMATURE")
                    mod.use_bone_envelopes         = False
                    mod.use_vertex_groups          = True
                    mod.use_deform_preserve_volume = False
                    mod.object                     = tgt_armature
                else:
                    for mod in [mod for mod in obj.modifiers if mod.type=='ARMATURE']:
                        mod.object = tgt_armature
                if armature_type == MANUELMAP:
                    rig.karaage_split_manuel(context, obj, 100)
                    rig.fix_manuel_object_name(obj)
                    loc = util.get_center(context, obj)
                    obj['cog'] = loc

                obj.select = False
                
            for obj in newsources:
                obj.select=True
                obj.hide=False
 
            scene.objects.active = parent
            bpy.ops.object.parent_set(type='OBJECT', keep_transform=False)
            log.warning("|  Parented %d meshes to %s" % (len(parent.children), parent.name) )
            scene.cursor_location = curloc
            bpy.ops.object.select_all(action='DESELECT')
            util.set_select_and_hide(select_states)

    def adjust_to_manuellab_rig(self, context, tgt_armature):
        try:
            context.space_data.show_relationship_lines = False
        except:
            pass
        util.ensure_mode_is("EDIT")
        bones       = tgt_armature.data.edit_bones

        pelvis      = bones['Pelvis']
        pelvisInv   = bones['PelvisInv']
        torso       = bones['Torso']
        cog         = bones['COG']
        torso.head  = pelvis.tail

        cog.head    = pelvis.tail
        cog.tail[2] = pelvis.tail[2]
        pelvisInv.head = torso.head
        log.info("Transfer(armature): Move torso head to pelvis tail!")

        try:
            hi0L = bones['HandIndex0Left']
            ht1L = bones['HandThumb1Left']
            hi0L.head = ht1L.head
            hi0R = bones['HandIndex0Right']
            ht1R = bones['HandThumb1Right']
            hi0R.head = ht1R.head
        except:
            pass

        try:
            log.info("Transfer(armature): Fixing the eyes ...")
            mal_eye = Vector([c for c in tgt_armature.children if c.name.endswith('.EyeballLeft')][0].get('cog'))
            ava_eye = bpy.context.object.data.bones['EyeLeft'].head
            diff = ava_eye - mal_eye
            scale_x = mal_eye[0] / ava_eye[0]
            trans_y = mal_eye[1] - ava_eye[1]
            trans_z = mal_eye[2] - ava_eye[2]
            flul = bpy.context.object.data.bones['FaceLipUpperLeft'].head
            flcl = bpy.context.object.data.bones['FaceLipCornerLeft'].head
            dlip = flul[2] - flcl[2]

            for bone in [b for b in bones if b.name.startswith('Face') or b.name.startswith('Eye') or b.name.startswith('ikFace')  ]:

                bone.head[0] *= scale_x
                bone.head[1] += trans_y
                bone.head[2] += trans_z
                bone.tail[0] *= scale_x
                bone.tail[1] += trans_y
                bone.tail[2] += trans_z
                if bone.name.startswith('FaceLip'):
                    bone.tail[2] += dlip
                    bone.head[2] += dlip
                if bone.name.startswith('FaceEyebrowInner'):
                    bone.head[1] -= 0.005
                    bone.tail[1] -= 0.005

            fluc = bones['FaceLipUpperCenter'].head
            fllc = bones['FaceLipLowerCenter'].head
            lipik_z = 0.5*(fluc[2]+fllc[2])
            bones['ikFaceLipShapeMaster'].head[2] = lipik_z
            bones['ikFaceLipShape'      ].head[2] = lipik_z
            bones['ikFaceLipShapeMaster'].tail[2] = lipik_z
            bones['ikFaceLipShape'      ].tail[2] = lipik_z

        except:
            log.info("Transfer(armature): Can not adjust face bones")

        util.ensure_mode_is("POSE")
        try:
            log.info("Transfer(armature): Fixing the ik Hand Controllers ...")
            const.adjust_custom_shape(tgt_armature.pose.bones['ikWristRight'],   armature_type)
            const.adjust_custom_shape(tgt_armature.pose.bones['ikWristLeft'],    armature_type)
            const.adjust_custom_shape(tgt_armature.pose.bones['ikFaceLipShape'], armature_type)
            const.adjust_custom_shape(tgt_armature.pose.bones['PelvisInv'],      armature_type)
        except:
            log.info("Transfer(armature): Can not adjust ik Wrist control bones")

    def transfer_joint_info(self, context, src_armature, tgt_armature, armature_type, bone_store, sync):

        def copy_default_attributes(tbone, sbone):

            attributes = ['ohead', 'orelhead', 'otail', 'oreltail', 'scale']
            for attr in attributes:
                val = tbone.get(attr)
                if val:
                    continue

                val = sbone.get(attr)
                if val:
                    tbone[attr] = val

        def add_prop(tbone, sbone, key):
            v = sbone.get(key, None )
            if v != None:
                tbone[key]=v

        def add_channel(tbone, sbone, type):
            add_prop(tbone, sbone, "%s_%s" % (type, 'x'))
            add_prop(tbone, sbone, "%s_%s" % (type, 'y'))
            add_prop(tbone, sbone, "%s_%s" % (type, 'z'))

        def add_custom_bindpose(tbone, sbone):
            if not (sbone and tbone):
                return

            add_prop(tbone, sbone, 'bind_mat')
            add_prop(tbone, sbone, 'rest_mat')

            add_channel(tbone, sbone, 'restpose_loc')
            add_channel(tbone, sbone, 'restpose_rot')
            add_channel(tbone, sbone, 'restpose_scale')

            copy_default_attributes(tbone, sbone)

        def add_iklimits(tgt_pbone, iklimits):
            tgt_pbone.use_ik_limit_x = iklimits[0]
            tgt_pbone.use_ik_limit_y = iklimits[1]
            tgt_pbone.use_ik_limit_z = iklimits[2]
        
        def add_contraint_data(tgt_pbone,const_info):

            #

            cursor = 0
            length = len(const_info)
            for cons in [c for c in tgt_pbone.constraints if c.type=='LIMIT_ROTATION']:
                while cursor < length and const_info[cursor][0] != 'LIMIT_ROTATION':
                    cursor += 1
                if cursor >= length:
                    break
                cons.influence = const_info[cursor][1]
                cons.mute = const_info[cursor][2]

        scene = context.scene
        active = scene.objects.active
        amode  = active.mode
        log.info("|- Copy joints from armature [%s] (%s)" % (src_armature.name, src_armature.RigProps.RigType))
        log.info("|- Copy joints to   armature [%s] (%s)" % (tgt_armature.name, tgt_armature.RigProps.RigType))
        scene.objects.active = src_armature

        util.ensure_mode_is("POSE")
        selected_bone_names = util.getVisibleSelectedBoneNames(src_armature)
        log.debug("Found %d selected bones in Armature %s" % (len(selected_bone_names), src_armature.name))
        layers = [l for l in src_armature.data.layers]
        for i in range(32): src_armature.data.layers[i]=True
        src_armature.data.layers = layers

        log.info("|- Transfer Bone locations from [%s]" % src_armature.name)
        log.info("|- Transfer Bone locations to   [%s]" % tgt_armature.name)
        scene.objects.active = tgt_armature
        omode = util.ensure_mode_is("OBJECT")

        bpy.ops.karaage.unset_rotation_limits(True)

        tgt_armature.data.show_bone_custom_shapes = src_armature.data.show_bone_custom_shapes
        tgt_armature.show_x_ray                   = src_armature.show_x_ray
        tgt_armature.draw_type                    = src_armature.draw_type

        util.ensure_mode_is("EDIT")
        pbones = tgt_armature.pose.bones
        ebones = tgt_armature.data.edit_bones
        bgroups = tgt_armature.pose.bone_groups
        rig.reset_cache(tgt_armature)
        self.untag_boneset(ebones)

        for bone_data in bone_store:
            key = bone_data[BONE_DATA_NAME]

            bid = key if 'karaage' in src_armature else map_sl_to_Karaage(key, armature_type, all=False)

            if bid is None:
                log.debug("Transfer(armature): - Ignore source bone [%s] (not supported in Target)" % (key) )
                continue
            if not bid in ebones:
                log.debug("Transfer(armature): Miss [%s] to [%s]" % (key, bid) )
                continue

            tgt_ebone = ebones[bid]
            tgt_pbone = pbones[bid]
            if not bone_data[BONE_DATA_CONNECT]:
                rig.set_connect(tgt_ebone, False)
            
            head = PVector(bone_data[BONE_DATA_HEAD])
            tail = PVector(bone_data[BONE_DATA_TAIL])

            bone_group_name = bone_data[BONE_POSE_GROUP]
            if bone_group_name:
                colorset = bone_data[BONE_POSE_COLORSET]
                log.debug("Assign bone group %s with color set %s" % (bone_group_name, colorset) )
                bone_group = bgroups.get(bone_group_name)
                if not bone_group:
                    bone_group = bgroups.new(name=bone_group_name)
                tgt_pbone.bone_group = bone_group
                if colorset:
                    bone_group.color_set=colorset
            else:
                log.debug("No bone group assigned to bone %s" % (key) )

            group_index = tgt_pbone.bone_group_index
            if self.show_offsets:
                restpose_head, rtail = rig.get_sl_restposition(tgt_armature, tgt_ebone, use_cache=True)
                restpose_tail = restpose_head + rtail

                util.gp_draw_line(context, restpose_head, head, pname='karaage', lname='karaage', color_index = group_index)
                util.gp_draw_line(context, restpose_tail, tail, pname='karaage', lname='karaage', color_index = group_index)

            tgt_ebone['tag'] = True
            tgt_ebone.roll = bone_data[BONE_DATA_ROLL]
            tgt_ebone.matrix = bone_data[BONE_DATA_MATRIX]
            tgt_ebone.use_deform = bone_data[BONE_DATA_DEFORM]
            tgt_ebone.head = head.copy() # Here we copy head and tail of the source bone
            tgt_ebone.tail = tail.copy() # to the target bone

            if tgt_ebone.use_connect and tgt_ebone.parent:
                tgt_ebone.parent.tail = head.copy()

            add_custom_bindpose(tgt_ebone, src_armature.data.bones.get(key))
            add_contraint_data(tgt_pbone, bone_data[BONE_DATA_CONSTRAINT])
            add_iklimits(tgt_pbone, bone_data[BONE_DATA_IKLIMITS])

            if key!= bid and key in ebones:

                tgt_sebone = ebones[key]
                tgt_sebone['tag']=True
                tgt_sebone.roll   = bone_data[BONE_DATA_ROLL]
                tgt_sebone.matrix = bone_data[BONE_DATA_MATRIX]
                tgt_sebone.head = head.copy()
                tgt_sebone.tail = tail.copy()
                if tgt_sebone.use_connect and tgt_sebone.parent:
                    tgt_sebone.parent.tail = head.copy()
                    tgt_ebone.parent.tail  = head.copy()
                add_custom_bindpose(tgt_sebone, src_armature.data.bones.get(key))
                log.info("Move Bone %s to Bone %s" % (key, bid) )

            if armature_type == MANUELMAP:
                const.adjust_custom_shape(tgt_armature.pose.bones[tgt_ebone.name], armature_type)

                if bid.startswith("Hand"):
                    sign = -1 if bid.endswith("Left") else 1;
                    v = Vector((0.25*sign if bid.startswith("HandThumb") else 0, 0, 0.5))
                    tgt_ebone.align_roll(v)

                    continue
                if bid in SLARMBONES:
                    tgt_ebone.align_roll((0,0,1))
                    continue
                if bid in SLLEGBONES:
                    tgt_ebone.align_roll((0,1,0))
                    continue

        #

        bone_names = util.Skeleton.bones_in_hierarchical_order(tgt_armature)
        log.info("| Adjust Karaage Bones missing from Source Rig [%s] " % (src_armature.name))
        madjust_counter = 0
        cadjust_counter = 0

        for key in bone_names:

            if not (key[0] in ['m', 'a'] or key in SLVOLBONES):

                continue

            tgt_ebone = ebones[key]
            if not 'tag' in tgt_ebone:
                madjust_counter += 1
                log.debug("- Adjust bone %s" % tgt_ebone.name)

                parent = tgt_ebone.parent
                if not parent:
                    tgt_ebone['tag'] = True
                    continue
                if key[0:6] == 'mSpine':
                    log.debug("delay processing of %s" % (key) )
                    continue

                tgt_ebone['tag']=True
                head,   tail   = rig.get_sl_restposition(tgt_armature, tgt_ebone, use_cache=True)
                prhead, prtail = rig.get_sl_restposition(tgt_armature, parent, use_cache=True)

                log.debug("- adjust head:%s of bone [%s]" % (head, key))

                p_head   = parent.head
                p_tail   = parent.tail
                p_rest_v = Vector(prtail)
                p_v      = Vector(p_tail     - p_head)
                offset   = Vector(p_head     - prhead)
                Q        = p_rest_v.rotation_difference(p_v)

                t    = tail
                dt   = Q*t
                h    = head - prhead
                dh   = Q*h
                tgt_ebone.head = p_head         + dh
                tgt_ebone.tail = tgt_ebone.head + dt
                rig.reset_cache(tgt_armature, subset=[tgt_ebone])

                if key[0] == 'm':
                    cadjust_counter += 1
                    tgt_cbone = ebones[key[1:]]
                    if tgt_cbone.get('tag'):

                        tgt_ebone.head = tgt_cbone.head
                        tgt_ebone.tail = tgt_cbone.tail
                        log.debug("Adjust Deform Bone %s to Control Bone %s" % (tgt_ebone.name, tgt_cbone.name) )
                    else:

                        tgt_cbone.head = tgt_ebone.head
                        tgt_cbone.tail = tgt_ebone.tail
                        rig.reset_cache(tgt_armature, subset=[tgt_cbone])
                        log.debug("Adjust Control Bone %s to Deform Bone %s" % (tgt_cbone.name, tgt_ebone.name) )
                        tgt_cbone['tag']=True

                if self.show_offsets:
                    group_index = pbones[key].bone_group_index
                    util.gp_draw_line(context, head, tgt_ebone.head, pname='karaage', lname='karaage', color_index = group_index)

        ebones = tgt_armature.data.edit_bones

        pelvis = ebones['mPelvis']
        torso = ebones['mTorso']
        for key in bone_names:
            if not (key[0:6] == 'mSpine'):

                continue

            tgt_ebone = ebones[key]
            if not 'tag' in tgt_ebone:
                log.debug("processing of %s" % (key) )
                if key == 'mSpine1':
                    tgt_ebone.head = pelvis.tail.copy()
                    tgt_ebone.tail = pelvis.head.copy()
                elif key == 'mSpine2':
                    tgt_ebone.head = pelvis.head.copy()
                    tgt_ebone.tail = pelvis.tail.copy()
                elif key == 'mSpine3':
                    tgt_ebone.head = torso.tail.copy()
                    tgt_ebone.tail = torso.head.copy()
                else:
                    tgt_ebone.head = torso.head.copy()
                    tgt_ebone.tail = torso.tail.copy()

                tgt_ebone['tag'] = True
                tgt_cbone = ebones[key[1:]]
                tgt_cbone.head = tgt_ebone.head
                tgt_cbone.tail = tgt_ebone.tail
                tgt_cbone['tag'] = True
                rig.reset_cache(tgt_armature, subset=[tgt_cbone, tgt_ebone])
                
        log.info("| Adjusted %d Deform  Bones in target rig [%s]" % (madjust_counter, tgt_armature.name) )
        log.info("| Adjusted %d Control Bones in target rig [%s]" % (cadjust_counter, tgt_armature.name) )
        
        rig.adjustIKToRig(tgt_armature) # We get issues with the restpose otherwise
        log.info("| Adjusted IK Rig of rig [%s]" % (tgt_armature.name))

        if armature_type == MANUELMAP:
            self.adjust_to_manuellab_rig(context, tgt_armature)
            log.info("| Adjusted Manuellab [%s]" % (tgt_armature.name))

        transfer_constraints(context, tgt_armature, src_armature)
        log.info("| Adjusted Constraints of rig [%s]" % (tgt_armature.name))

        scene.objects.active = tgt_armature

        util.ensure_mode_is(omode)

        scene.objects.active = active
        util.ensure_mode_is(amode)

    def untag_boneset(self, bones):
        for b in bones:
            if 'tag' in b:
               del b['tag']

    def set_ik(self, src_armature, tgt_armature):

        on = src_armature.IKSwitches.Enable_Limbs
        if on:
            tgt_armature.IKSwitches.Enable_Limbs = on
            bpy.ops.karaage.ik_limbs_enable(enable_ik=True)

        on = src_armature.IKSwitches.Enable_Legs
        if on:
            tgt_armature.IKSwitches.Enable_Legs = on
            bpy.ops.karaage.ik_legs_enable(enable_ik=True)

        on = src_armature.IKSwitches.Enable_Arms
        if on:
            tgt_armature.IKSwitches.Enable_Arms = on
            bpy.ops.karaage.ik_arms_enable(enable_ik=True)

    def copy_skeleton(self, context, src_armature, selected, tgt_armature, armature_type, transfer_joints=True, sync=True):
        util.progress_update(10, absolute=False)
        scene = context.scene
        active = scene.objects.active
        amode = active.mode

        tgt_armature.RigProps.generate_joint_ik = src_armature.RigProps.generate_joint_ik
        tgt_armature.RigProps.generate_joint_tails = src_armature.RigProps.generate_joint_tails
        self.set_ik(src_armature, tgt_armature)

        if self.inplace_transfer:
            bones  = util.get_modify_bones(src_armature)
            origin = bones.get("Origin")
            origin_mismatch = origin != None and Vector(origin.head).magnitude > MIN_JOINT_OFFSET

            if "karaage" in src_armature and self.adjust_pelvis and rig.needPelvisInvFix(src_armature):
                rig.matchPelvisInvToPelvis(context, src_armature, alignToDeform=self.align_to_deform)

            children    = util.getChildren(src_armature)
            if origin_mismatch:

                if self.adjust_origin == 'ORIGIN_TO_ROOT':
                    util.transform_origin_to_rootbone(context, src_armature)
                    log.warning("| Transformed Origin to Root Bone in source Armature [%s]" % src_armature.name)
                else:
                    util.transform_rootbone_to_origin(context, src_armature)
                    log.warning("| Transformed Root Bone to Origin in source Armature [%s]" % src_armature.name)
            else:
                log.warning("Clean rig: Origin matches to Root Bone")

            if len(children) > 0:
                util.transform_origins_to_target(context, src_armature, children, V0)
            else:
                log.warning("Source Armature [%s] has no children (no need to adjust Origin")

        if self.apply_pose:
            util.ensure_mode_is("OBJECT")
            objs = self.freeze_armature(context, src_armature)
            self.sources = objs
            if objs:
                log.info("| Added %d frozen mesh objects for later attachment" % len(self.sources))

        log.info("| Transfer Skeleton from armature [%s] (%s)" % (src_armature.name, src_armature.RigProps.RigType))
        log.info("| Transfer Skeleton to   armature [%s] (%s)" % (tgt_armature.name, tgt_armature.RigProps.RigType))

        matrix_world = src_armature.matrix_world.copy()
        context.scene.cursor_location=src_armature.location
        
        util.ensure_mode_is("OBJECT")
        bpy.ops.object.select_all(action='DESELECT')

        util.progress_update(10, absolute=False)

        bone_store = self.extract_bone_data(context, src_armature, armature_type)

        util.progress_update(10, absolute=False)
        util.ensure_mode_is("OBJECT")

        if transfer_joints:
            self.transfer_joint_info(context, src_armature, tgt_armature, armature_type, bone_store, sync)
        else:
            log.info("|- Omitt joint info transfer from [%s] to [%s]" % (src_armature.name, tgt_armature.name) )

        util.ensure_mode_is("OBJECT")
        util.progress_update(10, absolute=False)

        if self.inplace_transfer:

            name = src_armature.name
            if self.active==src_armature:
                self.active = tgt_armature

            tgt_armature.name = name
            if armature_type == MANUELMAP:
                tgt_armature.name = tgt_armature.name.replace("skeleton_humanoid","Avatar_")

        util.progress_update(10, absolute=False)
        scene.objects.active = tgt_armature

        omode=util.ensure_mode_is('POSE')

        bpy.ops.pose.transforms_clear()
        util.ensure_mode_is('OBJECT')
        if armature_type == MANUELMAP:
            tgt_armature.data.layers[B_LAYER_SPINE]=True

        bpy.ops.object.select_all(action='DESELECT')

        scene.update()
        scene.MeshProp.standalonePosed=False
        scene.MeshProp.removeWeights=False
        scene.MeshProp.handleOriginalMeshSelection="DELETE"
        scene.MeshProp.joinParts=False
        util.ensure_mode_is("EDIT")

        if self.inplace_transfer:
            tgt_armature.data.show_bone_custom_shapes = False
            tgt_armature.show_x_ray                   = True
            tgt_armature.data.draw_type               = src_armature.data.draw_type 
            tgt_armature.matrix_world                 = matrix_world

            if self.sl_bone_ends:
                log.info("Adjust imported bone ends to Match the Karaage default")
                ebones = tgt_armature.data.edit_bones
                self.untag_boneset(ebones)

                for bone_data in bone_store:
                    key = bone_data[BONE_DATA_NAME]
                    if key in ebones:
                        tgt_ebone = ebones[key]
                        if tgt_ebone and tgt_ebone.parent and not util.Skeleton.has_connected_children(tgt_ebone):
                            parent = tgt_ebone.parent

                            rig.reset_cache(tgt_armature, subset=[tgt_ebone, parent])
                            d, rtail   = rig.get_sl_restposition(tgt_armature, tgt_ebone, use_cache=True)
                            cu_tail    = Vector(parent.tail) - Vector(parent.head)
                            d, sl_tail = rig.get_sl_restposition(tgt_armature, parent, use_cache=True)

                            M = sl_tail.rotation_difference(cu_tail).to_matrix()
                            dv= M*rtail
                            if dv.magnitude > MIN_BONE_LENGTH:
                                tgt_ebone['tag']=True
                                tgt_ebone.tail = tgt_ebone.head + dv
                                log.debug("Fixing bone tail for bone [%s]" % tgt_ebone.name)
                            else:
                                log.warning("Cant fix bone tail for bone [%s] (bone too short)" % tgt_ebone.name)

                log.info("Adjust not imported bone ends to Match imported bone ends")
                for bone_data in bone_store:
                    key = bone_data[BONE_DATA_NAME]
                    if key in ebones:
                        bid = key[1:] if key[0] == 'm' else 'm'+key
                        tbone = ebones.get(bid,None)
                        if tbone and not 'tag' in tbone:
                            tbone['tag'] = True
                            ebone = ebones.get(key)
                            tbone.tail = ebone.tail
                            log.debug("Adjusted bone %s to imported bone %s" % (tbone.name, ebone.name) )

            if "karaage" in src_armature and self.adjust_rig and rig.needRigFix(src_armature):

                rig.adjustAvatarCenter(tgt_armature)
                rig.adjustSLToRig(tgt_armature) if self.align_to_rig == 'DEFORM_TO_ANIMATION' else rig.adjustRigToSL(tgt_armature)
                rig.adjustIKToRig(tgt_armature)

                if self.snap_collision_volumes:
                    rig.adjustVolumeBonesToRig(tgt_armature)
                if self.snap_attachment_points:
                    rig.adjustAttachmentBonesToRig(tgt_armature)

            sync = False

            if self.transferJoints:
                with_ik = tgt_armature.RigProps.generate_joint_ik
                with_tails = tgt_armature.RigProps.generate_joint_tails
                delete_only = not ButtonCopyKaraage.sliders_allowed(context)
                bind.cleanup_binding(context, tgt_armature, sync, with_ik, with_tails, delete_only, only_meta=True)
            else:
                bind.remove_binding(context, tgt_armature, sync=sync)

            util.ensure_mode_is("POSE")
            log.debug("Transfer Select state of bones to Armature [%s]" % (tgt_armature.name) )
            for bone in tgt_armature.data.bones:
                bone.select_head = False
                bone.select_tail = False
                bone.select      = False

            for bone_data in  bone_store:
                key = bone_data[BONE_DATA_NAME]
                if bone_data[BONE_DATA_SELECT]:
                    bid =  map_sl_to_Karaage(key, armature_type, all=False)
                    if bid and bid in tgt_armature.data.bones:
                        bone = tgt_armature.data.bones[bid]
                        bone.select = True

            rig.fix_karaage_armature(context, tgt_armature)

        util.ensure_mode_is('OBJECT')
        if self.transferJoints and not self.inplace_transfer and not 'karaage' in src_armature:
            log.info("|- Roll neutral rotation of [%s]" % (src_armature.name) )
            roll_neutral_rotate(src_armature, Rz90I)
        util.ensure_mode_is(omode)

        layers = [l for l in src_armature.data.layers]
        tgt_armature.data.layers=layers

        scene.update()

        scene.objects.active = active
        util.ensure_mode_is(amode)

    def find_transfer_sources(self, context):
        scene = context.scene
        self.sources  = [obj for obj in self.selected if obj.is_visible(scene) and is_animated_mesh(obj, self.src_armature)]

        self.use_all_sources = (len(self.sources) == 0)
        if self.use_all_sources:
           if self.inplace_transfer:
               self.sources = [obj for obj in scene.objects if is_animated_mesh(obj, self.src_armature)]
           else:
               self.sources = [obj for obj in scene.objects if obj.is_visible(scene) and is_animated_mesh(obj, self.src_armature)]

    def init(self, context):

        self.src_armature = util.get_armature(context.object)
        if not self.src_armature:
            return False

        scene = context.scene
        self.active = scene.objects.active
        if not self.active:
            return False

        self.active_mode = self.active.mode
        self.sources          = None
        self.use_all_sources  = False 
        self.JointType        = 'PIVOT'

        if 'karaage' in self.src_armature and self.src_armature['karaage'] > 2:
            self.rig_display_type = self.src_armature.ObjectProp.rig_display_type
        else:
            self.rig_display_type = 'ALL'

        self.srcRigType = 'KARAAGE' if 'karaage' in self.src_armature else self.srcRigType

        if self.srcRigType == 'KARAAGE':
            shape.ensure_drivers_initialized(self.src_armature)
            self.sl_bone_ends = False
            self.pose_library = self.src_armature.pose_library
            self.is_male = self.src_armature.ShapeDrivers.male_80
        else:
            self.pose_library     = None

        updateRigProp = scene.UpdateRigProp
        self.transferJoints = updateRigProp.transferJoints

        self.selected = [ob for ob in bpy.context.selected_objects]
        self.targets  = [arm for arm in self.selected if arm.type=='ARMATURE' and 'karaage' in arm and arm != self.src_armature]
        self.inplace_transfer = (len(self.targets) == 0)

        self.find_transfer_sources(context)

        return True

    def invoke(self, context, event): 
        scene                          = context.scene
        updateRigProp                  = scene.UpdateRigProp

        self.transferMeshes            = updateRigProp.transferMeshes
        self.attachSliders             = updateRigProp.attachSliders
        self.applyRotation             = updateRigProp.applyRotation
        self.is_male                   = updateRigProp.is_male
        self.handleTargetMeshSelection = updateRigProp.handleTargetMeshSelection
        self.adjust_origin             = updateRigProp.adjust_origin
        self.align_to_deform           = updateRigProp.align_to_deform
        self.adjust_pelvis             = updateRigProp.adjust_pelvis
        self.align_to_rig              = updateRigProp.align_to_rig
        self.adjust_rig                = updateRigProp.adjust_rig

        if util.get_ui_level() > UI_ADVANCED:
            self.snap_collision_volumes = updateRigProp.snap_collision_volumes
            self.snap_attachment_points = updateRigProp.snap_attachment_points
        else:
            self.snap_collision_volumes = False
            self.snap_attachment_points = False
        
        self.bone_repair               = updateRigProp.bone_repair
        self.mesh_repair               = updateRigProp.mesh_repair
        self.show_offsets              = updateRigProp.show_offsets if get_blender_revision() > 277000 else False
        self.sl_bone_ends              = updateRigProp.sl_bone_ends
        self.sl_bone_rolls             = updateRigProp.sl_bone_rolls
        self.srcRigType                = updateRigProp.srcRigType
        self.tgtRigType                = updateRigProp.tgtRigType

        return self.execute(context)

    def execute(self, context):

        if not self.init(context):
            return {'CANCELLED'}

        active_mode = util.ensure_mode_is('OBJECT')
        src_armature_mode  = self.src_armature.mode
        selected_bones = [b.name for b in self.src_armature.data.bones if b.select]

        util.set_operate_in_user_mode(False)
        rigtype = self.tgtRigType

        def is_extended_rig():
            has_fingers = all( bn in self.src_armature.pose.bones \
                        for bn in ['pinky00_R', 'spine03', 'upperarm_L', 'clavicle_L'] \
                       )
            return has_fingers

        def replace_armature(src_armature, tgt_armature):
            util.ensure_mode_is('OBJECT', object=src_armature)
            context.scene.objects.active = tgt_armature
            log.info("| Unlink Source armature %s" % src_armature.name)
            util.remove_object(context, src_armature)

        tgt_armatures = None
        tgt_armature = None

        if self.srcRigType != 'KARAAGE':
            log.info("Converting an SL Armature to Karaage: [%s]" % self.src_armature.name)
            tgt_armature = convert_sl(
                self,
                context,
                rigtype,
                self.active,
                self.src_armature,
                self.inplace_transfer,
                self.bone_repair,
                self.mesh_repair,
                self.transferJoints
                )

        else:

            if is_extended_rig():

                rigtype       = 'EXTENDED'

            if self.inplace_transfer:
                self.transferMeshes = True
                tgt_armature = update_karaage(
                    self,
                    context,
                    rigtype,
                    self.active, 
                    self.src_armature, 
                    self.bone_repair,
                    self.mesh_repair,
                    self.transferJoints
                    )

            else:

                tgt_armatures = copy_karaage(
                    self,
                    context,
                    rigtype,
                    self.active, 
                    self.src_armature, 
                    self.bone_repair,
                    self.mesh_repair
                    )

        if tgt_armature:

            replace_armature(self.src_armature, tgt_armature)
            if self.pose_library:
                tgt_armature.pose_library = self.pose_library

            if self.attachSliders:
                tgt_armature.ObjectProp.slider_selector = 'SL'
            else:
                tgt_armature.ObjectProp.slider_selector = 'NONE'

            if not self.inplace_transfer:
                util.ensure_mode_is(src_armature_mode, object=tgt_armature)
                tgt_armature.ObjectProp.filter_deform_bones = False
                context.scene.objects.active.select = True

            omode = util.ensure_mode_is('EDIT')
            bpy.ops.armature.select_all(action='SELECT')
            bpy.ops.transform.translate(value=(0, 0, 0)) # Dont ask hrmpfff
            bpy.ops.armature.select_all(action='DESELECT')
            for bname in selected_bones:
                bone = tgt_armature.data.edit_bones.get(bname)
                if bone:
                    bone.select=True
            util.ensure_mode_is('OBJECT')
            util.ensure_mode_is(omode)

        util.set_operate_in_user_mode(True)
        util.ensure_mode_is(active_mode)
        return {'FINISHED'}

    @classmethod
    def poll(self, context):
        try:
            return context.active_object and context.active_object.type == 'ARMATURE'
        except (TypeError, AttributeError):
            pass
        return False

def create_transfer_preset(layout):
    last_select = bpy.types.karaage_transfer_presets_menu.bl_label
    row = layout.row(align=True)
    row.menu("karaage_transfer_presets_menu", text=last_select )
    row.operator("karaage.transfer_presets_add", text="", icon='ZOOMIN')
    if last_select not in ["Transfer Presets", "Presets"]:
        row.operator("karaage.transfer_presets_update", text="", icon='FILE_REFRESH')
        row.operator("karaage.transfer_presets_remove", text="", icon='ZOOMOUT').remove_active = True

def add_transfer_preset(context, filepath):
    armobj = context.object
    log.warning("Create transfer preset for object %s" % (armobj.name) )
    scene = context.scene
    sceneProps = scene.SceneProp
    updateRigProp = scene.UpdateRigProp

    file_preset = open(filepath, 'w')
    file_preset.write(
    "import bpy\n"
    "import karaage\n"
    "from karaage import shape, util\n"
    "\n"
    "context = bpy.context\n"
    "scene = context.scene\n"
    "armobj = context.object\n"
    "updateRigProp = scene.UpdateRigProp\n"
    "sceneProps  = scene.SceneProp\n\n"
    )

    file_preset.write("armobj.data.pose_position = '%s'\n" % armobj.data.pose_position)
    file_preset.write("updateRigProp.srcRigType = '%s'\n" % updateRigProp.srcRigType)
    file_preset.write("updateRigProp.tgtRigType = '%s'\n" % updateRigProp.tgtRigType)
    file_preset.write("updateRigProp.handleTargetMeshSelection = '%s'\n" % updateRigProp.handleTargetMeshSelection)
    file_preset.write("updateRigProp.transferJoints = %s\n" % updateRigProp.transferJoints)
    file_preset.write("armobj.RigProps.JointType = '%s'\n" % armobj.RigProps.JointType)
    file_preset.write("armobj.RigProps.rig_use_bind_pose = %s\n" % armobj.RigProps.rig_use_bind_pose)
    file_preset.write("updateRigProp.sl_bone_ends = %s\n" % updateRigProp.sl_bone_ends)
    file_preset.write("updateRigProp.sl_bone_rolls = %s\n" % updateRigProp.sl_bone_rolls)
    file_preset.write("updateRigProp.show_offsets = %s\n" % updateRigProp.show_offsets)
    file_preset.write("updateRigProp.attachSliders = %s\n" % updateRigProp.attachSliders)
    file_preset.write("updateRigProp.applyRotation = %s\n" % updateRigProp.applyRotation)
    file_preset.write("updateRigProp.is_male = %s\n" % updateRigProp.is_male)
    file_preset.write("updateRigProp.apply_pose = %s\n" % updateRigProp.apply_pose)

    file_preset.close()

class KARAAGE_MT_transfer_presets_menu(Menu):
    bl_idname = "karaage_transfer_presets_menu"
    bl_label  = "Transfer Presets"
    bl_description = "Transfer Presets for Karaage\nHere you define configurations for updating/importing Rigs."
    preset_subdir = os.path.join("karaage","transfers")
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset

class KaraageAddPresetTransfer(AddPresetBase, Operator):
    bl_idname = "karaage.transfer_presets_add"
    bl_label = "Add Transfer Preset"
    bl_description = "Create new Preset from current Panel settings"
    preset_menu = "karaage_transfer_presets_menu"

    preset_subdir = os.path.join("karaage","transfers")

    def invoke(self, context, event):
        print("Create new Preset...")
        return AddPresetBase.invoke(self, context, event)

    def add(self, context, filepath):
        add_transfer_preset(context, filepath)

class KaraageUpdatePresetTransfer(AddPresetBase, Operator):
    bl_idname = "karaage.transfer_presets_update"
    bl_label = "Update Transfer Preset"
    bl_description = "Update active Preset from current Panel settings"
    preset_menu = "karaage_transfer_presets_menu"
    preset_subdir = os.path.join("karaage","transfers")

    def invoke(self, context, event):
        self.name = bpy.types.karaage_transfer_presets_menu.bl_label
        print("Updating Preset", self.name)
        return self.execute(context)

    def add(self, context, filepath):
        add_transfer_preset(context, filepath)

class KaraageRemovePresetTransfer(AddPresetBase, Operator):
    bl_idname = "karaage.transfer_presets_remove"
    bl_label = "Remove Transfer Preset"
    bl_description = "Remove last selected Preset from the list"
    preset_menu = "karaage_transfer_presets_menu"
    preset_subdir = os.path.join("karaage","transfers")

#

#

def transfer_constraints(context, tgt_armature, src_armature):
    pbones = tgt_armature.pose.bones
    ebones = tgt_armature.data.edit_bones
    sbones = src_armature.pose.bones

    def get_constraints(bone, type):
        cons = [ con for con in bone.constraints if con.type == type]
        return cons

    def copycons(tbone, sbone, type, tcbone=None, tcpbone=None):

        scons = get_constraints(sbone, type)
        tcons = get_constraints(tbone, type)

        for scon, tcon in zip(scons, tcons):
            tcon.mute = scon.mute

            if tcbone:

                targetless_iks = [c for c in tcpbone.constraints if c.type=='IK' and c.target==None]
                for ikc in targetless_iks:
                    ikc.influence = 0.0 if tcon.mute else 1.0

    def copylock(tbone, sbone):
        for n in range(0,3):
            tbone.lock_location[n] = sbone.lock_location[n]

    def get_control_bone(tbone, ebones, pbones):
        cname = tbone.name[1:]
        return ebones.get(cname), pbones.get(cname)

    for tbone in pbones:
        sbone = sbones.get(tbone.name)
        if not sbone:

            continue

        copycons(tbone, sbone, 'COPY_ROTATION')
        tcbone, tcpbone = get_control_bone(tbone, ebones, pbones) 

        copycons(tbone, sbone, 'COPY_LOCATION', tcbone, tcpbone)
        copylock(tbone, sbone)
        if not src_armature.data.bones[tbone.name].use_connect:
            rig.set_connect(ebones[tbone.name], False) # uhuuu

def transfer_joints(context, armobj, bone_store):
    log.debug("transfer_joints: Apply Source data to armature %s" % (armobj.name) )

    with set_context(context, armobj, 'EDIT'):
        log.debug("transfer_joints: Transfer %d bones from bone_store to armature %s in EDIT mode" % (len(bone_store), armobj.name) )
        pbones = armobj.pose.bones
        ebones = armobj.data.edit_bones
        rig.reset_cache(armobj)
        processed_mbones = {}
        processed_cbones = {}

        bpy.ops.armature.select_all(action='DESELECT')
        self.untag_boneset(ebones)
        for bone_data in bone_store:
            key = bone_data[BONE_DATA_NAME]
            if not key in ebones:
                pname=bone_data[BONE_DATA_PARENT]
                if pname in ebones:
                    log.info("transfer_joints: - Add Bone [%s] (parent= [%s]) to Armature [%s]" % (key, pname, armobj.name) )
                else:
                    log.error("transfer_joints: - Add Bone [%s] failed. Cause: Armature [%s] has no parent bone named [%s]" % (key, armobj.name, pname) )
                    continue
                b=ebones.new(key)

                b.parent=ebones[pname]

            tgt_ebone = ebones[key]
            tgt_pbone = pbones[key]

            head = bone_data[BONE_DATA_HEAD]
            tail = bone_data[BONE_DATA_TAIL]

            tgt_ebone['tag'] = True
            tgt_ebone.roll = bone_data[BONE_DATA_ROLL]
            tgt_ebone.matrix = bone_data[BONE_DATA_MATRIX]
            tgt_ebone.head = head
            tgt_ebone.tail = tail
            tgt_ebone.select = bone_data[BONE_DATA_SELECT]
            if bone_data[BONE_DATA_SELECT]:
                log.debug("Preserve Select State for Bone %s" % (key))
            else:
                log.debug("Bone %s not selected" % (key))

            #
            if key[0] == 'm':
                processed_mbones[key]=tgt_ebone
            elif 'm'+key in ebones:
                processed_cbones[key]=tgt_ebone

            bone_group_name = bone_data[BONE_POSE_GROUP]
            if bone_group_name:
                colorset = bone_data[BONE_POSE_COLORSET]
                log.debug("Assign bone group %s with color set %s" % (bone_group_name, colorset) )
                bone_group = arm.pose.bone_groups.get(bone_group_name)
                if not bone_group:
                    bone_group = arm.pose.bone_groups.new(name=bone_group_name)
                tgt_pbone.bone_group = bone_group
                if colorset:
                    bone_group.color_set=colorset
            else:
                log.info("No bone group assigned to bone %s" % (key) )

        for key, mbone in processed_mbones.items():
            if not key[1:] in processed_cbones:
                cbone = ebones.get(key[1:], None)
                if cbone:
                    log.debug("transfer_joints: - Synchronize Bone %s to its deform bone %s" % (key[1:], key) )
                    cbone['tag'] = True
                    cbone.roll   = mbone.roll
                    cbone.matrix = mbone.matrix
                    cbone.head   = mbone.head
                    cbone.tail   = mbone.tail
                    cbone.select = mbone.select
                else:
                    log.warning("transfer_joints: - The source Rig controls the unsupported deform bone [%s]" % (key) )

def roll_neutral_rotate(armobj, rot):
        log.debug("roll_neutral_rotate: Rotate Armature: [%s] (preserving boneroll)" % armobj.name)

        util.ensure_mode_is("OBJECT")
        armobj.matrix_world *= rot
        bpy.ops.object.select_all(action='DESELECT')
        armobj.select=True
        bpy.ops.object.transform_apply(rotation=True)

        util.ensure_mode_is("OBJECT")

def extract_bone_data(context, armobj, Rot):
    log.debug("extract_bone_data: Extract Source bone data")
    bone_store = []

    with set_context(context, armobj, 'OBJECT'):

        if Rot:
            roll_neutral_rotate(armobj, Rot)

        util.ensure_mode_is("EDIT")

        bone_names = util.Skeleton.bones_in_hierarchical_order(armobj)
        ebones = armobj.data.edit_bones
        pbones = armobj.pose.bones
        for name in bone_names:
            ebone = ebones[name]
            pbone = pbones[name]
            constraints = [[c.type,c.influence,c.mute] for c in pbone.constraints]
            iklimits = [ pbone.use_ik_limit_x, pbone.use_ik_limit_y, pbone.use_ik_limit_z ]
            bone_store.append([
                name,
                ebone.head.copy(),
                ebone.tail.copy(),
                ebone.select,
                ebone.use_deform,
                ebone.roll,
                ebone.matrix,
                ebone.parent.name if ebone.parent else None,
                pbone.bone_group.name if pbone.bone_group else None,
                pbone.bone_group.color_set if pbone.bone_group else None,
                ebone.use_connect,
                constraints,
                iklimits]
            )

        if Rot:
            roll_neutral_rotate(armobj, Rot.inverted())

    return bone_store

#

#

#

def copy_armature(context, from_rig, to_rig, Rot=None):
    bone_store = None

    with set_context(context, from_rig, 'EDIT'):
        bone_store = extract_bone_data(context, from_rig, Rot)

    with set_context(context, to_rig, 'EDIT'):
        transfer_joints(context, to_rig, bone_store)

    return

#

#

def move_rigged(context, from_rig, to_rig):
    pass
