#
#
#
#
#
#
#
#

import bpy, os, logging
import  xml.etree.ElementTree as et
from struct import unpack
from math import radians
from mathutils import Euler, Vector
from . import util, const
from .util import Bone, Skeleton, V,  sym, s2b, s2bo
from .const import *

log = logging.getLogger('karaage.data')

WEIGHTSMAP = {
    'hairMesh':[('mNeck','mHead'), ('mHead', None)],
    'headMesh':[('mNeck','mHead'), ('mHead', None)],
    'eyelashMesh':[('mHead',  None)],
    'upperBodyMesh':[('mPelvis','mTorso' ), ('mTorso', 'mChest'), ('mChest', 'mNeck'), ('mNeck', None),
                    ('mChest','mCollarLeft' ), ('mCollarLeft', 'mShoulderLeft'), ('mShoulderLeft', 'mElbowLeft'), ('mElbowLeft','mWristLeft' ), 
                    ('mWristLeft',None), ('mChest','mCollarRight' ), ('mCollarRight', 'mShoulderRight'), ('mShoulderRight', 'mElbowRight'),
                    ('mElbowRight','mWristRight' ), ('mWristRight', None)],
    'lowerBodyMesh':[('mPelvis','mHipRight'), ('mHipRight', 'mKneeRight'), ('mKneeRight', 'mAnkleRight'), ('mAnkleRight',  None),
                    ('mPelvis', 'mHipLeft'), ('mHipLeft', 'mKneeLeft'), ('mKneeLeft','mAnkleLeft'), ('mAnkleLeft', None)],
     'skirtMesh':[('mTorso', 'mPelvis'),('mPelvis',None ),('mPelvis','mHipRight' ),('mHipRight','mKneeRight' ),
                ('mKneeRight', None),('mPelvis', 'mHipLeft'),('mHipLeft','mKneeLeft' ),('mKneeLeft',None)],

     'eyeBallLeftMesh':[('mEyeLeft', None)],
     'eyeBallRightMesh':[('mEyeRight', None)],
}

def get_armature_rigtype(armobj):
    RigType = armobj.RigProps.RigType
    if not RigType:
        RigType = armobj.AnimProps.RigType
    if not RigType:
        RigType='BASIC'
    return RigType

def get_mtui_bones(armobj=None):
    RigType = 'EXTENDED' if armobj == None else get_armature_rigtype(armobj)
    return MTUIBONES_EXTENDED if RigType == 'EXTENDED' else MTUIBONES

def get_mt_bones(armobj=None):
    RigType = 'EXTENDED' if armobj == None else get_armature_rigtype(armobj)
    return MTBONES_EXTENDED if RigType == 'EXTENDED' else MTBONES

def get_mcm_bones(armobj=None):
    RigType = 'EXTENDED' if armobj == None else get_armature_rigtype(armobj)
    return MCMBONES_EXTENDED if RigType == 'EXTENDED' else MCMBONES

def get_msl_bones(armobj=None):
    RigType = 'EXTENDED' if armobj == None else get_armature_rigtype(armobj)
    return MSLBONES_EXTENDED if RigType == 'EXTENDED' else MSLBONES

def get_volume_bones(obj=None, only_deforming=False):
    armobj = util.get_armature(obj) if obj else None
    if armobj and only_deforming:
        bones = util.get_modify_bones(armobj)
        bone_set = [bone.name for bone in bones if bone.name in SLVOLBONES and bone.use_deform]
    else:
        bone_set = SLVOLBONES
    return bone_set
    
def get_base_bones(obj=None, only_deforming=False):
    armobj = util.get_armature(obj) if obj else None
    if armobj and only_deforming:
        bones = util.get_modify_bones(armobj)
        bone_set = [bone.name for bone in bones if bone.name in SLBASEBONES and bone.use_deform]
    else:
        bone_set = SLBASEBONES
    return bone_set
    
def get_extended_bones(obj, only_deforming=False):
    armobj = util.get_armature(obj)
    bones = util.get_modify_bones(armobj)    
    if only_deforming:
        bone_set = [bone.name for bone in bones if bone.name[0]=='m' and bone.name not in SLBASEBONES and bone.use_deform]
    else:
        bone_set = [bone.name for bone in bones if bone.name[0]=='m' and bone.name not in SLBASEBONES]
    return bone_set

def get_deform_bones(obj, exclude_volumes=False, exclude_eyes=False):
    armobj = util.get_armature(obj)
    volumes = get_volume_bones(obj=armobj) if exclude_volumes else []
    bones = util.get_modify_bones(armobj)
    bone_set = [bone.name for bone in bones if bone.use_deform  
                and not (exclude_volumes and bone.name in volumes)
                and not(exclude_eyes and bone.name in SL_ALL_EYE_BONES)]

    return bone_set
    
def getVertexIndex(mesh, vertex):
    if vertex in mesh['vertexRemap']:
        vi = mesh['vertexRemap'][vertex]
    else:
        vi = vertex
    return(mesh['vertLookup'].index(vi))

