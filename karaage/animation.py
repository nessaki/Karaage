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

import bpy, bgl
from bpy.props import *
from struct import pack, unpack, calcsize
from mathutils import Matrix, Vector, Euler

import re, os, logging, gettext
from math import *
from .const import *
from . import create, data, rig, shape, util, context_util
from .context_util import set_context
from bpy_extras.io_utils import ExportHelper
from bpy_extras.io_utils import ImportHelper

LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locale')
translator = gettext.translation('karaage', LOCALE_DIR, fallback=True)
_ = translator.gettext

log = logging.getLogger('karaage.animation')

ALL_CHANNELS = "CHANNELS 6 Xposition Yposition Zposition Xrotation Yrotation Zrotation"
ROT_CHANNELS = "Xrotation Yrotation Zrotation"
LOC_CHANNELS = "Xposition Yposition Zposition"

BVH_CHANNELS_TEMPLATE = "CHANNELS %d %s %s"  #usage: BVH_CHANNELS_TEMPLATE % (6, LOC_CHANNELS, ROT_CHANNELS)

msg_too_many_bones = 'Max Bonecount(32) exceeded|'\
                +  'DETAIL:\n'\
                +  'This animation uses %d bones, while in SL the maximum number\n'\
                +  'of bones per animation sequence is limitted to 32.\n'\
                +  'You possibly run into this problem when you first \n'\
                +  'select all bones and then add a keyframe.\n\n'\
                +  'YOUR ACTION:\n'\
                +  'Remove unnecessary bones from the animation (use the Dopesheet)\n'\
                +  'or split the animation into 2 or more separate animations\n'\
                +  'and run the animations in parallel in the target system.|'

def transfer_motion(context, source, target, prop, reference_frame):
    scn = context.scene
    start_frame = scn.frame_start
    end_frame   = scn.frame_end

    translations = []
    for bonename in data.get_mt_bones(target):
        sourcebone = getattr(prop, bonename)
        if sourcebone != "":
            if bonename == "COGloc":
                bone_target = BoneTarget(source=sourcebone,target="COG",loc=True,frames={})
            else:
                bone_target = BoneTarget(source=sourcebone,target=bonename,frames={})
            translations.append(bone_target)

    setReference(context, source, target, translations, reference_frame)
    transferMotion(source, target, translations, reference_frame, start_frame, end_frame, prop)

def set_best_match(prop, source, target):
    prop.flavor, bonelist = find_best_match(source, target)

    for sourcebone, targetbone in zip(bonelist, data.get_mt_bones(target)):
        if sourcebone in source.pose.bones:
            setattr(prop, targetbone, sourcebone)
        else:
            setattr(prop, targetbone, "")

def find_best_match(source, target):

    SLBONES = data.get_msl_bones(target)
    slcount = len ([bone for bone in SLBONES if bone in source.pose.bones])
    if slcount > 18:
        return "SL/OpenSim, etc.", SLBONES
    
    CMBONES = data.get_mcm_bones(target)
    cmcount = len ([bone for bone in CMBONES if bone in source.pose.bones])
    if cmcount > 18:
        return "Carnegie Mellon", CMBONES
        
    return "", data.get_mt_bones(target)
    
def clamp(inputval, lower, upper):
    '''
    Limit a value to be between the lower and upper values inclusive
    '''
    return max( min( inputval, upper), lower)

def U16_to_F32(inputU16, lower, upper):
    '''
    The way LL uncompresses floats from a U16. Fudge for 0 included
    In 2 bytes have 256**2 = 65536 values
    '''
    temp = inputU16 / float(65535)
    temp *= (upper - lower)
    temp += lower
    delta = (upper - lower)

    if abs(temp) < delta/float(65535):
        temp = 0

    return temp

def F32_to_U16(inputF, lower, upper):
    '''
    The way LL compresses a float into a U16.
    In 2 bytes have 256**2 = 65536 values
    '''
    inputF = clamp(inputF, lower, upper)
    inputF -= lower
    if upper!=lower:
        inputF /= (upper - lower)
    inputF *= 65535

    return int(floor(inputF))

def visualmatrix(context, armobj, dbone, pbone):
    '''
        return a local delta transformation matrix that captures the visual
        transformation from the bone's parent to the bone. This includes
        the influence of the IK chain etc relative to parent

        N.B. pose_bone.matrix_basis will not capture rotations due to IK

        Hint: The caller must ensure that dbone is a data.bone and pbone is a pose.bone
              also the bone must have a parent!
    '''
    
    if util.use_sliders(context) and armobj.RigProps.rig_use_bind_pose:
        M = Matrix(dbone['mat0']).copy() # bone pose matrix in objects frame
        MP = Matrix(dbone.parent['mat0']).copy() if dbone.parent else Matrix()

    else:
        M = dbone.matrix_local.copy() # bone data matrix in objects frame
        MP = dbone.parent.matrix_local.copy() if dbone.parent else Matrix()
    MI = M.inverted()

    P = pbone.matrix.copy()
    PP = pbone.parent.matrix.copy() if pbone.parent else Matrix()
    PPI = PP.inverted()

    V = MI * MP * PPI * P

    C = M.to_3x3().to_4x4()
    CI = C.inverted()

    visual_matrix = C*V*CI

    return visual_matrix

def dot(v1,v2):
    '''
    return the dot product between v1 and v2
    '''
   
    ans=0
    for a in map(lambda x,y:x*y, v1,v2):
        ans+=a
    return ans

def distanceToLine(P,A,B):
    '''
    Calculate Euclidean distance from P to line A-B in any number of dimensions
    '''

    P = tuple(P)
    A = tuple(A)
    B = tuple(B)

    AP = [v for v in map(lambda x,y:x-y, A,P)] 
    AB = [v for v in map(lambda x,y:x-y, A,B)] 

    ABAP = dot(AB,AP)
    ABAB = dot(AB,AB)
    APAP = dot(AP,AP)

    d = sqrt(abs(APAP-ABAP**2/ABAB))

    return d

def update_sync_influence(context, val, symmetry):
    pbones = context.object.pose.bones
    for part in ["Thumb", "Index", "Middle", "Ring", "Pinky"]:
        name = "ik%sTarget%s" % (part, symmetry) 
        bone = pbones[name]
        if bone.sync_influence:
            name = "ik%sSolver%s" % (part, symmetry)
            bone = pbones[name] 
            con  = bone.constraints['Grab']
            con.influence = val

def update_sync_influence_left(pbone, context):
    val = context.object.RigProps.IKHandInfluenceLeft
    update_sync_influence(context, val, "Left")

def update_sync_influence_right(pbone, context):
    val = context.object.RigProps.IKHandInfluenceRight
    update_sync_influence(context, val, "Right")

def animationUpdate(self, context):

    obj = context.active_object
         
    shape.setHands(obj, context.scene)

def loopUpdate(self, context):
    obj = context.object
    arm = util.get_armature(obj)
    if arm:
        props = get_props_from_arm(arm)

        if props.Loop:

            props.Loop_In = context.scene.frame_start
            props.Loop_Out = context.scene.frame_end

def update_bone_type(self, context):
    obj = context.object
    arm = util.get_armature(obj)
    if arm and  len(self.draw_type) > 0:
        arm.data.draw_type = self.draw_type.pop()
        
def update_restpose_mode(self, context):
    obj = context.object
    arm = util.get_armature(obj)
    if arm:
        shape.updateShape(self, context, target="", scene=None, refresh=True, init=False, object=None, msg="update_restpose_mode")

def update_affect_all_joints(self, context):
    obj    = context.object
    armobj = util.get_armature(obj)
    if armobj:
        joints = armobj.get('sl_joints')
        if joints:
            bones = util.get_modify_bones(armobj)
            for key, joint in joints.items():
                b=bones.get(key, None)
                if b:
                    b.select = b.select_head = b.select_tail = self.affect_all_joints

def update_rig_pose_type(self, context):
    obj = context.object
    armobj = util.get_armature(obj)
    if armobj and ('karaage' in armobj or 'avastar' in armobj):
        shape.updateShape(None, context, scene=context.scene, refresh=True, init=False, msg="updateShape after switch pose type")

def update_toggle_select(self, context):
    for action in bpy.data.actions:
        action.AnimProps.select = self.toggle_select

update_scene_data_on = True
def set_update_scene_data(state):
    global update_scene_data_on
    update_scene_data_on = state

def update_scene_data(self, context):
    global update_scene_data_on
    if not update_scene_data_on:
        return
    
    scene=context.scene
    active = scene.objects.active
    if not ( active and active.type =='ARMATURE' and ('karaage' in active or 'avastar' in active)):

        return
    if not active.animation_data:
        return

    action = active.animation_data.action
    if not action:
        return

    props = action.AnimProps
    try:
        set_update_scene_data(False)
        log.warning("Action changed")
        if props.frame_start != -2 and context.scene.SceneProp.loc_timeline:

            scene.frame_start = props.frame_start
            scene.frame_end = props.frame_end
            scene.render.fps = props.fps
    finally:
        set_update_scene_data(True)

