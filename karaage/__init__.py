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

bl_info = {
    "name": "Karaage Bento",
    "author": "Nessaki",
    "version": ( 2, 333, 0 ),
    "blender": (2, 77, 0),
    "api": 36147,
    "location": "Add Menu, 3D View Properties, Property sections and Tools",
    "description": "Character creation & animation for SL and OpenSim",
    "show_expanded": True,
    "wiki_url":  "http://karaage.online/",
    "tracker_url": "https://discord.gg/4XfNvSfdM8",
    "category": "Object"}

import os, glob, string, gettext, re

if "bpy" in locals():
    import imp
    if "animation" in locals():
        imp.reload(animation)
    if "create" in locals():
        imp.reload(create)
    if "context_util" in locals():
        imp.reload(context_util)
    if "const" in locals():
        imp.reload(const)
    if "data" in locals():
        imp.reload(data)
    if "bind" in locals():
        imp.reload(bind)
    if "debug" in locals():
        imp.reload(debug)
    if "generate" in locals():
        imp.reload(generate)
    if "copyrig" in locals():
        imp.reload(copyrig)
    if "mesh" in locals():
        imp.reload(mesh)
    if "messages" in locals():
        imp.reload(messages)
    if "pannels" in locals():
        imp.reload(pannels)
    if "rig" in locals():
        imp.reload(rig)
    if "shape" in locals():
        imp.reload(shape)
    if "util" in locals():
        imp.reload(util)
    if "weights" in locals():
        imp.reload(weights)
    if "www" in locals():
        imp.reload(www)
else:
    import bpy
    from . import animation
    from . import context_util
    from . import const
    from . import create
    from . import data
    from . import bind
    from . import debug
    from . import generate
    from . import copyrig
    from . import mesh
    from . import messages
    from . import pannels
    from . import rig
    from . import shape
    from . import util
    from . import weights
    from . import www

from .pannels import PanelKaraageTool
from .create import set_karaage_materials
from .util   import Skeleton
from .const  import *

import bmesh, addon_utils
from bpy.types import Menu, Operator
from bpy.props import *
from bpy.utils import previews
from bl_operators.presets import AddPresetBase
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ExportHelper

from mathutils import Quaternion, Matrix, Vector
from math import sin, asin
import logging, importlib

translator = gettext.translation('karaage', LOCALE_DIR, fallback=True)
_ = translator.gettext

BLENDER_VERSION = 10000 * bpy.app.version[0] + 100 * bpy.app.version[1] +  bpy.app.version[2]

log = logging.getLogger('karaage.main')
updatelog = logging.getLogger('karaage.update')

global in_config
in_config = False
def init_log_level(context):
    global in_config
    in_config = True
    print("init log level")

    logger_list = context.window_manager.LoggerPropList
    logger_names = logging.Logger.manager.loggerDict.keys()
    logger_list.clear()

    prop = logger_list.add()
    prop.name = "root"
    prop.log_level = str(logging.getLogger().getEffectiveLevel())

    for name in logger_names:
        prop = logger_list.add()
        prop.name = name
        prop.log_level = str(logging.getLogger(name).getEffectiveLevel())

    in_config=False

def configure_log_level(self, context):
    global in_config
    if in_config:
        return

    logger = logging.getLogger() if self.name == 'root' else logging.getLogger(self.name)
    logger.setLevel(int(self.log_level))
    init_log_level(context)

class LoggerPropIndex(bpy.types.PropertyGroup):
    index = IntProperty(name="index")

class LoggerProp(bpy.types.PropertyGroup):
    log_level = EnumProperty(
    items=(
        (str(logging.DEBUG),    'Debug',    'Detailed Programmer Information\nEnable when requested by Support team'),
        (str(logging.INFO),     'Info',     'Detailed User Information to Console\nEnable when in need to see more details'),
        (str(logging.WARNING),  'Warning',  '(Default) Events which may or may not indicate an Issue\nUsually this is all you need'),
        (str(logging.ERROR),    'Error',    'Events which very likely need to be fixed by User'),
        (str(logging.CRITICAL), 'Critical', 'Events which certainly need care taking by the Support team')),
    name="Log Level",
    description=_("Log Level Settings"),
    default=str(logging.WARNING),
    update = configure_log_level)

class LoggerPropVarList(bpy.types.UIList):

    def draw_item(self,
                  context,
                  layout,
                  data,
                  item,
                  icon,
                  active_data,
                  active_propname
                  ):

        row = layout.row(align=True)
        row.alignment='LEFT'
        row.prop(item,"log_level", text='')
        row.label(text=item.name)

def installedAddonsCallback(scene, context):
    items=[]
    if addon_utils.check("karaage")[0]:
        items.append(('Karaage',   'Karaage', "Karaage Addon for Blender"))
        
    if addon_utils.check("sparkles")[0]:
        items.append(('Sparkles',   'Sparkles', "Sparkles Addon for Blender"))
        
    if addon_utils.check("primstar")[0]:
        items.append(('Primstar',   'Primstar', "Primstar Addon for Blender"))
    return items

def ui_complexity_callback(self, context):
    obj = context.active_object
    arm = util.get_armature(obj)
    complexity = int(self.ui_complexity)
    if complexity == UI_SIMPLE:
        pass #coming soon

def selectedAddonCallback(self, context):
    preferences = util.getAddonPreferences()
    info = preferences.addonVersion
    if preferences.productName   == 'Karaage':
        info = bl_info['version']
    elif preferences.productName == 'Sparkles':
        import sparkles
        info = sparkles.bl_info['version']
    elif preferences.productName == 'Primstar':
        import primstar
        info = primstar.bl_info['version']
    else:
        return
    version_string = "%s.%s.%s" % (info)
    preferences.addonVersion = version_string
    
if hasattr(bpy.types, "AddonPreferences"):

    from bpy.types import Operator, AddonPreferences
    from bpy.props import StringProperty, IntProperty, BoolProperty
    class Karaage(AddonPreferences):

        bl_idname = __name__

        exportImagetypeSelection = EnumProperty(
            items=(
                ('PNG', _('PNG'), _('Use PNG image file format for GENERATED images')),
                ('TARGA', _('TGA'), _('Use TARGA image file format for GENERATED images')),
                ('JPEG', _('JPG'), _('Use JPEG image file format for GENERATED images')),
                ('BMP', _('BMP'), _('Use BMP image file format for GENERATED images'))),
            name=_("Format"),
            description=_("Image File type"),
            default='PNG')

        import configparser
        config_file = os.path.join(CONFIG_DIR,"credentials.conf")
        config = configparser.ConfigParser()
        if not os.path.exists(config_file):

            config.add_section('credentials')
            if not os.path.exists(CONFIG_DIR):
               print("Create Karaage configuration folder")
               os.makedirs(CONFIG_DIR)
        else:
            print("Read the Addon credentials")
            config.read(config_file)

        log_level = EnumProperty(
            items=(
                ('DEBUG',    'Debug',    'Detailed Programmer Information\nEnable when requested by Support team'),
                ('INFO',     'Info',     'Detailed User Information to Console\nEnable when in need to see more details'),
                ('WARNING',  'Warning',  '(Default) Events which may or may not indicate an Issue\nUsually this is all you need'),
                ('ERROR',    'Error',    'Events which very likely need to be fixed by User'),
                ('CRITICAL', 'Critical', 'Events which certainly need care taking by the Support team')),
            name="Log Level",
            description=_("Log Level Settings"),
            default='WARNING',
            update = configure_log_level)
            
        _username = config.get("credentials","user", fallback="")
        _password = config.get("credentials","pwd",  fallback="")

        username       = StringProperty(
            name       = 'User',
            description=_("Not Used"),
            default    =_username)

        password       = StringProperty(
            name       = 'Pwd',
            subtype='PASSWORD',
            description=_("Not Used"),
            default    =_password)
            
        keep_cred       = BoolProperty(
            name        = "Keep Credentials",
            description = "Keep login Credentials on local file for reuse on next start of Blender",
            default     = _username != '')

        server       = StringProperty(
            description=_("Server"))
        page       = StringProperty(
            description=_("Page"))

        user       = StringProperty(
            description=_("User"))
        purchase       =  StringProperty(
            description=_("Your Account name on the  website"))
        version       =  StringProperty(
            description=_("Version"))

        update_status  = EnumProperty(
            items=(
                ('BROKEN', _('Broken'), _('We could not setup the Remote caller on your system.\nPlease visit the website and\ncheck manually for new updates.')),
                ('UNKNOWN', _('Unknown'), _('You need to Login at  at least Check for Updates to see your update status')),
                ('UPTODATE', _('Up to date'), _('You seem to have already installed the newest product version')),
                ('ONLINE', _('Up to date'), _('You have already installed the newest product version')),
                ('CANUPDATE', _('Can Update'), _('A newer product version is available (Please login to get the download)')),
                ('UPDATE', _('Update available'), _('A newer product version is available for Download')),
                ('ACTIVATE', _('Restart to Activate'), _('A new update has been installed, Press F8 or restart Blender to activate')),
                ('READY_TO_INSTALL', _('Update Ready to Install'), _('A new update has been downloaded and can now be installed'))),
            name=_("Update Status"),
            description=_("Update Status of your Product"),
            default='UNKNOWN')

        ui_complexity  = EnumProperty(
            items=(
                ('0', 'Basic', 'Show the most basic Karaage functions'),
                ('1', 'Advanced', 'Show the most useful Karaage functions'),
                ('2', 'Expert', 'Show expert features'),
                ('3', 'Experimental', 'Show New features, work in progress')),
                name="Addon Complexity",
            description="User Interface Complexity",
            default='0',
            update = ui_complexity_callback)

        initial_rig_mode = EnumProperty(
            items=(
                ('OBJECT', 'Object', 'Create Rig in Object Mode'),
                ('POSE', 'Pose', 'Create Rig in Pose Mode (use Pose&Animation Workflow)'),
                ('EDIT', 'Edit', 'Create Rig in Edit Mode (use Joint Edit Workflow)')),
                name="Initial Rig Mode",
            description="Initial Rig Interaction Mode after creating a new Karaage Rig",
            default='POSE')
            
        update_path = StringProperty(
            description=_("Path to updated Addon zip file"))

        forceImageType = BoolProperty(default=False, name=_("All"),
            description=_("Enforce selected image format on all exported images"))
        useImageAlpha  = BoolProperty(default=False, name=_("Use RGBA"),
            description=_("Use Alpha Channel if supported by selected image Format"))

        adaptive_iterations = IntProperty(default=10, min=0, max=100, name=_("Iteration Count"),
            description=_("Number of iterations used at maximum to adapt the sliders to the model's shape") )
        adaptive_tolerance = FloatProperty(name = _("Slider Precision %"),   min = 0.001, max = 100, default = 0.01,
            description=_("Maximum tolerance for adaptive sliders [0.001-100] %"))
        adaptive_stepsize = FloatProperty(name = _("Correction Stepsize %"), min = 0.001, max = 100, default = 20,
            description=_("Stepsize for corrections [0.001-100] %"))

        verbose  = BoolProperty(default=True, name=_("Display additional Help"),
            description=_("Enable display of help links in Panel headers"))

        rig_version_check  = BoolProperty(default=True, name=_("Rig Update Dialog"),
            description=_("Karaage should always be used with the newest rig.\nBy default Karaage checks if all rigs in a Blend file are up to date.\nDisable this option to permanently suppress this check.\nNote: We recommend you keep this option enabled!"))

        rig_edit_check  = BoolProperty(default=True, name=_("System Mesh Check"),
            description=_(Karaage_rig_edit_check_description))

        default_attach  = BoolProperty(default=True, name=_("Attach Sliders by Default"),
            description=_("if set, then sliders get attached by default, when binding a Custom Mesh"))

        enable_unsupported  = BoolProperty(default=False, name=_("Display Unsupported Export Options"),
            description=_("Show Export Options which are not (no longer) supported by Second Life."))

        maxFacePerMaterial = IntProperty(default=21844, min=0, name=_("Max tri-count per Material"),
            description= _("Reject export of meshes when the number of triangles\nin any material face (texture face) exceeds this number\n\nNote: The SL Importer starts behaving extremely odd\nwhen this count goes above 21844.\nSet to 0 for disabling the check (not recommended)"))

        ticketTypeSelection = EnumProperty( name='Ticket Type', default='bug', items =
            [
            ('bug', 'Bug', 'Bug'),
            ('feedback', 'Feedback', 'Feedback'),
            ('feature', 'Feature Request', 'Feature Request'),
            ]
        )

        productName     = EnumProperty( name = "Product", items = installedAddonsCallback, update = selectedAddonCallback )

        addonVersion    = StringProperty( name = "Addon",    default = "%s.%s.%s" % (bl_info['version']))
        blenderVersion  = StringProperty( name = "Blender",  default = (bpy.app.version_string))
        operatingSystem = StringProperty( name = "Plattform",default = (bpy.app.build_platform.decode("utf-8")))
        auto_adjust_ik_targets = BoolProperty(
                                     name = "Adjust IK Targets",
                                     default = True,
                                     description = "Automatically adjust the IK targets for Arms, legs and hinds when in Edit mode"
                                 )
        always_alter_restpose = BoolProperty(name = "Bind to Visual Pose", default = False,
            description = "Karaage binds to the T-Pose by default (recommended).\nSetting this option enforces a Bind to the visual pose.\nNote: Bind to visual pose disables the Karaage Appearance Sliders\nuntil you call the 'Alter to Rest Pose' operator (See documentation).")

        #
        #
        skeleton_file   = StringProperty( name = "Skeleton File", default = "avatar_skeleton_2.xml",
                                          description = "This file defines the Deform Skeleton\n"
                                                      + "This file is also used in your SL viewer. You find this file in:\n\n"
                                                      + "{Viewer Installation folder}/character/avatar_skeleton.xml\n\n"
                                                      + "You must make sure that the Definition file used in Karaage matches\n"
                                                      + "with the file used in your Viewer.\n\n"
                                                      + "When you enter a simple file name then Karaage reads the data its own lib subfolder\n"
                                        )
        lad_file        = StringProperty( name = "Lad File",      default = "avatar_lad_2.xml",
                                          description = "This file defines the Appearance Sliders\n"
                                                      + "This file is also used in your SL viewer. You find this file in:\n\n"
                                                      + "{Viewer Installation folder}/character/avatar_lad_2.xml\n\n"
                                                      + "You must make sure that the Definition file used in Karaage matches\n"
                                                      + "with the file used in your Viewer.\n\n"
                                                      + "When you enter a simple file name then Karaage reads the data its own lib subfolder\n"
                                        )        
        #
        target_system   = EnumProperty(
            items=(
                ('EXTENDED', 'SL Main',  "Create items for the Second Life Main Grid.\n"
                               +  "This setting takes care that your creations are working with all \n"
                               +  "officially supported Bones. (Note: This includes the new Bento Bones as well)"),
                ('BASIC',    'SL Legacy', "Create items using only the SL legacy bones.\n"
                               +  "This setting takes care that your creations only use\n"
                               +  "the Basic Boneset (26 bones and 26 Collision Vollumes).\n"
                               +  "Note: You probably must use this option for creating items for other worlds."),
            ),
            name="Default Target",
            description = "The System for which the items are created by default.\nNote: The new Bento Bones only work on Secondlife Aditi for now\n",
            default     = 'EXTENDED'
        )
        RigType = EnumProperty(
            items=(
                ('BASIC', 'Basic' , 'The Basic Rig supports only the old Bones.\nGood for Main grid and other Online Worlds like OpenSim, etc."'),
                ('EXTENDED', 'Extended'  , 'The Extended Rig supports new Bones for Face, Hands, Wings, and Tail.\nThe Extended Rig is only available on the Test Grid (Aditi) ')),
            name=_("Rig Type"),
            description= "The set of used Bones",
            default='BASIC')
        
        JointType = EnumProperty(
            items=(
            ('POS',   'Pos' ,    'Create a rig based on the pos values from the avatar skeleton definition\nFor making Cloth Textures for the System Character (for the paranoid user)'),
            ('PIVOT', 'Pivot'  , 'Create a rig based on the pivot values from the avatar skeleton definition\nFor Creating Mesh items (usually the correct choice)')
            ),
            name=_("Joint Type"),
            description= "SL supports 2 Skeleton Defintions.\n\n- The POS definition is used for the System Avatar (to make cloth).\n- The PIVOT definition is used for mesh characters\n\nAttention: You need to use POS if your Devkit was made with POS\nor when you make cloth for the System Avatar",
            default='PIVOT')

        show_panel_collada = BoolProperty(
            default=False, 
            name="Collada Panel",
            description="Show the Collada Export Panel in the Tool Shelf"
            )

        show_panel_appearance = BoolProperty(
            default=True, 
            name="Appearance Panel",
            description="Show the Appearance Slider Panel in the Tool Shelf"
            )

        def store_credentials(self):
            print("Storing configuration")
            cp = self.config
            print("Set credentials")

            if self.keep_cred:
                cp.set("credentials","user", self.username)
                cp.set("credentials","pwd", self.password)
            else:
                cp.remove_option("credentials","user")
                cp.remove_option("credentials","pwd")

            print("store credentials")
            with open(self.config_file, 'w+') as configfile:
                print("user:", cp.get("credentials","user", fallback="none"))
                cp.write(configfile)
                print("Done")
                
        def draw_create_panel(self, context, box):
        
            from . import SceneProp
            sceneProps = context.scene.SceneProp
            last_select = bpy.types.karaage_rig_presets_menu.bl_label
            row = box.row(align=True)

            row.menu("karaage_rig_presets_menu", text=last_select )
            row.operator("karaage.rig_presets_add", text="", icon='ZOOMIN')
            if last_select not in ["Rig Presets", "Presets"]:
                row.operator("karaage.rig_presets_update", text="", icon='FILE_REFRESH')
                row.operator("karaage.rig_presets_remove", text="", icon='ZOOMOUT').remove_active = True

            col = box.column(align=True)
            row = col.row(align=True)
            row.label(SceneProp.karaageMeshType[1]['name'])
            row.prop(sceneProps, "karaageMeshType",   text='')

            row = col.row(align=True)
            row.label(SceneProp.karaageRigType[1]['name'])
            row.prop(sceneProps, "karaageRigType",   text='')

            row = col.row(align=True)
            row.label(SceneProp.karaageJointType[1]['name'])
            row.prop(sceneProps, "karaageJointType",   text='')

        def draw(self, context):
            layout = self.layout

            split = layout.split(percentage=0.45)

            box = split.box()
            box.label(text="General Settings", icon="SCRIPTWIN")
            col = box.column(align=True)
            col.label("Initial Rig Mode after create")
            row = col.row(align=True)
            row.prop(self, "initial_rig_mode", expand=True)
            col = box.column(align=True)
            col.prop(self, "verbose")
            col.prop(self, "default_attach")
            col.prop(self, "enable_unsupported")
            col.prop(self, "rig_version_check")
            col.prop(self, "rig_edit_check")

            col.prop(self, "auto_adjust_ik_targets")

            row=col.row(align=True)
            row.alignment='RIGHT'
            row.label("Max Tris per Material", icon='MESH_DATA')
            row.alignment='LEFT'
            row.prop(self, "maxFacePerMaterial", text='')

            box = split.box()
            box.label(text="Character definitions", icon="SCRIPTWIN")
            col = box.column(align=True)
            col.prop(self, "target_system")            
            box.separator()
            self.draw_create_panel(context, box)

            split = layout.split(percentage=0.45)
            box=split.box()
            box.label("Links")
            col = box.column(align=True)
            col.operator("wm.url_open", text="Karaage Release Info ...", icon="URL").url=RELEASE_INFO
            col.operator("wm.url_open", text="Reference Guides ...", icon="URL").url=DOCUMENTATION
            col.operator("wm.url_open", text="Ticket System...", icon="URL").url=TICKETS

            box=split.box()
            box.alignment='RIGHT'
            irow = box.row(align=False)
            irow.alignment='RIGHT'
            irow.operator("wm.url_open", text='',icon='INFO').url=KARAAGE_DOWNLOAD

          

            layout.separator()
                        
            split = layout.split(percentage=0.45)
            
            box=split.box()
            box.label(text="Panel Visibility", icon='VISIBLE_IPO_ON')
            col = box.column()
            col.prop(self, "show_panel_collada", text="Show the Collada Panel")
            col.prop(self, "show_panel_appearance", text="Show the Appearance Panel")
            col.prop(self, "ui_complexity")
            
            box=split.box()
            box.label(text="Collada Export Options", icon="FILE_BLANK")
            col = box.column()
            col.prop(self, "exportImagetypeSelection", text='Image type', toggle=False, icon="IMAGE_DATA")
            t = "Use %s for all images" % self.exportImagetypeSelection
            col.prop(self, "forceImageType", text=t, toggle=False)
            col.prop(self, "useImageAlpha", toggle=False)

            layout.separator()          
            
            split = layout.split(percentage=0.45)
            box = split.box()
            box.label(text="Adaptive Sliders Control parameters", icon="SCRIPTWIN")
            col = box.column(align=True)
            col.prop(self,"adaptive_tolerance",  slider=True, toggle=False)
            col.prop(self,"adaptive_iterations", slider=True, toggle=False)
            col.prop(self,"adaptive_stepsize",   slider=True, toggle=False)

            box = split.box()
            col=box.column(align=True)
            col.label("Logging Configuration", icon='TEXT')
            col.template_list('LoggerPropVarList',
                                 'LoggerPropList',
                                 bpy.context.window_manager,
                                 'LoggerPropList',
                                 bpy.context.window_manager.LoggerIndexProp,
                                 'index',
                                 rows=5)

            if bpy.app.version_cycle != 'release':
                box = layout.box()
                box.label(text="Unsupported Blender release type '%s'" % (bpy.app.version_cycle), icon="ERROR")
                col = box.column(align=True)
                col.label(text = "Your Blender instance is in state '%s'." % (bpy.app.version_cycle), icon="BLANK1")
                col = col.column(align=True)
                col.label(text = "This Addon might not work in this context.", icon="BLANK1")
                col = col.column(align=True)
                col.label(text="We recommend to use an official release from Blender.org instead.", icon="BLANK1")

    class KaraageShowPrefs(Operator):
        bl_idname = "karaage.pref_show"
        bl_description = 'Display Karaage addons preferences'
        bl_label = "Karaage Preferences"
        bl_options = {'INTERNAL'}

        def execute(self, context):
            wm = context.window_manager

            mod = importlib.import_module(__package__)
            if mod is None:
                print("Karaage seems to be not enabled or broken in some way")
                return {'CANCELLED'}
            bl_info = getattr(mod, "bl_info", {})
            mod.bl_info['show_expanded'] = True
            context.user_preferences.active_section = 'ADDONS'
            wm.addon_search = bl_info.get("name", __package__)
            wm.addon_filter = bl_info.get("category", 'ALL')
            wm.addon_support = wm.addon_support.union({bl_info.get("support", 'COMMUNITY')})

            bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
            return {'FINISHED'}