def loadLLM(name, filename):
    '''
    load and parse binary mesh file (llm)
    '''

    stream = open( filename, 'rb' )
    llm = {}
    llm['header'] = stream.read(24).decode('utf-8').split( "\x00" )[0]
    hasWeights = unpack( "B", stream.read(1) )[0]
    hasDetailTexCoords = unpack( "B", stream.read(1) )[0]
    llm['position'] = unpack( "<3f", stream.read(12) )
    llm['rotationAngles'] = unpack( "<3f", stream.read(12) )
    llm['rotationOrder'] = unpack( "B", stream.read(1) )[0]
    llm['scale'] = unpack( "<3f", stream.read(12) )
    numVertices = unpack( "<H", stream.read(2) )[0]

    EYE_SCALE = 1

    scale = (1,1,1)

    if name == "eyeBallLeftMesh":
        shift = (0.0729999989271164+0.0006, 0.035999998450279236, 1.7619999647140503-0.0003)
        scale = (EYE_SCALE, EYE_SCALE, EYE_SCALE)

    elif name == "eyeBallRightMesh":
        shift = (0.0729999989271164+0.0006, -0.035999998450279236, 1.7619999647140503-0.0003)
        scale = (EYE_SCALE, EYE_SCALE, EYE_SCALE)

    else:
        shift = (0,0,0)    
    
    llm['baseCoords'] = []
    for i in range(numVertices):
        co = unpack("<3f", stream.read(12)) 
        llm['baseCoords'].append(s2b((co[0]*scale[0]+shift[0], co[1]*scale[1]+shift[1], co[2]*scale[2]+shift[2])))
        
    llm['baseNormals'] = []
    for i in range(numVertices):
        llm['baseNormals'].append( s2b(unpack( "<3f", stream.read(12) )))
        
    llm['baseBinormals'] = []
    for i in range(numVertices):
        llm['baseBinormals'].append( s2b(unpack( "<3f", stream.read(12) )))
    
    llm['texCoords'] = []
    for i in range(numVertices):
        llm['texCoords'].append( unpack( "<2f", stream.read(8) ))
    
    if hasDetailTexCoords:
        llm['detailTexCoords'] = []
        for i in range(numVertices):
            llm['detailTexCoords'].append( unpack( "<2f", stream.read(8) ))
    
    #

    #

    #
    if hasWeights:
        llm['weights'] = []
        for i in range(numVertices):
            raw = unpack( "<f", stream.read(4) )[0]
            idx = int(raw)-1
            iweight = raw-int(raw)
            llm['weights'].append( (idx, iweight) )
            
    if name == "eyeBallLeftMesh" or name == "eyeBallRightMesh":
        llm['weights'] = [(0,0.0)]*numVertices

    numFaces = unpack( "<H", stream.read(2) )[0]
    llm['faces'] = []
    for i in range(numFaces):
        llm['faces'].append( unpack( "<3H", stream.read(6) ))
    
    if hasWeights:
        numSkinJoints = unpack( "<H", stream.read(2) )[0]
        llm['skinJoints'] = []
        for i in range(numSkinJoints):
            llm['skinJoints'].append(stream.read(64).decode('utf-8').split("\x00")[0])
        
    if name == "eyeBallLeftMesh":
        llm['skinJoints'] = ['mEyeLeft']
    elif name == "eyeBallRightMesh":
        llm['skinJoints'] = ['mEyeRight']

    llm['morphsbyname'] = {}
    n = stream.read(64).decode('utf-8').split("\x00")[0]
    while n != "End Morphs":
        morph = {'name':n}
        numMorphVertices = unpack( "<L", stream.read(4) )[0]
        morph['vertices'] = []
        for i in range(numMorphVertices):
            v = {}
            v['vertexIndex'] = unpack( "<L", stream.read(4) )[0] # 0-indexed
            v['coord'] = s2b(unpack( "<3f", stream.read(12) ))
            v['normal'] = s2b(unpack( "<3f", stream.read(12) ))
            v['binormal'] = s2b(unpack( "<3f", stream.read(12) ))
            v['texCoord'] = unpack( "<2f", stream.read(8) )
            morph['vertices'].append( v )
        llm['morphsbyname'][n] = morph
        n = stream.read(64).decode('utf-8').split("\x00")[0]
        
    numRemaps = unpack( "<l", stream.read(4) )[0]
    llm['vertexRemap'] = {}
    for i in range(numRemaps):
        remap = unpack( "<2l", stream.read(8) )
        llm['vertexRemap'][ remap[0] ] = remap[1]
    stream.close()

    llm['vertLookup'] = [i for i in range(len(llm['baseCoords'])) \
        if i  not in llm['vertexRemap']]

    return llm

def cleanId(nid, name):

    #

    #

    clean_name = name.lower().replace(" ","_")
    pid = "_%s"%nid

    return clean_name+pid

def loadDrivers(rigType=None, max_param_id=-1):
    '''
    Read in shape drivers from avatar_lad.xml
    '''

    #

    #

    ladxml = et.parse(util.get_lad_file(rigType, "Load Drivers"))

    DRIVERS = {}
    
    #

    #
    meshes = ladxml.findall('mesh')
    for mesh in meshes:
        lod = int(mesh.get('lod'))
        if lod != 0:

            continue

        mname = mesh.get('type')

        params = mesh.findall('param')       
        for p in params:
            pname = p.get('name')
            id  = int(p.get('id'))
            pid = cleanId(id, pname)
            
            paramd = {'pid': pid,
                      'name': pname,
                      'type': 'mesh',
                      'label': p.get('label', pname),
                      'label_min': p.get('label_min'),
                      'label_max': p.get('label_max'),
                      'value_default': float(p.get('value_default', "0")),
                      'value_min': float(p.get('value_min')),
                      'value_max': float(p.get('value_max')),
                      'sex': p.get('sex', None),
                      'edit_group': p.get('edit_group', None),
                      'mesh': mname,
                      } 
           
            vbones = []

            param_morphs = p.findall('param_morph')
            for param_morph in param_morphs:
                volume_morphs = param_morph.findall('volume_morph')
                for vol in volume_morphs:
                
                    scale = vol.get('scale','0.0 0.0 0.0').split()
                    pos   = vol.get('pos','0.0 0.0 0.0').split()
                    vname = vol.get('name')
                    
                    if all(v == 0 for v in scale):
                        log.warning("Volume Morph %s has no scale" % (vol.get('name')))
                    
                    vbone = {
                        'name':vname,
                        'scale':s2bo([float(s) for s in scale]),
                        'offset':s2b([float(p) for p in pos]),
                    }
                    vbones.append(vbone)

            if 'bones' in paramd:
                raise Exception("parameter 'bones' already defined in %s"%pname)
            
            paramd['bones'] = vbones
        
            if max_param_id == -1 or id < max_param_id:
                if pid in DRIVERS:
                    DRIVERS[pid].append(paramd)
                else:
                    DRIVERS[pid] = [paramd]

    #

    #
    params = ladxml.findall('skeleton')[0].findall('param')
    for p in params:

        pname = p.get('name')
        id    = int(p.get('id'))
        if max_param_id > -1 and id < max_param_id:
            continue
            
        pid = cleanId(id, pname)

        paramd = {'pid': pid,
                  'name': pname,
                  'type': 'bones',
                  'label': p.get('label', pname),
                  'label_min': p.get('label_min'),
                  'label_max': p.get('label_max'),
                  'value_default': float(p.get('value_default', 0)),
                  'value_min': float(p.get('value_min')),
                  'value_max': float(p.get('value_max')),
                  'edit_group': p.get('edit_group', None),
                  'sex': p.get('sex', None),
                  }

        try:
            bones = p.findall('param_skeleton')[0].findall('bone')
        except:
            log.warning("Issue in param [%s]" % pname)
            continue
        bs = []
        for b in bones:
            bname = b.get('name')
            raw = b.get('scale','0 0 0').split()
            sx = float(raw[0])
            sy = float(raw[1])
            sz = float(raw[2])

            scale = (sy,sx,sz)        
            raw = b.get('offset','0 0 0').split()
            offset = s2b((float(raw[0]), float(raw[1]), float(raw[2])))            

            bs.append({'name':bname, 'scale':scale, 'offset':offset}) 

        paramd['bones'] = bs

        if pid in DRIVERS:
            logging.error("unexpected duplicate pid: %s", pid)
        else:
            DRIVERS[pid] = [paramd]

    #

    drivers = ladxml.findall('driver_parameters')[0].findall('param')
    for p in drivers:
        id    = int(p.get('id'))
        if max_param_id > -1 and id < max_param_id:
            continue
            
        pname = p.get('name')
        pid = cleanId(id, pname)

        paramd = {'pid': pid,
                  'name': pname,
                  'label': p.get('label', pname),
                  'type': 'driven',
                  'label_min': p.get('label_min'),
                  'label_max': p.get('label_max'),
                  'value_default': float(p.get('value_default', 0)),
                  'value_min': float(p.get('value_min')),
                  'value_max': float(p.get('value_max')),
                  'edit_group': p.get('edit_group', None),
                  'sex': p.get('sex', None),
                  }

        dr = []
        driven=p.findall('param_driver')[0].findall('driven')
        for d in driven:

            ##

            nid="_"+d.get('id')

            did = None
            for driver in DRIVERS.keys():
                if driver.endswith(nid):
                    did=driver
                    break

            if did is None:

                continue

            drivend = {'pid':did,
                       'min1':float(d.get('min1', paramd['value_min'])),
                       'max1':float(d.get('max1', paramd['value_max'])),
                       'min2':float(d.get('min2', paramd['value_max'])),
                       'max2':float(d.get('max2', paramd['value_max'])),
                       }
            dr.append(drivend)

        paramd['driven']=dr

        if pid in DRIVERS:
            logging.error("unexpected duplicate pid: %s", pid)
        else:
            DRIVERS[pid] = [paramd]
                
    return DRIVERS

