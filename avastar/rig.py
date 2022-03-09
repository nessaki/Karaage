#
#
#
#
#
#
#

import bpy, os, logging, traceback
from bpy.props import *
from bpy.app.handlers import persistent

from . import data, const, util
from .util import Skeleton, PVector, s2b
from .context_util import *
from .const import *
from mathutils import Vector, Matrix, Euler, Quaternion
from bpy.types import Menu, Operator
from bl_operators.presets import AddPresetBase

log = logging.getLogger('karaage.rig')
connectlog = logging.getLogger('karaage.rig.connect')

log_cache = logging.getLogger('karaage.cache')

def matrixToStringArray(M, precision=6, location_precision=None):
    p = precision
    lp = location_precision if location_precision else p
    mat = ["% 0.6f%s" % (round(M[ii][jj], lp if jj == 3 and ii != 3 else p), "\n" if jj==3 else "") for ii in range(4) for jj in range(4)]
    mat[0] = "\n "+mat[0]
    return mat

def calculate_bind_shape_matrix(arm, mesh, with_rot=True):
    Marm = arm.matrix_world
    
    t = mesh.matrix_world.to_translation()
    mat = Matrix.Translation(t)

    bsm = Rz90I*Marm.inverted() *mat if with_rot else mat
    return bsm

#

#
def get_offset_to_parent(bone, get_roll=True):
    
    head = Vector(bone.head)
    tail = Vector(bone.tail)
    roll = bone.roll if get_roll else 0;
    
    parent = bone.parent
    if parent:
        head -= bone.parent.head
        tail -= bone.parent.tail

    return head, tail, roll
#

#
def get_offset_from_sl_bone(bone, corrs=None, get_roll=True):
    head, tail, roll = get_offset_to_parent(bone, get_roll)
    head -= Vector(bone['relhead'])
    tail -= Vector(bone['reltail'])
    
    if corrs:
        corr = corrs.get(bone.name, None)
        if corr:
            head -= Vector(corr['head'])
            tail -= Vector(corr['tail'])    

    return head, tail, roll

def get_bone_names_with_jointpos(arm):

    joints = arm.get('sl_joints')
    if joints == None:
        return []

    boneset = joints.keys()
    bones   = util.get_modify_bones(arm)

    resultset = set()
    for name in boneset:
        resultset.add(name)
        if name[0]=='m' and name[1:] in bones:
            resultset.add(name[1:])
        elif 'm' + name in bones:
            resultset.add('m'+name)
    return resultset

def get_first_connected_child(bone):
    for child in bone.children:
        if child.use_connect:
            return child
    return None

def treat_as_linked(bone,ebones):
    connected = is_linked(bone, ebones)
    if not connected and bone.name[0] == 'm':
        dbone = ebones.get(bone.name[1:])
        if dbone:
            connected = dbone.use_connect
    return connected

def is_linked(bone,ebones):
    connected = bone.use_connect
    if not connected and bone.parent:
        head = getattr(bone,        'head_local', getattr(bone,'head'))
        tail = getattr(bone.parent, 'tail_local', getattr(bone.parent,'tail'))
        mag = (head - tail).magnitude
        connected = mag < 0.0001
    return connected

def set_connect(bone, connect, msg=None):
    if bone.parent and bone.use_connect != connect:
        bone.use_connect = connect
        if msg:
            connectlog.info("%s bone %s o-- %s %s" % (\
              "Connecting" if connect else "Disconnect",
              bone.parent.name, 
              bone.name, 
              msg
             ))

def get_joint_cache(armobj, include_ik=False):
    cache = armobj.get('sl_joints')
    if not cache or include_ik:
        return cache
    return {key:j for key,j in cache.items() if key[0:2] != 'ik'}

def get_joint_offset_count(armobj):
    joints = get_joint_cache(armobj)
    joint_count = len(joints) if joints else 0
    return joint_count

def get_joint_bones(arm, all=True, sort=True, order='TOPDOWN'):
    ebones = util.get_modify_bones(arm)
    keys = util.Skeleton.bones_in_hierarchical_order(arm, order=order) if sort else ebones.keys()

    bones = [ebones[name] for name in keys if name[0] in ["m", "a"] or name in SLVOLBONES or name == 'COG']

    if not all:
        bones = [b for b in bones if b.select_head or (b.parent and b.parent.select_tail and treat_as_linked(b,ebones))]

    return bones

def get_cb_partner(bone, bones):
    pname = bone.name[1:] if bone.name[0] == 'm' else 'm' + bone.name
    return bones.get(pname)

def reset_bone(armobj, bone, boneset):
    h, t = get_sl_restposition(armobj, bone, use_cache=False)
    head  = h     #Skeleton.head(context, bone, ebones)
    tail  = h + t #Skeleton.tail(context, bone, ebones)
    roll  = boneset[bone.name].roll if bone.name in boneset else 0

    if 'fix_head' in bone: del bone['fix_head'] 
    if 'fix_tail' in bone: del bone['fix_tail']
    if 'cache' in bone: del bone['cache']
    
    if armobj.mode == 'EDIT':
        bone.head = head
        bone.tail = tail
        bone.roll = roll

    else:
        bone.head_local = head
        bone.tail_local = tail

def remove_joint_from_armature(bone, joints):
    if bone.name in joints:
        del joints[bone.name]
        util.set_head_offset(bone, None)
        util.set_tail_offset(bone, None)
        if 'joint' in bone: del bone['joint']
        return 1

    return 0

def del_offset_from_sl_armature(context, arm, delete_joint_info, all=True):
    log.info("Delete Joint Offsets from [%s]" % (arm.name))
    ebones = arm.data.edit_bones
    boneset = data.get_reference_boneset(arm)
    bones = get_joint_bones(arm, all=all, order='BOTTOMUP')

    joint_offset_list = arm.data.JointOffsetList
    joint_offset_list.clear()

    oumode = util.set_operate_in_user_mode(False)
    if delete_joint_info:
        log.info("delete_joint_info %d selected edit bones to SL Restpose in Armature:[%s]" % (len(bones), arm.name) )
        for b in bones:
            mbone, cbone = get_sync_pair(b, ebones)
            if mbone and cbone:

                reset_bone(arm, mbone, boneset)
                reset_bone(arm, cbone, boneset)
            else:

                reset_bone(arm, b, boneset)

    joints  = arm.get('sl_joints', None)
    if joints:
        counter = 0
        for b in bones:
            mbone, cbone = get_sync_pair(b, ebones)
            if mbone and cbone:
                counter += remove_joint_from_armature(mbone, joints)
                counter += remove_joint_from_armature(cbone, joints)
            else:
                counter += remove_joint_from_armature(b, joints)
        if all:
            orphans = 0
            for key in joints.keys():
                if key not in bones:
                    log.debug("Removing orphan Joint [%s]" % (key) )
                    del joints[key]
                    orphans += 1
            log.warning("Removed %d orphaned Jointpos definitions" % (orphans))
            del arm['sl_joints']
            log.warning("Deleted sl_joints from %s" % (arm.name) )
    reset_cache(arm, full=True)
    util.set_operate_in_user_mode(oumode)
    return

def copy_bone (from_bone, to_bone, mode):
   if mode == 'EDIT':

       to_bone.head = from_bone.head
       to_bone.tail = from_bone.tail
       to_bone.roll = from_bone.roll
   else:

       to_bone.head_local = from_bone.head_local
       to_bone.tail_local = from_bone.tail_local

def get_sync_pair(bone, bones):
    name = bone.name
    if name[0] == 'm' and name != 'mPelvis':
        mbone = bone
        cbone = bones.get(name[1:])
    elif name[0] == "a" or name in SLVOLBONES:
        mbone = cbone = None
    else:
        cbone = bone
        mbone = bones.get('m'+name, None)
    return mbone, cbone

def synchronize_bone(bone, bones, mode):
    mbone, cbone = get_sync_pair(bone, bones)
        
    if mbone and cbone:
        if mbone.select_head:
            copy_bone (mbone, cbone, mode)
        else:
            copy_bone (cbone, mbone, mode)

def get_toe_location(armobj):
    bones = util.get_modify_bones(armobj, only='mToeRight')    
    loc = bones[0].head if armobj.mode == 'EDIT' else bones[0].head_local
    return loc

def get_sl_bone(bone, bones):

    return bone if bone.name[0] in ['m','a'] else bones.get('m'+bone.name, bone)

def calculate_offset_from_bone(context=None, armobj=None, dbone=None, bones=None, Bones=None):
    if not context:
        context = bpy.context
    if not armobj:
        armobj = util.get_armature(context.object)
    if not dbone:
        dbone = bpy.context.active_bone
    if not bones:
        bones = util.get_modify_bones(armobj)
    if not Bones:
        Bones = data.get_reference_boneset(armobj)

    jbone = get_master_bone(bones, dbone)
    JOINT_OFFSET = util.get_min_joint_offset()
    
    mparent = get_parent_no_structure(jbone)
    hscale  = util.get_bone_scale(mparent, inverted=True) if mparent else Vector((1,1,1))
    MHI     = util.matrixScale(hscale)
    tscale  = util.get_bone_scale(jbone, inverted=True) if mparent else Vector((1,1,1))
    MTI     = util.matrixScale(tscale)
    if jbone.name in SLVOLBONES:
        MTI = util.matrixScale(hscale, M=MTI)
        
    h0, t0 = get_custom_bindposition(armobj, jbone, use_cache=False)
    h = jbone.head
    t = jbone.tail - jbone.head
    o = Vector(jbone.get('offset', (0,0,0) ))
    
    dhead = MHI*(h - h0) # head offset
    dtail = MTI*(t - t0) # tail offset

    hmag = dhead.magnitude
    tmag = dtail.magnitude
    roll  = jbone.roll
    
    enabled = hmag > JOINT_OFFSET or tmag > JOINT_OFFSET
    if hmag > JOINT_OFFSET:
        dhead += o

    h0 = Vector(jbone.get('relhead', dhead)) #original distance in rest shape

    jbone['orelhead'] = dhead + Vector(jbone.get('relhead', (0,0,0)))
    jbone['oreltail'] = dtail + Vector(jbone.get('reltail', (0,0,0)))

    joint   = {'key':jbone.name,
               'head':dhead,
               'tail':dtail,
               'roll':roll,
               'enabled':enabled,
               'hmag':hmag,
               'tmag':tmag,
               'h0':h0}

    return jbone, joint

def calculate_offset_from_sl_armature(
        context,
        armobj,
        corrs=None,
        all=False,
        with_ik_bones=False,
        with_joint_tails=True):

    def cofa_print(key, bonename, joint, end):
        log.info("cofa: Offset %s added:   m:% .4f h:[% .4f % .4f % .4f] for %s/%s" 
        % (end,
           joint.magnitude,
           joint[0], joint[1], joint[2],
           key,
           bonename)
        )
    joints = armobj.get('sl_joints', None)
    if joints is None:
        log.info("cofa: Create new joint repository for armature %s" % (armobj.name) )
        joints = {}
        armobj['sl_joints'] = joints
    elif len(joints) == 0 or all:
        log.info("cofa: Reuse existing joint repository for armature %s" % (armobj.name) )
        joints.clear()
    else:
        log.info("cofa: Add Bones to existing pre filled joint repository for armature %s" % (armobj.name) )

    joint_bones = get_joint_bones(armobj, all=all)
    bones       = util.get_modify_bones(armobj)
    Bones       = data.get_reference_boneset(armobj)

    log.info("cofa: processing %d joint bones for armobj %s" % (len(joint_bones), armobj.name) )

    JOINT_OFFSET = util.get_min_joint_offset()

    reset_cache(armobj)
    ignored = 0

    joint_offset_list = armobj.data.JointOffsetList
    joint_offset_list.clear()
    for jbone in joint_bones:

        if jbone.name in joints:
            del joints[jbone.name]
        bone, joint = calculate_offset_from_bone(context, armobj, jbone, bones, Bones)
        head = Vector(joint['head'])
        tail = Vector(joint['tail'])

        if joint['enabled'] :
            key, dummy = get_joint_for_bone(joints, bone) # Only want the name here

            prop = None
            if joint['hmag'] > JOINT_OFFSET:
                util.set_head_offset(bone, head, msg="rig:")

                prop = joint_offset_list.add()
                prop.has_head = True
                prop.head = head
            if joint['tmag'] > JOINT_OFFSET and with_joint_tails:
                util.set_tail_offset(bone, tail, msg="rig:")
                if not prop:
                    prop = joint_offset_list.add()
                prop.has_tail = True
                prop.tail=tail

            if prop:
                prop.name = key
                try:
                    joints[key] = joint
                except:
                    print("ERROR cofa: key %s: joint %s %d" % (key, joint, len(joints)) )

        elif bone.name in joints:
            log.info("cofa: Offset removed: %s  for %s" % (head, jbone.name) )
        elif all:
            ignored += 1
        else:

            ignored += 1

    if ignored > 0:
        log.info("cofa: %d bones located close to their default position (offset < %0.2f mm) (armature:%s)" % (ignored, JOINT_OFFSET*1000, armobj.name) )

    try:
        armobj['sl_joints'] = joints
    except:
        log.error("ERROR cofa: Can not assign joint offset list to armature:")
        log.error("ERROR cofa: armature type[%s]" % type(armobj))
        log.error("ERROR cofa: armature name[%s]" % armobj.name)
        log.error("ERROR cofa: joints type [%s]" % type(joints))
        log.error("ERROR cofa: joints len [%s]" % len(joints))
        raise
    return joints

def get_joint_for_bone(joints, bone):

    if joints == None:
        return bone.name, None

    jname = bone.name
    joint = joints.get(jname)

    return jname, joint

def get_effective_joint_location(context=None, arm=None, bone=None, Bones=None, jointtype='POS'):
    if not context:
        context=bpy.context
    if not arm:
        arm=util.get_armature(context.object)
    if not bone:
        bone = context.active_bone
    if not Bones:
        Bones = data.get_reference_boneset(arm)
    jh,jt = util.get_joint_offset(bone)
    if jh.magnitude > 0:
        use_bind_pose=arm.RigProps.rig_use_bind_pose
        parent = get_parent_no_structure(bone)
        if parent:
            phead = util.Skeleton.get_restposition(context, parent, bind=False, with_joint=True, use_bind_pose=use_bind_pose)
        else:
            phead = V0.copy()
        head = util.Skeleton.get_restposition(context, bone, bind=False, with_joint=True, use_bind_pose=use_bind_pose)
        fix = head - phead
        precision = 6
        bone_type      = 'custom_pos'
    else:
        fix       = Vector(Bones[bone.name].pivot0) if jointtype=='PIVOT' else Vector(Bones[bone.name].pos0)
        precision = 6 if jointtype=='PIVOT' else 3
        bone_type      = 'avatar_pos'
    #
    return fix, precision, bone_type

