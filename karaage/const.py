#
#
#
#
#
#
#
#
#

import os, re, bpy, logging
from .messages import *
from math import *
from . import bl_info
from mathutils import Vector, Matrix
from bpy.props import *

log=logging.getLogger("karaage.const")

MAX_PRIORITY = 6
MIN_PRIORITY = -1
NULL_BONE_PRIORITY = -2

LL_MAX_PELVIS_OFFSET = 5.0

BLtoBVH = Matrix.Rotation(-pi/2, 4, 'X')

AVASTAR_RIG_ID = 5

BENTOBOX        = "https://github.com/nessaki/Karaage"
DOCUMENTATION        = "https://github.com/nessaki/Karaage/wiki"
TICKETS              = BENTOBOX + "/issues"
TOOL_PARAMETER       = "addon=karaage-%s.%s.%s" % bl_info['version']

AVASTAR_COLLADA      = BENTOBOX + "/karaage/help/export_mesh/"
AVASTAR_SKINNING     = BENTOBOX + "/karaage/help/skinning/"
AVASTAR_POSING       = BENTOBOX + "/karaage/help/posing/"
AVASTAR_RIGGING      = BENTOBOX + "/karaage/help/rigging/"
AVASTAR_FITTING      = BENTOBOX + "/karaage/help/fitting/"
AVASTAR_TOOLS        = BENTOBOX + "/karaage/help/karaage-tools/"
AVASTAR_SHAPE        = BENTOBOX + "/karaage/help/karaage_shapes/"
HELP_PAGE            = BENTOBOX + "/karaage/help/"
AVASTAR_URL          = BENTOBOX + "/karaage"
AVASTAR_FORUM        = BENTOBOX + "/forum/stars/karaage-1/"
AVASTAR_REGISTER     = BENTOBOX + "/register-download-page/"
AVASTAR_DOWNLOAD     = BENTOBOX + "/my-account/products/"
XMLRPC_SERVICE       = BENTOBOX + "/xmlrpc.php"
RELEASE_INFO         = BENTOBOX + "/karaage/update/"
LINDEN_BUG_EXPLAINED = BENTOBOX + "/karaage/help/linden-bugs-explained/#shape_keys"

LOCALE_DIR     = os.path.join(os.path.dirname(__file__), 'locale')
TMP_DIR        = os.path.join(os.path.dirname(__file__), 'tmp')
TEMPLATE_DIR   = os.path.join(os.path.dirname(__file__), 'templates')
LIB_DIR        = os.path.join(os.path.dirname(__file__), 'lib')
CONFIG_DIR     = os.path.join(os.path.dirname(__file__), 'config')
ICONS_DIR      = os.path.join(os.path.dirname(__file__), 'icons')

USER_PRESETS   = os.path.join(bpy.utils.user_resource('SCRIPTS'), 'presets/karaage')
RIG_PRESET_DIR = os.path.join(USER_PRESETS, "rigs")
DATAFILESDIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)),'lib')
ASSETS         = os.path.join(DATAFILESDIR,'assets.blend')
SHAPEBOARD     = os.path.join(TMP_DIR,'shapeboard.xml')

COPY_ROTATION    = 'COPY_ROTATION'
COPY_LOCATION    = 'COPY_LOCATION'

INCHES_TO_METERS   = 0.02540005
DEGREES_TO_RADIANS = pi/180.0
RADIAN_TO_DEGREE   = 180/pi

Rz90 = Matrix((
       (0.0, 1.0, 0.0, 0.0),
       (-1.0, 0.0, 0.0, 0.0),
       (0.0, 0.0, 1.0, 0.0),
       (0.0, 0.0, 0.0, 1.0)
       ))
Rz90I = Rz90.inverted()
V0 = Vector((0,0,0))
V1 = Vector((1,1,1))

OB_TRANSLATED = 1
OB_SCALED     = 2
OB_ROTATED    = 4
OB_NEGSCALED  = 8

MIN_BONE_LENGTH          = 0.0001
MIN_JOINT_OFFSET         = 0.0001
MIN_JOINT_OFFSET_RELAXED = 0.001


HOVER_NULL = Vector((0,0,0.005876120179891586))

LArmBones = set(['ShoulderLeft','ElbowLeft','WristLeft','ikWristLeft','ikElbowTargetLeft'])
RArmBones = set(['ShoulderRight','ElbowRight','WristRight','ikWristRight','ikElbowTargetRight'])
LLegBones = set(['HipLeft','KneeLeft','AnkleLeft','ikHeelLeft','ikFootPivotLeft','ikKneeTargetLeft'])
RLegBones = set(['HipRight','KneeRight','AnkleRight','ikHeelRight','ikFootPivotRight','ikKneeTargetRight'])
LHindBones = set(['HindLimb1Left','HindLimb2Left','HindLimb3Left','ikHindHeelLeft','ikHindFootPivotLeft','ikHindLimb2TargetLeft'])
RHindBones = set(['HindLimb1Right','HindLimb2Right','HindLimb3Right','ikHindHeelRight','ikHindFootPivotRight','ikHindLimb2TargetRight'])

def get_limb_from_ikbone(ikbone):
    if ikbone in LArmBones:
        return LArmBones
    if ikbone in RArmBones:
        return RArmBones
    if ikbone in LLegBones:
        return LLegBones
    if ikbone in RLegBones:
        return RLegBones
    if ikbone in LHindBones:
        return LHindBones
    if ikbone in RHindBones:
        return RHindBones
    return None

SLARMBONES = LArmBones.union(RArmBones)
SLLEGBONES = LLegBones.union(RLegBones)
LPinchBones= set(['ikIndexPinchLeft'])
RPinchBones= set(['ikIndexPinchRight'])
LGrabBones = set(['ikThumbTargetLeft', 'ikIndexTargetLeft', 'ikMiddleTargetLeft', 'ikRingTargetLeft', 'ikPinkyTargetLeft'])
RGrabBones = set(['ikThumbTargetRight', 'ikIndexTargetRight', 'ikMiddleTargetRight', 'ikRingTargetRight', 'ikPinkyTargetRight'])
GrabBones  = set(['ikThumbTargetRight', 'ikIndexTargetRight', 'ikMiddleTargetRight', 'ikRingTargetRight', 'ikPinkyTargetRight',
                  'ikThumbTargetLeft', 'ikIndexTargetLeft', 'ikMiddleTargetLeft', 'ikRingTargetLeft', 'ikPinkyTargetLeft'])
SolverBones = set(['ikThumbSolverRight', 'ikIndexSolverRight', 'ikMiddleSolverRight', 'ikRingSolverRight', 'ikPinkySolverRight',
                   'ikThumbSolverLeft', 'ikIndexSolverLeft', 'ikMiddleSolverLeft', 'ikRingSolverLeft', 'ikPinkySolverLeft'])

ALL_IK_BONES = LArmBones.union(RArmBones,LLegBones,RLegBones,LPinchBones,RPinchBones, LGrabBones, RGrabBones, LHindBones, RHindBones)
                   