class DownloadReload(bpy.types.Operator):
    bl_idname = "karaage.download_reload"
    bl_label  = "Reload Scripts"
    bl_description = "Reset Blender Python Modules (Like Pressing F8 or restarting Blender)"

    def execute(self, context):
        bpy.ops.script.reload()
        return {'FINISHED'}

class DownloadInstall(bpy.types.Operator):
    bl_idname = "karaage.download_install"
    bl_label  = "Check for Updates"
    bl_description = "Install the just downloaded Karaage Update"

    reset = BoolProperty(default=False, name=_("Reset"),
        description=_("Reset to not logged in"))

    filename_pattern  = re.compile('.*filename.*=\s*([^;]*);?.*', re.IGNORECASE)
    extension_pattern = re.compile('.*\.(zip|py)', re.IGNORECASE)

    def install(self, src):
        error_count = 0
        try:
            print ("Install from file",src)
            bpy.ops.wm.addon_install(overwrite=True,
                    target='DEFAULT',
                    filepath=src,
                    filter_folder=True,
                    filter_python=True,
                    filter_glob="*.py;*.zip")
            return 0
        except:
            print("Can not install ", src )
            self.report({'ERROR'},("Install to File was interrupted."))
            raise
            return 1

    def execute(self, context):
        props = util.getAddonPreferences()
        if self.reset:
            props.update_status='UNKNOWN'
            return {'FINISHED'}

        if props.update_status != 'READY_TO_INSTALL':
            return {'CANCELLED'}

        if not props.update_path:
            return {'CANCELLED'}

        if props.update_path:
            errcount = self.install(props.update_path)
        if errcount == 0:
            props.update_status='ACTIVATE'
            return {'FINISHED'}
        return {'CANCELLED'}

class DownloadReset(bpy.types.Operator):
    bl_idname = "karaage.download_reset"
    bl_label  = "Reset Download"
    bl_description = "Reset this panel to start over again"

    def execute(self, context):
        props = util.getAddonPreferences()
        props.update_status='UNKNOWN'
        return {'FINISHED'}

class DownloadUpdate(bpy.types.Operator):
    bl_idname = "karaage.download_update"
    bl_label  = "Check for Updates"
    bl_description = "Download Karaage Update from GitHub (Freezes Blender for ~1 minute, depending on your internet)"

    reset = BoolProperty(default=False, name=_("Reset"),
        description=_("Reset to not logged in"))

    filename_pattern  = re.compile('.*filename.*=\s*([^;]*);?.*', re.IGNORECASE)
    extension_pattern = re.compile('.*\.(zip|py)', re.IGNORECASE)

    def download(self, props):
        url = "http://"+props.server+props.page
        log.debug("Getting data from server [%s] on page [%s]..." % (props.server,props.page))
        log.debug("Calling URL [%s]" %  url)
        response, extension, filename = www.call_url(self, url)

        if response is None:
            log.error("Error while downloading: No valid Response from Server")
            return None
        elif filename is None or extension is None:
            log.warning("Got a response but something went wrong with the filename")
        else:
            log.debug("Got the download for file [%s] with extension [%s]" % (filename, extension) )

        path = None
        try:

            destination_folder = bpy.app.tempdir
            print("Write to [%s]" % destination_folder)

            path= os.path.join(destination_folder, filename)
            basedir = os.path.dirname(path)
            if not os.path.exists(basedir):
                os.makedirs(basedir)
            f = open(path, "wb")
            b = bytearray(10000)
            util.progress_begin(0,10000)
            while response.readinto(b) > 0:
                f.write(b)
                util.progress_update(1, absolute=False)
            util.progress_end()

            f.close()
        except:
            print("Can not store download to:", path)
            print("system info:", sys.exc_info())
            self.report({'ERROR'},("Download to File was interrupted."))
            path = None
        return path

    def execute(self, context):
        props = util.getAddonPreferences()
        if props.update_status != 'UPDATE':
            return {'CANCELLED'}

        props.update_path = self.download(props)
        if props.update_path:
            props.update_status = 'READY_TO_INSTALL'
            return {'FINISHED'}
        return {'CANCELLED'}

product_id_map = {
    "Karaage": 698,
    "Primstar": 700,
    "Sparkles": 702
}
        
class CreateReport(bpy.types.Operator):
    bl_idname = "karaage.send_report"
    bl_label  = "Create Report"
    bl_description = "Create a Report and send the data to the GitHub"

    def execute(self, context):
        
        return {'FINISHED'}

class CheckForUpdates(bpy.types.Operator):
    bl_idname = "karaage.check_for_updates"
    bl_label  = "Check for Updates"
    bl_description = "Check GitHub Repo for Karaage Updates\n\nNote: The Update Tool does not work for\nDevelopment Releases and Release Candidates."

    def execute(self, context):
        addonProps = util.getAddonPreferences()
        try:
            import xmlrpc.client
        except:
            print("xmlrpc: i can not configure the remote call to github.")
            print("Sorry, we can not provide this feature on your computer")
            addonProps.update_status = 'BROKEN'
            return {'CANCELLED'}

        service = xmlrpc.client.ServerProxy(XMLRPC_SERVICE)

        user            = addonProps.addonVersion
        pwd             = addonProps.addonVersion

        addon_version   = util.get_addon_version()
        blender_version = str(util.get_blender_revision())
        #
        product         = 'Karaage-2'

        dld=service.karaage.getPlugin(1,user, pwd, addon_version, blender_version, product)
        if dld[0] in  ['UPDATE','ONLINE']:
            addonProps.update_status = dld[0]
            addonProps.server        = dld[1]
            addonProps.page          = dld[2]
            addonProps.user          = dld[3]
            addonProps.purchase      = dld[4]
            addonProps.version       = dld[5]
            
            addonProps.store_credentials()

        else:
            addonProps.server        = ''
            addonProps.page          = ''
            addonProps.user          = ''
            addonProps.purchase      = ''
            addonProps.version       = ''

        if dld[0] in ['UNKNOWN','UPTODATE','CANUPDATE', 'UPDATE', 'ONLINE']:
            addonProps.update_status = dld[0]
            addonProps.version       = dld[5]
            return {'FINISHED'}
        else:
            addonProps.update_status = 'UNKNOWN'
            print("Error in CheckForUpdates: unknown status [",dld[0],"]")
            return {'CANCELLED'}

''' class PanelKaraageInfo(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label = _("Karaage %s.%s.%s" % (bl_info['version']))
    bl_idname = "karaage.custom_info"
    bl_category    = "Karaage"
    bl_options      = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        url = RELEASE_INFO + "?myversion=" + util.get_addon_version() + "&myblender=" + str(util.get_blender_revision())
        col = layout.column(align=True)
        col.operator("wm.url_open", text="Check for updates", icon="URL").url=url
'''

class KaraageMaterialProps(bpy.types.PropertyGroup):

    def type_changed(self, context):
        scn = context.scene
        ava = context.active_object
        set_karaage_materials(ava)

    types = [
            ('NONE',     'None',     'Default Material'),
            ('FEMALE',   'Female',   'Female Materials'),
            ('MALE',     'Male',     'Male Materials'),
            ('CUSTOM',   'Custom',   'Custom Materials'),
            ('TEMPLATE', 'Template', 'Template Materials'),
            ]

    type = EnumProperty(
        items       = types,
        name        = 'type',
        description = 'Material type',
        default     = 'NONE',
        update      = type_changed
    )

    unique = BoolProperty(
             name        = "unique",
             default     = False,
             description = "Make material unique",
             update      = type_changed)

class PanelAvatarMaterials(bpy.types.Panel):
    '''
    Creates a Panel in the scene context of the properties editor
    '''
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = 'object'
    bl_label       = "Avatar Materials"
    bl_idname      = "karaage.avatar_materials"
    bl_options      = {'DEFAULT_CLOSED'}
    bl_category    = "Skinning"

    def draw(self, context):

        obj = context.active_object

        layout = self.layout

        scn = context.scene

        row = layout.row()
        row.prop(obj.karaageMaterialProps, "type", expand=True)
        row.prop(obj.karaageMaterialProps, "unique")

    @classmethod
    def poll(self, context):
        '''
        This panel will only appear if the object has a
        Custom Property called "karaage" (value doesn't matter)
        '''
        obj = context.active_object
        scn = context.scene
        try:
            if "karaage" in obj or "avastar" in obj:

                currentmeshes = util.findKaraageMeshes(obj)
                if len(currentmeshes)>0:

                    return True
                else:

                    return False
        except TypeError:
            return False

def add_rig_preset(context, filepath):
    sceneProps  = context.scene.SceneProp
    file_preset = open(filepath, 'w')
    file_preset.write(
    "import bpy\n"
    "import karaage\n"
    "from karaage import shape, util\n"
    "\n"
    "sceneProps  = bpy.context.scene.SceneProp\n"
    )
    
    file_preset.write("sceneProps.karaageMeshType   = '%s'\n" % sceneProps.karaageMeshType)
    file_preset.write("sceneProps.karaageRigType    = '%s'\n" % sceneProps.karaageRigType)
    file_preset.write("sceneProps.karaageJointType  = '%s'\n" % sceneProps.karaageJointType)
    file_preset.close()

class KARAAGE_MT_rig_presets_menu(Menu):
    bl_idname = "karaage_rig_presets_menu"
    bl_label  = "Rig Presets"
    bl_description = "Rig Presets for the Karaage Rig\nHere you define configurations for creating Karaage Rigs.\nYou call your configurations from the the Footer of the 3DView\nNavigate to: Add -> Karaage -> ..."
    preset_subdir = os.path.join("karaage","rigs")
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset

class KaraageAddPresetRig(AddPresetBase, Operator):
    bl_idname = "karaage.rig_presets_add"
    bl_label = "Add Rig Preset"
    bl_description = "Create new Preset from current Panel settings"
    preset_menu = "karaage_rig_presets_menu"

    preset_subdir = os.path.join("karaage","rigs")

    def invoke(self, context, event):
        print("Create new Preset...")
        return AddPresetBase.invoke(self, context, event)

    def add(self, context, filepath):
        add_rig_preset(context, filepath)

class KaraageUpdatePresetRig(AddPresetBase, Operator):
    bl_idname = "karaage.rig_presets_update"
    bl_label = "Update Rig Preset"
    bl_description = "Update active Preset from current Panel settings"
    preset_menu = "karaage_rig_presets_menu"
    preset_subdir = os.path.join("karaage","rigs")

    def invoke(self, context, event):
        self.name = bpy.types.karaage_rig_presets_menu.bl_label
        print("Updating Preset", self.name)
        return self.execute(context)

    def add(self, context, filepath):
        add_rig_preset(context, filepath)

class KaraageRemovePresetRig(AddPresetBase, Operator):
    bl_idname = "karaage.rig_presets_remove"
    bl_label = "Remove Rig Preset"
    bl_description = "Remove last selected Preset from the list"
    preset_menu = "karaage_rig_presets_menu"
    preset_subdir = os.path.join("karaage","rigs")
    
def add_shape_preset(context, filepath):
    arm    = util.get_armature(context.object)
    pbones = arm.pose.bones

    file_preset = open(filepath, 'w')
    file_preset.write(
    "import bpy\n"
    "import karaage\n"
    "from karaage import shape, util\n"
    "\n"
    "arm    = util.get_armature(bpy.context.object)\n"
    "\n"
    )
    dict = shape.asDictionary(arm)
    file_preset.write("dict=" + str(dict) + "\n")
    file_preset.write("shape.resetToDefault(arm)\n")
    file_preset.write("shape.fromDictionary(arm,dict)\n")
    file_preset.close()

class KARAAGE_MT_shape_presets_menu(Menu):
    bl_idname = "karaage_shape_presets_menu"
    bl_label  = "Shape Presets"
    bl_description = "Shape Presets for the Karaage Rig"
    preset_subdir = os.path.join("karaage","shapes")
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset

class KaraageAddPresetShape(AddPresetBase, Operator):
    bl_idname = "karaage.shape_presets_add"
    bl_label = "Add Shape Preset"
    bl_description = "Create new Preset from current Slider settings"
    preset_menu = "karaage_shape_presets_menu"

    preset_subdir = os.path.join("karaage","shapes")

    def invoke(self, context, event):
        print("Create new Preset...")
        return AddPresetBase.invoke(self, context, event)

    def add(self, context, filepath):
        add_shape_preset(context, filepath)

class KaraageUpdatePresetShape(AddPresetBase, Operator):
    bl_idname = "karaage.shape_presets_update"
    bl_label = "Update Shape Preset"
    bl_description = "Store current Slider settings in last selected Preset"
    preset_menu = "karaage_shape_presets_menu"
    preset_subdir = os.path.join("karaage","shapes")

    def invoke(self, context, event):
        self.name = bpy.types.karaage_shape_presets_menu.bl_label
        print("Updating Preset", self.name)
        return self.execute(context)

    def add(self, context, filepath):
        add_shape_preset(context, filepath)

class KaraageRemovePresetShape(AddPresetBase, Operator):
    bl_idname = "karaage.shape_presets_remove"
    bl_label = "Remove Shape Preset"
    bl_description = "Remove last selected Preset from the list"
    preset_menu = "karaage_shape_presets_menu"
    preset_subdir = os.path.join("karaage","shapes")

class ObjectSelectOperator(bpy.types.Operator):
    bl_idname      = "karaage.object_select_operator"
    bl_label       = _("select")
    bl_description = _("Select this object as active Object")
    name = StringProperty()
    def execute(self, context):
        if self.name:
           ob = bpy.data.objects[self.name]
           if ob:
               bpy.context.object.select=False
               context.scene.objects.active = ob
               ob.select = True
               ob.hide   = False

        return{'FINISHED'}

class DisplayKaraageVersionOperator(bpy.types.Operator):
    bl_idname      = "karaage.display_version_operator"
    bl_label       = _("Karaage")
    bl_description = _("The version of Karaage that was used to create this Rig\n\n The first part of the version string is the Karaage Release\nThe part in parantheses () is the Rig_id\n\nNote: The Rig ID can be the same over several Karaage releases.")
    name = StringProperty()
    def execute(self, context):
        return{'FINISHED'}

class DisplayKaraageVersionMismatchOperator(bpy.types.Operator):
    bl_idname      = "karaage.version_mismatch"
    bl_label       = _("Version Mismatch")
    bl_description = _("You probably use a rig from an older Karaage. Click for details")
    msg = 'Version Mismatch|'\
        +  'DETAIL:\n'\
        +  'Your Rig has been made with a different version of Karaage.\n\n'\
        +  'Please note that a version mismatch could lead to broken functionality.\n'\
        +  'There is a good chance that your rig works, but to keep on the safe side\n'\
        +  'you may want to consider upgrading your rig\n\n'\
        +  'YOUR ACTION:\n'\
        +  'Upgrade your rig to the current Karaage version. If you do not know how to\n'\
        +  'do this, then please click on the Online Help button below.|workflow_upgrade_rig'

    def execute(self, context):
        util.ErrorDialog.dialog(self.msg, "INFO")
        return{'FINISHED'}

class DisplayKaraageRigVersionOperator(bpy.types.Operator):
    bl_idname      = "karaage.display_rigversion_operator"
    bl_label       = _("Karaage")
    bl_description = _("The version of Karaage that was used to create this Rig\n\n The first part of the version string is the Karaage Release\nThe part in parantheses () is the Rig_id\n\nNote: The Rig ID can be the same over several Karaage releases.")
    def execute(self, context):
        return{'FINISHED'}

class WeightAcceptedHint(bpy.types.Operator):
    bl_idname      = "karaage.weight_accept_hint"
    bl_label       = _("accepted")
    bl_description = _("This is the number of Vertex groups which will be exported as bone weightmaps")
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        return{'FINISHED'}

class WeightIgnoredHint(bpy.types.Operator):
    bl_idname      = "karaage.weight_ignore_hint"
    bl_label       = _("ignored")
    bl_description = _("This is the number of Vertex groups which are associated to non deform Bones. these groups will not be used as weight maps!")
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        return{'FINISHED'}

class ShapeTypeMorphHint(bpy.types.Operator):
    bl_idname      = "karaage.shape_type_morph_hint"
    bl_label       = _("Shape Type")
    bl_description = _('''This is a Morph slider
Affects Morph shapes on the System Avatar.
Has no effect on Custom Meshes.'''
    )
    bl_options = {'REGISTER', 'UNDO'}
    pid = StringProperty()
    def execute(self, context):
        arm=util.get_armature(context.object)
        D = arm.ShapeDrivers.DRIVERS.get(self.pid)[0]
        D['show'] = not D.get('show',False)
        return{'FINISHED'}

class ShapeTypeBoneHint(bpy.types.Operator):
    bl_idname      = "karaage.shape_type_bone_hint"
    bl_label       = _("Shape Type")
    bl_description = _('''This is a Bone Slider.
Affects Bone length on the System Avatar.
Affects Bone length on Custom Meshes.

Important: Expect to see almost equal results for System Avatar and Custom Meshes!'''
    )
    bl_options = {'REGISTER', 'UNDO'}
    pid = StringProperty()
    def execute(self, context):
        arm=util.get_armature(context.object)
        D = arm.ShapeDrivers.DRIVERS.get(self.pid)[0]
        D['show'] = not D.get('show',False)
        return{'FINISHED'}

class ShapeTypeExtendedHint(bpy.types.Operator):
    bl_idname      = "karaage.shape_type_extended_hint"
    bl_label       = _("Shape Type")
    bl_description = _('''This is an Extended Morph Slider
Affects Morph shapes on the System Avatar.
Affects Extended Bones on Custom Meshes.

Important: Expect to see very different results for System Avatar and Custom Meshes!'''
    )
    bl_options = {'REGISTER', 'UNDO'}
    pid = StringProperty()
    def execute(self, context):
        arm=util.get_armature(context.object)
        D = arm.ShapeDrivers.DRIVERS.get(self.pid)[0]
        D['show'] = not D.get('show',False)
        return{'FINISHED'}

class ShapeTypeFittedHint(bpy.types.Operator):
    bl_idname      = "karaage.shape_type_fitted_hint"
    bl_label       = _("Shape Type")
    bl_description = _('''This is a Fitted Mesh Slider
Affects Morph shapes on the System Avatar.
Affects Collision Volumes (Fitted Mesh bones) on Custom Meshes.

Important: Expect to see different results for System Avatar and Custom Meshes!'''
    )
    bl_options = {'REGISTER', 'UNDO'}
    pid = StringProperty()
    def execute(self, context):
        arm=util.get_armature(context.object)
        D = arm.ShapeDrivers.DRIVERS.get(self.pid)[0]
        D['show'] = not D.get('show',False)
        return{'FINISHED'}

class FittingBoneDeletePgroup(bpy.types.Operator):
    bl_idname      = "karaage.fitting_bone_delete_pgroup"
    bl_label       = _("Cleanup PGroup")
    bl_description = _("Delete Edited Weight distribution")
    
    bname  = StringProperty()

    def execute(self, context):
        obj = context.object
        armobj = obj.find_armature()
        omode = obj.mode if obj.mode != 'EDIT' else util.ensure_mode_is('OBJECT', object=obj)
        if not ( armobj and self.bname in armobj.data.bones):
            print("%s has no armature object using bone %s" % (obj.name, self.bname))
            return {'CANCELLED'}
            
        pgroup = weights.get_pgroup(obj, self.bname)
        if pgroup:
            pgroup.clear()
        
        percent = getattr(obj.FittingValues, self.bname)
        only_selected = False
        weights.set_fitted_strength(context, obj, self.bname, percent, only_selected, omode)
        util.enforce_armature_update(context.scene,armobj)
        util.ensure_mode_is(omode, object=obj)
        return{'FINISHED'}

class FittingBoneSelectedHint(bpy.types.Operator):
    bl_idname      = "karaage.fitting_bone_selected_hint"
    bl_label       = _("Shape Type")
    bl_description = _("Select the Bone associated to this slider")

    bone  = StringProperty()
    bone2 = StringProperty()
    add   = False

    def invoke(self, context, event):
        self.add = event.shift
        return self.execute(context)

    def execute(self, context):
        obj = context.object
        armobj = obj.find_armature()
        if not ( armobj and self.bone in armobj.data.bones):
            print("%s has no armature object using bone %s" % (obj.name, self.bone))
            return {'CANCELLED'}

        context.scene.objects.active = armobj
        original_mode = util.ensure_mode_is('POSE')
        dbone = armobj.data.bones[self.bone]

        partner_name = weights.get_bone_partner(self.bone)
        pbone = armobj.data.bones.get(partner_name, None) if partner_name else dbone

        if self.add:
            dbone.select = not dbone.select
            pbone.select = dbone.select
        else:
            pselect = not pbone.select
            dselect = not dbone.select
            for db in armobj.data.bones:
                db.select=False
            pbone.select = pselect
            dbone.select = not pselect

        ab = pbone if pbone.select else dbone if dbone.select else None
        if ab and ab != armobj.data.bones.active:
            armobj.data.bones.active = ab
            if ab.name in obj.vertex_groups:
                obj.vertex_groups.active_index=obj.vertex_groups[ab.name].index
            else:
                obj.vertex_groups.active_index=-1
        else:
            obj.vertex_groups.active_index=-1

        if self.bone2 in armobj.data.bones:
            armobj.data.bones[self.bone2].select = dbone.select

        util.ensure_mode_is(original_mode)

        context.scene.objects.active = obj
        original_mode = util.ensure_mode_is('EDIT')
        util.ensure_mode_is(original_mode)

        return{'FINISHED'}