class AnimProps(bpy.types.PropertyGroup):
    Loop = BoolProperty(name=_("Loop"), default = False, description=_("Loop part of the animation"), update=loopUpdate)
    Loop_In = IntProperty(name=_("Loop In"), description=_("Frame to start looping animation"))
    Loop_Out = IntProperty(name=_("Loop Out"), description=_("Frame to stop looping, rest will play when animation is stopped"))
    Priority = IntProperty(name=_("Priority"), default = 3, min=MIN_PRIORITY, max=MAX_PRIORITY, description=_("Priority at which to play the animation"))
    Ease_In = FloatProperty(name=_("Ease In"), default=0.8, min=0, description=_("Fade in the influence of the animation at the beginning [s]"))
    Ease_Out = FloatProperty(name=_("Ease Out"), default=0.8, min=0, description=_("Fade out the influence of the animation at the end [s]"))

    frame_start = IntProperty(
                  name="Start Frame",
                  description="First frame to be exported",
                  default = -2,
                  update = update_scene_data
                  )

    frame_end   = IntProperty(
                  name="End Frame",
                  description="Last frame to be exported",
                  default = -2,
                  update = update_scene_data
                  )

    fps         = IntProperty(
                  name="Frame Rate",
                  description="Frame rate to be exported",
                  default = -2,
                  update = update_scene_data
                  )

    Translations = BoolProperty(
                   name = "With Bone translation",
                   default = False,
                   description = AnimProps_Translation_description
                   )

    selected_actions = BoolProperty(
                  name="Bulk Export",
                  default = False,
                  description = AnimProps_selected_actions_description
                  )

    select = BoolProperty(
                  name="select",
                  default = False,
                  description = "Select this action for exporting"
                  )

    toggle_select = BoolProperty(
                  name="All",
                  default = False,
                  description = "Select/Deselkct All",
                  update=update_toggle_select
                  )

    ReferenceFrame = BoolProperty(name=_("Prepend reference"), default = True, description=_("Prepend a reference frame so the animation importer knows which bones are being animated"))

    modeitems = [
        ('bvh', 'BVH', 'BVH'),
        ('anim', 'Anim', 'Anim'),
        ]
    Mode = EnumProperty(items=modeitems, name='Mode', default='anim')

    Basename = StringProperty(name=_("name"), description=_("template for filename with substitutions ($action=action name, $avatar=avatar name). See Help for more substitutions"), maxlen=100, default= "$action")

    handitems = []

    HANDS = shape.HANDS

    for key in range(len(HANDS.keys())):
        handitems.append((str(HANDS[key]['id']),HANDS[key]['label'],HANDS[key]['label'] ))
    Hand_Posture = EnumProperty( items=handitems, name=_('Hands'), default='1', 
            update=animationUpdate, description=_("Hand posture to use in the animation") )

    rigtypes = [
       ('BASIC', "Basic", "This Rig type Defines the Legacy Rig:\nThe basic Avatar with 26 Base bones and 26 Collision Volumes"),
       ('EXTENDED', "Extended", "This Rig type Defines the extended Rig:\nNew bones for Face, Hands, Tail, Wings, ... (the Bento rig)"),
    ]
    RigType = EnumProperty(
        items       = rigtypes,
        name        = "Rig Type",
        description = "Basic: Old Avatar Skeleton, Extended: Bento Bones",
        default     = 'BASIC')
    
class ExportActionsPropIndex(bpy.types.PropertyGroup):
    index = IntProperty(name="index")

class ExportActionsProp(bpy.types.PropertyGroup):
    select = BoolProperty(
                name = "has_head",
                description = "has Head",
                default = False,
    )

class ExportActionsPropVarList(bpy.types.UIList):

    def draw_item(self,
                  context,
                  layout,
                  data,
                  item,
                  icon,
                  active_data,
                  active_propname
                  ):

        layout.prop(item.AnimProps,"select", text=item.name)

class RigProps(bpy.types.PropertyGroup):    
    IKHandInfluenceLeft  = FloatProperty(name="Left Hand IK Combined", 
                           default=0.0,
                           min=0.0,
                           max=1.0,
                           update=update_sync_influence_left,
                           description="Combined Influence for all IK Controllers of the Left Hand"
                           )
                           
    IKHandInfluenceRight = FloatProperty(name="Right Hand IK Combined",
                           default=0.0,
                           min=0.0,
                           max=1.0,
                           update=update_sync_influence_right,
                           description="Combined Influence for all IK Controllers of the Right Hand"
                           )

    constraintItems = [
                ('SELECTION', 'Selected Bones', 'The Selected Pose Bones'),
                ('VISIBLE',   'Visible Bones',  'All Visible Pose Bones'),
                ('SIMILAR',   'Same Group',  'All Pose Bones in same Group'),
                ('ALL'    ,   'All Bones',      'All Pose Bones'),
    ]

    ConstraintSet   = EnumProperty(
        items       = constraintItems,
        name        = "Set",
        description = "Affected Bone Set",
        default     = 'ALL')

    handitems = []

    HANDS = shape.HANDS

    for key in range(len(HANDS.keys())):
        handitems.append((str(HANDS[key]['id']),HANDS[key]['label'],HANDS[key]['label'] ))
    Hand_Posture = EnumProperty( items=handitems, name=_('Hands'), default='1', 
            update=animationUpdate, description=_("Hand posture to use in the animation") )

    RigType = EnumProperty(
        items = (
            ('BASIC', "Basic", "This Rig type Defines the Legacy Rig:\nThe basic Avatar with 26 Base bones and 26 Collision Volumes"),
            ('EXTENDED', "Extended", "This Rig type Defines the extended Rig:\nNew bones for Face, Hands, Tail, Wings, ... (the Bento rig)"),
        ),
        name        = "Rig Type",
        description = "Basic: Old Avatar Skeleton, Extended: Bento Bones",
        default     = 'BASIC')
    
    JointType = EnumProperty(
        items = (
            ('POS',   'Pos' ,    'Create a rig based on the pos values from the avatar skeleton definition\nFor making Cloth Textures for the System Character (for the paranoid user)'),
            ('PIVOT', 'Pivot'  , 'Create a rig based on the pivot values from the avatar skeleton definition\nFor Creating Mesh items (usually the correct choice)')
        ),
        name=_("Joint Type"),
        description= "SL supports 2 Skeleton Defintions.\n\n- The POS definition is used for the System Avatar (to make cloth).\n- The PIVOT definition is used for mesh characters\n\nAttention: You need to use POS if your Devkit was made with POS\nor when you make cloth for the System Avatar",
        default='PIVOT')
    
    affect_all_joints = BoolProperty(
               name    = "All Joints",
               default = True,
               description = "Affect all bones.\nWhen this option is cleared then only selected bones are affected",
               update      = update_affect_all_joints
               )

    keep_edit_joints = BoolProperty(
               name    = "Keep",
               default = True,
               description = RigProps_keep_edit_joints_description
               )
    restpose_mode = BoolProperty(
               name    = "SL Restpose mode",
               default = False,
               description = RigProps_restpose_mode_description
               )
    
    rig_use_bind_pose = BoolProperty(
        default=False,
        name        =_("Use Bind Pose"),
        update      = update_rig_pose_type,
        description =RigProps_rig_use_bind_pose_description
        )

    display_joint_heads = BoolProperty (
               default = True,
               name = "Heads",
               description = "List the Bones with modified Bone head location (Joint offsets)"
               )
    
    display_joint_tails = BoolProperty (
               default = False,
               name = "Tails",
               description = "List the Bones with modified Bone tail location (Bone ends)"
               )
    
    generate_joint_tails = BoolProperty (
               default = True,
               name = "Generate Tail Offsets",
               description = "Generate Joint entries also for Bone tails\nYou want to keep this enabled! (experts only)"
               )
    
    generate_joint_ik = BoolProperty (
               default = False,
               name = "Generate IK Offsets",
               description = "Generate Joint Offsets for the IK Joints\nMake IK Bones react on Sliders (experimental)"
               )
    
    display_joint_values = BoolProperty (
               default = False,
               name    = "Values [mm]",
               description = RigProps_display_joint_values_description
               )

    drawtypes = [
       ('OCTAHEDRAL', "Octahedral",  "Display bones as Octahedral shapes"),
       ('STICK',      "Stick", "Display Bones as Sticks")
    ]
    draw_type = EnumProperty(
        items       = drawtypes,
        name        = "Draw Type",
        description = "Set the Bone Draw Type for this Rig",

        options     = {'ANIMATABLE', 'ENUM_FLAG'},
        update      = update_bone_type)
        
    spine_unfold_upper = BoolProperty (
               default = False,
               name    = "Unfold Upper",
               description = "Unfold the Spine3,Spine4 Bones (the upper spine connecting torso with chest)",
               update = rig.update_spine_folding
               )
    spine_unfold_lower = BoolProperty (
               default = False,
               name    = "Unfold Lower",
               description = "Unfold the Spine1,Spine2 Bones (the lower spine connecting Pelvis with Torso)",
               update = rig.update_spine_folding
               )        