SEAM_EXCEPTIONS = {}
SEAM_EXTRA      = {}
PIN_EXTRA       = {}

SEAM_EXCEPTIONS['upperBodyMesh']  = [129, 168, 181, 200, 339, 1166, 1480, 1676, 1781, 2489,
                                     3048, 3273, 3380, 3430, 3885, 4189, 4351, 4709, 4744,
                                     5026, 5183, 5490]
SEAM_EXTRA['upperBodyMesh']       = []
PIN_EXTRA['upperBodyMesh']        = []
#

#
#

SEAM_EXCEPTIONS['lowerBodyMesh']  = [248, 803, 1114, 1258, 1389, 1614, 1670, 2122]
SEAM_EXTRA['lowerBodyMesh']       = []
PIN_EXTRA['lowerBodyMesh']        = []

#
#

SEAM_EXCEPTIONS['headMesh']      = [144, 347, 382, 532, 595, 621, 778, 784, 835, 862,
                                    1022, 1162, 1206, 1225, 1436, 1551, 1687, 1712, 1802,
                                    1829, 1852, 1872, 1885, 1902, 2097, 2152, 2203,
                                    2317, 2349, 2444, 1174, 1939, 467, 489, 526, 570,
                                    674, 699, 756, 999, 1210, 1235, 1261, 1301, 1352,
                                    1395, 1655, 1681, 1815, 1970, 2085, 2118, 2146, 2567,
                                    312, 554, 1359, 1402, 1752, 1949, 2075, 2460, 2510, 2554,
                                    467, 526, 570, 674, 699, 999, 1261, 1301, 1655, 2085, 2118, 2567
                                    ]
SEAM_EXTRA['headMesh']            = []
PIN_EXTRA['headMesh']             = []

#

#
#

#
#

SHAPEKEYS = {}

def get_karaage_shapekeys(ob):
    if len(SHAPEKEYS) == 0:
        if ob.type=='ARMATURE':
            arm = ob
        else:
            arm = ob.find_armature()

        avas = util.getKaraageChildSet(arm)
        for name in avas:
            if name in bpy.data.objects:
                ob = bpy.data.objects[name]
                if ob.type=='MESH' and ob.data.shape_keys and ob.data.shape_keys.key_blocks:
                    for i in range (1, len(ob.data.shape_keys.key_blocks)):
                        key = ob.data.shape_keys.key_blocks[i].name
                        SHAPEKEYS[key] = key
    return SHAPEKEYS
    
def has_karaage_shapekeys(ob):
    if not (ob and ob.data.shape_keys):
        return False
    shapekeys = get_karaage_shapekeys(ob)
    for x in ob.data.shape_keys.key_blocks.keys():
        if x in shapekeys:
            return True
    return False

def loadMeshes(rigType=None):
    '''
    Load the mesh details from avatar_lad.xml and the .llm files
    '''

    MESHES = {}
    ladxml = et.parse(util.get_lad_file(rigType, "Load meshes"))

    logging.info("Loading avatar data")

    meshes = ladxml.findall('mesh')
    for mesh in meshes:
        lod = int(mesh.get('lod'))
        if lod != 0:

            continue

        name = mesh.get('type')

        file_name = mesh.get('file_name')

        meshd = loadLLM(name, os.path.join(DATAFILESDIR,file_name))
        meshd['name'] = name
       
        meshd['morphs'] = {}

        MESHES[name] = meshd
        if name in SEAM_EXCEPTIONS:
           meshd['noseams']    = SEAM_EXCEPTIONS[name]
           meshd['extraseams'] = SEAM_EXTRA[name]
           meshd['extrapins']  = PIN_EXTRA[name]

        params = mesh.findall('param')       
        for p in params:
            pname = p.get('name')

            try:
                morph = meshd['morphsbyname'][pname]
            except KeyError as e:

                continue

            pid = cleanId(p.get('id'), pname)
            SHAPEKEYS[pid]=morph

            meshd['morphs'][pid]   = morph
            morph['value_min']     = float(p.get('value_min'))
            morph['value_max']     = float(p.get('value_max'))
            morph['value_default'] = float(p.get('value_default', 0))

    return MESHES

skeleton_meta = {}
def getSkeletonDefinition(rigType, jointType):
    global skeleton_meta
    key = "%s_%s" % (rigType, jointType)
    
    skeleton = skeleton_meta.get(key, None)
    if skeleton:
        return skeleton

    filepath = util.get_skeleton_file(rigType)

    from .util import V
    skeleton = util.Skeleton()
    boneset = get_rigtype_boneset(rigType, jointType, filepath)
    skeleton.add_boneset(boneset)
    skeleton_meta[key] = skeleton

    return skeleton

def getDefaultSkeletonDefinition():
    log.info("getDefaultSkeletonDefinition: get skeleton definition from filepath ")
    sceneRigType   = util.get_rig_type()
    sceneJointType = util.get_joint_type()
    skeleton = getSkeletonDefinition(sceneRigType, sceneJointType)
    return skeleton

SPECIAL_BONES = {
    "COG":["Origin", "Torso"],
    "PelvisInv":["COG", "Torso"],
    "Torso":["COG", "Torso"],
    "Pelvis":["PelvisInv", "Structure"],
    "CollarLinkLeft":["Chest", "Structure"], 
    "CollarLinkRight":["Chest", "Structure"],
    "CollarLeft":["CollarLinkLeft", "Arms"],
    "CollarRight":["CollarLinkRight", "Arms"],
    "HipLinkLeft":["Pelvis", "Structure"],
    "HipLinkRight":["Pelvis", "Structure"],
    "HipLeft":["HipLinkLeft", "Legs"],
    "HipRight":["HipLinkRight", "Legs"]
    }

ANIMATION_CONTROL_BONES = {
    "CWingLeft" :["Wing1Left",  "WingRoot", Vector((0,0,0.1)), "Wing"],
    "CWingRight":["Wing1Right", "WingRoot", Vector((0,0,0.1)), "Wing"]
    }

def get_hand_control_bones_for(boneset):
    lhcb  = {"C"+key[1:-5]+"Left":[key, "WristLeft", Vector((0,0,0.0)), "Hand", "CustomShape_Circle02"]   for key in boneset.keys() if key.startswith("mHand") and key.endswith("1Left")}
    rhcb  = {"C"+key[1:-6]+"Right":[key, "WristRight", Vector((0,0,0.0)), "Hand", "CustomShape_Circle02"] for key in boneset.keys() if key.startswith("mHand") and key.endswith("1Right")}
    return util.merge_dicts(lhcb, rhcb)
    
