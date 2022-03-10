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

from collections import OrderedDict
import bpy
from bpy.props import *
import  xml.etree.ElementTree as et
from mathutils import Vector, Matrix
import time, logging, traceback, os, gettext
from math import fabs, radians
from bpy.app.handlers import persistent

from . import context_util, const, data, util, rig
from .util import rescale, Skeleton, s2b, PVector
from .const import *
from .context_util import *

LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locale')
translator = gettext.translation('karaage', LOCALE_DIR, fallback=True)
_ = translator.gettext

log = logging.getLogger("karaage.shape")
timerlog = logging.getLogger("karaage.timer")
updatelog = logging.getLogger('karaage.update')

MSG_UPDATE_SHAPE = 'Base Shape not found.|'\
                 +  'YOUR ACTION:\n'\
                 +  '- Detach the Sliders (No Sliders)\n'\
                 +  '- Adjust the Karaage Shape to your mesh (if necessary)\n'\
                 +  '  Or load your original character shape from file\n'\
                 +  '- Attach the Sliders again (SL Appearance).\n'\
                 +  '\nEXPLAIN:\n'\
                 +  'Karaage was looking for the reference Shape of your mesh item.\n'\
                 +  'This reference shape is normally created whenever you attach\n'\
                 +  'the shape sliders to your mesh.\n'\
                 +  'However, the reference shape does not exist in your environment.\n'\
                 +  'This is probably caused by an update from an earlier Karaage version|'

HANDS = {
0:{'id':0, 'label': _('Spread'), 'mesh': 'Hands_Spread'},
1:{'id':1, 'label': _('Relaxed'), 'mesh': 'hands_relaxed_101'},
2:{'id':2, 'label': _('Point'), 'mesh': 'hands_point_102'},
3:{'id':3, 'label': _('Fist'), 'mesh': 'hands_fist_103'},
4:{'id':4, 'label': _('L Relaxed'), 'mesh': 'hands_relaxed_l_666'},
5:{'id':5, 'label': _('L Point'), 'mesh': 'hands_point_l_667'},
6:{'id':6, 'label': _('L Fist'), 'mesh': 'hands_fist_l_668'},
7:{'id':7, 'label': _('R Relaxed'), 'mesh': 'hands_relaxed_r_669'},
8:{'id':8, 'label': _('R Point'), 'mesh': 'hands_point_r_670'},
9:{'id':9, 'label': _('R Fist'), 'mesh': 'hands_fist_r_671'},
10:{'id':10, 'label': _('R Salute'), 'mesh': 'hands_salute_r_766'},
11:{'id':11, 'label': _('Typing'), 'mesh': 'hands_typing_672'},
12:{'id':12, 'label': _('R Peace'), 'mesh': 'hands_peace_r_791'},
13:{'id':13, 'label': _('R Splayed'), 'mesh': 'hands_spread_r_792'}, 
}

SHAPEUI = OrderedDict()
SHAPEUI[_("Body")] = [ "male_80", "height_33", "thickness_34", "body_fat_637"]
SHAPEUI[_("Head")] = [ "head_size_682", "squash_stretch_head_647", "head_shape_193", "egg_head_646", "head_length_773", "face_shear_662", "forehead_angle_629", "big_brow_1", "puffy_upper_cheeks_18", "sunken_cheeks_10", "high_cheek_bones_14"]
SHAPEUI[_("Eyes")] = [ "eye_size_690", "wide_eyes_24", "eye_spacing_196", "eyelid_corner_up_650", "eyelid_inner_corner_up_880", "eye_depth_769", "upper_eyelid_fold_21", "baggy_eyes_23", "puffy_lower_lids_765", "eyelashes_long_518", "pop_eye_664"]
SHAPEUI[_("Eyebrows")] = ["eyebrow_size_119", "eyebrow_density_750", "lower_eyebrows_757", "arced_eyebrows_31", "pointy_eyebrows_16"]
SHAPEUI[_("Ears")] = [ "big_ears_35", "ears_out_15", "attached_earlobes_22", "pointy_ears_796"]
SHAPEUI[_("Nose")] = [ "nose_big_out_2", "wide_nose_517", "broad_nostrils_4", "low_septum_nose_759", "bulbous_nose_20", "noble_nose_bridge_11", "lower_bridge_nose_758", "wide_nose_bridge_27", "upturned_nose_tip_19", "bulbous_nose_tip_6", "crooked_nose_656"]
SHAPEUI[_("Mouth")] = [ "lip_width_155", "tall_lips_653", "lip_thickness_505", "lip_ratio_799", "mouth_height_506", "mouth_corner_659", "lip_cleft_deep_764", "wide_lip_cleft_25", "shift_mouth_663"]
SHAPEUI[_("Chin")] = [ "weak_chin_7", "square_jaw_17", "deep_chin_185", "jaw_angle_760", "jaw_jut_665", "jowls_12", "cleft_chin_5", "cleft_chin_upper_13", "double_chin_8"]
SHAPEUI[_("Torso")] = [ "torso_muscles_649", "torso_muscles_678", "neck_thickness_683", "neck_length_756", "shoulders_36", "breast_size_105", "breast_gravity_507", "breast_female_cleavage_684", "chest_male_no_pecs_685", "arm_length_693", "hand_size_675", "torso_length_38", "love_handles_676", "belly_size_157"]
SHAPEUI[_("Legs")] = [ "leg_muscles_652", "leg_length_692", "hip_width_37", "hip_length_842", "butt_size_795", "male_package_879", "saddlebags_753", "bowed_legs_841", "foot_size_515"]
SHAPEUI[_("Shoes")] = [ "heel_height_198", "heel_shape_513", "toe_shape_514", "shoe_toe_thick_654", "platform_height_503", "shoe_platform_width_508"]
SHAPEUI[_("Shirt")] = [ "loose_upper_clothing_828", "shirtsleeve_flair_840"]
SHAPEUI[_("Pants")] = [ "pants_length_815", "loose_lower_clothing_816", "leg_pantflair_625", "low_crotch_638"]
SHAPEUI[_("Skirt")] = [ "skirt_looseness_863", "skirt_bustle_848"]
SHAPEUI[_("Hair")] = [ "hair_volume_763", "hair_front_133", "hair_sides_134" , "hair_back_135" , "hair_big_front_181" , "hair_big_top_182" , "hair_big_back_183" , "front_fringe_130" , "side_fringe_131" , "back_fringe_132" , "hair_sides_full_143" , "hair_sweep_136" , "hair_shear_front_762" , "hair_shear_back_674" , "hair_taper_front_755" , "hair_taper_back_754" , "hair_rumpled_177" , "pigtails_785" , "ponytail_789" , "hair_spiked_184" , "hair_tilt_137" , "hair_part_middle_140" , "hair_part_right_141" , "hair_part_left_142" , "bangs_part_middle_192"]

#

#

#

SHAPE_FILTER = OrderedDict()
SHAPE_FILTER[_("Skeleton")] = [
                              "height_33", "thickness_34", 
                              "head_size_682", "head_length_773", "face_shear_662",
                              "eye_size_690", "eye_spacing_196", "eye_depth_769",
                              "neck_thickness_683", "neck_length_756", "shoulders_36", "arm_length_693", "hand_size_675", "torso_length_38",
                              "leg_length_692", "hip_width_37", "hip_length_842",
                              "heel_height_198", "platform_height_503",
                              "nose_big_out_2", "wide_nose_517", "broad_nostrils_4", "bulbous_nose_20", "noble_nose_bridge_11", "upturned_nose_tip_19",
                              "lower_bridge_nose_758", "wide_nose_bridge_27", "crooked_nose_656", "low_septum_nose_759", "bulbous_nose_tip_6",
                              "lip_width_155",  "tall_lips_653", "lip_thickness_505", "lip_ratio_799", "mouth_height_506", "mouth_corner_659",
                              "lip_cleft_deep_764", "wide_lip_cleft_25", "shift_mouth_663", 
                              "big_ears_35", "pointy_ears_796",
                              "deep_chin_185","jaw_jut_665", "weak_chin_7", "jaw_angle_760", "double_chin_8", "square_jaw_17", "head_shape_193",
                              "wide_eyes_24",  "eyelid_corner_up_650", "eyelid_inner_corner_up_880", "upper_eyelid_fold_21", "puffy_lower_lids_765", "baggy_eyes_23",
                              "forehead_angle_629", "big_brow_1", "puffy_upper_cheeks_18", "sunken_cheeks_10", "high_cheek_bones_14", "egg_head_646", "squash_stretch_head_647"
                              ]
SHAPE_FILTER[_("Changed")] = []
SHAPE_FILTER[_("Fitted")]  = [
                             "body_fat_637", "squash_stretch_head_647", "torso_muscles_649", "torso_muscles_678",
                             "breast_size_105", "breast_gravity_507", "breast_female_cleavage_684",
                             "love_handles_676", "belly_size_157", "chest_male_no_pecs_685",
                             "leg_muscles_652", "saddlebags_753", "butt_size_795"
                             "bowed_legs_841", "foot_size_515"
                             ]