class JointOffsetPropIndex(bpy.types.PropertyGroup):
    index = IntProperty(name="index")

class JointOffsetProp(bpy.types.PropertyGroup):
    has_head = BoolProperty(
                name = "has_head",
                description = "has Head",
                default = False,
    )
    has_tail = BoolProperty(
                name = "has_tail",
                description = "has Tail",
                default = False,
    )
    
    head = FloatVectorProperty(
                name = "Head",
                description = "Head",
    )
    
    tail = FloatVectorProperty(
                name = "Tail",
                description = "Tail",
    )

class JointOffsetPropVarList(bpy.types.UIList):

    def draw_item(self,
                  context,
                  layout,
                  data,
                  item,
                  icon,
                  active_data,
                  active_propname
                  ):

        armobj = util.get_armature(context.object)
        key = item.name
        H = "H" if item.has_head else ""
        T = "T" if item.has_tail else ""
        marker = "%s%s" % (H,T)
        percentage = 1
        if armobj.RigProps.display_joint_tails:
            percentage *= 0.6
        if armobj.RigProps.display_joint_heads:
            percentage *= 0.6

        if percentage < 1:

           spl = layout.split(percentage=percentage)
           row1= spl.row()
           row2= spl.row()
        else:
           row1 = layout.row(align=True)
           row2 = row1

        row1.alignment='LEFT'             
        row1.operator('karaage.focus_on_selected', text="", icon='VISIBLE_IPO_ON', emboss=False).bname=key
        row1.operator('karaage.focus_on_selected', emboss=False, text="%s - (%s)" % (key, marker)).bname=key
        if percentage <1:

            h = 1000 * Vector(item.head)
            H = ("h:% 04d, % 04d, % 04d" % (h[0], h[1], h[2])) if armobj.RigProps.display_joint_heads else ""
            if len(H) > 0:
                row2.label(H)

            t = 1000 * Vector(item.tail)
            T = ("t:% 04d, % 04d, % 04d" % (t[0], t[1], t[2])) if armobj.RigProps.display_joint_tails else ""
            if len(T) > 0:
                row2.label(T)

def initialisation():

    bpy.types.Object.AnimProps = PointerProperty(type = AnimProps)
    bpy.types.Action.AnimProps = PointerProperty(type = AnimProps)
    bpy.types.Object.RigProps  = PointerProperty(type = RigProps)
    bpy.types.Armature.JointOffsetIndex = PointerProperty(type=JointOffsetPropIndex)
    bpy.types.Armature.JointOffsetList = CollectionProperty(type=JointOffsetProp)
    bpy.types.Scene.ExportActionsIndex = PointerProperty(type=ExportActionsPropIndex)
    bpy.types.Scene.ExportActionsList = CollectionProperty(type=ExportActionsProp)

def get_dependecies(master, key):
    dependencies = master.get(key, None)
    if dependencies == None:
        dependencies = {}
        master[key] = dependencies
    return dependencies

def add_dependency(arm, bone, constraint, drivers, drivenby):
 
    try:

        target     = constraint.target
        subtarget  = constraint.subtarget
    except:

        return

    if target == None or subtarget == '' or target != arm:

        return

    if subtarget in drivers and subtarget in drivenby:

        return

    slave  = bone.name
    master = subtarget

    bone_drivers = get_dependecies(drivers, slave)
    
    try:
        tbone = arm.pose.bones[subtarget]
        bone_drivers[slave] = tbone

        for sub_constraint in tbone.constraints:
            add_dependency(arm, tbone, sub_constraint, drivers, drivenby)
    except:
        if subtarget.startswith('ik'):
            log.debug("Found IK bone animation from %s" % subtarget)
        else:
            log.warning("Can not assign subtarget %s" % subtarget)
        
    driven_bones = get_dependecies(drivenby, master)    
    driven_bones[master] = bone
            
def init_dependencies(arm):
    dependencies = {}
    drivers      = {}
    drivenby     = {}

    dependencies['drivers']   = drivers
    dependencies['drivenby']  = drivenby

    for bone in arm.pose.bones:
        for constraint in bone.constraints:
            add_dependency(arm, bone, constraint, drivers, drivenby)
    return dependencies

def get_slaves(dependencies, master):
    drivenby = dependencies['drivenby']
    return drivenby.get(master, None)

def get_masters(dependencies, slave):
    drivers = dependencies['drivers']
    return drivers.get(slave, None)
    
def is_driven_by(dependencies, master, slave):
    drivenby = dependencies['drivenby']
    bone_drivers = drivenby[master.name]
    return slave.name in bone_drivers

def drives_other(dependencies, master, slave):
    drivers = dependencies['drivers']
    driven_bones = drivers[master.name]
    return slave.name in driven_bones

def get_props_from_action(armobj, action):
    props  = action.AnimProps if action else armobj.AnimProps
    return props
    
def get_props_from_arm(armobj):
    action = armobj.animation_data.action
    return get_props_from_action(armobj, action)
    
def get_props_from_obj(obj):
    arm    = util.get_armature(obj)
    return get_props_from_arm(arm)

def get_props_from_context(context):
    obj    = context.active_object
    return get_props_from_obj(obj)

def exportAnimation(action, filepath, mode):

    logging.debug("="*50)
    logging.debug(_("Export for %s animation"), mode)
    logging.debug(_("file: %s"), filepath)
    logging.debug("-"*50)

    ANIM = {}

    ANIM["version"]    = 1
    ANIM["subversion"] = 0

    ANIM["emote_name"] = ""

    context = bpy.context
    obj    = context.active_object
    arm    = util.get_armature(obj)
    scn    = context.scene
    props  = get_props_from_arm(arm)

    fps = scn.render.fps
    frame_start = scn.frame_start
    frame_end = scn.frame_end

    log.warning("animation: %4d frame_start" % (frame_start) )
    log.warning("animation: %4d frame_end" % (frame_end) )
    log.warning("animation: %4d fps" % (fps) )

    ANIM["fps"] = fps
    ANIM["frame_start"] = frame_start
    ANIM["frame_end"] = frame_end
    ANIM["duration"] = (frame_end-frame_start)/float(fps)

    meshes = util.findKaraageMeshes(obj)
    for key,name in (
                    ("express_tongue_out_301","express_tongue_out"),
                    ("express_surprise_emote_302","express_surprise_emote"),
                    ("express_wink_emote_303","express_wink_emote"),
                    ("express_embarrassed_emote_304","express_embarrassed_emote"),
                    ("express_shrug_emote_305","express_shrug_emote"),
                    ("express_kiss_306","express_kiss"),
                    ("express_bored_emote_307","express_bored_emote"),
                    ("express_repulsed_emote_308","express_repulsed_emote"),
                    ("express_disdain_309","express_disdain"),
                    ("express_afraid_emote_310","express_afraid_emote"),
                    ("express_worry_emote_311","express_worry_emote"),
                    ("express_cry_emote_312","express_cry_emote"),
                    ("express_sad_emote_313","express_sad_emote"),
                    ("express_anger_emote_314","express_anger_emote"),
                    ("express_frown_315","express_frown"),
                    ("express_laugh_emote_316","express_laugh_emote"),
                    ("express_toothsmile_317","express_toothsmile"),
                    ("express_smile_318","express_smile"),
                    ("express_open_mouth_632","express_open_mouth"),
                    ("express_closed_mouth_300",""),
                    ):

        try:

           if meshes["headMesh"].data.shape_keys.key_blocks[key].value !=0:
               emote = name if name != "" else "closed mouth"
               print("Setting emote to %s" % emote )
               ANIM["emote_name"] = name;
               break;
        except (KeyError, AttributeError): pass    

    ANIM["hand_posture"] = int(arm.RigProps.Hand_Posture)
    ANIM["priority"] = props.Priority

    if props.Loop:
        ANIM["loop"] = 1 
        ANIM["loop_in_frame"] = props.Loop_In
        ANIM["loop_out_frame"] = props.Loop_Out
    else:
        ANIM["loop"] = 0
        ANIM["loop_in_frame"] = 0
        ANIM["loop_out_frame"] = 0

    ANIM["ease_in"] = props.Ease_In
    ANIM["ease_out"] = props.Ease_Out
    ANIM["translations"] = props.Translations

    ANIM["reference_frame"] = props.ReferenceFrame

    if scn.MeshProp.applyScale:
        ANIM["apply_scale"] = True
        Marm = obj.matrix_world
        tl,tr,ts = Marm.decompose() 
        ANIM["armature_scale"] = ts
    else:
        ANIM["apply_scale"] = False

    ROTS, LOCS, BONE0 = collectBones(obj, context, with_translation=props.Translations)
    log.info("Found %d ROTS and %d LOCS" % (len(ROTS), len(LOCS)) )

    ANIM['ROTS'] = ROTS
    ANIM['LOCS'] = LOCS
    ANIM['BONE0'] = BONE0

    FRAMED = collectVisualTransforms(obj, context, ROTS, LOCS)

    if mode == 'anim':

        log.info("Simplify animation for armature %s..." % (arm.name))
        FRAMED = simplifyCollectedTransforms(arm, FRAMED, ROTS, LOCS)
        ANIM['FRAMED'] = FRAMED
        ANIM['BONES'], ANIM['CBONES'] = collectBoneInfo(obj, context, ROTS, LOCS) 
        log.info("Export to ANIM")
        exportAnim(arm, filepath, ANIM)

    else:

        ANIM['FRAMED'] = FRAMED
        ANIM['BONES'], ANIM['CBONES'] = collectBoneInfo(obj, context, ROTS, LOCS)         
        log.info("Export to BVH")
        exportBVH(arm, filepath, ANIM)

