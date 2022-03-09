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


msg_export_warnings = '%d warnings during export.|'\
                +  'DETAIL:\nWhile exporting your meshes i found some trouble makers.\n'\
                +  'I can not tell for sure but the following items might cause serious problems:\n\n'\
                +  '%s \n\n'\
                +  'ACTION:\nYou either can ignore me for now and just upload the files to SL\nor you can try to fix the issues and then export again.\n\nFor Experts: More info can be found in the Blender Console|'

msg_no_armature = '%s is not assigned to an Armature.|'\
                +  'DETAIL: We need an armature to decide which weight groups need to be examined.\n'\
                +  'However your object is currently not assigned to an armature.\n'\
                +  'ACTION: Please assign this object to an armature, then try again.|'

msg_unweighted_verts = 'Please fix %d unweighted vertices on %s.|'\
                +  'DETAIL INFO:\nSome of the vertices in your mesh are not assigned to any weight group.\n'\
                +  'Karaage has stopped processing your request, because it can not handle unweighted vertices.\n\n'\
                +  'YOUR ACTION:\n'\
                +  '- Ensure that all vertices of your mesh are assigned to weight groups.\n'\
                +  '- Tip: Use the Weight copy tools from the Weight Paint Tool shelf to fix this.\n\n|find_unweighted'

msg_zero_verts = 'Please fix %d verts with a weight sum of 0 in %s.|'\
                +  'DETAIL INFO:\nAll of the vertices in your mesh are assigned correctly to weight groups.\n'\
                +  'But some of the assigned verts have a weight sum of 0 (zero). Karaage can not handle \n'\
                +  'this and has aborted the operation.\n\n'\
                +  'YOUR ACTION:\n'\
                +  '- Lookup the "Zero Weights" finder in the Tool Shelf to checkmark the offending vertices.\n'\
                +  '- For each selected vertex assign a non zero value to at least one weight group.\n'\
                +  '- Please use the available Weight copy tools from the\n'\
                +  '  Weight Paint Tools shelf to fix this.\n\n|find_unweighted'

msg_face_tricount = 'At least one Texture Face with high Triangle count (%d tris).|'\
              +  'DETAIL INFO:\nIn SL any Texture Face has a limit of 21844 Triangles.\n'\
              +  'If a texture face uses more than 21844 Triangles,\n'\
              +  'the SL Importer automatically splits the face into subfaces.\n'\
              +  'and each subface is treated by the SL Importer as one extra Material.\n'\
              +  'This can lead to unexpected results:\n\n'\
              +  'More than 8 materials:\n'\
              +  'If a Mesh has more than 8 materials the entire mesh gets split into submeshes.\n'\
              +  'You might want to avoid this.\n\n'\
              +  'Missing Material in LOD\n'\
              +  'When you let the SL Importer generate LOD, then it may end up in a weird state\n'\
              +  "where it calculates different Material counts in the lower LOD's\n"\
              +  'which results in an Importer Error.\n\n'\
              +  'YOUR ACTION:\n'\
              +  '- Reduce the number of Triangles in your Mesh\n'\
              +  '- Take care to create texture faces with less than 21844 triangles\n\n|high_tricount'

msg_mesh_tricount = 'Mesh with high Triangle count (%d tris).|'\
              +  'DETAIL INFO:\nIn SL a Mesh may not use more than 65536 triangles on any texture face.\n'\
              +  'One of your meshes exceeds this number.\n'\
              +  'This will cause an error when you try to import your mesh to SL.\n\n'\
              +  'YOUR ACTION:\n'\
              +  '- Reduce the number of Triangles in your Mesh\n'\
              +  '- Take care to create texture faces with less than 21844 triangles\n\n|high_tricount'

#
#
#
#
#

msg_identified_weightgroups = "The following %d mesh Weight Groups have been identified as Bone deforming Weightmaps.\n"\
                + "These Weightmaps will be exported by Karaage\n\n"\
                + "List of affected Weightmaps:\n\n"

msg_discarded_weightgroups = "The following %d mesh Weight Groups will not be used as Bone deforming Weightmaps,\n"\
                + "because the associated Bones are not marked as 'Deforming Bones'.\n\n"\
                + "Note: You can change this by enabling 'Deform' in the corresponding\n"\
                + "Bone properties of the associated Armature.\n\n"\
                + "List of affected Weight Groups:\n\n"
                