def load_control_bones(boneset, add_special_bones=True):
    #

    #

    CONTROL_BONES = [key[1:] for key in boneset.keys() if key.startswith("m") and key[1:] not in boneset]

    added_bones = CONTROL_BONES + [b for b in SPECIAL_BONES.keys() if b not in boneset and b not in CONTROL_BONES]
    for bone_name in added_bones:
        if bone_name not in boneset:
            mBone = None
            mBoneName = "m"+bone_name
            if mBoneName in boneset:
                mBone = boneset[mBoneName]
                bonegroup = mBone.bonegroup if mBone.bonegroup[0] != 'm' else mBone.bonegroup[1:]
            elif bone_name in SPECIAL_BONES.keys():
                val = SPECIAL_BONES[bone_name]
                bonegroup = val[1]
            else:
                log.debug("Set bone group for %s to %s" % (bone_name, bonegroup) )
                bonegroup = 'Custom'
            
            bonelayers = BONEGROUP_MAP[bonegroup][1]
            log.debug("load_control_bones: add Special Bone %s (group:%s)" % (bone_name, bonegroup))
            bone = Bone(bone_name, bonegroup=bonegroup, bonelayers=bonelayers)
            if mBone:
                bone.skeleton = mBone.skeleton
            boneset[bone_name] = bone

    for bone_name, val in SPECIAL_BONES.items():
        parent_name = val[0]
        bonegroup    = val[1]
        bone        = boneset[bone_name]
        parent      = boneset[parent_name]
        bone.set(bonegroup=bonegroup, parent=parent)

    for bone_name in CONTROL_BONES:
        bone         = boneset[bone_name]
        mbone        = boneset["m"+bone_name]

        if bone_name == 'Pelvis':
            bone.relhead = -mbone.reltail #Because of the PelvisInv
        else:
            bone.relhead = mbone.relhead

        bone.reltail = mbone.reltail
        
        parent_name  = mbone.parent.blname[1:] if bone_name not in SPECIAL_BONES.keys() else None
        if parent_name:
            parent = boneset[parent_name]
            bone.parent=parent
            parent.children.append(bone)

        if bone_name.startswith("Hand"):
            if any ([ str(i) in bone_name for i in range(2,4)]):
                bone.set(stiffness=(0,0.95,0.95))

    preset_bone_limitations(boneset)
    preset_bone_constants(boneset)

    #

    #

    #

    #

    #

def add_to_boneset(boneset, bonename, **args):
    bone = boneset.get(bonename, None)
    if bone:
        bone.set(**args)

def preset_bone_constants(boneset):
    from .util import V
    #

    #

    torsohead  = boneset['mTorso'].relhead
    spine2tail = boneset['mSpine2'].reltail
    pelvishead = boneset['mPelvis'].relhead
    pelvistail = boneset['mPelvis'].reltail
    coghead    = pelvishead+pelvistail # COG is relative to Origin like mPelvis!

    add_to_boneset(boneset, "Torso",     shape="CustomShape_Torso", relhead=(0,0,0), connected=False)
    add_to_boneset(boneset, "COG",       shape="CustomShape_COG",    relhead=coghead, reltail=(0,0.1,0) , connected=False)
    add_to_boneset(boneset, "PelvisInv", shape="CustomShape_Pelvis", relhead=(0,0,0), reltail=-pelvistail, connected=False)
    add_to_boneset(boneset, "Pelvis",    shape="CustomShape_Target", relhead=-pelvistail, reltail=pelvistail, connected=False)

    collarLeft  = boneset["mCollarLeft"]
    collarRight = boneset["mCollarRight"]
    hipLeft     = boneset["mHipLeft"]
    hipRight    = boneset["mHipRight"]
    chest       = boneset["mChest"]
    pelvis      = boneset["mPelvis"]

    add_to_boneset(boneset, "CollarLeft",      relhead=collarLeft.relhead,  reltail=collarLeft.reltail,  shape="CustomShape_Collar")
    add_to_boneset(boneset, "CollarRight",     relhead=collarRight.relhead, reltail=collarRight.reltail, shape="CustomShape_Collar")
    add_to_boneset(boneset, "HipLeft",         relhead=hipLeft.relhead,     reltail=hipLeft.reltail,     shape="CustomShape_Circle03")
    add_to_boneset(boneset, "HipRight",        relhead=hipRight.relhead,    reltail=hipRight.reltail,    shape="CustomShape_Circle03")

    add_to_boneset(boneset, "CollarLinkLeft",  relhead=chest.reltail,  reltail=collarLeft.relhead, is_structure=True)
    add_to_boneset(boneset, "CollarLinkRight", relhead=chest.reltail,  reltail=collarRight.relhead, is_structure=True)
    add_to_boneset(boneset, "HipLinkLeft",     relhead=pelvis.reltail, reltail=hipLeft.relhead, is_structure=True, connected=False)
    add_to_boneset(boneset, "HipLinkRight",    relhead=pelvis.reltail, reltail=hipRight.relhead, is_structure=True, connected=False)

    add_to_boneset(boneset, "Chest",         shape="CustomShape_Circle10")
    add_to_boneset(boneset, "Neck",          shape="CustomShape_Neck")
    add_to_boneset(boneset, "Head",          shape="CustomShape_Head")
    add_to_boneset(boneset, "ShoulderLeft",  shape="CustomShape_Circle03")
    add_to_boneset(boneset, "ShoulderRight", shape="CustomShape_Circle03")
    add_to_boneset(boneset, "ElbowLeft",     shape="CustomShape_Circle03")
    add_to_boneset(boneset, "ElbowRight",    shape="CustomShape_Circle03")
    add_to_boneset(boneset, "WristLeft",     shape="CustomShape_Circle05")
    add_to_boneset(boneset, "WristRight",    shape="CustomShape_Circle05")
    add_to_boneset(boneset, "KneeLeft",      shape="CustomShape_Circle03")
    add_to_boneset(boneset, "KneeRight",     shape="CustomShape_Circle03")
    add_to_boneset(boneset, "AnkleLeft",     shape="CustomShape_Circle05")
    add_to_boneset(boneset, "AnkleRight",    shape="CustomShape_Circle05")
        
def preset_bone_limitations(boneset):
    #

    #

    for bone, val in DEFAULT_BONE_LIMITS.items():
        if bone in boneset:
            stiffness, limit_rx, limit_ry, limit_rz, roll = val
            if roll:
                roll = radians(roll)
            boneset[bone].set( stiffness = stiffness, limit_rx = limit_rx, limit_ry = limit_ry, limit_rz = limit_rz, roll = roll)

def set_bone_layer(boneset, category, bcategory=None):
    if bcategory==None: bcategory = category
    layers = LAYER_MAP[category]
    for key in util.bone_category_keys(boneset, bcategory):
        boneset[key].layers = [layers[0]]

    if len(layers) == 2:
        for key in util.bone_category_keys(boneset, "m"+bcategory):
            boneset[key].layers = [layers[1]]