SHAPE_FILTER[_("Extended")] = [
                              "nose_big_out_2", "wide_nose_517", "broad_nostrils_4", "bulbous_nose_20", "noble_nose_bridge_11", "upturned_nose_tip_19",
                              "lower_bridge_nose_758", "wide_nose_bridge_27", "crooked_nose_656", "low_septum_nose_759", "bulbous_nose_tip_6",
                              "lip_width_155",  "tall_lips_653", "lip_thickness_505", "lip_ratio_799", "mouth_height_506", "mouth_corner_659",
                              "lip_cleft_deep_764", "wide_lip_cleft_25", "shift_mouth_663", 
                              "big_ears_35", "pointy_ears_796",
                              "deep_chin_185","jaw_jut_665", "weak_chin_7", "jaw_angle_760", "double_chin_8", "square_jaw_17", "head_shape_193",
                              "wide_eyes_24",  "eyelid_corner_up_650", "eyelid_inner_corner_up_880", "upper_eyelid_fold_21", "puffy_lower_lids_765", "baggy_eyes_23",
                              "forehead_angle_629", "big_brow_1", "puffy_upper_cheeks_18", "sunken_cheeks_10", "high_cheek_bones_14", "egg_head_646", "squash_stretch_head_647"
                              ]

DEFORMER_NORMALIZE_EXCEPTIONS = ["head_shape_193", "head_length_773", "face_shear_662",
                                 "eye_size_690", "eye_spacing_196", "eye_depth_769"]

def get_shapekeys(obj):
    section = obj.ShapeDrivers.Sections
    try:
        result = SHAPEUI[section]
    except:
        if section == "Changed":
            result = []
            for section, pids in SHAPEUI.items():
                for pid in pids:
                    D = obj.ShapeDrivers.DRIVERS[pid][0]
                    s = D['sex']
                    if not is_set_to_default(obj,pid):
                        result.append(pid)
        else:
            result = SHAPE_FILTER[section]
    return result

def is_set_to_default(obj, pid):
    if pid == "male_80":
        v = getattr(obj.ShapeDrivers,pid)
        return not v
        
    value   = getShapeValue(obj, pid)
    default = get_default_value(obj,pid)               
    result = fabs(value - default)
    return result < 0.001
    
def get_default_value(obj,pid):
    D = obj.ShapeDrivers.DRIVERS[pid][0]
    if pid == "male_80":
        return False
        
    default = rescale(D['value_default'], D['value_min'], D['value_max'], 0, 100)                        
    return default
    
class ShapeDrivers(bpy.types.PropertyGroup):
    bl_description = "Shape drivers control how the Shape Sliders\naffect the bones and Shape Keys of the Karaage character.\nThe data is loaded form the avatar lad file"
    pass

class ShapeValues(bpy.types.PropertyGroup):

    pass

def shapeInitialisation():
    
    ##

    ##
    bpy.types.Object.ShapeDrivers   = PointerProperty(type = ShapeDrivers)
    bpy.types.Object.ShapeValues    = PointerProperty(type = ShapeValues)

    ShapeDrivers.Freeze =  IntProperty(name = _('Freeze'), min = 0, max = 1,
                                    soft_min = 0, soft_max = 1, default = 0) 

def pivotLeftUpdate(self, context):
    scene = context.scene
    obj = scene.objects.active    
    pivotUpdate(obj, scene, 'Left')

def pivotRightUpdate(self, context):
    scene = context.scene
    obj = scene.objects.active    
    pivotUpdate(obj, scene, 'Right')

def pivotUpdate(obj, scene, side, refresh=True):

    def do_update(val, ikFootBall, ikHeel, ikFootPivot):

        ballh = ikFootBall.head_local
        heelh = ikHeel.head_local
        posh = val*(ballh-heelh)+heelh
        ikFootPivot.head_local = posh

        ballt = ikFootBall.tail_local
        heelt = ikHeel.tail_local
        post = val*(ballt-heelt)+heelt
        ikFootPivot.tail_local = post

    try:
        val = obj.IKSwitches.IK_Foot_Pivot_L if side=='Left' else obj.IKSwitches.IK_Foot_Pivot_R
        ikFootBall = obj.data.bones['ikFootBall'+side]
        ikHeel = obj.data.bones['ikHeel'+side]
        ikFootPivot = obj.data.bones['ikFootPivot'+side]
        do_update(val, ikFootBall, ikHeel, ikFootPivot)

        val = obj.IKSwitches.IK_HindLimb3_Pivot_L if side=='Left' else obj.IKSwitches.IK_HindLimb3_Pivot_R
        ikFootBall = obj.data.bones['ikHindFootBall'+side]
        ikHeel = obj.data.bones['ikHindHeel'+side]
        ikFootPivot = obj.data.bones['ikHindFootPivot'+side]
        do_update(val, ikFootBall, ikHeel, ikFootPivot)

        if refresh:
            util.enforce_armature_update(scene, obj)
    except:
        pass

def get_driven_bones(dbones, DRIVERS, D, indent=""):
    driven_bones = {}
    driven = D.get('driven', None)
    bones  = D.get('bones', None)
    joint_count = 0
    if bones:
        scales = []
        offsets= []
        for b in bones:
            bname = b['name']
            o = Vector(b.get('offset', V0)).magnitude
            s = b.get('scale', None)
            if s:
                s = Vector(s).magnitude
                if s > 0 or o > 0:
                    dos = driven_bones.get(bname,[False,False])
                    driven_bones[bname] = [o>0 or dos[0], s>0 or dos[1]] 
                    if o>0:
                        offsets.append(bname)
                        dbone = dbones.get(bname,None)
                        mbone = dbones.get('m'+bname,None)
                        if (util.has_head_offset(dbone) or util.has_head_offset(mbone)):
                            joint_count += 1

    if driven:

        for D2 in driven:
            dpid = D2['pid']
            DRIVER = DRIVERS[dpid]
            for DD in DRIVER:
                dpid = DD['pid']

                subbones, hj = get_driven_bones(dbones, DRIVERS, DD, indent+"    ")
                joint_count += hj
                for key,val in subbones.items():
                    dos = driven_bones.get(key,[False,False])
                    driven_bones[key] = [val[0] or dos[0], val[1] or dos[1]] 

    return driven_bones, joint_count

def print_driven_bones(context=None):
    if not context:
        context=bpy.context
    arm = util.get_armature(context.object)
    if not arm:
        return False
    ensure_drivers_initialized(arm)
    DRIVERS= arm.ShapeDrivers.DRIVERS
    text = bpy.data.texts.new("slider_info")
    for key in SHAPEUI.keys():
        text.write("[Section:%s]\n" % key)
        has_entries=False
        for pid in SHAPEUI[key]:
            for D in DRIVERS[pid]:
                dpid = D['pid']
                bones, joint_count = get_driven_bones(arm.data.bones, DRIVERS, D)
                if len(bones) > 0:
                    label = pid
                    if not has_entries:
                        text.write("\n+%s-+-%s-+-%s-%s +\n" % ('-'*30, '-'*25, '-'*5, '-'*5))
                        has_entries=True
                    keys = sorted(bones.keys())
                    for key in keys:
                        val = bones[key]
                        text.write("|%30s | %25s | %5s %5s |\n" % (label, key, 'trans' if val[0] else '', 'scale' if val[1] else ''))
                        label=''
                    text.write("+%s-+-%s-+-%s-%s +\n" % ('-'*30, '-'*25, '-'*5, '-'*5))
        if has_entries:
            text.write("\n")
    return True

def html_driven_bones(context, text_name, HEADER, FOOTER, SECTION, SECTIONELEMENT, br="\n"):
    arm = util.get_armature(context.object)
    if not arm:
        return False
    ensure_drivers_initialized(arm)
    DRIVERS= arm.ShapeDrivers.DRIVERS
    text = bpy.data.texts.new(text_name)
    sections=[]
    for key in SHAPEUI.keys():
        dict = {}
        dict['section'] = key
        sectionelements=[]
        has_influenced_bones = False
        for pid in SHAPEUI[key]:
            for D in DRIVERS[pid]:
                bones, joint_count = get_driven_bones(arm.data.bones, DRIVERS, D)
                if len(bones) > 0:
                    has_influenced_bones = True
                    dict['slider'] = pid[0:pid.rfind('_')].replace('_', ' ').title()
                    bonelist  = []
                    translist = []
                    scalelist = []
                    keys = sorted(bones.keys())
                    for key in keys:
                        val = bones[key]
                        trans = 'trans' if val[0] else '-'
                        scale = 'scale' if val[1] else '-'
                        bonelist.append(key)
                        translist.append(trans)
                        scalelist.append(scale)
                    dict['bonelist']  = br.join(bonelist)
                    dict['translist'] = br.join(translist)
                    dict['scalelist'] = br.join(scalelist)
                    sectionelements.append(SECTIONELEMENT % dict)
        if has_influenced_bones:
            dict['elements'] = "\n".join(sectionelements)
            sections.append(SECTION % dict)
    dict['canvas'] = "\n".join(sections)
    canvas = HEADER % dict
    footer = FOOTER % dict
    text.write(canvas)
    text.write(footer)
    return True

class ShapeCopy(bpy.types.Operator):
    """Copy Current Shape from active Armature into a temporary shape Buffer"""
    bl_idname = "karaage.shape_copy"
    bl_label = "Copy Shape"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        armobj = util.get_armature(ob)
        return armobj != None

    def execute(self, context):
        ob = context.object
        armobj = util.get_armature(ob)
        context.scene['shape_buffer'] = asDictionary(armobj, full=True)
        return {'FINISHED'}

class ShapePaste(bpy.types.Operator):
    """Paste Shape from internal shape Buffer into active Karaage Armature"""
    bl_idname = "karaage.shape_paste"
    bl_label = "Paste Shape"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        armobj = util.get_armature(ob)
        if armobj == None:
            return False
        return context.scene.get('shape_buffer') != None

    def execute(self, context):
        ob = context.object
        armobj = util.get_armature(ob)
        shape_data = context.scene.get('shape_buffer')
        fromDictionary(armobj, shape_data)
        return {'FINISHED'}
    