msg_missing_uvmaps = "No UV Map found in %d %s:|"\
                + "%s\n"\
                + "DETAIL:\n"\
                + "You need UV Maps to texturise your Mesh.\n"\
                + "If you later try to add a texture to an object without UV Map,\n"\
                + "this will fail (the mesh gets a unique color at best).\n\n"\
                + "YOUR ACTION:\n"\
                + "Unwrap (keyboard shortcut 'U') all meshes with no UV Layer\n\n"\
                + "NOTE:\nYou must have a good understanding of UV unwrapping\n"\
                + "before you can expect to get good results!\n"

msg_no_objects_to_copy_from = "No meshes available from where to copy weights|"\
                + "DETAIL:\n"\
                + "You want to assign weights from other meshes to %s.\n"\
                + "But there is no other weighted mesh rigged to the Armature [%s]\n\n"\
                + "YOUR ACTION:\n"\
                + "Probably you want to switch the Weight option from 'Meshes' to 'Bones' (see panel)|copy_bone_weights"

msg_no_weights_to_copy_from = "No meshes visible from where to copy weights|"\
                + "DETAIL:\n"\
                + "You want to Bind with copy weights from other 'Meshes' to %s. However \n"\
                + "all other rigged meshes on the active armature [%s] are not visible.\n\n"\
                + "YOUR ACTION:\n"\
                + "- Either Switch the Weight option from 'Meshes' to 'Bones' (see panel)\n"\
                + "or otherwise please ensure that:\n"\
                + "- At least one other Mesh is already attached to the Armature\n"\
                + "- AND at least one of the attached other meshes is visible|copy_bone_weights"

msg_failed_to_bind_automatic = "Could not generate weights for all vertices|"\
                + "DETAIL:\n"\
                + "You want to Bind with generating weights from Bones. However \n"\
                + "Blender was not able to find a solution for %d vertices in your mesh \"%s\".\n\n"\
                + "REASON:\n"\
                + "Your Mesh probably contains multiple overlaping sub meshes.\n\n"\
                + "YOUR ACTIONS (alternatives):\n"\
                + "- Ensure that the submeshes do not overlap\n"\
                + "- consider to make a cleaner topology with only one mesh\n"\
                + "- You could separate your mesh into multiple objects\n"\
                + "  instead of using just one single object\n"\
                + "Hint: You can revert this operation by pressing CTRL Z|binding"

panel_info_mesh = '''Mesh Info Display Important Mesh statistics for current Selection| Quickinfo:
* Statistics:
  - Verts : Number of vertices for current selection
  - Faces : Number of Faces for Current Selection
  - Tris  : Number of Triangles after triangulate is performed
  - Mats  : Number of Materials (for the Object with highest number of materials)
Note: Mats can have 2 numbers n/m where n is the number of user defined materials
and m is the number of materials created by the SL Importer

* Estimates: Estimated numbers for different Levels of Detail.
The estimates only give an estimate! 
The final numbers are calculated by the Mesh Importer.
'''

panel_info_workflow = '''Workflow (Only available for Karaage Armatures)| Quickinfo:
* Presets for various Tasks:
  - Skin      : Preset for weighting your mesh
  - Pose      : Preset for posing your Mesh
  - Retarget: Preset for importing a BVH animation for your Mesh
  - Edit      : Preset for editing the Bones (for non human characters)
'''

panel_info_rigging = '''Rigging (Only available for Karaage Armatures)| Quickinfo:
* Bone Display Style: modifies the look&feel of the bones.
* Visibility: defines which bones are displayed
* Deform Bones: These Bones are used to animate your Mesh
'''
panel_info_skinning = '''Skinning|Skinning is the process of creating an association
between a Mesh (the Skin) and a Rig. Quickinfo:

Bind to Armature: Assign selected Meshes to selected Armature
* Weight: The source from where the initial weights are taken.
  Note: Each weight source uses different intitial parameters

Appearance Control: Allows to assign/deassign Appearance Sliders.
* Apply Sliders: bakes the current Shape into the Mesh
* No Sliders: Revert to initial state, mesh is NOT modified!
'''

panel_info_posing = '''Posing|Posing is the process of placing bones
to create Poses for the Meshes bound to the Skeleton. Quickinfo:

Set Bind Pose: Use the current Pose as new Restpose

'''

