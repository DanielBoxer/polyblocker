# Copyright (C) 2023 Daniel Boxer

import bpy


def name_and_icon(name):
    icon = name.replace(" ", "").upper()
    return {"text": name, "icon": f"MESH_{icon}"}


def draw_mesh_op(name, menu, location, rotation, scale, set_loc, **kwargs):
    id = name.replace(" ", "_").lower()
    op = menu.operator(f"mesh.primitive_{id}_add", **name_and_icon(name))
    if set_loc:
        op.location = location
    op.rotation = rotation
    if name != "Torus":
        op.scale = scale
    for key, value in kwargs.items():
        setattr(op, key, value)


class POLYBLOCKER_MT_pie(bpy.types.Menu):
    bl_label = "PolyBlocker"

    def draw(self, context):
        pie = self.layout.menu_pie()
        if context.object is not None and context.object.mode == "EDIT":
            pie.operator("polyblocker.add_mesh", **name_and_icon("Plane")).idx = 0
            pie.operator("polyblocker.add_mesh", **name_and_icon("Cube")).idx = 1
            pie.operator("polyblocker.add_mesh", **name_and_icon("Circle")).idx = 2
            pie.operator("polyblocker.add_mesh", **name_and_icon("UV Sphere")).idx = 3
            pie.operator("polyblocker.add_mesh", **name_and_icon("Ico Sphere")).idx = 4
            pie.operator("polyblocker.add_mesh", **name_and_icon("Cylinder")).idx = 5
            pie.operator("polyblocker.add_mesh", **name_and_icon("Cone")).idx = 6
            pie.operator("polyblocker.add_mesh", **name_and_icon("Torus")).idx = 7
        else:
            selected = context.object if len(context.selected_objects) > 0 else None
            # if 3D cursor is not at origin, use its location
            set_loc = tuple(context.scene.cursor.location) == (0, 0, 0)

            size = 1
            location = (0, 0, 0)
            rotation = (0, 0, 0)
            scale = (1, 1, 1)
            if selected is not None:
                size = max(selected.dimensions)
                location = selected.location
                rotation = selected.rotation_euler
                scale = selected.scale

            args = (pie, location, rotation, scale, set_loc)
            draw_mesh_op("Plane", *args, size=size)
            draw_mesh_op("Cube", *args)
            draw_mesh_op("Circle", *args, radius=size / 2)
            draw_mesh_op("UV Sphere", *args)
            draw_mesh_op("Ico Sphere", *args)
            draw_mesh_op("Cylinder", *args)
            draw_mesh_op("Cone", *args)
            draw_mesh_op("Torus", *args, major_radius=size / 2, minor_radius=size / 4)