class ResetShapeSectionOperator(bpy.types.Operator):
    bl_idname      = "karaage.reset_shape_section"
    bl_label       = _("Reset Section")
    bl_description = _("Reset Section values to SL Default")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        shape.recurse_call = True # Needed to avoid automatic rounding
        active = context.active_object
        omode = util.ensure_mode_is("OBJECT")
        try:
            obj = util.get_armature(active)
            for pid in shape.get_shapekeys(obj):
                if pid != "male_80":
                    D = obj.ShapeDrivers.DRIVERS[pid][0]
                    shape.setShapeValue(obj,pid,D['value_default'], D['value_min'], D['value_max'])
            shape.updateShape(self, context, scene=context.scene, refresh=True, msg="reset_shape_section")
            util.enforce_armature_update(context.scene, obj)
        finally:
            shape.recurse_call = False
            context.scene.objects.active = active
            util.ensure_mode_is(omode)
        return{'FINISHED'}

class ResetShapeValueOperator(bpy.types.Operator):
    bl_idname      = "karaage.reset_shape_slider"
    bl_label       = _("Reset Shape")
    bl_description = _("Reset Appearance Slider to SL Default")
    bl_options = {'REGISTER', 'UNDO'}

    pid = StringProperty()

    def execute(self, context):
        shape.recurse_call = True # Needed to avoid automatic rounding
        arms = {}
        active = context.active_object
        omode = util.ensure_mode_is("OBJECT")
        try:
            obj = util.get_armature(context.active_object)
            for pid in shape.get_shapekeys(obj):
                if self.pid==pid:
                    D = obj.ShapeDrivers.DRIVERS[pid][0]
                    shape.setShapeValue(obj,pid,D['value_default'], D['value_min'], D['value_max'])
            shape.updateShape(self, context, scene=context.scene, refresh=True, msg="reset_shape_slider")
            util.enforce_armature_update(context.scene, obj)
        finally:
            shape.recurse_call = False
            context.scene.objects.active = active
            util.ensure_mode_is(omode)
        return{'FINISHED'}

class ButtonLoadShapeUI(bpy.types.Operator):
    bl_idname = "karaage.load_shape_ui"
    bl_label = _("Load Appearance Sliders")
    bl_description = _("Load the Karaage Shape User Interface (Appearance Sliders)")

    def execute(self, context):
        try:
            arm = util.get_armature(context.object)
            rigType = arm.RigProps.RigType
            shape.initialize(rigType)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonPrintProps(bpy.types.Operator):
    '''
    Write out all the driver values. Currently there is no way to
    import a shape into OpenSim (or similar online worlds) other than manually setting the values
    '''
    bl_idname = "karaage.print_props"
    bl_label = _("Write Shape")
    bl_description = _("Write shape values into textblock")

    def execute(self, context):
        try:
            obj = util.get_armature(context.active_object)
            name = shape.printProperties(obj)
            self.report({'INFO'}, _("See %s textblock")%name)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonSaveProps(bpy.types.Operator):
    '''
    Write out all the driver values. Currently there is no way to
    import a shape into OpenSim (or similar online worlds) other than manually setting the values
    '''
    bl_idname = "karaage.save_props"
    bl_label = _("Save Shape")
    bl_description = _("Write Shape to file (as xml) or textblock (as txt)")

    filepath = bpy.props.StringProperty(subtype="FILE_PATH", default="")

    check_existing = BoolProperty(name=_("Check Existing"), description=_("Check and warn on overwriting existing files"), default=True)

    filter_glob = StringProperty(
                default="*.xml",
                options={'HIDDEN'},
                )

    def invoke(self, context, event):
        meshProps = bpy.context.scene.MeshProp
        if meshProps.save_shape_selection == 'DATA':
            return self.execute(context)
        else:

            try:
                avatarname = context.active_object.name
                name = bpy.path.clean_name(avatarname)
                name = bpy.path.clean_name(name)

                dirname = os.path.dirname(bpy.data.filepath)
                self.filepath = bpy.path.ensure_ext(os.path.join(dirname,name),".xml")

                wm = context.window_manager
                wm.fileselect_add(self) # will run self.execute()

            except Exception as e:
                util.ErrorDialog.exception(e)
            return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            meshProps = bpy.context.scene.MeshProp
            obj = util.get_armature(context.active_object)
            if meshProps.save_shape_selection == 'DATA':
                name = shape.printProperties(obj)
                self.report({'INFO'}, _("Shape saved to textblock %s")%name)
            else:
                name = shape.saveProperties(obj, self.filepath)
                self.report({'INFO'}, _("Shape saved to file %s")%name)
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonLoadProps(bpy.types.Operator):
    '''
    Load the shape from the xml file produced for debugging
    (usually: Advanced/Character/Character Tests/Appearance To XML)
    '''
    bl_idname = "karaage.load_props"
    bl_label =_("Load Shape")
    bl_description =_("Load Shape from file (xml)")

    filepath = StringProperty(name=_("File Path"), description=_("File path used for importing shape from xml"), maxlen=1024, default= "")

    def invoke(self, context, event):
        try:
            wm = context.window_manager

            wm.fileselect_add(self) # will run self.execute()
            return {'RUNNING_MODAL'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'RUNNING_MODAL'}

    def execute(self, context):
        try:
            armobj = util.get_armature(context.active_object)
            shape.loadProps(armobj, self.filepath)
            util.enforce_armature_update(context.scene, armobj)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonResetToSLRestPose(bpy.types.Operator):
    '''
    Reset all shape parameters to Second Life Restpose.
    '''
    bl_idname = "karaage.reset_to_restpose"
    bl_label =_("Neutral Shape")
    bl_options = {'REGISTER', 'UNDO'}
    bl_description=\
'''Reset Sliders to the SL Neutral Shape

Note: The appearance sliders take no effect in this mode.
Used when exporting Meshes with Joint Offsets,
or when importing a foreign Devkit
'''

    def execute(self, context):
        try:
            omode = util.ensure_mode_is("OBJECT")
            arm = util.get_armature(context.active_object)
            arm.RigProps.Hand_Posture = '0'
            shape.resetToRestpose(arm, context)
            util.ensure_mode_is(omode)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonResetToDefault(bpy.types.Operator):
    '''
    Reset all shape parameters to default values.
    '''
    bl_idname = "karaage.reset_to_default"
    bl_label =_("Default Shape")
    bl_description =_("Reset Mesh to the SL Default Shape\n\nUse this as the default Shape for making (and animating) characters\nNote: This is not Ruth but it is exactly the same as the Default Shape in SL.")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            omode = util.ensure_mode_is("OBJECT")
            arm = util.get_armature(context.active_object)
            arm.RigProps.Hand_Posture = '0'
            shape.resetToDefault(arm, context)
            util.ensure_mode_is(omode)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonDeleteAllShapes(bpy.types.Operator):
    '''
    Delete all Karaage default shapes.
    '''
    bl_idname = "karaage.delete_all_shapes"
    bl_label =_("Delete Karaage Meshes")
    bl_description =_("Delete all Karaage meshes from the Rig. (useful when you create your own full body character)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            armobj = util.get_armature(context.active_object)
            shape.delete_all_shapes(context, armobj)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonRefreshShape(bpy.types.Operator):
    '''
    Refresh all shape parameters.
    '''
    bl_idname = "karaage.refresh_character_shape"
    bl_label =_("Refresh Shape")
    bl_description =_("Recalculate Shape of active mesh after modifying weights for Collision Volume Bones")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):    

        arms, objs = util.getSelectedArmsAndObjs(context)

        util.set_disable_update_slider_selector(True)
        for obj in objs:
            arm = util.get_armature(obj)
            mode = obj.mode
            if obj.ObjectProp.slider_selector != 'NONE':

                shape.refresh_shape(arm, obj, graceful=False)

        util.set_disable_update_slider_selector(False)
        
        return{'FINISHED'}

IKMatchDetails = False
class ButtonIKMatchDetails(bpy.types.Operator):
    bl_idname = "karaage.ikmatch_display_details"
    bl_label = _("")
    bl_description = _("advanced: Hide/Unhide ik bone Rotations display")

    toggle_details_display = BoolProperty(default=False, name=_("Toggle Details"),
        description=_("Toggle Details Display"))

    def execute(self, context):
        global IKMatchDetails
        IKMatchDetails = not IKMatchDetails
        return{'FINISHED'}

class ButtonIKMatchAll(bpy.types.Operator):
    bl_idname = "karaage.ik_match_all"
    bl_label = _("Align IK to Pose")
    bl_description = _("Align IK bone Rotations of selected Limbs to the current Pose")
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(self, context):
        if context == None:
            msg = "karaage.ik_match_all: No context available while polling"
            raise util.Error(msg)

        ob = context.object
        if ob == None:
            msg = "karaage.ik_match_all: No context object available while polling"
            raise util.Error(msg)

        if ob.mode != 'POSE':
            msg = "karaage.ik_match_all: Context object [%s] is in[%s] mode (where POSE was needed)" % (ob.name, ob.mode)
            raise util.Error(msg)

        try:
            if "karaage" in context.active_object or "avastar" in context.active_object:
                return True
        except TypeError:
            msg = "Issues with context object: [%s]" % context.active_object
            raise util.Error(msg)

    def execute(self, context):
        armobj = context.object
        rig.apply_ik_orientation(context, armobj)
        return{'FINISHED'}

class PanelIKUI(bpy.types.Panel):
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label       =_("IK Controls")
    bl_idname      = "karaage.ik_ui"
    bl_category    = "Rigging"

    @classmethod
    def poll(self, context):
        if context.mode != 'POSE':
            return False
        else:
            try:
                if "karaage" in context.active_object or "avastar" in context.active_object:
                    return True
            except TypeError:
                return None

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        active = context.active_object
        arm    = util.get_armature(active) 
        col.prop(active.IKSwitches, "Show_All")

        #
        bones = set([b.name for b in bpy.context.object.pose.bones if b.bone.select or b.sync_influence])

        box = layout.box()
        box.label("Target Controls", icon='OUTLINER_DATA_ARMATURE')

        col = box.column(align=True)
        rig.create_ik_button(col.row(align=True), arm, B_LAYER_IK_HAND)
        rig.create_ik_button(col.row(align=True), arm, B_LAYER_IK_ARMS)
        rig.create_ik_button(col.row(align=True), arm, B_LAYER_IK_LEGS)
        rig.create_ik_button(col.row(align=True), arm, B_LAYER_IK_LIMBS)

        if active.IKSwitches.Show_All or not bones.isdisjoint(ALL_IK_BONES):
            col = box.column(align=True)
            if active.IKSwitches.Show_All or not bones.isdisjoint(LArmBones):
                try:
                    row = col.row(align=True)
                    con = rig.get_ik_constraint(active.pose.bones, 'ElbowLeft', "ikWristLeft")
                    if con:
                        row.prop(con, "influence", text = _('Left Arm'), slider=True)
                        props = row.operator("karaage.ik_apply", text='', icon='POSE_DATA')
                        props.limb='ARM'
                        props.symmetry='Left'
                except KeyError: pass
            if active.IKSwitches.Show_All or not bones.isdisjoint(RArmBones):
                try:
                    row = col.row(align=True)
                    con = rig.get_ik_constraint(active.pose.bones, 'ElbowRight', "ikWristRight")
                    if con:
                        row.prop(con, "influence", text = _('Right Arm'), slider=True)
                        props = row.operator("karaage.ik_apply", text='', icon='POSE_DATA')
                        props.limb='ARM'
                        props.symmetry='Right'
                except KeyError: pass
            if active.IKSwitches.Show_All or not bones.isdisjoint(LLegBones):
                try:
                    row = col.row(align=True)
                    con = rig.get_ik_constraint(active.pose.bones, 'KneeLeft', "ikAnkleLeft")
                    if con:
                        row.prop(con, "influence", text = _('Left Leg'), slider=True)
                        props = row.operator("karaage.ik_apply", text='', icon='POSE_DATA')
                        props.limb='LEG'
                        props.symmetry='Left'
                except KeyError: pass
            if active.IKSwitches.Show_All or not bones.isdisjoint(RLegBones):
                try:
                    row = col.row(align=True)
                    con = rig.get_ik_constraint(active.pose.bones, 'KneeRight', "ikAnkleRight")
                    if con:
                        row.prop(con, "influence", text = _('Right Leg'), slider=True)
                        props = row.operator("karaage.ik_apply", text='', icon='POSE_DATA')
                        props.limb='LEG'
                        props.symmetry='Right'
                except KeyError: pass

            if active.IKSwitches.Show_All or not bones.isdisjoint(LHindBones):
                try:
                    row = col.row(align=True)
                    con = rig.get_ik_constraint(active.pose.bones, 'HindLimb2Left', "ikHindLimb3Left")
                    if con:
                        row.prop(con, "influence", text = _('Left Hind'), slider=True)
                        props = row.operator("karaage.ik_apply", text='', icon='POSE_DATA')
                        props.limb='HIND'
                        props.symmetry='Left'
                except KeyError: pass

            if active.IKSwitches.Show_All or not bones.isdisjoint(RHindBones):
                try:
                    row = col.row(align=True)
                    con = rig.get_ik_constraint(active.pose.bones, 'HindLimb2Right', "ikHindLimb3Right")
                    if con:
                        row.prop(con, "influence", text = _('Right Hind'), slider=True)
                        props = row.operator("karaage.ik_apply", text='', icon='POSE_DATA')
                        props.limb='HIND'
                        props.symmetry='Right'
                except KeyError: pass

            if active.IKSwitches.Show_All or not bones.isdisjoint(RPinchBones):
                try:

                    col.prop(active.pose.bones['ikThumbSolverRight'],"pinch_influence", text = _('Right Pinch'), slider=True)
                except KeyError: pass
            if active.IKSwitches.Show_All or not bones.isdisjoint(LPinchBones):
                try:

                    col.prop(active.pose.bones['ikThumbSolverLeft'],"pinch_influence", text = _('Left Pinch'), slider=True)
                except KeyError: pass
            
            if active.IKSwitches.Show_All or not bones.isdisjoint(GrabBones):
                for symmetry in ["Right", "Left"]:
                    col.separator()
                    counter = 0
                    synced  = 0
                    for bone in [bone for bone in bones if bone in GrabBones and bone.endswith(symmetry)]:
                        row = col.row(align=True)
                        i = bone.index("Target")
                        part = bone[2:i]

                        solver = 'ik%sSolver%s' % (part, symmetry)
                        try:
                            bsolver = active.pose.bones[solver]
                            bbone   = active.pose.bones[bone]
                            con  = bsolver.constraints['Grab']
                            txt  = '%s %s' % (symmetry, part)
                            if bbone.sync_influence:
                                lock_icon = 'LOCKED'
                                synced += 1
                            else:
                                lock_icon = 'UNLOCKED'
            
                            row.prop(con, "influence", text = txt, slider=True)
                            row.prop(bbone, "sync_influence", text = '', icon = lock_icon, slider=True)
                            counter += 1
                        except KeyError:
                            raise
                            pass
                    if counter > 1 or synced > 1:
                       row=col.row(align=True)
                       row.prop(arm.RigProps,"IKHandInfluence%s" % symmetry, text="Combined", slider=True)

            row = col.row()
            row.label("FK")
            row=row.row()
            row.alignment = "RIGHT"
            row.label("IK")

        hasLLegBones = not bones.isdisjoint(LLegBones)
        hasRLegBones = not bones.isdisjoint(RLegBones)
        hasLegBones  = hasLLegBones or hasRLegBones

        hasRHindBones = not bones.isdisjoint(RHindBones)
        hasLHindBones = not bones.isdisjoint(LHindBones)
        hasHindBones = hasLHindBones or hasRHindBones

        hasLArmBones = not bones.isdisjoint(LArmBones)
        hasRArmBones = not bones.isdisjoint(RArmBones)
        hasArmBones  = hasLArmBones or hasRArmBones

        hasLPinchBones = not bones.isdisjoint(LPinchBones)
        hasRPinchBones = not bones.isdisjoint(RPinchBones)
        hasGrabBones   = not bones.isdisjoint(GrabBones)
        hasPinchBones  = hasLPinchBones or hasRPinchBones
        hasBones     = hasLegBones or hasArmBones or hasHindBones or hasPinchBones or hasGrabBones

        if active.IKSwitches.Show_All or hasLegBones:
            col = box.column(align=True)
            col.label(text=_("Foot Pivot:"))
            if active.IKSwitches.Show_All or hasLLegBones:
                try:
                    col.prop(active.IKSwitches, "IK_Foot_Pivot_L", text = _('Left Pivot'), slider=True)
                except KeyError: pass
            if active.IKSwitches.Show_All or hasRLegBones:
                try:
                    col.prop(active.IKSwitches, "IK_Foot_Pivot_R", text = _('Right Pivot'), slider=True)
                except KeyError: pass
            row = col.row()
            row.label(_("Heel"))
            row=row.row()
            row.alignment = "RIGHT"
            row.label(_("Toe"))

        if active.IKSwitches.Show_All or hasHindBones:
            col = box.column(align=True)
            col.label(text=_("Hind Foot Pivot:"))
            if active.IKSwitches.Show_All or hasLHindBones:
                try:
                    col.prop(active.IKSwitches, "IK_HindLimb3_Pivot_L", text = _('Left Hind Pivot'), slider=True)
                except KeyError: pass
            if active.IKSwitches.Show_All or hasRHindBones:
                try:
                    col.prop(active.IKSwitches, "IK_HindLimb3_Pivot_R", text = _('Right Hind Pivot'), slider=True)
                except KeyError: pass
            row = col.row()
            row.label(_("Heel"))
            row=row.row()
            row.alignment = "RIGHT"
            row.label(_("Toe"))

        if active.IKSwitches.Show_All or hasBones:
            icon = util.get_collapse_icon(IKMatchDetails)

            box = layout.box()
            box.label("Target align", icon='MOD_ARMATURE')
            row=box.row(align=True)
            row.operator(ButtonIKMatchDetails.bl_idname, text="", icon=icon)
            row.operator(ButtonIKMatchAll.bl_idname)
            if IKMatchDetails:
                if active.IKSwitches.Show_All or hasArmBones:
                    col = box.column(align=True)
                    col.label(text=_("IK Wrist Rotation:"))
                    if active.IKSwitches.Show_All or hasLArmBones:
                        try:
                            col2 = col.column(align=True)
                            col2.prop(active.IKSwitches, "IK_Wrist_Hinge_L", text = _('Hinge Left'), slider=True)
                            row = col2.row(align=True)
                            row.operator(ButtonIKWristLOrient.bl_idname)
                            row.operator(ButtonIKElbowTargetLOrient.bl_idname)
                        except KeyError: pass
                    if active.IKSwitches.Show_All or hasRArmBones:
                        try:
                            col2 = col.column(align=True)
                            col2.prop(active.IKSwitches, "IK_Wrist_Hinge_R", text = _('Hinge Right'), slider=True)
                            row = col2.row(align=True)
                            row.operator(ButtonIKWristROrient.bl_idname)
                            row.operator(ButtonIKElbowTargetROrient.bl_idname)
                        except KeyError: pass

                if active.IKSwitches.Show_All or hasLegBones:
                    col = box.column(align=True)
                    col.label(text="IK Ankle Rotation:")
                    if active.IKSwitches.Show_All or hasLLegBones:
                        try:
                            col2 = col.column(align=True)
                            col2.prop(active.IKSwitches, "IK_Ankle_Hinge_L", text = _('Hinge Left'), slider=True)
                            row = col2.row(align=True)
                            row.operator(ButtonIKHeelLOrient.bl_idname)
                            row.operator(ButtonIKKneeTargetLOrient.bl_idname)
                        except KeyError: pass
                    if active.IKSwitches.Show_All or hasRLegBones:
                        try:
                            col2 = col.column(align=True)
                            col2.prop(active.IKSwitches, "IK_Ankle_Hinge_R", text = _('Hinge Right'), slider=True)
                            row = col2.row(align=True)
                            row.operator(ButtonIKHeelROrient.bl_idname)
                            row.operator(ButtonIKKneeTargetROrient.bl_idname)
                        except KeyError: pass

                if active.IKSwitches.Show_All or hasHindBones:
                    col = box.column(align=True)
                    col.label(text="IK Hind Ankle Rotation:")
                    if active.IKSwitches.Show_All or hasLHindBones:
                        try:
                            col2 = col.column(align=True)
                            col2.prop(active.IKSwitches, "IK_HindLimb3_Hinge_L", text = _('Hinge Left'), slider=True)
                            row = col2.row(align=True)
                            row.operator(ButtonIKHindLimb3LOrient.bl_idname)
                            row.operator(ButtonIKHindLimb2TargetLOrient.bl_idname)
                        except KeyError: pass
                    if active.IKSwitches.Show_All or hasRHindBones:
                        try:
                            col2 = col.column(align=True)
                            col2.prop(active.IKSwitches, "IK_HindLimb3_Hinge_R", text = _('Hinge Right'), slider=True)
                            row = col2.row(align=True)
                            row.operator(ButtonIKHindLimb3ROrient.bl_idname)
                            row.operator(ButtonIKHindLimb2TargetROrient.bl_idname)
                        except KeyError: pass

        box = layout.box()
        box.label("Chain Controls", icon='OUTLINER_OB_ARMATURE')

        limbBones = util.sym(['Shoulder.','Elbow.','Wrist.','Knee.','Ankle.','Foot.','Toe.', 'Head', 'Neck', 'Chest', 'Spine4', 'Spine3', 'Spine2', 'Spine1', 'Torso'])
        activebone = context.active_pose_bone
        if activebone and activebone.bone.select:
            try:
                con = activebone.constraints.get('TargetlessIK')
                if not con:
                    return

                if con.use_tail:
                    ii = con.chain_count-2
                else:
                    ii = con.chain_count-1

                chainend = rig.get_bone_recursive(activebone, ii)
                endname = chainend.name

                col = box.column(align=True)
                row = col.row(align=True)
                row.label(text=activebone.name)
                row.label(text='', icon='ARROW_LEFTRIGHT')
                row.label(text=endname)

                col = box.column(align=True)
                row = col.row(align=True)
                row2 = row.row(align=True)
                row2.operator(ButtonChainParent.bl_idname)
                if activebone.parent==chainend:
                    row2.enabled=False

                row2 = row.row(align=True)
                row2.operator(ButtonChainLimb.bl_idname)
                if activebone.name not in limbBones:
                    row2.enabled = False

                row2 = row.row(align=True)
                row2.operator(ButtonChainCOG.bl_idname)
                if chainend.name=="COG":
                    row2.enabled=False

                row = col.row(align=True)
                row2=row.row(align=True)
                row2.operator(ButtonChainLess.bl_idname)
                if activebone.parent==chainend:
                    row2.enabled=False

                row2=row.row(align=True)
                row2.operator(ButtonChainMore.bl_idname)
                if chainend.name=="COG":
                    row2.enabled=False

                col.label(_('Chain tip movement:'))
                row = col.row(align=True)
                row.operator(ButtonChainClamped.bl_idname)
                row.operator(ButtonChainFree.bl_idname)

                col = box.column(align=False)
                col.prop(con,"influence")
            except (AttributeError, IndexError, KeyError):
                raise
                pass

