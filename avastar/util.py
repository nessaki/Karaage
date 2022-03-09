#
#
#
#
#
#
#
#
#

from collections import namedtuple
import logging, traceback
import bpy, sys, os, gettext
from math import radians, sqrt, pi
from mathutils import Vector, Matrix, Quaternion, Color
import bmesh
from bpy.app.handlers import persistent
from bpy.props import *
from . import bl_info, const, messages
from .const import *
import time, shutil

LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locale')
TMP_DIR    = os.path.join(os.path.dirname(__file__), 'tmp')
DATAFILESDIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),'lib')

translator = gettext.translation('karaage', LOCALE_DIR, fallback=True)
_ = translator.gettext

log = logging.getLogger("karaage.util")
timerlog = logging.getLogger("karaage.timer")

SEVERITY_ERROR          = "ERROR"
SEVERITY_MESH_ERROR     = "ERROR"
SEVERITY_ARMATURE_ERROR = "ERROR"
SEVERITY_WARNING        = "WARNING"
SEVERITY_INFO           = "INFO"
MIN_VERSION             = 63
SVN = -1

IN_USER_MODE = True
def set_operate_in_user_mode(mode):
    global IN_USER_MODE
    omode = IN_USER_MODE
    if IN_USER_MODE != mode:

        IN_USER_MODE = mode
    return omode

def is_in_user_mode():
    global IN_USER_MODE
    return IN_USER_MODE

tic = time.time()
toc = tic
def tprint(s):
    global tic, toc
    toc = time.time()
    print( "%0.6f | %s" % (toc-tic, s))
    tic = toc

def draw_info_header(layout, link, msg="panel|the awesome message", emboss=False, icon='INFO', op=None, is_enabled=None):
    preferences = getAddonPreferences()
    if preferences.verbose:
        prop = layout.operator("karaage.generic_info_operator", text="", icon=icon, emboss=emboss)
        prop.url=link
        prop.msg=msg
        prop.type=SEVERITY_INFO
        
        if op and is_enabled:
            layout.prop(op, is_enabled, text="")

class GenericInfoOperator(bpy.types.Operator):
    bl_idname      = "karaage.generic_info_operator"
    bl_label       = _("Infobox")
    bl_description = "Click icon to open extended tooltip"
    bl_options = {'REGISTER', 'UNDO'}
    msg        = StringProperty(default="brief|long|link")
    url        = StringProperty(default=BENTOBOX)
    type       = StringProperty(default=SEVERITY_INFO)

    def execute(self, context):
        ErrorDialog.dialog(self.msg+"|"+self.url, self.type)
        return {"FINISHED"}

class WeightmapInfoOperator(bpy.types.Operator):
    bl_idname      = "karaage.weightmap_info_operator"
    bl_label       = _("weightmap info")
    bl_description = "Number of accepted/denied Bone deforming weightmaps (click icon for details)"

    msg        = StringProperty()
    icon       = StringProperty()

    def execute(self, context):
        ErrorDialog.dialog(self.msg, self.icon)
        return {"FINISHED"}

class TrisInfoOperator(bpy.types.Operator):
    bl_idname      = "karaage.tris_info_operator"
    bl_label       = _("Tricount info")
    bl_description = "Number of used Tris (click icon for details)"

    msg        = StringProperty()
    icon       = StringProperty()
    
    def execute(self, context):
        ErrorDialog.dialog(self.msg, self.icon)
        return {"FINISHED"}

def missing_uv_map_text(targets):
    nwo   = ""
    no_uv_layers = 0
    for obj in [o for o in targets if o.data.uv_layers.active == None]:
        no_uv_layers += 1
        nwo += "* " + obj.name+"\n"
    msg= messages.msg_missing_uvmaps % (no_uv_layers, pluralize("Mesh", no_uv_layers), nwo)
    return msg
        
class UVmapInfoOperator(bpy.types.Operator):
    bl_idname      = "karaage.uvmap_info_operator"
    bl_label       = _("UVmap info")
    bl_description = "Number of missing UV maps (click icon for details)"

    msg        = StringProperty()
    icon       = StringProperty()
    
    def execute(self, context):
        ErrorDialog.dialog(self.msg, self.icon)
        return {"FINISHED"}

class Ticker:
    def __init__(self, fire = 100):
        self._fire   = fire
        self._ticker = 0

    @property
    def tick(self):
        self._ticker += 1

    @property
    def fire(self):
        return (self._ticker % self._fire) == 0

bpy.types.Scene.ticker = Ticker()

class OperatorCallContext():
    def __enter__(self):
        scene = bpy.context.scene
        prefs = bpy.context.user_preferences

        self.curact = scene.objects.active
        self.cursel = { ob : ob.select for ob in scene.objects }
        
        self.use_global_undo = prefs.edit.use_global_undo
        prefs.edit.use_global_undo = False

        return (self.curact, self.cursel)
    
    def __exit__(self, exc_type, exc_value, traceback):
        scene = bpy.context.scene
        prefs = bpy.context.user_preferences

        scene.objects.active = self.curact
        for ob in scene.objects:
            ob.select = self.cursel.get(ob, False)

        prefs.edit.use_global_undo = self.use_global_undo

def select_single_object(ob):
    scene = bpy.context.scene
    
    scene.objects.active = ob
    for tob in scene.objects:
        tob.select = (tob == ob)
        
def unselect_all_objects(scene):
    for tob in scene.objects:
        tob.select = false
        
class Error(Exception):
    pass

class MeshError(Error):
    pass

class ArmatureError(Error):
    pass

class Warning(Exception):
    pass

class ErrorDialog(bpy.types.Operator):
    bl_idname = "karaage.error"
    bl_label = ""
    
    msg=""

    @staticmethod
    def exception(e):
        if isinstance(e, MeshError):
            ErrorDialog.dialog(str(e), SEVERITY_MESH_ERROR)
        elif isinstance(e, ArmatureError):
            ErrorDialog.dialog(str(e), SEVERITY_ARMATRUE_ERROR)
        elif isinstance(e, Error):
            ErrorDialog.dialog(str(e), SEVERITY_ERROR)
        elif isinstance(e, Warning):
            ErrorDialog.dialog(str(e), SEVERITY_WARNING)
        else:
            msg = "Not sure what went wrong, this traceback might help:\n(also look in the log file or console)\n\n" +\
                        traceback.format_exc()
            ErrorDialog.dialog(msg, SEVERITY_ERROR)
        
    @staticmethod
    def dialog(msg, severity):
        ErrorDialog.msg = msg
        ErrorDialog.severity = severity
        bpy.ops.karaage.error('INVOKE_DEFAULT')
        if ErrorDialog.severity == SEVERITY_INFO:
            logging.info(msg)
        elif ErrorDialog.severity == SEVERITY_WARNING:
            logging.warning(msg)
        else:
            logging.error(msg)
 
    def draw(self, context):
        layout = self.layout

        box = layout.column() 

        help_url = HELP_PAGE
        help_topic = ""
        paragraphs = self.msg.split("|")
        if len(paragraphs) > 1:
            label = paragraphs[0]
            text  = paragraphs[1]
            if len(paragraphs) == 3:
                help_url += paragraphs[2];
                help_topic = "(" + paragraphs[2] + ")"
        else:
            label = ""
            text  = self.msg
            
        if ErrorDialog.severity == SEVERITY_INFO:
            box.label("Info: %s"%label, icon='INFO')
        elif ErrorDialog.severity == SEVERITY_WARNING:
            box.label("Warning: %s"%label, icon='INFO')
        elif ErrorDialog.severity == SEVERITY_MESH_ERROR:
            box.label("Mesh has issues: %s"%label, icon='HAND')
        elif ErrorDialog.severity == SEVERITY_ARMATURE_ERROR:
            box.label("Armature has issues: %s"%label, icon='HAND')
        else:
            box.label("Error: %s"%label, icon='ERROR')
            
        layout.separator()
        
        col = layout.column(align=True)
        lines = text.split("\n")
        for line in lines:
            col.label(line)
        
        col.operator("wm.url_open", text="Karaage Online Help " + help_topic, icon='URL').url=help_url

    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        width = 500 * bpy.context.user_preferences.system.pixel_size
        return context.window_manager.invoke_popup(self, width=width)
 
def apply_armature_modifiers(context, obj, preserve_volume=False):
    ctx                  = context.copy()
    ctx['active_object'] = obj
    ctx['object']        = obj

    try:
        for mod in obj.modifiers:
            if mod.type=="ARMATURE":
                if preserve_volume is not None:
                    mod.use_deform_preserve_volume=preserve_volume
                ctx['modifier'] = mod
                obj['use_deform_preserve_volume'] = mod.use_deform_preserve_volume
                bpy.ops.object.modifier_apply(ctx, apply_as='DATA', modifier=mod.name)
                print("Set %s.mod.use_deform_preserve_volume = %s" % ( obj.name, obj['use_deform_preserve_volume']))

    except:
        print("apply_armature_modifiers: Failed to apply modifier on Object %s" % obj.name)

def visualCopyMesh(context, target, apply_pose=True, apply_shape_modifiers=False, remove_weights=False, preserved_shape_keys=None, filter=None, preserve_volume=None):

    dupobj      = target.copy()
    dupobj.data = target.data.copy()
    
    ctx                  = context.copy()
    ctx['active_object'] = dupobj
    ctx['object']        = dupobj
    
    if 'bone_morph'    in dupobj: del dupobj['bone_morph']
    if 'neutral_shape' in dupobj: del dupobj['neutral_shape']
    if 'original'      in dupobj: del dupobj['original']
    if 'mesh_id'       in dupobj: del dupobj['mesh_id']

    context.scene.objects.link(dupobj)

    if apply_shape_modifiers:
        try:
            for mod in dupobj.modifiers:
                if mod.type=="SHRINKWRAP":
                    ctx['modifier'] = mod
                    bpy.ops.object.modifier_apply(ctx, apply_as='SHAPE', modifier=mod.name)
                    key_blocks = dupobj.data.shape_keys.key_blocks
                    N = len(key_blocks)
                    sk = key_blocks[N-1]
                    if 'bone_morph' in key_blocks:
                        sk.relative_key = key_blocks['bone_morph']
                    sk.value        = 1.0
        except:
            print("Unexpected error while applying modifier:", sys.exc_info()[0])
            pass
    
    if dupobj.data.shape_keys:
        N = len(dupobj.data.shape_keys.key_blocks)
        if N > 0:
            if preserved_shape_keys or filter:
                for sk in dupobj.data.shape_keys.key_blocks:
                    if (preserved_shape_keys and sk.name in preserved_shape_keys) or\
                       (filter and not sk.name in filter):
                        sk.mute=True
                mix = dupobj.shape_key_add("mix", from_mix=True)
                co  = [0.0]*3*len(dupobj.data.vertices)
                mix.data.foreach_get('co',co)

                N += 1
                for ii in range (N-2, -1, -1):
                    sk = dupobj.data.shape_keys.key_blocks[ii]
                    if (preserved_shape_keys and sk.name in preserved_shape_keys) or\
                       (filter and not sk.name in filter):
                       sk.mute=False
                    else:
                        dupobj.active_shape_key_index = ii
                        bpy.ops.object.shape_key_remove(ctx)

                sk = dupobj.data.shape_keys.key_blocks[0]
                sk.data.foreach_set('co', co)
                dupobj.data.vertices.foreach_set('co',co)

            else:
                sk = dupobj.shape_key_add("mix", from_mix=True)
                N += 1
                for ii in range (N-2, -1, -1):
                    dupobj.active_shape_key_index = ii
                    bpy.ops.object.shape_key_remove(ctx)

                dupobj.active_shape_key_index = 0
                bpy.ops.object.shape_key_remove(ctx)

    if apply_pose:

        try:
            for key in dupobj.keys():
                del dupobj[key]
        except:
            pass

        apply_armature_modifiers(context, dupobj, preserve_volume)

        if remove_weights:
            active_object = context.scene.objects.active
            context.scene.objects.active = dupobj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')

            try:
                bpy.ops.object.vertex_group_remove_from(use_all_groups=True, use_all_verts=True)
            except:

                bpy.ops.object.vertex_group_remove_from(all=True)

            bpy.ops.object.mode_set(mode='OBJECT')
            context.scene.objects.active = active_object
    return dupobj