def collectBones(obj, context, with_translation):

    def get_regular_children_of(dbone):
        limbset = []
        while len(dbone.children) > 0:
            childset = [b for b in dbone.children if b.name[0] != 'a' and not b.name.startswith('ik')]
            if len(childset) == 1:
                dbone = childset[0]
                limbset.append(dbone.name)
        return limbset

    def get_bone_names_of_limb(ikbone):
        limbset = get_limb_from_ikbone(ikbone)
        if not limbset:
            return None
        return [key for key in limbset if not key.startswith('ik')]

    def add_bone_data(ROTS, LOCS, BONE0, obj, bonenames, use_bind_pose):
        for bonename in bonenames:
            if BONE0.get(bonename):

                continue

            dbone = obj.data.bones[bonename]
            if use_bind_pose:
                p0=Matrix(dbone['mat0']).to_translation()
                if bonename == "mPelvis":

                    p0p=p0
                else:
                    p0p=Matrix(dbone.parent['mat0']).to_translation()

            else:
                p0=dbone.matrix_local.to_translation()
                if bonename == "mPelvis":

                    p0p=p0
                else:
                    p0p=dbone.parent.matrix_local.to_translation()

            ds, s0 = util.get_bone_scales(dbone.parent)
            r0 = dbone.get('rot0', (0,0,0))
            rot0 = (r0[0], r0[1], r0[2])
            rh = dbone.get('relhead',(0,0,0))
            relhead = (rh[0], rh[1], rh[2])
            BONE0[bonename] = {'rot0'   : rot0,
                               'pscale0': s0,
                               'pscale' : ds,
                               'offset' : tuple(p0-p0p),
                               'relhead': relhead
                              }

            if bonename in ROTS or bonename in LOCS:

                continue

            ROTS.add(bonename)
            log.debug("1: Add ROT for %s" % bonename)

        return

    use_bind_pose = util.use_sliders(context) and obj.RigProps.rig_use_bind_pose
    action = obj.animation_data.action
    nla_tracks = obj.animation_data.nla_tracks

    ROTS = set()
    LOCS = set()
    BONE0 = {} # this will hold scale0 rot0 etc

    logging.debug(_("Collecting bones..."))

    solo = False
    if obj.animation_data.use_nla and len(nla_tracks)>0:

        tracks = []
        for track in nla_tracks:
            if track.is_solo:
                tracks = [track]
                solo = True
                break
            else:
                tracks.append(track)

        for track in tracks:
            if track.mute:
                logging.debug(_("    skipping muted track '%s'"), track.name)
                continue

            for strip in track.strips:
                if strip.mute:
                    logging.debug(_("    skipping muted strip '%s'"), strip.name)
                    continue

                if strip.action is not None:
                    R, L = collectActionBones(obj, strip.action, with_translation)
                    ROTS = ROTS.union(R)
                    LOCS = LOCS.union(L)

                logging.debug(_("    grabbing animated bones from NLA track '%s', strip '%s'"), track.name, strip.name)

    if action is not None and not solo: 
        logging.debug(_("    grabbing animated bones from Action '%s'"), action.name)
        R, L = collectActionBones(obj, action, with_translation)
        ROTS = ROTS.union(R)
        LOCS = LOCS.union(L)

    if len(ROTS)>0 or len(LOCS)>0:
        for bonename in set().union(ROTS).union(LOCS):
            dbone = obj.data.bones[bonename]

            if dbone.parent is None:

                continue

            add_bone_data(ROTS, LOCS, BONE0, obj, [bonename], use_bind_pose)

            if bonename in ALL_IK_BONES:
                log.debug("Find limb affected by %s" % (bonename) )
                limb_names = get_bone_names_of_limb(bonename)
                if limb_names and len(limb_names) > 0:
                    log.info("Add    Limb: %s (for IK %s)" % (limb_names, bonename))
                    add_bone_data(ROTS, LOCS, BONE0, obj, limb_names, use_bind_pose)

            if bonename[0:5] == "mHand":

                limb_names = get_regular_children_of(dbone)
                if limb_names and len(limb_names) > 0:
                    log.info("Add fingers: %s ( for root: %s)" % (limb_names, bonename))
                    add_bone_data(ROTS, LOCS, BONE0, obj, limb_names, use_bind_pose)

    return ROTS, LOCS, BONE0

def collectActionBones(obj, action, with_translation):

    ROTS = set()
    LOCS = set()

    arm = util.get_armature(obj)
    props = action.AnimProps
    dependencies = init_dependencies(arm)
    ignored_bones = set()

    for fc in action.fcurves:

        if fc.mute:

            logging.debug(_("    skipping muted channel: %s"), fc.data_path)
            continue

        mo = re.search('"([\w\. ]+)".+\.(rotation|location|scale)', fc.data_path)
        if mo is None:

            continue

        bonename = mo.group(1)
        keytype = mo.group(2)
        
        if bonename in ['Origin']:
            continue
        elif bonename in ['COG', 'PelvisInv']:

            bonename = 'Pelvis'
        elif bonename == 'EyeTarget' and keytype=='location':

            ROTS.add("mEyeLeft")
            ROTS.add("mEyeRight")
            log.debug("2: Add ROT for mEyeLeft/Righ")
            continue
        elif bonename == 'FaceEyeAltTarget' and keytype=='location':

            ROTS.add("mFaceEyeAltLeft")
            ROTS.add("mFaceEyeAltRight")
            log.debug("2: Add ROT for mFaceEyeAltLeft/Righ")
            continue

        if "m"+bonename in obj.data.bones:

            bonename = "m"+bonename
        elif not bonename in obj.data.bones:
            ignored_bones.add(bonename)
            continue

        if keytype=='rotation':
            ROTS.add(bonename)
            log.debug("3: Add ROT for %s" % bonename)
        elif keytype=='location' and ( props.Translations or bonename == 'mPelvis'):

            LOCS.add(bonename)
            log.debug("3: Add LOC for %s" % bonename)
        else:
            slaves = get_slaves(dependencies, bonename)
            if slaves:
                for slave in slaves.keys():
                    bn = "m" + slave if "m"+slave in obj.data.bones else slave

                    if bn[0] == 'm':
                        ROTS.add(bn)
                        log.debug("4: Add ROT for %s" % bn)

    if len(ignored_bones) > 0:
        log.warning("%d Bones refered in fcurves but missing in rig:" % (len(ignored_bones)))
        for name in ignored_bones:
            log.warning("- %s" % name)

    log.warning("Collected %d ROTS, %d LOCS" % (len(ROTS), len(LOCS)) )
    return ROTS, LOCS

def collectVisualTransforms(obj, context, ROTS, LOCS):

    ALL = {}

    BONES = set().union(ROTS).union(LOCS)
   
    scn   = context.scene
    arm   = util.get_armature(obj)
    props = get_props_from_arm(arm)

    frame_start = scn.frame_start
    frame_end = scn.frame_end
    logging.debug(_("Collecting visual transformations from frames %d-%d ..."), frame_start, frame_end)

    frame_original = scn.frame_current

    for frame in range(frame_start, frame_end+1):

        ALL[frame] = {}

        bpy.context.scene.frame_set(frame)

        for bonename in BONES:
            pbone = arm.pose.bones[bonename]
            dbone = arm.data.bones[bonename]

            matrix = visualmatrix(context, arm, dbone, pbone)
            ALL[frame][bonename] = matrix

    context.scene.frame_set(frame_original)

    return ALL