class PrintSliderRelationship(bpy.types.Operator):
    """Print slider relationship to console"""
    bl_idname = "karaage.print_slider_relationship"
    bl_label = "Slider Details"
    
    WP_HEADER        = "%(canvas)s"
    WP_FOOTER        = ""
    WP_BR            = "\n"
    WP_SECTION       = '[symple_toggle title="%(section)s" state="closed"] %(elements)s [/symple_toggle]'
    WP_SECTIONELEMENT='''
<div class="row-fluid">
<div class="rhcol span4">%(slider)s</div>
<div class="rhcol span4">%(bonelist)s</div>
<div style="text-align: center;" class="rhcol span2">%(translist)s</div>
<div style="text-align: center;" class="rhcol span2">%(scalelist)s</div>
</div>'''

    HTML_HEADER        = '''<html>
<head>
<style>
.page      {font-family: "Segoe UI",Arial,sans-serif;}
.section   {padding:1px;}
.slider    {padding-left: 15px; vertical-align:top; width:15em;}
.bonelist  {padding-left: 15px; vertical-align:top; width:15em;}
.translist {padding-left: 15px; padding-right:15px;text-align: center; vertical-align:top;}
.scalelist {padding-left: 15px; padding-right:15px;text-align: center; vertical-align:top;}
</style>
</head>
<body class="page">%(canvas)s'''
    HTML_FOOTER        = "</body></html>"
    HTML_BR            = "<br/>\n"
    HTML_SECTION       = '<h2>%(section)s</h2> <table border style="background-color:#dddddd;padding:10px;">%(elements)s</table>'
    HTML_SECTIONELEMENT='''
<tr class="section">
<td class="slider">%(slider)s</td>
<td class="bonelist">%(bonelist)s</td>
<td class="translist">%(translist)s</td>
<td class="scalelist">%(scalelist)s</td>
</tr>'''
    
    @classmethod
    def poll(self, context):
        ob = context.object
        return ob.type=='ARMATURE'

    def execute(self, context):

        html_driven_bones(context, "slider_info_html", self.HTML_HEADER, self.HTML_FOOTER, self.HTML_SECTION, self.HTML_SECTIONELEMENT, self.HTML_BR)
        html_driven_bones(context, "slider_info_wp", self.WP_HEADER, self.WP_FOOTER, self.WP_SECTION, self.WP_SECTIONELEMENT, self.WP_BR)
        return {'FINISHED'}

def createShapeDrivers(DRIVERS):
    
    logging.info(_("Creating Shape UI"))
    
    sectionitems = []
    for section in SHAPEUI.keys():
        sectionitems.append((section, section, section))
    for section in SHAPE_FILTER.keys():
        sectionitems.append((section, section, section))
        
    sectionitems.reverse()
    ShapeDrivers.Sections = EnumProperty( items=sectionitems, name='Sections', default='Body' )    
    
    ShapeDrivers.DRIVERS = DRIVERS
    
    target = ShapeDrivers
    values = ShapeValues
    
    for pids in SHAPEUI.values():
        for pid in pids:
            P = DRIVERS.get(pid,None)
            if not P:
                continue
            D = P[0]

            if pid=="male_80":

                setattr(target, pid,  
                        BoolProperty(name = D['label'], 

                                    update=eval("lambda a,b:updateShape(a,b,'%s')"%pid),
                                    description = "Gender switch\ndisabled:Female\nenabled:Male",
                                    default = False))
                
            else:

                default = rescale(D['value_default'], D['value_min'], D['value_max'], 0, 100)
                description = "%s - %s"%(D['label_min'], D['label_max'])
                setattr(target, pid,  
                        IntProperty(name = D['label'], 

                                    update=eval("lambda a,b:updateShape(a,b,'%s')"%pid),
                                    description = description,
                                    min      = 0, max      = 100,
                                    soft_min = 0, soft_max = 100,

                                    default = int(round(default))))

                setattr(values, pid,  
                        FloatProperty(name = D['label'], 
                                    min      = 0, max      = 100,
                                    soft_min = 0, soft_max = 100,
                                    default = default))

def createMeshShapes(MESHES):

    MESHSHAPES = {}
    
    for mesh in MESHES.values():
        util.progress_update(10, False)
        meshname = mesh['name']
        MESH = {'name':meshname}

        WEIGHTS = {} 
        if 'skinJoints' in mesh:
            for joint in mesh['skinJoints']:
                WEIGHTS[joint] = {}
            
            for vidx, (bi, w) in enumerate(mesh['weights']):
                if vidx in mesh['vertexRemap']:
                    continue
                i = data.getVertexIndex(mesh, vidx)
                b1, b2 = data.WEIGHTSMAP[meshname][bi]
                WEIGHTS[b1][i] = 1-w
                if b2 is not None:
                    WEIGHTS[b2][i] = w
        MESH['weights'] = WEIGHTS

        SHAPE_KEYS= {}
        for pid, morph in mesh['morphs'].items():
            util.progress_update(1, False)

            DVS = {} 
            for v in morph['vertices']:
                ii = v['vertexIndex']
                if ii in mesh['vertexRemap']:
                    continue
                dv = v['coord']
                DVS[data.getVertexIndex(mesh, ii)] = dv

            BONEGROUPS={}
            dvset = set(DVS)
            for bone, weights in WEIGHTS.items():
                IWDVs = []
                for vid in dvset.intersection(weights):
                    IWDVs.append( (vid, WEIGHTS[bone][vid], DVS[vid]) )
                BONEGROUPS[bone] = IWDVs

            SHAPE_KEYS[pid] = BONEGROUPS
        MESH['shapekeys'] = SHAPE_KEYS

        verts = [mesh['baseCoords'][i] for i in mesh['vertLookup']]
        co = [item for sublist in verts for item in sublist]
        MESH['co'] = co

        MESHSHAPES[meshname]=MESH
    
    ShapeDrivers.MESHSHAPES = MESHSHAPES

def initialize(rigType):
    log.debug("Loading Karaage Shape Interface for rigType %s" % (rigType))
    progress=100
    util.progress_begin()
    log.debug("Loading Karaage DRIVER data rigType %s" % (rigType))
    DRIVERS = data.loadDrivers(rigType=rigType)
    util.progress_update(progress, False)
    log.debug("Create Karaage DRIVERS for rigType %s" % (rigType))
    createShapeDrivers(DRIVERS)
    util.progress_update(progress, False)
    log.debug("Loading Karaage MESH data rigType %s" % (rigType))
    MESHES = data.loadMeshes(rigType=rigType)
    util.progress_update(progress, False)
    log.debug("Loading Karaage MESHES for rigType %s" % (rigType))
    createMeshShapes(MESHES)
    util.progress_end()

def ensure_drivers_initialized(obj):
    if not hasattr(obj.ShapeDrivers, 'DRIVERS'):
        log.debug("%s %s has no Shape Drivers" % (obj.type, obj.name) )
        arm = util.get_armature(obj)
        if arm:
            log.info("Initialise Shape Drivers...")
            rigType = arm.RigProps.RigType
            omode = util.ensure_mode_is("OBJECT")
            initialize(rigType)
            util.ensure_mode_is(omode)

def getShapeValue(obj, pid, normalize=False):

    ensure_drivers_initialized(obj)

    if pid=="male_80":
        value = getattr(obj.ShapeDrivers,pid)
    else:
        if normalize and pid in SHAPE_FILTER[_("Skeleton")] and not pid in DEFORMER_NORMALIZE_EXCEPTIONS:
            value = get_default_value(obj,pid)
        else:
            value   = obj.ShapeValues.get(pid)
            if value is None:
                value = getattr(obj.ShapeDrivers,pid)
    return value

def setShapeValue(obj, pid, default, min, max, prec=False):
    if pid=="male_80":

        obj.ShapeDrivers[pid] = default
    else:
        v = rescale(default, min, max, 0, 100)

        obj.ShapeValues[pid]  = v
        obj.ShapeDrivers[pid] = v if prec else int(round(v))

def printProperties(obj):
    male = obj.ShapeDrivers.male_80
    blockname = _("Shape for: '%s'")%obj.name 
    textblock = bpy.data.texts.new(blockname)
   
    textblock.write(_("Shape sliders for '%s' (%s)\n")%(obj.name, time.ctime()))
    textblock.write(_("Custom values marked with 'M' at begin of line.\n"))
    
    for section, pids in SHAPEUI.items():
        textblock.write("\n=== %s ===\n\n"%section)
        for pid in pids:
            D = obj.ShapeDrivers.DRIVERS[pid][0]
            s = D['sex']
            modified = "M"
            if is_set_to_default(obj,pid):
                modified = " "
                
            if s is None or (s=='male' and male==True) or (s=='female' and male==False):
                textblock.write(_("%c  %s: %d\n")%(modified, D["label"], round(getShapeValue(obj, pid))))                

    logging.info(_("Wrote shape data to textblock '%s'"),blockname)

    return blockname

def fromDictionary(obj, dict, update=True):
    armobj = util.get_armature(obj)
    log.info("|- Paste shape from dictionary to [%s]" % (armobj.name) )

    armobj.ShapeDrivers.Freeze = 1
    pidcount = 0
    for pid, v in dict.items():
        if pid=="male_80":
            v = v > 0
            armobj.ShapeDrivers[pid] = v
        else:
            armobj.ShapeValues[pid]  = v
            armobj.ShapeDrivers[pid] = int(round(v))
        pidcount += 1

    armobj.ShapeDrivers.Freeze = 0
    scene = bpy.context.scene

    if update:

        updateShape(None, bpy.context, scene=bpy.context.scene, refresh=True, msg="fromDictionary")
        util.enforce_armature_update(scene, armobj)
        log.info("|- Updated shape of [%s]" % (armobj.name) )

    log.info("|- Updated %d pids for in [%s]" % (pidcount, armobj.name) )