def get_bone_scales(bone, use_custom=True):

    s0 = Vector(bone.get('scale0',(1,1,1)))
    if use_custom:

        x = bone.get('restpose_scale_y', s0[0])
        y = bone.get('restpose_scale_x', s0[1])
        z = bone.get('restpose_scale_z', s0[2])
        sc = Vector((x,y,z))
        if abs(sc.magnitude-s0.magnitude) > MIN_BONE_LENGTH and \
           abs(sc.normalized().dot(s0.normalized()) - 1) > MIN_BONE_LENGTH:
                log.warning("Custom Scale: SL: %s -> Custom: %s  Bone: %s" % (s0, sc, bone.name) )
                s0 = sc
    ds = Vector(bone.get('scale',(0,0,0)))

    return ds, s0

def get_bone_scale_matrix(bone, f=1, inverted=False, normalized=True):
    scale = get_bone_scale(bone, f, inverted, normalized)
    M = matrixScale(scale)
    return M

def get_bone_scale(bone, f=1, inverted=False, normalized=True, use_custom=True):
    ds, s0 = get_bone_scales(bone, use_custom)
    scale = f*ds+s0
    
    if normalized:
       scale = Vector([scale[i]/s0[i] for i in range(3)])
    
    if inverted:
       scale = Vector([1/scale[i] for i in range(3)])
    return scale

def getBoneScaleMatrix(bone, MScale=None, normalize=True, verbose=False, use_custom=True):
    if not bone:
        return Matrix()

    if bone.use_deform:
        scaleDelta, scaleBasis = get_bone_scales(bone, use_custom)
    else:
        scaleDelta = Vector((0,0,0))
        scaleBasis = Vector((1,1,1))
    
    scale = scaleDelta + scaleBasis
    
    if not MScale:
        MScale = Matrix()
        MScale[0][0] = 1
        MScale[1][1] = 1
        MScale[2][2] = 1
        
    if normalize:
        MScale[0][0] *= ((scale.x) / scaleBasis.x)
        MScale[1][1] *= ((scale.y) / scaleBasis.y)
        MScale[2][2] *= ((scale.z) / scaleBasis.z)
    else:
        MScale[0][0] *= scale.x
        MScale[1][1] *= scale.y
        MScale[2][2] *= scale.z

    if verbose:
        print("bone:%-25s deform:%s ds:%s s0:%s" % (bone.name, bone.use_deform, scaleDelta, scaleBasis))

    if bone.parent and bone.parent.use_deform and not bone.name.startswith(("m","a")):

        MScale = getBoneScaleMatrix(bone.parent, MScale, normalize, verbose, use_custom)

    return MScale

def get_min_joint_offset(jointtype='PIVOT'):
    return MIN_JOINT_OFFSET_RELAXED if jointtype=='PIVOT' else MIN_JOINT_OFFSET

def get_highest_materialcount(targets):
    matcount = 0
    material_warnings = []
    for obj in targets:
        if obj.type == "MESH":
            nmat = 0
            for slot in obj.material_slots:
                if not slot.material is None:
                    nmat += 1
            if matcount < nmat:
                matcount = nmat
            if nmat > 8:
                material_warnings.append(_("%s contains %d materials")%(obj.name,nmat))

    return matcount, material_warnings

def selection_has_shapekeys(targets):
    for obj in targets:
        if obj.active_shape_key:
            return True
    return False  

def get_armature(obj):
    if not obj:
        return None
    elif obj.type == "ARMATURE":
        arm = obj
    else:
        arm = obj.find_armature()
    return arm
    
def get_armatures(selection):
    armobjs = set()
    for obj in selection:
        arm = get_armature(obj)
        if arm:
            armobjs.add(arm)
    return armobjs

def getSelectedArmsAndObjs(context):
    ob = context.object
   
    arms = {}
    objs = []
    
    if ob:
        if ob.type == 'ARMATURE':
            arms[ob.name] = ob
            objs = getCustomChildren(ob, type='MESH')

        elif context.mode=='EDIT_MESH':
            arm = ob.find_armature()
            if arm:
                objs           = [ob]
                arms[arm.name] = arm
        else:

            objs = [ob for ob in context.selected_objects if ob.type=='MESH']
            for ob in objs:
                arm = ob.find_armature()
                if arm:
                    arms[arm.name] = arm
    return list(arms.values()), objs

def getSelectedArmsAndAllObjs(context):
    ob = context.object
    arms = {}
    objs = {}
    
    if ob:
        if context.mode=='EDIT_MESH':
            arm = ob.find_armature()
            if arm:
                arms[arm.name] = arm
        else:
            for ob in context.selected_objects:

                arm = get_armature(ob)
                if arm:
                    log.warning("Add Armature %s" % ob.name)
                    arms[arm.name] = arm
                    
    for arm in arms.values():

        for obj in getCustomChildren(arm, type='MESH'):
            log.warning("Add mesh %s" % obj.name)
            objs[obj.name]=obj

    return list(arms.values()), list(objs.values())
    
def is_karaage(obj):
    arm = get_armature(obj)
    return (not arm is None and ('karaage' in arm or 'Karaage' in arm))

def getSelectedCustomMeshes(selection):
    custom_meshes = [obj for obj in selection if obj.type=='MESH' and not 'karaage-mesh' in obj and obj.find_armature() ]
    return custom_meshes

def getCustomChildren(parent, type=None, select=None, visible=None):
    children = getChildren(parent, type=type, select=select, visible=visible)
    custom_children = [obj for obj in children if not 'karaage-mesh' in obj]
    return custom_children

def getKaraageChildSet(parent, type=None, select=None, visible=None):
    children = getChildren(parent, type=type, select=select, visible=visible)
    childSet = {obj.name.rsplit('.')[0]:obj for obj in children if 'karaage-mesh' in obj or obj.type=='EMPTY'}
    return childSet

def object_is_visible(context, ob):
    if ob.hide:
        return False
    return True in [x and y for x,y in zip(ob.layers,context.scene.layers)]    

def get_meshes(context, type= None, select=None, visible=None, hidden=None):
    meshes = [ob for ob in context.scene.objects
        if
            (select  == None or ob.select     == select)
        and (type    == None or ob.type       == type)
        and (hidden  == None or ob.hide       == hidden)
        and (visible == None or ob.is_visible(context.scene) == visible )
        and True in [x and y for x,y in zip(ob.layers,context.scene.layers)]
        ]
    return meshes

def get_weight_group_names(selection):
    groups = []
    for ob in selection:
        groups += [group.name for group in ob.vertex_groups]
    return set(groups)

def get_animated_meshes(context, armature, with_karaage=True, only_selected=False, return_names=False):
    animated_meshes=[]
    visible_meshes = [ob for ob in context.scene.objects 
        if ob.type=='MESH' 
        and not ob.hide 
        and ob.is_visible(context.scene)
        and True in [x and y for x,y in zip(ob.layers,context.scene.layers)]        
        ]

    for mesh in visible_meshes:
       if with_karaage == False and "karaage-mesh" in mesh:
           continue
           
       if any([mod for mod in mesh.modifiers if mod.type=='ARMATURE' and mod.object==armature]):
           if mesh.select or not only_selected:
               animated_meshes.append(mesh.name if return_names else mesh)

    return animated_meshes

def get_animated_mesh_count(context, armature, with_karaage=True, only_selected=False):
    return len(get_animated_meshes(context, armature, with_karaage, only_selected))

def getChildren(parent, type=None, select=None, visible=None, children=None, context=None):
    if context == None:
        context=bpy.context
    if children == None:
        children = []
    if parent:
        for child in parent.children:
            getChildren(child, type=type, select=select, visible=visible, children=children, context=context)
            if (visible==None or child.is_visible(context.scene)==visible) and (type==None or child.type==type) and (select==None or child.select==select):
                children.append(child)

    return children

def get_select_and_hide(selection, select=None, hide_select=None, hide=None):
    backup = {}
    for obj in selection:
        backup[obj] = [obj.select, obj.hide, obj.hide_select]
        if select != None:
            obj.select = select
        if hide != None:
            obj.hide=hide
        if hide_select != None:
            obj.hide_select = hide_select
    return backup        

def select_hierarchy(obj, select=True):
    selection = getChildren(obj)
    selection.append(obj)
    backup = get_select_and_hide(selection, select, False, False)
    return backup

def set_select_and_hide(backup):
    for ch, state in backup.items():
        ch.select      = state[0]
        ch.hide        = state[1]
        ch.hide_select = state[2]

def restore_hierarchy(backup):
    set_select_and_hide(backup)

def getKaraageArmaturesInScene(context=None, selection=None):
    armatures = set()
    if selection:
        armatures |= getKaraageArmaturesFromSelection(selection)
    if context:
        armatures |= getKaraageArmaturesFromSelection(context.scene.objects)
    return armatures

def getMasterBoneNames(bnames):
    masterNames = [n for n in bnames if n[0] in ['m', 'a'] or n in SLVOLBONES]
    return masterNames

def getControlledBoneNames(bnames):
    controlNames = [n for n in bnames if n[0] == 'm']
    return controlNames

def getKaraageArmaturesFromSelection(selection):
    armatures = [get_armature(obj) for obj in selection if (obj.type == 'ARMATURE' and 'karaage' in obj) or (obj.type=='MESH' and not 'karaage-mesh' in obj and obj.find_armature())]        
    armatures = set([arm for arm in armatures if 'karaage' in arm])
    return armatures

def getVisibleSelectedBoneNames(armobj):
    visible_layers = [i for i, l in enumerate(bpy.data.armatures[armobj.data.name].layers) if l]
    bones = get_modify_bones(armobj)
    selected_bones = [bone.name for bone in bones if bone.select and not bone.hide and any(bone.layers[i] for i in visible_layers)]
    return selected_bones

def getVisibleBoneNames(armobj):
    visible_layers = [i for i, l in enumerate(bpy.data.armatures[armobj.data.name].layers) if l]
    bones = get_modify_bones(armobj)
    visible_bones = [bone.name for bone in bones if not bone.hide and any(bone.layers[i] for i in visible_layers)]
    return visible_bones

def getHiddenBoneNames(armobj):
    visible_layers = [i for i, l in enumerate(bpy.data.armatures[armobj.data.name].layers) if l]
    bones = get_modify_bones(armobj)
    hidden_bones = [bone.name for bone in bones if bone.hide or not (any(bone.layers[i] for i in visible_layers))]
    return hidden_bones
    
def getVisibleSelectedBones(armobj):
    visible_layers = [i for i, l in enumerate(bpy.data.armatures[armobj.data.name].layers) if l]    
    bones = get_modify_bones(armobj)
    selected_bones = [bone for bone in bones if bone.select and not bone.hide and any(bone.layers[i] for i in visible_layers)]
    return selected_bones

def getVisibleBones(armobj):
    visible_layers = [i for i, l in enumerate(bpy.data.armatures[armobj.data.name].layers) if l]
    bones = get_modify_bones(armobj)
    visible_bones = [bone for bone in bones if not bone.hide and any(bone.layers[i] for i in visible_layers)]
    return visible_bones

def getControlBones(armobj, filter=None):
    bones = armobj.pose.bones
    control_bones = {}
    for bone in bones:
        if bone.name[0] == 'm':
            cname = bone.name[1:]
            control_bones[cname] = bones[cname]
        elif filter and filter in bone.name:
            control_bones[bone.name] = bone
    return control_bones

def getControlledBones(armobj, filter=None):
    bones = armobj.pose.bones
    deform_bones = {}
    for bone in bones:
        if bone.name[0] == 'm' or (filter and filter in bone.name):
            deform_bones[bone.name] = bone
    return deform_bones

def getLinkBones(armobj):
    bones = armobj.pose.bones
    link_bones = {}
    for bone in bones:
        if 'Link' in bone.name:
            link_bones[bone.name] = bone
    return link_bones

def getDeformBones(armobj):
    bones = armobj.pose.bones
    deform_bones = [b.name for b in bones if b.bone.use_deform]
    return deform_bones
    
def get_bone_type(bone, bones):
    name = bone.name
    if name[0]=="m" and name[1:] not in bones:
        return BONE_UNSUPPORTED
    if 'm'+name in armobj.data.edit_bones:
        return BONE_CONTROL
    if name[0] == 'm':
        return BONE_SL
    if name[0] == 'a':
        return BONE_ATTACHMENT
    if dbone_name in SLVOLBONES:
        return BONE_VOLUME
    return 'META' #IKBone or other stuff

def get_modify_bones(armobj, only=None):
    result = armobj.data.edit_bones if armobj.mode == 'EDIT' else armobj.data.bones
    if only:
        result = [b for b in result if b.name in only]
    return result

def get_selected_objects(context):
    return [o for o in context.scene.objects if o.select]