IK_TARGET_BONES = ["ikElbowTargetLeft", "ikElbowTargetRight", "ikKneeTargetLeft", "ikKneeTargetRight", "ikHindLimb2TargetLeft", "ikHindLimb2TargetRight"]
IK_LINE_BONES   = ["ikElbowLineLeft", "ikElbowLineRight", "ikKneeLineLeft", "ikKneeLineRight", "ikHindLimb2LineLeft", "ikHindLimb2LineRight"]
IK_POLE_BONES   = ["ElbowLeft", "ElbowRight", "KneeLeft", "KneeRight", "HindLimb2Left", "HindLimb2Right"]

BONE_UNSUPPORTED = 'UNSUPPORTED'
BONE_CONTROL     = 'CONTROL'
BONE_SL          = 'SL'
BONE_ATTACHMENT  = 'ATTACHMENT'
BONE_VOLUME      = 'VOLUME'
BONE_META        = 'META'


MTUIBONES = [
         "Skull", "Head", "Neck",
         "CollarLeft", "ShoulderLeft", "ElbowLeft", "WristLeft",
         "CollarRight", "ShoulderRight", "ElbowRight", "WristRight",
         "Chest", "Torso", "COG", "PelvisInv",
         "HipLeft", "KneeLeft", "AnkleLeft", "FootLeft", "ToeLeft",
         "HipRight", "KneeRight", "AnkleRight", "FootRight", "ToeRight",
    ]

MTUIBONES_EXTENDED = [
         "Skull", "Head", "Neck",

         'FaceRoot',
         'EyeRight', 'EyeLeft', 'FaceEyeAltRight', 'FaceEyeAltLeft',
         'FaceForeheadCenter',
         'FaceForeheadLeft',  'FaceEyebrowOuterLeft',  'FaceEyebrowCenterLeft',  'FaceEyebrowInnerLeft',
         'FaceForeheadRight', 'FaceEyebrowOuterRight', 'FaceEyebrowCenterRight', 'FaceEyebrowInnerRight',

         'FaceEyeLidUpperLeft', 'FaceEyeLidLowerLeft',
         'FaceEyeLidUpperRight', 'FaceEyeLidLowerRight',
         'FaceEar1Left', 'FaceEar2Left', 'FaceEar1Right', 'FaceEar2Right',
         'FaceNoseBase', 'FaceNoseLeft', 'FaceNoseCenter', 'FaceNoseRight',
         'FaceCheekLowerLeft', 'FaceCheekUpperLeft', 'FaceCheekLowerRight', 'FaceCheekUpperRight',

         'FaceJaw',
         'FaceChin',

         'FaceTeethLower',
         'FaceLipLowerLeft', 'FaceLipLowerRight', 'FaceLipLowerCenter',
         'FaceTongueBase', 'FaceTongueTip', 'FaceJawShaper',

         'FaceTeethUpper',
         'FaceLipUpperLeft', 'FaceLipUpperRight', 'FaceLipCornerLeft', 'FaceLipCornerRight', 'FaceLipUpperCenter',
         'FaceEyecornerInnerLeft', 'FaceEyecornerInnerRight', 'FaceNoseBridge',

         'CollarLinkLeft', 'CollarLeft', 'ShoulderLeft', 'ElbowLeft', 'WristLeft',
         'HandMiddle1Left', 'HandMiddle2Left', 'HandMiddle3Left',
         'HandIndex1Left', 'HandIndex2Left', 'HandIndex3Left',
         'HandRing1Left', 'HandRing2Left', 'HandRing3Left',
         'HandPinky1Left', 'HandPinky2Left', 'HandPinky3Left',
         'HandThumb1Left', 'HandThumb2Left', 'HandThumb3Left',

         'CollarLinkRight', 'CollarRight', 'ShoulderRight', 'ElbowRight', 'WristRight',
         'HandMiddle1Right', 'HandMiddle2Right', 'HandMiddle3Right',
         'HandIndex1Right', 'HandIndex2Right', 'HandIndex3Right',
         'HandRing1Right', 'HandRing2Right', 'HandRing3Right',
         'HandPinky1Right', 'HandPinky2Right', 'HandPinky3Right',
         'HandThumb1Right', 'HandThumb2Right', 'HandThumb3Right',

         'WingsRoot',
         'Wing1Left', 'Wing2Left', 'Wing3Left', 'Wing4Left', 'Wing4FanLeft',
         'Wing1Right', 'Wing2Right', 'Wing3Right', 'Wing4Right', 'Wing4FanRight',

         'Chest','Spine4', 'Spine3', 'Torso', 'Spine2', 'Spine1', 'COG', 'PelvisInv',

         'HipLinkLeft', 'HipLeft', 'KneeLeft', 'AnkleLeft', 'FootLeft', 'ToeLeft',
         'HipLinkRight', 'HipRight', 'KneeRight', 'AnkleRight', 'FootRight', 'ToeRight',

         'Tail1', 'Tail2', 'Tail3', 'Tail4', 'Tail5', 'Tail6',
         'Groin',

         'HindLimbsRoot',
         'HindLimb1Left', 'HindLimb2Left', 'HindLimb3Left', 'HindLimb4Left',
         'HindLimb1Right', 'HindLimb2Right', 'HindLimb3Right', 'HindLimb4Right'
]

MTUI_SEPARATORS = ['FaceRoot', 'FaceForeheadCenter', 'FaceEyeLidUpperLeft', 'FaceJaw', 'FaceTeethLower',
    'Chest', 'CollarLinkLeft', 'CollarLinkRight',
    'WingsRoot', 'Tail1',
    'HipLinkLeft', 'HipLinkRight', 'HindLimbsRoot'
    ]


MTBONES = [
         "COG",'PelvisInv',
         "Torso", "Chest", "Neck", "Head", "Skull",
         "CollarLinkLeft", "CollarLeft", "ShoulderLeft", "ElbowLeft", "WristLeft",
         "CollarLinkRight", "CollarRight", "ShoulderRight", "ElbowRight", "WristRight",

         "HipLinkLeft",  "HipLeft",  "KneeLeft",  "AnkleLeft",  "FootLeft",  "ToeLeft",
         "HipLinkRight", "HipRight", "KneeRight", "AnkleRight", "FootRight", "ToeRight",
    ]