def asDictionary(obj, full=False):
    armobj = util.get_armature(obj)
    log.info("|- Copy shape from [%s] to dictionary" % (armobj.name) )

    dict = {}
    male = armobj.ShapeDrivers.male_80

    pidcount = 0
    for section, pids in SHAPEUI.items():
        modified = [pid for pid in pids if (pid != 'male_80' and (full or not is_set_to_default(armobj,pid)))]
        for pid in modified:
            D     = armobj.ShapeDrivers.DRIVERS[pid][0]
            sex   = D['sex']
            if True: #sex is None or (sex=='male' and male==True) or (sex=='female' and male==False):
                dict[pid]  = getattr(armobj.ShapeValues,pid)
                pidcount += 1

    log.info("|- Added %d pids to dictionary of [%s]" % (pidcount, armobj.name) )
    return dict

def saveProperties(obj, filepath, normalize=False, pack=False):

    comment = et.Comment("Generated with Karaage on %s"%time.ctime())
    comment.tail = os.linesep
    pool = et.Element('linden_genepool', attrib={'version':'1.0'})  
    pool.tail = os.linesep
    xml = et.ElementTree(pool) 
    archetype = et.Element('archetype', attrib={'name': obj.name})   
    archetype.tail = os.linesep
    pool.append(comment)
    pool.append(archetype)
    
    male = getShapeValue(obj,'male_80')
    for section, pids in SHAPEUI.items():
        for pid in pids:
            D = obj.ShapeDrivers.DRIVERS[pid][0]
            s = D['sex']
            if s is None or (s=='male' and male==True) or (s=='female' and male==False):

                np   = pid.split("_")
                id   = np[-1]
                name = np[:-1]
            
                if id == "80":
                    v = 0.0
                    if male: v += 1.0
                else:
                    value100 = getShapeValue(obj, pid, normalize)
                    v    = rescale(value100, 0, 100, D['value_min'], D['value_max']) 
                
                data = {
                'id':id,
                'name':'_'.join(name),
                'value':"%.3f"%v,
                }
                
                item = et.Element('param', attrib=data)
                item.tail = os.linesep
                archetype.append(item)
                
    if pack:
        blockname = filepath
        if blockname in bpy.data.texts:
            textblock = bpy.data.texts[blockname]
            textblock.clear()
        else:
            textblock = bpy.data.texts.new(blockname)
        root = root=xml.getroot()
        textblock.write(et.tostring(root).decode())
    else:
        xml.write(filepath, xml_declaration=True)
    return filepath

ORESTPOSE_FEMALE={
    "height_33":53,
    "head_size_682":72,
    "shoulders_36":56,
    "arm_length_693":50.6,
    "torso_length_38":51,
    "leg_length_692":51,
    "hip_length_842":49,
    "neck_thickness_683":67,
    "butt_size_795":30
}

NRESTPOSE_FEMALE={
    "height_33":52.05,
    "head_size_682":71.5,
    "neck_thickness_683":67,
    "neck_length_756":51.3,
    "shoulders_36":56.3,
    "breast_gravity_507":44,
    "breast_female_cleavage_684":19,
    "arm_length_693":50.7,
    "torso_length_38":50.5,
    "leg_length_692":51.75,
    "hip_length_842":50,
    "butt_size_795":30,
    "eye_spacing_196":50,
    "thickness_34":32
}

RESTPOSE_FEMALE={
    'hip_length_842' : 50.000000,
    'forehead_angle_629' : 50.000000,

    'lip_width_155' : 40.909091,
    'height_33' : 53.488372,
    'eyelid_inner_corner_up_880' : 52.000000,
    'shoe_heels_197' : 0.000000,
    'thickness_34' : 31.818182,
    'lip_cleft_deep_764' : 45.454545,
    'wide_nose_bridge_27' : 52.000000,
    'big_brow_1' : 13.043478,
    'hip_width_37' : 53.333333,
    'shift_mouth_663' : 50.000000,
    'head_shape_193' : 50.000000,
    'jaw_angle_760' : 37.500000,
    'eye_size_690' : 50.000000,
    'deep_chin_185' : 50.000000,
    'tall_lips_653' : 33.333333,
    'male_package_879' : 20.000000,
    'torso_length_38' : 50.000000,
    'platform_height_503' : 0.000000,
    'weak_chin_7' : 50.000000,
    'bulbous_nose_tip_6' : 40.000000,
    'shoulders_36' : 56.250000,
    'eyebrow_size_119' : 0.000000,
    'broad_nostrils_4' : 33.333333,
    'eye_depth_769' : 50.000000,
    'square_jaw_17' : 33.333333,
    'jaw_jut_665' : 50.000000,
    'squash_stretch_head_647' : 33.333333,
    'double_chin_8' : 25.000000,
    'baggy_eyes_23' : 25.000000,
    'wide_nose_517' : 33.333333,
    'leg_length_692' : 50.000000,

    'eyelid_corner_up_650' : 52.000000,
    'noble_nose_bridge_11' : 25.000000,
    'hand_size_675' : 50.000000,
    'nose_big_out_2' : 24.242424,
    'wide_lip_cleft_25' : 34.782609,
    'lower_bridge_nose_758' : 50.000000,
    'arm_length_693' : 50.000000,
    'pointy_eyebrows_16' : 14.285714,
    'low_septum_nose_759' : 40.000000,
    'wide_eyes_24' : 42.857143,
    'head_size_682' : 71.428571,
    'ears_out_15' : 25.000000,
    'neck_thickness_683' : 66.666667,
    'puffy_upper_cheeks_18' : 37.500000,
    'high_cheek_bones_14' : 33.333333,
    'big_ears_35' : 33.333333,
    'mouth_height_506' : 50.000000,
    'crooked_nose_656' : 50.000000,

    'egg_head_646' : 100-56.521739,
    'bulbous_nose_20' : 25.000000,
    'eyebone_head_shear_661' : 50.000000,
    'pointy_ears_796' : 11.764706,
    'puffy_lower_lids_765' : 10.714286,
    'sunken_cheeks_10' : 33.333333,
    'eyebone_head_elongate_772' : 50.000000,

    'lower_eyebrows_757' : 66.666667,
    'upturned_nose_tip_19' : 60.000000,
    'upper_eyelid_fold_21' : 13.333333,
    'eyebone_big_eyes_689' : 50.000000,
    'eye_spacing_196' : 50.000000,
    'neck_length_756' : 50.000000,
    "butt_size_795":30,
}

def get_restpose_values(armobj):
    return RESTPOSE_FEMALE
    RESTPOSE = {}
    ensure_drivers_initialized(armobj)
    for D in armobj.ShapeDrivers.DRIVERS.values():
        for P in D:
            if P['type'] == 'bones':
                pid = P.get('pid')
                min = P.get('value_min')
                max = P.get('value_max')
                val = P.get('value_default', 0)
                fv = 100 * (val - min) / (max - min)
                RESTPOSE[pid] = fv
    return RESTPOSE

def resetToRestpose(obj, context=None, preserveGender=True, init=False):
    if not context: context = bpy.context
    scene=context.scene
    armobj = util.get_armature(obj)

    ensure_drivers_initialized(armobj)  
    armobj.ShapeDrivers.Freeze = 1
    RESTPOSE = get_restpose_values(armobj)

    for pids in SHAPEUI.values():
        for pid in pids:
            if pid == "male_80" and preserveGender:

                continue

            P = armobj.ShapeDrivers.DRIVERS.get(pid,None)
            if not P:
                continue
            D = P[0]                

            if pid in RESTPOSE:
                v = RESTPOSE[pid]
                armobj.ShapeValues[pid]  = v
                armobj.ShapeDrivers[pid] = int(round(v))

            else:
                setShapeValue(armobj,pid,D['value_default'], D['value_min'], D['value_max'])

    armobj.ShapeDrivers.Freeze = 0
    updateShape(None, context, scene=scene, refresh=True, init=init, msg="updateShape from resetToRestpose")
    util.enforce_armature_update(scene, armobj)
    armobj.RigProps.restpose_mode = True

def resetToDefault(obj, context=None, preserveGender=True, init=False):
    if not context: context = bpy.context
    scene=context.scene
    armobj = util.get_armature(obj)

    armobj.ShapeDrivers.Freeze = 1

    for pids in SHAPEUI.values():
        for pid in pids:
            if pid == "male_80" and preserveGender:

                continue

            P = armobj.ShapeDrivers.DRIVERS.get(pid, None)
            if not P:
                continue
            D = P[0]

            setShapeValue(armobj,pid,D['value_default'], D['value_min'], D['value_max'])
    resetEyes(context, armobj)

    armobj.ShapeDrivers.Freeze = 0
    updateShape(None, context, scene=scene, refresh=True, init=init, msg="updateShape from resetToDefault")
    update_tail_info(context, armobj)
    util.enforce_armature_update(scene, armobj)
    armobj.RigProps.restpose_mode = False