def get_leaf_bones(boneset):
    return [boneset[b.blname[1:]] for b in boneset.values() if b.blname[0]=='m' and b.leaf]

def get_ik_roots(boneset, rigType):

    return [b for b in boneset.values() if b.is_ik_root and (rigType=='EXTENDED' or b.skeleton=='basic')]

def connect_bone_chains(boneset):
    for cb in get_leaf_bones(boneset):
        entry     = cb
        chain_len = 1
        if not entry.blname.startswith('Wing4Fan'):
            while entry.parent and entry.parent.reltail == entry.relhead:
                entry.connected = entry.blname not in ['Skull', 'FaceEar1Right', 'FaceEar1Left', 'Torso', 'Pelvis']

                entry = entry.parent
                chain_len +=1

        if chain_len > 0:

            entry.is_ik_root = True
            entry.ik_len     = chain_len
            entry.ik_end     = cb
            cb.ik_root       = entry

def set_bento_bone_layers(boneset):
    for n in sym(['Eye.',
                  'FaceEyeAlt.'
                 ]):
        if n in boneset:

            boneset[n].layers=[B_LAYER_EXTRA]

    for n in sym(['FaceEyeAltTarget']):
        if n in boneset: boneset[n].layers=[B_LAYER_EYE_ALT_TARGET]
    try:
        for n in sym(["ikFaceLipCorner.","ikFaceEyebrowCenter.", "ikFaceLipShape", "ikFaceLipShapeMaster"]):
            boneset[n].layers=[B_LAYER_IK_FACE]
    except:
        pass

def set_bone_layers(boneset):
    boneset['COG'].layers=[B_LAYER_TORSO]

    for n in sym(['Ankle.', 'Knee.', 'Hip.']):
        boneset[n].layers=[B_LAYER_LEGS]
        
    for n in sym(['Collar.', 'Shoulder.', 'Elbow.', 'Wrist.']):
        boneset[n].layers=[B_LAYER_ARMS]
        
    for n in ['PelvisInv', 'Torso', 'Chest']:
        boneset[n].layers=[B_LAYER_TORSO]

    for n in ['Neck', 'Head']:
        boneset[n].layers=[B_LAYER_TORSO]

    for n in sym_expand(boneset.keys(), ['*Link.', 'Pelvis']):
        boneset[n].layers=[B_LAYER_STRUCTURE]
    
    for n in sym(['Toe.', 'Foot.', 'Skull','Eye.',
                 ]):
        if n in boneset: boneset[n].layers=[B_LAYER_EXTRA]
        
    for n in sym(['EyeTarget']):
        if n in boneset: boneset[n].layers=[B_LAYER_EYE_TARGET]

    for n in sym(['CollarLink.', 'Pelvis']):
        boneset[n].layers=[B_LAYER_STRUCTURE]

def create_face_rig(boneset):

    from .util import V
    for symmetry in ["Left", "Right"]:
        for handle in ["FaceLipCorner","FaceEyebrowCenter"]:
            try:
                ikHandleName   = "ik%s%s" % (handle, symmetry)
                parentBoneName = "%s%s" % (handle,symmetry)
                parentBone = boneset[parentBoneName]
                headBone   = boneset['Head']
                relhead    = parentBone.tail() - headBone.head()
                reltail    = parentBone.reltail

                ikHandle = Bone(ikHandleName,
                       parent    = headBone,
                       relhead   = relhead ,
                       reltail   = reltail,
                       connected = False,
                       layers    = [B_LAYER_IK_FACE],
                       group     = 'IK Face',
                       shape     = 'CustomShape_Cube',
                       wire      = False
                     )
                boneset[ikHandleName] = ikHandle
            except:
                continue
    try:
        faceRoot     = boneset.get('FaceLowerRoot', boneset.get('FaceRoot', boneset.get('Head')))

        lipLeft      = boneset['FaceLipCornerLeft']
        lipRight     = boneset['FaceLipCornerRight']
        lipCenter    = boneset.get('FaceLipUpperCenter', None)
        relhead = lipLeft.relhead + lipLeft.reltail
        if lipCenter:
            relhead = (0, lipCenter.relhead[1]+lipCenter.reltail[1], relhead[2] - 0.000)
            reltail = lipCenter.reltail
        else:
            relhead = (0, relhead[1] - 0.01, relhead[2] - 0.005)
            reltail = lipLeft.reltail
            reltail = (0, reltail[1], reltail[2])

        lipShapeBone = Bone('ikFaceLipShape',
                            parent      = faceRoot,
                            relhead     = relhead,
                            reltail     = reltail,
                            shape       = 'CustomShape_Lip',
                            shape_scale = 0.8,
                            connected   = False,
                            bonegroup   = 'IK Face',
                            bonelayers  = [B_LAYER_IK_FACE]
                            )
        boneset['ikFaceLipShape'] = lipShapeBone

        lipShapeMaster = Bone('ikFaceLipShapeMaster',
                            parent     = faceRoot,
                            relhead    = relhead,
                            reltail    = (0.01,0,0),
                            shape      = 'CustomShape_Cube',
                            connected  = False,
                            bonegroup  = 'IK Face',
                            bonelayers = [B_LAYER_IK_FACE]
                            )
        boneset['ikFaceLipShapeMaster'] = lipShapeMaster

    except:
        pass

def create_hand_rig(boneset):
    from .util import V
    for symmetry in ["Left", "Right"]:
        for finger in ["Thumb","Index","Middle","Ring","Pinky"]:
            try:
                wrist        = boneset["Wrist%s" % symmetry]
                fingerEnd    = boneset["Hand%s3%s" % (finger, symmetry)]
                ikSolverName = "ik%sSolver%s" % (finger, symmetry)
                ikTargetName = "ik%sTarget%s" % (finger, symmetry)
            except:
                continue
            ikSolver = Bone(ikSolverName,
                       parent     = fingerEnd,
                       reltail    = fingerEnd.reltail + V(0,0,0.01),
                       connected  = True,
                       bonelayers = [B_LAYER_IK_HIDDEN],
                       group      = 'IK'
                     )

            ikTarget = Bone(ikTargetName,
                       parent     = wrist,
                       relhead    = fingerEnd.tail() - wrist.head(),# + V(0,-.01,0),
                       reltail    = fingerEnd.reltail,
                       bonelayers = [B_LAYER_IK_HAND],
                       shape      = "CustomShape_Pinch",
                       group      = 'IK'
                     )

            if finger == 'Index':
                ikPinchName = "ik%sPinch%s" % (finger, symmetry)
                fingerMiddle  = boneset["Hand%s2%s" % (finger, symmetry)]
                thumbMiddle   = boneset["HandThumb2%s" % (symmetry)]
                ikPinch = Bone(ikPinchName,
                           parent     = wrist,
                           relhead    = 0.5*(thumbMiddle.head() + fingerMiddle.head()) - wrist.head() + V(0,0,-0.05),
                           reltail    = fingerMiddle.reltail,
                           bonelayers = [B_LAYER_IK_HAND],
                           shape      = "CustomShape_Pinch",
                           group      = 'IK'
                         )
                boneset[ikPinchName] = ikPinch

            boneset[ikSolverName] = ikSolver
            boneset[ikTargetName] = ikTarget