MTBONES_EXTENDED = [
        "COG",'PelvisInv', 'Spine1', 'Spine2', 'Torso', 'Spine3', 'Spine4',
        'Chest', 'Neck', 'Head', 'Skull',
        'EyeRight', 'EyeLeft',
        'FaceRoot',
        'FaceEyeAltRight', 'FaceEyeAltLeft',
        'FaceForeheadLeft', 'FaceForeheadRight',
        'FaceEyebrowOuterLeft', 'FaceEyebrowCenterLeft', 'FaceEyebrowInnerLeft',
        'FaceEyebrowOuterRight', 'FaceEyebrowCenterRight', 'FaceEyebrowInnerRight',
        'FaceEyeLidUpperLeft', 'FaceEyeLidLowerLeft', 'FaceEyeLidUpperRight', 'FaceEyeLidLowerRight',
        'FaceEar1Left', 'FaceEar2Left', 'FaceEar1Right', 'FaceEar2Right',
        'FaceNoseLeft', 'FaceNoseCenter', 'FaceNoseRight', 'FaceCheekLowerLeft', 'FaceCheekUpperLeft', 'FaceCheekLowerRight', 'FaceCheekUpperRight',
        'FaceJaw', 'FaceChin', 'FaceTeethLower',
        'FaceLipLowerLeft', 'FaceLipLowerRight', 'FaceLipLowerCenter',
        'FaceTongueBase', 'FaceTongueTip', 'FaceJawShaper',
        'FaceForeheadCenter', 'FaceNoseBase',
        'FaceTeethUpper', 'FaceLipUpperLeft', 'FaceLipUpperRight', 'FaceLipCornerLeft', 'FaceLipCornerRight', 'FaceLipUpperCenter',
        'FaceEyecornerInnerLeft', 'FaceEyecornerInnerRight', 'FaceNoseBridge',

        'CollarLinkLeft', 'CollarLeft', 'ShoulderLeft', 'ElbowLeft', 'WristLeft',
        'HandMiddle1Left', 'HandMiddle2Left', 'HandMiddle3Left',
        'HandIndex1Left', 'HandIndex2Left', 'HandIndex3Left',
        'HandRing1Left', 'HandRing2Left', 'HandRing3Left',
        'HandPinky1Left', 'HandPinky2Left', 'HandPinky3Left',
        'HandThumb1Left', 'HandThumb2Left', 'HandThumb3Left',

        'CollarLinkRight', 'CollarRight', 'ShoulderRight', 'ElbowRight', 'WristRight',
        'HandMiddle1Right', 'HandMiddle2Right', 'HandMiddle3Right',
        'HandIndex1Right', 'HandIndex2Right', 'HandIndex3Right',
        'HandRing1Right', 'HandRing2Right', 'HandRing3Right',
        'HandPinky1Right', 'HandPinky2Right', 'HandPinky3Right',
        'HandThumb1Right', 'HandThumb2Right', 'HandThumb3Right',

        'WingsRoot',
        'Wing1Left', 'Wing2Left', 'Wing3Left', 'Wing4Left', 'Wing4FanLeft',
        'Wing1Right', 'Wing2Right', 'Wing3Right', 'Wing4Right', 'Wing4FanRight',

        'HipLinkLeft', 'HipLeft', 'KneeLeft', 'AnkleLeft', 'FootLeft', 'ToeLeft',
        'HipLinkRight', 'HipRight', 'KneeRight', 'AnkleRight', 'FootRight', 'ToeRight',

        'Tail1', 'Tail2', 'Tail3', 'Tail4', 'Tail5', 'Tail6', 'Groin',

        'HindLimbsRoot', 
        'HindLimb1Left', 'HindLimb2Left', 'HindLimb3Left', 'HindLimb4Left',
        'HindLimb1Right', 'HindLimb2Right', 'HindLimb3Right', 'HindLimb4Right'
    ]


MCMBONES = [
        "Hips", "Hips",
        "LowerBack", "Spine", "Spine1", "Neck1", "Head",
        "", "LeftShoulder",  "LeftArm",  "LeftForeArm",  "LeftHand",
        "", "RightShoulder", "RightArm", "RightForeArm", "RightHand",

        "", "LeftUpLeg",  "LeftLeg",  "LeftFoot",  "LeftToeBase",  "",
        "", "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase", "",
    ]
MCMBONES_EXTENDED = [
        'Hips', 'Hips', 'Spine1', 'Spine2', 'LowerBack', 'Spine', 'Spine1',
        'Chest', 'Neck1', 'Head', 'Skull',
        'EyeRight', 'EyeLeft',
        'FaceRoot',
        'FaceEyeAltRight', 'FaceEyeAltLeft',
        'FaceForeheadLeft', 'FaceForeheadRight',
        'FaceEyebrowOuterLeft', 'FaceEyebrowCenterLeft', 'FaceEyebrowInnerLeft',
        'FaceEyebrowOuterRight', 'FaceEyebrowCenterRight', 'FaceEyebrowInnerRight',
        'FaceEyeLidUpperLeft', 'FaceEyeLidLowerLeft', 'FaceEyeLidUpperRight', 'FaceEyeLidLowerRight',
        'FaceEar1Left', 'FaceEar2Left', 'FaceEar1Right', 'FaceEar2Right',
        'FaceNoseLeft', 'FaceNoseCenter', 'FaceNoseRight', 'FaceCheekLowerLeft', 'FaceCheekUpperLeft', 'FaceCheekLowerRight', 'FaceCheekUpperRight',
        'FaceJaw', 'FaceChin', 'FaceTeethLower',
        'FaceLipLowerLeft', 'FaceLipLowerRight', 'FaceLipLowerCenter',
        'FaceTongueBase', 'FaceTongueTip', 'FaceJawShaper',
        'FaceForeheadCenter', 'FaceNoseBase',
        'FaceTeethUpper', 'FaceLipUpperLeft', 'FaceLipUpperRight', 'FaceLipCornerLeft', 'FaceLipCornerRight', 'FaceLipUpperCenter',
        'FaceEyecornerInnerLeft', 'FaceEyecornerInnerRight', 'FaceNoseBridge',

        '', 'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand',
        'HandMiddle1Left', 'HandMiddle2Left', 'HandMiddle3Left',
        'HandIndex1Left', 'HandIndex2Left', 'HandIndex3Left',
        'HandRing1Left', 'HandRing2Left', 'HandRing3Left',
        'HandPinky1Left', 'HandPinky2Left', 'HandPinky3Left',
        'HandThumb1Left', 'HandThumb2Left', 'HandThumb3Left',

        '', 'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand',
        'HandMiddle1Right', 'HandMiddle2Right', 'HandMiddle3Right',
        'HandIndex1Right', 'HandIndex2Right', 'HandIndex3Right',
        'HandRing1Right', 'HandRing2Right', 'HandRing3Right',
        'HandPinky1Right', 'HandPinky2Right', 'HandPinky3Right',
        'HandThumb1Right', 'HandThumb2Right', 'HandThumb3Right',

        'WingsRoot',
        'Wing1Left', 'Wing2Left', 'Wing3Left', 'Wing4Left', 'Wing4FanLeft',
        'Wing1Right', 'Wing2Right', 'Wing3Right', 'Wing4Right', 'Wing4FanRight',

        '', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase', '',
        '', 'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase', '',

        'Tail1', 'Tail2', 'Tail3', 'Tail4', 'Tail5', 'Tail6', 'Groin',

        'HindLimbsRoot', 'HindLimb1Left', 'HindLimb2Left', 'HindLimb3Left', 'HindLimb4Left',
        'HindLimb1Right', 'HindLimb2Right', 'HindLimb3Right', 'HindLimb4Right'
    ]



MSLBONES = [
        "hip", "hip",
        "abdomen", "chest", "neck", "head", "figureHair",
        '', "lCollar", "lShldr", "lForeArm", "lHand",
        '', "rCollar", "rShldr", "rForeArm", "rHand",
        
        '', "lThigh", "lShin", "lFoot", "", "",
        '', "rThigh", "rShin", "rFoot", "", "",
    ]