def simplifyCollectedTransforms(arm, ALL, ROTS, LOCS, tol=0.02):

    logging.debug(_("Simplifying bone curves (Lowes global method, tol=%f) ..."), tol)

    curve = []

    frames = list(ALL.keys())
    frames.sort()

    for frame in frames:
        point = [frame]

        for bone in ROTS:
            matrix = ALL[frame][bone]
            q = matrix.to_quaternion()
            point.extend(list(q))

        for bone in LOCS:
            matrix = ALL[frame][bone]

            l = 2*matrix.to_translation()
            point.extend(list(l))

        curve.append(point)

    sframes = simplifyLowes(curve, 0, len(curve)-1, set(), tol=tol)

    props = get_props_from_arm(arm)
    allframes = ALL.keys()

    if props.Loop:
        if props.Loop_In in allframes:
            sframes.add(props.Loop_In)
        if props.Loop_Out in allframes:
            sframes.add(props.Loop_Out)

    for marker in bpy.context.scene.timeline_markers:
        if marker.name == 'fix' and marker.frame in allframes:
            logging.debug("Keeping fixed frame %d", marker.frame)
            sframes.add(marker.frame) 

    Ni=len(curve)
    Nf=len(sframes)

    logging.debug(_("    keyframe simplification: %d -> %d (%.1f%% reduction)")%(Ni, Nf, round((1-Nf/Ni)*100) ) )

    SIMP = {}

    for frame in sframes:
        SIMP[frame] = ALL[frame]

    return SIMP

def collectBoneInfo(armobj, context, ROTS, LOCS):

    scn    = context.scene
    props  = get_props_from_obj(armobj)
    pbones = armobj.pose.bones

    BONES = {}
    CBONES = {}
    
    for bname in set().union(ROTS).union(LOCS):
        if bname.startswith("a") or bname.startswith("m") or 'm'+bname in pbones or bname in SLVOLBONES:
            BONES[bname] = {}
        else:
            CBONES[bname] = {}
            if bname.startswith('ik'):
                log.debug("IK Bone is not directly exported: %s (only its influence on FK Bones)" % (bname) )
            else:
                log.info("FK bone is not directly supported: %s (but can influence supported bones)" % (bname) )

    log.debug("collectBoneInfo: Found %d LOCS, %d ROTS %d BONES" % (len(LOCS), len(ROTS), len(BONES)) )
    for ROT in ROTS:
        log.debug("collectBoneInfo: ROT %s" % (ROT) )
    for LOC in LOCS:
        log.debug("collectBoneInfo: LOC %s" % (LOC) )
    for B in BONES:
        log.debug("collectBoneInfo: BON %s" % (B) )

    for bname in BONES.keys():

        B =  BONES[bname]
        B["name"] = bname

        try:        
            slpriority = clamp(pbones[bname]['priority'], NULL_BONE_PRIORITY, MAX_PRIORITY)
        except KeyError:
            slpriority = NULL_BONE_PRIORITY

        try:        
            if bname == 'mPelvis':
                pelvispriority = clamp(pbones['Pelvis']['priority'], NULL_BONE_PRIORITY, MAX_PRIORITY)
                pelvisinvpriority = clamp(pbones['PelvisInv']['priority'], NULL_BONE_PRIORITY, MAX_PRIORITY)
                if pelvispriority > NULL_BONE_PRIORITY:

                    rigpriority = pelvispriority
                else:
                    rigpriority = pelvisinvpriority

            else:
                rigpriority = clamp(pbones[bname[1:]]['priority'], NULL_BONE_PRIORITY, MAX_PRIORITY) # sans "m"

        except KeyError:
            rigpriority = NULL_BONE_PRIORITY

        if slpriority > NULL_BONE_PRIORITY:

            priority = slpriority 
        elif rigpriority > NULL_BONE_PRIORITY:

            priority = rigpriority
        else:

            priority = props.Priority 

        B["priority"] = priority

    return BONES, CBONES

def exportAnim(armobj, animationfile, ANIM):

    def get_export_bone_set(armobj, ANIM):
        export_bones = {}
        for B in ANIM["BONES"].values():
            bname = B["name"]
            export_name = 'm'+bname if 'm'+bname in armobj.data.bones else bname

            if export_name in export_bones.keys():
                log.warning("%s already exported using data from %s" % (bname, export_name))
                continue

            BDATA = {}
            for f in ANIM["FRAMED"]:
                if bname in ANIM["FRAMED"][f]:
                    BDATA[f] = ANIM["FRAMED"][f][bname]

            if len(BDATA) == 0:
                log.warning("%s has no animation data" % (bname))
                continue

            ename = export_name[1:] if export_name[0]=="a" else export_name
            export_bones[ename]=[B, BDATA]

        return export_bones

    buff = open(animationfile, "wb")

    data = pack("HHif", ANIM["version"] , ANIM["subversion"], ANIM["priority"], ANIM["duration"])
    buff.write(data)

    data = pack("%dsB"%len(ANIM["emote_name"]), bytes(ANIM["emote_name"], 'utf8'), 0)
    buff.write(data)

    loop_in_point = (ANIM["loop_in_frame"]-ANIM["frame_start"])/float(ANIM["fps"])
    loop_out_point = (ANIM["loop_out_frame"]-ANIM["frame_start"])/float(ANIM["fps"])

    export_bones = get_export_bone_set(armobj, ANIM)
    other_bones = ANIM["CBONES"].keys()
    
    data = pack("ffiffii",
                loop_in_point,
                loop_out_point,
                ANIM["loop"],
                ANIM["ease_in"],
                ANIM["ease_out"],
                ANIM["hand_posture"],
                len(export_bones))
    buff.write(data)

    duration = ANIM['duration']
    log.info("+-----------------------------------------------------------------")
    log.info("| Export Summary for %s" % animationfile)
    log.info("+-----------------------------------------------------------------")
    log.info("| Duration: %.2f sec, Priority: %d, Hands: '%s', Emote: '%s'"%(ANIM["duration"], ANIM["priority"], ANIM["hand_posture"], ANIM["emote_name"]))
    log.info("| Loop: %d, In: %.2f sec, Out: %.2f sec"%(ANIM["loop"],loop_in_point, loop_out_point))
    log.info("| Ease In: %.2f sec, Ease Out: %.2f sec"%(ANIM["ease_in"],ANIM["ease_out"]))
    log.info("| Hand pose: %s" % (ANIM["hand_posture"]) )
    log.info("+-----------------------------------------------------------------")
    log.info("| used Bones    %4d" % (len(export_bones)) )
    log.info("| related Bones %4d (indirectly used)" % (len(other_bones))  )
    log.info("| Rotations     %4d (from used and related bones)" % (len(ANIM['ROTS'])) )
    log.info("| Locations     %4d (from used and related bones)" % (len(ANIM['LOCS'])) )
    log.info("|")
    log.info("| Startframe    %4d" % ANIM["frame_start"] )
    log.info("| Endframe      %4d" % ANIM["frame_end"] )
    log.info("| fps           %4d" % ANIM["fps"] )
    log.info("+-----------------------------------------------------------------")

    for ename, bdata in export_bones.items():
        B = bdata[0]
        BDATA = bdata[1]
        bname = B["name"]
        frames = list(BDATA.keys())
        frames.sort()

        data = pack("%dsB"%len(ename), bytes(ename,'utf8') , 0)
        buff.write(data)

        data = pack("i", B["priority"])
        buff.write(data)

        rotloc = "%s%s" % ( 'ROT' if bname in ANIM['ROTS'] else '',
                            'LOC' if bname in ANIM['LOCS'] else '')

        log.debug("Export %d frames for bone %s (%s)" % (len(BDATA), ename, rotloc))

        has_data = False
        if bname in ANIM['ROTS']:
            has_data = True
            log.debug("Export ROT data of Bone %s" % (ename) )

            data = pack("i", len(BDATA))
            buff.write(data)

            for f in frames:

                #
                
                matrix = BDATA[f].copy()

                t = (f-ANIM["frame_start"])/float(ANIM["fps"])
                time = F32_to_U16(float(t), 0, duration)
                data = pack("H",time)
                buff.write(data)

                euler = None
                try:
                    r0 = ANIM['BONE0'][bname]['rot0']
                    rot0 = (r0[0], r0[1], r0[2])
                    euler = Euler(rot0,'ZYX')
                except:
                    log.warning("%s.rot0 seems broken. use (0,0,0)" % (bname) )
                    euler = Euler((0,0,0),'ZYX')

                M3    = euler.to_matrix()
                R     = M3.to_4x4() # this is RxRyRz
                q     = ( Rz90I*matrix*R*Rz90 ).to_quaternion().normalized()

                x = F32_to_U16(q.x, -1, 1)
                y = F32_to_U16(q.y, -1, 1)
                z = F32_to_U16(q.z, -1, 1)
                data = pack("HHH", x, y, z)

                buff.write(data)

        else:

            data = pack("i", 0)
            buff.write(data)

        if bname in ANIM['LOCS']:
            has_data = True
            log.debug("Export LOC data of Bone %s" % (ename) )

            data = pack("i", len(BDATA))
            buff.write(data)

            for f in frames:
                matrix = BDATA[f].copy()

                t = (f-ANIM["frame_start"])/float(ANIM["fps"])
                time = F32_to_U16(float(t), 0, duration)
                data = pack("H",time)
                buff.write(data)

                abone  = ANIM['BONE0'][bname]
                try:
                    rot0   = abone['rot0'] if 'rot0' in abone else Vector((0,0,0))
                    psx0, psy0, psz0 = abone['pscale0'] if 'pscale0' in abone else Vector((1,1,1))
                    psx,  psy,  psz  = abone['pscale']  if 'pscale' in abone else Vector((1,1,1))
                    L0     = Vector(abone['relhead']) if 'relhead' in abone else Vector((0,0,0))
                    offset = Vector(abone['offset'])  if 'offset' in abone else Vector((0,0,0))
                except:
                    log.warning("Data corruption in bone [%s]" % (L0) )
                    raise

                R = Euler(rot0,'ZYX').to_matrix().to_4x4() # this is RxRyRz
                S = Matrix()
                if ANIM.get('apply_scale', False):
                    ts = ANIM['armature_scale'] 
                else:
                    ts = (1,1,1)
                S[0][0] = ts[0]/(psx0+psx)
                S[1][1] = ts[1]/(psy0+psy)
                S[2][2] = ts[2]/(psz0+psz)

                L = matrix.to_translation()

                L = Rz90.inverted()*S*R*(L+offset)   

                #

                x = F32_to_U16(L.x/LL_MAX_PELVIS_OFFSET, -1, 1)
                y = F32_to_U16(L.y/LL_MAX_PELVIS_OFFSET, -1, 1)
                z = F32_to_U16(L.z/LL_MAX_PELVIS_OFFSET, -1, 1)

                data = pack("HHH",x, y, z)

                buff.write(data)

        else:

            data = pack("i", 0)
            buff.write(data)

        if not has_data:
            log.warning ("Bone %s ignored (has no animation data)" % (ename) )
    #

    #

    #

    #

    #

    data = pack("i",0)
    buff.write(data)

    buff.close()

    logging.debug("-"*50)
    logging.info(_("Wrote animation to %s")%animationfile)

