# Copyright (C) 2023 Daniel Boxer

import bpy
import bmesh
import random
import time


class POLYBLOCKER_OT_bump(bpy.types.Operator):
    bl_idname = "polyblocker.bump"
    bl_label = "Bump"
    bl_description = "Proportional translate constrained to normal"
    bl_options = {"UNDO", "REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        old_pivot_point = context.scene.tool_settings.transform_pivot_point
        context.scene.tool_settings.transform_pivot_point = "INDIVIDUAL_ORIGINS"

        bm = bmesh.from_edit_mesh(context.object.data)
        s_verts = [v for v in bm.verts if v.select]

        size = 1
        if len(s_verts) > 0:
            # use avg edge length for size
            edges = s_verts[0].link_edges
            if len(edges) > 0:
                edge_sum = sum(e.calc_length() for e in edges)
                # multiply by 3 for more rounded bump
                size = (edge_sum / len(edges)) * 3

        bpy.ops.transform.translate(
            "INVOKE_DEFAULT",
            constraint_axis=(False, False, True),
            orient_type="NORMAL",
            use_proportional_edit=True,
            proportional_size=size,
        )
        context.scene.tool_settings.transform_pivot_point = old_pivot_point
        return {"FINISHED"}


class POLYBLOCKER_OT_random_bumps(bpy.types.Operator):
    bl_idname = "polyblocker.random_bumps"
    bl_label = "Random Bumps"
    bl_description = "Random bumps"
    bl_options = {"UNDO", "REGISTER"}

    amount: bpy.props.IntProperty(name="Amount", min=0, default=5)
    depth: bpy.props.FloatProperty(name="Depth", default=0.1)
    falloff_size: bpy.props.FloatProperty(name="Falloff Size", default=1, min=0.01)
    seed: bpy.props.IntProperty(name="Seed", min=0)
    mode: bpy.props.EnumProperty(
        name="Mode", items=[("BUMP", "Bump", ""), ("INDENT", "Indent", "")]
    )

    def execute(self, context):
        obj = context.object
        old_mode = obj.mode
        bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(obj.data)

        for vert in bm.verts:
            vert.select = False
        for face in bm.faces:
            face.select = False
        if not self.options.is_repeat:
            size = sum(obj.dimensions) / 60
            self.depth = size
            self.falloff_size = size * 6
            self.seed = int(time.time() * 1000) % 1000
        
        random.seed(self.seed)
        depth = self.depth if self.mode == "BUMP" else -self.depth
        bm.verts.ensure_lookup_table()
        for v in (random.randint(0, len(bm.verts) - 1) for _ in range(self.amount)):
            bm.verts[v].select = True
            bpy.ops.transform.translate(
                value=(0, 0, depth),
                constraint_axis=(False, False, True),
                orient_type="NORMAL",
                use_proportional_edit=True,
                proportional_size=self.falloff_size,
            )
            bm.verts[v].select = False

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode=old_mode)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "amount")
        layout.prop(self, "depth")
        layout.prop(self, "falloff_size")
        layout.prop(self, "seed")
        row = layout.row()
        row.prop(self, "mode", expand=True)