def create_ik_bones(boneset):

    LH = Vector((0.08279900252819061, -0.005131999962031841, -0.005483999848365784))
    RH = Vector((-0.08279900252819061, -0.005131999962031841, -0.005483999848365784))

    LB = Vector((0.08279900252819061, 0.1735360026359558, -0.0031580000650137663))
    RB = Vector((-0.08279900252819061, 0.1735360026359558, -0.0031580000650137663))

    create_ik_arm_bones(boneset)
    create_ik_leg_bones(boneset, 'Left', LH, LB)
    create_ik_leg_bones(boneset, 'Right', RH, RB)

    mHindLimb3Left = Vector(boneset["mHindLimb3Left"].head())
    mHindLimb3Left[2]=LH[2]
    mHindLimb3Right = mHindLimb3Left.copy()

    mHindLimb3Right[0] *= -1
    LB[1] += mHindLimb3Left[1]
    RB[1] += mHindLimb3Left[1]
    create_ik_limb_bones(boneset, 'Left', mHindLimb3Left, LB)
    create_ik_limb_bones(boneset, 'Right', mHindLimb3Right, RB)

def create_ik_arm_bones(boneset):
    ikLine = V(0,0.5,0)
    Origin = boneset['Origin']

    mWristLeft  = boneset["mWristLeft"]
    mWristRight = boneset["mWristRight"]

    bonegroup  = "IK Arms"
    bonelayers = BONEGROUP_MAP[bonegroup][1]

    ikWristLeft  = Bone("ikWristLeft", relhead=mWristLeft.head(), reltail=mWristLeft.reltail, parent=Origin, bonelayers=bonelayers, group="IK", shape="CustomShape_Hand", bonegroup=bonegroup)
    ikWristRight = Bone("ikWristRight", relhead=mWristRight.head(), reltail=mWristRight.reltail, parent=Origin, bonelayers=bonelayers, group="IK", shape="CustomShape_Hand", bonegroup=bonegroup)
    mElbowLeft = boneset["mElbowLeft"]
    mElbowRight = boneset["mElbowRight"]

    tloc=mElbowLeft.head() - ikWristLeft.head() + ikLine
    ikElbowTargetLeft = Bone("ikElbowTargetLeft", relhead=tloc, reltail=s2b(V(0, 0, 0.1)),parent=ikWristLeft, bonelayers=bonelayers, group="IK", shape="CustomShape_Target", bonegroup=bonegroup)

    tloc=mElbowRight.head() - ikWristRight.head() + ikLine
    ikElbowTargetRight = Bone("ikElbowTargetRight", relhead=tloc, reltail=s2b(V(0, 0, 0.1)),parent=ikWristRight, bonelayers=bonelayers, group="IK", shape="CustomShape_Target", bonegroup=bonegroup)

    ikElbowLineLeft = Bone("ikElbowLineLeft", relhead=mElbowLeft.head(), reltail=ikLine, parent=ikWristLeft, bonelayers=bonelayers, group="IK", shape="CustomShape_Line", bonegroup=bonegroup)
    ikElbowLineRight = Bone("ikElbowLineRight", relhead=mElbowRight.head(), reltail=ikLine, parent=ikWristRight,bonelayers=bonelayers,group="IK", shape="CustomShape_Line", bonegroup=bonegroup)

    IK_BONES = [ikWristLeft, ikWristRight, ikElbowTargetLeft, ikElbowTargetRight,
                ikElbowLineLeft, ikElbowLineRight]

    for bone in IK_BONES:
        boneset[bone.blname]=bone

def create_ik_leg_bones(boneset, side, Heel, Ball):
    ikLine = V(0,-0.3,0)
    Origin = boneset['Origin']

    bonegroup  = "IK Legs"
    bonelayers = BONEGROUP_MAP[bonegroup][1]
    
    ikHeel       = Bone("ikHeel"+side,      relhead=Heel, reltail=s2b(V(0, 0, -0.1)),  parent=Origin,      group="IK", bonelayers=bonelayers, shape="CustomShape_Foot",      bonegroup=bonegroup)
    ikFootPivot  = Bone("ikFootPivot"+side, relhead=V0, reltail=ikHeel.reltail,  parent=ikHeel,  group="IK", bonelayers=bonelayers, shape="CustomShape_FootPivot", bonegroup=bonegroup)

    bonegroup  = "Structure"
    bonelayers = BONEGROUP_MAP[bonegroup][1]
    loc = Ball-Heel
    ikFootBall = Bone("ikFootBall"+side, relhead=loc, reltail=s2b(V(0, 0, -0.1)), parent=ikHeel, bonelayers=bonelayers, group="IK", bonegroup=bonegroup)

    bonegroup  = "IK Legs"
    bonelayers = BONEGROUP_MAP[bonegroup][1]

    loc=boneset["mKnee"+side].head() - ikHeel.head() + ikLine
    ikKneeTarget = Bone("ikKneeTarget"+side, relhead=loc, reltail=s2b(V(0, 0, 0.1)),parent=ikHeel, bonelayers=bonelayers, group="IK", shape="CustomShape_Target", bonegroup=bonegroup)

    loc=boneset["mKnee"+side].head()
    ikKneeLine = Bone("ikKneeLine"+side, relhead=loc, reltail=ikLine, parent=ikHeel, bonelayers=bonelayers, group="IK", shape="CustomShape_Line", bonegroup=bonegroup)

    bonegroup  = "Structure"
    bonelayers = BONEGROUP_MAP[bonegroup][1]

    mAnkle = boneset["mAnkle"+side]
    loc = mAnkle.head() - ikFootPivot.head()
    ikAnkle = Bone("ikAnkle"+side, relhead=loc, reltail=mAnkle.reltail, parent=ikFootPivot, bonelayers=bonelayers, group="IK", bonegroup=bonegroup)

    IK_BONES = [ikHeel, ikFootPivot,
                ikFootBall, ikKneeTarget,
                ikKneeLine, ikAnkle]

    for bone in IK_BONES:
        boneset[bone.blname]=bone