def resetEyes(context, armobj):

    def fix(armobj, eye):
        bones       = armobj.data.edit_bones
        eyeLeft     = bones.get('%sLeft'   % eye)
        eyeRight    = bones.get('%sRight'  % eye)
        eyeTarget   = bones.get('%sTarget' % eye)

        if eyeLeft and eyeRight and eyeTarget:
            loc = 0.5*(eyeLeft.head + eyeRight.head)
            eyeTarget.head = Vector((loc[0], loc[1]-2, loc[2]))
            eyeTarget.tail = Vector((loc[0], loc[1]-2, loc[2]+0.1))

    active = context.active_object
    amode = util.ensure_mode_is("OBJECT")
    context.scene.objects.active = armobj
    omode = util.ensure_mode_is("EDIT") 

    fix(armobj, 'Eye')
    fix(armobj, 'FaceEyeAlt')
    
    util.ensure_mode_is(omode)
    context.scene.objects.active = active
    util.ensure_mode_is(amode)

def update_tail_info(context, armobj, remove=False):
    if context == None:
        context = bpy.context

    omode = util.ensure_mode_is("OBJECT")
    active = context.object

    context.scene.objects.active = armobj

    amode = util.ensure_mode_is("EDIT")
    joints = armobj.get('sl_joints', None )

    for bone in armobj.data.edit_bones:
        key, joint = rig.get_joint_for_bone(joints, bone)
        util.set_head_offset(bone, None)
        util.set_tail_offset(bone, None)
        if remove or joint == None:
            if 'bhead' in bone: del bone['bhead']
            if 'btail' in bone: del bone['btail']
            if 'joint' in bone: del bone['joint'] # to be removed
        else:
            if joint.get('hmag',1) > MIN_JOINT_OFFSET:
                head = Vector(joint.get('head', (0,0,0)))
                util.set_head_offset(bone, head, msg="shape:")
            if joint.get('tmag',1) > MIN_JOINT_OFFSET:
                tail = Vector(joint.get('tail', (0,0,0)))
                util.set_tail_offset(bone, tail, msg="shape:")

    util.ensure_mode_is(amode)
    context.scene.objects.active = active
    util.ensure_mode_is(omode)

def delete_all_shapes(context, armobj):
    shapes = util.getChildren(armobj, type="MESH")
    for child in (child for child in shapes if 'karaage-mesh' in child):
        context.scene.objects.unlink(child)
        bpy.data.objects.remove(child)
    
@persistent
def update_on_framechange(scene):

    active = scene.objects.active
    omode   = active.mode if active else None
    try:

        for armobj in [obj for obj in scene.objects if obj.type=="ARMATURE" and "karaage" in obj]:
            if armobj.animation_data and armobj.animation_data.action:
                if not (hasattr(armobj, 'ShapeDrivers') and hasattr(armobj.ShapeDrivers, 'DRIVERS')):
                    ensure_drivers_initialized(armobj)
                    
                try:
                    recurse_call = True
                    armobj.ShapeDrivers.Freeze = 1

                    update = False
                    
                    animated_pids = [fcurve.data_path.split(".")[1] for fcurve in armobj.animation_data.action.fcurves if fcurve.data_path.split(".")[0]=='ShapeDrivers']
                    
                    for pids in SHAPEUI.values():
                        for pid in pids:
                            if pid in animated_pids:
                                D = armobj.ShapeDrivers.DRIVERS[pid][0]
                                if pid != 'male_80':
                                    v100 = getattr(armobj.ShapeDrivers, pid)
                                    vorg = getattr(armobj.ShapeValues, pid)
                                    if vorg != v100:

                                        setattr(armobj.ShapeValues, pid, float(v100))
                                        update=True
                    if update:

                        scene.objects.active = armobj
                        armobj.ShapeDrivers.Freeze = 0
                        updateShape(None, bpy.context, scene=scene, refresh=True, msg="update_on_framechange")
                except:

                    logging.warn(_("Could not initialise Armature %s (Maybe not an Karaage ?)"), armobj.name)
                    print(traceback.format_exc())
                    raise
                finally:
                    armobj.ShapeDrivers.Freeze = 0
                    recurse_call = False

                pivotUpdate(armobj, scene, 'Left', False)
                pivotUpdate(armobj, scene, 'Right', True)

    except:
        print("Stepped out of update shape due to exception.")
        print(traceback.format_exc())
        pass #raise
    finally:
        scene.objects.active = active
        if active and omode:
            util.ensure_mode_is(omode)
    
def loadProps(obj, filepath, pack=False):
    
    ensure_drivers_initialized(obj)

    obj.ShapeDrivers.Freeze = 1

    if pack:
        blockname = filepath
        if blockname in bpy.data.texts:
            textblock = bpy.data.texts[blockname]
            txt=textblock.as_string()
            xml=et.XML(txt)
        else:
            return
    else:
        xml=et.parse(filepath)

    for item in xml.getiterator('param'):
        nid = "%s"%item.get('id')
        pname = item.get('name') # this tends to be lowercase
        value = float(item.get('value'))

        pid = None
        for driver in obj.ShapeDrivers.DRIVERS.keys():
            if driver.endswith("_"+nid):
                pid = driver
                break

        if pid is None:
            logging.debug(_("ignoring shape key: %s (%s)"),pname, nid)
            continue

        if pid=="male_80":
            value = value > 0

        D = obj.ShapeDrivers.DRIVERS[pid][0]
        setShapeValue(obj,pid,value, D['value_min'], D['value_max'])

    obj.ShapeDrivers.Freeze = 0
    updateShape(None, bpy.context, scene=bpy.context.scene, refresh=True, msg="loadProps")

def get_binding_data(armobj, dbone, use_cache):
    MScale      = util.getBoneScaleMatrix(dbone, normalize=True)
    BoneLoc0, t = rig.get_custom_restposition(armobj, dbone, use_cache, with_floc=False)
    BoneLoc,  t = rig.get_custom_bindposition(armobj, dbone, use_cache, with_floc=True)
    
    return BoneLoc0, BoneLoc, MScale

def update_system_morphs(scene, armobj, meshobjs):

    start = time.time()
    bones = util.get_modify_bones(armobj)    
    log.debug("update_system_morphs: update %d Mesh Objects" % (len(meshobjs)) )
    for mname,  meshobj in meshobjs.items():
        log.debug("update_system_morphs: Propagate morph sliders for system object %s" % meshobj.name)

        if not meshobj.is_visible(scene):

            continue

        MESH = meshobj.ShapeDrivers.MESHSHAPES[mname]

        co = list(MESH['co']) 
        dco = [0.0]*len(co)
        mask = [0]*len(co)

        ttic = time.time()
        mesh_weights = MESH['weights'].items()
        for bname, weights in mesh_weights:
            dbone = bones[bname]
            if dbone.use_deform:
                BoneLoc0, BoneLoc, MScale = get_binding_data(armobj, dbone, use_cache=True)

                for vi,w in weights.items():

                    offset = 3*vi
                    vertLocation   = Vector(co[offset:offset+3])
                    targetLocation = MScale*(vertLocation - BoneLoc0) + BoneLoc
                    L              = w * targetLocation

                    dco[offset]   += L[0]
                    dco[offset+1] += L[1]
                    dco[offset+2] += L[2]

                    mask[offset  ] = 1
                    mask[offset+1] = 1
                    mask[offset+2] = 1
        ttic = util.logtime(ttic, "update_system_morphs: modified %d weighted bones for %s)" % (len(mesh_weights), meshobj.name), 4)
        
        for ii in range(len(dco)):
            if mask[ii]:
                co[ii] = dco[ii]

        meshobj.data.shape_keys.key_blocks[0].data.foreach_set('co',co)

        shapekey_items = MESH['shapekeys'].items()
        for pid, SK in shapekey_items:
            sk_items = SK.items()
            if len(sk_items) == 0:
                continue

            co2 = list(co)
            for bname, IWDVs in sk_items:

                if len(IWDVs) == 0:
                    continue

                scale = util.get_bone_scale(bones[bname])
                for vi,w,dv in IWDVs:
                    co2[3*vi]   += w*dv[0]*scale[0]
                    co2[3*vi+1] += w*dv[1]*scale[1]
                    co2[3*vi+2] += w*dv[2]*scale[2]

            try:
                meshobj.data.shape_keys.key_blocks[pid].data.foreach_set('co',co2)
            except:
                logging.debug("Morph shape_key not found: pid %s" % pid)

        ttic = util.logtime(ttic, "update_system_morphs: modified %d shape keys for %s)" % (len(shapekey_items), meshobj.name), 4)

    util.logtime(start, "update_system_morphs: runtime", 2)

def createSliderShapeKeys(obj):
    get_shape_data(obj, 'original')
    get_shape_data(obj, 'neutral_shape')
    get_shape_data(obj, 'bone_morph')

def destroy_shape_info(context, armobj):
    with util.slider_context() as is_locked:
        objs = util.get_animated_meshes(context, armobj, with_karaage=False, only_selected=False)
        for ob in objs:
            detachShapeSlider(ob, reset=False)
            ob.ObjectProp.slider_selector = 'NONE'
        armobj.ObjectProp.slider_selector = 'NONE'