def getCurrentSelection(context, verbose=False):
    karaages      = []  # Karaage Armatures
    armatures     = []  # Referenced Armatures
    attached      = []  # Custom Meshes attached to an armature
    detached      = []  # Custom Meshes not attached to an armature
    weighttargets = []  # Meshes which are allowed to receive weights
    targets       = []  # Meshes
    others        = []  # all other selected
    active        = bpy.context.scene.objects.active
    shapekeys     = False
    
    for obj in [o for o in context.scene.objects if o.select]:

        if 'karaage' in obj or 'Karaage' in obj:
            karaages.append(obj)
            if verbose: print("Append Karaage %s" % obj.name)
        elif obj.type=='MESH':
            targets.append(obj)
            if verbose: print("Append Target %s" % obj.name)
            armature = getArmature(obj)
            
            if not ('weight' in obj and obj['weight']=='locked'):
                weighttargets.append(obj)

            if armature is not None:
                armatures.append(armature)
                attached.append(obj)
                if verbose: print("Append related Armature %s:%s" % (obj.name,armature.name))
            else:
                if verbose: print("Append %s also to Detached" % obj.name)
                detached.append(obj)
                if obj.data.shape_keys:
                    shapekeys = True
        elif obj.type=='ARMATURE':
            if verbose: print("Append selected Armature %s" % obj.name)
            armatures.append(obj)
        else:
            others.append(obj)

    currentSelection = {}
    currentSelection['karaages']      = karaages
    currentSelection['armatures']     = armatures
    currentSelection['targets']       = targets
    currentSelection['attached']      = attached
    currentSelection['detached']      = detached
    currentSelection['weighttargets'] = weighttargets
    currentSelection['others']        = others
    currentSelection['active']        = active
    currentSelection['shapekeys']     = shapekeys

    return currentSelection
def set_mesh_select_mode(select_modes):
    mesh_select_mode = bpy.context.scene.tool_settings.mesh_select_mode
    bpy.context.scene.tool_settings.mesh_select_mode = select_modes
    return mesh_select_mode

def ensure_mode_is(new_mode, def_mode=None, object=None, toggle_mode=None, context=None):
    if new_mode is None:
        if def_mode is None:
            return None
        new_mode = def_mode

    if context == None:
        context = bpy.context

    active_object = getattr(context, "active_object", None)

    try:
        if object == None and active_object:

            object = active_object

        if object == None:

            return None

        if object.mode == new_mode:
            if toggle_mode != None:
                new_mode = toggle_mode
            else:

                return new_mode
    except:
        print ("Failed to get [%s]" % object )
        return None

    original_mode = object.mode
    if active_object == object:
        bpy.ops.object.mode_set(mode=new_mode)
    else:
        context.scene.objects.active = object
        bpy.ops.object.mode_set(mode=new_mode)
        context.scene.objects.active = active_object
    return original_mode

def update_all_verts(obj, omode=None):
    return not update_only_selected_verts(obj, omode=omode)

def update_only_selected_verts(obj, omode=None):
    if omode is None:
        omode = obj.mode

    if omode == 'EDIT':
        only_selected = True
    else:
        only_selected = omode=='WEIGHT_PAINT' and (obj.data.use_paint_mask_vertex or obj.data.use_paint_mask)

    return only_selected

def select_all_doubles(me, dist=0.0001):
    
    bpy.ops.mesh.select_all(action='DESELECT')
    bm  = bmesh.from_edit_mesh(me)
    map = bmesh.ops.find_doubles(bm,verts=bm.verts, dist=dist)['targetmap']
    count = 0
    
    try:
        bm.verts.ensure_lookup_table()
    except:
        pass
        
    for key in map:
        bm.verts[key.index].select=True
        bm.verts[map[key].index].select=True
        count +=1

    bmesh.update_edit_mesh(me)
    return count
    
def select_edges(me, edges, seam=None, select=None):
    bm  = bmesh.from_edit_mesh(me)
    
    try:
        bm.edges.ensure_lookup_table()
    except:
        pass
        
    for i in edges:
        if not seam is None:   bm.edges[i].seam   = seam
        if not select is None: bm.edges[i].select = select
    bmesh.update_edit_mesh(me)

def get_vertex_coordinates(ob):    
    me = ob.data
    vcount = len(me.vertices)
    coords  = [0]*vcount*3

    for index in range(vcount):
        co = me.vertices[index].co
        coords[3*index+0] = co[0]
        coords[3*index+1] = co[1]
        coords[3*index+2] = co[2]
   
    return coords
    
def get_weights(ob, vgroup):
    weights = []
    for index, vert in enumerate(ob.data.vertices):
        for group in vert.groups:
            if group.group == vgroup.index:
                weights.append([index, group.weight])
                break
    return weights

def get_weight_set(ob, vgroup):
    weights = {}
    for index, vert in enumerate(ob.data.vertices):
        for group in vert.groups:
            if group.group == vgroup.index:
                weights[index] = group.weight
                break
    return weights

def merge_weights(ob, source_group, target_group):
    source_weights = get_weight_set(ob, source_group)
    target_weights = get_weight_set(ob, target_group)

    for key, val in source_weights.items():
        if key in target_weights:
            target_weights[key] = target_weights[key] + val
        else:
            target_weights[key] = val

    for key, val in target_weights.items():
        target_group.add([key], min(val,1), 'REPLACE')

def rescale(value1, vmin1, vmax1, vmin2, vmax2):
    '''
    rescale value1 from range vmin1-vmax1 to vmin2-vmax2
    '''
    range1 = float(vmax1-vmin1)
    range2 = float(vmax2-vmin2)
    value2 = (value1-vmin1)*range2/range1+vmin2

    value2 = max(min(value2, vmax2), vmin2)
    return value2
    
def s2bo(p):

    if isinstance(p,V):
        return V(p[1],p[0],p[2]) 
    else:
        return (p[1],p[0],p[2]) 

def s2b(p):

    if isinstance(p,V):
        return V(p[1],-p[0],p[2]) 
    else:
        return (p[1],-p[0],p[2]) 
    
def b2s(p):

    return (-p[1],p[0],p[2]) 

def bone_category_keys(boneset, category_name):
    subset_keys = [ key for key in boneset.keys() if key.startswith(category_name) ]
    return subset_keys

def get_addon_version():
    version = "%s.%s.%s" % (bl_info['version'])
    return version
    
def get_blender_revision():
    global SVN

    try:
        test = bpy.app.build_hash # check if we are in git
        n = bpy.app.version[0] * 100000 +\
            bpy.app.version[1] * 1000   +\
            bpy.app.version[2] * 100    
    except:
        try:
            n = bpy.app.build_revision.decode().split(':')[-1].rstrip('M')
        except:
            n = bpy.app.build_revision.split(':')[-1].rstrip('M')
        try:
            n = int(n)
        except:

            v = bpy.app.version[1]
            logging.critical(_("The Build revision of your system seems broken: [%s]" % (str(bpy.app.build_revision))))
            logging.critical(_("We now get your Blender Version number %d from: [%s]" % (v, str(bpy.app.version))))
            if v < MIN_VERSION:
                n = 0
            else:
                if v > 67: v = 67
                n = {'63':45996,
                     '64':51026,
                     '65':52851,
                     '66':55078,
                     '67':56533}[str(v)] 
    SVN = n
    return SVN

def get_collapse_icon(state):
    return "TRIA_DOWN" if state else "TRIA_RIGHT"

progress = 0
def progress_begin(min=0,max=9999):
    global progress
    try:
        bpy.context.window_manager.progress_begin(min,max)
        progress = 0
    except:
        pass    
        
def progress_update(val, absolute=True):
    global progress
    if absolute:
        progress = val
    else:
        progress += val
        
    try:
        bpy.context.window_manager.progress_update(progress)
    except:
        pass    

def progress_end():
    try:
        bpy.context.window_manager.progress_end()
    except:
        pass    

def getMesh(context, obj, exportRendertypeSelection, apply_mesh_rotscale = True, apply_armature=False):

    disabled_modifiers = []
    armature_modifiers = []

    #

    #

    log.debug("getMesh: + begin ++++++++++++++++++++++++++++++++++++++++++++")
    log.debug("getMesh: Get Mesh for %s" % (obj.name) )
    for m in obj.modifiers:
        log.debug("getMesh: Examine modifier %s %s %s" % (m.name, m.show_viewport, m.show_render))
        if exportRendertypeSelection == 'NONE' or (exportRendertypeSelection == 'RAW' and m.type != 'ARMATURE'):

            if m.show_viewport == True:
                disabled_modifiers.append(m)
                m.show_viewport=False
                log.debug("getMesh: Disabled PREVIEW modifier %s" % m.name)
        elif m.type == 'ARMATURE':
            if apply_armature:
                armature_modifiers.append([m,m.use_deform_preserve_volume])

                log.debug("getMesh: Apply ARMATURE modifier %s" % m.name)
            else:

                if exportRendertypeSelection == 'PREVIEW' and m.show_viewport == True:
                    m.show_viewport=False
                    disabled_modifiers.append(m)
                    log.debug("getMesh: Disabled %s modifier %s" % (exportRendertypeSelection, m.name))
                elif exportRendertypeSelection == 'RENDER' and m.show_render == True:
                    m.show_render=False
                    disabled_modifiers.append(m)
                    log.debug("getMesh: Disabled %s modifier %s" % (exportRendertypeSelection, m.name))
                else:
                    log.debug("getMesh: Enabled %s modifier %s" % (exportRendertypeSelection, m.name))
        else:
            log.debug("getMesh: Use %s modifier %s for viewport:%s render:%s" % \
                     (exportRendertypeSelection, m.name, m.show_viewport, m.show_render))

    mesh_type = exportRendertypeSelection
    if mesh_type == 'NONE':
        mesh_data_copy = obj.to_mesh(context.scene, False, 'PREVIEW')
        log.warning("getMesh: NONE -> Generate mesh using Rendertype 'PREVIEW" )
    elif mesh_type == 'RAW':
        mesh_data_copy = obj.to_mesh(context.scene, True, 'PREVIEW')
        log.warning("getMesh: RAW -> Generate mesh using Rendertype 'PREVIEW" )
    else:
        mesh_data_copy = obj.to_mesh(context.scene, True, mesh_type)
        log.warning("getMesh: Finally Generate mesh using Rendertyype %s" % (mesh_type) )

    mesh_data_copy.name = mesh_data_copy.name + "_mdc"

    for m in disabled_modifiers:

        if exportRendertypeSelection == 'RENDER':
            m.show_render=True
        else:
            m.show_viewport=True

    for val in armature_modifiers:
        m = val[0]
        m.use_deform_preserve_volume = val[1]

    if apply_mesh_rotscale:
        m = obj.matrix_world.copy()
        m[0][3] = m[1][3] = m[2][3] = 0
        mesh_data_copy.transform(m)
        mesh_data_copy.calc_normals()
        log.warning("getMesh: Calculating normals here will destroy custom normals!" )

    log.debug("getMesh: - end ----------------------------------------------")
    return mesh_data_copy

def get_uv_vert_count(me):
    edge_count = len([e.use_seam for e in me.edges if e.use_seam])
    return edge_count + len(me.vertices)
    
def get_nearest_vertex_normal(source_verts, target_vert):
    for source_vert in source_verts:
        dist = (target_vert.co - source_vert.co).magnitude
        if dist < 0.001:
            return source_vert.normal
    return

def get_boundary_verts(bmsrc, context, obj, exportRendertypeSelection="NONE", apply_mesh_rotscale = True):
    mesh_data_copy = getMesh(context, obj, exportRendertypeSelection, apply_mesh_rotscale)
    bmsrc.from_mesh(mesh_data_copy)
    
    invalidverts = []
    boundaryvert = False
    for edge in bmsrc.edges:

        if len(edge.link_faces) > 1:
            for vert in edge.verts:
                for edge in vert.link_edges:
                    if len(edge.link_faces) < 2:
                        boundaryvert = True
                if boundaryvert:
                    boundaryvert = False
                    continue
                else:
                    invalidverts.append(vert)
                    
    for vert in invalidverts:
        if vert.is_valid:
            bmsrc.verts.remove(vert)
            
    bpy.data.meshes.remove(mesh_data_copy)
    return bmsrc.verts