panel_info_fitting = '''Fitting|The Fitting Panel is used to create the weights
for the Collision Volume Bones.
This pannel is not needed for classic (mBone) weighting.

Fitting Presets: Predefined weight distributions
   - Fully Classic: Use only mBones (classic weighting)
   - Fully Fitted: Use only Collision Volume bones for weighting

* Generate Physics: Enables the Peck, Butt, Handles, Back bones and adds initial weights.
* Bone fitting Strength: Gradually shift bone weights between fully classic and fully fitted
* Adjust Shape: Use existing Shape key as target shape for the fitting weights (experimental)
* Smooth Weights: tries to make the mesh smoother by smoothing the weights.
'''

panel_info_appearance = '''Appearance|We support the same shape slider system as you can find
in SL, OpenSim or other compatible worlds.

* Shape Presets: Your Shapes to be applied in one click.
* The orange stickman: Avatar default Shape
* The white Stickman: Avatar technical restpose Shape

* Bake to Mesh: Bake the current Shape key setting to Mesh
'''
panel_warning_appearance = '''Appearance|This Armature has unsaved Joints!

You probably have opened the Armature Editor and moved some bones.
When you do this then you need to ensure the joint edits have been
stored before you can use the Appearance Sliders again.

You can store the joints when the Armature is in Edit mode.
Then open the Posing panel.
And Store Joint Edits.
'''

panel_info_tools = '''Tools|The Karaage Tools Panel is a container for tools which
do not fit anywhere else. You find the Karaage Tool Panel in the Tool Shelf,
in the Karaage tab.

* Vertex Tools: to find zero weighted unweighted vertices, etc...
* Most important tool: Freeze shape
'''

panel_info_register = '''Info|This panel is about your product registration.
If you have registered your product
and if you have created an account on our website,
then you can always check/download/install
the newest Update right away from this panel...
'''

panel_info_edited_joints = '''Joint State|This armature has been modified.
Note: This Armature contains at least one bone with a Joint Offset.
When you upload this rig to SL then do one of the 2 options below:

- enable the 'with joints' option to propagate the edited joints to SL
- enable the 'bind pose' option in this panel

Note: If you enable the bind pose option then the rig behaves effectively
equal to a Rig without Joint Offsets. It just happens to have a different
Rest position (bind pose)
'''

panel_info_clean_joints = '''Joint State|This armature is a clean vanilla Second Life Rig.
Note: This Armature does not contain any edited Joints.
When you upload this rig to SL then keep the 'with joints' option disabled.
'''

panel_info_negative_scales = '''Negative Scales|At least one of the selected Objects contains negative Object Scaling.
This can potentially damage your Face Normals.

Your Action (mandatory): Please cleanup your Object Scaling before binding.
'''

panel_info_scales = '''Scaled items|At least one of the selected Objects has Object Scaling.
This can potentially damage your Exported Objects.

Your Action (optional): Consider to cleanup your Object Scaling before binding.
'''

panel_info_rotations = '''Rotated items|At least one of the selected Objects has Object rotations.
This can potentially damage your Exported Objects.

Your Action (optional): Consider to cleanup your Object Rotations before binding.
'''

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
#

panel_info_collada = '''Collada|The Karaage Collada Panel contains the user interface
for our own optimised Collada Exporter. The exporter implements a few special features
which can not be added to the Blender default Collada exporter. Here are the most 
important export features:

* Modifiers: To swtich between exporting the modifier settings for Viewport or Render 
* Texures: To specify which textuires shall be exported
* Advanced: A set of tools for special situations 
* Unsupported: A set of tools which are not or no longer supported by SL 

The Collada exporter also can export to different target systems:
Basic    : Old behavior for Second Life before Project Bento
Extended : Takes new Bones from Project Bento into account
Other    : Export to worlds other than Second Life, currently identical to Basic

Note: The Unsupported subpanel appears only when it is also enabled in the Addon panel.
Please check the Karaage documentation for more details.
'''

UpdateRigProp_snap_collision_volumes_description = \
'''Try to move the Collision Volumes to reasonable locations
relative to their related Deform Bones (experimental)
'''

UpdateRigProp_snap_attachment_points_description = \
'''Try to move the Attachment Points to reasonable locations
relative to their related Deform Bones (experimental)
'''

UpdateRigProp_bone_repair_description = \
'''Reconstruct all missing bones.
This applies when bones have been removed from the original rig

IMPORTANT: when you convert a Basic Rig to an Extended Rig
then you should enable this option
Otherwise the extended (Bento) bones are not generated.'''