#

#

def calculate_pivot_matrix(context=None, armobj=None, dbone=None, bones=None, with_rot=True, with_joints=True, jointtype='POS'):

    def export_sl_definition(dbone, armobj):
        if not util.use_sliders(context):

            return False

        jh,jt = util.get_joint_offset(dbone)
        if not jh:

            return True

        return jh.magnitude < util.get_min_joint_offset()

    def get_sl_bone(armobj, dbone, parent):
        head, t  = get_sl_restposition(armobj, dbone, use_cache=True)
        if parent:
            phead, t = get_sl_restposition(armobj, parent, use_cache=True)
            head -= phead
        p    = 6
        bone_type = 'no_offset'
        return head, p, bone_type

    if not context:
        context=bpy.context
    if not armobj:
        armobj=util.get_armature(context.object)
    if not dbone:
        dbone = context.active_bone
    if not bones:
        bones = data.get_reference_boneset(armobj)

    parent  = get_parent_no_structure(dbone)

    if armobj.RigProps.rig_use_bind_pose:

        if 'rest_mat' in dbone:
            array = Vector(dbone['rest_mat'])
            M = Matrix()
            for i in range(0,4):
                for j in range(0,4):
                    M[i][j] = array[4*j + i]
            return M, 6, 'no_offset'
        else:
            head, p, bone_type = get_sl_bone(armobj, dbone, parent)

    elif export_sl_definition(dbone, armobj):

        head, p, bone_type = get_sl_bone(armobj, dbone, parent)

    else:
        if with_joints:
            h, t = get_custom_restposition(armobj, dbone)
            if dbone.parent:
               p, t = get_custom_restposition(armobj, dbone.parent)
               head = h - p
        else:

            head = dbone.head.copy() #the bone is moved around if you omitt the copy() here!
            if dbone.parent:
               head -= dbone.parent.head
        p = 6
        bone_type = 'custom_pos'

    if with_rot:
        head = Vector((-head.y, head.x, head.z))
    M    = util.matrixLocation(head)
    return M, p, bone_type

def set_bone_to_restpose(arm, bone, boneset):
    if bone.name[0] in ["m", "a"] or bone.name in SLVOLBONES:
        restloc, scale, scale0 = calculate_local_matrix(arm, bone, boneset)

        loc     =  bone.head # returns same value as util.Skeleton.head(context=None, bone, bones)
        disposition = (restloc - loc).magnitude
        if disposition >= 0.001:

            bone.head = restloc
            if bone.name[0]=='m':
                bones = util.get_modify_bones(arm)
                cBone = bones.get(bone.name[1:], None)
                if cBone:
                    cBone.head = restloc

    for child in bone.children:
        set_bone_to_restpose(arm, child, boneset)

def set_to_restpose(context, arm):
    RigType = arm.RigProps.RigType
    boneset = data.get_rigtype_boneset(RigType)

    active = context.object
    bpy.context.scene.objects.active = arm
    omode = util.ensure_mode_is('EDIT')

    roots = roots = [b for b in arm.data.edit_bones if b.parent == None]
    for root in roots:
        set_bone_to_restpose(arm, root, boneset)

    util.ensure_mode_is('OBJECT')
    util.ensure_mode_is(omode)
    bpy.context.scene.objects.active = active
    return

def calculate_local_matrix(arm, bone, boneset = None, rotate=False, verbose=False):

    if boneset == None:
        rigType = arm.RigProps.RigType
        boneset = data.get_rigtype_boneset(rigtype)

    Bone    = boneset[bone.name]
    pivot   = Vector(Bone.pivot0)    # pivot comint from avatar_skeleton
    offset  = Vector(bone['offset']) # offset coming from avatar_lad
    loc     = pivot + offset

    if bone.name in ['mPelvis'] or not bone.parent:
        L      = Vector((0,0,0))
        scale  = Vector((0,0,0))
        scale0 = Vector((1,1,1))
    else:
        L, scale, dummy = calculate_local_matrix(arm, bone.parent, boneset, rotate, verbose)
        scale  = Vector(bone.parent['scale'])
        scale0 = Vector(bone.parent['scale0'])

    if rotate:
        L += Vector([ -loc[1], loc[0], loc[2]])
    else:
        L += Vector([ loc[0],  loc[1], loc[2]])
    
    if verbose:
        print("bone %s pivot %s trans %s scale %s" % (bone.name, Vector(pivot), (M*L).translation, scale) )

    return L, scale, scale0

def mpp(M):
    print( "Matrix((({: 6f}, {: 6f}, {: 6f}, {: 6f}),".format  (*M[0]))
    print( "        ({: 6f}, {: 6f}, {: 6f}, {: 6f}),".format  (*M[1]))
    print( "        ({: 6f}, {: 6f}, {: 6f}, {: 6f}),".format  (*M[2]))
    print( "        ({: 6f}, {: 6f}, {: 6f}, {: 6f}))),".format(*M[3]))

def pose_mat_experimental(armobj, dbone):
    pbone = armobj.pose.bones[dbone.name]
    pt    = Vector(pbone.tail - pbone.head)
    bt    = Vector(dbone.get('reltail', pt))
    cross = bt.cross(pt)
    angle = bt.angle(pt)
    M = Matrix.Rotation(angle,4,cross)
    O = Matrix(dbone['mat0']).to_3x3()
    O.rotate(M)
    return M

def rot0_mat(dbone):

    if 'rot0' in dbone:
        rot0 = Vector(dbone['rot0'])
        Rot0 = Euler(rot0,'XYZ').to_matrix().to_4x4()
    else:
        Rot0 = Matrix()
    return Rot0

def pose_mat(armobj, dbone, use_custom=False, sync_volume_bones=True):
    
    if sync_volume_bones and dbone.name in SLVOLBONES:
        return pose_mat(armobj, dbone.parent, use_custom, sync_volume_bones=False)

    MC = None
    if use_custom:

        def get_rot(bone, channel, default):
            val = dbone.get(channel)
            if val == None:
                val = default
            else:
                val = DEGREES_TO_RADIANS * val
            return val

        x = get_rot (dbone, 'restpose_rot_y', None)
        y = get_rot (dbone, 'restpose_rot_x', None)
        z = get_rot (dbone, 'restpose_rot_z', None)

        if x!= None and y != None and z != None:
            crot = Vector((x,y,z))

            MC = Euler(crot,'XYZ').to_matrix().to_4x4()

    pbone = armobj.pose.bones[dbone.name]
    pt    = Vector(pbone.tail - pbone.head)
    bt    = Vector(dbone.get('reltail', pt))
    Q     = bt.rotation_difference(pt)
    M     = Q.to_matrix().to_4x4()

    if MC:
        log.warning("--------------------------------------------------------------")
        log.warning("Karaage Rot: %s for bone: %s" % (M.to_euler(), dbone.name) )
        log.warning("Custom  Rot: %s for bone: %s" % (MC.to_euler(), dbone.name) )
        M = MC
        
    return M

def scale_mat(armobj, dbone, applyScale):

    S = util.getBoneScaleMatrix(dbone, normalize=False, use_custom=True)

    if applyScale:
        Marm = armobj.matrix_world
        tl,tr,ts = Marm.decompose()
        S[0][0] = S[0][0]/ts[0]
        S[1][1] = S[1][1]/ts[1]
        S[2][2] = S[2][2]/ts[2]
    return S

def calculate_bind_matrix(armobj, dbone, applyScale=False, with_sl_rot=True, use_bind_pose=True, with_rot=True):

    if use_bind_pose:

        if 'bind_mat' in dbone:
            array = Vector(dbone['bind_mat'])
            M = Matrix()
            for i in range(0,4):
                for j in range(0,4):
                    M[i][j] = array[4*j + i]
            return M

        bone = armobj.pose.bones[dbone.name]
        loc = bone.head
        R = pose_mat(armobj, dbone)
    else:
        bone = dbone
        loc = bone.head_local
        R = Matrix()
    L = util.matrixLocation(loc)

    if with_rot:
        R0 = rot0_mat(dbone)
    else:
        R0 = Matrix()

    S = scale_mat(armobj, dbone, applyScale)    

    M = L*R*R0*S

    if with_sl_rot:
        M= Rz90I*M*Rz90

    return M

def calculate_inverse_bind_matrix(armobj, dbone, applyScale=False, with_sl_rot=True, use_bind_pose=True):

    M = calculate_bind_matrix(armobj, dbone, applyScale, with_sl_rot, use_bind_pose)
    Minv = M.inverted()
    return Minv

def get_bones_from_layers(armobj, layers):
    bones   = util.get_modify_bones(armobj)
    boneset = [b for b in bones if any (b.layers[layer] for layer in layers)]
    return boneset

def get_skeleton_from(armobj):
    objRigType   = armobj.RigProps.RigType
    objJointType = armobj.RigProps.JointType
    S = data.getSkeletonDefinition(objRigType, objJointType)
    return S

def adjustAvatarBonesToRig(armobj, boneset):

    S = get_skeleton_from(armobj)

    for cbone in boneset:
        try:

            Cbone = S[cbone.name] # The original cbone bone descriptor
            Mbone = Cbone.parent  # The original mBone descriptor       
            mbone = cbone.parent  # The mBone partner of the cbone

            DCT   = Vector(Cbone.tail() - Mbone.tail())
            DCH   = Vector(Cbone.head() - Mbone.head())    # The original mBone in <0,0,0>

            M     = Vector(Mbone.tail() - Mbone.head())
            m     = mbone.tail_local - mbone.head_local
            rot   = M.rotation_difference(m) # rotation relative to its default location

            DCH.rotate(rot)
            DCT.rotate(rot)

            cbone.head_local = mbone.head_local + DCH
            cbone.tail_local = mbone.tail_local + DCT

        except:
            print("Could not adjust Bone %s" % (cbone.name) )
            raise

def adjustVolumeBonesToRig(armobj):
    omode=util.ensure_mode_is('EDIT')
    bones = util.get_modify_bones(armobj)
    boneset = [b for b in bones if b.layers[B_LAYER_VOLUME]]
    S = get_skeleton_from(armobj)

    for b in boneset:
        if b.parent == None: continue
        p = b.parent                   # The mBone of the volume
        n = Vector(p.head - p.tail)    # The mBone in <0,0,0>

        B = S[b.name]                  # The original volume bone descriptor
        if B:
            P = B.parent                   # The original mBone descriptor
            N = Vector(P.head() - P.tail())# The original mBone in <0,0,0>

            M = N.rotation_difference(n)

            l = M*Vector(B.head() - P.head())
            t = b.tail - b.head
            bhead  = p.head + l
            btail  = bhead  + t
            b.head = bhead
            b.tail = btail
        else:
            print("Bone %s has no Definition in SKELETON" % (b.name) )

    util.ensure_mode_is(omode)

def adjustAttachmentBonesToRig(armobj):
    bones = util.get_modify_bones(armobj)
    boneset = [b for b in bones if b.layers[B_LAYER_ATTACHMENT]]
    S = get_skeleton_from(armobj)

    for b in boneset:
        if b.parent == None: continue
        p = b.parent                   # The mBone of the volume
        n = Vector(p.head - p.tail)    # The mBone in <0,0,0>

        B = S[b.name]                  # The original volume bone descriptor
        if B:
            P = B.parent                   # The original mBone descriptor
            N = Vector(P.head() - P.tail())# The original mBone in <0,0,0>

            M = N.rotation_difference(n)

            l = M*Vector(B.head() - P.head())
            t = Vector((0,0,0.03))

            bhead  = p.head + Vector(l)
            btail  = bhead  + Vector(t)
            b.head = bhead
            b.tail = btail
        else:
            print("Bone %s has no Definition in SKELETON" % (b.name) )

def adjustAvatarCenter(armobj):

    if armobj.mode != 'EDIT':
         raise "adjustAvatarCenter: must be called in edit mode"

    bones = armobj.data.edit_bones

    mPelvis = bones.get('mPelvis')
    if mPelvis:

        for bb in [b for b in bones if b.parent and b.parent.name=="Origin" and b.name[0]=="a"]:
            try:
                bb.head = mPelvis.head
                bb.tail = mPelvis.head + Vector((0,0,0.03))
            except KeyError as e:
                logging.debug(_("KeyError: %s"), e)

        cog = bones.get('COG')
        if cog:
            d = mPelvis.tail - cog.head
            cog.head = mPelvis.tail
            cog.tail += d

        pelvis = bones.get('Pelvis')
        if pelvis:
            set_connect(pelvis, False)
            pelvis.head = mPelvis.head
            pelvis.tail = mPelvis.tail
            pelvisi = bones.get('PelvisInv')
            if pelvisi:
                set_connect(pelvisi, False)
                pelvisi.head = mPelvis.tail
                pelvisi.tail = mPelvis.head
    else:
        log.error("adjustSupportRig: mPelvis bone missing in armature %s. Maybe not an Karaage Rig?" % (armobj.name))
    
def adjustCollarLink(armobj, side):
    if armobj.mode != 'EDIT':
         raise "adjustCollarLink: must be called in edit mode"

    bones = armobj.data.edit_bones
    mNeck = bones.get('mNeck', None)
    mCollar = bones.get('mCollar'+side, None)
    CollarLink = bones.get('CollarLink'+side, None)

    if mNeck and mCollar and CollarLink:
        CollarLink.head = mNeck.head
        CollarLink.tail = mCollar.head
    else:
        log.debug("Armature %s has no %s Collar Link" % (armobj.name, side))

