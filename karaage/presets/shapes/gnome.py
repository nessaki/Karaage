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

import bpy
import karaage
from karaage import shape, util

arm    = util.get_armature(bpy.context.object)

dict={'saddlebags_753': 41.0, 'hair_front_133': 0.0, 'tall_lips_653': 50.0, 'double_chin_8': 50.0, 'eyelid_inner_corner_up_880': 50.0, 'hair_taper_back_754': 80.0, 'low_septum_nose_759': 50.0, 'squash_stretch_head_647': 30.0, 'height_33': 0.0, 'attached_earlobes_22': 50.0, 'leg_length_692': 0.0, 'hair_sides_134': 0.0, 'ears_out_15': 50.0, 'hair_back_135': 0.0, 'square_jaw_17': 50.0, 'lip_width_155': 50.0, 'bulbous_nose_20': 50.0, 'leg_muscles_652': 68.0, 'cleft_chin_upper_13': 50.0, 'eye_spacing_196': 50.0, 'wide_nose_517': 14.0, 'high_cheek_bones_14': 50.0, 'puffy_lower_lids_765': 50.0, 'hair_taper_front_755': 51.0, 'hair_big_top_182': 49.0, 'hair_tilt_137': 56.0, 'torso_length_38': 71.0, 'head_shape_193': 76.0, 'side_fringe_131': 37.0, 'foot_size_515': 69.0, 'wide_eyes_24': 50.0, 'shoe_platform_width_508': 33.0, 'belly_size_157': 56.0, 'eyelid_corner_up_650': 50.0, 'lip_cleft_deep_764': 50.0, 'upturned_nose_tip_19': 50.0, 'broad_nostrils_4': 50.0, 'butt_size_795': 72.0, 'hair_rumpled_177': 100.0, 'big_brow_1': 50.0, 'body_fat_637': 25.0, 'hair_big_front_181': 0.0, 'nose_big_out_2': 66.0, 'wide_lip_cleft_25': 50.0, 'front_fringe_130': 48.0, 'wide_nose_bridge_27': 50.0, 'bulbous_nose_tip_6': 49.0, 'shoulders_36': 50.0, 'head_size_682': 72.0, 'hair_spiked_184': 7.0, 'pointy_ears_796': 50.0, 'arm_length_693': 49.0, 'hair_part_middle_140': 17.0, 'hip_length_842': 67.0, 'hair_volume_763': 0.0, 'noble_nose_bridge_11': 50.0, 'cleft_chin_5': 50.0, 'jowls_12': 50.0, 'sunken_cheeks_10': 50.0, 'hair_big_back_183': 0.0, 'love_handles_676': 42.0, 'hair_shear_front_762': 44.0, 'baggy_eyes_23': 50.0, 'thickness_34': 67.0, 'egg_head_646': 50.0, 'back_fringe_132': 0.0, 'big_ears_35': 50.0, 'eye_size_690': 62.0, 'eyelashes_long_518': 49.0, 'hair_sides_full_143': 74.0, 'upper_eyelid_fold_21': 50.0, 'hair_sweep_136': 64.0, 'puffy_upper_cheeks_18': 50.0, 'hair_part_left_142': 55.0, 'jaw_angle_760': 50.0, 'hip_width_37': 59.0, 'pigtails_785': 2.0, 'skirt_looseness_863': 33.0, 'neck_thickness_683': 60.0, 'hair_shear_back_674': 4.0}
shape.resetToDefault(arm)
shape.fromDictionary(arm,dict)
