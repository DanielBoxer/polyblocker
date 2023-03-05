# Copyright (C) 2023 Daniel Boxer

import bpy
import bmesh
from mathutils import Vector
from . import line_draw


class POLYBLOCKER_OT_cap_tool(bpy.types.Operator):
    bl_idname = "polyblocker.cap_tool"
    bl_label = "Cap Tool"
    bl_description = "Cap"
    bl_options = {"UNDO", "GRAB_CURSOR", "BLOCKING"}

    loop_count: bpy.props.IntProperty(name="Segments", default=5)
    scale_fac: bpy.props.FloatProperty(name="Scale", default=0.15)
    invert: bpy.props.BoolProperty(name="Invert")
    control_len: bpy.props.BoolProperty(name="Control Length")
    flip_scale: bpy.props.BoolProperty(name="Flip Scale")

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.mode == "EDIT" and obj.type == "MESH"

    def invoke(self, context, event):
        self.init_mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))
        self.bm = bmesh.from_edit_mesh(context.object.data)

        active_face = None
        connected_groups = []
        # get selected faces and find connected
        for f in self.bm.faces:
            if f.select:
                if f == self.bm.faces.active:
                    active_face = f
                found_groups = []
                for group in connected_groups:
                    # faces are connected if they share 2 or more verts
                    if len(set(f.verts).intersection(group["verts"])) >= 2:
                        found_groups.append(group)

                # merge all found groups
                merged_group = {"faces": set([f]), "verts": set(f.verts)}
                for group in found_groups:
                    merged_group["faces"].update(group["faces"])
                    merged_group["verts"].update(group["verts"])
                    connected_groups.remove(group)
                connected_groups.append(merged_group)

        if len(connected_groups) == 0:
            self.report({"ERROR"}, "No faces selected")
            return {"CANCELLED"}

        start_verts = set()
        normal_sum = Vector()
        self.origin_faces = []
        largest_group = max(connected_groups, key=lambda group: len(group["faces"]))
        # deselect other groups
        for group in connected_groups:
            if group != largest_group:
                for f in group["faces"]:
                    f.select = False
        largest_group = set(largest_group["faces"])
        for f in largest_group:
            start_verts.update(list(f.verts))
            self.origin_faces.append(f)
            normal_sum += f.normal
            f.select = False
            f.hide = True
            for e in f.edges:
                # check if boundary
                if len(set(e.link_faces).intersection(largest_group)) > 1:
                    e.hide = True
        self.avg_normal = normal_sum / len(self.origin_faces)

        # extrude and store new geometry
        new_verts = []
        new_verts_co = []
        for g in bmesh.ops.extrude_face_region(self.bm, geom=self.origin_faces)["geom"]:
            if isinstance(g, bmesh.types.BMVert):
                new_verts.append(g)
                # need to make vector copy
                new_verts_co.append(g.co.copy())
            elif isinstance(g, bmesh.types.BMEdge):
                g.hide = False
            elif isinstance(g, bmesh.types.BMFace):
                g.hide = False
                g.select = True
        self.bm.faces.active = active_face

        self.loops = []
        self.init_loop_co = []
        old_verts = set(self.bm.verts)
        segment_edge = self.get_segment_edge(new_verts[0], start_verts)
        for _ in range(self.loop_count):
            try:
                self.segment(segment_edge, old_verts)
            except AttributeError:
                self.report({"ERROR"}, "Too many faces selected")
                bmesh.ops.delete(self.bm, geom=new_verts)
                self.finish(context, revert=True)
                return {"CANCELLED"}

        # fix order
        if len(self.loops) > 0:
            if self.get_segment_edge(self.loops[0][0], start_verts) is None:
                self.loops.reverse()
                self.init_loop_co.reverse()
        # add initial faces as last loop
        self.loops.append(new_verts)
        self.init_loop_co.append(new_verts_co)
        if len(self.loops) == 1:
            self.select_first()

        self.segment_input = ""
        context.window.cursor_set("SCROLL_XY")
        context.workspace.status_text_set(
            "Left Click: Confirm     Right Click/Esc: Cancel"
            "     Scroll: Add/Remove Segments     Numpad: Set Segments"
            "     A/D: Change Scale     F: Flip Scale     C: Control Length"
            "     I: Invert     R: Reset"
        )
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        try:
            if event.type == "MOUSEMOVE":
                self.update(context, event)
            elif event.type == "WHEELUPMOUSE" and self.loop_count < 250:
                self.add_segment()
                self.update(context, event)
            elif event.type == "WHEELDOWNMOUSE" and self.loop_count > 0:
                self.del_segment()
                self.update(context, event)
            elif event.type == "A" and event.value == "PRESS" and self.scale_fac > 0.02:
                self.scale_fac -= 0.01
                self.update(context, event)
            elif event.type == "D" and event.value == "PRESS":
                self.scale_fac += 0.01
                self.update(context, event)
            elif event.type == "I" and event.value == "PRESS":
                self.invert = not self.invert
                self.update(context, event)
            elif event.type == "C" and event.value == "PRESS":
                self.control_len = not self.control_len
                self.update(context, event)
            elif event.type == "F" and event.value == "PRESS":
                self.flip_scale = not self.flip_scale
                self.update(context, event)
            elif event.type == "R" and event.value == "PRESS":
                self.set_segments(5)
                self.scale_fac = 0.15
                self.invert = False
                self.control_len = False
                self.flip_scale = False
                self.segment_input = ""
                self.update(context, event)
            elif event.type.startswith("NUMPAD_") and event.value == "PRESS":
                val = event.type[7:]
                if val.isdigit() and 0 <= int(self.segment_input + val) <= 250:
                    if len(self.segment_input) < 3:
                        self.segment_input += val
                elif val == "ENTER":
                    self.set_segments(int(self.segment_input))
                    self.segment_input = ""
                self.update(context, event)
            elif event.type == "BACK_SPACE" and event.value == "PRESS":
                self.segment_input = self.segment_input[:-1]
                self.update(context, event)
            elif event.type == "LEFTMOUSE":
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

    def update(self, context, event):
        current_pos = Vector((event.mouse_region_x, event.mouse_region_y))
        distance_px = (current_pos - self.init_mouse_pos).length
        ratio = distance_px / ((context.region.width + context.region.height) / 2)
        # get approximate distance relative to viewport
        distance_m = ratio * context.area.spaces.active.region_3d.view_distance
        if self.invert:
            distance_m *= -1
        # get translate vector
        displacement = self.avg_normal * distance_m

        def falloff(segment_idx, max_val):
            return (
                max_val
                * (self.scale_fac ** ((segment_idx + 1) / (self.loop_count + 2)) - 1)
                / (self.scale_fac - 1)
            )

        for loop_idx, loop in enumerate(self.loops):
            v_sum = Vector()
            falloff_disp = falloff(loop_idx, displacement)
            # move loop
            for v_idx, v in enumerate(loop):
                new_co = self.init_loop_co[loop_idx][v_idx] + falloff_disp
                v.co = new_co
                v_sum += new_co

            center = v_sum / len(loop)
            # scale loop
            falloff_scale = falloff(self.loop_count - loop_idx, 1)
            if self.flip_scale:
                falloff_scale = 1 / falloff_scale
            for v_idx, v in enumerate(loop):
                v.co = center + (v.co - center) * falloff_scale

        # calling this with no args fixes dark faces bug?
        bmesh.ops.triangulate(self.bm)
        bmesh.update_edit_mesh(context.object.data)

        count_txt = f"[{self.segment_input}]" if self.segment_input else self.loop_count
        invert_txt = "ON" if self.invert else "OFF"
        control_len_txt = "ON" if self.control_len else "OFF"
        flip_scale_txt = "ON" if self.flip_scale else "OFF"
        context.area.header_text_set(
            f"D: {abs(distance_m):.5f} m     Segments: {count_txt}"
            f"     Scale: {self.scale_fac:.2f}     Flip Scale: {flip_scale_txt}"
            f"     Control Length: {control_len_txt}     Invert: {invert_txt}"
        )
        line_draw.remove()
        line_draw.add((tuple(self.init_mouse_pos), tuple(current_pos)), (0, 0, 0, 1))

    def segment(self, segment_edge, old_verts):
        def walk(edge):
            yield edge
            edge.tag = True
            for l in edge.link_loops:
                loop = l.link_loop_radial_next.link_loop_next.link_loop_next
                if not (len(loop.face.verts) != 4 or loop.edge.tag):
                    yield from walk(loop.edge)

        # reset loops so initial pos is correct for new loop
        if not self.control_len:
            for loop_idx, loop in enumerate(self.loops):
                for v_idx, v in enumerate(loop):
                    v.co = self.init_loop_co[loop_idx][v_idx]
        for e in self.bm.edges:
            e.tag = False
        # do cuts one at a time to keep order
        cut_faces = bmesh.ops.subdivide_edgering(
            self.bm, edges=list(walk(segment_edge)), cuts=1
        )

        # find new loop
        new = []
        for f in cut_faces["faces"]:
            f.select = True
            for v in f.verts:
                if v not in old_verts:
                    new.append(v)
                    # keep track of new vertices
                    old_verts.add(v)

        self.loops.append(new)
        self.init_loop_co.append([v.co.copy() for v in new])

    def add_segment(self):
        start_verts = set(v for f in self.origin_faces for v in f.verts)
        segment_edge = self.get_segment_edge(self.loops[0][0], start_verts)
        self.segment(segment_edge, set(self.bm.verts))
        # move new loop to the bottom
        self.loops.insert(0, self.loops.pop())
        self.init_loop_co.insert(0, self.init_loop_co.pop())
        self.loop_count += 1

    def del_segment(self):
        lv = set(self.loops[0])
        old = [e for e in self.bm.edges if e.verts[0] in lv and e.verts[1] in lv]
        bmesh.ops.dissolve_edges(self.bm, edges=old)
        bmesh.ops.dissolve_verts(self.bm, verts=self.loops[0])
        del self.loops[0]
        del self.init_loop_co[0]
        self.select_first()
        self.loop_count -= 1

    def get_segment_edge(self, vert, start_verts):
        for e in vert.link_edges:
            if e.other_vert(vert) in start_verts:
                return e

    def set_segments(self, n):
        op = self.add_segment if n - self.loop_count > 0 else self.del_segment
        for _ in range(abs(n - self.loop_count)):
            op()

    def select_first(self):
        for v in self.loops[0]:
            for f in v.link_faces:
                if len(set(f.verts).intersection(set(self.loops[0]))) > 0:
                    f.select = True

    def finish(self, context, revert=False):
        try:
            if revert:
                # delete new geometry
                bmesh.ops.delete(self.bm, geom=[v for loop in self.loops for v in loop])
                bmesh.ops.recalc_face_normals(self.bm, faces=self.origin_faces)
                for f in self.origin_faces:
                    f.hide = False
                    f.select = True
                    for e in f.edges:
                        e.hide = False
            else:
                # delete original faces
                bmesh.ops.delete(self.bm, geom=self.origin_faces, context="FACES")
            bmesh.update_edit_mesh(context.object.data)
            context.area.header_text_set(None)
            context.workspace.status_text_set(None)
            line_draw.remove()
        except Exception as e:
            self.report({"ERROR"}, f"Error cleaning up: {str(e)}")