def get_adjusted_vertex_normals(context, sources, exportRendertypeSelection, apply_mesh_rotscale):
    bm_source  = bmesh.new()
    bm_target  = bmesh.new()
    
    targets = sources.copy()
    source_normals    = {}
    
    for obj in sources:
        try:
            bm_target.verts.ensure_lookup_table()
            bm_source.verts.ensure_lookup_table()
        except:
            pass
            
        target_verts = get_boundary_verts(bm_target, context, obj, exportRendertypeSelection, apply_mesh_rotscale)
        targets.remove(obj)
        for otherobj in sources:
        
            if otherobj == obj:
                continue
                
            source_verts = get_boundary_verts(bm_source, context, otherobj, exportRendertypeSelection, apply_mesh_rotscale)
            if not obj.name in source_normals:
                source_normals[obj.name]={}
            normals = source_normals[obj.name]
            fixcount = 0
            for vert in target_verts:
                near = get_nearest_vertex_normal(source_verts, vert)
                if near:
                    vert.normal = (vert.normal + near) * 0.5
                    vert.normal.normalize()
                    normals[vert.index] = vert.normal.copy()
                    fixcount +=1
                    
            if fixcount > 0:
                print("merged %d normals from %s with target %s" % (fixcount, otherobj.name, obj.name) )
            bm_source.clear()
        bm_target.clear()
        
    bm_source.free()        
    bm_target.free()
    return source_normals
        
ABERRANT_PLURAL_MAP = {
    'appendix': 'appendices',
    'child': 'children',
    'criterion': 'criteria',
    'focus': 'foci',
    'index': 'indices',
    'knife': 'knives',
    'leaf': 'leaves',
    'mouse': 'mice',
    'self': 'selves'
    }

VOWELS = set('aeiou')

def pluralize(singular, count=2, plural=None):
    '''
    singular : singular form of word
    count    : if count > 1 return plural form of word 
               otherwise returns word as is
    plural   : for irregular words
    '''

    if not singular or count < 2:
        return singular
    if plural:
        return plural

    plural = ABERRANT_PLURAL_MAP.get(singular)
    if plural:
        return plural
        
    root = singular
    try:
        if singular[-1] == 'y' and singular[-2] not in VOWELS:
            root = singular[:-1]
            suffix = 'ies'
        elif singular[-1] == 's':
            if singular[-2] in VOWELS:
                if singular[-3:] == 'ius':
                    root = singular[:-2]
                    suffix = 'i'
                else:
                    root = singular[:-1]
                    suffix = 'ses'
            else:
                suffix = 'es'
        elif singular[-2:] in ('ch', 'sh'):
            suffix = 'es'
        else:
            suffix = 's'
    except IndexError:
        suffix = 's'
    plural = root + suffix
    return plural

class PVector(Vector):
    def __init__(self, val, prec=4):
        self.prec = prec

    def __str__(self):
        return 'Vector(('+', '.join([str(round(self[n], self.prec)) for n in range(0,3)])+'))'

class V(namedtuple('V', 'x, y, z')):
    '''
    Simple vector class
    '''
    
    def __new__(_cls, *args):
        'Create new instance of Q(x, y, z)'
        if len(args)==1:
            x,y,z = args[0]
        else:
            x,y,z = args
        return super().__new__(_cls, x, y, z) 
    def __add__(self, other):
        if type(other) == V:
            return V( *(s+o for s,o in zip(self, other)) )
        try:
            f = float(other)
        except:
            return NotImplemented
        return V(self.x+f, self.y+f, self.z+f)

    __radd__ = __add__

    def __neg__(self):
        return V(-self.x, -self.y, -self.z)
 
    def __sub__(self, other):
        if type(other) == V:
            return V( *(s-o for s,o in zip(self, other)) )
        try:
            f = float(other)
        except:
            return NotImplemented
        return V(self.x-f, self.y-f, self.z-f)

    def __mul__(self, other):
        try:
            f = float(other)
        except:
            return NotImplemented
        return V(self.x * f, self.y * f, self.z * f)
    
    def __truediv__(self, other):
        try:
            f = float(other)
        except:
            return NotImplemented
        return V(self.x / f, self.y / f, self.z / f)
    
    def copy(self):
        return V(self.x, self.y, self.z)
        
    def magnitude(self):
        v = Vector((self.x, self.y, self.z))
        return v.magnitude
    
    __rmul__ = __mul__
    
def findKaraageMeshes(parent, meshobjs=None, armature_version=None):

    if meshobjs == None:
        meshobjs = {}

    if armature_version == None:
        try:
            armature_version = parent['karaage']
        except:
            armature_version = 0

    for child in parent.children:
        findKaraageMeshes(child, meshobjs, armature_version)
        if child.type=='MESH':
            name = child.name.split(".")[0] 
            if name in ['headMesh','hairMesh','upperBodyMesh','lowerBodyMesh','skirtMesh','eyelashMesh','eyeBallLeftMesh','eyeBallRightMesh']:
                if armature_version == 2 and not 'karaage-mesh' in child:
                    continue
                    
                if name in meshobjs:

                    try:
                        if len(child.data.shape_keys.key_blocks) > 1:
                            meshobjs[name] = child
                    except AttributeError:

                        pass
                else:
                    meshobjs[name] = child

    return meshobjs

def ensure_shadow_exists(key, arm, obj, me = None):
    context = bpy.context
    shadow_name = 'karaage_reference_' + key
    try:
        shadow = bpy.data.objects[shadow_name]
        if me:
            oldme, shadow.data = shadow.data, me
            bpy.data.meshes.remove(oldme)
    except:
        print("Create missing shadow for", obj)
        shadow             = visualCopyMesh(context, obj)
        shadow.name        = shadow_name

        shadow.hide        = False
        shadow.select      = False
        shadow.hide_select = False
        shadow.hide_render = True
        shadow.parent      = arm

        if 'karaage-mesh' in shadow: del shadow['karaage-mesh'] 
        if 'mesh_id'      in shadow: del shadow['mesh_id']      

        context.scene.objects.unlink(shadow)

    if me:
        me.name = shadow_name

        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(shadow.data)
        bm.clear()

        shadow.data.name = me.name
        print("Updated Shadow object key:[%s] name:[%s:%s]" % (key, shadow.name, shadow.data.name))

    return shadow

def getArmature(obj):

    armature = None
    
    for mod in obj.modifiers:
        if mod.type=="ARMATURE":
            armature = mod.object
            break
    
    if armature is None and obj.parent_type == 'ARMATURE':
        armature = obj.parent
            
    return armature

def flipName(name):

    if "Left" in name:
        fname = name.replace("Left","Right")
    elif "Right" in name:
        fname = name.replace("Right","Left")
    elif "left" in name:
        fname = name.replace("left","right")
    elif "right" in name:
        fname = name.replace("right","left")
    elif name.endswith(".R") or name.endswith("_R"):
        fname = name[0:-1]+"L"
    elif name.endswith(".L") or name.endswith("_L"):
        fname = name[0:-1]+"R"
    elif name.startswith("l"):
        fname = "r" + name[1:]
    elif name.startswith("r"):
        fname = "l" + name[1:]
    else:
        fname = ""

    return fname
    
class BindBone:

    def __init__(self,bone):

        self.name      = bone.name
        self.head      = bone.head
        self.tail      = bone.tail
        self.parent    = bone.parent.name if bone.parent else None

        self.matrix    = bone.matrix_basis.copy()
        
        if bone.name=="CollarRight":
            print("matrix:", self.matrix)
        
class AlterToRestPose(bpy.types.Operator):
    bl_idname = "karaage.alter_to_reference_pose"
    bl_label = "Alter To Reference Pose"
    bl_description =_("Alter pose to Reference Pose")
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(self, context):
        obj = context.active_object
        if obj:
            arm = get_armature(obj)
            return arm and arm.type=='ARMATURE'
        return False

    @classmethod
    def resetBinding(self, arm):
        reference = ArmatureBinding.get_binding(arm)
        if not reference:
            print("Can not alter to rest pose. No reference pose found")
            return False
        
        pbones = arm.pose.bones
        bbones = reference.bbones
            
        omode = ensure_mode_is('POSE', object=arm)
        for key in bbones:
            rbone  = bbones[key]
            pbones[key].matrix_basis = rbone.matrix.inverted()

        ensure_mode_is(omode, object=arm)
        return True

    def execute(self, context):
        obj = context.active_object
        arm = get_armature(obj)
        if AlterToRestPose.resetBinding(arm):
            return {'FINISHED'}
        else:
            return {'CANCELLED'}

class ArmatureBinding:

    armature_bindings={}
    
    def __init__(self, arm, reference):
        self.reference = reference
        ArmatureBinding.armature_bindings[arm.name]=self

    @staticmethod
    def get_binding(arm):
        ref = ArmatureBinding.armature_bindings[arm.name].reference if arm.name in ArmatureBinding.armature_bindings else None
        return ref

class BindSkeleton:

    def __init__(self, arm):
        self.bbones = {}
        omode = ensure_mode_is('POSE', object=arm)
        for bone in arm.pose.bones:
           bbone = BindBone(bone)
           self.bbones[bbone.name] = bbone

        ensure_mode_is(omode, object=arm)

class BindToCurrentPose(bpy.types.Operator):
    bl_idname = "karaage.bind_to_pose"
    bl_label = "Bind To Pose"
    bl_description =_("Create new Karaage Character using custom avatar_skeleton")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        if context.active_object:
            active = context.active_object
            return active and active.type=='ARMATURE'
        return False
        
    @classmethod
    def createBinding(self,arm, context):

        omode = ensure_mode_is('POSE')
        arm.data.pose_position='REST'
        enforce_armature_update(context.scene, arm)
        reference = BindSkeleton(arm)
        arm.data.pose_position='POSE'
        bpy.ops.pose.armature_apply()

        ArmatureBinding(arm, reference)
        ensure_mode_is(omode)
        print("Done")

    def execute(self, context):
        arm = context.active_object
        BindToCurrentPose.createBinding(arm, context)
        return {'FINISHED'}
           
