# Copyright (C) 2023 Daniel Boxer

import bpy
import bmesh
from mathutils import Vector


class POLYBLOCKER_OT_cap_tool(bpy.types.Operator):
    bl_idname = "polyblocker.cap_tool"
    bl_label = "Cap Tool"
    bl_description = "Cap"
    bl_options = {"UNDO", "GRAB_CURSOR", "BLOCKING"}

    loop_count: bpy.props.IntProperty(default=5)
    scale_fac: bpy.props.FloatProperty(default=0.15)

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.mode == "EDIT"

    def invoke(self, context, event):
        self.init_mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))
        self.bm = bmesh.from_edit_mesh(context.object.data)

        start_verts = set()
        normal_sum = Vector()
        self.origin_faces = []
        active_face = self.bm.faces.active
        # get selected faces
        for f in self.bm.faces:
            if f.select:
                start_verts.update(list(f.verts))
                if f == active_face:
                    # active face is stored at start of list
                    self.origin_faces.insert(0, f)
                else:
                    self.origin_faces.append(f)
                normal_sum += f.normal
                f.select = False
                f.hide = True
                for e in f.edges:
                    e.hide = True
        self.bm.faces.active = None

        if len(self.origin_faces) == 0:
            self.report({"ERROR"}, "No faces selected")
            return {"CANCELLED"}

        self.avg_normal = normal_sum / len(self.origin_faces)

        # extrude and store new geometry
        new_verts = []
        new_verts_co = []
        segment_edge = None
        for g in bmesh.ops.extrude_face_region(self.bm, geom=self.origin_faces)["geom"]:
            if isinstance(g, bmesh.types.BMVert):
                new_verts.append(g)
                # need to make vector copy
                new_verts_co.append(g.co.copy())

                # find edge for loop cuts
                for e in g.link_edges:
                    if e.other_vert(g) in start_verts:
                        segment_edge = e
                        break
            elif isinstance(g, bmesh.types.BMFace):
                g.hide = False
                for e in g.edges:
                    e.hide = False
                g.select = True

        self.loops = []
        self.init_loop_co = []
        old_verts = set(self.bm.verts)
        for _ in range(self.loop_count):
            self.add_segment(segment_edge, old_verts)

        # see if order is correct
        found = False
        for e in self.loops[-1][0].link_edges:
            if e.other_vert(self.loops[-1][0]) in start_verts:
                found = True
                break
        # fix order
        if found:
            self.loops.reverse()
            self.init_loop_co.reverse()

        # add initial faces as last loop
        self.loops.append(new_verts)
        self.init_loop_co.append(new_verts_co)

        context.window.cursor_set("SCROLL_XY")
        context.workspace.status_text_set(
            "Left Click: Confirm     Right Click/Esc: Cancel"
            "     Scroll: Add/Remove Loops"
        )
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "MOUSEMOVE":
            self.update(context, event)
        elif event.type == "WHEELUPMOUSE" and self.loop_count < 500:
            segment_edge = None
            start_verts = set(v for f in self.origin_faces for v in f.verts)
            for v in self.loops[0]:
                for e in v.link_edges:
                    if e.other_vert(v) in start_verts:
                        segment_edge = e
                        break
            self.add_segment(segment_edge, set(self.bm.verts), append_seg=False)
            self.update(context, event)
        elif event.type == "WHEELDOWNMOUSE" and self.loop_count > 1:
            bmesh.ops.dissolve_edges(
                self.bm,
                edges=[
                    e
                    for e in self.bm.edges
                    if e.verts[0] in set(self.loops[0])
                    and e.verts[1] in set(self.loops[0])
                ],
            )
            bmesh.ops.dissolve_verts(self.bm, verts=self.loops[0])
            del self.loops[0]
            del self.init_loop_co[0]
            self.loop_count -= 1
            # select first loop
            for f in self.bm.faces:
                if len(set(f.verts).difference(set(self.loops[0]))) != len(f.verts):
                    f.select = True
            self.update(context, event)
        elif event.type == "LEFTMOUSE":
            self.finish(context)
            return {"FINISHED"}
        elif event.type in {"RIGHTMOUSE", "ESC"}:
            self.finish(context, revert=True)
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def update(self, context, event):
        current_pos = Vector((event.mouse_region_x, event.mouse_region_y))
        distance_px = (current_pos - self.init_mouse_pos).length
        ratio = distance_px / ((context.region.width + context.region.height) / 2)
        # get approximate distance relative to viewport
        distance_m = ratio * context.area.spaces.active.region_3d.view_distance
        # get translate vector
        displacement = self.avg_normal * distance_m

        def falloff(segment_idx, max_val):
            return (
                max_val
                * (self.scale_fac ** ((segment_idx + 1) / (self.loop_count + 1)) - 1)
                / (self.scale_fac - 1)
            )

        for loop_idx, loop in enumerate(self.loops):
            v_sum = Vector()
            falloff_dist = falloff(loop_idx, displacement)
            for v_idx, v in enumerate(loop):
                # move loop
                new_co = self.init_loop_co[loop_idx][v_idx] + falloff_dist
                v.co = new_co
                v_sum += new_co

            center = v_sum / len(loop)
            for v_idx, v in enumerate(loop):
                # scale loop
                v.co = center + (v.co - center) * falloff(
                    self.loop_count - loop_idx, 1  # reverse falloff
                )

        # calling this with no args fixes dark faces bug?
        bmesh.ops.triangulate(self.bm)
        bmesh.update_edit_mesh(context.object.data)

        context.area.header_text_set(
            f"D: {distance_m:.5f} m     Segments: {self.loop_count}"
        )

    def add_segment(self, segment_edge, old_verts, append_seg=True):
        def walk(edge):
            yield edge
            edge.tag = True
            for l in edge.link_loops:
                loop = l.link_loop_radial_next.link_loop_next.link_loop_next
                if not (len(loop.face.verts) != 4 or loop.edge.tag):
                    yield from walk(loop.edge)

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
        if append_seg:
            # segment is added in invoke
            self.loops.append(new)
            self.init_loop_co.append([v.co.copy() for v in new])
        else:
            # segment is added during modal
            self.loops.insert(0, new)
            # the new loop will start with some displacement
            # so use values of other loop but keep new sign
            no_disp_co = [
                Vector(
                    (
                        abs(c2.x) if c1.x >= 0 else -abs(c2.x),
                        abs(c2.y) if c1.y >= 0 else -abs(c2.y),
                        abs(c2.z) if c1.z >= 0 else -abs(c2.z),
                    )
                )
                for c1, c2 in zip([v.co.copy() for v in new], self.init_loop_co[0])
            ]
            self.init_loop_co.insert(0, no_disp_co)
            self.loop_count += 1

    def finish(self, context, revert=False):
        if revert:
            # delete new geometry
            bmesh.ops.delete(self.bm, geom=[v for loop in self.loops for v in loop])
            bmesh.ops.recalc_face_normals(self.bm, faces=self.origin_faces)
            self.bm.faces.active = self.origin_faces[0]
            for f in self.origin_faces:
                f.hide = False
                for e in f.edges:
                    e.hide = False
                f.select = True
        else:
            # delete original faces
            bmesh.ops.delete(self.bm, geom=self.origin_faces, context="FACES")
        bmesh.update_edit_mesh(context.object.data)
        context.area.header_text_set(None)
        context.workspace.status_text_set(None)