def get_bvh_name(bone):
    if 'bvhname' in bone:
        return bone['bvhname']
    elif bone.name.startswith("m"):
        return bone.name
    else:
        return None

def exportBVH(armobj, animationfile, ANIM):
    dbones = armobj.data.bones

    buff = open(animationfile, "w")

    buff.write("HIERARCHY\n")
    buff.write("ROOT hip\n{\n")
    buff.write("\tOFFSET 0.00 0.00 0.00\n")
    buff.write("\t" + ALL_CHANNELS + "\n")
  
    hierarchy = ['mPelvis'] 
    for child in dbones['mPelvis'].children:
        if get_bvh_name(child):
            hierarchy.extend(bvh_hierarchy_recursive(buff, child, ANIM['LOCS'], 1))

    buff.write("}\n")

    ref = ANIM["reference_frame"]

    frame_time = 1/float(ANIM['fps'])
    frames = ANIM['frame_end']-ANIM['frame_start']+1+ref
    buff.write("MOTION\nFrames: %d\nFrame Time: %f\n"%(frames,frame_time))

    logging.debug("-"*50)
    logging.debug(_("Summary for %s")%animationfile)
    logging.debug("-"*50)
    logging.debug(_("Frames: %d at %d fps. Frame time: %.2f")%(frames, ANIM["fps"], frame_time))

    FRAMED = ANIM['FRAMED']

    summary = {'mPelvis loc':[]}
    for name in hierarchy:
        summary[name] = []
        summary['%s loc'%name] = []

    if ref:
        logging.debug(_("Prepending reference frame"))
        FBONES = FRAMED[ANIM['frame_start']]
        
        rotinfo=""
        for export_name in hierarchy:
            name = export_name
            if export_name not in FBONES:
                name = export_name[1:]

            if name in ANIM['LOCS'] or name == 'Pelvis':
                if name in FBONES:
                    matrix = FBONES[name]
                    loc = BLtoBVH*matrix.to_translation()
                    if abs(loc.x)<0.1 and abs(loc.y)<0.1 and abs(loc.z)<0.1:
                        loc = (0.0, 0.0, loc.z+0.1)
                    else: 
                        loc = (0.0, 0.0, 0.0)
                else:
                    loc = (0.0, 0.0, 0.0)
                buff.write('%.4f %.4f %.4f '%(loc[0],loc[1],loc[2]))
                summary['%s loc'%export_name].append("\tref: %.3f %.3f %.3f"%(loc[0], loc[1], loc[2]))

            if name in FBONES:
                matrix = FBONES[name]
                r = Vector(matrix.to_euler('ZYX'))/DEGREES_TO_RADIANS
                if abs(r.x)<1 and abs(r.y)<1 and abs(r.z)<1:
                    rot = (r.x+1.0, 0.0, 0.0)
                else:
                    rot = (0.0, 0.0, 0.0)
            else:
                rot = (0.0, 0.0, 0.0)
            buff.write('%.4f %.4f %.4f '%(rot[0],rot[1],rot[2]))
            summary[export_name].append("\tref: %.3f %.3f %.3f"%(rot[0],rot[1],rot[2]))
        buff.write("\n")
    
    frames = list(FRAMED.keys())
    frames.sort()
    for frame in frames:

        FBONES = FRAMED[frame]

        rotinfo=""
        for export_name in hierarchy:
            name = export_name
            if export_name not in FBONES:
                name = export_name[1:]

            if name in ANIM['LOCS'] or name == 'Pelvis':
                if name in FBONES:
                    matrix = FBONES[name]
                    psx, psy, psz = ANIM['BONE0'][name]['pscale']
                    S = Matrix()
                    
                    if ANIM.get('apply_scale', False):
                        ts = ANIM['armature_scale']
                    else:
                        ts = (1,1,1)
                   
                    S[0][0] = ts[0]/(1+psx)
                    S[1][1] = ts[1]/(1+psy)
                    S[2][2] = ts[2]/(1+psz)

                    R = Matrix() #maybe rot0 ?
                    abone  = ANIM['BONE0'][name]
                    offset = Vector(abone['offset'])  if 'offset' in abone else Vector((0,0,0))
                    L = matrix.to_translation()
                    loc = BLtoBVH*S*R*(L+offset)/INCHES_TO_METERS

                    if "Ring1" in name:
                        log.warning("%d: %s %s" % (frame, loc, name) )

                else:

                    loc = (0.0, 0.0, 0.0)

                buff.write('%.4f %.4f %.4f '%(loc[0], loc[1], loc[2]))
                summary['%s loc'%export_name].append("\t%d: %.3f %.3f %.3f"%(frame, loc[0], loc[1], loc[2]))

            if name in FBONES:
                matrix = FBONES[name]
                matrix = BLtoBVH*matrix*BLtoBVH.inverted()

                #

                r = matrix.to_euler('ZYX')

                rx,ry,rz = tuple(Vector(r)/DEGREES_TO_RADIANS)

                rx = round(rx,4)            
                ry = round(ry,4)            
                rz = round(rz,4)            
                if rx ==0: rx=0.0
                if ry ==0: ry=0.0
                if rz ==0: rz=0.0
            else:

                rx, ry, rz = 0.0, 0.0, 0.0

            buff.write('%.4f %.4f %.4f '%(rx,ry,rz))
            summary[export_name].append("\t%d: %.3f %.3f %.3f"%(frame, rx, ry, rz))
        buff.write("\n")
 
    buff.close()
    for bname in summary:
        logging.debug(bname)
        for line in summary[bname]:
            logging.debug(line)
    logging.debug("-"*50)
    logging.info(_("Wrote animation to %s")%animationfile)
    
    export_bones = ANIM["BONES"].keys()
    other_bones = ANIM["CBONES"].keys()
    
    log.info("+-----------------------------------------------------------------")
    log.info("| Export Summary for %s" % animationfile)
    log.info("+-----------------------------------------------------------------")
    log.info("| used Bones    %4d" % (len(export_bones)) )
    log.info("| related Bones %4d (indirectly used)" % (len(other_bones))  )
    log.info("| Rotations     %4d (from used and related bones)" % (len(ANIM['ROTS'])) )
    log.info("| Locations     %4d (from used and related bones)" % (len(ANIM['LOCS'])) )
    log.info("|")
    log.info("| Startframe    %4d" % ANIM["frame_start"] )
    log.info("| Endframe      %4d" % ANIM["frame_end"] )
    log.info("| fps           %4d" % ANIM["fps"] )
    log.info("+-----------------------------------------------------------------")