class Bone:

    bonegroups = []

    def __init__(self, blname, bvhname=None, slname=None, relhead=V(0,0,0), reltail=V(0,0,-0.1), parent=None, 
                 bonelayers=[B_LAYER_TORSO], shape=None, shape_scale=None, roll = 0, connected=False, group="Rig", 
                 stiffness=[0.0,0.0,0.0], limit_rx=None, limit_ry=None, limit_rz=None, deform=False,
                 scale0=V(1,1,1), rot0=V(0,0,0), skeleton='basic', bonegroup='Custom', 
                 mandatory='false', leaf=None, wire=True, pos0=V(0,0,0), pivot0=V(0,0,0), attrib= None,
                 end0=V(0,0,0), is_structure=False):

        self.blname       = blname # Blender name
        self.children     = []
        self.parent       = None
        self.scale        = V(0, 0, 0)
        self.offset       = V(0, 0, 0)
        self.is_ik_root   = False
        self.ik_end       = None
        self.ik_root      = None
        self.wire         = True
        self.attrib       = None
        self.is_structure = False
        self.b0head       = V(0, 0, 0)
        self.b0tail       = V(0, 0, 0)
        self.b0dist       = 0
               
        self.set(all=True,
            bvhname    = bvhname,
            slname     = slname,
            relhead    = relhead,
            reltail    = reltail,
            parent     = parent, 
            bonelayers = bonelayers,
            shape      = shape,
            shape_scale= shape_scale,
            roll       = roll,
            connected  = connected,
            group      = group, 
            stiffness  = stiffness,
            limit_rx   = limit_rx,
            limit_ry   = limit_ry,
            limit_rz   = limit_rz,
            deform     = deform,
            scale0     = scale0,
            rot0       = rot0,
            pos0       = pos0,
            pivot0     = pivot0,
            skeleton   = skeleton,
            bonegroup  = bonegroup,
            mandatory  = mandatory,
            leaf       = leaf,
            wire       = wire,
            attrib     = attrib,
            end0       = end0,
            is_structure = is_structure
            )

    def set(self,all=False, bvhname=None, slname=None, 
            relhead=None, reltail=None, parent=None, 
            bonelayers=None, shape=None, shape_scale= None, 
            roll = None, connected=None, group=None, 
            stiffness=None, limit_rx=None, limit_ry=None, limit_rz=None, deform=None,
            scale0=None, rot0=None, pos0=None, pivot0=None, 
            skeleton=None, bonegroup=None, 
            mandatory=None, leaf=None, wire=None,
            attrib=None, end0=None, is_structure=None):
                    
        if all or bvhname   != None: self.bvhname   = bvhname   # BVH name or None
        if all or slname    != None: self.slname    = slname    # SL name or None
        if all or relhead   != None: self.relhead   = relhead   # Default bone head relative to parent head, SL frame
        if all or reltail   != None: self.reltail   = reltail   # Default bone tail relative to own head, SL frame
        if parent != None: 
            self.parent = parent
            parent.children.append(self) # set up the children bones
            
        if all or bonelayers != None: self.bonelayers = bonelayers    # layers bone will be visible on 
        if all or shape      != None: self.shape      = shape     # name of custom shape if used
        if all or shape_scale!= None: self.shape_scale= shape_scale# custom shape scale
        if all or roll       != None: self.roll       = roll      # bone roll angle in radians
        if all or connected  != None: self.connected  = connected # wether bone is connected to parent
        if all or group      != None: self.group      = group
        if all or scale0     != None: self.scale0     = scale0
        if all or rot0       != None: self.rot0       = rot0
        if all or pos0       != None: self.pos0       = pos0
        if all or pivot0     != None: self.pivot0     = pivot0
        if all or stiffness  != None: self.stiffness  = stiffness
        if all or limit_rx   != None: self.limit_rx   = limit_rx
        if all or limit_ry   != None: self.limit_ry   = limit_ry
        if all or limit_rz   != None: self.limit_rz   = limit_rz
        if all or deform     != None: self.deform     = deform
        if all or skeleton   != None: self.skeleton   = skeleton
        
        if all or bonegroup   != None:
            if not bonegroup in Bone.bonegroups:
                Bone.bonegroups.append(bonegroup)
            self.bonegroup     = bonegroup
            
        if all or mandatory  != None: self.mandatory = mandatory
        if all or leaf       != None: self.leaf      = leaf
        if all or wire       != None: self.wire      = wire
        if all or attrib     != None: self.attrib    = attrib
        if all or end0       != None: self.end0      = end0
        if all or is_structure != None: self.is_structure = is_structure

    def get_scale(self):
        if self.is_structure and self.parent:
            return self.parent.get_scale()
        dps = Vector(self.scale)
        ps0 = Vector(self.scale0)
        return ps0, dps
    
    def get_headMatrix(self):
        if self.is_structure and self.parent:
            return self.parent.get_headMatrix()
        M = self.headMatrix()
        return M
    
    def headMatrix(self):
    
        o = Vector(self.offset)
        h = Vector(self.relhead)
        
        if hasattr(self, 'parent') and self.parent:
            M  = self.parent.get_headMatrix()
            ps0, dps = self.parent.get_scale()
            matrixScale(ps0+dps, M, replace=True)
            matrixLocation(h+o,M)
            
        else:

            M = Matrix()
        
        return M

    def get_parent(self):
        if self.parent:
            if self.parent.is_structure:
                return self.parent.get_parent()
            else:
                return self.parent
        else:
            return None
        
    def head(self, bind=True):
        '''
        Return the location of the bone head relative to Origin head
        '''
        
        o = Vector(self.offset)
        h = Vector(self.relhead)
        oh = o+h
        parent = self.get_parent()
        if parent:
            ph = parent.head(bind)
            if bind:
                ps0, dps = parent.get_scale()
                ps = ps0+dps
            else:
                ps = V(1,1,1)

            psoh = V(ps[0]*oh[0], ps[1]*oh[1], ps[2]*oh[2])
            ah = ph + psoh
            
        else:

            ah = V(0,0,0)
        
        return ah

    def tail(self):
        '''
        Return the location of the bone tail relative to topmost bone head
        '''

        ah = self.head()
        t = self.reltail if self.reltail is not None else V(0.0,0.1,0.0)        
        s = Vector(self.scale) + Vector(self.scale0)
        
        at = ah+V(s[0]*t[0], s[1]*t[1], s[2]*t[2])
        return at
    
    def pprint(self):
        print("bone       ", self.blname)
        print("bone bvh   ", self.bvhname)
        print("children   ", self.children)
        print("parent     ", self.parent.blname if self.parent else None)
        print("scale      ", self.scale)
        print("offset     ", self.offset)
        print("slname     ", self.slname)
        print("relhead    ", self.relhead)
        print("reltail    ", self.reltail)
        print("bonelayers ", self.bonelayers)
        print("shape      ", self.shape)
        print("shape_scale", self.shape_scale)
        print("roll       ", self.roll)
        print("connected  ", self.connected)
        print("group      ", self.group)
        print("scale0     ", self.scale0)
        print("rot0       ", self.rot0)
        print("stiffness  ", self.stiffness)
        print("limit_rx   ", self.limit_rx)
        print("limit_ry   ", self.limit_ry)
        print("limit_rz   ", self.limit_rz)
        print("deform     ", self.deform)
        print("skeleton   ", self.skeleton)
        print("bonegroup  ", self.bonegroup)
        print("mandatory  ", self.mandatory)
        print("leaf       ", self.leaf)
        print("end0       ", self.end0)

    def diff(self, obone):
        if obone.blname     != self.blname     : print("%15s.blname: %s    | %s" % (self.blname, self.blname, obone.blname))
        if obone.bvhname    != self.bvhname    : print("%15s.bvhname:%s    | %s" % (self.blname, self.bvhname, obone.bvhname))
        if obone.scale      != self.scale      : print("%15s.scale:%s      | %s" % (self.blname, self.scale, obone.scale))
        if obone.offset     != self.offset     : print("%15s.offset:%s     | %s" % (self.blname, self.offset, obone.offset))
        if obone.slname     != self.slname     : print("%15s.slname:%s     | %s" % (self.blname, self.slname, obone.slname))
        if obone.relhead    != self.relhead    : print("%15s.relhead:%s    | %s" % (self.blname, self.relhead, obone.relhead))
        if obone.reltail    != self.reltail    : print("%15s.reltail:%s    | %s" % (self.blname, self.reltail, obone.reltail))
        if obone.bonelayers != self.bonelayers : print("%15s.layers:%s     | %s" % (self.blname, self.bonelayers, obone.bonelayers))
        if obone.shape      != self.shape      : print("%15s.shape:%s      | %s" % (self.blname, self.shape, obone.shape))
        if obone.shape_scale!= self.shape_scale: print("%15s.shape_scale:%s| %s" % (self.blname, self.shape_scale, obone.shape_scale))
        if obone.roll       != self.roll       : print("%15s.roll:%s       | %s" % (self.blname, self.roll, obone.roll))
        if obone.connected  != self.connected  : print("%15s.connected:%s  | %s" % (self.blname, self.connected, obone.connected))
        if obone.group      != self.group      : print("%15s.group:%s      | %s" % (self.blname, self.group, obone.group))
        if obone.scale0     != self.scale0     : print("%15s.scale0:%s     | %s" % (self.blname, self.scale0, obone.scale0))
        if obone.rot0       != self.rot0       : print("%15s.rot0:%s       | %s" % (self.blname, self.rot0, obone.rot0))
        if obone.stiffness  != self.stiffness  : print("%15s.stiffness:%s  | %s" % (self.blname, self.stiffness, obone.stiffness))
        if obone.limit_rx   != self.limit_rx   : print("%15s.limit_rx:%s   | %s" % (self.blname, self.limit_rx, obone.limit_rx))
        if obone.limit_ry   != self.limit_ry   : print("%15s.limit_ry:%s   | %s" % (self.blname, self.limit_ry, obone.limit_ry))
        if obone.limit_rz   != self.limit_rz   : print("%15s.limit_rz:%s   | %s" % (self.blname, self.limit_rz, obone.limit_rz))
        if obone.deform     != self.deform     : print("%15s.deform:%s     | %s" % (self.blname, self.deform, obone.deform))
        if obone.skeleton   != self.skeleton   : print("%15s.skeleton:%s   | %s" % (self.blname, self.skeleton, obone.skeleton))
        if obone.bonegroup  != self.bonegroup  : print("%15s.bonegroup:%s  | %s" % (self.blname, self.bonegroup, obone.bonegroup))
        if obone.mandatory  != self.mandatory  : print("%15s.mandatory:%s  | %s" % (self.blname, self.mandatory, obone.mandatory))
        if obone.leaf       != self.leaf       : print("%15s.leaf     :%s  | %s" % (self.blname, self.leaf     , obone.leaf     ))
        if obone.end0       != self.end0       : print("%15s.end0     :%s  | %s" % (self.blname, self.end0     , obone.end0     ))

        op = obone.parent.blname if obone.parent else None
        sp = self.parent.blname  if self.parent else None
        parent_mismatch = op != sp and ( op == None or sp == None)
        if parent_mismatch : print("%15s.parent:%s    | %s" % (self.blname, op, sp))

        selfnames  = [child.blname for child in self.children]
        othernames = [child.blname for child in obone.children]
        for selfname in [ name for name in selfnames if name not in othernames]:
            print("%15s.child:%s missing in obone" % (self.blname, selfname))
        for oname in [ name for name in othernames if name not in selfnames]:
            print("%15s.child:%s missing in self" % (self.blname, oname))