def adjustHipLink(armobj, side):
    if armobj.mode != 'EDIT':
         raise "adjustHipLink: must be called in edit mode"

    bones = armobj.data.edit_bones
    mTorso = bones.get('mTorso',None)
    mHip = bones.get('mHip' + side, None)
    HipLink = bones.get('HipLink' + side, None)

    if mTorso and mHip and HipLink:
        set_connect(HipLink, False, msg="Adjust HipLink")
        HipLink.head = mTorso.head
        HipLink.tail = mHip.head

    else:
        log.debug("Armature %s has no %s Hip Link" % (armobj.name, side))

def getFootPivotRange(bones,side):

    mToe = bones.get('mToe'+side, None)
    mAnkle = bones.get('mAnkle'+side, None)
    if mToe and mAnkle:
        lb = PVector(mToe.head)
        la = mAnkle.head
        lh = PVector((la.x, la.y, lb.z))
        return lb, lh
    return None, None

def adjustFootBall(bones, side, subtype=""):
    lh = lb = None
    bname = 'ik%sFootBall%s' % (subtype, side)
    ikFootBall = bones.get(bname, None)
    if ikFootBall:
        lb, lh = getFootPivotRange(bones, side)
        if lb:
            ikFootBall.head = lb
            ikFootBall.tail = lb + Vector(s2b((0,0,-0.1)))
        else:
            log.info("Armature has no %s Ankle or Toe" % (side))
    else:
        log.info("Armature has no %s" % (bname))
    return lh, lb

def adjustIKToRig(armobj):
    bones = util.get_modify_bones(armobj)

    adjustIKFootToRig(bones, 'Left')
    adjustIKFootToRig(bones, 'Right')

    adjustIKHandToRig(bones, 'Left')
    adjustIKHandToRig(bones, 'Right')

    if armobj.RigProps.RigType == 'EXTENDED':
        adjustIKHindFootToRig(bones, 'Left')
        adjustIKHindFootToRig(bones, 'Right')

    fix_stretch_to(armobj)

def adjustIKFootToRig(bones, side):

    origin = bones.get('Origin')
    Ankle = bones.get('Ankle' + side)
    Knee = bones.get('Knee' + side)

    ikAnkle = bones.get('ikAnkle' + side)
    ikKneeLine = bones.get('ikKneeLine' + side)
    ikKneeTarget = bones.get('ikKneeTarget' + side)

    ikHeel = bones.get('ikHeel'+side)
    ikFootPivot = bones.get('ikFootPivot'+side)
    if ikHeel and ikFootPivot and Ankle:
        d = ikHeel.tail - ikHeel.head
        z = origin.head[2]
        ikHeel.head      = Ankle.head
        ikHeel.head[2]   = z
        ikHeel.tail      = ikHeel.head + d
        ikFootPivot.head = ikHeel.head
        ikFootPivot.tail = ikHeel.tail
    else:
        log.warning("Can not adjust ik for %s Foot (missing ik bones)" % (side) )

    adjustFootBall(bones, side)

    if ikKneeLine and Knee and ikKneeTarget and ikAnkle and Ankle:

        ikAnkle.head = Ankle.head
        ikAnkle.tail = Ankle.tail
        ikAnkle.roll = Ankle.roll

        td = ikKneeTarget.tail - ikKneeTarget.head
        ikKneeTarget.head.z = Knee.head.z
        ikKneeTarget.tail = ikKneeTarget.head + td

        ikKneeLine.head = Knee.head.copy()
        ikKneeLine.tail = ikKneeTarget.head.copy()

    else:
        log.warning("Can not adjust ik for %s Knee (missing ik bones)" % (side) )

def adjustIKHindFootToRig(bones, side):

    origin = bones.get('Origin')
    Ankle = bones.get('HindLimb3' + side)
    Knee = bones.get('HindLimb2' + side)

    ikAnkle = bones.get('ikHindLimb3' + side)
    ikKneeLine = bones.get('ikHindLimb2Line' + side)
    ikKneeTarget = bones.get('ikHindLimb2Target' + side)

    ikHeel = bones.get('ikHindHeel'+side)
    ikFootPivot = bones.get('ikHindFootPivot'+side)
    if ikHeel and ikFootPivot and Ankle:
        d = ikHeel.tail - ikHeel.head
        z = origin.head[2]
        ikHeel.head      = Ankle.head
        ikHeel.head[2]   = z
        ikHeel.tail      = ikHeel.head + d
        ikFootPivot.head = ikHeel.head
        ikFootPivot.tail = ikHeel.tail
    else:
        log.warning("Can not adjust ik for %s Foot (missing ik bones)" % (side) )

    adjustFootBall(bones, side, "Hind")

    if ikKneeLine and Knee and ikKneeTarget and ikAnkle and Ankle:

        ikAnkle.head = Ankle.head
        ikAnkle.tail = Ankle.tail
        ikAnkle.roll = Ankle.roll

        td = ikKneeTarget.tail - ikKneeTarget.head
        ikKneeTarget.head.z = Knee.head.z
        ikKneeTarget.tail = ikKneeTarget.head + td

        ikKneeLine.head = Knee.head.copy()
        ikKneeLine.tail = ikKneeTarget.head.copy()

    else:
        log.warning("Can not adjust ik for %s Knee (missing ik bones)" % (side) )

def adjustIKHandToRig(bones, side):

    Wrist = bones.get('Wrist' + side)
    Elbow = bones.get('Elbow' + side)

    ikWrist = bones.get('ikWrist' + side)
    ikElbowLine = bones.get('ikElbowLine' + side)
    ikElbowTarget = bones.get('ikElbowTarget' + side)

    if ikElbowLine and Elbow and ikElbowTarget and ikWrist and Wrist:

        ikWrist.head = Wrist.head
        ikWrist.tail = Wrist.tail
        ikWrist.roll = Wrist.roll

        td = ikElbowTarget.tail - ikElbowTarget.head
        ikElbowTarget.head.z = Elbow.head.z
        ikElbowTarget.tail  = ikElbowTarget.head + td
        
        ikElbowLine.head = Elbow.head.copy()
        ikElbowLine.tail = ikElbowTarget.head.copy()

    else:
        log.warning("Can not adjust ik for %s hand (missing ik bones)" % (side) )

def SLBoneStructureRestrictStates(armobj):
    bones  = get_structure_bones(armobj)        
    mute_count = len([b for b in bones if b.hide_select])
    all_count = len(bones)
    if mute_count==all_count:
        return 'Disabled', 'Enable'
    if mute_count == 0:
        return 'Enabled', 'Disable'
    return 'Mixed', ''
    
def setSLBoneStructureRestrictSelect(armobj, restrict):
    bones  = get_structure_bones(armobj)
    for bone in bones:
        bone.hide_select     = restrict
        if restrict:
            bone.select      = False
            bone.select_tail = False
            bone.select_head = False
        elif bone.select_tail == True and bone.select_head == True:
            bone.select      = True
    
def getControlledBonePairs(armobj):
    bones  = util.get_modify_bones(armobj)
    bone_pairs = [[bones[b.name[1:]],b] for b in bones if b.name[0]=='m' and b.name[1:] in bones]
    return bone_pairs

def get_structure_bones(armobj):
    bones  = util.get_modify_bones(armobj)
    structure_bones = [b for b in bones if b.layers[B_LAYER_STRUCTURE] and b.name[0:2]!="ik"]
    return structure_bones

def needRigFix(armobj):
    bones = util.get_modify_bones(armobj)
    for b in bones:
        if b.name[0] != 'm':
            continue
        cname = b.name[1:]
        c = bones.get(cname)
        if not c:
            log.warning("Bone %s missing (unexpected)" % (cname))
            continue
        chead = Vector(c.head) if armobj.mode == 'EDIT' else Vector(c.head_local) 
        bhead = Vector(b.head) if armobj.mode == 'EDIT' else Vector(b.head_local) 
        diff = (chead - bhead).magnitude
        if diff > MIN_JOINT_OFFSET:

            return True
    return False

def needPelvisInvFix(armobj, msg="ops"):
    bones = armobj.data.edit_bones if armobj.mode=='EDIT' else armobj.pose.bones
    needFix = False

    try:

        mpelvis = bones.get('mPelvis')
        if not mpelvis:
            return False

        pelvis = bones.get('Pelvis')
        if not pelvis:
            return False

        pelvisi = bones.get('PelvisInv')
        if not pelvisi:
            return False

        cog = bones.get('COG')
        if not cog:
            return False

        f1 = MIN_JOINT_OFFSET < (Vector(pelvisi.tail) - Vector(pelvis.head)).magnitude
        f2 = MIN_JOINT_OFFSET < (Vector(pelvisi.head) - Vector(pelvis.tail)).magnitude
        f3 = MIN_JOINT_OFFSET < (Vector(cog.head) - Vector(pelvis.tail)).magnitude
        f4 = MIN_JOINT_OFFSET < (Vector(mpelvis.head) - Vector(pelvis.head)).magnitude
        f5 = MIN_JOINT_OFFSET < (Vector(mpelvis.tail) - Vector(pelvis.tail)).magnitude

        needFix = f1 or f2 or f3 or f4 or f5

    except Exception as e:
        log.warning("Serious issue with Rig, missing Bone Pelvis,PelvisInv or COG")
        needFix = False # Can't fix actually
        raise e

    return needFix

def matchPelvisInvToPelvis(context, armobj, alignToDeform=False):
    with set_context(context, armobj, 'EDIT'):
        
        bones = armobj.data.edit_bones
        
        mpelvis = bones.get('mPelvis')
        pelvis = bones.get('Pelvis')
        master = mpelvis if alignToDeform else pelvis
        
        pelvisi = bones.get('PelvisInv')
        cog = bones.get('COG')
        
        pelvis.head = master.head.copy()
        pelvis.tail = master.tail.copy()
        mpelvis.head = master.head.copy()
        mpelvis.tail = master.tail.copy()
        
        pelvisi.tail = master.head.copy()
        pelvisi.head = master.tail.copy()
        
        cogdiff = cog.tail - cog.head
        cog.head = pelvis.tail.copy()
        cog.tail = cog.head + cogdiff

        log.warning("Adjusted root bone group using [%s] as master" % master.name)
        log.warning("Pelvis   : t:%s h:%s" % (PVector(pelvis.tail), PVector(pelvis.head) ))
        log.warning("PelvisInv: h:%s t:%s" % (PVector(pelvisi.head), PVector(pelvisi.tail)))
        log.warning("COG      : h:%s t:%s" % (PVector(cog.head), PVector(cog.tail)))

        reset_cache(armobj)

def adjustRigToSL(armobj):
    pairs = getControlledBonePairs(armobj)
    log.debug("adjustRigToSL for %d pairs of armature %s in mode %s" % (len(pairs), armobj.name, armobj.mode))
    for bone, slBone in pairs:
        log.debug("Adjust control Bone [%s] to sl bone [%s]" % (bone.name, slBone.name) )
        bone.head = slBone.head.copy()
        bone.tail = slBone.tail.copy()
        bone.roll = slBone.roll

def adjustSLToRig(armobj):
    pairs = getControlledBonePairs(armobj)
    log.debug("adjustSLToRig for %d pairs of armature %s in mode %s" % (len(pairs), armobj.name, armobj.mode))
    for bone, slBone in pairs:
        log.debug("Adjust slBone [%s] to control bone [%s]" % (slBone.name, bone.name) )
        slBone.head = bone.head.copy()
        slBone.tail = bone.tail.copy()
        slBone.roll = bone.roll

def mesh_uses_collision_volumes(obj):
    volbones = data.get_volume_bones()
    for vg in obj.vertex_groups:
        if vg.name in volbones:
            return True
    return False
    
def armature_uses_collision_volumes(arm):
    volbones = data.get_volume_bones()
    bones = util.get_modify_bones(arm)
    for bone in bones:
        if bone.use_deform and not bone.name.startswith("m") and bone.name in volbones:
            return True
    return False

def is_collision_rig(obj):
    if obj.type == 'MESH':
        return mesh_uses_collision_volumes(obj)
    else:
        return armature_uses_collision_volumes(obj)

def adjustBoneRoll(arm):
    #
    wings = get_bones_from_layers(arm, [B_LAYER_WING, B_LAYER_HAND, B_LAYER_FACE, B_LAYER_TAIL])
    for bone in wings:

        bone.align_roll((0,0,1))
        if bone.name.startswith("HandThumb"):
            deg       = 45 if bone.name.endswith("Left") else -45
            bone.roll += deg * DEGREES_TO_RADIANS

def get_ik_constraint(pose_bones, bone_name, ik_bone_name):
    iks = [con for con in pose_bones[bone_name].constraints if con.type=="IK" and con.subtarget==ik_bone_name]
    if len(iks) == 0:
        log.info("get_ik_constraint: No IK constraint found for bone %s and subtarget %s" % (bone_name, ik_bone_name) )
    return iks[0] if len(iks) > 0 else None
    
def get_ik_influence(pose_bones, bone_name, ik_bone_name):
    try:
        ik = get_ik_constraint(pose_bones, bone_name, ik_bone_name)
        influence = ik.influence if ik else 0
    except:

        influence = 0
    return influence
    
def create_ik_button(row, active, layer):
    if active == None or active.pose == None: return

    pose_bones = active.pose.bones
    text="???"
    try:
        if layer == B_LAYER_IK_LEGS:
            ik = get_ik_influence(pose_bones, "KneeRight", "ikAnkleRight") + get_ik_influence(pose_bones, "KneeLeft", "ikAnkleLeft")
            icon = "FILE_TICK" if ik > 1.9 else "BLANK1"
            text = "IK Legs"
            op = "karaage.ik_legs_enable"
        elif layer == B_LAYER_IK_LIMBS:
            ik = get_ik_influence(pose_bones, "HindLimb2Right", "ikHindLimb3Right") + get_ik_influence(pose_bones, "HindLimb2Left", "ikHindLimb3Left")
            icon = "FILE_TICK" if ik > 1.9 else "BLANK1"
            text = "IK Limbs"
            op = "karaage.ik_limbs_enable"
        elif layer == B_LAYER_IK_ARMS:
            ik = get_ik_influence(pose_bones, "ElbowRight", "ikWristRight") + get_ik_influence(pose_bones, "ElbowLeft", "ikWristLeft")
            icon  = "FILE_TICK" if ik  > 1.9 else "BLANK1"
            text = "IK Arms"
            op   = "karaage.ik_arms_enable"
        elif layer == B_LAYER_IK_HAND:
            row.prop(active.IKSwitches,"Enable_Hands", text='', icon='CONSTRAINT_BONE')
            if active.IKSwitches.Enable_Hands in ['FK', 'GRAB']:
                props = row.operator("karaage.ik_apply", text='', icon='POSE_DATA')
                props.limb='HAND'
                props.symmetry='BOTH'
            return
        else:
            icon = "BLANK1"
    except:
        raise
        icon = "BLANK1"

    icon_value = visIcon(active, layer, type='ik')
    row.prop(active.data, "layers", index=layer, toggle=True, text=text, icon_value=icon_value)
    row.operator(op, text="",icon=icon)