MSLBONES_EXTENDED = [
        'hip', 'hip', 'Spine1', 'Spine2', 'abdomen', 'Spine3', 'Spine4',
        'chest', 'neck', 'head', 'figureHair',
        'EyeRight', 'EyeLeft',

        'mFaceRoot',
        'mFaceEyeAltRight', 'mFaceEyeAltLeft',
        'mFaceForeheadLeft', 'mFaceForeheadRight',
        'mFaceEyebrowOuterLeft', 'mFaceEyebrowCenterLeft', 'mFaceEyebrowInnerLeft',
        'mFaceEyebrowOuterRight', 'mFaceEyebrowCenterRight', 'mFaceEyebrowInnerRight',
        'mFaceEyeLidUpperLeft', 'mFaceEyeLidLowerLeft', 'mFaceEyeLidUpperRight', 'mFaceEyeLidLowerRight',
        'mFaceEar1Left', 'mFaceEar2Left', 'mFaceEar1Right', 'mFaceEar2Right',
        'mFaceNoseLeft', 'mFaceNoseCenter', 'mFaceNoseRight', 'mFaceCheekLowerLeft', 'mFaceCheekUpperLeft', 'mFaceCheekLowerRight', 'mFaceCheekUpperRight',
        'mFaceJaw', 'mFaceChin', 'mFaceTeethLower',
        'mFaceLipLowerLeft', 'mFaceLipLowerRight', 'mFaceLipLowerCenter',
        'mFaceTongueBase', 'mFaceTongueTip', 'mFaceJawShaper',
        'mFaceForeheadCenter', 'mFaceNoseBase',
        'mFaceTeethUpper', 'mFaceLipUpperLeft', 'mFaceLipUpperRight', 'mFaceLipCornerLeft', 'mFaceLipCornerRight', 'mFaceLipUpperCenter',
        'mFaceEyecornerInnerLeft', 'mFaceEyecornerInnerRight', 'mFaceNoseBridge',

        '', 'lCollar', 'lShldr', 'lForeArm', 'lHand',
        'mHandMiddle1Left', 'mHandMiddle2Left', 'mHandMiddle3Left',
        'mHandIndex1Left', 'mHandIndex2Left', 'mHandIndex3Left',
        'mHandRing1Left', 'mHandRing2Left', 'mHandRing3Left',
        'mHandPinky1Left', 'mHandPinky2Left', 'mHandPinky3Left',
        'mHandThumb1Left', 'mHandThumb2Left', 'mHandThumb3Left',

        '', 'rCollar', 'rShldr', 'rForeArm', 'rHand',
        'mHandMiddle1Right', 'mHandMiddle2Right', 'mHandMiddle3Right',
        'mHandIndex1Right', 'mHandIndex2Right', 'mHandIndex3Right',
        'mHandRing1Right', 'mHandRing2Right', 'mHandRing3Right',
        'mHandPinky1Right', 'mHandPinky2Right', 'mHandPinky3Right',
        'mHandThumb1Right', 'mHandThumb2Right', 'mHandThumb3Right',

        'mWingsRoot',
        'mWing1Left',  'mWing2Left',  'mWing3Left',  'mWing4Left',  'mWing4FanLeft',
        'mWing1Right', 'mWing2Right', 'mWing3Right', 'mWing4Right', 'mWing4FanRight',

        '', 'lThigh', 'lShin', 'lFoot', '', '',
        '', 'rThigh', 'rShin', 'rFoot', '', '',

        'mTail1', 'mTail2', 'mTail3', 'mTail4', 'mTail5', 'mTail6', 'mGroin',

        'mHindLimbsRoot',  'mHindLimb1Left',  'mHindLimb2Left',  'mHindLimb3Left', 'mHindLimb4Left',
        'mHindLimb1Right', 'mHindLimb2Right', 'mHindLimb3Right', 'mHindLimb4Right'
    ]



ANIMBONE_MAP = {
         "COG"            : "hip",
         "Torso"          : "abdomen",
         "Chest"          : "chest",
         "Neck"           : "neck",
         "Head"           : "head",
         "Skull"          : "figureHair",
         "CollarLeft"     : "lCollar",
         "ShoulderLeft"   : "lShldr",
         "ElbowLeft"      : "lForeArm",
         "WristLeft"      : "lHand",
         "CollarRight"    : "rCollar",
         "ShoulderRight"  : "rShldr",
         "ElbowRight"     : "rForeArm",
         "WristRight"     : "rHand",
         "PelvisInv"      : "hip",
         "Pelvis"         : "hip",
         "HipLeft"        : "lThigh",
         "KneeLeft"       : "lShin",
         "AnkleLeft"      : "lFoot",
         "FootLeft"       : None,
         "ToeLeft"        : None,
         "HipRight"       : "rThigh",
         "KneeRight"      : "rShin",
         "AnkleRight"     : "rFoot",
         "FootRight"      : None,
         "ToeRight"       : None
    }



BONE_TAIL_LOCATIONS = {

    "Origin"       : (-0.20,    0.0,  0.0     ),
    "COG"          : (-0.15368, 0.0,  0.0     ),

    }