def get_used_channels(bone, LOCS):

    cc = 3
    loc_channels = ''

    if bone.name in LOCS:
        cc +=3
        loc_channels = LOC_CHANNELS

    used_channels = BVH_CHANNELS_TEMPLATE % (cc, loc_channels, ROT_CHANNELS)
    return used_channels

def bvh_hierarchy_recursive(buff, bone, LOCS, lvl=0):

    bvhname = get_bvh_name(bone)
    if bvhname == None:
        return []

    channels = get_used_channels(bone, LOCS)

    buff.write("\t"*lvl+"JOINT %s\n"%bvhname)
    buff.write("\t"*lvl+"{\n")

    hl = bone.head_local
    phl = bone.parent.head_local
    offset = BLtoBVH*(hl-phl)/INCHES_TO_METERS
    buff.write("\t"*(lvl+1)+"OFFSET %.4f %.4f %.4f\n"%tuple(offset))
    buff.write("\t"*(lvl+1) + channels + "\n")
    hierarchy = [bone.name]
    children = 0
    for child in bone.children:
        if get_bvh_name(child):
            children += 1
            hierarchy.extend(bvh_hierarchy_recursive(buff, child, LOCS, lvl+1))
    if children == 0:
        buff.write("\t"*(lvl+1)+"End Site\n")
        buff.write("\t"*(lvl+1)+"{\n")
        offset = BLtoBVH*Vector(bone['reltail'])/INCHES_TO_METERS
        buff.write("\t"*(lvl+2)+"OFFSET %.4f %.4f %.4f\n"%tuple(offset))
        buff.write("\t"*(lvl+1)+"}\n")

    buff.write("\t"*lvl+"}\n")

    return hierarchy

def getReferenceOffset(context, src_armobj, tgt_armobj, translations, frame=None):
    src_ppos = src_armobj.data.pose_position
    tgt_ppos = tgt_armobj.data.pose_position

    if frame:
        context.scene.frame_set(frame)

    else:
        src_armobj.data.pose_position='REST'
        tgt_armobj.data.pose_position='REST'

    sbones = src_armobj.pose.bones
    tbones = tgt_armobj.pose.bones

    MWS = src_armobj.matrix_world
    MWT = tgt_armobj.matrix_world

    Goffset = Matrix()

    for anim_map in translations:
        tgt_bname = anim_map.target
        if tgt_bname=="COG":

            src_bname = anim_map.source
            spbone = sbones[src_bname]
            tpbone = tbones[tgt_bname]

            m10 = spbone.matrix
            m20 = tpbone.matrix

            l1 = (MWS*m10).to_translation()
            l2 = (MWT*m20).to_translation()

            Goffset = Matrix.Translation(l2-l1)

            break

    src_armobj.data.pose_position = src_ppos
    tgt_armobj.data.pose_position = tgt_ppos

    return Goffset

def setReference(context, src_armobj, tgt_armobj, translations, frame=None):

    src_ppos = src_armobj.data.pose_position
    tgt_ppos = tgt_armobj.data.pose_position

    if frame:
        context.scene.frame_set(frame)
    else:
        src_armobj.data.pose_position='REST'
        tgt_armobj.data.pose_position='REST'

    sbones = src_armobj.pose.bones
    tbones = tgt_armobj.pose.bones

    MWS = src_armobj.matrix_world
    MWT = tgt_armobj.matrix_world

    Goffset = getReferenceOffset(bpy.context, src_armobj, tgt_armobj, translations, frame=frame)

    for anim_map in translations:
        sbone = sbones[anim_map.source]
        tbone = tbones[anim_map.target]
        
        m10 = sbone.matrix
        m20 = tbone.matrix
            
        anim_map.offset  = m10.inverted()*MWS.inverted()*Goffset*MWT*m20
        anim_map.Goffset = Goffset
        
    src_armobj.data.pose_position = src_ppos
    tgt_armobj.data.pose_position = tgt_ppos
        
    return translations   

def transferMotion(source, target, translation, reference_frame, start_frame, end_frame, prop):

    util.progress_begin(0,10000)
    progress = 0
    util.progress_update(progress)

    W1 = source.matrix_world
    W2 = target.matrix_world
    
    #

    #
    log.warning("transferMotion: reading source transformations")
    for frame in range(start_frame, end_frame+1):

        if frame == reference_frame:

            continue
        
        bpy.context.scene.frame_set(frame)

        for bone in translation:
            
            b1 = source.pose.bones[bone.source]

            m1 = b1.matrix
            
            if bone.target=="COG":
                m2 = W2.inverted()*bone.Goffset*W1*m1
                loc0, rot0, scl0 = m2.decompose()
                
                m2 = m2*bone.offset
                loc, rot, scl = m2.decompose()
                
                bone.frames[frame] = [loc0, rot]
                
            else:
                m2 = W2.inverted()*bone.Goffset*W1*m1*bone.offset
                
                loc, rot, scl = m2.decompose()
                
                bone.frames[frame] = [loc, rot]

    #

    #

    #

    #

    util.progress_update(progress)

    if prop.seamlessRotFrames>0 or prop.seamlessLocFrames>0:
        log.warning("transferMotion: adjusting motion at end to make seamless")
        for bone in translation:
            makeSeamless(bone,prop.seamlessLocFrames, prop.seamlessRotFrames)    

    #

    #

    util.progress_update(progress)
    
    if prop.simplificationMethod == "loweslocal":
        log.warning("transferMotion: simplifying bone curves (Lowes local method, tol=%f)" % (prop.lowesLocalTol))
        Ni=Nf=0
        for bone in translation:
            curve = []
            
            for frame in bone.frames:
                point = [frame]
                if bone.target=="COG":
                    point.extend(bone.frames[frame][0])
                
                point.extend(bone.frames[frame][1])
                curve.append(point)

            bone.sframes = simplifyLowes(curve, 0, len(curve)-1, set(),tol=prop.lowesLocalTol)

            Ni+=len(curve)
            Nf+=len(bone.sframes)
        log.warning("transferMotion: total keyframes on all bones: %d -> %d (%.1f%% reduction)" %(Ni, Nf, round((1-Nf/Ni)*100) ) )

    elif prop.simplificationMethod == "lowesglobal":
        log.warning("transferMotion: simplifying bone curves (Lowes global method, tol=%f)"%(prop.lowesGlobalTol))

        Ni=Nf=0
        curve = []

        for frame in range(start_frame, end_frame+1):

            if frame == reference_frame:

                continue

            point = [frame]
            for bone in translation:
                try:
                    if bone.target=="COG":
                        point.extend(bone.frames[frame][0])
                    point.extend(bone.frames[frame][1])
                except:
                    log.warning("Frame %d has no record for bone %s " % (frame, bone.target))
                    pass
            curve.append(point)

        sframes = simplifyLowes(curve, 0, len(curve)-1, set(),tol=prop.lowesGlobalTol)
        Ni+=len(curve)
        Nf+=len(sframes)
        for bone in translation:
            bone.sframes = sframes

        log.warning("transferMotion: total keyframes on all bones: %d -> %d (%.1f%% reduction)" % (Ni, Nf, round((1-Nf/Ni)*100) ) )
    else:

        for bone in translation:
            bone.sframes = bone.frames.keys()

    #

    #

    util.progress_update(progress)

    log.warning("transferMotion: writing target rotations in range [%d - %d]" % (start_frame, end_frame) )
    for frame in range(start_frame, end_frame+1):

        if frame == reference_frame:

            continue
        
        progress += 1
        util.progress_update(progress)
        for bone in translation:
            
            if frame not in bone.sframes:
                continue

            b2 = target.pose.bones[bone.target]
            
            loc, rot = bone.frames[frame] 
            
            if bone.target=="COG":

                b2.matrix = Matrix.Translation(loc)
                b2.keyframe_insert(data_path="location", index=-1, frame=frame)

            b2.matrix = rot.to_matrix().to_4x4()
            b2.keyframe_insert(data_path="rotation_quaternion", index=-1, frame=frame)

            bpy.context.scene.update()
            
    bpy.context.scene.frame_set(start_frame)
        
    util.progress_end()

class BoneTarget:
    
    def __init__(self, **keys):
        
        for key,value in keys.items():
            setattr(self,key,value) 

