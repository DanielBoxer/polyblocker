# Copyright (C) 2023 Daniel Boxer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import bpy
from .ui import POLYBLOCKER_MT_pie, POLYBLOCKER_AP_preferences
from .add_mesh import POLYBLOCKER_OT_add_mesh, POLYBLOCKER_OT_make_collection
from .cap_tool import POLYBLOCKER_OT_cap_tool
from .quick_mirror import POLYBLOCKER_OT_quick_mirror
from .bump import POLYBLOCKER_OT_bump, POLYBLOCKER_OT_random_bumps


bl_info = {
    "name": "PolyBlocker",
    "author": "Daniel Boxer",
    "description": "Enhanced add mesh menu, cap tool, quick mirror, and more",
    "blender": (2, 80, 0),
    "version": (1, 3, 0),
    "location": "View3D > Ctrl Shift A/C, Alt M",
    "category": "Mesh",
}


keymaps = []
classes = (
    POLYBLOCKER_OT_add_mesh,
    POLYBLOCKER_OT_make_collection,
    POLYBLOCKER_OT_cap_tool,
    POLYBLOCKER_OT_quick_mirror,
    POLYBLOCKER_OT_bump,
    POLYBLOCKER_OT_random_bumps,
    POLYBLOCKER_MT_pie,
    POLYBLOCKER_AP_preferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    key_config = bpy.context.window_manager.keyconfigs.addon
    if key_config:
        keymap = key_config.keymaps.new("3D View", space_type="VIEW_3D")
        keymap_item = keymap.keymap_items.new(
            "wm.call_menu_pie", type="A", value="PRESS", shift=True, ctrl=True
        )
        keymap_item.properties.name = "POLYBLOCKER_MT_pie"
        keymaps.append((keymap, keymap_item))

        keymap_item = keymap.keymap_items.new(
            "polyblocker.cap_tool", type="C", value="PRESS", shift=True, ctrl=True
        )
        keymaps.append((keymap, keymap_item))

        keymap_item = keymap.keymap_items.new(
            "polyblocker.quick_mirror", type="M", value="PRESS", alt=True
        )
        keymaps.append((keymap, keymap_item))


def unregister():
    for keymap, keymap_item in keymaps:
        keymap.keymap_items.remove(keymap_item)
    keymaps.clear()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