DEFAULT_BONE_LIMITS= {

    "COG"            :[(0.95,0.95,0.95),  None,       None,      None,      None],
    "PelvisInv"      :[(0.85,0.85,0.85), (-90,40),   (-60,60),  (-40,40),   None],
    "Torso"          :[(0.85,0.85,0.85), (-40,80),   (-60,60),  (-40,40),   None],
    "Pelvis"         :[None,              None,       None,      None,      None],
    "Chest"          :[(0.8,0.8,0.8),    (-40,50),   (-60,60),  (-40,40),   None],
    "Neck"           :[(0.75,0.75,0.75), (-50,40),   (-60,60),  (-40,40),   None],
    "Head"           :[(0.8,0.8,0.8),    (-70,40),   (-80,80),  (-40,40),   None],
    "Skull"          :[(0.8,0.8,0.8),     None,       None,      None,      None],
    "CollarLinkLeft" :[None,              None,       None,      None,      -45],
    "CollarLinkRight":[None,              None,       None,      None,      45],
    "CollarLeft"     :[(0.9,0.9,0.9),    (-80,80),   (-80,80),  (-80,80),   None],
    "CollarRight"    :[(0.9,0.9,0.9),    (-80,80),   (-80,80),  (-80,80),   None],
    "ShoulderLeft"   :[(0.3,0.3,0.3),    (-120,30),  (-90,90),  (-100,30),  None],
    "ShoulderRight"  :[(0.3,0.3,0.3),    (-120,30),  (-90,90),  (-30,100),  None],
    "ElbowLeft"      :[(0.2, 0.2, 0.2),  (-45,45),   (-10,10),  (-160,15) , None],
    "ElbowRight"     :[(0.2, 0.2, 0.2),  (-45,45),   (-10,10),  (-15,160) , None],
    "WristLeft"      :[(0.5, 0.5, 0.5),  (-100,100), (-45,45),  (-30,40) ,  None],
    "WristRight"     :[(0.5, 0.5, 0.5),  (-100,100), (-45,45),  (-40,30) ,  None],
    "HipLinkLeft"    :[None,              None,       None,      None,      -45],
    "HipLinkRight"   :[None,              None,       None,      None,      45],
    "HipLeft"        :[(0.5,0.5,0.5),    (-160,40),  (-60,40),  (-100,30),  5],
    "HipRight"       :[(0.5,0.5,0.5),    (-160,40),  (-40,60),  (-30,100), -5],
    "KneeLeft"       :[(0.6,0.6,0.6),    (-10,160),  (-40,40),  (0,0),      None],
    "KneeRight"      :[(0.6,0.6,0.6),    (-10,160),  (-40,40),  (0,0),      None],
    "AnkleLeft"      :[(0.75,0.75,0.75), (-50,70),   (-50,20),  (-20,20),   None],
    "AnkleRight"     :[(0.75,0.75,0.75), (-50,70),   (-20,50),  (-20,20),   None],
    "FootLeft"       :[(0.8,0.8,0.8),     None,       None,      None,      -14.3],
    "FootRight"      :[(0.8,0.8,0.8),     None,       None,      None,      None],

    "HindLimb1Left"  :[(0.5,0.5,0.5),    (-160,40),  (-60,40),  (-100,30),  5],
    "HindLimb1Right" :[(0.5,0.5,0.5),    (-160,40),  (-40,60),  (-30,100), -5],
    "HindLimb2Left"  :[(0.6,0.6,0.6),    (-10,160),  (-40,40),  (0,0),      None],
    "HindLimb2Right" :[(0.6,0.6,0.6),    (-10,160),  (-40,40),  (0,0),      None],
    "HindLimb3Left"  :[(0.75,0.75,0.75), (-50,70),   (-50,20),  (-20,20),   None],
    "HindLimb3Right" :[(0.75,0.75,0.75), (-50,70),   (-20,50),  (-20,20),   None],
    "HindLimb4Left"  :[(0.8,0.8,0.8),     None,       None,      None,      -14.3],
    "HindLimb4Right" :[(0.8,0.8,0.8),     None,       None,      None,      14.3],

    "ToeLeft"        :[(0.8,0.8,0.8),     None,       None,      None,      None],
    "ToeRight"       :[(0.8,0.8,0.8),     None,       None,      None,      None],
    "EyeLeft"        :[None,              None,       None,      None,      None],
    "EyeRight"       :[None,              None,       None,      None,      None],
    }


NONDEFORMS = ['mFaceEyeAltLeft', 'mFaceEyeAltRight', 'mEyeLeft', 'mEyeRight', 'mFaceTongueBase', 'mFaceTongueTip', 'mFaceTeethUpper', 'mFaceTeethLower']
EXTRABONES = ["mHead", 'mEyeLeft', 'mEyeRight']
B_LAYER_COUNT       = 32

B_LAYER_ORIGIN          = 0
B_LAYER_TORSO           = 1
B_LAYER_ARMS            = 2
B_LAYER_LEGS            = 3
B_LAYER_EYE_TARGET      = 4
B_LAYER_EYE_ALT_TARGET  = 5
B_LAYER_ATTACHMENT      = 6
B_LAYER_VOLUME          = 7

B_LAYER_FACE            =  8
B_LAYER_HAND            =  9
B_LAYER_WING            = 10
B_LAYER_TAIL            = 11
B_LAYER_GROIN           = 12
B_LAYER_SPINE           = 13
B_LAYER_LIMB            = 14
B_LAYER_EXTRA           = 15

B_LAYER_SL              = 16
B_LAYER_IK_ARMS         = 17
B_LAYER_IK_LEGS         = 18
B_LAYER_IK_LIMBS        = 19
B_LAYER_IK_FACE         = 20
B_LAYER_IK_HAND         = 21
B_LAYER_IK_HIDDEN       = 21
B_LAYER_STRUCTURE       = 22
B_LAYER_EXTENDED        = 23

B_LAYER_DEFORM_FACE     = 24
B_LAYER_DEFORM_HAND     = 25
B_LAYER_DEFORM_WING     = 26
B_LAYER_DEFORM_TAIL     = 27
B_LAYER_DEFORM_GROIN    = 28
B_LAYER_DEFORM_SPINE    = 29
B_LAYER_DEFORM_LIMB     = 30
B_LAYER_DEFORM          = 31

B_DEFAULT_POSE_LAYERS = [ \
B_LAYER_ORIGIN,
B_LAYER_TORSO,
B_LAYER_ARMS,
B_LAYER_LEGS,
B_LAYER_HAND,
B_LAYER_FACE,
]

B_SIMPLE_POSE_LAYERS = [ \
B_LAYER_ORIGIN,
B_LAYER_TORSO,
B_LAYER_ARMS,
B_LAYER_LEGS,
B_LAYER_EYE_TARGET,
B_LAYER_EYE_ALT_TARGET,
B_LAYER_FACE,
B_LAYER_HAND,
B_LAYER_WING,
B_LAYER_TAIL,
B_LAYER_GROIN,
B_LAYER_SPINE,
B_LAYER_LIMB,
B_LAYER_EXTRA,
]

B_STANDARD_POSE_LAYERS = [ \
B_LAYER_ORIGIN,
B_LAYER_TORSO,
B_LAYER_ARMS,
B_LAYER_LEGS,
B_LAYER_EYE_TARGET,
B_LAYER_EYE_ALT_TARGET,
B_LAYER_ATTACHMENT,
B_LAYER_VOLUME,
B_LAYER_FACE,
B_LAYER_HAND,
B_LAYER_WING,
B_LAYER_TAIL,
B_LAYER_GROIN,
B_LAYER_SPINE,
B_LAYER_LIMB,
B_LAYER_EXTRA,
]

B_SIMPLE_DEFORM_LAYERS = [ \
B_LAYER_DEFORM_FACE,
B_LAYER_DEFORM_HAND,
B_LAYER_DEFORM_WING,
B_LAYER_DEFORM_TAIL,
B_LAYER_DEFORM_GROIN,
B_LAYER_DEFORM_SPINE,
B_LAYER_DEFORM_LIMB,
B_LAYER_DEFORM,
B_LAYER_ORIGIN,
B_LAYER_EYE_TARGET,
B_LAYER_EYE_ALT_TARGET,
]

B_STANDARD_DEFORM_LAYERS = [ \
B_LAYER_DEFORM_FACE,
B_LAYER_DEFORM_HAND,
B_LAYER_DEFORM_WING,
B_LAYER_DEFORM_TAIL,
B_LAYER_DEFORM_GROIN,
B_LAYER_DEFORM_SPINE,
B_LAYER_DEFORM_LIMB,
B_LAYER_DEFORM,
B_LAYER_ORIGIN,
B_LAYER_EYE_TARGET,
B_LAYER_EYE_ALT_TARGET,
B_LAYER_VOLUME,
]