def get_bone_constraint(bone, type, namehint=None):
    if not bone: return None

    candidates = [c for c in bone.constraints if c.type==type]
    if len(candidates) == 0:
        return None

    if len(candidates) == 1:
       return candidates[0]

    if namehint:
        for c in candidates:
            if namehint in c:
                return c

    return candidates[0]

def setEyeTargetInfluence(arm, prep):
    left  = "%sLeft" % prep
    right = "%sRight" % prep

    EyeLeft      = arm.pose.bones.get(left,None)
    EyeRight     = arm.pose.bones.get(right,None)
    EyeLeftCons  = get_bone_constraint(EyeLeft, 'DAMPED_TRACK', namehint='DAMPED_TRACK')
    EyeRightCons = get_bone_constraint(EyeRight, 'DAMPED_TRACK', namehint='DAMPED_TRACK')

    state = arm.IKSwitches.Enable_Eyes if prep == 'Eye' else arm.IKSwitches.Enable_AltEyes
    if state:
        if EyeLeftCons: EyeLeftCons.influence=1
        if EyeRightCons: EyeRightCons.influence=1
    else:
        if EyeLeftCons: EyeLeftCons.influence=0
        if EyeRightCons: EyeRightCons.influence=0

def get_posed_bones(armobj):
    posed_bones = []
    Q0 = Quaternion((1,0,0,0))
    for b in armobj.pose.bones:
        if b.matrix_basis.decompose()[1].angle > 0.001:
            log.warning("Found posed bone %s" % b.name)
            posed_bones.append(b)
    return posed_bones

def set_rotation_limit(bones, state):
    for b in bones:
        for c in b.constraints:
            if c.type =='LIMIT_ROTATION':
                c.influence = 1 if state else 0
                b.use_ik_limit_x = state
                b.use_ik_limit_y = state
                b.use_ik_limit_z = state

def set_bone_rotation_limit_state(arm, state, all=False):
    if all:
        bones = arm.pose.bones
    else:
        bones = [b for b in arm.pose.bones if b.bone.select]

    set_rotation_limit(bones, state)

class KaraageFaceWeightGenerator(bpy.types.Operator):
    bl_idname      = "karaage.face_weight_generator"
    bl_label       = "Generate Face weights"
    bl_description = "Generate Face weights (very experimental)"
    bl_options = {'REGISTER', 'UNDO'}

    focus = FloatProperty(name="Focus", min=0, max=1.5, default=0, description="Bone influence offset (very experimental)")
    all    = BoolProperty(name="All Bones", default=True, description = "Weight All Face Bones except eyes and Tongue" )
    limit  = BoolProperty(name="Limit to 4", default=True, description = "Limit Weights per vert to 4 (recommended)" )
    gain   = FloatProperty(name="Gain", min=0, max=10, default=1, description="Weight factor(level gain)")
    clean  = FloatProperty(name="Clean", min=0, max=1.0, description="Remove weights < this value")
    use_mirror_x = BoolProperty(name="X Mirror", default=False, description = "Use X-Mirror" )
    suppress_implode = BoolProperty(name="Suppress Implode", default=False, description = "Do not move the Bones back after weighting (for demonstration purposes only, please dont use!)" )

    @classmethod
    def poll(self, context):
        obj=context.object
        if obj != None and obj.type == 'MESH':
            arm = util.get_armature(obj)
            return arm != None
        return False

    @staticmethod
    def explode(arm, use_mirror_x, full_armature=False, all_bones=True, focus=0):
        bones=arm.data.bones
        selects = {}
        deforms = {}
        offsets = {}

        if all_bones:
            for b in bones:
                selects[b.name] = b.select
                b.select=False

        bones = {b.name:b for b in bones if full_armature or b.name.startswith('mFace') or b.name in EXTRABONES }
        for bname, b in bones.items():
            if bname != 'mHead':

                h = b.head_local
                t = b.tail_local
                d = t - h
                f = focus
                offset = Vector((d[0]*f, d[1]*f, d[2]*f))
                b.tail_local  += offset
                b.head_local  += offset
                offsets[bname]=offset

            b.select = b.select or all_bones
            if b.select and use_mirror_x and not all_bones:
                mirror_name = util.get_mirror_name(bname)
                if mirror_name:
                    bones[mirror_name].select = True

            if bname in NONDEFORMS:
                deforms[b.name]=b.use_deform
                b.use_deform = False
        return selects, deforms, offsets

    @staticmethod
    def implode(arm, full_armature, selects, deforms, offsets):
        bones=arm.data.bones
        for name, select in selects.items():
            bones[name].select = select

        for bname, offset in offsets.items():
            b = bones[bname]
            b.head_local  -= offset
            b.tail_local  -= offset

            if b.name in NONDEFORMS and b.name in deforms:
                b.use_deform = deforms[b.name]

    @staticmethod
    def store_parameters(arm, focus, gain, clean):
        bones=[b for b in util.get_modify_bones(arm) if b.select]
        for b in bones:
            b['focus']  = focus
            b['gain']   = gain
            b['clean']  = clean

    def invoke(self, context, event):
        self.use_mirror_x = context.object.data.use_mirror_x
        return self.execute(context)

    def execute(self, context):
        return KaraageFaceWeightGenerator.generate(context, self.use_mirror_x, self.all, self.focus, self.gain, self.clean, self.limit, self.suppress_implode)

    @staticmethod
    def generate(context, use_mirror_x, all, focus, gain, clean, limit, suppress_implode):

        obj=context.object
        arm = util.get_armature(obj)
        use_full_armature = not 'karaage' in arm

        omode = util.ensure_mode_is("OBJECT")

        bpy.context.scene.objects.active = arm
        arm.data.pose_position="REST"

        amode = util.ensure_mode_is("OBJECT")
        selects, deforms, offsets = KaraageFaceWeightGenerator.explode(arm, use_mirror_x, full_armature=use_full_armature, all_bones=all, focus=focus)
        util.ensure_mode_is("POSE")

        bpy.context.scene.objects.active = obj
        util.ensure_mode_is("WEIGHT_PAINT")
        bpy.ops.paint.weight_from_bones()

        bpy.ops.object.vertex_group_levels(group_select_mode='BONE_SELECT', gain=gain)
        bpy.ops.object.vertex_group_clean(group_select_mode='BONE_SELECT', limit=clean)

        if limit:
            bpy.ops.object.vertex_group_limit_total(group_select_mode='BONE_SELECT')

        bpy.context.scene.objects.active = arm

        KaraageFaceWeightGenerator.store_parameters(arm, focus, gain, clean)

        if suppress_implode:
            util.ensure_mode_is("EDIT")
        else:

            util.ensure_mode_is("OBJECT")
            KaraageFaceWeightGenerator.implode(arm, use_full_armature, selects, deforms, offsets)        

        util.ensure_mode_is(amode)
        bpy.context.object.data.pose_position="POSE"

        bpy.context.scene.objects.active = obj
        util.ensure_mode_is(omode)

        return{'FINISHED'}

def get_islands(ob, minsize=1):
    island_id    = 0
    island_map   = {}
    islands      = {}

    def merge_islands(parts):
        iterparts = iter(parts)
        first= next(iterparts)
        for part in iterparts:
            src  = islands[part]
            islands[first].update(src)
            for key in src:
                island_map[key] = first
            islands[part].clear()
        return first

    for poly in ob.data.polygons:
        parts = sorted({island_map[index] for index in poly.vertices if index in island_map})

        if len(parts) > 0:
            id = merge_islands(parts)
        else:
            id = island_id
            islands[id] = {}
            island_id  += 1

        island = islands[id]
        for vert in poly.vertices:
            island_map[vert] = id
            island[vert]=True
            
    return [island for island in islands.values() if len(island) >= minsize]

def select_island(ob, minsize=1):
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.reveal()
    ob.update_from_editmode()
    
    islands = get_islands(ob, minsize)
    active_island = None
    for island in islands:
        if (active_island == None or len(island) > len(active_island)) and len(island) >= minsize:
            active_island = island

    if active_island:
        log.info("Found island of size %d" % len(active_island))
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        for index in active_island:
            ob.data.vertices[index].select = True
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    return active_island
    
def convert_weight_groups(armobj, obj, armature_type=SLMAP):
    for group in obj.vertex_groups:
        tgt_name = map_sl_to_Karaage(group.name, type=armature_type, all=True)
        if tgt_name and tgt_name in armobj.pose.bones:
            gname = 'm' + tgt_name
            if gname not in armobj.pose.bones:
                gname = tgt_name
            if gname in obj.vertex_groups:
                util.merge_weights(obj, group, obj.vertex_groups[gname])
                obj.vertex_groups.remove(group)
            else:
                group.name = gname
        else:
            log.info("convert_weight_groups: Ignore Group %s (not a %s group)" % (group.name, armature_type) )

class KaraageFromManuelLab(bpy.types.Operator):

    bl_idname = "karaage.convert_from_manuel_lab"
    bl_label = "Convert to Karaage"
    bl_description = "Store current Slider settings in last selected Preset"

    def convert_weights(self, context, children):
        log.info("Converting %d children from Manuel_Lab to Karaage..." % len(children) )
        for ob in children:
            log.info("Converting %s" % ob.name)

            if ob.type == 'MESH':
               log.info("ob is a MESH")
               arm = util.get_armature(ob)
               if arm and arm.get('karaage',None) is None:
                   log.info("ob ARMATURE %s" % arm.name)
                   bpy.context.scene.objects.active = ob
                   bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                   for mod in [ mod for mod in ob.modifiers if mod.type=='ARMATURE']:
                       log.info("Removed Modifier %s" % mod.name)
                       bpy.ops.object.modifier_apply(modifier=mod.name)
                   context.scene.objects.unlink(arm)
                   log.info("deleted %s" % arm.name)
                   bpy.data.objects.remove(arm)

            convert_weight_groups(arm, obj, armature_type=MANUELMAP)

    def execute(self, context):
        active = bpy.context.active_object
        children = util.get_meshes(context, type='MESH', select=True, visible=True, hidden=False)

        self.convert_weights(context, children)

        karaages = [arm for arm in util.get_meshes(context, type='ARMATURE', select=True, visible=True, hidden=False) if arm.get('karaage',None)]
        if len(karaages) == 0:
            karaages = [arm for arm in util.get_meshes(context, type='ARMATURE', select=None, visible=True, hidden=False) if arm.get('karaage',None)]

        if len(karaages) == 1:
            bpy.context.scene.objects.active = karaages[0]
            select = active.select 
            active.select = True
            bpy.ops.karaage.store_bind_data()
            context.scene.MeshProp.skinSourceSelection = 'NONE'

            from . import mesh
            mesh.parent_armature(self,
                context, karaages[0],
                type='NONE',
                clear = True,
                selected=False,
                weight_eye_bones=False,
                enforce_meshes = False )

            bpy.ops.karaage.alter_to_restpose()
            active.select = select

        bpy.context.scene.objects.active = active
        return {'FINISHED'}
import time

def fix_manuel_object_name(ob):

    if not (ob.data and ob.data.vertices and len(ob.data.vertices) > 0):
        log.error("Found issues with MANUELLAB object %s" % (ob.name) )

    vcount = len(ob.data.vertices)

    try:
        name, part = ob.name.split('.')
    except:
        name= ob.name
        part = 'Brows'
    side = ''
    if   vcount == 114:   part = "Tongue"
    elif vcount == 3475:  part = "Teeth"
    elif vcount  > 10000: part = "Body"
    else:
        side = "Right" if ob.data.vertices[0].co.x < 0 else "Left"
        if   vcount == 286: part = "Eyeball"
        elif vcount == 346: part = "Iris"
        else: side = ''
    if part != '':
        ob.name = "%s.%s%s" % (name,part,side)
    ob.name = ob.name.replace("humanoid_human","avatar_")

def karaage_split_manuel(context, active, island_min_vcount):
    omode  = active.mode
    mesh_select_mode = util.set_mesh_select_mode((True, False, False))
    running = True
    sepcount = 0
    while running:
        context.scene.objects.active = active
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        island = select_island(active, minsize=island_min_vcount)
        if not island:
            break

        if sepcount == 0:
            if len(island) == len(active.data.vertices):
                log.warning("The Mesh %s has no islands, maybe not a MANUELLAB character?" % active.name)
                break

        util.progress_update(100, absolute=False)

        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        sepcount += 1

    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode=omode, toggle=False)
    util.set_mesh_select_mode(mesh_select_mode)
    return sepcount

class KaraageMergeWeights(bpy.types.Operator):

    bl_idname = "karaage.merge_weights"
    bl_label = "Merge weights of selected to active"
    bl_description = "Try automatic weight from bones using islands"

    @classmethod
    def poll(self, context):
        return context.object.type == 'MESH'

    def convert_weight_groups(self, obj, active, selected):
        active_group = obj.vertex_groups.get(active.name,None)
        if not active_group:
            active_group = obj.vertex_groups.new(active.name)

        for bone in selected:
            bgroup = obj.vertex_groups[bone.name]
            util.merge_weights(obj, bgroup, active_group)
            obj.vertex_groups.remove(bgroup)

        return active_group

    def execute(self, context):
        obj    = context.object
        arm    = util.get_armature(obj)
        bones  = util.get_modify_bones(arm)
        active_bone = bones.active
        
        selected = [b for b in bones if b.select and not b==active_bone and b.name in obj.vertex_groups]
        
        active_group = self.convert_weight_groups(obj, active_bone, selected)
        active_bone.select = True
        bpy.ops.object.mode_set(toggle=True) # Enforce display of updated weight group in edit mode
        bpy.ops.object.mode_set(toggle=True)
        return {'FINISHED'}