def detachShapeSlider(obj, reset=True):

    if 'bone_morph' in obj:
        del obj['bone_morph']    
    if 'neutral_shape' in obj:
        del obj['neutral_shape']
    if 'original' in obj:
        if reset:
            try:
                set_shape_data(obj, 'original')
            except:
                log.warning("Could not load original shape into Mesh")
                log.warning("probable cause: The Mesh was edited while sliders where enabled.")
                log.warning("Keep Shape as it is and discard stored original")
        del obj['original']

    if obj.data.shape_keys is not None:
                
        active = bpy.context.scene.objects.active
        bpy.context.scene.objects.active = obj
        original_mode = util.ensure_mode_is("OBJECT")
        
        if 'bone_morph' in obj.data.shape_keys.key_blocks:
            obj.active_shape_key_index = obj.data.shape_keys.key_blocks.keys().index('bone_morph')
            bpy.ops.object.shape_key_remove()
            
        if 'neutral_shape' in obj.data.shape_keys.key_blocks:
            obj.active_shape_key_index = obj.data.shape_keys.key_blocks.keys().index('neutral_shape')
            bpy.ops.object.shape_key_remove()
            
        if len(obj.data.shape_keys.key_blocks) == 1:
            util.ensure_mode_is("EDIT")
            util.ensure_mode_is("OBJECT")
            bpy.ops.object.shape_key_remove(all=True)
            
        util.ensure_mode_is(original_mode)
        bpy.context.scene.objects.active = active

class ShapeSliderDetach(bpy.types.Operator):
    """Copy Current Shape from active Armature into a temporary shape Buffer"""
    bl_idname = "karaage.shape_slider_detach"
    bl_label = "Detach shape Slider of active Object"
    bl_options = {'REGISTER', 'UNDO'}
    
    reset = BoolProperty(name="Reset Shape", default=True, description = "Reset Object to shape when Sliders had been attached" )

    @classmethod
    def poll(self, context):
        ob = context.object
        armobj = util.get_armature(ob)
        return armobj != None

    def execute(self, context):
        if context.object and context.object.type == 'MESH':
            detachShapeSlider(context.object, reset=True)
        return {'FINISHED'}
        
def attachShapeSliders(context, reset=False, init=True, refresh=False):
    arm = None
    obj = context.object
    original_mode = util.ensure_mode_is("OBJECT", object=obj)
    if reset:
        print("temporary detach sliders for %s" % (obj.name) )
        detachShapeSlider(obj, reset=False)
    if obj.ObjectProp.slider_selector!='NONE' or refresh:
        arm=obj.find_armature()
        if arm and "karaage" in arm:
            print("Attach sliders for %s:%s" % (arm.name, obj.name) )
            attachShapeSlider(context, arm, obj, init=init)

    util.ensure_mode_is(original_mode, object=obj)

    if arm:
        shape_filename = arm.name #util.get_shape_filename(name)
        saveProperties(arm, shape_filename, normalize=False, pack=True)

def attachShapeSlider(context, arm, obj, init=True):
    
    active = context.scene.objects.active
    prop   = context.scene.MeshProp

    createSliderShapeKeys(obj)
    ensure_drivers_initialized(arm)

    arm_select = arm.select
    arm.select=True
   
    try:
        updateShape(None, context, scene=context.scene, refresh=True, init=init, object=obj, msg="attachShapeSlider 1", with_bone_check=False)

        if init:
            updateShape(None, context, scene=context.scene, refresh=True, init=False, object=obj, msg="attachShapeSlider 2", with_bone_check=False)
    except:
        log.warning("Could not update Shape in armature:%s for Object:%s" % (arm.name, obj.name) )
        log.warning("Discarding the update")

    context.scene.objects.active=active
    arm.select=arm_select

def has_enabled_sliders(context, armobj):
    objs = util.get_animated_meshes(context, armobj, with_karaage=False)
    for ob in objs:
        if ob.ObjectProp.slider_selector != 'NONE':
            return True
    return False

def enable_shape_keys(context, arm, obj):

    original_mode = obj.mode
    active_group  = obj.vertex_groups.active
    shape_filename = arm.name
    
    if shape_filename in bpy.data.texts:
    
        temp_filename  = "current_shape"
   
        original_mode  = util.ensure_mode_is("OBJECT")
        
        saveProperties(arm, temp_filename, normalize=False, pack=True)
        loadProps(arm, shape_filename, pack=True)
        attachShapeSlider(context, arm, obj, init=True)
        
        loadProps(arm, temp_filename, pack=True)
        text = bpy.data.texts[temp_filename]
        if text:
            util.remove_text(text, do_unlink=True)

        util.ensure_mode_is(original_mode)
        if active_group:
            obj.vertex_groups.active = active_group
        return shape_filename
    else:
        return None

def refresh_shape(arm, obj, graceful=False):
    original_mode = obj.mode
    active_group  = obj.vertex_groups.active
    shape_filename = arm.name

    if shape_filename in bpy.data.texts:
    
        temp_filename  = "current_shape"
   
        original_mode  = util.ensure_mode_is("OBJECT")
        
        #
        #
        update_custom_bones(obj, arm)
        
        #
        #
        #
        #

        util.ensure_mode_is(original_mode)
        if active_group:
            obj.vertex_groups.active = active_group
        return shape_filename
    elif graceful:
        return None
    else:
        raise util.Warning(MSG_UPDATE_SHAPE)

def get_joint_copy(joint):
    head = Vector(joint['head'])
    tail = Vector(joint['tail'])
    roll = joint['roll']
    copy = {'head':head, 'tail':tail, 'roll':roll}
    return copy

def set_bone_positions(context, armobj, toe_distance, ohead):

    bone_hierarchy = rig.bones_in_hierarchical_order(armobj)
    ebones  = armobj.data.edit_bones
    
    for name in util.getMasterBoneNames(bone_hierarchy):

        dbone = ebones.get(name)
        head_local, tail_local = rig.get_custom_bindposition(armobj, dbone, use_cache=True)
        head_local += ohead

        dbone.head = head_local
        if tail_local.magnitude > MIN_BONE_LENGTH:
            dbone.tail = head_local + tail_local
        else:
            dbone.tail = head_local + Vector((0,0.02,0))

        if dbone.use_connect:

            distance = (Vector(dbone.head) - Vector(dbone.parent.head)).magnitude
            if distance > MIN_BONE_LENGTH:
                dbone.parent.tail = dbone.head

    for name in util.getControlledBoneNames(bone_hierarchy):
        mbone = ebones.get(name)
        cbone = ebones.get(name[1:])
        if mbone and cbone:
            cbone.head = mbone.head
            cbone.tail = mbone.tail    

    new_distance = rig.get_toe_location(armobj)
    hover = new_distance[2] - toe_distance[2]
    return hover

def fix_hover(context, armobj, hover, children):
    scene = context.scene

    ocur = scene.cursor_location
    oloc = armobj.matrix_world.translation.copy()
    nloc = oloc.copy()
    nloc[2] += hover

    util.transform_origins_to_location(context, [armobj], nloc)
    util.transform_objects_to_location(context, [armobj], oloc)
    return oloc-nloc

def animated_custom_objects(context, armobj, object):

    if object:
        custom_objects = [object]
    else:
        custom_objects = [ \
            ob for ob in context.visible_objects \
            if ob.type=='MESH' and \
            not 'karaage-mesh' in ob and \
            any([mod for mod in ob.modifiers if mod.type=='ARMATURE' and mod.object==armobj])]

    custom_objects = [o for o in custom_objects if o.ObjectProp.slider_selector != 'NONE']
    return custom_objects

def updateShape(self, context, target="", scene=None, refresh=False, init=False, object=None, msg="Slider", with_bone_check=True):
    if scene is None:
        scene = context.scene

    if not scene.SceneProp.panel_appearance_enabled:
        return

    active = scene.objects.active
    armobj = util.get_armature(active)
    if armobj is None:
        return

    amode = active.mode

    scene.objects.active = armobj
    toe_distance = rig.get_toe_location(armobj).copy()
    log.debug("updateShape called from %s target:[%s]" % (msg, target))

    custom_objects = animated_custom_objects(context, armobj, object)
    inner_updateShape(context, target, scene, refresh, init, custom_objects, with_bone_check, toe_distance)

    scene.objects.active = active
    util.ensure_mode_is(amode)