class Skeleton:

    def __init__(self):

        self.bones = {}
        self.slbones = {}
        self.bvhbones = {}

    def __getitem__(self, key):
        return self.bones[key] if key in self.bones else None

    def __setitem__(self, key, value):
        self.bones[key] = value

    def __iter__(self):
        return self.bones.__iter__()

    def add_bone(self, B):
        self.bones[B.blname] = B
        if B.slname is not None:
            self.slbones[B.slname] = B
        if B.bvhname is not None:
            self.bvhbones[B.bvhname] = B
    
    def add_boneset(self, boneset):
        for bone in boneset.values():
            self.add_bone(bone)

    def add(self, blname,  *args,  **nargs):
        '''
        Convenience method to add a Bone() and link them together
        '''

        B = Bone(blname,  *args,  **nargs)
        self.add_bone(B)
        return B

    def addv(self, blname, relhead, reltail, parent, rot0=V(0,0,0), scale0=V(1,1,1)):
        '''
        Convenience method to add a volume Bone() and link them together
        '''

        rot0 = [radians(r) for r in s2b(rot0)]
        scale0 = s2bo(scale0)

        reltail = V( reltail[0]/scale0[0], reltail[1]/scale0[1], reltail[2]/scale0[2] )

        B = Bone(blname,  slname=blname, relhead=relhead, reltail=reltail, parent=parent,
                 layers=[B_LAYER_VOLUME], group='Collision', rot0=rot0, scale0=scale0, shape="CustomShape_Volume",
                 skeleton='basic', bonegroup='Volume', mandatory='false')
        self.add_bone(B)
        return B

    @staticmethod
    def get_toe_hover_z(armobj, reset=False, bind=True):
        hover = Skeleton.get_toe_hover(armobj, reset, bind)
        hover[0]=hover[1]=0
        return hover

    @staticmethod
    def get_toe_hover(armobj, reset=False, bind=True):
        if reset or not 'toe_hover' in armobj:
            bones    = get_modify_bones(armobj)
            b_toe    = bones.get('mToeRight',  None)
            l_toe    = Skeleton.head(context=None, dbone=b_toe,    bones=bones, bind=bind) if b_toe else V0
            b_origin = bones.get('Origin',  None)
            l_origin = Skeleton.head(context=None, dbone=b_origin,    bones=bones, bind=bind) if b_origin else V0
            hover    = l_toe-l_origin
            armobj['toe_hover'] = hover
        else:
            hover = Vector(armobj['toe_hover'])

        return hover

    @staticmethod
    def get_parent(bone):
        if bone.parent:
            parent = bone.parent
            if parent.get('is_structure', False):# or parent.name in ['PelvisInv', 'COG']:
                return Skeleton.get_parent(parent)
            else:
                return parent
        else:
            return None
 
    @staticmethod
    def get_bone_info(context, dbone, bones):
        if dbone == None or bones == None:
            if context == None:
                context=bpy.context
            if dbone == None:
                dbone = context.active_bone
            if bones == None:
                armobj = context.object
                bones   = get_modify_bones(armobj)
        return dbone, bones

    @staticmethod
    #

    #
    def has_connected_children(dbone):
        for child in dbone.children:
           if child.use_connect:
               return True
        return False
        
    @staticmethod
    def get_restposition(context, dbone, bind=True, with_joint=True, use_bind_pose=False):
        M = Matrix(([1,0,0],[0,1,0],[0,0,1]))
        j = V0

        if dbone == None:
            return V0.copy()

        parent  = Skeleton.get_parent(dbone)
        if not parent:
            pos = Vector(dbone.head) # This is the location of the root bone (Origin)
        else:

            pos = Skeleton.get_restposition(context, parent, bind, with_joint, use_bind_pose)

            d = V0.copy() if dbone.get('is_structure',False) else Vector(dbone.get('relhead',(0,0,0)))

            if with_joint:
                jh,jt = get_joint_offset(dbone)
                m = jh.magnitude
                if m:
                    if use_bind_pose:
                        from . import rig
                        if not context:
                            context = bpy.context
                        armobj = get_armature(context.object)
                        bindHead, bindTail = rig.get_sl_bindposition(armobj, dbone, use_cache=True)
                        restHead, restTail = rig.get_custom_restposition(armobj, dbone, use_cache=True)
                        if bindTail and restTail:

                            M = bindTail.rotation_difference(restTail).to_matrix()
                    d += jh
                else:
                    if bind:
                        d += Vector(dbone.get('offset', (0,0,0)))
            else:
                if bind:
                    d += Vector(dbone.get('offset', (0,0,0)))
            if bind:
                s = get_bone_scale(parent) if parent else V1.copy()
                dd = d*M
                dd = Vector([s[i]*d[i] for i in range(3)])
                d = M*dd

            pos += d

        return pos

    @staticmethod

    def headMatrix(context=None, dbone=None, bones=None, bind=True, with_joints=True, use_bind_pose=False):
        dbone, bones = Skeleton.get_bone_info(context, dbone, bones)
        bonename = dbone.name
        M = Matrix()
        parent = Skeleton.get_parent(dbone)
        oh = Skeleton.get_restposition(context, dbone, bind, with_joints, use_bind_pose)
        if parent:

            if bind:
                ps = get_bone_scale(dbone)
                matrixScale(ps, M) #We do not care about the scaling of the parent matrix here
            ps0 = Vector(dbone.get('scale0',(1,1,1)))
            matrixScale(ps0,M) # only needed for collision volumes ?
        M = matrixLocation(oh,M)
        return M

    @staticmethod
    def tailMatrix(context=None, dbone=None, bones=None, Mh=None, bind=True, with_joints=True, use_bind_pose=False):
        '''
        Return the location of the bone tail relative to topmost bone head
        with default=True it ignores scaling and offsets
        if bones is set then prefer SL bones (mBones) as reference
        Hint: the control skeleton can have a different hierarchy 
              so the control skeleton can potentially scale different 
              then the SL Skeleton. Caveat: this effectively synchronises
              the control bones to the mBones when the shape sliders are updated!
        '''

        location = None
        dbone, bones = Skeleton.get_bone_info(context, dbone, bones)
        if not Mh:
            Mh = Skeleton.headMatrix(context, dbone, bones, bind, with_joints)
        
        name = dbone.name
        reference_name = name if name[0] in ['m','a'] or name in SLVOLBONES or name in ['PelvisInv', 'EyeTarget'] or "Link" in name else 'm' + name
        reference_bone = bones.get(reference_name, None)
        if reference_bone:
            for child in reference_bone.children:
                if child.name[0] != 'm':
                    c = bones.get('m'+child.name, None)
                    if c:
                        child = c
                if child.use_connect:
                    location = Skeleton.headMatrix(context, child, bones, bind, with_joints, use_bind_pose).translation.copy()
                    break

        Mt = Mh.copy()
        sp = get_bone_scale(dbone)
        if bind and dbone.parent:
            if dbone.name in SLVOLBONES:
                Mt = matrixScale(sp, Mt, replace=True)
                sp = get_bone_scale(dbone.parent)
                Mt = matrixScale(sp,Mt)
            else:
                Mt = matrixScale(sp, Mt, replace=True)

        if location == None:
            if with_joints:
                h     = Vector(dbone.get('btail', dbone.get('reltail',(0,0,0))))
            else:
                h     = Vector(dbone.get('reltail',(0,0,0)))
            oh = h
            location  = Vector([oh[i]*sp[i] for i in range(3)]) + Mh.translation

        Mt = matrixLocation(location, Mt, replace=True)
        return Mt

    @staticmethod
    def head(context=None, dbone=None, bones=None, bind=True, with_joints=True, use_bind_pose=False):
        '''
        Return the location of the bone head relative to Origin head
        with scale=False it ignores scaling and offsets  
        if bones is set then prefer SL bones (mBones) as reference
        Hint: the control skeleton can have a different hierarchy 
              so the control skeleton can potentially sclae different 
              then the SL Skeleton. Caveat: this effectively synchronises
              the control bones to the mBones when the shape sliders are updated!
        '''
        M = Skeleton.headMatrix(context, dbone, bones, bind, with_joints, use_bind_pose)
        loc = M.translation
        return loc

    @staticmethod
    def bones_in_hierarchical_order(arm, roots=None, bone_names=None, order='TOPDOWN'):
        if not bone_names:
            bone_names = []

        if not roots:
            roots = [b for b in arm.data.bones if b.parent == None]

        for root in roots:
            bone_names.append(root.name)
            if root.children:
                Skeleton.bones_in_hierarchical_order(arm, root.children, bone_names)

        if order == 'BOTTOMUP':
            bone_names.reverse()
        return bone_names
    
    @staticmethod
    def get_bone_end(dbone, scale=True):
        be  = Vector(dbone.get('reltail', (0,0.1,0)))
        
        if scaled:
            s  = Vector(dbone.get('scale0', (1,1,1)))
            s += Vector(dbone.get('scale',  (0,0,0)))
            be = Vector([s[0]*be[0], s[1]*be[1], s[2]*be[2]])
        return be

    @staticmethod
    def tail(context=None, dbone=None, bones=None, bind=True, with_joints=True, use_bind_pose=False):
        '''
        Return the location of the bone tail relative to topmost bone head
        with scale=False it ignores scaling and offsets  
        if bones is set then prefer SL bones (mBones) as reference
        Hint: the control skeleton can have a different hierarchy 
              so the control skeleton can potentially sclae different 
              then the SL Skeleton. Caveat: this effectively synchronises
              the control bones to the mBones when the shape sliders are updated!
        '''

        Mh = Skeleton.headMatrix(context, dbone, bones, bind, with_joints, use_bind_pose)
        Mt = Skeleton.tailMatrix(context, dbone, bones, Mh, bind, with_joints, use_bind_pose)

        loc = Mt.translation
        return loc

def get_mirror_name(name):

    if name.find("Left") > -1:
        mirrorName = name.replace("Left", "Right")
    elif name.find("Right") > -1:
        mirrorName = name.replace("Right", "Left")
    elif name.find("RIGHT") > -1:
        mirrorName = name.replace("RIGHT", "LEFT")
    elif name.find("LEFT") > -1:
        mirrorName = name.replace("LEFT", "RIGHT")

    elif name[0:2] == "R_":
        mirrorName = "L_" + name[2:]
    elif name[0:2] == "L_":
        mirrorName = "R_" + name[2:]
    elif name[0:2] == "r_":
        mirrorName = "l_" + name[2:]
    elif name[0:2] == "l_":
        mirrorName = "r_" + name[2:]
    else:
        mirrorName = None

    return mirrorName

RF_LOWEST = 0.03
RF_LOW    = 0.06
RF_MID    = 0.24

MIN_AREA  = 1
MAX_AREA  = 102932

MAX_DISTANCE = 512

DISCOUNT      = 10
MIN_SIZE      = 2
FAKTOR        = 0.046

def limit_vertex_count(vertex_count, triangle_count):
    while vertex_count > triangle_count:
        vertex_count /= 2
    return vertex_count

def get_approximate_lods(ob, vertex_count, normals_count, uv_count, triangle_count):
    vcount = max(normals_count,uv_count)
    extra_normals = vcount - vertex_count
    rx = ob.dimensions[0] * ob.scale[0] / 2
    ry = ob.dimensions[1] * ob.scale[1] / 2
    rz = ob.dimensions[2] * ob.scale[2] / 2
    radius = max(rx,ry,rz)# sqrt(rx*rx + ry*ry + rz*rz) 
    
    if triangle_count == 0:
        correction=1
    else:
        correction = 4-(vcount*vcount)/(4*triangle_count*triangle_count)
    lowest_lod = max(limit_vertex_count(vcount/(6*correction), triangle_count/32) + extra_normals/42, MIN_SIZE)
    low_lod    = max(limit_vertex_count(vcount/(3*correction), triangle_count/16) + extra_normals/24, MIN_SIZE)
    medium_lod = max(limit_vertex_count(vcount/correction    , triangle_count/4)  + extra_normals/6 , MIN_SIZE)
    high_lod   = vcount
    
    return radius, lowest_lod, low_lod, medium_lod, high_lod

def get_streaming_costs(radius, vc_lowest, vc_low, vc_mid, vc_high, triangle_count):

    dlowest = min(radius/RF_LOWEST, MAX_DISTANCE)
    dlow    = min(radius/RF_LOW   , MAX_DISTANCE)
    dmid    = min(radius/RF_MID   , MAX_DISTANCE)

    trilowest = max(vc_lowest - DISCOUNT,MIN_SIZE)
    trilow    = max(vc_low    - DISCOUNT,MIN_SIZE)
    trimid    = max(vc_mid    - DISCOUNT,MIN_SIZE)
    trihigh   = max(vc_high   - DISCOUNT,MIN_SIZE)

    ahigh   = min(pi * dmid*dmid,       MAX_AREA)
    amid    = min(pi * dlow*dlow,       MAX_AREA)
    alow    = min(pi * dlowest*dlowest, MAX_AREA)
    alowest = MAX_AREA
    
    alowest -= alow
    alow    -= amid
    amid    -= ahigh

    atot = ahigh + amid + alow + alowest
    
    wahigh   = ahigh/atot
    wamid    = amid/atot
    walow    = alow/atot
    walowest = alowest/atot

    wavg = trihigh   * wahigh + \
           trimid    * wamid  + \
           trilow    * walow  + \
           trilowest * walowest
           
    cost = (wavg * FAKTOR)
    return cost

if __name__ == '__main__':
    pass

def unparent_selection(context, selection):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in selection:
        ob.select = True
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

def parent_selection(context, tgt, selection, keep_transform=False):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in selection:
        ob.select = True
    tgt.select=True
    context.scene.objects.active = tgt
    
    bpy.ops.object.parent_set(type='OBJECT', keep_transform=keep_transform)

def move_children(context, src, tgt, root, ignore):
    sources=[]
    for obj in src.children:

        if ignore and ignore in obj:
            continue
        if obj.parent == src:
            sources.append(obj)

    unparent_selection(context, sources)

    for obj in sources:
        obj.parent=tgt
        for mod in [mod for mod in obj.modifiers if mod.type=='ARMATURE']:
            mod.object=root
        sources.extend(move_children(context, obj, obj, tgt, ignore))            

    return sources

def reparent_selection(context, src, tgt, ignore):
    sources=[]
    for obj in src.children:

        if ignore and ignore in obj:
            continue

        sources.append(obj)

    unparent_selection(context, sources)
    context.scene.objects.active = tgt
    bpy.ops.object.parent_set(type='OBJECT')

    for obj in sources:
        for mod in [mod for mod in obj.modifiers if mod.type=='ARMATURE']:
            if mod.object == src:
               mod.object = tgt

    return sources

def fix_modifier_order(context, ob):
    mod_arm_index = -1
    for index, mod in enumerate(ob.modifiers):
        if mod.type=='ARMATURE':
            mod_arm_index = index
            print("fix_modifier_order: %s has armature modifier %s at position %d" % (ob.name, mod.name, index))

    mod_data_index = -1
    mod_data_name  = None
    for index, mod in enumerate(ob.modifiers):
        if mod.type=='DATA_TRANSFER':
            print("fix_modifier_order: %s has datatransfer modifier %s at position %d" % (ob.name, mod.name, index))
            mod_data_index = index
            mod_data_name = mod.name
            break

    if mod_arm_index > mod_data_index > -1:
       print("Need to move weld higher up by",  mod_arm_index - mod_data_index, "slots")

       active = context.scene.objects.active
       context.scene.objects.active = ob
       while mod_arm_index > mod_data_index:
          mod_data_index +=1
          bpy.ops.object.modifier_move_down(modifier=mod_data_name)
       context.scene.objects.active = active

def copy_object_attributes(context, src_armature, tgt_armature, tgt, src):
    print("copy_object_attributes...")
    tgt.select       = src.select
    tgt.hide         = src.hide
    tgt.layers       = src.layers

    if tgt.type=='MESH':
        tgt.data.materials.clear() # ensure the target material slots are clean
        if src.type=='MESH':
            for mat in src.data.materials:
                tgt.data.materials.append(mat)

            mod_arm_index = -1
            for index, mod in enumerate([mod for mod in tgt.modifiers if mod.type=='ARMATURE']):
                print("mod   orig", mod.type, mod.name, mod.object.name)
                if mod.object==src_armature:
                    print("mod change", mod.type, mod.name, mod.object.name)
                    mod.object = tgt_armature