def simplifyLowes(curve, i,f, simplified, tol=.1):

    #

    pl1 = curve[i]
    pl2 = curve[f]
    
    simplified.add(pl1[0])
    simplified.add(pl2[0])
    
    maxd = 0
    maxi = 0

    for ii in range(i+1,f):
        p = curve[ii]
        d = distanceToLine(p,pl1,pl2)
        if d > maxd:
            maxd = d
            maxi = ii
            
    if maxd > tol:
        
        if maxi==f-1:
            simplified.add(curve[maxi][0])
        else:
            simplified = simplifyLowes(curve, maxi, f, simplified, tol=tol)

        if maxi==i+1:
            simplified.add(curve[maxi][0])
        else:
            simplified = simplifyLowes(curve, i, maxi, simplified, tol=tol)

    return simplified

def makeSeamless(bone, loc_frames, rot_frames):

    F = list(bone.frames.keys())
    F.sort()

    if loc_frames>0:
        for ii in range(len(bone.frames[F[0]][0])):
        
            p0 = bone.frames[F[0]][0][ii]
            p1 = bone.frames[F[-1]][0][ii]
      
            bone.frames[F[-1]][0][ii]=p0
    
            for f in range(loc_frames):
                bone.frames[F[-(f+2)]][0][ii]+=(loc_frames-f)*(p0-p1)/float(loc_frames+1)
                
    if rot_frames>0:
        for ii in range(len(bone.frames[F[0]][1])):
            p0 = bone.frames[F[0]][1][ii]
            p1 = bone.frames[F[-1]][1][ii]
      
            bone.frames[F[-1]][1][ii]=p0
    
            for f in range(rot_frames):
                bone.frames[F[-(f+2)]][1][ii]+=(rot_frames-f)*(p0-p1)/float(rot_frames+1)

def find_animated_bones(arm):
    bones = {}
    try:
        for fcurve in arm.animation_data.action.fcurves:
            bone_name = fcurve.group.name
            if bone_name not in bones and bone_name in arm.data.bones:
                co=None
                for point in fcurve.keyframe_points:
                    if co == None:
                        co = point.co
                    elif co == point.co:
                        continue
                    else:
                        bones[bone_name]=bone_name
                        break
    except:
        pass
        
    return bones

class AvatarAnimationTrimOp(bpy.types.Operator):
    bl_idname = "karaage.action_trim"
    bl_label = "Trim Timeline"
    bl_description ="Adjust start frame and end frame to action frame range"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        active = context.active_object
        if active:
            arm = util.get_armature(active)
            if arm:
                animation_data = arm.animation_data
                if animation_data:
                    action = arm.animation_data.action
                    return action != None

    def execute(self, context):
        arm = util.get_armature(context.active_object)
        action = arm.animation_data.action
        scn=context.scene
        fr = action.frame_range
        scn.frame_start, scn.frame_end = fr[0], fr[1]
        prop = action.AnimProps

        prop.frame_start = fr[0]
        prop.frame_end = fr[1]

        if prop.Loop_In < fr[0]:
            prop.Loop_In = fr[0]
        if fr[0] > prop.Loop_Out:
            prop.Loop_Out = fr[0]
        if fr[1] <= prop.Loop_Out:
            prop.Loop_Out = fr[1]
        prop.Loop = prop.Loop_Out == prop.Loop_In
        return {'FINISHED'}

class ImportAvatarAnimationOp(bpy.types.Operator, ImportHelper):
    bl_idname = "karaage.import_avatar_animation"
    bl_label = "SL Animation (bvh)"
    bl_description =_("Create new default Karaage Character and import bvh")
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".bvh"
    files = CollectionProperty(type=bpy.types.PropertyGroup)

    filter_glob = StringProperty(
            default="*.bvh",
            options={'HIDDEN'},
            )

    rigtypes = [
       ('BASIC', "Basic", "This Rig type Defines the Legacy Rig:\nThe basic Avatar with 26 Base bones and 26 Collision Volumes"),
       ('EXTENDED', "Extended", "This Rig type Defines the extended Rig:\nNew bones for Face, Hands, Tail, Wings, ... (the Bento rig)"),
    ]
    rigtype = EnumProperty(
        items       = rigtypes,
        name        = "Rig Type",
        description = "Basic: Old Avatar Skeleton, Extended: Bento Bones",
        default     = 'EXTENDED')

    reference_frame = IntProperty(name='Refernece Frame', min=0, default=0, description="In the reference frame the poses of the source and the target match best to each other.\nWe need this match pose to find the correct translations\nbetween the source animation and the target animation")
    use_restpose    = BoolProperty(name="Use Restpose", default=True, description = "Assume the restpose of the source armature\nmatches best to the current pose of the target armature.\nHint:Enable this option when you import animations\nwhich have been made for SL.")
    with_translation = BoolProperty(name="with Translation", default=True, description = "Prepare the Rig to allow translation animation")
    
    @classmethod
    def poll(self, context):
        if context.active_object:
            return context.active_object.mode == 'OBJECT'
        return True

    def draw(self, context):

        armobj = None
        obj = context.object
        if obj:
            armobj = util.get_armature(obj)

        layout = self.layout
        col = layout.column()
        if armobj:
            col.label('Assign to Armature')
        else:
            col.label('Import with Rig')
            row=layout.row(align=True)
            row.prop(self,"rigtype",expand=True)

        col = layout.column()
        col.prop(self,'reference_frame')
        col.enabled= not self.use_restpose

        col = layout.column()
        col.prop(self,'use_restpose')
        col.prop(self,'with_translation')
        
    @staticmethod
    def exec_imp(context, target, filepath, use_restpose, reference_frame, with_translation=True):
        scn = context.scene
        print("BVH Load from :", filepath)

        bpy.ops.import_anim.bvh(filepath=filepath)
        source = context.object
        util.match_armature_scales(source, target)

        source_action = ImportAvatarAnimationOp.exec_trans(context, source, target, use_restpose, reference_frame, with_translation)

        scn.objects.unlink(source)
        bpy.data.objects.remove(source)
        util.remove_action(source_action, do_unlink=True)

    @staticmethod
    def exec_trans(context, source, target, use_restpose, reference_frame, with_translation=True):
    
        def set_restpose(target):
            ll = [l for l in target.data.layers]
            target.data.layers=[True]*32
            omode = util.ensure_mode_is('POSE')
            bpy.ops.pose.select_all(action='SELECT')
            bpy.ops.pose.transforms_clear()
            target.data.layers=ll
            return ll
            
        oselect_modes = util.set_mesh_select_mode((False,True,False))
        ll = None
        if use_restpose:
            reference_frame = 0
            context.scene.frame_set(0)

            context.scene.objects.active = source
            omode = util.ensure_mode_is('POSE')
            bpy.ops.pose.select_all(action='SELECT')
            bpy.ops.pose.rot_clear()
            bpy.ops.anim.keyframe_insert_menu(type='Rotation')
            source_action      = source.animation_data.action
            action_name        = source_action.name
            source_action.name = "%s_del" % action_name
            util.ensure_mode_is(omode)

            context.scene.objects.active = target
            ll = set_restpose(target)

        else:
            context.scene.objects.active = source
            omode = util.ensure_mode_is('POSE')
            source_action      = source.animation_data.action
            action_name        = source_action.name
            source_action.name = "%s_del" % action_name
            util.ensure_mode_is(omode)

            context.scene.objects.active = target
            omode = util.ensure_mode_is('POSE')
        
        log.warning("import_avatar_animation.exec_trans: Create new action with name %s" % (action_name))
        if target.animation_data is None:
            target.animation_data_create()

        action = bpy.data.actions.new(action_name)
        action.use_fake_user=True
        target.animation_data.action = action
        bpy.ops.anim.keyframe_insert_menu(type='Rotation')
        util.ensure_mode_is(omode)

        scn = context.scene
        prop = scn.MocapProp
        set_best_match(prop, source, target)

        frame_range = source.animation_data.action.frame_range
        scn.frame_start = frame_range[0]
        scn.frame_end   = frame_range[1]

        log.warning("import_avatar_animation.exec_trans: Transfer motion to action %s" % (action_name))
        if with_translation:
            bpy.ops.karaage.armature_unlock_loc(reset_pose=True)
        transfer_motion(context, source, target, prop, reference_frame)
        if with_translation:
            set_restpose(target)

        util.set_mesh_select_mode(oselect_modes)
        return source_action

    def execute(self, context):

        armobj = None
        obj = context.object
        if obj:
            armobj = util.get_armature(obj)
        if not armobj:
            armobj = create.createAvatar(context, rigType=self.rigtype)
            shape.resetToRestpose(armobj, context)
            armobj.RigProps.Hand_Posture = '0'

        folder = (os.path.dirname(self.filepath))

        with set_context(context, armobj, 'POSE'):
            for i in self.files:

                filepath = (os.path.join(folder, i.name))
                print("Importing", filepath)
                try:
                    ImportAvatarAnimationOp.exec_imp(context, armobj, filepath, self.use_restpose, self.reference_frame, self.with_translation)
                except Exception as e:
                    print("Error importing",filepath)
                    raise e
        return {'FINISHED'}