recurse_call = False
def inner_updateShape(context, target, scene, refresh, init, custom_objects, with_bone_check, toe_distance):
    '''
    Update avatar shape based on driver values.
    Important:
    
    This function relies on correct bone data info to calculate the correct
    bone locations. When used during a rig update, we first have to preset
    correct joint location information.
    
    '''
    tic = time.time()

    active = scene.objects.active
    armobj = util.get_armature(active)

    global recurse_call
    ensure_drivers_initialized(armobj)
    if 'dirty' in armobj:
        log.warning("Calling Jointpos Store from Update Shape for %s" % (armobj.name) )
        bpy.ops.karaage.armature_jointpos_store(sync=False)

    if armobj.ShapeDrivers.Freeze:

        return

    with set_context(context, armobj, 'POSE'):
        oumode = util.set_operate_in_user_mode(False)

        targets = []
        if refresh:

            for section, pids in SHAPEUI.items():
                targets.extend(pids)
        elif not recurse_call:
            targets = [target]

            if target != "":
                armobj.RigProps.restpose_mode = False
            
                try:

                    Ds = armobj.ShapeDrivers.DRIVERS[target]
                    recurse_call=True 
                    for D in Ds:
                        pid = D['pid']
                        if pid != 'male_80':
                            v100 = getattr(armobj.ShapeDrivers, pid)
                            setattr(armobj.ShapeValues, pid, float(v100))
                except:
                    pass
                finally:
                    recurse_call = False

        meshchanges, bonechanges = expandDrivers(armobj, targets)

        if not refresh and len(bonechanges)>0:

            targets = []
            for section, pids in SHAPEUI.items():
                targets.extend(pids)
            meshchanges, bonechanges = expandDrivers(armobj, targets)

        ava_objects = util.getKaraageChildSet(armobj, type='MESH', visible=True)

        log.debug("Updating %d custom objects" % (len(custom_objects)) )

        for D,v,p in meshchanges:
            updateMeshKey(armobj, D, v, p, ava_objects)
            updateCustomMeshKey(armobj, D, v, p, custom_objects)

        if with_bone_check and len(bonechanges)>0:

            for dbone in armobj.data.bones:
                dbone['scale']  = (0.0, 0.0, 0.0)
                dbone['offset'] = (0.0, 0.0, 0.0)

            rig.reset_cache(armobj)
    
            for D,v,p in bonechanges:
                if len(D['bones']) > 0:

                    apply_sliders_to_rig(armobj.data.bones, D, v)

            util.ensure_mode_is("EDIT")
            ttic = time.time()
            
            origin = armobj.data.edit_bones.get("Origin")
            if origin:
                ohead = origin.head.copy()
                otail = origin.tail.copy()
            else:
                ohead = V0.copy()
                otail = ohead + Vector((0,0.02,0))

            hover = set_bone_positions(context, armobj, toe_distance, ohead)
            if abs(hover) > MIN_JOINT_OFFSET:

                children = util.getChildren(armobj)
                delta = fix_hover(context, armobj, hover, children)

                sys_objects = [ch for ch in children if ch not in custom_objects]
                util.transform_origins_to_target(context, armobj, sys_objects, delta, set_origin=True)
                util.transform_origins_to_target(context, armobj, custom_objects, delta, set_origin=False)

                origin = armobj.data.edit_bones.get("Origin")
                if origin:
                    origin.head = ohead
                    origin.tail = otail

            adjustSupportRig(context, armobj)

            util.ensure_mode_is("OBJECT")
            update_system_morphs(scene, armobj, ava_objects)

            bone_hierarchy = rig.bones_in_hierarchical_order(armobj)
            for name in bone_hierarchy:
                dbone = armobj.data.bones.get(name,None)
                if not dbone:
                    log.warning("Bone %s is not in Rig %s" % (name, armobj.name) )
                    continue

                if dbone and 'p_offset' in dbone:
                    del dbone['p_offset']

        for child in [ch for ch in custom_objects if ch.ObjectProp.slider_selector!='NONE']:

            ttic = time.time()
            try:

                if not has_shape_data(child):
                    log.warning("%s has no slider data, ignore" % (child.name) )
                    continue
            except AttributeError:
                log.warning("%s has an attribute error, something going utterly wrong, ignore" % (child.name) )
                continue

            arm = util.getArmature(child)
            if arm is None:
                log.warning("%s has no associated Armature, ignore" % (child.name) )
                continue

            update_custom_bones(child, arm, init)

        setHands(armobj, scene=scene)
        util.set_operate_in_user_mode(oumode)

def get_bones_from_groups(bones, vertex_groups):
    active_bones = []
    for group in vertex_groups:
        if group.name in bones and bones[group.name].use_deform:
            active_bones.append(bones[group.name])
    return active_bones

def sort_bones_by_hierarhy(bones, active_bones):
    processed   = []
    unprocessed = []
    for i, bone in enumerate(active_bones):
        if bone in bones:
            processed.append(bone)
        else:
            unprocessed.append(bone)

    if len(unprocessed) > 0:
        for bone in bones:
            children = bone.children
            if len(children) > 0:
                r = sort_bones_by_hierarhy(bone.children, unprocessed)
                if len(r) > 0:
                    processed.append(r)
    return processed

def has_shape_data(meshobj):
    return meshobj.get('neutral_shape', None) != None and meshobj.get('bone_morph', None) != None

def fast_get_verts(me):
    verts = me.vertices
    co = [0.0]*3*len(verts)
    verts.foreach_get('co',co)
    return co

def fast_set_verts(me, co):
    verts = me.vertices
    verts.foreach_set('co', co)
    
def get_shape_data(child, key):
    updatelog.debug("get_shape_data: load from obj:%s shape:%s" % (child.name, key) )
    skey = str(key)
    dta = child.get(skey,None)

    if not dta:

        if "original" in child:
            dta = child['original'].to_list()

            updatelog.debug("get_shape_data: copied vertex array of length %d from obj:%s shape:original -> shape:%s" % (len(dta), child.name, key))
        else:
            dta = fast_get_verts(child.data)

            updatelog.debug("get_shape_data: initialized vertex array from %d vertices -> obj:%s shape:%s" % (len(dta), child.name, key))

        child[skey] = dta
        return dta, key
    else:
        updatelog.debug("get_shape_data: initialized vertex array from dta of length %d -> obj:%s shape:%s" % (len(dta), child.name, key))

    lvert = 3*len(child.data.vertices)
    ldta  = len(dta)
    dta = dta.to_list() # convert from idproperty to array

    if lvert != ldta:
        if  lvert > ldta:
            lvert = int(lvert/3)
            ldta  = int(ldta/3)
            updatelog.warning("get_shape_data: %s:%s Adding Shape data on the fly for %d missing verts" % (child.name, skey, (lvert-ldta)) )

            verts = child.data.vertices
            for i in range(ldta, lvert):
                co = verts[i].co.copy()
                dta.extend([co[0], co[1], co[2]])
            child[skey] = dta

        else:
            updatelog.warning("get_shape_data: %s:%s shape has %d verts, mesh has %d verts (please reset shape)" % (child.name, skey, ldta, lvert) )
    updatelog.debug("get_shape_data: loaded shape %s:%s with %d verts %d dta" % (child.name, skey, lvert, len(dta)) )
    return dta, key

def set_shape_data(child, key, co=None):
    log.debug("set_shape_data: for obj:%s - key%s" % (child.name, key) )
    if co:
        child[key] = co
    else:
        co = child[key][:]
    try:
        fast_set_verts(child.data, co)
    except:
        log.warning("Could not Set Shape Data for Object %s. Please reset the Shape Info" % (child.name) )

#

#

#

def adjust_vertex_shifting(obj, co, from_data, zero_shape, to_data, tolerance, stepsize, all_verts=True):
    shift_counter = 0
    tolerance = tolerance*obj.dimensions
    for v in obj.data.vertices:
        if all_verts or v.select:
            i=v.index
            ii=3*i
            out_of_limit=0

            for c in range(3):
                sourceco = from_data[ii+c]
                targetco = to_data[ii+c]
                delta = targetco - sourceco
                if abs(delta) > abs(tolerance[c]):
                    co[ii + c]   -= stepsize*delta
                    out_of_limit += 1
                
            if out_of_limit > 0:
                shift_counter +=1
            
    if shift_counter > 0:
        arm = obj.find_armature()

        set_shape_data(obj, zero_shape, co)
        update_custom_bones(obj, arm, adjust_shift=True)
    return shift_counter

def update_custom_bones(child, arm, init=False, adjust_shift=None, all_verts=True):
    util.progress_update(10, absolute=False)

    #

    #

    unweightedvertices = False

    MMeshWorld  = child.matrix_local
    MMeshWorldI = MMeshWorld.inverted()

    if init:
       from_shape = 'original'
       to_shape   = 'neutral_shape'

    else:
       from_shape = 'neutral_shape'
       to_shape   = 'bone_morph'

    bones = util.get_modify_bones(arm)
       
    co, from_shape = get_shape_data(child, from_shape)
    if co == None:
        updatelog.warning("update_custom_bones: Mesh object %s has no mesh shape data (ignore)" % (child.name) )
        return
    if len(co)/3 < len(child.data.vertices):
        updatelog.error("update_custom_bones: shape %s:%s of length %d < vertlen: %d"
                       % (child.name,from_shape, len(co)/3, len(child.data.vertices)) )
    updatelog.debug("update_custom_bones: use shape %s:%s of length %d"
                       % (child.name,from_shape, len(co)/3) )
    dco  = [0.0]*len(co)
    mask = [0]*len(co)

    updatelog.debug("update_custom_bones: collect weight groups...")
    groups = None #precompiled_maps.get(child.name, None)
    if not groups:
        groups = {}
        for i,group in enumerate(child.vertex_groups):
            if group.name in bones and bones[group.name].use_deform:
                groups[i] = (group.name, [])

        for i,v in enumerate(child.data.vertices):
            if all_verts or v.select:
                totw = 0
                vgroups = [] # will contain only valid deforming bone groups 
                for g in v.groups:
                    if g.group in groups:
                        vgroups.append((g.group,g.weight))
                        totw += g.weight

                if totw == 0:

                    unweightedvertices = True
                    continue

                for g,w in vgroups:
                    groups[g][1].append((i, w/totw))

        for key, values in groups.items():
            if len(values) == 0:
                del groups[key]

    else:
        updatelog.warning("update_custom_bones: Loaded precompiled map of child %s" % child.name)
        pass

    for name, weights in groups.values():
        dbone = bones.get(name, None)
        if not dbone or len(weights) == 0:
            continue

        BoneLoc0, BoneLoc, MScale = get_binding_data(arm, dbone, use_cache=True)

        MatRot = Matrix()
        if 'rot0' in dbone:# and dbone.name.startswith(("m","a")):
            rx,ry,rz = dbone['rot0']
            MatRot = Matrix.Rotation(rx,4,'X')*Matrix.Rotation(ry,4,'Y')*Matrix.Rotation(rz,4,'Z')
            MScaleLocal = MatRot * MScale * MatRot.inverted()
        else:

            MScaleLocal = MScale

        M = rig.bind_rotation_matrix(arm, dbone).to_4x4()
        MScaleLocal = M * MScaleLocal * M.inverted()

        if init:

            BoneLoc0, BoneLoc = BoneLoc, BoneLoc0
            MScaleLocal       = MScaleLocal.inverted()

        for vert,weight in weights:

            offset        = 3*vert

            if offset+3 > len(co):
                updatelog.error("update_custom_bones: shape too small: %s:%s has %d entries, but needs %d to solve offset %d" 
                             % (child.name, from_shape, len(co), 3*len(child.data.vertices), offset) )
                continue

            vertLocation  = Vector(co[offset:offset+3])  # in local space
            mv            = MMeshWorld*vertLocation      # in world space
            mv0           = mv-BoneLoc0
            msl           = MScaleLocal*mv0
            mslc          = msl+BoneLoc
            L0            = MMeshWorldI*mslc - vertLocation

            DL = L0 * weight

            dco[offset]   += DL[0]
            dco[offset+1] += DL[1]
            dco[offset+2] += DL[2]

            mask[offset]   = 1
            mask[offset+1] = 1
            mask[offset+2] = 1

    updatelog.debug("update_custom_bones: updated %d Groups" % (len(groups)) )

    for ii in range(len(dco)):
        if mask[ii]:
            co[ii] += dco[ii]

    updatelog.debug("update_custom_bones: Set_shape_data for %s:%s" % (child.name, to_shape) )
    set_shape_data(child, to_shape, co)

    if init:
        update_custom_bones(child, arm, all_verts=all_verts)

        props = bpy.context.scene.MeshProp

        pref=util.getAddonPreferences()
        cd=pref.adaptive_iterations
        if cd > 0:
            tolerance = pref.adaptive_tolerance / 100
            stepsize  = pref.adaptive_stepsize / 100

            from_data, k = get_shape_data(child, from_shape)
            to_data, k   = get_shape_data(child, 'bone_morph')
            shift_counter = adjust_vertex_shifting(child, co, from_data, to_shape, to_data, tolerance, stepsize, all_verts=all_verts)
            cd -= 1
            while shift_counter > 0 and cd > 0:
                util.progress_update(10, absolute=False)
                from_data, k = get_shape_data(child, from_shape)
                to_data, k   = get_shape_data(child, 'bone_morph')
                shift_counter = adjust_vertex_shifting(child, co, from_data, to_shape, to_data, tolerance, stepsize, all_verts=all_verts)
                cd -= 1

            ic = pref.adaptive_iterations - cd
            if ic > 1:
                updatelog.info("Attached %s in %d iterations" % (child.name, ic))
            if shift_counter > 0:
                updatelog.warning("%d verts not precisely placed (placement error > 1mm)" % (shift_counter))

    if unweightedvertices:
        updatelog.warning("Found unweighted vertices in %s" % child.name)
    updatelog.debug("updated %d Groups" % (len(groups)) )