def get_bone_recursive(posebone, ii, stopname='Pelvis'):
    result = posebone    
    if result.name != stopname:
        for i in range(0,ii):
            result = result.parent
            if result.name == stopname:
                break
    return result

class EditKaraageMeshPopup(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "karaage.edit_karaage_mesh"
    bl_label = "Edit system mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        width = 400 * bpy.context.user_preferences.system.pixel_size
        status = context.window_manager.invoke_props_dialog(self, width=width)
        return status

    @classmethod
    def poll(self, context):
        if not context:
            return False
        ob = context.object
        if not ob:
            return False
        return True

    def draw(self, context):
        layout = self.layout

        col   = layout.column()
        col.label("Karaage Object [%s] should not be edited!" % (context.object.name), icon='ERROR' )
        col.label("")
        col.label("Please use the Freeze Tool to create an editable copy")
        col.label("You find the Freeze tool in the Tool Shelf:")
        col.label("")
        col.label("Karaage Tab --> Tools Panel --> Freeze Shape section")

        props = util.getAddonPreferences()
        col.prop(props,"rig_edit_check",text='Always check for System Meshes.')

    def execute(self, context):

        return {'FINISHED'}

def setIKTargetOrientation(obj, parent, child, target, line):

    try:
        pbones = obj.pose.bones
        dbones = obj.data.bones

        ph = pbones[parent].head
        ch = pbones[child].head
        th = pbones[target].head
        pline = pbones[line]
        dline = dbones[line]

        tm = (dbones[target].head_local - dbones[child].head_local).magnitude
        
        vrot = (th-ch).cross(ph-ch) # The rotation axis
        vfin = ch + (ph-ch).cross(vrot).normalized()*tm

        pbones[target].matrix.translation = vfin        

    except KeyError:
        log.error("Can not calculate POle Target location (bones missing)")

def setIKPoleboneOrientation(context, obj, ankle, ikAnkle, ikHeel, ikKneeTarget):
    try:
        M1 = obj.pose.bones[ankle].matrix
        M2 = obj.pose.bones[ikAnkle].matrix
        M3 = obj.pose.bones[ikHeel].matrix
        m = obj.pose.bones[ikKneeTarget].matrix
        t = m.to_translation()

        #
        con = obj.pose.bones[ikKneeTarget].constraints.new('LIMIT_LOCATION')
        con.owner_space = 'POSE'
        con.min_x = con.max_x = t.x
        con.min_y = con.max_y = t.y
        con.min_z = con.max_z = t.z
        con.use_min_x = con.use_max_x = True
        con.use_min_y = con.use_max_y = True
        con.use_min_z = con.use_max_z = True

        obj.pose.bones[ikHeel].matrix = M1*M2.inverted()*M3

        context.scene.update()

        obj.pose.bones[ikKneeTarget].matrix = m

        obj.pose.bones[ikKneeTarget].constraints.remove(con)
    except KeyError: pass

def setIKElbowTargetOrientation(context, obj, side):
    parent = 'Shoulder' + side
    child = 'Elbow' + side
    target = 'ikElbowTarget' + side
    line = 'ikElbowLine' + side

    setIKTargetOrientation(obj, parent, child, target, line)

def setIKKneeTargetOrientation(context, obj, side):
    parent = 'Hip' + side
    child = 'Knee' + side
    target = 'ikKneeTarget' + side
    line = 'ikKneeLine' + side

    setIKTargetOrientation(obj, parent, child, target, line)

def setIKHindLimb2TargetOrientation(context, obj, side):
    parent = 'HindLimb1' + side
    child = 'HindLimb2' + side
    target = 'ikHindLimb2Target' + side
    line = 'ikHindLimb2Line' + side
    setIKTargetOrientation(obj, parent, child, target, line)

def setIKAnkleOrientation(context, obj, side):
    ankle        = 'Ankle' + side
    ikAnkle      = 'ik' + ankle
    ikHeel       = 'ikHeel' + side
    ikKneeTarget = 'ikKneeTarget' + side
    setIKPoleboneOrientation(context, obj, ankle, ikAnkle, ikHeel, ikKneeTarget)

def setIKHindLimb3Orientation(context, obj, side):
    ankle        = 'HindLimb3' + side
    ikAnkle      = 'ik' + ankle
    ikHeel       = 'ikHindLimb2' + side
    ikKneeTarget = 'ikHindLimb2Target' + side
    setIKPoleboneOrientation(context, obj, ankle, ikAnkle, ikHeel, ikKneeTarget)

def setIKWristOrientation(context, obj, side):
    wrist         = 'Wrist'         + side
    ikWrist       = 'ik' + wrist
    ikElbowTarget = 'ikElbowTarget' + side

    try:
        M = obj.pose.bones[wrist].matrix
        m = obj.pose.bones[ikElbowTarget].matrix
        t = m.to_translation()

        con = obj.pose.bones[ikElbowTarget].constraints.new('LIMIT_LOCATION')
        con.owner_space = 'POSE'
        con.min_x = con.max_x = t.x
        con.min_y = con.max_y = t.y
        con.min_z = con.max_z = t.z
        con.use_min_x = con.use_max_x = True
        con.use_min_y = con.use_max_y = True
        con.use_min_z = con.use_max_z = True

        obj.pose.bones[ikWrist].matrix = M

        context.scene.update()

        obj.pose.bones[ikElbowTarget].matrix = m

        obj.pose.bones[ikElbowTarget].constraints.remove(con)
    except KeyError:
        print ("Key error...")
        pass

def apply_ik_orientation(context, armature):

    bones = set([b.name for b in armature.data.bones if b.select])
    hasLLegBones  = not bones.isdisjoint(LLegBones)
    hasRLegBones  = not bones.isdisjoint(RLegBones)
    hasLArmBones  = not bones.isdisjoint(LArmBones)
    hasRArmBones  = not bones.isdisjoint(RArmBones)
    hasLHindBones = not bones.isdisjoint(LHindBones)
    hasRHindBones = not bones.isdisjoint(RHindBones)
    hasLPinchBones = not bones.isdisjoint(LPinchBones)
    hasRPinchBones = not bones.isdisjoint(RPinchBones)
    hasGrabBones  = not bones.isdisjoint(GrabBones)

    if hasLArmBones:
        setIKWristOrientation(context, armature, 'Left')
        setIKElbowTargetOrientation(context, armature, 'Left')
    if hasRArmBones:
        setIKWristOrientation(context, armature, 'Right')
        setIKElbowTargetOrientation(context, armature, 'Right')
    if hasLLegBones:
        setIKAnkleOrientation(context, armature, 'Left')
        setIKKneeTargetOrientation(context, armature, 'Left')
    if hasRLegBones:
        setIKAnkleOrientation(context, armature, 'Right')
        setIKKneeTargetOrientation(context, armature, 'Right')
    if hasLHindBones:
        setIKHindLimb3Orientation(context, armature, 'Left')
        setIKHindLimb2TargetOrientation(context, armature, 'Left')
    if hasRHindBones:
        setIKHindLimb3Orientation(context, armature, 'Right')
        setIKHindLimb2TargetOrientation(context, armature, 'Right')

def copy_pose_from_armature(context, srcarm, tgtarm, all=True):

    def matches_filter(name,filter):
        if filter:
            for key in filter:
                if key in name:
                    return True
        return False

    def bones_in_hierarchical_order(arm, roots=None, bone_names=None, filter=None):
        if not bone_names:
            bone_names = []
        if not roots:
            roots = [b for b in arm.data.bones if b.parent == None]
        for root in [n for n in roots]:
            if not matches_filter(root.name, filter):
                bone_names.append(root.name)
            if root.children:
                bones_in_hierarchical_order(arm, root.children, bone_names, filter=filter)
        return bone_names

    active = context.scene.objects.active
    context.scene.objects.active = tgtarm
    src_bones = srcarm.pose.bones
    tgt_bones = tgtarm.pose.bones
    names  = bones_in_hierarchical_order(tgtarm, filter=['ik', 'Link'])
    setSLBoneLocationMute(None, context, True, 'ALL')
    setSLBoneRotationMute(None, context, True, 'ALL')
    set_bone_rotation_limit_state(tgtarm, False, all=True)
    for name in names:
        tgt = tgt_bones[name]
        src = src_bones.get(name,None)
        if src and (tgt.bone.select or all):
                tgt.matrix = src.matrix
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.mode_set(mode='POSE')

    context.scene.objects.active = active

class FocusOnBone(bpy.types.Operator):
    """selects a bone and set focus on it (view selected)"""
    bl_idname = "karaage.focus_on_selected"
    bl_label = "Focus Bone"
    bl_options = {'REGISTER', 'UNDO'}

    bname= StringProperty(
        name        = 'Bone',
        description = 'A Bone to put focus on'
    )

    @classmethod
    def poll(self, context):
        ob = context.object
        return ob.type=='ARMATURE'

    def execute(self, context):
        armobj = context.object
        bones  = armobj.data.bones
        dbone  = bones.get(self.bname, None)

        if dbone:
            util.set_bone_select_mode(armobj, True, boneset=[dbone.name], additive=False)
            cloc = context.scene.cursor_location.copy()
            context.scene.cursor_location = dbone.head_local + armobj.matrix_local.translation
            ctx = util.find_view_context(context)
            if ctx:
                bpy.ops.view3d.view_center_cursor(ctx)

        return {'FINISHED'}

class DrawOffsets(bpy.types.Operator):
    '''Draw offsets from current rig to SL Default Rig (Using the Grease Pencil)
    
Please use the Grease Pencil tools in the 'N' properties sidebar
to edit or remove the lines when you no longer need them'''    

    bl_idname = "karaage.draw_offsets"
    bl_label = "Draw Joint Offsets"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        ob = context.object
        return ob and ob.type=='ARMATURE'

    def execute(self, context):
        armobj = context.object
        omode = util.ensure_mode_is('OBJECT')
        pbones  = armobj.pose.bones
        dbones  = armobj.data.bones

        reset_cache(armobj)

        for pbone in pbones:
            dbone = pbone.bone
            if util.bone_is_visible(armobj, dbone):

                slHead, slTail = get_sl_bindposition(armobj, dbone, use_cache=True)       # Joint: SL Restpose location
                cuHead, cuTail = get_custom_bindposition(armobj, dbone, use_cache=True)   # Joint: With Joint offsets added
                if slHead and cuHead:

                    slHead = Vector(slHead)
                    cuHead = Vector(cuHead)
                    slTail = Vector(slTail)
                    cuTail = Vector(cuTail)
                    util.gp_draw_line(context, slHead,        cuHead,        lname='offsets', color_index=pbone.bone_group_index, dots=40)
                    util.gp_draw_line(context, slHead+slTail, cuHead+cuTail, lname='offsets', color_index=pbone.bone_group_index, dots=40)

                if cuHead and cuTail:

                    util.gp_draw_line(context, cuHead, cuHead + Vector(cuTail), lname='user-skeleton', color_index=pbone.bone_group_index)

                if slHead and slTail:

                    util.gp_draw_line(context, slHead, slHead + Vector(slTail), lname='sl-skeleton', color_index=pbone.bone_group_index)

        return {'FINISHED'}

def armatureAsDictionary(armobj):
    context = bpy.context
    active  = context.scene.objects.active
    context.scene.objects.active = armobj
    amode = armobj.mode
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)

    dict = {}
    names = util.Skeleton.bones_in_hierarchical_order(armobj, order='TOPDOWN')
    for name in names:
        bone = armobj.data.edit_bones[name]
        dict[name] = [bone.head, bone.tail - bone.head, bone.roll]

    bpy.ops.object.mode_set(mode=amode, toggle=False)
    context.scene.objects.active = active
    return dict

def matches_filter(name, filter):
    if filter:
        for key in filter:
            if key in name:
                return True
    return False

def bones_in_hierarchical_order(armobj, roots=None, bone_names=None, filter=None):
    if not bone_names:
        bone_names = []
    if not roots:
        roots = [b for b in armobj.data.bones if b.parent == None]
    for root in roots:
        if not matches_filter(root.name, filter):
            if True:#root.name[0]=='m' or root.name[0]=='a' or "m%s" % (root.name) in armobj.data.bones:
                bone_names.append(root.name)
        if root.children:
            bone_names = bones_in_hierarchical_order(armobj, root.children, bone_names, filter=filter)
    return bone_names

def armatureFromDictionary(context, armobj, dict):
    print("armatureFromDictionary: Get armature data for Armature [%s] from dictionary" % armobj.name)
    sceneProps = context.scene.SceneProp
    apply_as_restpose = sceneProps.armature_preset_apply_as_Restpose
    all_bones         = sceneProps.armature_preset_apply_all_bones
    adjust_tails      = sceneProps.armature_preset_adjust_tails
    active  = context.scene.objects.active
    amode   = active.mode if active else None
    if active:
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    context.scene.objects.active = armobj
    omode = armobj.mode
    bone_names = bones_in_hierarchical_order(armobj, roots=None, bone_names=None, filter=['ik'])

    bpy.ops.object.mode_set(mode='POSE', toggle=False)
    if apply_as_restpose:
        print("armatureFromDictionary: Apply dictionary to %s as rig change to %d bones" % (armobj.name, len(bone_names)))

    else:
        print("armatureFromDictionary: Apply dictionary to %s by posing %d bones" % (armobj.name, len(bone_names)))

        con_states = []

    setSLBoneLocationMute(None, context, True, 'CONTROLLED', filter='Link')
    setSLBoneRotationMute(None, context, True, 'CONTROL',    filter='Link')
    set_bone_rotation_limit_state(armobj, False, all=True)

    pbones  = armobj.pose.bones
    cbones = util.getControlBones(armobj, filter='Link')
    parent_offset = {}

    print("armatureFromDictionary: Set the pose for %d bones" % (len(bone_names)) )
    for bname in bone_names:
        if bname in SLVOLBONES:
            continue # This is for testing only. it looks like some data is applied twice when Volume bones are affected...

        val = dict.get(bname)
        if val:
            head = val[0]
            tail = val[1]
            pbone = pbones.get(bname, None)

            selected = all_bones or (pbone and pbone.bone.select)
            if pbone and selected:
                hs = pbone.bone.hide_select
                pbone.bone.hide_select=False
                matrix = pbone.matrix.to_3x3()
                dv     = pbone.tail - pbone.head
                dq     = dv.rotation_difference(tail)
                matrix.rotate(dq)
                matrix = matrix.to_4x4()
                matrix.translation = head
                pbone.matrix = matrix
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.mode_set(mode='POSE')

                if adjust_tails and (bname in cbones.keys() or 'Link' in bname) and not apply_as_restpose:
                    pmag = Vector(pbone.head - pbone.parent.head).magnitude
                    parent_offset[bname] = pmag
                pbone.bone.hide_select=hs

    print("armatureFromDictionary: Set original armature mode [%s]" % (amode))
    bpy.ops.object.mode_set(mode=amode, toggle=False)

    if apply_as_restpose:
        print("armatureFromDictionary: Apply as Restpose")
        bpy.ops.karaage.armature_bake(handleBakeRestPoseSelection='ALL', apply_armature_on_snap_rig=True, adjust_stretch_to=True, adjust_pole_angles=True)
    elif adjust_tails:
        print("armatureFromDictionary: Fix bone tails to match Bone lengths")
        bpy.ops.object.mode_set(mode='EDIT')
        ebones = armobj.data.edit_bones

        for key in bone_names:
            pmag = parent_offset.get(key)
            if pmag:
                ebone = ebones[key]
                eparent = ebone.parent
                if 'Wrist' in eparent.name:
                    continue

                evec = Vector(eparent.tail - eparent.head).normalized()
                if pmag < 0.0000001:
                    print("armatureFromDictionary: Bone parent %s in armature %s too short for calculation" % (ebone.parent.name, armobj.name) )
                else:
                    eparent.tail = eparent.head + evec*pmag

                    mbone = ebones.get('m'+eparent.name)
                    if mbone:
                        mbone.tail = eparent.tail

    bpy.ops.object.mode_set(mode='OBJECT')
    print("armatureFromDictionary: Unmute rotation")
    bpy.ops.object.mode_set(mode=omode)
    context.scene.objects.active = active
    bpy.ops.object.mode_set(mode=amode)
    print("armatureFromDictionary: end.")