def copy_attributes(context, src_armature, tgt_armature, sources, target_set):

    for src in sources:
        tgt  = target_set.get(src.name.rsplit('.')[0], None)

        if tgt:
            copy_object_attributes(context, src_armature, tgt_armature, tgt, src)

def remove_selection(selected, src):
    for obj in selected:
        if obj.parent == src or any([mod for mod in obj.modifiers if mod.type=='ARMATURE' and mod.object == src]):
            remove_children(obj, context)
            context.scene.objects.unlink(obj)            

def remove_object(context, obj, do_unlink=True):
        context.scene.objects.unlink(obj)
        if get_blender_revision() >= 278000:
            bpy.data.objects.remove(obj, do_unlink)
        else:
            bpy.data.objects.remove(obj)

def remove_text(text, do_unlink=True):
        if get_blender_revision() >= 278000:
            bpy.data.texts.remove(text, do_unlink=do_unlink)
        else:
            bpy.data.texts.remove(text)

def remove_action(action, do_unlink=True):
        if get_blender_revision() >= 278000:
            bpy.data.actions.remove(action, do_unlink=do_unlink)
        else:
            bpy.data.actions.remove(action)

def remove_children(src, context):
    for obj in src.children:
        name = obj.name
        remove_children(obj, context)
        try:
            context.scene.objects.unlink(obj)
            bpy.data.objects.remove(obj)
            log.warning("Removed child %s from its parent %s" % (name, src.name))
        except:
            log.error("Removing of child %s from its parent %s failed" % (name, src.name))

def unlink_children(src, context, unlink=True, remove=False, recursive=False):
    unlinked = []
    for obj in src.children:
        name = obj.name
        if recursive:
            unlinked.extend(unlink_children(obj, context, unlink, remove))
        
        try:
            obj.parent = None
            if unlink:
                context.scene.objects.unlink(obj)
            if unlink and remove and len(obj.children) == 0:
                bpy.data.objects.remove(obj)
            else:
                unlinked.append(obj)

        except:
            print("Removing", name, "from", src.name, "failed")

    return unlinked

def remove_karaage_children(src, context, remove=True):
    unlinked = []
    for obj in [obj for obj in src.children]:
        name = obj.name
        unlinked.extend(remove_karaage_children(obj, context, remove))
        if "karaage-mesh" in obj or (obj.type == 'EMPTY' and len(obj.children)==0):

            try:
                context.scene.objects.unlink(obj)
                if remove:
                    bpy.data.objects.remove(obj)

                else:
                    unlinked.append(obj)
            except:
                print("Removing", name, "from", src.name, "failed")
    return unlinked

def setSelectOption(armobj, bone_names, exclusive=True):
    backup = {}
    for bone in armobj.data.bones:
        if bone.name in bone_names:
            if not bone.select:
                backup[bone.name] = bone.select
                bone.select = True
        else:
            if exclusive and bone.select:
                backup[bone.name] = bone.select
                bone.select = False
    return backup
        
def setDeformOption(armobj, bone_names, exclusive=True):
    backup = {}
    bones = get_modify_bones(armobj)
    for bone in bones:
        if bone.name in bone_names:
            if not bone.use_deform:
                backup[bone.name] = bone.use_deform
                bone.use_deform = True
        else:
            if exclusive and bone.use_deform:
                backup[bone.name] = bone.use_deform
                bone.use_deform = False
    return backup
    
def restoreDeformOption(armobj, backup):
    bones = get_modify_bones(armobj)
    for key, val in backup.items():
        bones[key].use_deform = val
        
def restoreSelectOption(armobj, backup):
    bones = get_modify_bones(armobj)
    for key, val in backup.items():
        bones[key].select = val
        
def removeWeightsFromSelected(obj, weight_group_names):
    active     = bpy.context.scene.objects.active
    bpy.context.scene.objects.active = obj
    original_mode = ensure_mode_is("EDIT") 
    for gname in [ name for name in weight_group_names if name in obj.vertex_groups]:
        bpy.ops.object.vertex_group_set_active(group=gname) 
        bpy.ops.object.vertex_group_remove_from()
        print("Removed selected from vgroup %s" % gname)
    ensure_mode_is(original_mode)
    bpy.context.scene.objects.active = active
    
def removeWeightsFrom(obj, gname):
    active     = bpy.context.scene.objects.active
    bpy.context.scene.objects.active = obj
    original_mode = ensure_mode_is("EDIT") 
    bpy.ops.object.vertex_group_set_active(group=gname) 
    bpy.ops.object.vertex_group_remove_from()
    print("Removed selected from vgroup %s" % gname)
    ensure_mode_is(original_mode)
    bpy.context.scene.objects.active = active

def removeWeightGroups(obj, weight_group_names): 
    for gname in [ name for name in weight_group_names if name in obj.vertex_groups]:
        obj.vertex_groups.remove(obj.vertex_groups[gname])

def removeEmptyWeightGroups(obj):
    if obj and obj.type=='MESH':
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        
        try:
            bm.verts.ensure_lookup_table()
        except:
            pass
            
        dvert_lay = bm.verts.layers.deform.active
        empty_groups = [g.name for g in obj.vertex_groups if not any(v for v in bm.verts if obj.vertex_groups[g.name].index in v[dvert_lay])]
        if len(empty_groups) > 0:
            removeWeightGroups(obj, empty_groups)
        return len(empty_groups)
    else:
        if obj:
            name= obj.name
        else:
            name= "None"
        print("WARN: can not remove weightgroups from Object %s" % name)
        return 0
        
def createEmptyGroups(obj, names=None):
    arm = obj.find_armature()
    if names == None:
        names = [bone.name for bone in get_modify_bones(arm) if bone.use_deform]
    if arm:
        for gname in [name for name in names if not name in obj.vertex_groups]:
            obj.vertex_groups.new(name=gname)

def get_ui_level():
    preferences = getAddonPreferences()
    ui_level = preferences.ui_complexity
    return int(ui_level)

def getAddonPreferences(data=-1):
    if hasattr(bpy.types, "AddonPreferences"):
        user_preferences = bpy.context.user_preferences
        try:
            d = user_preferences.addons[__package__].preferences
        except:
            d = bpy.context.scene.MeshProp
    elif data==-1:
        d = bpy.context.scene.MeshProp
    else:
        d = data
    return d

def always_alter_to_restpose():
    props = getAddonPreferences()
    return props.always_alter_restpose
#

def get_rig_type(rigType=None):
    if rigType == None:
        sceneProps = context.scene.SceneProp
        rigType    = sceneProps.karaageRigType
    return rigType

def get_joint_type(jointType=None):
    if jointType == None:
        sceneProps = context.scene.SceneProp
        jointType    = sceneProps.karaageJointType
    return jointType

def resolve_definition_file(file):
    if os.path.exists(file):
        result = file
    else:
        file = os.path.join(DATAFILESDIR, file)
        result = file if os.path.exists(file) else None
    return file

def get_default_skeleton_definition(filename, rigType=None, comment='get_default_skeleton_definition'):
    #

    if not rigType:
        sceneProps = context.scene.SceneProp
        rigType = sceneProps.karaageRigType
        print("%s: %s use default rigType %s" % (filename, comment, rigType))
    
    definition_file = "avatar_%s_2.xml" % filename

    definition_file = resolve_definition_file(definition_file)
    return definition_file

def get_skeleton_file(rigType = None, comment='get_skeleton_file'):
    return get_default_skeleton_definition("skeleton", rigType = rigType, comment = comment)

def get_lad_file(rigType = None, comment = "get_lad_file"):
    return get_default_skeleton_definition("lad", rigType = rigType, comment = comment)

def get_shape_filename(name):
    if not os.path.exists(TMP_DIR):
        os.makedirs(TMP_DIR)
    return os.path.join(TMP_DIR, name+'.xml')

Identity = Matrix()    
def print_mat(msg, Mat):
    if Mat == Identity:
        print(msg,"Identity")
    else:
        print(msg,Mat)

def get_version_info(armobj):
    karaageversion = "%s.%s.%s" % (bl_info['version'])
    rigid   = armobj.get('karaage', None)
    rigType = armobj.RigProps.RigType

    if 'version' in armobj:
        rigversion = "%s.%s.%s" % (armobj['version'][0],armobj['version'][1],armobj['version'][2], )
    else:
        rigversion = None

    return karaageversion, rigversion, rigid, rigType
    
def copydir(src,dst, overwrite=False):
    for root, dirs, files in os.walk(src):
        srcdir=root
        folder=srcdir[len(src):]
        dstdir=dst+folder
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)
            
        for file in files:
            dstfile = os.path.join(dstdir,file)
            if not os.path.exists(dstfile) or overwrite:
                srcfile = os.path.join(srcdir,file)
                shutil.copyfile(srcfile, dstfile)

class slider_context():

    def __init__(self):
        pass

    def __enter__(self):
        self.was_locked = get_disable_update_slider_selector()
        set_disable_update_slider_selector(True)
        return self.was_locked

    def __exit__(self, type, value, traceback):
        set_disable_update_slider_selector(self.was_locked)
        if type or value or traceback:
            log.error("Exception type: %s" % type )
            log.error("Exception value: %s" % value)
            log.error("traceback: %s" % traceback)
            raise

disable_update_slider_selector=False
def set_disable_update_slider_selector(state):
    global disable_update_slider_selector
    disable_update_slider_selector=state

def get_disable_update_slider_selector():
    global disable_update_slider_selector
    return disable_update_slider_selector

updateShapeActive = False
def is_updating():
    global updateShapeActive
    return updateShapeActive

def enforce_armature_update(scene, armobj):
    global updateShapeActive

    try:
        updateShapeActive = True
        omode = ensure_mode_is('EDIT', object=armobj, toggle_mode='POSE')
        ensure_mode_is(omode, object=armobj)
        updateShapeActive = False
        scene.update()
    except:
        pass

def get_modifiers(ob, type):
    return [mod for mod in ob.modifiers if mod.type==type]
    
def get_tri_count(faces, loops):
    tris = 0
    if faces > 0:
        tris = int(((loops / faces) - 2) * faces + 0.5)
    return tris

def merge_dicts(x, y):
    '''Given two dicts, merge them into a new dict as a shallow copy.'''
    z = x.copy()
    z.update(y)
    return z

def shorten_text(text, maxlen=24, cutbegin=False, cutend=False):
    if len(text) <= maxlen: return text

    if cutbegin:
        newtext = '...' + text[-maxlen:]
    elif cutend:
        newtext = text[0:maxlen] + '...'
    else:
        splitlen = int((maxlen-2)/2)
        newtext = text[0:splitlen] + "..." + text[-splitlen:]
    return newtext

def closest_point_on_mesh(ob,co):
    if get_blender_revision() > 276000:
        status, co, no, index = ob.closest_point_on_mesh(co)
    else:
        co, no, index = ob.closest_point_on_mesh(co)
        status = index > -1
    return status, co, no, index

def ray_cast(ob, co, nor):
    if get_blender_revision() > 276000:
        status, co, no, index = ob.ray_cast(co, nor)
    else:
        co, no, index = ob.ray_cast(co, nor)
        status = index > -1
    return status, co, no, index

def get_center(context, ob):

    active = context.scene.objects.active    
    context.scene.objects.active = ob
    cursor_location = context.scene.cursor_location
    
    omode = ensure_mode_is('EDIT')

    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.view3d.snap_cursor_to_selected()
    loc = context.scene.cursor_location

    context.scene.cursor_location = cursor_location
    ensure_mode_is(omode)
    context.scene.objects.active = active
    return loc

def remember_selected_objects(context):
    selected = []
    for ob in context.selected_objects:
        selected.append(ob.name)
    return selected

def restore_selected_objects(context, selected):
    bpy.ops.object.select_all(action='DESELECT')
    scene = context.scene
    for name in selected:
        ob = scene.objects.get(name)
        if ob: 
            ob.select=True

def check_selected_change(context, oselected, msg=''):
    selected = remember_selected_objects(context)
    if len(set(selected) - set(oselected)) > 0 or len(set(oselected) - set(selected)) > 0:
        print("Selection changed:", msg)
        print ( "Original "  , *oselected )
        print ( "Changed to ", *selected )

repo_container = {}
def reset_karaage_repository():
    global repo_container
    repo_container.clear()