def create_ik_limb_bones(boneset, side, Heel, Ball):
    ikLine = V(0,-0.3,0)
    Origin = boneset['Origin']

    bonegroup  = "IK Limbs"
    bonelayers = BONEGROUP_MAP[bonegroup][1]
    
    ikLimbHeel       = Bone("ikHindHeel"+side,  relhead=Heel, reltail=s2b(V(0, 0, -0.1)),  parent=Origin,      group="IK", bonelayers=bonelayers, shape="CustomShape_Foot",      bonegroup=bonegroup)
    ikLimbFootPivot  = Bone("ikHindFootPivot"+side, relhead=V0, reltail=ikLimbHeel.reltail,  parent=ikLimbHeel,  group="IK", bonelayers=bonelayers, shape="CustomShape_FootPivot", bonegroup=bonegroup)

    bonegroup  = "Structure"
    bonelayers = BONEGROUP_MAP[bonegroup][1]
    loc = Ball-Heel
    ikLimbFootBall = Bone("ikHindFootBall"+side, relhead=loc, reltail=s2b(V(0, 0, -0.1)), parent=ikLimbHeel, bonelayers=bonelayers, group="IK", bonegroup=bonegroup)

    bonegroup  = "IK Limbs"
    bonelayers = BONEGROUP_MAP[bonegroup][1]

    loc=boneset["mHindLimb2"+side].head() - ikLimbHeel.head() + ikLine
    ikLimbKneeTarget = Bone("ikHindLimb2Target"+side, relhead=loc, reltail=s2b(V(0, 0, 0.1)),parent=ikLimbHeel, bonelayers=bonelayers, group="IK", shape="CustomShape_Target", bonegroup=bonegroup)

    loc=boneset["mHindLimb2"+side].head()
    ikLimbKneeLine = Bone("ikHindLimb2Line"+side, relhead=loc, reltail=ikLine, parent=ikLimbHeel, bonelayers=bonelayers, group="IK", shape="CustomShape_Line", bonegroup=bonegroup)

    bonegroup  = "Structure"
    bonelayers = BONEGROUP_MAP[bonegroup][1]

    mHindLimb3 = boneset["mHindLimb3"+side]
    loc = mHindLimb3.head() - ikLimbFootPivot.head()
    ikLimbAnkle = Bone("ikHindLimb3"+side, relhead=loc, reltail=mHindLimb3.reltail, parent=ikLimbFootPivot, bonelayers=bonelayers, group="IK", bonegroup=bonegroup)

    IK_BONES = [ikLimbHeel, ikLimbFootPivot,
                ikLimbFootBall, ikLimbKneeTarget,
                ikLimbKneeLine, ikLimbAnkle]

    for bone in IK_BONES:
        boneset[bone.blname]=bone

def load_attachment_points(boneset, rigtype):
    from .util import V
    '''
    Load attachment points from avatar_lad.xml
    '''

    ATTACH = {}
    ladfile = util.get_lad_file(rigtype, "Load attachment points")
    ladxml = et.parse(ladfile)

    skel = ladxml.find('skeleton')
    attachments = skel.findall('attachment_point')

    up = Vector((0,0,0.03))
    reltail=s2b(up)
    bonegroup="Attachment"
    bonelayers=BONEGROUP_MAP[bonegroup][1]
    shape="CustomShape_Target"
    deform=False
    
    for attach in attachments:

        joint = attach.get('joint')
        if joint in boneset or joint=="mRoot":
            name = attach.get('name')

            pos = attach.get('position')
            pos = pos.split()
            for ii in range(len(pos)):
                pos[ii] = float(pos[ii])

            rot = attach.get('rotation')   
            rot = rot.split()
            for ii in range(len(rot)):
                rot[ii] = radians(float(rot[ii]))

            if joint=="mRoot":
                mPelvis = boneset["mPelvis"]
                root = mPelvis.head()
                relhead=s2b(V(pos)+root)
                parent=boneset["Origin"]
                rot0=V(0,0,0)

            else:
                relhead=s2b(V(pos))
                parent=boneset[joint]
                rot0=s2bo(V(rot))            

            abone_name = "a"+name

            bone = Bone(abone_name,
                         relhead=relhead,
                         reltail=reltail,
                         parent=parent, 
                         group=bonegroup,
                         bonelayers=bonelayers,
                         shape=shape, 
                         deform=deform,
                         rot0=rot0,
                         pos0=V(pos),
                         pivot0=relhead,
                         skeleton='basic', 
                         bonegroup=bonegroup, 
                         mandatory='false')
            boneset[abone_name] = bone

def get_bone_attributes(bone_xml):
    type   = bone_xml.tag
    attrib = bone_xml.attrib

    if type=='bone':
        blname = attrib['name']
        if blname in sym(['mAnkle.', 'mKnee.', 'mHip.']):
            attrib['skeleton']  = 'basic'
            attrib['bonegroup']  = 'mLegs'
            attrib['mandatory'] = 'true'
        elif blname in sym(['mCollar.', 'mShoulder.', 'mElbow.', 'mWrist.']):
            attrib['skeleton']  = 'basic'
            attrib['bonegroup']  = 'mArms'
            attrib['mandatory'] = 'true'
        elif blname in ['mPelvis', 'mTorso', 'mChest', 'mNeck', 'mHead']:
            attrib['skeleton']  = 'basic'
            attrib['bonegroup']  = 'mTorso'
            attrib['mandatory'] = 'true'
        elif blname in sym(['mToe.', 'mFoot.', 'mSkull', 'mEye.']):
            attrib['skeleton']  = 'basic'
            attrib['bonegroup'] = 'mExtra'
            attrib['mandatory'] = 'false'
        else:
            attrib['skeleton']  = 'extended'
            attrib['mandatory'] = 'false'
            
            if blname.startswith('mSpine'):
                attrib['bonegroup'] = 'Spine'
            else:        
                attrib['bonegroup'] = attrib.get('group', 'Custom')

    else:
        attrib['skeleton']  = 'basic'
        attrib['bonegroup']  = 'Collision'
        attrib['mandatory'] = 'false'

    return attrib

def has_connected_child(parent_xml):
    sibblings = parent_xml.findall('bone')
    for bone_xml in sibblings:
        attrib = get_bone_attributes(bone_xml)
        blname     = attrib['name']
        if 'connected' in attrib:
            connected = attrib['connected']
            if  connected =='true':
                return True

    attrib     = get_bone_attributes(parent_xml)
    blname     = attrib['name']

    return False
    