DEFORM_TO_POSE_MAP = {
B_LAYER_ARMS: [B_LAYER_SL,B_LAYER_DEFORM],
B_LAYER_LEGS: [B_LAYER_SL,B_LAYER_DEFORM],
B_LAYER_TORSO: [B_LAYER_SL,B_LAYER_DEFORM],
B_LAYER_FACE: [B_LAYER_DEFORM_FACE,B_LAYER_DEFORM],
B_LAYER_HAND: [B_LAYER_DEFORM_HAND,B_LAYER_DEFORM],
B_LAYER_WING: [B_LAYER_DEFORM_WING,B_LAYER_DEFORM],
B_LAYER_TAIL: [B_LAYER_DEFORM_TAIL,B_LAYER_DEFORM],
B_LAYER_GROIN: [B_LAYER_DEFORM_GROIN,B_LAYER_DEFORM],
B_LAYER_SPINE: [B_LAYER_DEFORM_SPINE,B_LAYER_DEFORM],
B_LAYER_LIMB: [B_LAYER_DEFORM_LIMB,B_LAYER_DEFORM],
B_LAYER_VOLUME: [B_LAYER_VOLUME],
B_LAYER_DEFORM: [B_LAYER_DEFORM]
}

LAYER_MAP = {
    'Origin':     [B_LAYER_ORIGIN],
    'Torso':      [B_LAYER_TORSO],
    'Collision':  [B_LAYER_VOLUME],
    'Extra':      [B_LAYER_EXTRA],
    'Arms':       [B_LAYER_ARMS],
    'Legs':       [B_LAYER_LEGS],
    'IK Arms':    [B_LAYER_IK_ARMS],
    'IK Legs':    [B_LAYER_IK_LEGS],
    'IK Limbs':   [B_LAYER_IK_LIMBS],
    'Structure':  [B_LAYER_STRUCTURE],
    'SL Base':    [B_LAYER_SL],
    'SL Extended':[B_LAYER_EXTENDED],
    'Eye Target': [B_LAYER_EYE_TARGET],
    'Eye Alt Target': [B_LAYER_EYE_ALT_TARGET],
    'Attachment': [B_LAYER_ATTACHMENT],

    'Face':    [B_LAYER_FACE,   B_LAYER_DEFORM_FACE],
    'Lip':     [B_LAYER_FACE,   B_LAYER_DEFORM_FACE],
    'Lips':    [B_LAYER_FACE,   B_LAYER_DEFORM_FACE],
    'Eye':     [B_LAYER_FACE,   B_LAYER_DEFORM_FACE],
    'Eyes':    [B_LAYER_FACE,   B_LAYER_DEFORM_FACE],
    'Mouth':   [B_LAYER_FACE,   B_LAYER_DEFORM_FACE],
    'Nose':    [B_LAYER_FACE,   B_LAYER_DEFORM_FACE],
    'Ear':     [B_LAYER_FACE,   B_LAYER_DEFORM_FACE],
    'Ears':    [B_LAYER_FACE,   B_LAYER_DEFORM_FACE],

    'Hand':    [B_LAYER_HAND,   B_LAYER_DEFORM_HAND],
    'IK Hands':[B_LAYER_IK_HAND],
    'IK Face': [B_LAYER_IK_FACE],
    'Wing':    [B_LAYER_WING,   B_LAYER_DEFORM_WING],
    'Groin':   [B_LAYER_GROIN,  B_LAYER_DEFORM_GROIN],
    'Tail':    [B_LAYER_TAIL,   B_LAYER_DEFORM_TAIL],
    'Limb':    [B_LAYER_LIMB,   B_LAYER_DEFORM_LIMB],
    'Spine':   [B_LAYER_SPINE,  B_LAYER_DEFORM_SPINE],
}


