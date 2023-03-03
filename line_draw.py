import bpy
import gpu
from gpu_extras.batch import batch_for_shader


SHADER = gpu.shader.from_builtin("2D_UNIFORM_COLOR")
handles = []


def add(coords, colour):
    def draw():
        SHADER.uniform_float("color", colour)
        batch_for_shader(SHADER, "LINES", {"pos": coords}).draw(SHADER)

    handles.append(
        bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_PIXEL")
    )


def remove():
    for handle in handles:
        bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
    handles.clear()