def autosnap_bones(armobj, snap_control_to_rig=False):
    ebones = armobj.data.edit_bones
    for dbone in [b for b in ebones if b.name[0] == 'm' and b.name[1:] in ebones]:

        cbone = ebones.get(dbone.name[1:])

        master = dbone if snap_control_to_rig else cbone
        slave  = dbone if master == cbone else cbone

        slave.head = master.head
        slave.tail = master.tail
        slave.roll = master.roll

def add_armature_preset(context, filepath):
    armobj = util.get_armature(context.object)
    pbones = armobj.pose.bones

    file_preset = open(filepath, 'w')
    file_preset.write(
    "import bpy\n"
    "import karaage\n"
    "from karaage import shape, util, rig\n"
    "from mathutils import Vector, Matrix\n"
    "\n"
    "context=bpy.context\n"
    "armobj = util.get_armature(context.object)\n"
    "print ('Armature Preset:Upload into [%s]' % (armobj.name) )"
    "\n"
    )
    dict = armatureAsDictionary(armobj)
    file_preset.write("dict=" + str(dict) + "\n")
    file_preset.write("rig.armatureFromDictionary(context, armobj, dict)\n")
    file_preset.close()

class AVASTAR_MT_armature_presets_menu(Menu):
    bl_idname = "karaage_armature_presets_menu"
    bl_label  = "Armature Presets"
    bl_description = "Armature Presets (bone configurations)\nStore the editbone matrix values for a complete Armature\nThis can later be used\n\n- as Restpose template to setup other Armatures\n- as pose template for posing another armature."
    preset_subdir = os.path.join("karaage","armatures")
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset

class KaraageAddPresetArmature(AddPresetBase, Operator):
    bl_idname = "karaage.armature_presets_add"
    bl_label = "Add Armature Preset"
    bl_description = "Create new Preset from current Rig"
    preset_menu = "karaage_armature_presets_menu"

    preset_subdir = os.path.join("karaage","armatures")

    def invoke(self, context, event):
        print("Create new Preset...")
        return AddPresetBase.invoke(self, context, event)

    def add(self, context, filepath):
        add_armature_preset(context, filepath)

class KaraageUpdatePresetArmature(AddPresetBase, Operator):
    bl_idname = "karaage.armature_presets_update"
    bl_label = "Update Armature Preset"
    bl_description = "Store current Slider settings in last selected Preset"
    preset_menu = "karaage_armature_presets_menu"
    preset_subdir = os.path.join("karaage","armatures")

    def invoke(self, context, event):
        self.name = bpy.types.karaage_armature_presets_menu.bl_label
        print("Updating Preset", self.name)
        return self.execute(context)

    def add(self, context, filepath):
        add_armature_preset(context, filepath)

class KaraageRemovePresetArmature(AddPresetBase, Operator):
    bl_idname = "karaage.armature_presets_remove"
    bl_label = "Remove Armature Preset"
    bl_description = "Remove last selected Preset from the list"
    preset_menu = "karaage_armature_presets_menu"
    preset_subdir = os.path.join("karaage","armatures")

def getActiveArmature(context):
    active = context.active_object
    if not active:
        return None, None
    if  active.type == "ARMATURE":
        armobj = active
    else:
        armobj = active.find_armature()
    return active, armobj

def setSLBoneRotationMute(operator, context, mute, selection, filter=None, with_reconnect=True):
    active, armobj = getActiveArmature(context)
    if armobj is None:
        if operator:
            operator.report({'WARNING'},_("Active Object %s is not attached to an Armature")%active.name)
        return
    else:
        armature_mode = armobj.mode

        context.scene.objects.active = armobj
        bpy.ops.object.mode_set(mode='POSE')
        locked_bone_names = []

        deformBones = get_pose_bones(armobj, selection, filter)
        Bones = data.get_reference_boneset(armobj)
        
        for sb in Skeleton.bones_in_hierarchical_order(armobj, order='TOPDOWN'):

            bone = deformBones.get(sb)
            if not bone:
                continue

            rcs = [c for c in bone.constraints if c.type=='COPY_ROTATION']
            if len(rcs) > 0:
                for rc in rcs:
                    rc.mute = True
                    try:

                        cname = bone.name[1:]
                        if cname in armobj.pose.bones:
                            cbone = armobj.pose.bones[cname]
                            armobj.update_tag({'DATA'})
                            context.scene.update()                            
                            if mute:
                                bone.matrix = cbone.matrix
                            else:
                                cbone.matrix = bone.matrix

                    except:
                        print(traceback.format_exc())
                        pass
                    rc.mute = mute

                lcs = [c for c in bone.constraints if c.type=='COPY_LOCATION']
                if len(lcs) > 0:
                    for con in lcs:
                        if mute:
                            con.target_space = 'LOCAL'
                            con.owner_space = 'LOCAL'
                        else:
                            con.target_space = 'WORLD'
                            con.owner_space = 'WORLD'

            if with_reconnect:
                locked_bone_names.append(bone.name)

        bpy.ops.object.mode_set(mode='EDIT')
        disconnect_errors = 0
        for name in locked_bone_names:
            try:
                bone = armobj.data.edit_bones[name]
                set_connect(bone, Bones[name].connected if not mute else False, "setSLBoneRotationMute")
            except:
                disconnect_errors += 1
                if disconnect_errors < 10:
                    print("Can not modify rotation lock of bone [%s] " % (name) )
                    raise
        if disconnect_errors >9:
            print("Could not modify %d more bone rotation locks from %s" % (disconnect_errors-10, armobj.name) )

        bpy.ops.object.editmode_toggle()
        bpy.ops.object.mode_set(mode=armature_mode)
        bpy.context.scene.objects.active = active

def setSLBoneLocationMute(operator, context, mute, selection, filter=None):
    active, armobj = getActiveArmature(context)
    if armobj is None:
        if operator:
            operator.report({'WARNING'},_("Active Object %s is not attached to an Armature")%active.name)
        return
    else:
        armature_mode = armobj.mode

        context.scene.objects.active = armobj
        bpy.ops.object.mode_set(mode='POSE')
        locked_bone_names = []

        pose_bones = get_pose_bones(armobj, selection, filter)
        Bones = data.get_reference_boneset(armobj)
        for bone in [ b for b in pose_bones.values() if b.name.startswith('m') or (filter and filter in b.name)]:
            lcs = [c for c in bone.constraints if c.type=='COPY_LOCATION']
            if len(lcs) > 0:
                cname = bone.name[1:]
                try:
                    cbone = armobj.pose.bones[cname]

                    targetless_iks = [c for c in cbone.constraints if c.type=='IK' and c.target==None]
                except:
                    cbone = None
                    targetless_iks = []

                if not mute:
                    for rc in lcs:

                        rc.mute = mute

                for ikc in targetless_iks:
                    ikc.influence = 0.0 if mute else 1.0

                try:

                    bone.matrix = cbone.matrix
                    locked_bone_names.append(cbone.name)
                    locked_bone_names.append(bone.name)

                except:

                    pass
            if filter and filter in bone.name:
                locked_bone_names.append(bone.name)

        bpy.ops.object.mode_set(mode='EDIT')
        disconnect_errors = 0
        for name in locked_bone_names:
            try:
                bone = armobj.data.edit_bones[name]
                set_connect(bone, Bones[name].connected if not mute else False, "setSLBoneLocationMute")

                if not Bones[name].connected:
                    pbone = armobj.pose.bones[name]
                    pbone.lock_location[0] = not mute
                    pbone.lock_location[1] = not mute
                    pbone.lock_location[2] = not mute

            except:
                disconnect_errors += 1
                if disconnect_errors < 10:
                    print("Can not modify connect of bone [%s] " % (name) )
                    raise
        if disconnect_errors >9:
            print("Could not modify %d more location locks from %s" % (disconnect_errors-10, armobj.name) )

        bpy.ops.object.editmode_toggle()
        bpy.ops.object.mode_set(mode=armature_mode)
        context.scene.objects.active = active

def setSLBoneVolumeMute(operator, context, mute, selection, filter=None):
    active, armobj = getActiveArmature(context)
    if armobj is None:
        if operator:
            operator.report({'WARNING'},_("Active Object %s is not attached to an Armature")%active.name)
        return
    else:
        armature_mode = armobj.mode
        context.scene.objects.active = armobj
        bpy.ops.object.mode_set(mode='POSE')

        pose_bones = armobj.pose.bones
        for name in [ b for b in SLVOLBONES if not filter or (filter and filter in b.name)]:
            bone = pose_bones.get(name)
            if not bone:
                continue

            bone.lock_location[0] = mute
            bone.lock_location[1] = mute
            bone.lock_location[2] = mute

        bpy.ops.object.editmode_toggle()
        bpy.ops.object.mode_set(mode=armature_mode)
        context.scene.objects.active = active

def get_pose_bones(armobj, selection, filter=None, ordered=False):
    pose_bones = []
    result = {}
    active = armobj.data.bones.active
    if active:
        name = active.name
        if name[0] != 'm':
            name = 'm' + name
        try:
            active = armobj.pose.bones[name]
        except:
            active = None
    if selection == 'SELECTION':
        pose_bones = [armobj.pose.bones[b.name] for b in util.getVisibleSelectedBones(armobj)]
    elif selection == 'VISIBLE':
        pose_bones = [armobj.pose.bones[b.name] for b in util.getVisibleBones(armobj)]
    elif selection == 'SIMILAR':
        if active:
            gindex = active.bone_group_index
            pose_bones = [b for b in bpy.context.object.pose.bones if b.bone_group_index==gindex]
    elif selection == 'CONTROL':
        return util.getControlBones(armobj, filter)
    elif selection == 'LINK':
        return util.getLinkBones(armobj)
    elif selection == 'CONTROLLED':
        return util.getControlledBones(armobj, filter)
    elif selection == 'DEFORM':
        return util.getDeformBones(armobj)
    else:
        pose_bones = armobj.pose.bones

    for b in pose_bones:
        try:
            if b.name[0]!='m':
                b = armobj.pose.bones['m'+b.name]
            result[b.name]=b
        except:
            pass
    return result

def MuteArmaturePoseConstraints(context, armobj):
    active = context.object
    armature_mode = armobj.mode
    context.scene.objects.active = armobj
    bpy.ops.object.mode_set(mode='OBJECT')

    names = util.Skeleton.bones_in_hierarchical_order(armobj)
    bones = armobj.pose.bones
    con_states = {}
    for name in names:
        bone = bones[name]
        if len(bone.constraints) > 0:
            constraints = {}
            con_states[name] = constraints
            for cons in bone.constraints:
                constraints[cons.name] = [cons.mute, cons.influence]
                cons.mute      = True
                cons.influence = 0

    bpy.ops.object.mode_set(mode=armature_mode)
    context.scene.objects.active = active
    return con_states

def RestoreArmaturePoseConstraintsMute(context, armobj, con_states):
    active = context.object
    armature_mode = armobj.mode
    context.scene.objects.active = armobj
    bpy.ops.object.mode_set(mode='OBJECT')

    names = util.Skeleton.bones_in_hierarchical_order(armobj, order='BOTTOMUP')
    bones = armobj.pose.bones
    for name, constraints in con_states.items():
        bone = bones[name]
        for cons_name, mute_state in constraints.items():
            cons = bone.constraints[cons_name]
            mute_state     = val[0]
            influence      = val[1]
            cons.mute      = mute_state
            cons.influence = influence

    bpy.ops.object.mode_set(mode=armature_mode)
    context.scene.objects.active = active

def get_master_bone(bones, bone):
    if not bone:
        return None

    name = bone.name
    if name[0] in ['a','m']:
        return bone
        
    if name == 'PelvisInv':
        return bones.get('mPelvis', bone)

    return bones.get('m'+name, bone)

def get_parent_no_structure(bone):
    if not bone.parent:
        return None

    parent = bone.parent
    if parent.get('is_structure', False):
        return get_parent_no_structure(parent)

    return parent

def bind_rotation_matrix(armobj, dbone, use_cache=True):

    if armobj.RigProps.rig_use_bind_pose:
        slpos, sl_tail = get_sl_restposition(armobj, dbone, use_cache=use_cache)
        cupos, cu_tail = get_custom_restposition(armobj, dbone, use_cache=use_cache)
        M = sl_tail.rotation_difference(cu_tail).to_matrix()
    else:
        M = Matrix()
    return M