def load_bone_hierarchy(parent_xml, parent_bone, boneset, jointtype):
    from .util import V

    if boneset == None:
        boneset = {}

    sibblings = parent_xml.findall('*')

    for bone_xml in sibblings:
        bone_type  = bone_xml.tag    # can be 'bone' or 'collision_volume'
        attrib     = get_bone_attributes(bone_xml)
        blname     = attrib['name']
        ctrl_name  = blname[1:] if blname.startswith("m") else None

        pos0 = s2b(V(tuple(float(x) for x in attrib['pos'].split(" "))))   if 'pos'   in attrib else None

        scale0  = s2bo(V(tuple(float(x) for x in attrib['scale'].split(" "))))if 'scale' in attrib else None
        pivot0  = s2b(V(tuple(float(x) for x in attrib['pivot'].split(" ")))) if 'pivot' in attrib else pos0

        connected = attrib['connected']=='true' if 'connected' in attrib else False

        relhead  = pos0 if blname.startswith('mToe') or jointtype=='POS' else pivot0
        
        if blname=='mNeck' or (connected and bone_type=='bone' and parent_bone): #and (parent_bone.reltail == None or blname=='mNeck'):
            parent_bone.reltail = relhead
            parent_bone.end0    = relhead
            parent_bone.leaf    = False

        end0    = s2b(V(tuple(float(x) for x in attrib['end'].split(" "))))  if 'end' in attrib else None #and has_connected_child(bone_xml)==False else None
        reltail = end0

        if reltail == None and blname in BONE_TAIL_LOCATIONS:
            print("load_bone_hierarchy: enforce predefined bone tail for ", blname)
            reltail = s2b(V(BONE_TAIL_LOCATIONS[blname]))
        
        leaf       = True
        bonegroup  = attrib['bonegroup']
        if 'm' + bonegroup in BONEGROUP_MAP:
            bonegroup  = 'm' + bonegroup
        bonelayers = BONEGROUP_MAP[bonegroup][1]
        
        if bone_type == 'bone':

            if 'support' in attrib and attrib['support'] == "extended":
                group      = 'SL Extended'
            else:
                group      = 'SL Base'

            deform  = True
            bvhname = ANIMBONE_MAP[ctrl_name] if ctrl_name in ANIMBONE_MAP else None
            shape   = None
            rot0    = s2bo(V(tuple(float(x) for x in attrib['rot'].split(" "))))  if 'rot' in attrib else None
        else:
            bonelayers  = [B_LAYER_VOLUME]
            deform      = True
            group       = "Collision"
            bvhname     = None
            shape       = "CustomShape_Volume"
            rot0        = [radians(r) for r in s2b(V(tuple(float(x) for x in attrib['rot'].split(" "))))]
            
            if reltail:
                eul  = Euler( rot0, 'XYZ')
                reltail = Vector(reltail)
                reltail.rotate(eul)
            else:
                print("load bone hierarchy: found bone %s without defined reltail" % (blname) )

        childbone = Bone(blname, 
                        bvhname    = bvhname, 
                        slname     = blname, 
                        relhead    = relhead,
                        reltail    = reltail,
                        end0       = end0,                        
                        parent     = parent_bone,
                        bonelayers = bonelayers, 
                        shape      = shape, 
                        roll       = 0, 
                        connected  = connected, 
                        group      = group, 
                        stiffness  = [0.0,0.0,0.0], 
                        limit_rx   = None, 
                        limit_ry   = None, 
                        limit_rz   = None, 
                        deform     = deform, 
                        scale0     = scale0, 
                        rot0       = rot0,
                        pos0       = pos0,
                        pivot0     = pivot0,
                        skeleton   = attrib['skeleton'],
                        bonegroup  = bonegroup,
                        mandatory  = attrib['mandatory'],
                        leaf       = leaf,
                        attrib     = attrib
                        )

        boneset[blname] = childbone
        
        load_bone_hierarchy(bone_xml, childbone, boneset, jointtype)

    return boneset

bonesets = {}

def get_reference_boneset(arm):
    rigType   = arm.RigProps.RigType
    jointType = arm.RigProps.JointType
    boneset   = get_rigtype_boneset(rigType, jointType)
    return boneset

def get_rigtype_boneset(rigType, jointtype, filepath=None):
    global bonesets
    use_rigType = filepath == None
    
    boneset = None
    if use_rigType:
        rigType = util.get_rig_type(rigType)    
        boneset = get_boneset(rigType, jointtype)
    
    if boneset == None:

        print("get_rigtype_boneset: Need to load boneset from file for rigType [%s] jointtype [%s]" % (rigType, jointtype) )
    
        if use_rigType:
            filepath = util.get_skeleton_file(rigType, comment='get_rigtype_boneset')

        boneset = load_skeleton_data(filepath, rigType, jointtype)
        add_boneset(rigType, jointtype, boneset)

    return boneset

def get_boneset(rigType, jointtype):
    global bonesets
    key = "%s_%s" % (rigType,jointtype)
    boneset = bonesets.get(key)
    return boneset
    
def add_boneset(rigType, jointtype, boneset):
    global bonesets
    key = "%s_%s" % (rigType,jointtype)
    bonesets[key] = boneset

def load_skeleton_data(filepath, rigType, jointtype):
    from .util import V

    global bonesets
    boneset = get_boneset(rigType, jointtype)
    print("Create %s Avatar %s file %s" % (rigType, "reusing" if boneset else "using", filepath) )

    if not boneset:

        skeletontree = et.parse(filepath)
        root = skeletontree.getroot()

        blname = "Origin"
        origin = Bone(blname,
                      bvhname     = None,
                      slname      = blname,
                      reltail     = s2b(V(BONE_TAIL_LOCATIONS[blname])),
                      bonelayers  = [B_LAYER_ORIGIN],
                      shape="CustomShape_Origin",
                      skeleton='basic', bonegroup='Origin', mandatory='false')

        boneset = {"Origin": origin}
        load_bone_hierarchy(root, origin, boneset, jointtype)
            
        boneset["mHipRight"].roll     = radians(-7.5)
        boneset["mHipLeft"].roll      = radians( 7.5)

        create_ik_bones(boneset)
        load_control_bones(boneset)

        create_face_rig(boneset)
        
        cog         = boneset['COG']
        mPelvis     = boneset['mPelvis']

        mEyeRight = boneset["mEyeRight"]
        mEyeLeft  = boneset["mEyeLeft"]
        
        loc = 0.5*(mEyeRight.relhead+mEyeLeft.relhead)
        EyeTarget = Bone("EyeTarget", relhead=V((loc.x, loc.y-2.0, loc.z)), reltail=V((0,0,0.1)), 
                         bonelayers=[B_LAYER_EYE_TARGET], parent=boneset["Head"], shape="CustomShape_EyeTarget",
                         skeleton='basic', bonegroup='Eye Target', mandatory='false')
        boneset["EyeTarget"] = EyeTarget
        FaceEyeTarget = Bone("FaceEyeAltTarget", relhead=V((loc.x, loc.y-2.0, loc.z)), reltail=V((0,0,0.1)), 
                         bonelayers=[B_LAYER_EYE_ALT_TARGET], parent=boneset["Head"], shape="CustomShape_EyeTarget",
                         skeleton='basic', bonegroup='Eye Alt Target', mandatory='false')
        boneset["FaceEyeAltTarget"] = FaceEyeTarget

        load_attachment_points(boneset, rigType)
        connect_bone_chains(boneset)
        set_bento_bone_layers(boneset)
        #
        add_boneset(rigType, jointtype, boneset)
        print("Loaded %s.%s Skeleton" % (rigType,jointtype))

        for bone in boneset.values():
            bone.b0head = bone.head(bind=True)
            bone.b0tail = bone.tail()
            b0dist = bone.head(bind=True)
            if bone.parent:
                b0dist -= bone.parent.head(bind=True)
            bone.b0dist = Vector(b0dist).magnitude

    return boneset

class LoadSkeleton(bpy.types.Operator):
    bl_idname = "karaage.load_skeleton"
    bl_label  = "Load Skeleton"
    bl_description = "Load the Karaage Skeleton from file"

    def execute(self, context):
        omode = util.ensure_mode_is("OBJECT", context=context)
        get_rigtype_boneset()
        util.ensure_mode_is(omode, context=context)
        return {'FINISHED'}
        
if __name__ == '__main__':

    pass

#
#
#
#
#
#
#
#