def expandDrivers(armobj, targets):
    
    meshchanges = []
    bonechanges = []
    
    try:
        is_male_shape = armobj.ShapeDrivers.male_80
    except:
        is_male_shape = False

    for target in targets: 

        try:
            Ds = armobj.ShapeDrivers.DRIVERS[target]
        except:
            Ds = []

        for D in Ds:
        
            pid = D['pid']
            
            v100 = getShapeValue(armobj,pid)
            if pid == 'male_80':
                v = v100
            else:
                v = rescale(v100, 0, 100, D['value_min'], D['value_max'])
            
            for_gender = D['sex']
            if (for_gender == 'male' and not is_male_shape) or (for_gender == 'female' and is_male_shape):
                v = 0
            
            if D['type'] == 'mesh':

                meshchanges.append((D, v, v100/100))
                if len(D['bones'])>0:

                    bonechanges.append((D, v, v100/100))
            elif D['type'] == 'bones':

                bonechanges.append((D, v, v100/100))
            elif D['type'] == 'driven':

                expandDrivenKeys(armobj, D, v, meshchanges, bonechanges)
            else:
                logging.error(D)
                raise Exception(_("Unknown shape driver %s")%pid)

    return meshchanges, bonechanges

def restore_spine_fold_state(armobj):
    foldstate = armobj.get('spine_unfold', 'none')
    if foldstate == 'none':
        bpy.ops.karaage.armature_spine_fold()
    if foldstate == 'all':
        bpy.ops.karaage.armature_spine_unfold()
    if foldstate == 'upper':
        bpy.ops.karaage.armature_spine_unfold_upper()
    if foldstate == 'lower':
        bpy.ops.karaage.armature_spine_unfold_lower()
        
def adjustSupportRig(context, armobj):

    rig.adjustAvatarCenter(armobj)
    rig.adjustHipLink(armobj, 'Left')
    rig.adjustHipLink(armobj, 'Right')

    rig.adjustCollarLink(armobj, 'Left')
    rig.adjustCollarLink(armobj, 'Right')

    rig.adjustIKToRig(armobj)

    resetEyes(context, armobj)

    context.scene.objects.active = armobj

    pivotUpdate(armobj, context.scene, 'Left', refresh=False)
    pivotUpdate(armobj, context.scene, 'Right', refresh=False)

def updateCustomMeshKey(arm, D, v, p, meshobjs):
    '''
    Update from driver that controls a mesh morph
    '''
    pid = D['pid']
    try:
        for meshobj in meshobjs:

            if meshobj.data.shape_keys and pid in meshobj.data.shape_keys.key_blocks:
                sk = meshobj.data.shape_keys.key_blocks[pid]
                if abs(v-sk.value) > 0.000001:
                    sk.value = sk.slider_max*p + sk.slider_min*(1-p)
    except KeyError as e:

        pass

def updateMeshKey(obj, D, v, p, meshobjs):
    '''
    Update from driver that controls a mesh morph
    '''
   
    try: 
        meshobj = meshobjs[D['mesh']]
        old = meshobj.data.shape_keys.key_blocks[D['pid']].value
        if abs(v-old) > 0.000001:

            meshobj.data.shape_keys.key_blocks[D['pid']].value = v

    except KeyError as e:

        pass

def apply_sliders_to_rig(bones, D, v):
    '''
    Update from driver that controls bone scale and offset
    '''
    
    if v == 0: 
        return

    for B in D['bones']:
        bname = B['name']
        bone = bones.get(bname, None)
        
        if not bone:
            continue
                        
        DS    = Vector(B['scale'])*v
        S     = Vector(bone['scale'])
        scale = tuple(S+DS)

        DO     = Vector(B['offset'])*v
        O      = Vector(bone['offset'])
        offset = tuple(O+DO)

        scale  = util.sanitize(scale)
        offset = util.sanitize(offset)
        bone['scale']  = scale
        bone['offset'] = offset
        
        if bone.name[0] == 'm':
            bone = bones.get(bname[1:])
            if bone:
                bone['scale']  = scale
                bone['offset'] = offset

def expandDrivenKeys(armobj, D, v, meshchanges, bonechanges):
    '''
    Expand from driver that controls other drivers
    '''

    #

    is_male_shape = armobj.ShapeDrivers.male_80
    
    for DR in D['driven']:
        dpid = DR['pid'] 

        if dpid in [
                    'eyeball_size_679',
                    'eyeball_size_680',
                    'eyeball_size_681',
                    'eyeball_size_687',
                    'eyeball_size_688',
                    'eyeball_size_691',
                    'eyeball_size_694',
                    'eyeball_size_695',
                    ]:

            continue
      
        if dpid == 'muscular_torso_106' and \
            ((is_male_shape and D['pid'] == 'torso_muscles_649') or \
             (not is_male_shape and D['pid'] == 'torso_muscles_678')):

            continue
            
        if v < DR['min1'] or v > DR['min2']:
            vg = 0.0
        elif v >= DR['max1'] and v <= DR['max2']:
            vg = 1.0
        elif v < DR['max1']:

            try:
                vg = (v - DR['min1'])/(DR['max1']-DR['min1'])
            except ZeroDivisionError:
                vg = 1.0
        else:

            try:
                vg = 1.0 - (v - DR['max2'])/(DR['min2']-DR['max2'])
            except ZeroDivisionError:
                vg = 1.0
       
        try:
            D2s = armobj.ShapeDrivers.DRIVERS[dpid]
        except KeyError:
            if dpid not in ["pants_length_shadow_915","pants_length_cloth_615","pants_length_cloth_1018","pants_length_cloth_1036","lower_clothes_shading_913","upper_clothes_shading_899"]:

                logging.warn(_("Missing driver: %s"), dpid)
            continue
        
        counter=0
        for D2 in D2s:
            counter +=1

            v2 = rescale(vg, 0.0, 1.0, D2['value_min'], D2['value_max'] )
           
            is_for_gender = D2['sex']
            
            if (is_for_gender == 'male' and not is_male_shape) or (is_for_gender == 'female' and is_male_shape):
                v2 = 0
                
            if D2['type'] == 'mesh':
                meshchanges.append((D2, v2, vg))
                if len(D2['bones'])>0:
                    bonechanges.append((D2, v2, vg))

            elif D2['type'] == 'bones':

                bonechanges.append((D2, v2, vg))
            else:
                logging.error(D2)
                raise Exception(_("Unknown shape driver %s")%D2['pid'])

def setHands(obj, scene):
    arm = util.get_armature(obj)
    props = arm.RigProps

    if "karaage" in obj or "avastar" in obj:

        meshes = util.findKaraageMeshes(obj)
        if 'upperBodyMesh' in meshes:
            upperbodyMesh = meshes['upperBodyMesh']
            if upperbodyMesh.data.shape_keys:

                for ii in range(1,14):
                    mesh = HANDS[ii]['mesh']

                    if ii == int(props.Hand_Posture):
                        value = 1
                    else:
                        value = 0

                    shape_key = upperbodyMesh.data.shape_keys.key_blocks.get(mesh, None)
                    if shape_key:
                        shape_key.value = value