def get_sl_bindmatrix(dbone):
    mat = dbone.get('mat', None)
    if mat:
        M = Matrix(mat)
    else:
        M = Matrix()
    return M

def get_floor_compensation(armobj, pos=None, tail=None, use_cache=False):
    toe = armobj.data.bones['mToeRight']
    bh,bt = get_custom_bindposition(armobj, toe, use_cache)
    rh,rt = get_custom_restposition(armobj, toe, use_cache)

    dh = bh-rh
    dt = bt-rt
    dh[0] = dh[1] = 0
    dt[0] = dt[1] = 0

    if pos:
        pos = Vector(pos) - dh
    if tail:
        tail = Vector(tail) - dt

    return pos, tail, dh, dt
    
def get_sl_restposition(armobj=None, dbone=None, use_cache=True, with_floc=False):
    if not armobj:
        armobj = bpy.context.object
        if not dbone:
            dbone=bpy.context.active_bone

    if dbone == None:
        return V0.copy(), V0.copy()
    parent  = get_parent_no_structure(dbone)

    bones = util.get_modify_bones(armobj)

    if use_cache:
        val = get_cache(dbone, 'slr')
        if val:
            if with_floc:
                val[0], val[1], dh, dt = get_floor_compensation(armobj, val[0], val[1], use_cache=use_cache)        
            return Vector(val[0]), Vector(val[1])

    if parent:
        pos, dummy = get_sl_restposition(armobj, parent, use_cache)
    else:
        pos, dummy = Vector((0,0,0)), Vector((0,0,0))

    master = get_master_bone(bones, dbone)

    t   = Vector(master.get('reltail',(0,0,0)))
    d   = Vector(master.get('relhead',(0,0,0)))
    pos += d
    
    if dbone.name == 'PelvisInv':
        log.warning("get_sl_restposition: Flipping head&tail for PelvisInv")
        tt = t.copy()
        pos += t
        t = -tt
   
    if use_cache:
        set_cache(dbone, 'slr', [pos, t])

    if with_floc:
        pos, tail, dh, dt = get_floor_compensation(armobj, pos, tail, use_cache=use_cache)    

    return pos, t

def get_custom_restposition(armobj=None, dbone=None, use_cache=True, with_floc=False):
    if not armobj:
        armobj = bpy.context.object
        if not dbone:
            dbone=bpy.context.active_bone

    if dbone == None:
        return V0.copy(), V0.copy()

    if use_cache:
        val = get_cache(dbone, 'cur')
        if val:
            if with_floc:
                val[0], val[1], dh, dt = get_floor_compensation(armobj, val[0], val[1], use_cache=use_cache)        
            return Vector(val[0]), Vector(val[1])

    bones = util.get_modify_bones(armobj)
    master = get_master_bone(bones, dbone)
    parent = get_parent_no_structure(master)

    if parent:
        pos, dummy = get_custom_restposition(armobj, parent, use_cache)
    else:
        pos, dummy = Vector((0,0,0)), Vector((0,0,0))

    t   = Vector(master.get('reltail',(0,0,0)))
    d   = Vector(master.get('relhead',(0,0,0)))
    pos += d
    jh, jt = util.get_joint_offset(master)
    pos += jh
    tail = t+jt
    
    if dbone.name == 'PelvisInv':
        log.warning("get_custom_restposition: Flipping head&tail for PelvisInv")
        tt = tail.copy()
        pos += tail
        tail = -tt
   
    if use_cache:
        set_cache(dbone, 'cur', [pos, tail])

    if with_floc:
        pos, tail, dh, dt = get_floor_compensation(armobj, pos, tail, use_cache=use_cache)    

    return pos, tail

#

#

#

def get_sl_bindposition(armobj=None, dbone=None, use_cache=True, with_floc=False):
    if not armobj:
        armobj = bpy.context.object
        if not dbone:
            dbone=bpy.context.active_bone

    if dbone == None:
        return V0.copy(), V0.copy()
        
    if use_cache:
        val = get_cache(dbone, 'slbr')
        if val:
            if with_floc:
                val[0], val[1], dh, dt = get_floor_compensation(armobj, val[0], val[1], use_cache=use_cache)
            return Vector(val[0]), Vector(val[1])

    bones = util.get_modify_bones(armobj)
    master = get_master_bone(bones, dbone)
    parent = get_parent_no_structure(master)

    if parent:
        pos, dummy = get_sl_bindposition(armobj, parent, use_cache)
    else:
        pos, dummy = Vector((0,0,0)), Vector((0,0,0))

    t   = Vector(master.get('reltail',(0,0,0)))
    d   = Vector(master.get('relhead',(0,0,0)))
    d += Vector(master.get('offset', (0,0,0)))

    pmaster = get_master_bone(bones, parent)
    s = util.get_bone_scale(pmaster) if pmaster else V1.copy()
    d = Vector([s[i]*d[i] for i in range(3)])
    s = util.get_bone_scale(master) if master else V1.copy()
    tail = Vector([s[i]*t[i] for i in range(3)])

    pos += d
    
    if dbone.name == 'PelvisInv':
        log.warning("get_sl_bindposition: Flipping head&tail for PelvisInv")
        tt = tail.copy()
        pos += tail
        tail = -tt
    
    if use_cache:
        set_cache(dbone, 'slbr', [pos, tail])

    if with_floc:
        pos, tail, dh, dt = get_floor_compensation(armobj, pos, tail, use_cache=use_cache)    

    return pos, tail

def get_custom_bindposition(armobj=None, dbone=None, use_cache=True, with_floc=False):
    if not armobj:
        armobj = bpy.context.object
        if not dbone:
            dbone=bpy.context.active_bone

    if dbone == None:
        return V0.copy(), V0.copy()
        
    if use_cache:
        val = get_cache(dbone, 'cubr')
        if val:
            if with_floc:
                val[0], val[1], dh, dt = get_floor_compensation(armobj, val[0], val[1], use_cache=use_cache)        
            return Vector(val[0]), Vector(val[1])

    bones = util.get_modify_bones(armobj)
    master = get_master_bone(bones, dbone)
    parent = get_parent_no_structure(master)

    if parent:
        pos, cu_tail = get_custom_bindposition(armobj, parent, use_cache)
    else:
        pos, cu_tail = Vector((0,0,0)), Vector((0,0,0))

    M  = bind_rotation_matrix(armobj, parent, use_cache)
    MT = bind_rotation_matrix(armobj, master, use_cache)

    t   = Vector(master.get('reltail',(0,0,0)))
    d   = Vector(master.get('relhead',(0,0,0)))

    jh, jt = util.get_joint_offset(master)
    m = jh.magnitude
    if jh.magnitude:
       d += jh
    else:
       d += Vector(master.get('offset', (0,0,0)))

    if jt.magnitude:
       t += jt

    pmaster = get_master_bone(bones, parent)
    s = util.get_bone_scale(pmaster) if pmaster else V1.copy()
    dd = d*M
    dd = Vector([s[i]*dd[i] for i in range(3)])
    d  = M*dd

    s = util.get_bone_scale(master) if master else V1.copy()
    tt = t*MT
    tt = Vector([s[i]*tt[i] for i in range(3)])
    tail  = MT*tt

    pos += d
    
    if dbone.name == 'PelvisInv':
        log.warning("get_custom_bindposition: Flipping head&tail for PelvisInv")
        tt = tail.copy()
        pos += tail
        tail = -tt

    if use_cache:
        set_cache(dbone, 'cubr', [pos, tail])

    if with_floc:
        pos, tail, dh, dt = get_floor_compensation(armobj, pos, tail, use_cache=use_cache)    

    return  pos, tail

def get_cache(dbone, key):
    cache = dbone.get('cache', None)
    if not cache:
        return None

    val = cache.get(key, None)
    return val

def set_cache(dbone, key, val):
    cache = dbone.get('cache', None)
    if not cache:
        cache = {}

    cache[key] = val
    dbone['cache'] = cache

def reset_cache(armobj, subset=None, full=False):
    log_cache.debug("Reset Cache")
    if subset == None:
        subset = util.get_modify_bones(armobj)
    for dbone in subset:
        util.remove_key(dbone, 'cache')
        if full:
            util.remove_key(dbone, 'fix_head')
            util.remove_key(dbone, 'fix_tail')

def store_restpose_mats(arm_obj):

    ebones = arm_obj.data.edit_bones
    for ebone in ebones:
        mat = ebone.matrix
        ebone['mat0'] = ebone.matrix

def restore_source_bone_rolls(armobj):
    omode = util.ensure_mode_is("EDIT")
    ebones = armobj.data.edit_bones
    bone_names = util.Skeleton.bones_in_hierarchical_order(armobj)
    for name in bone_names:
        ebone = ebones.get(name, None)
        if ebone:
            restore_source_bone_roll(armobj, ebone)
    util.ensure_mode_is(omode)

def get_line_bone_names(pbones, selection):
    linebones = []
    for name in selection:
        posebone = pbones[name]
        if len([constraint for constraint in posebone.constraints if constraint.type == "STRETCH_TO"]) > 0:
            linebones.append(name)
            continue
    return linebones

def get_pole_bone_names(pbones, selection):
    polebones = []
    for name in selection:
        posebone = pbones[name]
        if len([constraint for constraint in posebone.constraints if constraint.type == "IK" and constraint.pole_target]) > 0:
            polebones.append(name)
    return polebones

def restore_source_bone_roll(armobj, ebone):

    omode = util.ensure_mode_is("EDIT")
    head, tail = get_sl_restposition(armobj, ebone, use_cache=True)

    hs = ebone.hide_select
    ebone.hide_select=False
    matrix = Matrix(ebone['mat0']).to_3x3()
    dv     = ebone.tail - ebone.head
    dq     = tail.rotation_difference(dv)
    matrix.rotate(dq)
    matrix = matrix.to_4x4()
    matrix.translation = ebone.head
    ebone.matrix = matrix

    ebone.hide_select=hs
    util.ensure_mode_is(omode)

armature_mode         = None
ik_edit_bones         = None

last_action = None
@persistent
def sync_timeline_action(scene):
    from . import animation

    active = scene.objects.active
    if not ( active and active.type =='ARMATURE' and 'karaage' in active):

        return
    if not active.animation_data:
        return

    global last_action
    action = active.animation_data.action

    if not action:

        last_action = None
        return

    animation.set_update_scene_data(False)
    try:

        if action.AnimProps.frame_start == -2:

            fr = action.frame_range
            log.warning("Preset Action from Action Frame Range [%d -- %d]" % (fr[0], fr[1]))
            action.AnimProps.fps = scene.render.fps
            action.AnimProps.frame_start = fr[0]
            action.AnimProps.frame_end = fr[1]

        if scene.SceneProp.loc_timeline:
            if last_action != action:
                start = action.AnimProps.frame_start
                end = action.AnimProps.frame_end
                fps = action.AnimProps.fps
                log.warning("Preset Timeline from Action Frame Range [%d -- %d] fps:%d" % (start, end, fps))
                scene.frame_start = start
                scene.frame_end = end
                scene.render.fps = fps

            else:

                action.AnimProps.frame_start = scene.frame_start
                action.AnimProps.frame_end = scene.frame_end
                action.AnimProps.fps = scene.render.fps
        last_action = action

    finally:
        animation.set_update_scene_data(True)

@persistent
def check_dirty_armature_on_update(scene):
    active = scene.objects.active
    if not active or active.type !='ARMATURE' or 'dirty' in active or not util.is_in_user_mode():
        return

    if not 'karaage' in active:
        return

    if active.mode=='EDIT':
        ebones = active.data.edit_bones
        dbones = active.data.bones

        ebone = ebones.active
        if ebone:
            dbone = dbones.get(ebone.name)
            selection = [[ebone,dbone]]
        else:
            selection = [ [e, dbones.get(e.name)] for e in ebones if e.select]

        for ebone, dbone in selection:
            if not 'bone_roll' in ebone:
                ebone['bone_roll'] = ebone.roll

            if active.get('dirty') or dbone==None:
                continue

            if ebone.head != dbone.head_local:
                active['dirty'] = True
                log.warning("Dirty Bone %s:%s head mismatch" % (active.name, ebone.name) )
            if ebone.tail != dbone.tail_local:
                active['dirty'] = True
                log.warning("Dirty Bone %s:%s tail mismatch" % (active.name, ebone.name) )
            if ebone.roll != ebone['bone_roll']:
                active['dirty'] = True
                log.warning("Dirty Bone %s:%s roll mismatch" % (active.name, ebone.name) )

@persistent
def fix_linebones_on_update(dummy):

    if not bpy.context.scene.ticker.fire:
        return

    if util.is_updating():
        return # no need to do anything

    try:
        armobj = bpy.context.object
    except:
        return # Nothing to do here

    global armature_mode
    global ik_edit_bones

    armobj = bpy.context.object
    need_update = False
    pbone       = None

    if armobj and armobj.type=='ARMATURE' and "karaage" in armobj:
        if armobj.mode == "EDIT":
            p = util.getAddonPreferences()
            if not p.auto_adjust_ik_targets:
                return

            if armature_mode == armobj.mode:

                pbone = bpy.context.active_bone
                if pbone is not None and pbone.name in IK_TARGET_BONES:
                    if ik_edit_bones == None:
                        ik_edit_bones = {}
                    if pbone.name in ik_edit_bones :
                        if pbone.head != ik_edit_bones[pbone.name][0] or pbone.tail != ik_edit_bones[pbone.name][1]:
                            need_update = True
                            ik_edit_bones[pbone.name] = [pbone.head.copy(), pbone.tail.copy()]
                    else:
                        need_update = True
                        ik_edit_bones[pbone.name] = [pbone.head.copy(), pbone.tail.copy()]
            else:

                armature_mode = armobj.mode
                need_update  = True
                ik_edit_bones = {}

        elif armobj.mode=="POSE":

            if armature_mode != armobj.mode:

                armature_mode = armobj.mode
                need_update   = True
        else:
            armature_mode = armobj.mode
    else:
        armature_mode = None

    if armature_mode !="EDIT" and ik_edit_bones: ik_edit_bones = None

    if need_update:
        if armobj.mode == "EDIT":

            if pbone:
                if pbone.name.endswith("TargetRight"): name=pbone.name[0:-11]
                elif pbone.name.endswith("TargetLeft"): name=pbone.name[0:-10]
                else:
                    return
                selection = [name+"LineLeft", name+"LineRight"]
            else:
                selection = IK_LINE_BONES

            fix_stretch_to(armobj, selection)

        elif armobj.mode == "POSE":
            if bpy.context.scene.MeshProp.adjustPoleAngle:

                original_pose = armobj.data.pose_position
                armobj.data.pose_position="REST"

                for bonename in IK_POLE_BONES:

                    posebone = armobj.pose.bones[bonename] if bonename in armobj.pose.bones else None
                    if posebone:
                        for constraint in posebone.constraints:
                            if constraint.type == "IK" and constraint.pole_target:

                                fix_pole_angle(posebone, constraint)

                armobj.data.pose_position=original_pose
                bpy.context.scene.update()

