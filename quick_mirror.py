# Copyright (C) 2023 Daniel Boxer

import bpy
from mathutils import Vector, Matrix, geometry
from bpy_extras import view3d_utils
from . import line_draw


class POLYBLOCKER_OT_quick_mirror(bpy.types.Operator):
    bl_idname = "polyblocker.quick_mirror"
    bl_label = "Quick Mirror"
    bl_description = "Quick mirror"
    bl_options = {"UNDO", "BLOCKING"}

    axis_map = {0: "X", 1: "Y", 2: "Z"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH"

    def invoke(self, context, event):
        self.input = []
        self.mirror_objs = []
        self.hover_axis = None
        self.holding = False
        self.empty = None

        prefs = context.preferences.addons[__package__].preferences
        selected = context.selected_objects
        target = context.object
        is_single_obj = len(selected) == 1
        is_no_target = not context.object in selected
        if is_single_obj or is_no_target:
            if prefs.origin_method == "EMPTY":
                # make empty for mirror target
                self.empty = bpy.data.objects.new("Quick Mirror", None)
                target = self.empty
                context.scene.collection.objects.link(target)
            else:
                target = None
                for obj in selected:
                    # set origin to 0
                    mw = obj.matrix_world
                    obj.data.transform(Matrix.Translation(-(mw.inverted() @ Vector())))
                    mw.translation -= mw.translation
        
        # setup mirror mod
        for obj in selected:
            if target != obj or is_single_obj:
                m = obj.modifiers.new("Mirror", "MIRROR")
                m.use_axis[0] = False
                m.mirror_object = target
                self.mirror_objs.append({"obj": obj, "mod": m})
        
        # choose position of axis guide
        center_objs = [target]
        if is_single_obj:
            center_objs = [selected[0]]
        elif is_no_target:
            center_objs = selected
        center_sum = Vector()
        for obj in center_objs:
            local_center = sum((Vector(co) for co in obj.bound_box), Vector()) / 8
            center_sum += obj.matrix_world @ local_center
        center = center_sum / len(center_objs)

        self.axis_lines = [None] * 3
        self.axis_lines_2d = [None] * 3
        for axis in range(3):
            # get point offset from center
            def axis_point(dist, direction):
                p = center.copy()
                p[axis] += dist * direction
                return p

            # 10000 or any large number works
            self.axis_lines[axis] = (axis_point(10000, 1), axis_point(10000, -1))

            r = context.region
            r3d = context.space_data.region_3d
            # use axis of length 1 for 2d to fit in viewport better
            l1_2d = view3d_utils.location_3d_to_region_2d(r, r3d, axis_point(1, 1))
            l2_2d = view3d_utils.location_3d_to_region_2d(r, r3d, axis_point(1, -1))
            if l1_2d is None or l2_2d is None:
                self.report({"ERROR"}, "Selected object is not visible")
                self.finish(context, revert=True)
                return {"CANCELLED"}
            self.axis_lines_2d[axis] = (l1_2d, l2_2d)

            a_str = self.axis_map[axis]
            line_draw.draw_axis(a_str, line_draw.COLOURS[a_str], self.axis_lines[axis])

        # redraw fixes bug with single obj
        self.redraw_v3d(context)
        context.window.cursor_modal_set("SCROLL_XY")
        context.area.header_text_set(f"Axes: [ ]")
        context.workspace.status_text_set(
            "Left Click/Hold: Select Axes and Confirm     Right Click/Esc: Cancel"
            "     Scroll Up: Remove Axis"
        )
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        try:
            if event.type == "MOUSEMOVE":
                m_pos = Vector((event.mouse_region_x, event.mouse_region_y))
                
                # find closest axis to mouse
                min_dist = float("inf")
                axis = None
                for a in range(3):
                    l1, l2 = self.axis_lines_2d[a]
                    inter = geometry.intersect_point_line(m_pos, l1, l2)[0] - m_pos
                    dist = inter.length
                    if dist < min_dist:
                        min_dist = dist
                        axis = self.axis_map[a]

                old_axis = self.hover_axis
                if old_axis != axis:
                    # remove mirror preview or if dragging backwards
                    if not self.holding or axis in self.input:
                        self.remove(context)

                    line_draw.draw_axis(axis, (1, 1, 1, 1))
                    self.redraw_v3d(context)
                    self.add(context, axis)
                    self.hover_axis = axis

            elif event.type == "WHEELDOWNMOUSE" and event.value == "PRESS":
                self.remove(context)
            elif event.type == "LEFTMOUSE" and event.value == "PRESS":
                self.holding = True
            elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
                self.finish(context)
                return {"FINISHED"}
            elif event.type in {"RIGHTMOUSE", "ESC"}:
                self.finish(context, revert=True)
                return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Error: {str(e)}")
            self.finish(context, revert=True)
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def update(self, context):
        axes = [
            True if "X" in self.input else False,
            True if "Y" in self.input else False,
            True if "Z" in self.input else False,
        ]
        for m_obj in self.mirror_objs:
            m_obj["mod"].use_axis = axes
        s = f"{'X' if axes[0] else ''}{'Y' if axes[1] else ''}{'Z' if axes[2] else ''}"
        context.area.header_text_set(f"Axes: [ {s} ]")

    def redraw_v3d(self, context):
        context.view_layer.objects.active = context.view_layer.objects.active

    def add(self, context, axis):
        if axis not in self.input:
            self.input.append(axis)
        self.update(context)

    def remove(self, context):
        if len(self.input) > 0:
            axis = self.input.pop()
            # set old axis colour
            line_draw.draw_axis(axis, line_draw.COLOURS[axis])
            self.update(context)

    def finish(self, context, revert=False):
        if revert:
            for m_obj in self.mirror_objs:
                m_obj["obj"].modifiers.remove(m_obj["mod"])
            if self.empty is not None:
                bpy.data.objects.remove(self.empty, do_unlink=True)
        context.area.header_text_set(None)
        context.workspace.status_text_set(None)
        context.window.cursor_modal_restore()
        for axis in range(3):
            line_draw.remove(self.axis_map[axis])
        self.redraw_v3d(context)