def ensure_karaage_repository_is_loaded():
    global repo_container
    if len(repo_container) == 0:
        filepath = ASSETS

        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            data_to.objects = data_from.objects
        repo_container = {ob.name:ob for ob in data_to.objects}

def find_view_context(context, obj=None):
    ctx = context.copy()
    for window in context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                ctx['window']        = window
                ctx['screen']        = screen
                ctx['area']          = area
                if obj:
                    ctx['active_object'] = obj
                break
    return ctx

def matrixScale(scale, M=None, replace=False):
    if M == None:
        M = Matrix()

    if replace:
        M[0][0] = scale[0]
        M[1][1] = scale[1]
        M[2][2] = scale[2]
   
    else:
        M[0][0] *= scale[0]
        M[1][1] *= scale[1]
        M[2][2] *= scale[2]

    return M

def matrixLocation(loc, M=None, replace=False):
    if M == None:
        M = Matrix()

    if replace:
        M[0][3] = loc[0]
        M[1][3] = loc[1]
        M[2][3] = loc[2]
    else:
        M[0][3] += loc[0]
        M[1][3] += loc[1]
        M[2][3] += loc[2]

    return M

def sanitize_f(f):
    result = f if abs(f) > 0.000001 else 0
    return result   

def sanitize(vec):
    result = [sanitize_f(f) for f in vec]
    return Vector(result)

def clear_transforms(context, srcobjs):
    old_parents = {}
    bpy.ops.object.select_all(action='DESELECT')
    
    for ob in srcobjs:
        old_parents[ob.name]=ob.parent
        ob.select=True

    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    return old_parents

def transform_origins_to_location(context, srcobjs, loc):
    scene = context.scene
    active = context.object
    amode = ensure_mode_is('OBJECT')
    selected_objects = remember_selected_objects(context)
    cloc = context.scene.cursor_location.copy()
    scene.cursor_location = loc.copy()

    bpy.ops.object.select_all(action='DESELECT')
    for ob in srcobjs:
        ob.select = True
        log.debug("transform_origins: Add [%s %s] to set" % (ob.type, ob.name) )

    log.info("transform_origins_to_location: Move %d Origins to %s" % (len(srcobjs), scene.cursor_location))
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    restore_selected_objects(context, selected_objects)
    scene.cursor_location = cloc
    scene.objects.active = active
    ensure_mode_is(amode)

def transform_objects_to_location(context, srcobjs, loc):
    for ob in srcobjs:

        ob.location = loc.copy()
        log.info("transform_location: moved [%s %s] to %s" % (ob.type, ob.name, loc) )

def transform_origins_to_target(context, tgtobj, srcobjs, delta=V0, set_origin=True):
    scene = context.scene
    active = context.active_object
    amode = ensure_mode_is('OBJECT')
    selected_objects = remember_selected_objects(context)
        
    cloc   = scene.cursor_location.copy()
    scene.cursor_location = tgtobj.matrix_world.translation.copy()

    scene.objects.active = tgtobj

    bpy.ops.object.select_all(action='DESELECT')
    tgtobj.select=True

    for ob in srcobjs:
        ob.select = True
        if not set_origin:
            ob.matrix_world.translation -= delta

    log.info("transform_origins_to_target: Move %d Origins to %s" % (len(srcobjs), scene.cursor_location))
    if set_origin:
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    restore_selected_objects(context, selected_objects)
    
    scene.cursor_location = cloc
    scene.objects.active  = active
    ensure_mode_is(amode)

def transform_rootbone_to_origin(context, armobj):
    log.info("Transform Root Bone to Origin for [%s]" % context.object.name)
    active = context.object
    amode = ensure_mode_is("OBJECT", context=context)

    context.scene.objects.active = armobj
    omode = ensure_mode_is("EDIT", context=context)
    bones  = armobj.data.edit_bones
    origin_bone = bones.get('Origin')
    diff = origin_bone.head.copy()

    origin_bone.tail -= diff
    origin_bone.head  = Vector((0,0,0))
    log.info("Transform Root Bone has been reset to match Origin for [%s]" % context.object.name)
    ensure_mode_is(omode, context=context)

    context.scene.objects.active = active
    ensure_mode_is(amode, context=context)

    return diff

def transform_origin_to_rootbone(context, armobj):
    log.info("Transform Origin to Root Bone for [%s]" % armobj.name)
    active = context.object
    cloc   = context.scene.cursor_location.copy()
    bones  = get_modify_bones(armobj)
    origin_bone = bones.get('Origin')

    context.scene.objects.active = armobj
    omode = ensure_mode_is("OBJECT")
    selected_objects = remember_selected_objects(context)
    bpy.ops.object.select_all(action='DESELECT')
    armobj.select=True

    diff =  Vector(origin_bone.head).copy()
    context.scene.cursor_location = Vector(armobj.location) + Vector(origin_bone.head)

    print("Move armobj origin to cursor at %s" % context.scene.cursor_location)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    print("Origin of armature is now at %s" % armobj.location)
    ensure_mode_is("OBJECT")
    restore_selected_objects(context, selected_objects)
    context.scene.cursor_location = cloc
    context.scene.objects.active = active
    return diff
    
def set_bone_select_mode(armobj, state, boneset=None, additive=True):
    bones = get_modify_bones(armobj)
    if boneset == None:
        boneset = bones

    store = {}
    for bone in bones:
        newstate = state if bone.name in boneset else bone.select if additive else not state
        if newstate:
            print("set_bone_select_mode: set bone", bone.name, newstate)
        store[bone.name]=bone.select
        bone.select = bone.select_head = bone.select_tail = newstate
    return store

def set_bone_select_restore(armobj, store):
    bones = get_modify_bones(armobj)
    for name in store.keys():
        bone = bones.get(name,None)
        if bone:
            bone.select = bone.select_head = bone.select_tail = store.get(name)

def bone_is_visible(armobj, bone):
    if bone.hide:
        return False

    for layer in range(32):
        if armobj.data.layers[layer] and bone.layers[layer]:
            return True
    return False

def match_armature_scales(source, target):
    tlocs = [v for bone in target.data.bones if bone.use_deform for v in (bone.head_local, bone.tail_local)]
    slocs = [v for bone in source.data.bones if bone.use_deform for v in (bone.head_local, bone.tail_local)]
    source_size = source.scale[2] * (max([location[2] for location in slocs]) - min([location[2] for location in slocs]))
    target_size = target.scale[2] * (max([location[2] for location in tlocs]) - min([location[2] for location in tlocs]))
    source.scale *=  target_size / source_size
    print("Source size:", source.scale[2]*source_size, "Target size:", target.scale[2]*target_size)

def get_gp(context, gname='gp'):
    gp = context.scene.grease_pencil
    if not gp:
        gp = bpy.data.grease_pencil.get(gname, None)
        if not gp:
            gp = bpy.data.grease_pencil.new(gname)
            print("Created new Grease Pencil", gp.name)
        context.scene.grease_pencil = gp
        bpy.ops.gpencil.draw('EXEC_DEFAULT')
        print("Added Grease Pencil %s to current scene" % (gp.name) )
    return gp

def gp_init_callback(context, gp, palette):
    if palette:
        ob=context.object
        colcount = 0
        if ob:
            armobj = ob if ob.type=='ARMATURE' else ob.find_armature()
            if armobj:
                for bgroup in armobj.pose.bone_groups:
                    col = bgroup.colors.normal
                    color = palette.colors.new()
                    color.color = bgroup.colors.normal
                    color.name  = bgroup.name
                colcount = len(palette.colors)
                print("Added %d colors from Armature %s to palette %s" % (colcount, armobj.name, palette.name) )
        if colcount == 0:
            color = palette.colors.new()
            color.color=(1,0,1)
            print("Added default color to palette", palette.name)
    return
    
def get_gp_palette(context, gname='gp', pname='gp', callback=gp_init_callback):
    gp = get_gp(context, gname)
    palette = gp.palettes.get(pname)
    if not palette:
        palette = gp.palettes.new(pname, set_active=True)
        print("Added new Grease Pencil palette", palette.name)
        if callback:
            callback(context, gp, palette)
        else:
            color = palette.colors.new()
            color.color=(1,1,1)
            print("Added default color to palette", palette.name)
    return palette

def get_gp_color(palette, color_index=0 ):
    ccount = len(palette.colors)

    if color_index >= ccount:
        missingCount = color_index + 1 - ccount
        for i in range(missingCount):
            palette.colors.new()
        print("Added %d Pencil color slots" % (missingCount))
    color = palette.colors[color_index]
    return color

def get_gp_layer(context, gname='gp', lname='gp'):
    gp = get_gp(context, gname)
    if lname in gp.layers:
        layer = gp.layers[lname]
    else:
        layer = gp.layers.new(lname, set_active=True)
        print("Added new Grease Pencil layer", layer.info)
    return layer

def get_gp_frame(context, gname='gp', lname='gp'):
    layer = get_gp_layer(context, gname, lname)
    if len(layer.frames) == 0:
        frame = layer.frames.new(context.scene.frame_current)
    else:
        frame = layer.frames[0]
    return frame

def get_gp_stroke(context, gname='gp', lname='gp', pname='gp', color_index=0, callback=gp_init_callback):
    palette = get_gp_palette(context, gname=gname, pname=pname, callback=callback)
    color   = get_gp_color(palette, color_index)
    frame   = get_gp_frame(context, gname, lname)
    stroke  = frame.strokes.new(colorname=color.name)
    stroke.draw_mode = '3DSPACE'
    return stroke

def gp_draw_cross(context, locVector, sizeVector=Vector((0.01, 0.01, 0.01)), gname='gp', lname='gp', pname='gp', color_index=0, callback=gp_init_callback, dots=0):
    lines = [Vector((sizeVector[0],0,0)), Vector((0,sizeVector[1],0)), Vector((0,0,sizeVector[2]))]

    for line in lines:
        fromVector = locVector + line
        toVector = locVector - line
        gp_draw_line(context, fromVector, toVector, gname, lname, pname, color_index, callback, dots)

def gp_draw_line(context, fromVector, toVector, gname='gp', lname='gp', pname='gp', color_index=0, callback=gp_init_callback, dots=0):
    dotcount=dots+1
    substroke = (toVector - fromVector) / dotcount
    f = fromVector.copy()

    for i in range (ceil(dotcount/2)):
        t = f+substroke
        stroke = get_gp_stroke(context, gname, lname, pname, color_index, callback=callback)
        stroke.points.add(2)
        stroke.points.foreach_set("co", f.to_tuple() + t.to_tuple() )
        f += 2*substroke

def matrix_as_string(M):
    sm="\n"
    for i in range(0,4):
        sm += "Matrix((({: 6f}, {: 6f}, {: 6f}, {: 6f}),\n".format  (*M[i])
    return sm

def is_linked_hierarchy(selection):
    if not selection:
        return False

    for ob in selection:
        if is_linked_item(ob):
            log.warning("Found linked object %s" % ob.name)
            return True
        
        if is_linked_hierarchy(ob.children):
            log.warning("Found linked childlist in %s" % ob.name)
            return True
    return False

def is_linked_item(obj):
    if obj.library != None:
        return True
    if obj.dupli_group and obj.dupli_group.library != None:
        return True
    if obj.proxy and obj.proxy.library != None:
        return True
    return False

def use_sliders(context):
    return context.scene.SceneProp.panel_appearance_enabled

def remove_key(item, key):
    if key in item:
        del item[key]

def get_joint_offset(dbone):
    h = Vector(dbone.get('ohead', (0,0,0)))
    if h.magnitude <= MIN_JOINT_OFFSET:
        h = V0.copy()
    t = Vector(dbone.get('otail', (0,0,0)))
    if t.magnitude <= MIN_JOINT_OFFSET:
        t = V0.copy()
    return h, t
    
def set_head_offset(bone, head, msg=""):
    if not bone:
        return
    if head:
        bone['ohead'] = head
    elif 'ohead' in bone:
        del bone['ohead']

def set_tail_offset(bone, tail, msg=""):
    if not bone:
        return
    if tail:
        bone['otail'] = tail
    elif 'otail' in bone:
        del bone['otail']

def has_head_offset(bone):
    if not bone:
        return False
    return 'ohead' in bone

def has_tail_offset(bone):
    if not bone:
        return False
    return 'otail' in bone

def logtime(tic, msg, indent=0, mintime=20):
    toc = time.time()
    d = (toc - tic) * 1000
    if d > mintime:
        timerlog.debug("%s% 4.0f millis - %s" % ('_'*indent, d, msg))
    return toc
