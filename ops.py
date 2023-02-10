# Copyright (C) 2023 Daniel Boxer

import bpy
import bmesh
from mathutils import Vector, Matrix


class POLYBLOCKER_OT_add_mesh(bpy.types.Operator):
    bl_idname = "polyblocker.add_mesh"
    bl_label = "Add Mesh"
    bl_description = "Add mesh"
    bl_options = {"UNDO", "REGISTER"}

    idx: bpy.props.IntProperty(options={"SKIP_SAVE"})
    location: bpy.props.FloatVectorProperty(
        subtype="TRANSLATION", description="Translate on local axes"
    )
    rotation: bpy.props.FloatVectorProperty(
        subtype="EULER", description="Rotate on local axes"
    )
    scale: bpy.props.FloatVectorProperty(
        default=(1, 1, 1), subtype="XYZ", description="Scale on local axes"
    )

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.mode == "EDIT"

    def execute(self, context):
        obj = context.object

        # clear old properties
        if not self.options.is_repeat:
            self.location = (0, 0, 0)
            self.rotation = (0, 0, 0)
            self.scale = (1, 1, 1)

        # get meshes in edit mode
        meshes = []
        for obj in bpy.data.objects:
            if obj.mode == "EDIT":
                meshes.append({"obj": obj})

        # need to go into obj mode for transform
        bpy.ops.object.mode_set(mode="OBJECT")
        for mesh in meshes:
            obj = mesh["obj"]
            mesh["transform"] = obj.matrix_basis.copy()
            # apply transform
            obj.data.transform(obj.matrix_basis)
            obj.matrix_basis.identity()
        bpy.ops.object.mode_set(mode="EDIT")

        # get selected geometry
        s_verts = []
        s_edges = []
        s_faces = []
        for mesh in meshes:
            bm = bmesh.from_edit_mesh(mesh["obj"].data)
            mesh["bm"] = bm
            s_verts.extend([v for v in bm.verts if v.select])
            s_edges.extend([e for e in bm.edges if e.select])

            for f in bm.faces:
                if f.select:
                    s_faces.append(f)
                    # deselect geometry
                    f.select = False

        mesh_normal = Vector()
        mesh_center = Vector()
        align_matrix = Matrix()
        # calculate normal and center
        if len(s_verts) > 0:
            faces = s_faces
            if len(faces) == 0:
                # use faces close by if no faces found
                faces = set()
                for v in s_verts:
                    faces.update(v.link_faces)

            # if faces found, calculate avg normal and median
            if len(faces) > 0:
                sum_normal = Vector()
                sum_median = Vector()
                for face in faces:
                    sum_normal += face.normal
                    sum_median += face.calc_center_median()
                mesh_normal = sum_normal / len(faces)
                mesh_center = sum_median / len(faces)

            align_matrix = mesh_normal.to_track_quat("Z", "Y").to_matrix().to_4x4()

        size = 1
        if len(s_verts) == 0:
            # nothing selected
            max_dim = max(obj.dimensions)
            if max_dim > 0:
                size = max_dim
        elif len(s_verts) == 1:
            # 1 vert selected
            edge_sum = 0
            edges = s_verts[0].link_edges
            if len(edges) > 0:
                for edge in edges:
                    edge_sum += edge.calc_length()
                size = edge_sum / len(edges)
            mesh_center = s_verts[0].co
        elif len(s_edges) == 1:
            # 1 edge selected
            size = s_edges[0].calc_length()
            mesh_center = (s_edges[0].verts[0].co + s_edges[0].verts[1].co) / 2
        else:
            # faces, edges, or verts are selected
            local_x_axis = align_matrix.col[0].normalized()
            local_y_axis = align_matrix.col[1].normalized()

            min_x = float("inf")
            max_x = -float("inf")
            min_y = float("inf")
            max_y = -float("inf")
            geom = s_edges if len(s_edges) > 1 else s_verts
            for g in geom:
                # use edge midpoints to avoid diagonals
                midpoint = (
                    (g.verts[0].co + g.verts[1].co) / 2 if len(s_edges) > 1 else g.co
                )
                x_val = midpoint.dot(local_x_axis)
                y_val = midpoint.dot(local_y_axis)
                if x_val < min_x:
                    min_x = x_val
                if x_val > max_x:
                    max_x = x_val
                if y_val < min_y:
                    min_y = y_val
                if y_val > max_y:
                    max_y = y_val

            distance_x = max_x - min_x
            distance_y = max_y - min_y

            if distance_x > distance_y:
                size = distance_x
                # autoscale
                if not self.options.is_repeat:
                    ratio = distance_y / distance_x
                    self.scale.y = ratio
                    self.scale.z = ratio
            else:
                size = distance_y
                if not self.options.is_repeat:
                    ratio = distance_x / distance_y
                    self.scale.x = ratio
                    self.scale.z = ratio

        loc_vector = Matrix.Translation(mesh_center) @ align_matrix @ self.location
        rot_matrix = (
            align_matrix
            @ Matrix.Rotation(self.rotation.x, 4, Vector((mesh_normal.x, 0, 0)))
            @ Matrix.Rotation(self.rotation.y, 4, Vector((0, mesh_normal.y, 0)))
            @ Matrix.Rotation(self.rotation.z, 4, Vector((0, 0, mesh_normal.z)))
        )
        data = {"location": loc_vector, "rotation": rot_matrix.to_euler()}

        # go into obj mode so new mesh is separated
        bpy.ops.object.mode_set(mode="OBJECT")
        if self.idx == 0:
            bpy.ops.mesh.primitive_plane_add(size=size, **data)
        elif self.idx == 1:
            bpy.ops.mesh.primitive_cube_add(size=size, **data)
        elif self.idx == 2:
            bpy.ops.mesh.primitive_circle_add(radius=size / 2, **data)
        elif self.idx == 3:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=size / 2, **data)
        elif self.idx == 4:
            bpy.ops.mesh.primitive_ico_sphere_add(radius=size / 2, **data)
        elif self.idx == 5:
            bpy.ops.mesh.primitive_cylinder_add(radius=size / 2, depth=size / 2, **data)
        elif self.idx == 6:
            bpy.ops.mesh.primitive_cone_add(radius1=size / 2, depth=size / 2, **data)
        elif self.idx == 7:
            bpy.ops.mesh.primitive_torus_add(
                major_radius=size / 2, minor_radius=size / 4, **data
            )

        # scale param sometimes doesn't work, so set it here
        added_obj = bpy.context.active_object
        added_obj.scale = self.scale

        for m in meshes:
            m["obj"].select_set(True)
            # reverse apply transform
            m["obj"].data.transform(m["transform"].inverted())
            m["obj"].matrix_basis = m["transform"]
            m["bm"].free()

        bpy.ops.object.mode_set(mode="EDIT")

        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        row = layout.row()

        col = row.column()
        col.label(text="Location")
        col.prop(self, "location", text="")

        col = row.column()
        col.label(text="Rotation")
        col.prop(self, "rotation", text="")

        col = row.column()
        col.label(text="Scale")
        col.prop(self, "scale", text="")

        row = layout.row()
        row.scale_y = 1.25
        row.operator("wm.operator_defaults", text="Reset All")
