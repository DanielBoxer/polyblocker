# Copyright (C) 2023 Daniel Boxer

import bpy
import gpu
from gpu_extras.batch import batch_for_shader

SHADER_2D_NAME = "UNIFORM_COLOR" if bpy.app.version >= (4, 0, 0) else "2D_UNIFORM_COLOR"
SHADER_3D_NAME = "UNIFORM_COLOR" if bpy.app.version >= (4, 0, 0) else "3D_UNIFORM_COLOR"
SHADER_2D = gpu.shader.from_builtin(SHADER_2D_NAME)
SHADER_3D = gpu.shader.from_builtin(SHADER_3D_NAME)
COLOURS = {"X": (1, 0, 0, 1), "Y": (0, 1, 0, 1), "Z": (0, 0, 1, 1)}
handles = {}
batches = {}


def make_batch(shader, coords):
    return batch_for_shader(shader, "LINES", {"pos": coords})


def add_handle(name, callback, type):
    handles[name] = bpy.types.SpaceView3D.draw_handler_add(callback, (), "WINDOW", type)


def change_colour(shader, colour):
    shader.uniform_float("color", colour)


def draw_guide(coords, colour):
    def draw():
        change_colour(SHADER_2D, colour)
        make_batch(SHADER_2D, coords).draw(SHADER_2D)

    remove("guide")
    add_handle("guide", draw, "POST_PIXEL")


def draw_axis(name, colour, coords=()):
    def draw():
        change_colour(SHADER_3D, colour)
        # just change colour if no coords
        if coords:
            batches[name] = make_batch(SHADER_3D, coords)
        batches[name].draw(SHADER_3D)

    if not coords:
        remove(name)
    add_handle(name, draw, "POST_VIEW")


def remove(name):
    if name in handles:
        bpy.types.SpaceView3D.draw_handler_remove(handles[name], "WINDOW")
        del handles[name]