def fix_stretch_to(armobj, selection=None):
    log.debug("Fixing Stretch for armature %s" % armobj.name)
    if not selection:
        selection = IK_LINE_BONES
    for linebname in selection:

        if linebname in armobj.pose.bones:
            linebone = armobj.pose.bones[linebname]
            con_stretchto = None
            con_copyloc = None

            for constraint in linebone.constraints:
                if not con_stretchto and constraint.type == "STRETCH_TO":
                    con_stretchto = constraint
                elif not con_copyloc and constraint.type == "COPY_LOCATION":
                    con_copyloc = constraint

            if con_stretchto and con_copyloc:
                try:
                    if armobj.mode=="EDIT":
                        line_bone   = armobj.data.edit_bones[linebname]
                        pole_target = armobj.data.edit_bones[con_stretchto.subtarget]
                        pole_source = armobj.data.edit_bones[con_copyloc.subtarget]
                        line_bone.tail = pole_target.head
                        line_bone.head = pole_source.head
                except:
                    log.info("Can not fix the Stretch To IK Target (Missing IK bones)")

                log.debug("Fixing Stretch for bone %s in armature %s" % (linebone.name, armobj.name))
                con_stretchto.rest_length=0.0 #This actually recalculates value for "no stretch"

def fix_pole_angles(armobj, selection):

    for bonename in selection:
        posebone = armobj.pose.bones[bonename]
        for constraint in posebone.constraints:
            if constraint.type == "IK":
                fix_pole_angle(posebone, constraint)

def fix_pole_angle(pbone, constraint):
    if constraint.pole_target:
        pole_target = constraint.pole_target.data.bones.get(constraint.pole_subtarget,None)
        if pole_target:
            influence = constraint.influence
            constraint.influence = 0
            bpy.context.scene.update()

            v1          = pbone.x_axis
            v2          = pole_target.head_local - pbone.head
            vn          = pbone.y_axis # The normal

            sign        = 1
            if v2.cross(v1)*vn < 0:
                sign = -1

            constraint.pole_angle = sign * v1.angle(v2)
            constraint.influence = influence
            bpy.context.scene.update()

def fix_karaage_armature(context, armobj):
    scene=context.scene
    hidden = armobj.hide
    armobj.hide=False
    active_object = scene.objects.active
    if active_object == None:
        return

    original_mode = active_object.mode
    scene.objects.active = armobj

    original_armob_mode = util.ensure_mode_is('OBJECT')

    if armobj.get('karaage', 0) < 4:
        boneset = data.get_reference_boneset(armobj)
        for bone in armobj.data.bones:
            BONE = boneset.get(bone.name)
            if BONE:
                bone.layers = [ii in BONE.bonelayers for ii in range(32)]
    
        original_armob_mode = util.ensure_mode_is('EDIT')
        armobj['sl_joints'] = {}
        sl_joints = calculate_offset_from_sl_armature(
                           context,
                           armobj,
                           corrs=None,
                           all=True,
                           with_ik_bones=False,
                           with_joint_tails=True
                    )
    
        print("Add joints repository with %d entries to Armature %s" % (len(sl_joints), armobj.name) )
        util.ensure_mode_is('OBJECT')

    rigType = armobj.get('rigtype', None) #Old way to define the rigtype

    if rigType:
        armobj.RigProps.Rigtype = rigType
        del armobj['rigtype']

    util.ensure_mode_is('EDIT')
    bones = armobj.data.edit_bones
    pbones = armobj.pose.bones
    offset_count = 0
    for bone in bones:
        if not (bone.name[0:2]=='ik' or 'Link' in bone.name or bone.name=='Origin'):
            h, t = get_sl_bindposition(armobj, bone, use_cache=True)
            magnitude = (h - bone.head).magnitude
            if magnitude > MIN_BONE_LENGTH:
                offset_count += 1
                log.debug("Bone %s is offset by %f from expected loc %s" % (bone.name, magnitude, h) )
        if bone.use_deform and not bone.layers[B_LAYER_DEFORM]:
            bone.layers[B_LAYER_DEFORM]=True

    if offset_count > 0:
        context.scene.UpdateRigProp.transferJoints = True
        armobj['offset_count'] = offset_count
    elif 'offset_count' in armobj:
        del armobj['offset_count']

    selection = util.Skeleton.bones_in_hierarchical_order(armobj)
    linebones = get_line_bone_names(pbones, selection)
    fix_stretch_to(armobj, linebones)

    util.ensure_mode_is(original_armob_mode)
    armobj.hide = hidden
    scene.objects.active = active_object
    util.ensure_mode_is(original_mode)

def guess_pose_layers(armobj):
    layers = armobj.data.layers
    for player, dlayers in DEFORM_TO_POSE_MAP.items():
        for layer in dlayers:
            layers[player] = layers[player] or layers[layer]

    for player, dlayers in DEFORM_TO_POSE_MAP.items():
        for dlayer in dlayers:
            layers[dlayer] = False

def guess_deform_layers(armobj):
    layers = armobj.data.layers
    at_least_one = False
    for player, dlayers in DEFORM_TO_POSE_MAP.items():
        layers[dlayers[0]] = layers[dlayers[0]] or layers[player]
        at_least_one = at_least_one or layers[dlayers[0]]

    for player, dlayers in DEFORM_TO_POSE_MAP.items():
        layers[player] = False

    if not at_least_one:
        layers[B_LAYER_DEFORM] = True

def get_bone_location(b=None):
    if not b:
        b=bpy.context.active_bone
    parent = b.parent
    if parent:
        h0, t0 = get_bone_location(parent)
    else:
        h0 = t0 = Vector((0,0,0))
    h = b.get('orelhead', b.get('relhead', (0,0,0)))
    t = b.get('oreltail', b.get('reltail', (0,0,0)))
    h = Vector(h) + h0
    t = Vector(t)
    return h,t

def update_spine_fold(context, armobj):
    props = armobj.RigProps
    with set_context(context, armobj, 'EDIT'):
        armatureSpineFold(armobj)
        if props.spine_unfold_upper:
            armatureSpineUnfoldUpper(armobj)
        if props.spine_unfold_lower:
            armatureSpineUnfoldLower(armobj)

def update_spine_folding(self, context):
    armobj = util.get_armature(context.object)
    if armobj:
        update_spine_fold(context, armobj)

def armatureSpineUnfoldLower(arm):
    print("Unfolding Lower Spine")
    util.ensure_mode_is('EDIT')
    bones   = util.get_modify_bones(arm)

    cog     = bones['COG']
    torso   = bones['Torso']
    spine1  = bones['Spine1']
    spine2  = bones['Spine2']
    pelvisi = bones['PelvisInv']
    pelvis  = bones['Pelvis']
    mpelvis = bones['mPelvis']
    mspine1 = bones['mSpine1']
    mspine2 = bones['mSpine2']

    if spine1.tail != spine2.head or \
        spine2.tail != spine1.head or \
        torso.head  != spine2.tail:
        print("armatureSpineUnfold: Lower spine is already unfolded, nothing to do")
        return

    end     = Vector(torso.head)
    begin   = Vector(pelvisi.tail)
    dv      = (end-begin)/3

    torso.parent  = spine2
    spine2.parent = spine1
    spine1.parent = pelvis

    spine2.head   = end - dv
    spine2.tail   = end
    mspine2.head  = end - dv
    mspine2.tail  = end
    
    spine1.head   = begin + dv
    spine1.tail   = end - dv
    mspine1.head  = begin +  dv
    mspine1.tail  = end - dv
    
    pelvis.tail = begin + dv
    mpelvis.tail = begin + dv

    set_connect(mspine1, True)
    set_connect(mspine2, True)

    mspine1.hide = False
    mspine2.hide = False
    spine1.hide  = False
    spine2.hide  = False

def reset_rig_to_restpose(armobj):
    omode = util.ensure_mode_is("POSE")
    layers = []
    for i,l in enumerate(armobj.data.layers):
        layers.append(l)
        armobj.data.layers[l]=True
    bpy.ops.pose.select_all(action='SELECT')
    armobj.data.layers = layers
    
def armatureSpineUnfoldUpper(arm):
    print("Unfolding Upper Spine")
    util.ensure_mode_is('EDIT')
    bones  = util.get_modify_bones(arm)
    torso  = bones['Torso']
    spine3 = bones['Spine3']
    spine4 = bones['Spine4']

    if  spine3.head != torso.tail or \
        spine3.tail != torso.head or \
        spine4.head != spine3.tail or \
        spine4.tail != spine3.head:
        print("armatureSpineUnfold: Upper spine is already unfolded, nothing to do")
        return

    chest  = bones['Chest']

    end   = Vector(chest.head)
    begin = Vector(torso.head)
    dv    = (end-begin)/3

    chest.parent  = spine4
    spine4.parent = spine3
    spine3.parent = torso
    spine4.head   = end   - dv
    spine3.head   = begin + dv

    mchest  = bones['mChest']
    mspine3 = bones['mSpine3']
    mspine4 = bones['mSpine4']

    mspine4.head = end - dv
    mspine3.head = begin + dv
    set_connect(mspine4, True)
    set_connect(mspine3, True)
    set_connect(mchest, True)

    mspine3.hide = False
    mspine4.hide = False
    spine3.hide  = False
    spine4.hide  = False

def armatureSpineFold(arm):
    print("Folding all Spine bones")
    util.ensure_mode_is('EDIT')
    bones  = util.get_modify_bones(arm)

    Pelvis  = bones.get('Pelvis')
    Pelvisi = bones.get('PelvisInv')
    Torso   = bones.get('Torso')
    Chest   = bones.get('Chest')
    COG     = bones.get('COG')
    
    end     = Vector(Chest.head)
    begin   = Vector(Pelvisi.head)

    Chest.parent = Torso
    Torso.parent = COG

    Spine4 = bones.get('Spine4')
    Spine3 = bones.get('Spine3')
    Spine2 = bones.get('Spine2')
    Spine1 = bones.get('Spine1')
    
    mSpine4 = bones.get('mSpine4')
    mSpine3 = bones.get('mSpine3')
    mSpine2 = bones.get('mSpine2')
    mSpine1 = bones.get('mSpine1')
    mTorso  = bones.get('mTorso')
    
    Chest.head = end
    
    if Spine1 and Spine2 and Spine3 and Spine4:
        Spine4.tail = end
        Spine4.head = begin
        Spine3.tail = begin
        Spine3.head = end
        Torso.tail  = end
        Torso.head  = begin
        Spine2.tail = begin
        Spine2.head = Pelvis.head
        Spine1.tail = Pelvis.head
        Spine1.head = begin
        
        Spine1.hide  = True
        Spine2.hide  = True
        Spine3.hide  = True
        Spine4.hide  = True

    if mSpine1 and mSpine2 and mSpine3 and mSpine4:
        mSpine4.tail = end
        mSpine4.head = begin
        mSpine3.tail = begin
        mSpine3.head = end
        mTorso.tail  = end
        mTorso.head  = begin
        mSpine2.tail = begin
        mSpine2.head = Pelvis.head
        mSpine1.tail = Pelvis.head
        mSpine1.head = begin

        mSpine1.hide = True
        mSpine2.hide = True
        mSpine3.hide = True
        mSpine4.hide = True

def get_slider_displacement(armobj):
    mpelvis = armobj.data.bones.get('mPelvis')
    d = None
    if mpelvis:

        ch, ct = get_custom_bindposition(armobj, mpelvis, use_cache=False, with_floc=True)
        oh = mpelvis.head_local
        d = ch-oh
        if d.magnitude < MIN_BONE_LENGTH:
            return None

    return d

def deform_display_reset(arm):
    util. remove_key(arm, 'filter_deform_bones')
    util. remove_key(arm, 'rig_display_type')
    util. remove_key(arm, 'rig_display_mesh')
    util. remove_key(arm, 'rig_display_mesh_count')

def deform_display_changed(context, arm, objs):
    changed = False
    if arm.ObjectProp.filter_deform_bones != arm.get('filter_deform_bones'):
        arm['filter_deform_bones'] = arm.ObjectProp.filter_deform_bones
        changed = True
    if arm.ObjectProp.rig_display_type != arm.get('rig_display_type'):
        arm['rig_display_type'] = arm.ObjectProp.rig_display_type
        changed = True
    obname = context.object.name
    if arm.get('rig_display_mesh') != obname:
        arm['rig_display_mesh'] = obname
        changed = True
    if arm.get('rig_display_mesh_count', -1) != len(objs):
        arm['rig_display_mesh_count'] = len(objs)
        changed = True

    return changed

class KaraageAdjustSliderDisplacement(Operator):
    bl_idname = "karaage.adjust_slider_displacement"
    bl_label = "Adjust Slider Offset"
    bl_description = "Compensate Slider misalignment"

    @classmethod
    def poll(self, context):
        armobj = context.object
        if not armobj:
            return False
        return armobj.type == 'ARMATURE'

    def execute(self, context):
        armobj = context.object
        d = get_slider_displacement(armobj)
        if d:
            joints = armobj.get('sl_joints')
            if joints:
                joint = joints.get('mPelvis')
                if joint:
                    h = Vector(joint['head'])-d
                    joint['head'] = h

            omode = util.ensure_mode_is('EDIT')
            ebones = armobj.data.edit_bones
            origin = ebones.get('Origin')
            if origin:
                origin.head -= d
                origin.tail -= d
            util.ensure_mode_is(omode)
            
            util.transform_origin_to_rootbone(context, armobj)

        return {'FINISHED'}