UpdateRigProp_adjust_pelvis_description = \
'''Auto Align Pelvis and COG.

Pelvis, PelvisInv, and COG must be placed relative to each other:

- Pelvis and PelvisInv reverse match (head to tail, tail to head)
- Pelvis and mPelvis match
- COG head must be placed at Pelvis tail

Note: The Slider system only works when the bones are adjusted'''

UpdateRigProp_adjust_rig_description = \
'''Synchronize the Control Bones and the Deform Bones.

With Karaage-2 the slider system is much more integrated into the tool.
Because of this we have to ensure that the control bones and the deform
bones are aligned to each other. You have 2 choices:

- Align Control bones to match the Deform Bones
- Align Deform Bones to match the Control Bones'''

UpdateRigProp_align_to_deform_description = \
'''Specify who is the alignment master (pelvis or mPelvis):

-Pelvis: Move mPelvis to Pelvis (Use the green Pelvis bone as master)
-mPelvis:  Move Pelvis to mPelvis (Use the blue mPelvis bone as master)'''

UpdateRigProp_align_to_rig_description = \
'''Specify who is the alignment master (Deform Rig or Control Rig):

-Control Rig: Adjust the Deform Rig to match the Control Rig
-Deform Rig:  Adjust the Control Rig to match the Deform Rig'''

UpdateRigProp_adjust_origin = \
'''Matches the Karaage Root Bone with the Karaage Origin location.

Note: This adjustment is necessary to keep the Appearance Sliders working.
'''

UpdateRigProp_adjust_origin_armature = \
'''Move the Root Bone to the Armature Origin Location.
The location of the Armature in the scene is not affected'''

UpdateRigProp_adjust_origin_rootbone = \
'''Move the Armature Origin Location to the Root Bone.
The location of the Armature in the scene is not affected'''

Karaage_rig_edit_check_description = \
'''Karaage Meshes should not be edited.
By default Karaage creates a popup when a user attempts to edit an Karaage mesh
You can disable this check to permanently suppress the popup message.

Note: We recommend you keep this option enabled!'''

AnimProps_Translation_description = \
'''Export bone translation channels.
Enable this option when you intend to create animations with translation components.

When your animation contains translation components we recommend
that you also test your animations with different appearance slider settings
to detect potential conflicts with the slider system(Avatar Shapes)

Note: Animations with only Rotation channels are less likely to conflict with the avatar shape.'''

AnimProps_selected_actions_description = \
'''Export all Actions in the scene
When this option is enabled you get a list of all available actions
from which you can select the ones you want to export.'''

ObjectProp_apply_armature_on_snap_rig_description = \
'''Apply the current Pose to all bound meshes (including the Karaage meshes) before snapping the rig to pose

The snap Rig to Pose operator modifies the Restpose of the Armature.
When this flag is enabled, the bound objects will be frozen and reparented to the new restpose
Note: When this option is enabled, the operator deletes all Shape keys from the bound objects!

Handle with Care!'''

RigProps_restpose_mode_description = \
'''The Armature has been locked to the SL Restpose.
Click to unlock the Appearance Sliders.

Note: You use this mode when you want to attach Mesh characters (or devkits)
which have originally been made with the simple SL Avatar rig.
Unlocking the SLiders keeps the Restpose intact until you modify the Slider settings'''

RigProps_rig_use_bind_pose_description = \
'''Set the Rig pose type.

- unset: Use the rig with Joint Offsets. (to be used 'with joints' when importing to SL).
- set  : Use the rig with Bind pose. (Do not use 'with joints' when importing to SL).

Important: If this option is unset, then you later must set the 'with joints' option
when importing to SL. Otherwise your worn meshes become distorted!'''

RigProps_keep_edit_joints_description = \
'''Keep the Bone locations unchanged while removing the Joint data

Warning: When this option is set then the skeleton edits are preserved in Blender.
But any subsequent Slider Change resets the skeleton
regardless of the setting of this button!'''

RigProps_display_joint_values_description = \
'''List the modified Bone head locations (offsets).

If Heads, Tails and Values are all enabled:
For bones with head and tail modified, only the head data is shown'''

SceneProp_collada_export_with_joints_description = \
'''Export the reference skeleton with stored joint positions.
Important: When you disable this option
then the skeleton is exported unchanged (to transfer data to other tools)
The sliders must be set to the Neutral Shape in this case!

This option is not used when you export to Tool Exchange. '''

SceneProp_snap_control_to_rig_description = \
'''The Bone Snap direction to be used when storing the joint edits.

- Disabled: Snap the Deform Rig to the Control rig
- Enabled : Snap the Control Rig to the Deform Rig'''