class PanelRigUI(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label =_("Rig Controls")
    bl_idname = "karaage.rig_ui"
    bl_category    = "Rigging"

    @classmethod
    def poll(self, context):
        if context.mode != 'POSE':
            return False
        else:
            try:
                if "karaage" in context.active_object or "avastar" in context.active_object:
                    return True
            except TypeError:
                return None

    def draw_inherit_rot(self, armobj, col, child, parent, label):
        try:
            split = col.split(percentage=0.5, align=True)
            split.alignment = 'RIGHT'
            split.label(_(label))
            row = split.row(align=True)
            row.prop(armobj.data.bones[child], "use_inherit_rotation", text = '', icon='LINKED', toggle=True)
            row.label(_(parent))
        except KeyError: pass

    def draw(self, context):
        layout = self.layout

        active   = context.active_object
        meshProp = context.scene.MeshProp
        bones    = set([b.name for b in bpy.context.selected_pose_bones])

        box = layout.box()
        box.label(_('Rotation controls'), icon='FILE_REFRESH')
        row = box.row(align=True)
        split = row.split(percentage=0.55, align=True)
        split.label(_('Rotation Limits:'))
        split.prop(meshProp, "allBoneConstraints", text=_('All bones'), toggle=False)

        current_state, set_state = SLBoneLockRotationLimitStates(active, context)
        if current_state != '':
            row = box.row(align=True)

            if current_state == "Some limits":
                lock   = "Enable"
                unlock = "Disable"
            else:
                lock = set_state
                unlock = set_state

            if current_state != "No limits":
                row.operator(ButtonUnsetRotationLimits.bl_idname, text=unlock, icon="UNLOCKED").all=meshProp.allBoneConstraints
            if current_state != "All limits":
                row.operator(ButtonSetRotationLimits.bl_idname, text=lock, icon="LOCKED").all=meshProp.allBoneConstraints

        show_all = active.IKSwitches.Show_All
        if show_all or not bones.isdisjoint(set(['Head', 'Neck', 'Chest', 'Torso','ShoulderLeft','ShoulderRight'])):
            col = box.column(align=True)
            col.label(text="Inherit Rotation")
            if show_all or not bones.isdisjoint(set(['Head'])):
                self.draw_inherit_rot(active, col, 'Head', 'Neck', 'Head')
            if show_all or not bones.isdisjoint(set(['Neck'])):
                self.draw_inherit_rot(active, col, 'Neck', 'Chest', 'Neck')
            if show_all or not bones.isdisjoint(set(['Chest'])):
                self.draw_inherit_rot(active, col, 'Chest', 'Torso', 'Chest')
            if show_all or not bones.isdisjoint(set(['ShoulderLeft'])):
                self.draw_inherit_rot(active, col, 'ShoulderLeft', 'Collar(L)', 'Shoulder(L)')
            if show_all or not bones.isdisjoint(set(['ShoulderRight'])):
                self.draw_inherit_rot(active, col, 'ShoulderRight', 'Collar(R)', 'Shoulder(R)')

        if "Chest" in active.data.bones and "Torso" in active.data.bones:
            box = layout.box()
            box.label(text=_("Breathing:"), icon='BOIDS')
            col = box.column(align=True)
            row = col.row(align=True)
            row.operator(ButtonBreatheIn.bl_idname)
            row.operator(ButtonBreatheOut.bl_idname)

class ButtonEnableEyeTarget(bpy.types.Operator):
    bl_idname = "karaage.eye_target_enable"
    bl_label =_("Eye Targets")
    bl_description =_("Enable Eye Targets")

    def execute(self, context):
        active = context.active_object
        arm = util.get_armature(active)
        rig.setEyeTargetInfluence(arm)
        return {'FINISHED'}

class ButtonEnableIK(bpy.types.Operator):
    bl_idname = "karaage.ik_enable"
    bl_label = "IK"
    bl_description = "Enable IK"
    
    def toggle_ik_influence(self, arm, switch, bname):
        switch = not switch
        influence = 1.0 if switch else 0

        ButtonEnableIK.set_ik_influence(arm, influence, bname)

        return switch

    @staticmethod    
    def set_ik_influence(arm, influence, bname):

        bleft = arm.pose.bones.get(bname+'Left', None)
        if bleft:
            con = bleft.constraints.get('IK',None)
            if con:
                con.influence = influence
            else:
                log.warning("Can not find an 'IK' constraint on %s" % bleft.name)
        else:
            log.info("Ignore IK for missing bone %s" % bname+'Left')

        bright = arm.pose.bones.get(bname+'Right', None)
        if bright:
            con = bright.constraints.get('IK', None)
            if con:
                con.influence = influence
            else:
                log.warning("Can not find an 'IK' constraint on %s" % bright.name)
        else:
            log.info("Ignore IK for missing bone %s" % bname+'Right')

        return

class ButtonEnableArmsIK(ButtonEnableIK):
    bl_idname = "karaage.ik_arms_enable"
    bl_label =_("IK Arms")
    bl_description =_("Enable IK for Arms")

    enable_ik = BoolProperty (
        default = False,
        name = "Enable",
        description = "Enable IK"
    )

    def execute(self, context):

        active = context.active_object
        arm = util.get_armature(active)
        if self.enable_ik:
            arm.IKSwitches.Enable_Arms = True
            ButtonEnableIK.set_ik_influence(arm, 1.0, 'Elbow')
        else:
            arm.IKSwitches.Enable_Arms = self.toggle_ik_influence(arm, arm.IKSwitches.Enable_Arms, 'Elbow')
        return{'FINISHED'}

class ButtonEnableLegsIK(ButtonEnableIK):
    bl_idname = "karaage.ik_legs_enable"
    bl_label =_("IK Legs")
    bl_description =_("Enable IK for Legs")

    enable_ik = BoolProperty (
        default = False,
        name = "Enable",
        description = "Enable IK"
    )

    def execute(self, context):
        active = context.active_object
        arm = util.get_armature(active)
        if self.enable_ik:
            arm.IKSwitches.Enable_Legs = True
            ButtonEnableIK.set_ik_influence(arm, 1.0, 'Knee')
        else:
            arm.IKSwitches.Enable_Legs = self.toggle_ik_influence(arm, arm.IKSwitches.Enable_Legs, 'Knee')
        return{'FINISHED'}

class ButtonEnableLimbsIK(ButtonEnableIK):
    bl_idname = "karaage.ik_limbs_enable"
    bl_label =_("IK Legs")
    bl_description =_("Enable IK for Limbs")

    enable_ik = BoolProperty (
        default = False,
        name = "Enable",
        description = "Enable IK"
    )

    def execute(self, context):
        active = context.active_object
        arm = util.get_armature(active)
        if self.enable_ik:
            arm.IKSwitches.Enable_Limbs = True
            ButtonEnableIK.set_ik_influence(arm, 1.0, 'HindLimb2')
        else:
            arm.IKSwitches.Enable_Limbs = self.toggle_ik_influence(arm, arm.IKSwitches.Enable_Limbs, 'HindLimb2')
        return{'FINISHED'}

class ButtonApplyIK(bpy.types.Operator):
    bl_idname = "karaage.ik_apply"
    bl_label =_("Apply to FK Rig")
    bl_description =_("Apply IK pose to FK Rig")

    limb = EnumProperty(
        items=(
            ('NONE', 'None', 'None'),
            ('HAND', 'Hand', 'Bake Hand Bones IK to FK'),
            ('ARM' , 'Arm',  'Bake Arm  Bones IK to FK'),
            ('LEG' , 'Leg',  'Bake Leg  Bones IK to FK'),
            ('HIND' , 'Hind',  'Bake Hind  Bones IK to FK')),
        name = "Limb",
        description = "Which Limb shall be baked from IK to FK",
        default='NONE')
        
    symmetry = EnumProperty(
        items=(
            ('Left', 'None', 'None'),
            ('Right', 'Hand', 'Bake Hand Bones IK to FK'),
            ('BOTH' , 'Arm',  'Bake Arm  Bones IK to FK')),
        name=_("Symmetry"),
        description=_("Which side of the Skeleton shall be baked from IK to FK"),
        default='BOTH')

    def execute(self, context):
        active = context.active_object
        arm = util.get_armature(active)

        if   self.limb == 'ARM':
            bones = LArmBones if self.symmetry == 'Left' else RArmBones
            for name in bones:
                arm.pose.bones[name].bone.select=True
        elif self.limb == 'LEG':
            bones = LLegBones if self.symmetry == 'Left' else RLegBones
            for name in bones:
                arm.pose.bones[name].bone.select=True
        elif self.limb == 'LIMB':
            bones = LHindBones if self.symmetry == 'Left' else RHindBones
            for name in bones:
                arm.pose.bones[name].bone.select=True
        elif self.limb == 'HAND':
            hand_ik_bones = [b.name for b in arm.pose.bones if b.name.startswith("ik") and "Target" in b.name]
            for name in hand_ik_bones:
                part = name[2:name.index("Target")]
                if part in ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']:
                    sym = "Left" if name.endswith("Left") else "Right"
                    if sym == self.symmetry or self.symmetry == 'BOTH':
                        for index in range(1,4):
                            name = "Hand%s%d%s" % (part, index, sym)
                            arm.pose.bones[name].bone.select=True

        bpy.ops.pose.visual_transform_apply()

        return{'FINISHED'}

def set_hand_fk_contraints_status(pbones, part, symmetry, mute):
    for index in range (1,4):
        name = "Hand%s%d%s" % (part,index,symmetry)
        pbone = pbones[name] if name in pbones else None
        if pbone:
            for con in pbone.constraints:
               if con.type in ["LIMIT_ROTATION", "COPY_ROTATION"]:
                   con.mute=mute

def update_hand_ik_type(self, context):
    try:
        state = self.Enable_Hands

        active = context.active_object
        arm    = util.get_armature(active)
        pbones = arm.pose.bones

        for part in ["Thumb", "Index", "Middle", "Ring", "Pinky"]:
            for symmetry in ["Right","Left"]:
                bone_name = "ik%sSolver%s" % (part,symmetry)
                solver    = pbones[bone_name]
                if state in ['NONE', 'FK']:
                    arm.data.layers[B_LAYER_IK_HAND] = False
                    set_hand_fk_contraints_status(pbones, part, symmetry, mute = state == 'NONE')
                    solver.constraints['Grab'].mute = True
                    if part in ["Thumb", "Index"]:
                        solver.constraints['Pinch'].mute = True
                else:
                    arm.data.layers[B_LAYER_IK_HAND] = True
                    set_hand_fk_contraints_status(pbones, part, symmetry, mute=True)
                    solver.constraints['Grab'].mute = False
                    if part in ["Thumb", "Index"]:
                        solver.constraints['Pinch'].mute = False
    except:
        pass # probably no Hand ik defined for this rig

class ButtonIKWristLOrient(bpy.types.Operator):
    bl_idname = "karaage.ik_wrist_l_orient"
    bl_label =_("Match Left")
    bl_description =_("Match IK to left wrist")

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKWristOrientation(context, arm, 'Left')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKElbowTargetLOrient(bpy.types.Operator):
    bl_idname = "karaage.ik_elbowtarget_l_orient"
    bl_label =_("Set Target")
    bl_description =_("Reset Left ElbowTarget")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKElbowTargetOrientation(context, arm, 'Left')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKWristROrient(bpy.types.Operator):
    bl_idname = "karaage.ik_wrist_r_orient"
    bl_label =_("Match Right")
    bl_description =_("Match IK to right wrist")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKWristOrientation(context, arm, 'Right')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKElbowTargetROrient(bpy.types.Operator):
    bl_idname = "karaage.ik_elbowtarget_r_orient"
    bl_label =_("Set Target")
    bl_description =_("Reset Right ElbowTarget")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKElbowTargetOrientation(context, arm, 'Right')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKHeelLOrient(bpy.types.Operator):
    bl_idname = "karaage.ik_heel_l_orient"
    bl_label =_("Match Left")
    bl_description =_("Match IK to left foot")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKAnkleOrientation(context, arm, 'Left')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKKneeTargetLOrient(bpy.types.Operator):
    bl_idname = "karaage.ik_kneetarget_l_orient"
    bl_label =_("Set Target")
    bl_description =_("Reset Left KneeTarget")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKKneeTargetOrientation(context, arm, 'Left')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKHeelROrient(bpy.types.Operator):
    bl_idname = "karaage.ik_heel_r_orient"
    bl_label =_("Match Right")
    bl_description =_("Match IK to right foot")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKAnkleOrientation(context, arm, 'Right')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKKneeTargetROrient(bpy.types.Operator):
    bl_idname = "karaage.ik_kneetarget_r_orient"
    bl_label =_("Set Target")
    bl_description =_("Reset Right KneeTarget")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKKneeTargetOrientation(context, arm, 'Left')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKHindLimb3LOrient(bpy.types.Operator):
    bl_idname = "karaage.ik_hindlimb3_l_orient"
    bl_label =_("Match Left")
    bl_description =_("Match IK to left Hind foot")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKHindLimb3Orientation(context, arm, 'Left')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKHindLimb2TargetLOrient(bpy.types.Operator):
    bl_idname = "karaage.ik_hindlimb2target_l_orient"
    bl_label =_("Set Target")
    bl_description =_("Reset Left Hind Target")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKHindLimb2TargetOrientation(context, arm, 'Left')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKHindLimb3ROrient(bpy.types.Operator):
    bl_idname = "karaage.ik_hindlimb3_r_orient"
    bl_label =_("Match Right")
    bl_description =_("Match IK to right Hind foot")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKHindLimb3Orientation(context, arm, 'Right')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonIKHindLimb2TargetROrient(bpy.types.Operator):
    bl_idname = "karaage.ik_hindlimb2target_r_orient"
    bl_label =_("Set Target")
    bl_description =_("Reset Right Hind Target")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            obj = context.object
            arm = util.get_armature(obj)
            rig.setIKHindLimb2TargetOrientation(context, arm, 'Right')
        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonChainMore(bpy.types.Operator):
    bl_idname = "karaage.chain_more"
    bl_label =_("More")
    bl_description =_("Increase the IK chain length")

    def execute(self, context):
        try:
            activebone = context.active_pose_bone
            try:
                con = activebone.constraints['TargetlessIK']
                if con.use_tail:
                    parents = activebone.parent_recursive[con.chain_count-1:]
                else:
                    parents = activebone.parent_recursive[con.chain_count:]
                for idx, parent in enumerate(parents):
                    if parent.name == 'Origin':

                        break
                    if parent.lock_ik_x and parent.lock_ik_y and parent.lock_ik_z:

                        continue
                    con.chain_count += idx + 1
                    break
            except AttributeError:
                pass

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonChainLess(bpy.types.Operator):
    bl_idname = "karaage.chain_less"
    bl_label =_("Less")
    bl_description =_("Decrease the IK chain length")

    def execute(self, context):
        try:

            activebone = context.active_pose_bone
            try:
                con = activebone.constraints['TargetlessIK']
                if con.use_tail:
                    parents = activebone.parent_recursive[:con.chain_count-2]
                else:
                    parents = activebone.parent_recursive[:con.chain_count-1]
                parents.reverse()
                for idx, parent in enumerate(parents):
                    if parent.lock_ik_x and parent.lock_ik_y and parent.lock_ik_z:

                        continue
                    con.chain_count -= idx + 1
                    break
            except AttributeError:
                pass

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonChainCOG(bpy.types.Operator):
    bl_idname = "karaage.chain_cog"
    bl_label =_("COG")
    bl_description =_("Increase the IK chain length to COG")

    def execute(self, context):
        try:
            obj = context.active_object

            activebone = context.active_pose_bone
            try:
                for ii,bone in enumerate(activebone.parent_recursive):
                    if bone.name == 'COG':
                        break
                con = activebone.constraints['TargetlessIK']
                if con.use_tail:
                    con.chain_count = ii+2
                else:
                    con.chain_count = ii+1

            except AttributeError:
                pass

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonChainParent(bpy.types.Operator):
    bl_idname = "karaage.chain_parent"
    bl_label =_("Parent")
    bl_description =_("Decrease the IK chain length to parent")

    def execute(self, context):
        try:
            obj = context.active_object

            activebone = context.active_pose_bone
            try:
                con = activebone.constraints['TargetlessIK']
                if con.use_tail:
                    con.chain_count = 2
                else:
                    con.chain_count = 1
                if activebone.parent.name in util.sym(['CollarLink.']):

                    con.chain_count += 1
                elif activebone.parent.name in util.sym(['HipLink.']):

                    con.chain_count += 2
                elif activebone.parent.name in util.sym(['Pelvis']):

                    con.chain_count += 1
            except AttributeError:
                pass

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonChainLimb(bpy.types.Operator):
    bl_idname = "karaage.chain_limb"
    bl_label =_("Limb")
    bl_description =_("Set the IK chain length to base of limb")

    def execute(self, context):
        try:
            LArmBones = set(['CollarLeft','ShoulderLeft','ElbowLeft','WristLeft'])
            RArmBones = set(['CollarRight','ShoulderRight','ElbowRight','WristRight'])
            LLegBones = set(['HipLeft','KneeLeft','AnkleLeft','FootLeft','ToeLeft'])
            RLegBones = set(['HipRight','KneeRight','AnkleRight','FootRight','ToeRight'])

            activebone = context.active_pose_bone
            try:
                con = activebone.constraints['TargetlessIK']

                if activebone.name in LArmBones:

                    for ii,bone in enumerate(activebone.parent_recursive):
                        if bone.name == 'CollarLeft':
                            break
                    if con.use_tail:
                        con.chain_count = ii+2
                    else:
                        con.chain_count = ii+1
                if activebone.name in RArmBones:

                    for ii,bone in enumerate(activebone.parent_recursive):
                        if bone.name == 'CollarRight':
                            break
                    if con.use_tail:
                        con.chain_count = ii+2
                    else:
                        con.chain_count = ii+1
                if activebone.name in LLegBones:

                    for ii,bone in enumerate(activebone.parent_recursive):
                        if bone.name == 'HipLeft':
                            break
                    if con.use_tail:
                        con.chain_count = ii+2
                    else:
                        con.chain_count = ii+1
                if activebone.name in RLegBones:

                    for ii,bone in enumerate(activebone.parent_recursive):
                        if bone.name == 'HipRight':
                            break
                    if con.use_tail:
                        con.chain_count = ii+2
                    else:
                        con.chain_count = ii+1

            except AttributeError:
                pass

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonChainFree(bpy.types.Operator):
    bl_idname = "karaage.chain_free"
    bl_label =_("Free")
    bl_description =_("Configure so chain tip moves as part of chain")

    def execute(self, context):
        try:
            activebone = context.active_pose_bone
            try:
                con = activebone.constraints['TargetlessIK']
                m = activebone.matrix.copy()
                if con.use_tail == False:
                    con.chain_count = con.chain_count+1
                con.use_tail = True

                context.active_bone.use_inherit_rotation = True
                context.scene.update()
                activebone.matrix = m

            except AttributeError:
                pass

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonChainClamped(bpy.types.Operator):
    bl_idname = "karaage.chain_clamped"
    bl_label =_("Clamped")
    bl_description =_("Configure so chain tip moves as if clamped to current orientation")

    def execute(self, context):
        try:
            activebone = context.active_pose_bone
            try:
                con = activebone.constraints['TargetlessIK']
                m = activebone.matrix.copy()
                if con.use_tail == True:
                    con.chain_count = con.chain_count-1
                con.use_tail = False

                context.active_bone.use_inherit_rotation = False
                context.scene.update()
                activebone.matrix = m

            except AttributeError:
                pass

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

def SLBoneLockRotationLimitStates(armobj, context):
    all = context.scene.MeshProp.allBoneConstraints
    if all:
        bones = armobj.pose.bones
    else:
        bones = context.selected_pose_bones
    try:
        c = 'LIMIT_ROTATION'
        limit_count = 0
        free_count  = 0
        part_count  = 0

        if len(bones) == 0:
            return '',''

        for b in bones:
            for c in b.constraints:
                if c.type =='LIMIT_ROTATION':
                    if c.influence == 1:
                        limit_count += 1
                    elif c.influence == 0:
                        free_count += 1
                    else:
                        part_count +=1

        if free_count==0 and part_count == 0:
            return 'All limits', 'Disable rotation limits'
        if limit_count == 0 and part_count == 0:
            return 'No limits', 'Enable rotation limits'
        return 'Some limits', ''
    except:
        pass
    return '',''

class ButtonSetRotationLimits(bpy.types.Operator):
    bl_idname = "karaage.set_rotation_limits"
    bl_label =_("Set")
    bl_description =_("Set rotation limits on selected joints (if defined)")
    bl_options = {'REGISTER', 'UNDO'}

    all = BoolProperty(default=False)

    def execute(self, context):
        try:
            arm = util.get_armature(context.active_object)
            rig.set_bone_rotation_limit_state(arm, True, self.all)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonUnsetRotationLimits(bpy.types.Operator):
    bl_idname = "karaage.unset_rotation_limits"
    bl_label =_("Unset")
    bl_description =_("Unset rotation limits on selected joints (if defined)")
    bl_options = {'REGISTER', 'UNDO'}
    
    all = BoolProperty(default=False)

    def execute(self, context):
        try:
            arm = util.get_armature(context.active_object)
            rig.set_bone_rotation_limit_state(arm, False, self.all)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonBreatheIn(bpy.types.Operator):
    '''
    Move chest and torso for in breath
    (movement is subtle - hit repeatedly for stronger effect)
    '''
    bl_idname = "karaage.breathe_in"
    bl_label =_("In")
    bl_description =_("Move Chest and Torso for in-breath")

    def execute(self, context):
        try:
            armobj = util.get_armature(context.active_object)
            thetac=0.010
            try:
                thetat= asin(armobj.pose.bones['Chest'].length/armobj.pose.bones['Torso'].length* sin(thetac))
                armobj.pose.bones['Chest'].rotation_quaternion *= Quaternion((1,-thetac-thetat,0,0))
                armobj.pose.bones['Torso'].rotation_quaternion *= Quaternion((1,thetat,0,0))
            except KeyError:

                pass

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonBreatheOut(bpy.types.Operator):
    '''
    Move chest and torso for out breath
    (movement is subtle - hit repeatedly for stronger effect)
    '''
    bl_idname = "karaage.breathe_out"
    bl_label =_("Out")
    bl_description =_("Move Chest and Torso for out-breath")

    def execute(self, context):
        try:
            armobj = util.get_armature(context.active_object)
            thetac=0.010
            try:
                thetat= asin(armobj.pose.bones['Chest'].length/armobj.pose.bones['Torso'].length* sin(thetac))
                armobj.pose.bones['Chest'].rotation_quaternion *= Quaternion((1,thetac+thetat,0,0))
                armobj.pose.bones['Torso'].rotation_quaternion *= Quaternion((1,-thetat,0,0))
            except KeyError:

                pass

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class PanelExpressions(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    bl_label =_("Expressions")
    bl_idname = "karaage.expressions"
    bl_options = {'DEFAULT_CLOSED'}
    bl_category    = "Rigging"

    @classmethod
    def poll(self, context):
        try:
            return "karaage" in context.active_object
        except TypeError:
            return None

    def draw(self, context):
        layout = self.layout
        obj    = context.active_object
        arm    = util.get_armature(obj)
        meshes = util.findKaraageMeshes(obj)

        props = arm.RigProps
        layout.prop(props, "Hand_Posture", text=_('Hands'))

        col = layout.column(align=True)
        for key,label in (("express_closed_mouth_300", _("Closed Mouth")),
                            ("express_tongue_out_301", _("Tongue Out")),
                            ("express_surprise_emote_302", _("Surprise")),
                            ("express_wink_emote_303", _("Wink")),
                            ("express_embarrassed_emote_304", _("Embarrassed")),
                            ("express_shrug_emote_305", _("Shrug")),
                            ("express_kiss_306", _("Kiss")),
                            ("express_bored_emote_307", _("Bored")),
                            ("express_repulsed_emote_308", _("Repulsed")),
                            ("express_disdain_309", _("Disdain")),
                            ("express_afraid_emote_310", _("Afraid")),
                            ("express_worry_emote_311", _("Worry")),
                            ("express_cry_emote_312", _("Cry")),
                            ("express_sad_emote_313", _("Sad")),
                            ("express_anger_emote_314", _("Anger")),
                            ("express_frown_315", _("Frown")),
                            ("express_laugh_emote_316", _("Laugh")),
                            ("express_toothsmile_317", _("Toothy Smile")),
                            ("express_smile_318", _("Smile")),
                            ("express_open_mouth_632", _("Open Mouth"))):

            try:
                col.prop(meshes["headMesh"].data.shape_keys.key_blocks[key], "value", text=label)
            except (KeyError, AttributeError): pass

        col = layout.column(align=True)
        col.label(text="Non animatable in world")
        for key,label in (("furrowed_eyebrows_51", _("Furrowed Eyebrows")),
                            ("surprised_eyebrows_53", _("Surprised Eyebrows")),
                            ("worried_eyebrows_54", _("Worried Eyebrows")),
                            ("frown_mouth_55", _("Frown Mouth")),
                            ("smile_mouth_57", _("Smile Mouth")),
                            ("blink_left_58", _("Blink Left")),
                            ("blink_right_59", _("Blink Right")),
                            ("lipsync_aah_70", _("Lipsync Aah")),
                            ("lipsync_ooh_71", _("Lipsync Ooh"))):
            try:
                col.prop(meshes["headMesh"].data.shape_keys.key_blocks[key], "value", text=label)
            except (KeyError, AttributeError): pass

class ButtonCustomShape(bpy.types.Operator):
    bl_idname = "karaage.use_custom_shapes"
    bl_label =_("Custom Shapes")
    bl_description =_("Use custom shapes for controls")

    def execute(self, context):
        try:
            active = context.active_object

            active.data.show_bone_custom_shapes = True
            active.show_x_ray = False

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonStickShape(bpy.types.Operator):
    bl_idname = "karaage.use_stick_shapes"
    bl_label =_("Stick Shapes")
    bl_description =_("Use stick shapes for controls")

    def execute(self, context):
        try:
            active = context.active_object

            active.data.show_bone_custom_shapes = False
            active.show_x_ray = True
            active.data.draw_type = 'STICK'

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class PanelAnimationExport(bpy.types.Panel):
    '''
    Panel to control the animation export. SL parameters such as hand posture
    are set here.
    '''

    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'
    bl_label =_("Animation Export")
    bl_idname = "karaage.animation_export"
    bl_category    = "Animation"

    @classmethod
    def poll(self, context):
        '''
        This panel will only appear if the object has a
        Custom Property called "karaage" (value doesn't matter)
        and when the active object has animation data to be exported
        '''
        try:
            arm = context.active_object
            return arm and arm.type=='ARMATURE' and "karaage" in arm
        except (TypeError, AttributeError):
            return False

        return False

    def draw(self, context):

        def get_fcurve(armobj, bname):
            if not armobj:
                return None
            animation_data = armobj.animation_data
            if not animation_data:
                return None
            action = animation_data.action
            if not action:
                return None
            groups = action.groups
            if not groups:
                return None
            fc = groups.get(bname)
            return fc

        layout = self.layout
        scn = context.scene

        obj   = context.active_object
        armobj= util.get_armature(obj)
        is_bulk_export = armobj.AnimProps.selected_actions

        animation_data = armobj.animation_data
        if animation_data is None or animation_data.action is None:
            active_action = None
            props = armobj.AnimProps
            startprop = scn
            endprop = scn
            fpsprop = scn.render
            is_nla_export = animation_data != None and len(animation_data.nla_tracks) >0
        else:
            is_nla_export = False
            active_action = animation_data.action
            props = active_action.AnimProps
            startprop = props
            endprop = props
            fpsprop = props    

        layout.prop(props, "Mode")
        export_type = 'NLA' if is_nla_export else 'Bulk' if is_bulk_export else 'Action'
        col = layout.column(align=True)
        col.label("%s Export options" % export_type)

        col.enabled = not is_bulk_export
        col.prop(fpsprop, "fps", text=_("fps"))
        row = col.row(align=True)

        row.prop(startprop,"frame_start")
        if active_action:
            row.operator("karaage.action_trim",text='', icon='AUTO')
        row.prop(endprop,"frame_end")
        col = layout.column(align=True)
        col.prop(scn.SceneProp,"loc_timeline")
        col.enabled = active_action != None

        if props.Mode == 'anim':

            box = layout.box()
            box.label("Anim Export Options")
            col = box.column(align=True)
            row = col.row(align=True)
            row.prop(props,"Ease_In")
            row.prop(props,"Ease_Out")
            col.prop(props,"Priority")

            box.label(text=_("Loop Settings"))
            col = box.column()
            col.prop(props,"Loop", text=_("Loop animation"))
            row = col.row(align=True)
            row.prop(props,"Loop_In", text=_("In"))
            row.prop(props,"Loop_Out", text=_("Out"))

        layout.prop(props,"Basename")
        if props.Mode == 'bvh':
            layout.prop(props,"ReferenceFrame")

        layout.prop(scn.MeshProp, "applyScale", toggle=False)
        layout.prop(props,"Translations")
        
        ac = len(bpy.data.actions)
        exporting = 1

        if ac > 1:
            exporting = [a for a in bpy.data.actions if a.AnimProps.select]
            row=layout.row(align=True)
            row.prop(armobj.AnimProps, "selected_actions")
            if armobj.AnimProps.selected_actions:
                row.prop(armobj.AnimProps,"toggle_select")
                layout.template_list('ExportActionsPropVarList',
                                 'ExportActionsList',
                                 bpy.data,
                                 'actions',
                                 context.scene.ExportActionsIndex,
                                 'index',
                                 rows=5)

        row = layout.row()

        animation_data = armobj.animation_data

        origin_animated = False
        if not armobj.AnimProps.selected_actions:
            origin_fc = get_fcurve(armobj, 'Origin')
            if origin_fc:
                origin_animated = any(not c.mute for c in origin_fc.channels )

        no_keyframes = animation_data is None or (animation_data.action is None and len(animation_data.nla_tracks)==0)

        row_enabled = True
        row_alert = False        
        if armobj.AnimProps.selected_actions:
                anim_exporter = "karaage.export_bulk_anim"
                text = "Bulk Export (%d/%d Actions)" % (len(exporting), ac)
        else:
            dirname, name = ExportAnimOperator.get_export_name(armobj)        
            anim_exporter = "karaage.export_single_anim"
            text = "Export: %s" % name
            if no_keyframes:
                text = "No keyframes to export!"
                row_enabled = False
                row_alert = True
            elif origin_animated:
                if util.get_ui_level() < UI_ADVANCED:
                    text = "Origin is animated!"
                    row_enabled = False
                else:
                    text = "Export with Origin: %s" % name
                row_alert = True

        row.alert = row_alert
        row.enabled = row_enabled
        row.operator(anim_exporter, text=text, icon="RENDER_ANIMATION")

        if props.Mode == 'bvh':
            box = layout.box()
            box.label(text=_("Loop % calculator"))
            col = box.column()
            row = col.row(align=True)
            row.prop(props,"Loop_In", text=_("In"))
            row.prop(props,"Loop_Out", text=_("Out"))
            if props.ReferenceFrame:
                start = scn.frame_start
            else:

                start = scn.frame_start + 1
            frames = scn.frame_end-start
            if frames > 0:
                percent_in = round(100*(props.Loop_In-start)/float(frames),3)
                percent_out = round(100*(props.Loop_Out-start)/float(frames),3)
            elif props.Loop_In==start:
                percent_in = 0
                percent_out = 100
            else:
                percent_in = 0
                percent_out = 0
            row = col.row(align=True)
            row.label(text="%.3f%%"%percent_in)
            row.label(text="%.3f%%"%percent_out)

class ExportAnimOperator(bpy.types.Operator):
    '''
    Export the animation
    '''
    bl_idname = "karaage.export_anim"
    bl_label =_("Export Animation")
    bl_description = \
'''Export Animation (as .anim or .bvh)

- Need one or more Keyframes
- Origin Bone not animated or muted

Note: The .anim format is the SL internal format.'''

    log.warning("Init the ExportAnimOperator")
    check_existing = BoolProperty(name=_("Check Existing"), description=_("Check and warn on overwriting existing files"), default=True)

    @staticmethod
    def get_export_name(armobj):
        if armobj == None:
            raise
        animation_data = armobj.animation_data
        if animation_data == None:
            return "", ""

        action = animation_data.action
        if action == None:
            if len(animation_data.nla_tracks) >0:
                return "", "%s-NLA" % armobj.name
            return "", ""
            
        animProps = action.AnimProps
        mode      = animProps.Mode

        try:
            actionname = armobj.animation_data.action.name
        except AttributeError:
            actionname = armobj.animation_data.nla_tracks[0].name
        avatarname = armobj.name

        if mode=='bvh':
            priority = ''
        else:
            priority = animProps.Priority
        sub = {'action':actionname, 'avatar':avatarname, 'p':priority}
        basename = animProps.Basename

        dirname = os.path.dirname(bpy.data.filepath)

        name = string.Template(basename).safe_substitute(sub)
        name = bpy.path.clean_name(name)
        
        return dirname, name

    def invoke(self, context, event):
        log.warning("Invoke karaage.export_anim...")
        obj       = context.active_object
        armobj    = util.get_armature(obj)
        action    = armobj.animation_data.action
        animProps = armobj.animation_data.action.AnimProps if action else armobj.AnimProps
        mode      = animProps.Mode

        try:
            dirname, name = ButtonExportAnim.get_export_name(armobj)

            if armobj.AnimProps.selected_actions:
                self.directory = ''
                pass
            else:
                if mode=='bvh':
                    self.filepath = bpy.path.ensure_ext(os.path.join(dirname,name),".bvh")
                    self.filename_ext = ".bvh"
                    self.filter_glob = "*.bvh"
                else:
                    self.filepath = bpy.path.ensure_ext(os.path.join(dirname,name),".anim")
                    self.filename_ext = ".anim"
                    self.filter_glob = "*.anim"

            wm = context.window_manager

            wm.fileselect_add(self) # will run self.execute()
            return {'RUNNING_MODAL'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'RUNNING_MODAL'}

    def execute(self, context):
        log.warning("Execute karaage.export_anim...")
        active = context.active_object
        amode = active.mode
        armobj = util.get_armature(active)
        active_action = armobj.animation_data.action
        animProps = armobj.animation_data.action.AnimProps if active_action else armobj.AnimProps
        mode      = animProps.Mode
        scn = context.scene
        try:
            if armobj.AnimProps.selected_actions:
                filepath = self.directory
            else:
                filepath = self.filepath
                filepath = bpy.path.ensure_ext(filepath, self.filename_ext)
            context.scene.objects.active = armobj
            omode = util.ensure_mode_is("POSE")
            oscenedata = [scn.frame_start, scn.frame_end, scn.render.fps]

            if armobj.AnimProps.selected_actions:
                log.info("Bulk export %d actions" % len([a for a in bpy.data.actions if a.AnimProps.select]) )
            else:

                for action in bpy.data.actions:
                    action.AnimProps.select = (action == active_action)
                    if action.AnimProps.select:
                        log.debug("Marked single action [%s] for export" % (action.name) )

            if active_action or armobj.AnimProps.selected_actions:

                def get_frinfo(action, bulk, scn):
                    if bulk:

                        fr = action.frame_range
                        start = fr[0]
                        end = fr[1]
                    else:
                        start = action.AnimProps.frame_start
                        end = action.AnimProps.frame_end

                    fps = action.AnimProps.fps
                    
                    if fps == -2:
                        fps = scn.render.fps
                    if start == -2:
                        start = scn.frame_start
                    if end == -2:
                        end = scn.frame_end

                    return start, end, fps

                for action in [action for action in bpy.data.actions if action.AnimProps.select]:
                    armobj.animation_data.action = action
                    fr = action.frame_range
                    s, e, f = get_frinfo(action, armobj.AnimProps.selected_actions, scn)
                    scn.frame_start = s
                    scn.frame_end = e
                    scn.render.fps = f
                    path = "%s/%s.%s" % (filepath,action.name, mode) if armobj.AnimProps.selected_actions else filepath
                    animation.exportAnimation(action, path, mode)

            else:
                log.info("NLA Export to %s" % filepath)
                animation.exportAnimation(None, filepath, mode)

            scn.frame_start = oscenedata[0]
            scn.frame_end = oscenedata[1]
            scn.render.fps = oscenedata[2]
            armobj.animation_data.action = active_action
            
            util.ensure_mode_is(omode)
            context.scene.objects.active = active
            util.ensure_mode_is(amode)
            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonExportAnim(ExportAnimOperator):
    '''
    Export the animation
    '''
    bl_idname = "karaage.export_single_anim"
    bl_label =_("Export Animation")
    bl_description = \
'''Export Single Animation (as .anim or .bvh)

- Exports only if Keyframes found in Timeline
- Please mute Origin Bone animation when exists (see dope sheet) 

Note: The .anim format is the SL internal format.'''

    filename_ext = ""
    filepath = bpy.props.StringProperty(
               description="Animation File Name",
               subtype="FILE_PATH", 
               default="*.bvh;*.anim")

    filter_glob = StringProperty(
        default="",
        options={'HIDDEN'},
    )

    use_filer = True
    use_filter_folder = True

class ButtonExportBulkAnim(ExportAnimOperator):
    '''
    Export the animation
    '''
    bl_idname = "karaage.export_bulk_anim"
    bl_label =_("Export Animations")
    bl_description = \
'''Export A set of Actions (as .anim or .bvh)

Then the Origin Bone is muted to prevent unintentional export of Origin animations

Note: The .anim format is the SL internal format.'''

    directory = bpy.props.StringProperty(
               description="Animation export folder name",
               subtype="DIR_PATH", 
               default="")

    filter_glob = StringProperty(
        default="",
        options={'HIDDEN'},
    )

    use_filer = False
    use_filter_folder = False

@persistent
def fix_bone_layers_on_update(dummy):
    bind.fix_bone_layers(dummy, lazy=True)

@persistent
def fix_bone_layers_on_load(dummy):
    bind.fix_bone_layers(dummy, lazy=False)

@persistent
def fix_karaage_data_on_load(dummy):
    context = bpy.context
    scene   = context.scene
    props = util.getAddonPreferences()
    scene.MeshProp.weightSourceSelection = '' + scene.MeshProp.weightSourceSelection
    scene.MeshProp.attachSliders         = props.default_attach
    scene.MeshProp.enable_unsupported    = props.enable_unsupported

    util.reset_karaage_repository()
    init_log_level(context)

    try:
        ob = context.object
        hide_state = ob.hide
        ob.hide=False
        initial_mode = util.ensure_mode_is('OBJECT')
    except:
        ob = None
        initial_mode = None

    arms = [obj for obj in scene.objects if obj.type=="ARMATURE" and 'karaage' in obj]
    if len(arms) > 0:
        log.info("Fixing %d Karaage RigData %s after loading from .blend" % (len(arms), util.pluralize("structure", len(arms))) )

        for armobj in arms:

            if 'RigType' in armobj.AnimProps:
                 armobj.RigProps.RigType = armobj.AnimProps.RigType

            if 'skeleton_path' in armobj:
                del armobj['skeleton_path']

            if not armobj.library:
                rig.deform_display_reset(armobj)
                rig.fix_karaage_armature(context, armobj)

            if props.rig_version_check:
                karaage_version, rig_version, rig_id, rig_type = util.get_version_info(armobj)
                if karaage_version != rig_version:
                    ctx = None
                    scene.objects.active = armobj
                    for window in context.window_manager.windows:
                        screen = window.screen
                        for area in screen.areas:
                            if area.type == 'VIEW_3D':
                                ctx = context.copy()
                                ctx['window']        = window
                                ctx['screen']        = screen
                                ctx['area']          = area
                                ctx['active_object'] = armobj
                                ctx['object']        = armobj
                                break
                    if ctx:
                        bpy.ops.karaage.update_karaage(ctx, 'INVOKE_DEFAULT')
                        break

    if ob:
        scene.objects.active = ob
        util.ensure_mode_is(initial_mode)

    props.update_status='UNKNOWN'

@persistent
def check_for_system_mesh_edit(dummy):
    context = bpy.context
    if not context.scene.ticker.fire: return True

    ob = getattr(context,'object', None)
    if ob is None: return True
    if ob.type != 'MESH': return True
    if not 'mesh_id' in ob: return True

    if not util.is_in_user_mode():
        return True

    props = util.getAddonPreferences()
    if props.rig_edit_check == False:
        return True

    if ob.mode != 'EDIT':
        if 'editing' in ob:
            del ob['editing']
        return True

    if 'editing' in ob:
        log.debug("User tries to edit System mesh %s" % (ob.name))
        return True

    ob['editing'] = True

    ctx = None
    scene = context.scene
    scene.objects.active = ob
    for window in context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                ctx = context.copy()
                ctx['window']        = window
                ctx['screen']        = screen
                ctx['area']          = area
                ctx['active_object'] = ob
                ctx['object']        = ob
                break
    if ctx:
        log.warning("Warn user about editing the System Mesh %s" % (ob.name))
        bpy.ops.karaage.edit_karaage_mesh(ctx, 'INVOKE_DEFAULT')

    return False

@persistent
def check_for_armatures_on_update(dummy):

    context = bpy.context

    if not context.scene.ticker.fire: return

    prop = bpy.context.scene.MocapProp
    object_count = len(bpy.data.objects)
    if prop.object_count == object_count:
        return

    prop.sources.clear()
    prop.targets.clear()
    prop.object_count = object_count

    for obj in [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']:
        if "karaage" in obj or "avastar" in obj:
            entry = prop.targets.add()
        else:
            entry = prop.sources.add()
        entry.name = obj.name

    if len(prop.sources) == 1 and (prop.source == None or prop.source == ""):
        prop.source = prop.sources[0].name
    if len(prop.targets) == 1 and (prop.target == None or prop.target == ""):
        prop.target = prop.targets[0].name

class PanelMotionTransfer(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'

    bl_label =_("Motion Transfer")
    bl_idname = "karaage.motion_transfer"
    bl_category    = "Animation"

    @classmethod
    def poll(self, context):
        prop = context.scene.MocapProp
        return prop and len(prop.sources) > 0 and len(prop.targets) > 0

    def draw(self, context):

        layout = self.layout

        prop = context.scene.MocapProp

        mocap_sources = [obj.name for obj in bpy.data.objects if 'karaage' not in obj and obj.type == 'ARMATURE']
        mocap_targets = [obj.name for obj in bpy.data.objects if 'karaage' in obj and obj.type == 'ARMATURE']

        row = layout.row(align=True)
        row.label(text = _("Source:"))
        row.prop_search(prop, "source", prop, "sources", text="", icon="ARMATURE_DATA")
        row = layout.row(align=True)
        row.label(text = _("Target:"))
        row.prop_search(prop, "target", prop, "targets", text="", icon="ARMATURE_DATA")

        if prop.target in  mocap_targets and prop.source in  mocap_sources:

            if prop.show_bone_mapping:
                icon = "DISCLOSURE_TRI_DOWN"
            else:
                icon = "DISCLOSURE_TRI_RIGHT"

            col = layout.column()
            col.separator()
            row = col.row(align=True)
            row.operator(ButtonMappingDisplayDetails.bl_idname, text="", icon=icon)
            row.operator(ButtonGuessMapping.bl_idname, icon='MONKEY')

            if prop.show_bone_mapping:
                box = layout.box()
                row = box.row()
                targetcol = row.column(align=True)
                targetcol.scale_x = 2
                sourcecol = row.column(align=True)
                sourcecol.scale_x = 2
                selectcol = row.column(align=True)
                selectcol.scale_x = 0.1

                targetcol.label(text=_("Target"))
                if prop.flavor == "":
                    src_label =  "Source"
                else:
                    src_label = _("%s" % prop.flavor )
                sourcecol.label(text=src_label)
                selectcol.label(text=" ")

                source = bpy.data.objects[prop.source]
                target = bpy.data.objects[prop.target]
                for bone in data.get_mtui_bones(target):
                    if bone in MTUI_SEPARATORS:
                        targetcol.separator()
                        sourcecol.separator()
                        selectcol.separator()
                    targetcol.label(text=bone+":")
                    sourcecol.prop_search(prop, bone, source.data, "bones", text='')
                    selectcol.operator(ButtonSetSourceBone.bl_idname, text='', icon='CURSOR').target_bone = bone

                targetcol.separator()
                sourcecol.separator()
                selectcol.separator()

                row = box.row()
                row.operator(ButtonClearBoneMap.bl_idname, icon='X')
                row.operator(ButtonCopyOtherSide.bl_idname, icon='ARROW_LEFTRIGHT')

            col=layout.column()
            col.separator()
            box = layout.box()
            box.label("Pose")

            col = box.column(align=True)
            row = col.row(align=True)
            row.label(text = _("Ref frame:"))
            row.prop(prop, "referenceFrame", text="")
            row.enabled = not prop.use_restpose

            col = box.column(align=True)
            col.prop(prop, "use_restpose")

            col = box.column(align=True)
            row = col.row(align=True)
            row.operator(ButtonTransferePose.bl_idname, text=_('Transfer Pose'), icon='OUTLINER_OB_ARMATURE')
            row.operator(ButtonMatchScales.bl_idname, text=_('Match scales'), icon='MAN_SCALE')

            box = layout.box()
            box.label("Make Seamless:")
            row=box.row(align=True)
            row.prop(prop,"seamlessRotFrames")
            row.prop(prop,"seamlessLocFrames")

            col=box.column()
            col.label(_("Simplification:"))
            col.prop(prop, "simplificationMethod", text='')
            if prop.simplificationMethod == 'loweslocal':
                col.prop(prop, "lowesLocalTol")
            elif prop.simplificationMethod == 'lowesglobal':
                col.prop(prop, "lowesGlobalTol")

            col = layout.column()
            col.separator()
            row = col.row(align=True)
            row.operator(ButtonTransfereMotion.bl_idname, text='Transfer Motion', icon='POSE_DATA')
            row.operator(ButtonCleanupTarget.bl_idname, text='', icon='X')

def tag_redraw(type='ALL'):
    context = bpy.context
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if type == 'ALL' or area.type==type:
                for region in area.regions:
                    region.tag_redraw()

class ButtonCleanupTarget(bpy.types.Operator):
    bl_idname = "karaage.delete_motion"
    bl_label =_("Delete Motion")
    bl_description =_("Delete motion from Timeline")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            scn = context.scene
            prop = scn.MocapProp

            target = bpy.data.objects[prop.target]
            target.animation_data_clear()
            tag_redraw(type='TIMELINE')

        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonTransfereMotion(bpy.types.Operator):
    bl_idname = "karaage.transfer_motion"
    bl_label =_("Transfer Motion")
    bl_description =_("Transfer motion between start and end frames using reference frame as guide")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            scn = context.scene
            prop = scn.MocapProp

            source = bpy.data.objects[prop.source]
            target = bpy.data.objects[prop.target]
            reference_frame = 0 if prop.use_restpose else prop.referenceFrame
            animation.ImportAvatarAnimationOp.exec_trans(context, source, target, prop.use_restpose, reference_frame)
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'CANCELLED'}

        return{'FINISHED'}

class ButtonTransferePose(bpy.types.Operator):
    bl_idname = "karaage.transfer_pose"
    bl_label =_("Transfer Pose")
    bl_description =_("Transfer pose on current frame for selected bones using reference frame as guide")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            scn = context.scene
            prop = scn.MocapProp

            source = bpy.data.objects[prop.source]
            target = bpy.data.objects[prop.target]

            reference_frame = 0 if prop.use_restpose else prop.referenceFrame
            current_frame = scn.frame_current

            translations = []
            for bonename in data.get_mt_bones(target):
                sourcebone = getattr(prop, bonename)
                if bonename == "COGloc":
                    targetbone = "COG"
                else:
                    targetbone = bonename

                if sourcebone != "" and target.data.bones[targetbone].select:
                    if bonename == "COGloc":
                        bone_target = animation.BoneTarget(source=prop.COGloc,target=targetbone,loc=True,frames={})
                    else:
                        bone_target = animation.BoneTarget(source=sourcebone,target=targetbone,frames={})
                    translations.append(bone_target)

            animation.setReference(context, source, target, translations, reference_frame)
            animation.transferMotion(source, target, translations, reference_frame, current_frame, current_frame, prop)

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonMatchScales(bpy.types.Operator):
    bl_idname = "karaage.match_scales"
    bl_label =_("Match scales")
    bl_description =_("Match the scale of the imported armature to the Karaage")
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def execute_imp(context):
        try:
            scn  = context.scene
            prop = scn.MocapProp

            source = bpy.data.objects[prop.source]
            target = bpy.data.objects[prop.target]

            if source and target:
                util.match_armature_scales(source, target)
            else:
                print("WARN: Need 2 armatures to call the Armature Scale matcher")

        except Exception as e:
            util.ErrorDialog.exception(e)

    def execute(self, context):
        self.execute_imp(context)
        return{'FINISHED'}

class ButtonSetSourceBone(bpy.types.Operator):
    bl_idname = "karaage.set_source_bone"
    bl_label =_("Set source bone")
    bl_description =_("Copy active bone to source field")
    bl_options = {'REGISTER', 'UNDO'}

    target_bone = StringProperty()

    def execute(self, context):
        try:
            scn = context.scene
            prop = scn.MocapProp

            sbone = bpy.context.active_pose_bone

            source = bpy.data.objects[prop.source]

            if sbone.name in source.data.bones:
                setattr(prop, self.target_bone, sbone.name)

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonClearBoneMap(bpy.types.Operator):
    bl_idname = "karaage.clear_bone_map"
    bl_label =_("Clear")
    bl_description =_("Clear the bone mapping")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            scn = context.scene
            prop = scn.MocapProp
            target = bpy.data.objects[prop.target]
            for targetbone in data.get_mtui_bones(target):
                setattr(prop, targetbone, "")

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class ButtonMappingDisplayDetails(bpy.types.Operator):
    bl_idname = "karaage.mapping_display_details"
    bl_label = _("")
    bl_description = _("Hide/Unhide advanced mapping display")

    def execute(self, context):
        context.scene.MocapProp.show_bone_mapping = not context.scene.MocapProp.show_bone_mapping
        return{'FINISHED'}

class ButtonGuessMapping(bpy.types.Operator):
    bl_idname = "karaage.guess_bone_map"
    bl_label =_("Guess mapping")
    bl_description =_("Guess the bone mapping from the source names")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            scn = context.scene
            prop = scn.MocapProp
            source = bpy.data.objects[prop.source]
            target = bpy.data.objects[prop.target]
            prop.flavor, bonelist = animation.find_best_match(source, target)

            for sourcebone, targetbone in zip(bonelist, data.get_mt_bones(target)):
                if sourcebone in source.pose.bones:
                    setattr(prop, targetbone, sourcebone)
                else:
                    setattr(prop, targetbone, "")

        except Exception as e:
            util.ErrorDialog.exception(e)
        return{'FINISHED'}

class ButtonCopyOtherSide(bpy.types.Operator):
    bl_idname = "karaage.copy_other_side"
    bl_label =_("Mirror Copy")
    bl_description =_("Copy Limbs map to opposite side")
    bl_options = {'REGISTER', 'UNDO'}

    target_bone = StringProperty()

    def execute(self, context):
        try:
            scn = context.scene
            prop = scn.MocapProp
            target = bpy.data.objects[prop.target]
            for target1 in data.get_mtui_bones(target):
                source1 = getattr(prop, target1)
                if source1 == "":
                    continue
                if "Left" in target1:
                    target2 = target1.replace("Left","Right")
                    source2 = getattr(prop, target2)
                    if source2 == "":
                        setattr(prop, target2, util.flipName(source1))
                elif "Right" in target1:
                    target2 = target1.replace("Right","Left")
                    source2 = getattr(prop, target2)
                    if source2 == "":
                        setattr(prop, target2, util.flipName(source1))

            return{'FINISHED'}
        except Exception as e:
            util.ErrorDialog.exception(e)
            return{'FINISHED'}

class AddAvatarOp(bpy.types.Operator):
    bl_idname = "karaage.add_sl_avatar"
    bl_label = "Karaage"
    bl_description ="Create new Karaage Character"
    bl_options = {'REGISTER', 'UNDO'}

    quads = BoolProperty(
                name="with Quads",
                description="create Karaage with Quads (only when Sparkles-Pro is enabled",
                default=False,

                )
                
    no_mesh = BoolProperty(
                name="only Armature",
                description="create only the Karaage Rig (no Karaage meshes, good for creating custom avatars)",
                default=False,

                )

    file          = StringProperty()
    rigType       = StringProperty()
    jointType     = StringProperty()

    @classmethod
    def poll(self, context):
        if context.active_object:
            return context.active_object.mode == 'OBJECT'
        return True

    def get_preset(self, context, file):

        sceneProps    = context.scene.SceneProp
        
        b_meshType      = sceneProps.karaageMeshType
        b_rigType       = sceneProps.karaageRigType
        b_jointType     = sceneProps.karaageJointType

        bpy.ops.script.python_file_run(filepath=file)

        self.quads      = sceneProps.karaageMeshType == 'QUADS'
        self.no_mesh    = sceneProps.karaageMeshType == 'NONE'
        self.rigType    = sceneProps.karaageRigType
        self.jointType  = sceneProps.karaageJointType

        sceneProps.karaageMeshType  = b_meshType
        sceneProps.karaageRigType   = b_rigType
        sceneProps.karaageJointType = b_jointType
        
    def execute(self, context):
        oselect_modes = util.set_mesh_select_mode((False,True,False))

        if self.file:
            self.get_preset(context, self.file)

        arm_obj = create.createAvatar(
            context,
            quads                = self.quads, 
            no_mesh              = self.no_mesh, 
            rigType              = self.rigType,
            jointType            = self.jointType
        )

        if arm_obj == None:
            self.report({'ERROR'},("Could not create Armature\nOpen Blender Console for details on error"))
            util.set_mesh_select_mode(oselect_modes)
            return {'CANCELLED'}

        for l in range(0,32):
            arm_obj.data.layers[l] = l in B_DEFAULT_POSE_LAYERS
        
        preferences = util.getAddonPreferences()
        initial_mode = preferences.initial_rig_mode

        if initial_mode == 'POSE':
            bpy.ops.karaage.bone_preset_animate()
        elif initial_mode == 'EDIT':
            bpy.ops.karaage.bone_preset_edit()
            bpy.context.object.show_x_ray=True
        else:
            omode = util.ensure_mode_is("OBJECT")
            bpy.context.object.show_x_ray=False

        util.set_mesh_select_mode(oselect_modes)

        return {'FINISHED'}

class KaraageAddMenu(bpy.types.Menu):
    bl_label = "Karaage..."
    bl_idname = "OBJECT_MT_karaage_add_menu"

    def draw(self, context):
        layout = self.layout

        for file in glob.glob("%s/*.py" % RIG_PRESET_DIR):
            label      = os.path.basename(file).replace('.py','').replace('_',' ').replace('+',' ')
            props      = layout.operator(AddAvatarOp.bl_idname, text=label, icon='OUTLINER_OB_ARMATURE')
            props.file = file

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
        #

class KaraageAddMenu2(bpy.types.Menu):
    bl_label = "Karaage..."
    bl_idname = "OBJECT_MT_karaage_add_menu2"

    def draw(self, context):
        layout = self.layout
        
        props = layout.operator(AddAvatarOp.bl_idname, text="with Triangles", icon='OUTLINER_OB_ARMATURE')
        props.quads   = False
        props.no_mesh = False
        props.rigtype = util.getAddonPreferences().target_system

        props = layout.operator(AddAvatarOp.bl_idname, text="Only Rig", icon='OUTLINER_OB_ARMATURE')
        props.quads   = False
        props.no_mesh = True
        props.rigtype = util.getAddonPreferences().target_system

class KaraageHelpMenu(bpy.types.Menu):
    bl_label = "Karaage..."
    bl_idname = "OBJECT_MT_karaage_help_menu"

    def draw(self, context):
        layout = self.layout

        layout.operator("wm.url_open", text="check for Update",     icon='URL').url=KARAAGE_URL   + "/update?myversion=" + util.get_addon_version() + "&myblender=" + str(util.get_blender_revision())
        layout.operator("wm.url_open", text="Short Overview",       icon='URL').url=DOCUMENTATION + "/videos/"
        layout.operator("wm.url_open", text="Getting Help",         icon='URL').url=DOCUMENTATION + "/reference/getting-help/"
        layout.label("Basic tutorials:")
        layout.operator("wm.url_open", text="First Steps",          icon='URL').url=DOCUMENTATION + "/reference/first-steps/"
        layout.operator("wm.url_open", text="Pose a Character",     icon='URL').url=DOCUMENTATION + "/reference/pose-a-character/"
        layout.operator("wm.url_open", text="Create an Attachment", icon='URL').url=DOCUMENTATION + "/reference/create-an-attachment/"
        layout.operator("wm.url_open", text="Create an Animation",  icon='URL').url=DOCUMENTATION + "/reference/my-first-animation/"
        layout.operator("wm.url_open", text="Use your own Shape",   icon='URL').url=DOCUMENTATION + "/reference/use-sl-shapes/"
        layout.label("Knowledge:")
        layout.operator("wm.url_open", text="Skinning Basics",      icon='URL').url=DOCUMENTATION + "/knowledge/skinning-fundamentals/"
        layout.operator("wm.url_open", text="Karaage Bones",        icon='URL').url=DOCUMENTATION + "/knowledge/karaage-bones/"
        layout.operator("wm.url_open", text="Fitted Mesh",          icon='URL').url=DOCUMENTATION + "/knowledge/nutsbolts-of-fitted-mesh/"

class KaraageTemplates(bpy.types.Menu):
    bl_idname = "karaage.addon_add_template"
    bl_label = _("Open Template...")

    def draw(self, context):
        path = os.path.join(TEMPLATE_DIR,"*.blend")

        templates = glob.glob(path)
        templates.sort(key=lambda x: os.path.getmtime(x))
        layout = self.layout
        layout.operator_context = 'EXEC_SCREEN'

        for template in templates:

            name = os.path.basename(template)
            name = name[0:name.index(".")]
            name = name.replace("_", " ")

            if BLENDER_VERSION > 26900:
                props = layout.operator("wm.read_homefile", text=name, icon='FILE')

            else:
                props = layout.operator("wm.open_mainfile", text=name, icon='FILE')
                props.load_ui=False
            props.filepath=template

def menu_help_karaage(self, context):
    self.layout.menu(KaraageHelpMenu.bl_idname, text="Karaage", icon='URL')

def menu_add_karaage(self, context):

    #
    #
    #
    #
    #
    #
    #
    #
        self.layout.menu(KaraageAddMenu.bl_idname, text="Karaage", icon='URL')

def menu_export_collada(self, context):

    self.layout.operator(mesh.ButtonExportSLCollada.bl_idname)

user_templates = None
def menu_add_templates(self, context):
    global user_templates

    if user_templates == None:
        user_templates = register_templates()
        if user_templates == 'local':
            print("Use Karaage's native template system")

    if user_templates == 'local':
        self.layout.menu(KaraageTemplates.bl_idname, icon='OUTLINER_OB_ARMATURE')

def menu_import_karaage_shape(self, context):

    self.layout.operator(mesh.ButtonImportKaraageShape.bl_idname)

class MocapProp(bpy.types.PropertyGroup):
    flavor = StringProperty()
    source = StringProperty()
    target = StringProperty()
    object_count = IntProperty(default=0, min=0)

    referenceFrame    = IntProperty()
    use_restpose      = BoolProperty(name="Use Restpose", default=True, description = "Assume the restpose of the source armature\nmatches best to the current pose of the target armature.\nHint:Enable this option when you import animations\nwhich have been made for SL.")
    show_bone_mapping = BoolProperty(name=_("Show bone mapping"), default = False)
    simplificationitems = [
        ('none', _('None'), _('None')),
        ('loweslocal', _('Lowes Local'), _('Lowes Local')),
        ('lowesglobal', _('Lowes Global'), _('Lowes Global')),
        ]
    simplificationMethod = EnumProperty(items=simplificationitems, name=_('Method'), default='none')
    lowesLocalTol = FloatProperty(default=0.02, name=_("Tol"))
    lowesGlobalTol = FloatProperty(default=0.1, name=_("Tol"))
    seamlessRotFrames = IntProperty(default=0, name=_("Rot frames"), min=0,
        description="Blend range to make seamles rotation")
    seamlessLocFrames = IntProperty(default=0, name=_("Loc frames"), min=0,
        description="Blend range to make seamles translation")

def eyeTargetConstraintCallback(self, context):
    obj = context.object
    arm = util.get_armature(obj)
    if arm:
        rig.setEyeTargetInfluence(arm, 'Eye')

def altEyeTargetConstraintCallback(self, context):
    obj = context.object
    arm = util.get_armature(obj)
    if arm:
        rig.setEyeTargetInfluence(arm, 'FaceEyeAlt')

class IKSwitches(bpy.types.PropertyGroup):
    Show_All = BoolProperty(name = "Show all controls", default = False)
    Enable_Limbs = BoolProperty(name = "Enable IK Limbs", default = False)
    Enable_Legs = BoolProperty(name = "Enable IK Legs", default = False)
    Enable_Arms = BoolProperty(name = "Enable IK Arms", default = False)
    Enable_Eyes = BoolProperty(name = "Enable Eyes",
                  default = False,
                  update=eyeTargetConstraintCallback,
                  description = "Let the eyes follow the eye target when enabled"
    )
    Enable_AltEyes = BoolProperty(name = "Enable Alt Eyes",
                  default = False,
                  update=altEyeTargetConstraintCallback,
                  description = "Let the Alt Eyes eyes follow the Alt Eye target when enabled"
    )

    hand_ik_type = [
        ('NONE', _('FK Simple'), _('Use the simple FK Rig, do not show the IK Targets')),
        ('FK', _('FK constrained'), _('Use the constrained FK Rig (Uses Copy_Rotation and Limit_Rotation constraints)')),
        ('GRAB', _('IK Grab'), _('Use the Grab IK Rig (with active IK Targets'))
        ]
    Enable_Hands = EnumProperty(items=hand_ik_type, name = _("Enable IK Hands"), default = 'NONE', update=update_hand_ik_type)

    IK_Wrist_Hinge_L = FloatProperty(name = _("Left Wrist"), min = 0.0, max = 1.0, default = 1.0)
    IK_Wrist_Hinge_R = FloatProperty(name = _("Right Wrist"), min = 0.0, max = 1.0, default = 1.0)

    IK_Ankle_Hinge_L = FloatProperty(name = _("Left Ankle"), min = 0.0, max = 1.0, default = 1.0)
    IK_Ankle_Hinge_R = FloatProperty(name = _("Right Ankle"), min = 0.0, max = 1.0, default = 1.0)
    IK_Foot_Pivot_L  = FloatProperty(name = _("Left Foot Pivot"), min = -0.4, max = 1.0, default = 0.0, update=shape.pivotLeftUpdate)
    IK_Foot_Pivot_R  = FloatProperty(name = _("Right Foot Pivot"), min = -0.4, max = 1.0, default = 0.0, update=shape.pivotRightUpdate)

    IK_HindLimb3_Hinge_L = FloatProperty(name = _("Left Hind Ankle"), min = 0.0, max = 1.0, default = 1.0)
    IK_HindLimb3_Hinge_R = FloatProperty(name = _("Right Hind Ankle"), min = 0.0, max = 1.0, default = 1.0)
    IK_HindLimb3_Pivot_L  = FloatProperty(name = _("Left Hind Foot Pivot"), min = -0.4, max = 1.0, default = 0.0, update=shape.pivotLeftUpdate)
    IK_HindLimb3_Pivot_R  = FloatProperty(name = _("Right Hind Foot Pivot"), min = -0.4, max = 1.0, default = 0.0, update=shape.pivotRightUpdate)

def weightCopyAlgorithmsCallback(scene, context):

    items=[
        ('VERTEX',   'Vertex', "Copy weights to opposite Vertices (needs exact X symmetry)"),
        ('TOPOLOGY', 'Topology', "Copy weights to mirrored Topology (needs topology symmetry, does not work for simple mesh topology)"),
        ]

    if 'toolset_pro' in dir(bpy.ops.sparkles):
        items.append(
        ('SMART',   'Shape', "Copy weights to mirrored Shape (only depends on Shape, works always but is not exact)")
        )

    return items

def update_panel_presets(self, context):
    pass

def update_slider_type(self, context):
    with util.slider_context() as is_locked:

        updatelog.debug("update_slider_type to %s" % self.slider_selector)
        if is_locked:
            updatelog.debug("Leave update_slider_type")
            return
            
        arms,objs = util.getSelectedArmsAndAllObjs(context)
        util.set_disable_update_slider_selector(True)

        updatelog.debug("update_slider_type: for %d %s and %d %s" %
                        (len(arms), 
                         util.pluralize('Armature', len(arms)), 
                         len(objs), 
                         util.pluralize('Object', len(objs))
                        )
                       )

        if arms:
            updatelog.debug("Update %d Armatures" % (len(arms)) )
            for arm in arms:
                shape_filename = arm.name
                updatelog.debug("Update Armature %s" % (shape_filename) )
                if self.slider_selector == 'NONE':# and context.object == arm:

                    updatelog.debug("Search shape file %s" % (shape_filename) )
                    if shape_filename in bpy.data.texts:
                        updatelog.debug("Load existing shape file %s" % (shape_filename) )
                        omode = util.ensure_mode_is("OBJECT")
                        shape.ensure_drivers_initialized(arm)
                        try:
                            shape.loadProps(arm, shape_filename, pack=True)
                        except:
                            updatelog.warning("Could not load original shape into Mesh")
                            updatelog.warning("probable cause: The Mesh was edited while sliders where enabled.")
                            updatelog.warning("Discarding the Shape %s" % shape_filename)
                        
                        util.ensure_mode_is(omode)
                        if arm == context.object:

                            text = bpy.data.texts[shape_filename]
                            util.remove_text(text, do_unlink=True)
                            updatelog.debug("update_slider_type: Removed shape for Armature %s in textblock:%s" % (arm.name, shape_filename) )
                else:
                    if not shape_filename in bpy.data.texts:
                        shape.saveProperties(arm, shape_filename, normalize=False, pack=True)
                        updatelog.debug("update_slider_type: Stored initial shape for Armature %s in textblock:%s" % (arm.name, shape_filename) )
                arm.ObjectProp.slider_selector = self.slider_selector

        if objs:
            updatelog.debug("Update %d Objects" % (len(objs)) )
            active = context.scene.objects.active
            try:
                armobj = None
                for obj in objs:
                    context.scene.objects.active = obj
                    updatelog.debug("Update Object %s" % (obj.name) )
                    obj.ObjectProp.slider_selector = self.slider_selector
                    if self.slider_selector == 'NONE':
                        updatelog.debug("Removing Sliders from Object %s" %obj.name)
                        bpy.ops.karaage.shape_slider_detach(reset=True)
                        #

                    else:
                        armature = obj.find_armature()
                        if armature and armobj != armature:
                            armobj = armature
                            context.scene.objects.active = armature

                        if self.slider_selector == 'SHAPE':
                            keys = obj.data.shape_keys
                            if keys and armature:
                                filename = shape.enable_shape_keys(context, armature, obj)

                                if filename:
                                    continue

                        if armature:
                            updatelog.debug("update_slider_type: attach Sliders of armature %s to object %s" % (armature.name, obj.name))
                            shape.attachShapeSlider(context, armature, obj, init=True)
            except Exception as e:
                print("update_slider_type(objs): Runtime error:", e)
                raise e
            context.scene.objects.active = active

        util.set_disable_update_slider_selector(False)
        shape.updateShape(None, context, scene=context.scene, refresh=True, init=False, msg="update_slider_type")

def slider_options(self, context):
    ob = context.object
    obtype = ob.type if ob else 'NONE'
    
    if obtype=='ARMATURE':
        items=[
                ('NONE',  "No Sliders", "Disable Karaage Sliders from all of Armature's Custom Meshes "),
                ('SL',    "SL Appearance", "Use Karaage Sliders to simulate the SL Appearance Sliders on all of Armature's Custom Meshes")
              ]
        for ob in util.getCustomChildren(ob, type='MESH'):
            if data.has_karaage_shapekeys(ob):
                items.append(
                    ('SHAPE', "Shape Keys", 'Propagate Karaage sliders to Custom Shape keys (if custom Shape keys are available)')
                )
                break
    else:
        items=[
                ('NONE',  "No Sliders", 'Disable Karaage Sliders from Selected Meshes'),
                ('SL',    "SL Appearance", 'Use Karaage Sliders to simulate the SL Appearance Sliders on Selected Meshes')
              ]

        if obtype == 'MESH' and data.has_karaage_shapekeys(context.object):
            items.append(
                ('SHAPE', "Shape Keys", 'Propagate Karaage sliders to Custom Shape keys (if custom Shape keys are available)')
            )

    return items

def rig_display_type_items(self, context):
    items = [
            ('SL',     _('SL') , _('Display all deforming SL Base Bones defined for this Skeleton')),
            ('EXT', _('Ext'), _('Display all deforming SL Extended Bones defined for this Skeleton (Hands, Face, Wings, Tail)')),
            ('VOL',    _('Vol'), _('Display all deforming Collision Volumes defined for this Skeleton (Fitted mesh)')),
            ('POS', _('Joint'), _('Display bones having Joint Offsets\n\nNote: Joint offsets are defined by modifying the Skeleton in edit mode\nPlease remember to set the joint positions:\n\nKaraage -> Rigging Panel\nConfig Section\nJointpos Settings -> Store Joint Pos')),
            ]

    if context.object.type == 'MESH':
        items.append(('MAP', _('Map'), _('Display all Weighted Deforming Bones used by the current selection of Mesh Objects\nNote: There may be a small delay of ~1 second before the filter applies')))

    return items

class ObjectProp(bpy.types.PropertyGroup):

    slider_selector = EnumProperty(
        items=slider_options,
        name=_("Slider Type"),
        description=_("How to use Sliders"),
        update=update_slider_type)

    rig_display_type = EnumProperty(
        items   = rig_display_type_items,
        name    = _("Display Type"),
        update  = bind.configure_rig_display,
        description=_("Deform Bone Display Filter")
        )

    filter_deform_bones = BoolProperty(
        default=False,
        update      = bind.configure_rig_display,
        name        ="Filter Deform Bones",
        description ="Display only the deforming Bones from selected Group:\n\nSL  : SL Base Skeleton\nVol : Collision Volume Bones\nExt: SL Extended Skeleton\nPos: Bones which have stored Joint offsets \nMap: Bones weighted to one or more Meshes of the current selection"
        )

    edge_display   = BoolProperty(
       default     = False,
       update      = bind.configure_edge_display,
       name        = "Edge Display",
       description = "Enable visibility of edges in Object Mode and Weight Paint Mode"
    )

    apply_armature_on_unbind = BoolProperty(
       default     = False,
       name        = "With Apply Armature",
       description = "Apply the current Armature Pose on unbind"
    )

    apply_armature_on_snap_rig = BoolProperty(
       default     = True,
       name        = "Snap Mesh",
       description = ObjectProp_apply_armature_on_snap_rig_description
    )

def update_sync_influence(pbone, context):
    
    synced = pbone.sync_influence
    if synced and 'Grab' in pbone.constraints:
        print("update_sync_influence for", pbone.name)
        val = pbone.constraints['Grab'].influence
        pbones = context.object.pose.bones
        arm = util.get_armature(context.object)
        if pbone.name.endswith("SolverLeft"):
            arm.RigProps.IKHandInfluenceLeft = val
        elif pbone.name.endswith("SolverRight"):
            arm.RigProps.IKHandInfluenceRight = val

def update_pinch_influence(pbone,context):
    pinched = pbone.pinch_influence
    try:
        grab_inf = min(1,  2 * max(0.5-pinched, 0))
        pinch_inf= min(1,  2 * max(pinched-0.5, 0))

        pbone.constraints['Grab'].influence = grab_inf
        pbone.constraints['Pinch'].influence = pinch_inf

        if pbone.name.startswith("ikThumb"):
            otherbone = context.object.pose.bones["ikIndex%s" % pbone.name[7:]]
            otherbone.pinch_influence = pinched
    except:
        print("Could not balance grab/pinch constraint")
        raise

bpy.types.PoseBone.sync_influence = BoolProperty(
        default     = False,
        update      = update_sync_influence,
        name        =_("IK Lock"),
        description =_("Modify the influence of all locked bones in sync.")
        )

bpy.types.PoseBone.pinch_influence = FloatProperty(
        name="pinch",
        min=0, max=1, default=0,
        update=update_pinch_influence
        )

class SceneProp(bpy.types.PropertyGroup):
    karaageMeshType = EnumProperty(
        items=(
            ('NONE',    'Rig only'  , 'Create only the Rig (without the Second Life character meshes)'),
            ('TRIS',    'with Tris' , 'Create Rig and Meshes using Triangles'),
            ('QUADS',   'with Quads', 'Create Rig and Meshes mostly with Quads\nNote: This option is only active\nwhen you have Installed Sparkles-Pro')),
        name=_("Create Avatar"),
        description=_("Create a new Karaage character"),
        default='TRIS')

    karaageRigType = EnumProperty(
        items=(
            ('BASIC', 'Basic' , 'The Basic Rig supports only the old Bones.\nGood for Main grid and other Online Worlds like OpenSim, etc."'),
            ('EXTENDED', 'Extended'  , 'The Extended Rig supports new Bones for Face, Hands, Wings, and Tail.\nThe Extended Rig is only available on the Test Grid (Aditi) ')),
        name=_("Rig Type"),
        description= "The set of used Bones",
        default='BASIC')

    karaageJointType = EnumProperty(
        items=(
            ('POS',   'Pos' ,    'Create a rig based on the pos values from the avatar skeleton definition\nFor making Cloth Textures for the System Character (for the paranoid user)'),
            ('PIVOT', 'Pivot'  , 'Create a rig based on the pivot values from the avatar skeleton definition\nFor Creating Mesh items (usually the correct choice)')
        ),
        name=_("Joint Type"),
        description= "SL supports 2 Skeleton Defintions.\n\n- The POS definition is used for the System Avatar (to make cloth).\n- The PIVOT definition is used for mesh characters\n\nAttention: You need to use POS if your Devkit was made with POS\nor when you make cloth for the System Avatar",
        default='PIVOT')

    #
    #
    skeleton_file   = StringProperty( name = "Skeleton File", default = "avatar_skeleton_2.xml",
                                      description = "This file defines the Deform Skeleton\n"
                                                  + "This file is also used in your SL viewer. You find this file in:\n\n"
                                                  + "{Viewer Installation folder}/character/avatar_skeleton.xml\n\n"
                                                  + "You must make sure that the Definition file used in Karaage matches\n"
                                                  + "with the file used in your Viewer.\n\n"
                                                  + "When you enter a simple file name then Karaage reads the data its own lib subfolder\n"
                                    )
    lad_file        = StringProperty( name = "Lad File",      default = "avatar_lad_2.xml",
                                      description = "This file defines the Appearance Sliders\n"
                                                  + "This file is also used in your SL viewer. You find this file in:\n\n"
                                                  + "{Viewer Installation folder}/character/avatar_lad_2.xml\n\n"
                                                  + "You must make sure that the Definition file used in Karaage matches\n"
                                                  + "with the file used in your Viewer.\n\n"
                                                  + "When you enter a simple file name then Karaage reads the data its own lib subfolder\n"
                                    )        

    #
    target_system   = EnumProperty(
        items=(
            ('EXTENDED', 'SL Main',  "Export items for the Second Life Main Grid.\n"
                           +  "This setting takes care that your creations are working with all \n"
                           +  "officially supported Bones. (Note: This includes the new Bento Bones as well)"),
            ('BASIC', 'SL Legacy', "Export items using only the SL legacy bones.\n"
                           +  "This setting takes care that your creations only use\n"
                           +  "the Basic Boneset (26 bones and 26 Collision Vollumes).\n"
                           +  "Note: You probably must use this option for creating items for other worlds."),
            ('RAWDATA', 'Tool exchange',  "Export items for usage in other tools.\n"
                           +  "This setting exports the skeleton as is\n"
                           +  "without any considerations regarding the target system (experimental)"),
        ),
        name="Target System",
        description = "The System for which the items are created.\nNote: The new Bento Bones only work on Secondlife Aditi for now\n",
        default     = 'EXTENDED'
    )
    
    collada_only_weighted = BoolProperty(default=True, name= "Only Weighted Bones",
                            description="Enabled: Export only bones for which at least one mesh has weights.\nDisabled: Ensure the basic SL Skeleton is enclosed in the export\n\nNote: Enable this option only when your target system supports partial rig import.\nPartial rig import is a new Second Life feature coming with Project Bento"
                           )
    collada_only_deform   = BoolProperty(default=True, name= "Only Deform Bones",
                            description="Enabled: Export only bones which are marked as Deforming.\nDisabled: Do not check the Deform flag\n\nNote: Enable this option only when your target system supports partial rig import.\nPartial rig import is a new Second Life feature coming with Project Bento"
                           )
    collada_full_hierarchy = BoolProperty(default=True, name= "Include Parent Hierarchy",
                            description="Enabled: Export all deforming parent bones as well",
                           )
    collada_export_boneroll = BoolProperty(default=False, name= "Export Bone Roll",
                            description="Export with Karaage Bone Roll values (Experimental)"
                           )
    collada_export_layers = BoolProperty(default=False, name= "Export Bone Layers",
                            description="Export with Karaage Bone Layers"
                           )
    collada_blender_profile = BoolProperty(default=False, name= "Export with Blender Profile",
                            description="Add extra Blender data to the export by using the Blender Collada profile\nThe additional information can only be read from Collada importers which support the blender Collada profile as well.\nThe Blender profile is supported since blender 2.77a\n\nNote:It should be safe to export with the blender profile enabled because\nother tools should ignore the extra data if they do not support it."
                           )
    collada_export_rotated = BoolProperty(default=True, name= "Export SL rotation",
                            description="Rotate armature by 90 degree for SL (Experimental)"
                           )
    collada_export_with_joints = BoolProperty(
                    default=True, 
                    name= "Export with Joints",
                    description=SceneProp_collada_export_with_joints_description
                    )
    accept_attachment_weights = BoolProperty(default=False, name= "Accept Attachments Weights",
                            description="Enabled: Export only bones which are marked as Deforming.\nDisabled: Do not check the Deform flag\n\nNote: Enable this option only when your target system supports partial rig import.\nPartial rig import is a new Second Life feature coming with Project Bento"
                           )
    use_export_limits     = BoolProperty(default=True, name=_("Sanity Checks"),
                            description=_("Enable all checks which ensure the exported data is compatible to Second Life.")
                           )
    armature_preset_apply_as_Restpose  = BoolProperty(
                           name="Apply as Restpose",
                           description = "- DISABLED: Apply Preset as Pose and keep the current Restpose intact\n  Avoids joint offsets, but is experimental and \n  needs to be supported by the Collada Exporter\n\n- ENABLED: Apply the Preset as Restpose\n  needs joint offsets, otherwise safe to use",
                           default     = False
                           )
    armature_preset_apply_all_bones  = BoolProperty(
                           name="all",
                           description = "Apply all bones",
                           default     = True
                           )
    armature_preset_adjust_tails  = BoolProperty(
                           name="Match Tail",
                           description = "Match parent tails to bone heads\nThis function compensates pose presets where\nthe bone lengths do not match to the joint distances.\nHint: You usually want this feature to be turned on",
                           default     = True
                           )
    panel_appearance_enabled = BoolProperty(
                     name = "Enable Appearance",
                     default = True
                     )

    loc_timeline = BoolProperty(
                   name = "Synchronize",
                   default = False,
                   update=animation.update_scene_data,
                   description = "Update timeline (Startframe, Endframe, fps) automatically\nto reflect changes in the related settings of the active Action\n\nNote: For NLA exports the parameters are taken from the timeline and this option is not effective"
                   )

    panel_presets = EnumProperty(
                    name = "Workflow Presets",
                    items=(
                            ('SKIN',     'Skin & Weight'  , 'Prepare the Panels for Skinning and Weighting Workflows'),
                            ('POSE',     'Pose & Animate' , 'Prepare the Panels for posing & Animating Workflows'),
                            ('RETARGET', 'Retarget'       , 'Prepare the Panels for Retarget Workflow'),
                            ('EDIT',     'Joint Edit'     , 'Prepare the Panels for Editing joints (Bones)')
                          ),
                   )

    snap_control_to_rig = BoolProperty(
       name        = "snap_control_to_rig",
       description = SceneProp_snap_control_to_rig_description,
       default     = False
       )

class MeshProp(bpy.types.PropertyGroup):

    weightCopyAlgorithm = EnumProperty(
        items=weightCopyAlgorithmsCallback,
        name="Algorithm",
        description="Used Mirror Algoritm for mirror weight copy"
    )

    handleOriginalMeshSelection = EnumProperty(
        items=(
            ('KEEP',   _('Keep'), _('Keep both Meshes')),
            ('HIDE',   _('Hide'), _('Hide Original mesh')),
            ('DELETE', _('Delete'), _('Delete original mesh'))),
        name=_("Original"),
        description=_("How to proceed with the Original Mesh after freeze"),
        default='HIDE')

    hideOriginalMesh   = BoolProperty(default=False, name=_("Hide Original Mesh"))
    deleteOriginalMesh = BoolProperty(default=False, name=_("Delete Original Mesh"))

    handleBakeRestPoseSelection = EnumProperty(
        items=(
            ('SELECTED',_('Selected'), _('Bake selected Bones')),
            ('VISIBLE', _('Visible'),  _('Bake visible Bones')),
            ('ALL',     _('All'),      _('Bake all Bones'))),
        name=_("Scope"),
        description=_("Which bones are affected by the Bake"),
        default='SELECTED')

    standalonePosed = BoolProperty(default=False, name=_("as static Mesh"),
        description=_("Create a static copy in the current posture, not parented to armature"))
    removeWeights = BoolProperty(default=False, name=_("Remove Weight Groups"),
        description=_("Remove all vertex groups from the copy.(Only for 'Standalone Posed')"))
    joinParts = BoolProperty(default=False, name=_("Join Parts"),
        description=_("Join all selected parts into one singlemesh object')"))
    removeDoubles = BoolProperty(default=False, name=_("Weld Parts"),
        description=_("Remove duplicate verts from adjacent edges of joined parts"))

    copyWeights = BoolProperty(default=False, name=_("with Weight Copy"),
        description=_("Copy weights from all visible armature children"))

    clearTargetWeights = BoolProperty(default=True, name=_("Clear weights"),
        description=_("Reset affected target vertices before Copying the weights. Works also with 'Only selected vertices' "))
    toTPose = BoolProperty(default=False, name=_("Alter to Rest Pose"),
        description=_("Alter selected meshes into the Armature's rest pose.\n\nSpecial Notes:\n* This feature is disabled when the selected Meshes contain Shape Keys!\n* CAUTION: Your mesh models will be permanently modified!"))

    copyWeightsSelected = BoolProperty(default=False, name=_("Selected verts"),
        description=_("Copy weights only to selected vertices in the target mesh"))
    submeshInterpolation = BoolProperty(default=True, name=_("Interpolate"),
        description=_("Interpolate the weight values from closests point on surface of reference mesh") )

    exportArmature = BoolProperty(default=True, name=_("Include joint positions"),
        description=_("Use if modifying the bone locations. You need to import them in the viewer also to have an effect"))
    exportIncludeUVTextures = BoolProperty(default=True, name=_("UV Textures"),
        description=_("Export textures assigned to the Object's UV Maps"))
    exportIncludeMaterialTextures = BoolProperty(default=False, name=_("Material Textures"),
        description=_("Export textures assigned to the Object's materials"))

    exportOnlyActiveUVLayer = BoolProperty(default=True, name=_("Only Active UV layer"),
        description=_("Default: export all UV Layers. if set, only export the active UV Layer"))

    exportCopy = BoolProperty(default=True, name=_("Copy"),
        description=_("Copy textures to the same folder where the .dae file is exported"))
        
    exportDeformerShape = BoolProperty(default=False, name=_("Include Deformer Shape"),
        description=_("Mesh Deformer support(experimental): Export the Normalized version of the current Shape as XML. Use this XML file for your custom Mesh deformer upload"))

    applyScale = BoolProperty(default=False, name=_("Apply Armature Scale"),
        description=_("Apply the armature's object Scale to the Animation channels\n\nEnable this option when your armature is scaled in Object mode\nand your animation contains translation components.\nThen Scale is applied on the fly (only for the export)\n\nTypically needed when Armature is scaled in Object mode to create tinies or giants"))

    apply_mesh_rotscale = BoolProperty(default=True, name=_("Apply Rotation & scale"),
        description=_("Apply the Mesh object's Rotation & Scale, should always be used"))

    weld_normals = BoolProperty(default=True, name=_("Weld Edge Normals"),
        description=_("Adjust normals at matching object boundaries (to avoid visual seams)"))

    weld_to_all_visible = BoolProperty(default=False, name=_("Weld to all visible"),
        description=_("If enabled, then take all visible mesh objects into account for welding the normals, otherwise weld only with selected objects") )

    max_weight_per_vertex = IntProperty(name=_("Limit weight count"),
        default = 4,
        min     = 0,
        description=_("Define how many weights are allowed per vertex (set to 0 to allow arbitrary weight count)") )

    exportRendertypeSelection = EnumProperty(
        items=(
            ('NONE', _("Don't apply"), _('Ignore modifiers')),
            ('PREVIEW', _('View Settings'), _('Use View properties')),
            ('RENDER', _('Render Settings'), _('Use Render Properties'))),
        name=_("Modifiers"),
        description=_("Modifier render type"),
        default='PREVIEW')

    selectedBonesOnly = BoolProperty(default=False, name=_("Restrict to same Bones"),
        description=_("Copy only those weights from other Meshes, which are assigned to the selected Bones"))
    mirrorWeights = BoolProperty(default=False, name=_("Mirror from opposite Bones"),
        description=_("Copy weights from Bones opposite to selection (merge with current weights!)"))

    allBoneConstraints = BoolProperty(default=False, name=_("Set All"),
        description=_("Set all bone constraints of skeleton"))

    adjustPoleAngle = BoolProperty(default=True, name=_("Sync Pole Angles"),
        description=_("Automatically adjust pole angles of IK Pole Targets when entering Pose Mode"))

    weightCopyType = EnumProperty(
        items=(
            ('ATTACHMENT', _("from Attachments"), _('Copy bone weights from same bones of other attachments')),
            ('MIRROR', _('froom Opposite Bones'), _('Copy bone Weights from opposite bones of same object')),
            ('BONES', _('selected to active'), _('Copy bone weights from selected bone to active bone (needs exactly 2 selected bones) '))),
        name=_("Copy"),
        description=_("Method for Bone Weight transfer"),
        default='ATTACHMENT')

    useBlenderTopologyMirror = BoolProperty(default=False, name=_("Use Topology Mirror"),
        description=_("Use Blender's Topology weight mirror copy. Caution: Does only work when mesh is NOT symmetric (handle with care)!!!"))

    weight_type_selection = EnumProperty(
        items=(
            ('NONE',        _("No weights"), _('Create with empty Vertex groups')),
            ('COPYWEIGHTS', _('Copy weights'), _('Copy weights from all visible armature children')),
            ('AUTOMATIC',   _('Automatic weights'), _('Calculate weights from Bones')),
            ('ENVELOPES',   _('Envelope weights'), _('Calculate weights from Bone envelopes'))),
        name=_("Weighting"),
        description=_("Method to be used for creatin initial weights"),
        default='NONE')

    deform_type_selection = EnumProperty(
        items=(
            ('BONES', _("Deform"), _('Only edit weight Groups used for Pose bones')),
            ('OTHER', _('Other'), _('Only edit weight Groups used for non pose bones')),
            ('ALL',   _('All'), _('Edit all weight Groups'))),
        name=_("Subset"),
        description=_("Selection depending on usage of the Weight Groups"),
        default='ALL')

    save_shape_selection = EnumProperty(
        items=(
            ('FILE', _('File'),      _('Save Shape to Disk')),
            ('DATA', _('Textblock'), _("Save Shape to textblock (view with Blender's Text Editor)"))),
        name=_("Store Type"),
        description=_("Store Shape data in a File or in a Textblock (view with Blender's Text editor)"),
        default='FILE')

    skinSourceSelection = EnumProperty(
        items=(
            ('NONE',       _('Keep'),      _('Do not touch weight Groups (keep existing weight groups untouched)')),
            ('EMPTY',      _('Empty'),     _('Add empty weight groups (keep existing weight groups untouched)')),
            ('AUTOMATIC',  _('Bones'),     _('Generate weights from Bones (most commonly used, works out of the box)')),
            ('COPY',       _('Meshes'),    _('Copy weights from other visible Meshes rigged to same Armature')),
            ('KARAAGE',    _('Karaage'),   _('Copy weights from Karaage head, upper body and lower body\neven if the Karaage meshes are not visible.'))),
        name=_("Weights"),
        description=_("From where to get the initial weight data"),
        default='COPY')

    weightSourceSelection = EnumProperty(
        items=(

            ('EMPTY',      _('Create Empty Groups'),   _('Add empty weight groups (keep existing weight groups untouched)')),
            ('AUTOMATIC',  _('Automatic from Bones'),  _('Generate weights from Bones (most commonly used, works out of the box)')),
            ('COPY',       _('Copy from Meshes'),      _('Copy weights from all visible Meshes parented to same Armature')),
            ('KARAAGE',    _('Copy from Karaage'),     _('Copy weights from Karaage meshes.')),
            ('EXTENDED',   _('Copy from Extended'),    _('Copy weights from Extended weightmaps.')),
            ('SWAP',       _('Swap Weight Groups'),    _('Swap Weights of Collision Volumes with corresponding SL Bones.\nHandle with care')),
            ('FACEGEN', _('Face Map Generator'),    _('Generate Head Weight Maps. Works only on head bones (face bones)!.\nPlease use the Operator panel to tweak the values!\nHandle with care')),
            ),
        name=_("Weights"),
        description=_("From where to get the initial weight data"),
        default='AUTOMATIC')

    clearTargetWeights = BoolProperty(default=True, name=_("Clear weights"),
        description=_("Reset affected target vertices before Copying the weights. Works also with 'Only selected vertices' "))

    attachSliders = BoolProperty(default=True, name=_("Attach Sliders"),
        description=_("Attach the Appearance Sliders after binding"))
    enable_unsupported = BoolProperty(default=True, name=_("Attach Sliders"),
        description=_("Attach the Appearance Sliders after binding"))
        
    copyWeightsSelected = BoolProperty(default=False, name=_("Selected verts"),
        description=_("Copy weights only to selected vertices in the target mesh"))

    submeshInterpolation = BoolProperty(default=True, name=_("Interpolate"),
        description=_("Interpolate the weight values from closests point on surface of reference mesh") )

    keep_groups = BoolProperty(default=False, name=_("Keep Groups"),
        description=_("When transfering weights maps, keep empty weight maps in the target mesh(es). By default empty weight maps are deleted after weight transfer") )

    all_selected = BoolProperty(
        name = "Apply to Selected",
        default = False, 
        description = \
''' Apply the Operator to the current Object selection

If this property is disabled, then only
take the active Object into account.
'''
        )

    generate_weights = BoolProperty(default=False, name=_("Generate Weights"),
        description=_("For Fitted Mesh: Create weights 'automatic from bone' for BUTT, HANDLES, PECS and BACK") )

    butt_strength   = FloatProperty(name = _("Butt Strength"),   min = 0.0, max = 1.0, default = 0.5)
    pec_strength    = FloatProperty(name = _("Pec Strength"),    min = 0.0, max = 1.0, default = 0.5)
    back_strength   = FloatProperty(name = _("Back Strength"),   min = 0.0, max = 1.0, default = 0.5)
    handle_strength = FloatProperty(name = _("Handle Strength"), min = 0.0, max = 1.0, default = 0.5)

    with_hair = BoolProperty(default=True, name=_("Hair"),
        description=_("Include Karaage hair mesh as Weight Source") )
    with_head = BoolProperty(default=True, name=_("Head"),
        description=_("Include Karaage head mesh as Weight Source") )
    with_eyes = BoolProperty(default=True, name=_("Eyes"),
        description=_("Include Karaage eye meshes as Weight Source") )
    with_upper_body = BoolProperty(default=True, name=_("Upper Body"),
        description=_("Include Karaage upper body mesh as Weight Source") )
    with_lower_body = BoolProperty(default=True, name=_("Lower Body"),
        description=_("Include Karaage lower body mesh as Weight Source") )
    with_skirt = BoolProperty(default=True, name=_("Skirt"),
        description=_("Include Karaage skirt mesh as Weight Source") )

    weight_eye_bones = BoolProperty(default=False, name=_("With Eye Bones"),
        description=_("Generate Weights also for Eye Bones") )

    copy_pose_begin = IntProperty(default=0, min=0, name=_("Begin"),
            description=_("First source frame for a timeline copy") )
    copy_pose_end = IntProperty(default=0, min=0, name=_("End"),
            description=_("Last source frame for a timeline copy") )
    copy_pose_to = IntProperty(default=0, min=0, name=_("To"),
            description=_("First target frame for a timeline copy") )
    copy_pose_loop_at_end = BoolProperty(default=False, name=_("Create endframe"),
            description=_("Terminate target range with copy of first source frame (only if first source frame has keyframes)"))
    copy_pose_loop_at_start = BoolProperty(default=False, name=_("Create startframe"),
            description=_("Generate keyframes for first source key (if it has no keyframes yet)"))
    copy_pose_clean_target_range = BoolProperty(default=False, name=_("Replace"),
            description=_("Cleanup target range before copy (removes keyframes)"))
    copy_pose_x_mirror = BoolProperty(default=False, name=_("x-mirror"),
            description=_("Does an x-mirror copy (for walk cycles)"))

    apply_shrinkwap_to_mesh = BoolProperty(default=True, name=_("Apply Shrinkwrap"),
        description=_("Apply Shrinkwrap modifier while Baking Shape to Mesh"))

class WeightsProp(bpy.types.PropertyGroup):
    pass

class StringListProp(bpy.types.PropertyGroup):
    name = StringProperty()

class UpdateRigProp(bpy.types.PropertyGroup):
    transferMeshes = BoolProperty(
        name = "Transfer Meshes",
        default = False,
        description = "Migrate Child Meshes from Source armature to target Armature"
    )

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

    attachSliders = BoolProperty(default=True, name=_("Attach Sliders"),
        description=_("Attach the Appearance Sliders after binding"))

    applyRotation = BoolProperty(default=True, name="Apply Rot&Scale",
        description="Apply Rotation before converting (use if Rig contains meshes with inconsistent rotations and scales)")

    is_male = BoolProperty(default=False, name=_("Male"),
        description=_("Use the Male skeleton for binding"))

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

    handleTargetMeshSelection = EnumProperty(
        items=(
            ('KEEP',   _('Keep'), _('Keep Karaage Meshes in Target Armature(s)')),
            ('HIDE',   _('Hide'), _('Hide Karaage meshes in Target Armature(s)')),
            ('DELETE', _('Delete'), _('Delete Karaage Meshes from Target Armature(s)'))),
        name=_("Original"),
        description=_("How to treat the Karaage Meshes in the Target Armature(s)"),
        default='KEEP')

    apply_pose = BoolProperty(
        name="Apply Pose",
        default=True, 
        description="Apply pose of source rig to character mesh(es) before Transfering the rig.\n\nYou want to enable this option only if you\nintend to use the current pose as the new restpose.\nIn that case joint offsets will be generated as well!"
        )

    base_to_rig     = BoolProperty(
        name="Reverse Snap",
        description = "Reverse the snapping direction: Adjust the Rig bones to the Base bones",
        default     = False
    )
    
    adjust_origin = EnumProperty(
        items=(
            ('ROOT_TO_ORIGIN',   'Armature', 'Move the Root Bone to the Armature Origin Location.\nThe location of the Armature in the scene is not affected'),
            ('ORIGIN_TO_ROOT',   'Rootbone', 'Move the Armature Origin Location to the Root Bone.\nThe location of the Armature in the scene is not affected')
        ),
        name="Origin",
        description="Matches the Karaage Root Bone with the Karaage Origin location.\nThis must be done to keep the Sliders working correct.",
        default='ROOT_TO_ORIGIN'
    )
    
    bone_repair     = BoolProperty(
        name        = "Rebuild missing Bones",
        description = "Reconstruct all missing bones.\nThis applies when bones have been removed from the original rig\n\nIMPORTANT: when you convert a Basic Rig to an Extended Rig\nthen you should enable this option\nOtherwise the extended (Bento) bones are not generated.",
        default     = False
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
        description = "Ensure that the bone ends are defined according to the SL Skeleton Specification.\nYou probably need this when you import a Collada devkit\nbecause Collada does not maintain Bone ends (tricky thing)\n\nHint: \nDisable this option\n- when you transfer a non human character\n- or when you know you want to use Joint Positions",
        default     = True
    )
    sl_bone_rolls = const.sl_bone_rolls

    align_to_deform = EnumProperty(
        items=(
            ('DEFORM_TO_ANIMATION', 'Pelvis', 'Move mPelvis to Pelvis'),
            ('ANIMATION_TO_DEFORM', 'mPelvis', 'Move Pelvis to mPelvis')
        ),
        name="Align to",
        description = UpdateRigProp_align_to_deform_description,
        default='ANIMATION_TO_DEFORM'
    )

    align_to_rig = EnumProperty(
        items=(
            ('DEFORM_TO_ANIMATION', 'Green Animation Rig', 'Move Deform Bones to Animation Bone locations'),
            ('ANIMATION_TO_DEFORM', 'Blue Deform Rig', 'Move Animation Bones to Deform Bone Locations')
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

def BLinitialisation():
    ##

    ##

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)

    try:
        from . import wingdbstub
    except ImportError:
        pass

    bpy.types.Object.IKSwitches = PointerProperty(type = IKSwitches)

    bpy.types.Scene.MocapProp = PointerProperty(type = MocapProp)

    for bone in data.get_mtui_bones():
        setattr(MocapProp, bone, StringProperty() )

    MocapProp.sources = bpy.props.CollectionProperty(type=StringListProp)
    MocapProp.targets = bpy.props.CollectionProperty(type=StringListProp)

    bpy.types.Object.ObjectProp          = PointerProperty(type = ObjectProp)
    bpy.types.Scene.SceneProp            = PointerProperty(type = SceneProp)
    bpy.types.Scene.MeshProp             = PointerProperty(type = MeshProp)
    bpy.types.Scene.UpdateRigProp        = PointerProperty(type = UpdateRigProp)
    bpy.types.Scene.WeightsProp          = PointerProperty(type = WeightsProp)

    bpy.types.WindowManager.LoggerIndexProp = PointerProperty(type=LoggerPropIndex)
    bpy.types.WindowManager.LoggerPropList = CollectionProperty(type=LoggerProp)

    bones = data.get_base_bones()
    for bone in bones:
        setattr(WeightsProp, bone, FloatProperty(default=0.0, min=0.0, max=1.0, name=bone))

    bpy.types.Object.karaageMaterialProps = PointerProperty(type = KaraageMaterialProps)

    animation.initialisation()
    shape.shapeInitialisation()
    weights.fittingInitialisation()

    bpy.types.Object.karaageAlphaMask = bpy.props.EnumProperty(
        name="Vertex Group",
        description="Name of the vertex group",
        items=vgroup_items)

    init_log_level(bpy.context)

    bpy.app.handlers.scene_update_post.append(rig.sync_timeline_action)
    bpy.app.handlers.scene_update_post.append(rig.check_dirty_armature_on_update)
    bpy.app.handlers.scene_update_post.append(fix_bone_layers_on_update)
    bpy.app.handlers.scene_update_post.append(check_for_armatures_on_update)
    bpy.app.handlers.scene_update_post.append(check_for_system_mesh_edit)
    bpy.app.handlers.scene_update_post.append(weights.edit_object_change_handler)
    bpy.app.handlers.scene_update_post.append(rig.fix_linebones_on_update)

    bpy.app.handlers.load_post.append(fix_bone_layers_on_load)
    bpy.app.handlers.load_post.append(fix_karaage_data_on_load)
    bpy.app.handlers.frame_change_post.append(shape.update_on_framechange)

def vgroup_items(self, context):
    return [(vgroup.name, vgroup.name, "") for vgroup in context.active_object.vertex_groups]

def karaage_docs():
    url_manual_mapping = (
        ("bpy.ops.karaage.load_shape_ui",            "mesh_shapes?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.print_props",              "mesh_shapes?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.save_props",               "mesh_shapes?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.load_props",               "mesh_shapes?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.reset_to_default",         "mesh_shapes?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.delete_all_shapes",        "mesh_shapes?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.refresh_character_shape",  "mesh_shapes?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.import_shape",             "karaage_shapes?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.ikmatch_display_details",  "ik_controls?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.ik_match_all",             "ik_controls?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.ik_*_orient",              "ik_controls?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.ik*_enable",               "ik_controls?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.chain_*",                  "ik_controls?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.*set_rotation_limits",     "rig_controls?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.breathe_*",                "rig_controls/#breathing?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.expressions",              "face_expressions?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.bone_preset_*",            "bone_display/#presets?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.use_*_shapes",             "rig_display/#control_style?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.bone_display_details",     "bone_display/#toolshelf?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.export_anim",              "export_animation?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.guess_bone_map",           "motion_transfer/#guess_bone_map?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.set_source_bone",          "motion_transfer/#set_source_bone?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.clear_bone_map",           "motion_transfer/#clear_bone_map?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.copy_other_side",          "motion_transfer/#copy_other_side?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.transfer_pose",            "motion_transfer/#transfer_pose?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.match_scales",             "motion_transfer/#match_scales?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.delete_motion",            "motion_transfer/#delete_motion?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.transfer_motion",          "motion_transfer/#transfer_motion?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.add_sl_avatar",            "add_avatar?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.unparent_armature",        "binding#unparent_armature?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.parent_armature",          "binding#parent_armature?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.clearTargetWeights",    "binding#clear_weights?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.copyWeightsSelected",   "binding#clear_weights?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.weight_eye_bones",      "binding#clear_weights?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.submeshInterpolation",  "binding#submeshInterpolation?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.toTPose",               "binding#clear_weights?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.attach_shape_sliders",     "skinning?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.generate_weights",         "skinning?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.revert_shape_sliders",     "skinning?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.apply_shape_sliders",      "skinning?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.with*",                 "skinning?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.keep_groups",           "skinning?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.clearTargetWeights",    "skinning?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.copyWeightsSelected",   "skinning?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.find_doubles",             "find_verts#doubles?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.find_unweighted",          "find_verts#weight_none?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.find_zeroweights",         "find_verts#weight_zero?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.find_toomanyweights",      "find_verts#weight_limit?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.freeze_shape",             "freeze_shape?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.copy_bone_weights",        "copy_bone_weights?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.export_sl_collada",        "export_mesh?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.armature_allow_structure_select",    "rigging#structure_select?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.armature_restrict_structure_select", "rigging#structure_select?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.armature_*lock_*",                   "rigging#transform_loc?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.armature_bake",                      "rigging#bake_restpose?"+TOOL_PARAMETER),
        ("bpy.types.Meshprop.adjustPoleAngle",                 "rigging#pole_angle?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.check_mesh",               "check_mesh?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.armature_deform_enable",   "rigging?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.armature_deform_disable",  "rigging?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.armature_adjust_base2rig", "rigging#adjust_base?"+TOOL_PARAMETER),
        ("bpy.ops.karaage.copy_rig", "update_rig?"+TOOL_PARAMETER),

    )
    return HELP_PAGE, url_manual_mapping

addon_keymaps = []
SEPARATOR     = "===================================================================="

def register_templates():

    if 'toolset_pro' in dir(bpy.ops.sparkles):
        try:
            import sparkles
            path = os.path.join(TEMPLATE_DIR,"*.blend")
            sparkles.register_template_path(path, 'Karaage Templates')
            print("Added Karaage Templates to Sparkles Template list.")

            return 'sparkles'
        except:
            pass
    return 'local'

def sl_skeleton_func_export(self, context):
    self.layout.operator("karaage.export_sl_avatar_skeleton")

def sl_skeleton_func_import(self, context):
    self.layout.operator("karaage.import_sl_avatar_skeleton")

def sl_animation_func_import(self, context):
    self.layout.operator("karaage.import_avatar_animation")

def register():

    bpy.utils.register_module(__name__)

    bpy.types.INFO_MT_help.prepend(menu_help_karaage)
    bpy.types.INFO_MT_file.prepend(menu_add_templates)
    bpy.types.INFO_MT_add.append(menu_add_karaage)
    bpy.types.INFO_MT_file_export.prepend(menu_export_collada)
    bpy.types.INFO_MT_file_import.append(menu_import_karaage_shape)
    
    bpy.types.INFO_MT_file_export.append(sl_skeleton_func_export)
    bpy.types.INFO_MT_file_import.append(sl_skeleton_func_import)
    bpy.types.INFO_MT_file_import.append(sl_animation_func_import)

    BLinitialisation()

    has_warnings = False
    if bpy.app.version_cycle != 'release':
        logging.warn(SEPARATOR)
        logging.warn(_("Karaage:  Your Blender instance is in state '%s'"), bpy.app.version_cycle)
        logging.warn(_("          We recommend to install this addon only on official"))
        logging.warn(_("          Blender releases from Blender.org"))
        has_warnings = True

    bpy.utils.register_manual_map(karaage_docs)

    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name="3D View", space_type='VIEW_3D')
    kmi = km.keymap_items.new(ButtonRefreshShape.bl_idname, 'Q', 'PRESS', alt=True)
    addon_keymaps.append((km,kmi))

    karaage_init    = __file__
    karaage_home    = os.path.dirname(karaage_init)
    karaage_presets = os.path.join(karaage_home, "presets")
    blender_scripts  = bpy.utils.user_resource('SCRIPTS', "presets")
    destdir          = os.path.join(blender_scripts, __name__)
    util.copydir(karaage_presets,destdir,overwrite=True)

    const.register_icons()

    if has_warnings:
        logging.warn(SEPARATOR)

def unregister():

    try:

        bpy.app.handlers.scene_update_post.remove(weights.edit_object_change_handler)
        bpy.app.handlers.scene_update_post.remove(check_for_system_mesh_edit)
        bpy.app.handlers.scene_update_post.remove(check_for_armatures_on_update)
        bpy.app.handlers.scene_update_post.remove(fix_bone_layers_on_update)
        bpy.app.handlers.scene_update_post.remove(rig.sync_timeline_action)
        bpy.app.handlers.scene_update_post.remove(rig.check_dirty_armature_on_update)
        bpy.app.handlers.scene_update_post.remove(rig.fix_linebones_on_update)
        bpy.app.handlers.load_post.remove(fix_bone_layers_on_load)
        bpy.app.handlers.load_post.remove(fix_karaage_data_on_load)
        bpy.app.handlers.frame_change_post.remove(shape.update_on_framechange)

        bpy.types.INFO_MT_file_export.remove(sl_skeleton_func_export)
        bpy.types.INFO_MT_file_import.remove(sl_skeleton_func_import)
        bpy.types.INFO_MT_file_import.remove(sl_animation_func_import)
        bpy.types.INFO_MT_help.remove(menu_help_karaage)
        bpy.types.INFO_MT_add.remove(menu_add_karaage)
        bpy.types.INFO_MT_file_export.remove(menu_export_collada)
        bpy.types.INFO_MT_file.remove(menu_add_templates)
        bpy.types.INFO_MT_file_import.remove(menu_import_karaage_shape)

    except:
        pass

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    del bpy.types.Object.IKSwitches
    del bpy.types.Object.karaageMaterialProps
    del bpy.types.Object.karaageAlphaMask
    del bpy.types.Scene.MocapProp
    del bpy.types.Scene.MeshProp
    del bpy.types.Scene.SceneProp
    del bpy.types.Object.ObjectProp
    del bpy.types.Scene.UpdateRigProp
    del bpy.types.Scene.WeightsProp

    del bpy.types.WindowManager.LoggerIndexProp
    del bpy.types.WindowManager.LoggerPropList

    const.unregister_icons()
    bpy.utils.unregister_manual_map(karaage_docs)

    bpy.utils.unregister_module(__name__)

    user_templates = None
    print("Karaage Shutdown Completed")

if __name__ == "__main__":

    register()

#
#
#
#
#
#
#
#