BONEGROUP_MAP = {

    'Origin'         : ['THEME12', [B_LAYER_ORIGIN]         ],
    'SL Base'        : ['THEME04', [B_LAYER_SL]             ], # blues
    'SL Extended'    : ['THEME06', [B_LAYER_EXTENDED]       ], # purples
    'Structure'      : ['THEME12', [B_LAYER_STRUCTURE]      ],
    'Custom'         : ['THEME12', [B_LAYER_EXTENDED]       ],
    'Eye Target'     : ['THEME12', [B_LAYER_EYE_TARGET]     ],
    'Eye Alt Target' : ['THEME12', [B_LAYER_EYE_ALT_TARGET] ],
    'IK Arms'        : ['THEME09', [B_LAYER_IK_ARMS]        ], # yellows
    'IK Legs'        : ['THEME09', [B_LAYER_IK_LEGS]        ], # yellows
    'IK Limbs'       : ['THEME09', [B_LAYER_IK_LIMBS]       ], # yellows
    'IK Face'        : ['THEME11', [B_LAYER_IK_FACE]        ], # IK bones are pink
    
    'Attachment'     : ['THEME01', [B_LAYER_ATTACHMENT]     ], # reds
    'Collision'      : ['THEME02', [B_LAYER_VOLUME]         ], # oranges

    'Torso'          : ['THEME12', [B_LAYER_TORSO]          ],
    'Arms'           : ['THEME12', [B_LAYER_ARMS]           ],
    'Legs'           : ['THEME12', [B_LAYER_LEGS]           ],
    'Extra'          : ['THEME12', [B_LAYER_EXTRA]          ],
    'Face'        : ['THEME12', [B_LAYER_FACE]           ], #extended bones are light green
    'Hand'        : ['THEME12', [B_LAYER_HAND]           ],
    'Wing'        : ['THEME12', [B_LAYER_WING]           ],
    'Tail'        : ['THEME12', [B_LAYER_TAIL]           ],
    'Groin'       : ['THEME12', [B_LAYER_GROIN]          ],
    'Eye'         : ['THEME12', [B_LAYER_FACE]           ],
    'Eyes'        : ['THEME12', [B_LAYER_FACE]           ], #compatibility thing
    'Ear'         : ['THEME12', [B_LAYER_FACE]           ],
    'Ears'        : ['THEME12', [B_LAYER_FACE]           ], #compatibility thing
    'Lip'         : ['THEME12', [B_LAYER_FACE]           ],
    'Lips'        : ['THEME12', [B_LAYER_FACE]           ], #compatibility thing
    'Mouth'       : ['THEME12', [B_LAYER_FACE]           ],
    'Nose'        : ['THEME12', [B_LAYER_FACE]           ],
    'Limb'        : ['THEME12', [B_LAYER_LIMB]           ],
    'Spine'       : ['THEME12', [B_LAYER_SPINE]          ],

    'mTorso'         : ['THEME04', [B_LAYER_SL,           B_LAYER_DEFORM] ],
    'mArms'          : ['THEME04', [B_LAYER_SL,           B_LAYER_DEFORM] ],
    'mLegs'          : ['THEME04', [B_LAYER_SL,           B_LAYER_DEFORM] ],
    'mExtra'         : ['THEME04', [B_LAYER_SL,           B_LAYER_DEFORM] ],

    'mFace'       : ['THEME06', [B_LAYER_DEFORM_FACE,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ], #extended bones are purple
    'mHand'       : ['THEME06', [B_LAYER_DEFORM_HAND,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mWing'       : ['THEME06', [B_LAYER_DEFORM_WING,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mTail'       : ['THEME06', [B_LAYER_DEFORM_TAIL,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mGroin'      : ['THEME06', [B_LAYER_DEFORM_GROIN, B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mEye'        : ['THEME06', [B_LAYER_DEFORM_FACE,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mEar'        : ['THEME06', [B_LAYER_DEFORM_FACE,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mLip'        : ['THEME06', [B_LAYER_DEFORM_FACE,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mEyes'       : ['THEME06', [B_LAYER_DEFORM_FACE,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mEars'       : ['THEME06', [B_LAYER_DEFORM_FACE,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mLips'       : ['THEME06', [B_LAYER_DEFORM_FACE,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mMouth'      : ['THEME06', [B_LAYER_DEFORM_FACE,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mNose'       : ['THEME06', [B_LAYER_DEFORM_FACE,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mLimb'       : ['THEME06', [B_LAYER_DEFORM_LIMB,  B_LAYER_EXTENDED, B_LAYER_DEFORM] ],
    'mSpine'      : ['THEME06', [B_LAYER_DEFORM_SPINE, B_LAYER_EXTENDED, B_LAYER_DEFORM] ]
}

def sym(inlist):
    '''
    Return a list expanding  Left and Right for . suffix
    '''
    out = []

    for name in inlist:        
        if "." in name:
            out.append(name.replace(".", "Left"))
            out.append(name.replace(".", "Right"))
        else:
            out.append(name)
    
    return out
    
def sym_expand(bone_names, inlist):
    '''
    Return a list expanding  Left and Right for . suffix
    '''
    work = sym(inlist)
    out  = []

    for name in work:
        if name[0]=='*':
            out.extend([bn for bn in bone_names if name[1:] in bn])
        elif name[-1]=='*':
            out.extend([bn for bn in bone_names if name[0:-1] in bn])
        else:
            split = name.split("*")
            if len(split) > 1:
                out.extend([bn for bn in bone_names if all( [split[i] in bn for i in range(0,1)])])
            else:
                out.append(name)

    return out



SL_LEAF_BONES = sym(["mSkull", "mToe."])

SLVOLBONES  = ["PELVIS", "BELLY", "CHEST", "NECK", "HEAD", "L_CLAVICLE", "L_UPPER_ARM",
               "L_LOWER_ARM", "L_HAND", "R_CLAVICLE", "R_UPPER_ARM", "R_LOWER_ARM", "R_HAND",
               "R_UPPER_LEG", "R_LOWER_LEG", "R_FOOT", "L_UPPER_LEG", "L_LOWER_LEG", "L_FOOT"]

SLOPTBONES    = []


GENERATE_SKELETON_DATA = os.path.join(DATAFILESDIR, "avatar_skeleton_1.xml")

SLBONES = sym(["mHead", "mNeck" ,"mCollar.", "mShoulder.", "mElbow.",
               "mWrist.", "mChest", "mTorso", "mPelvis", "mHip.",
               "mKnee.", "mAnkle.", "mFoot."])

SL_EYE_BONES  = sym(["mEye."])
SL_ALT_EYE_BONES = sym(["mFaceEyeAlt."])
SL_ALL_EYE_BONES = SL_EYE_BONES + SL_ALT_EYE_BONES 

SLATTACHMENTS = ["aSkull", "aChin", "aRight Ear", "aLeft Ear", "aRight Eyeball",
               "aLeft Eyeball", "aNose", "aMouth", "aNeck", "aRight Shoulder",
               "aLeft Shoulder", "aR Upper Arm", "aL Upper Arm", "aR Forearm",
               "aL Forearm", "aRight Hand", "aLeft Hand", "aRight Pec", "aLeft Pec",
               "aChest", "aSpine", "aStomach", "aAvatar Center", "aRight Hip",
               "aLeft Hip", "aPelvis", "aR Upper Leg", "aL Upper Leg",
               "aR Lower Leg", "aL Lower Leg", "aRight Foot", "aLeft Foot",
               "aLeft Ring Finger", "aRight Ring Finger",
               "aTail Base", "aTail Tip",
               "aLeft Wing", "aRight Wing",
               "aAlt Left Ear", "aAlt Right Ear",
               "aAlt Left Eye", "aAlt Right Eye",
               "aJaw", "aTongue", "aGroin"
               ]

SLSHAPEVOLBONES = ["UPPER_BACK", "LOWER_BACK", "LEFT_PEC", "RIGHT_PEC", "LEFT_HANDLE", "RIGHT_HANDLE", "BUTT"]

SLOPTBONES.extend(SL_LEAF_BONES+SL_EYE_BONES)
SLVOLBONES.extend(SLSHAPEVOLBONES)
SLBASEBONES   = SLOPTBONES+SLBONES
SLALLBONES    = SLBASEBONES+SLATTACHMENTS+SLVOLBONES
REGULAR_BONES = ['Origin', 'PelvisInv','COG', '_EyeTarget', '_CollarLinkRight', '_CollarLinkLeft']
HOVER_POINTS  = ['COG', 'Pelvis', 'mPelvis']

SLMAP = 'SL'
MANUELMAP = 'MANUELLAB'
GENERICMAP = 'GENERIC'
AVASTARMAP = 'AVASTAR'

MANUEL2Karaage = {
"upperarm_L" : "ShoulderLeft",
"upperarm_R" : "ShoulderRight",
"lowerarm_L" : "ElbowLeft",
"lowerarm_R" : "ElbowRight",
"hand_L"     : "WristLeft",
"hand_R"     : "WristRight",
"thumb01_L"  : "HandThumb1Left",
"thumb02_L"  : "HandThumb2Left",
"thumb03_L"  : "HandThumb3Left",
"thumb01_R"  : "HandThumb1Right",
"thumb02_R"  : "HandThumb2Right",
"thumb03_R"  : "HandThumb3Right",
"index01_L"  : "HandIndex1Left",
"index02_L"  : "HandIndex2Left",
"index03_L"  : "HandIndex3Left",
"index01_R"  : "HandIndex1Right",
"index02_R"  : "HandIndex2Right",
"index03_R"  : "HandIndex3Right",
"middle01_L" : "HandMiddle1Left",
"middle02_L" : "HandMiddle2Left",
"middle03_L" : "HandMiddle3Left",
"middle01_R" : "HandMiddle1Right",
"middle02_R" : "HandMiddle2Right",
"middle03_R" : "HandMiddle3Right",
"ring01_L"   : "HandRing1Left",
"ring02_L"   : "HandRing2Left",
"ring03_L"   : "HandRing3Left",
"ring01_R"   : "HandRing1Right",
"ring02_R"   : "HandRing2Right",
"ring03_R"   : "HandRing3Right",
"pinky01_L"  : "HandPinky1Left",
"pinky02_L"  : "HandPinky2Left",
"pinky03_L"  : "HandPinky3Left",
"pinky01_R"  : "HandPinky1Right",
"pinky02_R"  : "HandPinky2Right",
"pinky03_R"  : "HandPinky3Right",
"clavicle_L" : "CollarLeft",
"clavicle_R" : "CollarRight",
"neck"       : "Neck",
"spine02"    : "Torso",
"spine03"    : "Chest",
"head"       : "Head",
"thigh_L"    : "HipLeft",
"thigh_R"    : "HipRight",
"calf_L"     : "KneeLeft",
"calf_R"     : "KneeRight",
"pelvis"     : "Pelvis",
"foot_L"     : "AnkleLeft",
"foot_R"     : "AnkleRight",
"toes_L"     : "FootLeft",
"toes_R"     : "FootRight",
"chest"      : "Chest",
"breast_R"   : "RIGHT_PEC",
"breast_L"   : "LEFT_PEC",
}

MANUEL_UNSUPPORTED = {
"spine01"    : "Pelvis",
"root"       : "Origin",
"index00_L"  : "WristLeft",
"index00_R"  : "WristRight",
"middle00_L" : "WristLeft",
"middle00_R" : "WristRight",
"ring00_L"   : "WristLeft",
"ring00_R"   : "WristRight",
"pinky00_L"  : "WristLeft",
"pinky00_R"  : "WristRight",
}

def map_sl_to_Karaage(SourceBonename, type=SLMAP, all=True):
    if type == MANUELMAP:
        result = MANUEL2Karaage.get(SourceBonename, MANUEL_UNSUPPORTED.get(SourceBonename, None) if all else None)
        return result

    result = SourceBonename[1:] if SourceBonename[0]=='m' else SourceBonename

    return result

def map2SL(armobj, SourceBonename):
    if SourceBonename[0]!='m' and 'm'+SourceBonename in armobj.data.bones:
        SourceBonename = 'm' + SourceBonename
    return SourceBonename

MANUEL_CUSTOM_SHAPE_SCALES = {
    "Head"           : 0.5,
    "Neck"           : 0.5,
    "CollarLeft"     : 0.5,
    "CollarRight"    : 0.5,
    "WristLeft"      : 2.0,
    "WristRight"     : 2.0,
    "Chest"          : 0.8,
    "Torso"          : 0.7,
    "PelvisInv"      : 0.8,
    "KneeLeft"       : 0.8,
    "KneeRight"      : 0.8,
    "AnkleLeft"      : 0.7,
    "AnkleRight"     : 0.7,
    "ikWristRight"   : 2.0,
    "ikWristLeft"    : 2.0,
    "ikFaceLipShape" : 0.4
}

def adjust_custom_shape(pbone, armature_type):

    if armature_type == MANUELMAP:
        scale = MANUEL_CUSTOM_SHAPE_SCALES.get(pbone.name, 1.0)
        try:
            pbone.custom_shape_scale = scale
        except:
            print("Can not fix Custom Shape scale (not supported in this Version of Blender")

BONEMAP_EXTENDED_TO_BASIC = {
    'mFace.*'       : 'mHead',
    'mTail.*'       : 'mPelvis',
    'mHand.*Left'   : 'mWristLeft',
    'mHand.*Right'  : 'mWristRight',
    'mEyeAlt.*Left' : 'mEyeLeft',
    'mEyeAlt.*Right': 'mEyeRight',
    'mWing.*'       : 'mTorso'
}

def get_export_bonename(groups, group, target_system):
    bonename = groups[group].name
    if target_system != 'BASIC' or bonename in SLALLBONES:
        return bonename

    for key in BONEMAP_EXTENDED_TO_BASIC:
        if re.search(key, bonename):
            mappedname = BONEMAP_EXTENDED_TO_BASIC[key]

            bonename = mappedname
            break

    return bonename if bonename in SLALLBONES else None
    

MAX_EXPORT_BONES = 110

UI_SIMPLE   = 0
UI_STANDARD = 1
UI_ADVANCED = 2
UI_EXPERIMENTAL = 3




custom_icons = None
def register_icons():
    global custom_icons
    custom_icons = bpy.utils.previews.new()
    custom_icons.load("eye", os.path.join(ICONS_DIR, "eye.png"), 'IMAGE')
    custom_icons.load("eyec", os.path.join(ICONS_DIR, "eyec.png"), 'IMAGE')
    custom_icons.load("ceyec", os.path.join(ICONS_DIR, "ceyec.png"), 'IMAGE')
    custom_icons.load("ceye", os.path.join(ICONS_DIR, "ceye.png"), 'IMAGE')
    custom_icons.load("ieyec", os.path.join(ICONS_DIR, "ieyec.png"), 'IMAGE')
    custom_icons.load("ieye", os.path.join(ICONS_DIR, "ieye.png"), 'IMAGE')
    custom_icons.load("cbone", os.path.join(ICONS_DIR, "cbone.png"), 'IMAGE')
    custom_icons.load("meyec", os.path.join(ICONS_DIR, "meyec.png"), 'IMAGE')
    custom_icons.load("meye", os.path.join(ICONS_DIR, "meye.png"), 'IMAGE')
    custom_icons.load("mbone", os.path.join(ICONS_DIR, "mbone.png"), 'IMAGE')
    custom_icons.load("cbones", os.path.join(ICONS_DIR, "cbones.png"), 'IMAGE')
    custom_icons.load("mbones", os.path.join(ICONS_DIR, "mbones.png"), 'IMAGE')
    custom_icons.load("ebones", os.path.join(ICONS_DIR, "ebones.png"), 'IMAGE')
    custom_icons.load("alock", os.path.join(ICONS_DIR, "alock.png"), 'IMAGE')
    custom_icons.load("elock", os.path.join(ICONS_DIR, "elock.png"), 'IMAGE')
    custom_icons.load("mlock", os.path.join(ICONS_DIR, "mlock.png"), 'IMAGE')
    custom_icons.load("aunlock", os.path.join(ICONS_DIR, "aunlock.png"), 'IMAGE')
    custom_icons.load("eunlock", os.path.join(ICONS_DIR, "eunlock.png"), 'IMAGE')
    custom_icons.load("munlock", os.path.join(ICONS_DIR, "munlock.png"), 'IMAGE')
    custom_icons.load("retarget", os.path.join(ICONS_DIR, "retarget.png"), 'IMAGE')
    log.warning("Custom icons initialized")

def unregister_icons():
    global custom_icons
    bpy.utils.previews.remove(custom_icons)

def get_sys_icon(key):
    return bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items[key].value

def get_cust_icon(key):
    return custom_icons[key].icon_id

def visIcon(armobj, layer, type=None):
    if not armobj.data.layers[layer]:
        return bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items['RESTRICT_VIEW_ON'].value
    if type == 'animation':
        return custom_icons["ceye"].icon_id
    elif type == 'deform':
        return custom_icons["meye"].icon_id
    elif type == 'ik':
        return custom_icons["ieye"].icon_id
    else:
        return bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items['RESTRICT_VIEW_OFF'].value




sl_bone_rolls = BoolProperty(
    name="Enforce SL Bone Roll",
    description = "Ensure that the bone Rolls are defined according to the SL Skeleton Specification\n\nNote:\nThis can be good for cleaning up (human) devkits.\nUsage with non human skeletons may cause damage!",
    default     = False
)

