# -*- coding: utf-8 -*-
# Copyright (c) 2013, Vispy Development Team.
# Distributed under the (new) BSD License. See LICENSE.txt for more info.

"""
Object oriented interface to OpenGL.

This module implements classes for most things that are "objetcs" in
OpenGL, such as textures, FBO's, VBO's and shaders. Further, some
convenience classes are implemented (like the collection class?).

Central to each visualization is the ShaderProgram. To enable it, it
should be used as a context manager. Other objects, such as Texture2D
and VertexBuffer should be set as uniforms and attributes of the
ShaderProgram object. 

Example::
    
    # Init
    program = ShaderProgram(...)
    program.attributes.position = VertexBuffer(my_positions_array)
    
    ...
    
    # Paint event handler
    with program:
        program.uniforms.color = 0.0, 1.0, 0.0
        program.draw_arrays(gl.GL_TRIANGLES)


The oogl classes:
    
  * :class:`ShaderProgram`
  * :class:`FragmentShader` and :class:`VertexShader`
  * :class:`VertexBuffer` and :class:`ElementBuffer`
  * :class:`Texture2D`, :class:`Texture3D`, :class:`TextureCubeMap`
  * :class:`FrameBuffer`
  * :class:`RenderBuffer`

"""

from __future__ import print_function, division, absolute_import

from vispy import gl


## Replacement for glPushAttrib (which is deprecated)

ENABLE_QUEUE = {}

def push_enable(enum):
    """ Like glEnable, but keeps track of how often it is called
    and really enables/disables if necessary. Only works as it should
    if the application does not make glEnable/glDisable calls by itself.
    """
    cur = ENABLE_QUEUE.get(enum, 0)
    if cur == 0:
        gl.glEnable(enum)
    ENABLE_QUEUE[enum] = cur + 1
    

def pop_enable(enum):
    """ Like glDisable, but keeps track of how often it is called
    and really enables/disables if necessary. Only works as it should
    if the application does not make glEnable/glDisable calls by itself.
    """
    cur = ENABLE_QUEUE.get(enum, 0)
    if cur == 1:
        gl.glDisable(enum)
    ENABLE_QUEUE[enum] = max(0, cur-1)


##

def ext_available(extension_name):
    return True # for now


class GLObject(object):
    """ Base class for classes that wrap an OpenGL object.
    All GLObject's can be used as a context manager to enable them,
    although some are better used by setting them as a uniform or
    attribute of a ShaderProgram.
    
    All GLObject's apply deferred (a.k.a. lazy) loading, which means
    that the objects can be created and data can be set even if no
    OpenGL context is available yet. 
    
    There are a few exceptions, most notably when enabling an object
    by using it as a context manager or via ShaderProgram.enable_object(), 
    and the delete method. In these cases, the called should ensure
    that the proper OpenGL context is current.
    """
    
    def __enter__(self):
        self._enable()
        return self
    
    def __exit__(self, type, value, traceback):
        self._disable()
    
    def __del__(self):
        self.delete()
    
    def delete(self):
        """ Delete the object from OpenGl memory. Note that the right
        context should be active when this method is called.
        """
        try:
            if self._handle > 0:
                self._delete()
        except Exception:
            pass  # At least we tried
        self._handle = 0
    
    @property
    def handle(self):
        """  The handle (i.e. id or name) of the underlying OpenGL object.
        """
        return self._handle
    
    
    def _enable(self):
        raise NotImplementedError()
    
    def _disable(self):
        raise NotImplementedError()
    
    def _delete(self):
        raise NotImplementedError()



from .vbo import VertexBuffer, ElementBuffer
from .texture import Texture, Texture2D, Texture3D, TextureCubeMap
from .shader import VertexShader, FragmentShader
from .fbo import FrameBuffer, RenderBuffer
from .program import ShaderProgram
