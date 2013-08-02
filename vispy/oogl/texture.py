# -*- coding: utf-8 -*-
# Copyright (c) 2013, Vispy Development Team.
# Distributed under the (new) BSD License. See LICENSE.txt for more info.

""" Definition of Texture class.

This code is inspired by similar classes from Visvis and Pygly.

"""

# todo: implement ext_available
# todo: make a Texture1D that makes a nicer interface to a 2D texture
# todo: same for Texture3D?
# todo: Cubemap texture


from __future__ import print_function, division, absolute_import

import sys
import numpy as np

from vispy import gl
from . import GLObject, push_enable, pop_enable, ext_available

if sys.version_info > (3,):
    basestring = str


# Dict that maps numpy datatypes to openGL ES 2.0 data types
DTYPES = {  'uint8': gl.GL_UNSIGNED_BYTE,
            'float16': gl.ext.GL_HALF_FLOAT, # Needs GL_OES_texture_half_float
            'float32': gl.GL_FLOAT,  # Needs GL_OES_texture_float
        }


class _RawTexture(GLObject):
    """ This class demonstrates the minimal encapsulation of an OpenGl
    texture. The rest is mostly sugar and stuff to support deferred
    loading and settings.
    """
    
    def __init__(self, target):
        
        # Store target (i.e. the texture type)
        if target not in [gl.GL_TEXTURE_2D, gl.ext.GL_TEXTURE_3D]:
            raise ValueError('Unsupported target "%r"' % target)
        self._target = target
        
        # Texture ID (by which OpenGl identifies the texture)
        # 0 means uninitialized, <0 means error.
        self._handle = 0
        
        # To store the used texture unit so we can disable it properly.
        self._unit = -1
    
    
    def _create(self):
        self._handle = gl.glGenTextures(1)
    
    def _delete(self):
        gl.glDeleteTextures([self._handle])
    
    
    def _enable(self):
        """ To be called by context handler. Never call this yourself.
        """
        # Enable things that we need
        push_enable(self._target)
        # Set active texture unit
        if self._unit >= 0:
            gl.glActiveTexture(gl.GL_TEXTURE0 + self._unit)
        # Bind
        gl.glBindTexture(self._target, self._handle)
    
    
    def _disable(self):
        """ To be called by context handler. Never call this yourself.
        """
        # Select active texture if we can
        if self._unit >= 0:
            gl.glActiveTexture(gl.GL_TEXTURE0 + self._unit)
            self._unit = -1
        # Unbind and disable
        gl.glBindTexture(self._target, 0)
        # Set active texture unit to default (0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        # No need for texturing anymore
        pop_enable(self._target)
    
    
    def _allocate(self, shape, format, level=0):
        """ Allocate space for the current texture object. 
        It should have been verified that the texture will fit.
        """
        # Determine function and target from texType
        D = {   #gl.GL_TEXTURE_1D: (gl.glTexImage1D, 1),
                gl.GL_TEXTURE_2D: (gl.glTexImage2D, 2),
                gl.ext.GL_TEXTURE_3D: (gl.ext.glTexImage3D, 3)}
        uploadFun, ndim = D[self._target]
        
        # Determine type
        gltype = gl.GL_UNSIGNED_BYTE
        
        # Build args list
        size = size = [i for i in reversed( shape[:ndim] )]
        args = [self._target, level, format] + size + [0, format, gltype, None]
        
        # Call
        uploadFun(*tuple(args))
    
    
    def _upload(self, data, format, level=0):
        """ Upload a texture to the current texture object. 
        It should have been verified that the texture will fit.
        """
        # Determine function and target from texType
        D = {   #gl.GL_TEXTURE_1D: (gl.glTexImage1D, 1),
                gl.GL_TEXTURE_2D: (gl.glTexImage2D, 2),
                gl.ext.GL_TEXTURE_3D: (gl.ext.glTexImage3D, 3)}
        uploadFun, ndim = D[self._target]
        
        # Determine type
        thetype = data.dtype.name
        if not thetype in DTYPES: # Note that we convert if necessary in Texture
            raise ValueError("Cannot translate datatype %s to GL." % thetype)
        gltype = DTYPES[thetype]
        
        # Build args list
        size, gltype = self._get_size_and_type(data, ndim)
        args = [self._target, level, format] + size + [0, format, gltype, data]
        
        # Check the alignment of the texture
        alignment = self._get_alignment(data.shape[-1])
        if alignment != 4:
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, alignment)
        
        # Call
        uploadFun(*tuple(args))
        
        # Check if we need to reset our pixel store state
        if alignment != 4:
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 4)
    
    
    def _update(self, data, offset, format, level=0):
        """ Update an existing texture object.
        """
        # Determine function and target from texType
        D = {   #gl.GL_TEXTURE_1D: (gl.glTexSubImage1D, 1),
                gl.GL_TEXTURE_2D: (gl.glTexSubImage2D, 2),
                gl.ext.GL_TEXTURE_3D: (gl.ext.glTexSubImage3D, 3)}
        uploadFun, ndim = D[self._target]
        
        # Build argument list
        size, gltype = self._get_size_and_type(data, ndim)
        offset = [i for i in offset]
        assert len(offset) == len(size)
        args = [self._target, level] + offset + size + [format, gltype, data]
        
        # Upload!
        uploadFun(*tuple(args))
    
    
    def _get_size_and_type(self, data, ndim):
        # Determine size
        size = [i for i in reversed( data.shape[:ndim] )]
        # Determine type
        thetype = data.dtype.name
        if not thetype in DTYPES: # Note that we convert if necessary in Texture
            raise ValueError("Cannot translate datatype %s to GL." % thetype)
        gltype = DTYPES[thetype]
        # Done
        return size, gltype
    
    # from pylgy
    def _get_alignment(self, width):
        """Determines a textures byte alignment.
    
        If the width isn't a power of 2
        we need to adjust the byte alignment of the image.
        The image height is unimportant
    
        http://www.opengl.org/wiki/Common_Mistakes#Texture_upload_and_pixel_reads
        """
        
        # we know the alignment is appropriate
        # if we can divide the width by the
        # alignment cleanly
        # valid alignments are 1,2,4 and 8
        # put 4 first, since it's the default
        alignments = [4,8,2,1]
        for alignment in alignments:
            if width % alignment == 0:
                return alignment



class Texture(_RawTexture):
    """ Representation of an OpenGL texture. 
    
    """
    # Builds on the raw texture class by implementing convenience and lazy loading
    
    def __init__(self, target, data=None, format=None, clim=None):
        _RawTexture.__init__(self, target)
        
        # A reference (not a weak one) to be able to process deferred
        # (i.e. lazy) loading. Also store the shape.
        self._pending_data = None
        self._texture_shape = None
        
        # The parameters that apply to this texture. One variable to 
        # keep track of pending parameters, the other for resetting
        # parameters if its re-uploaded.
        self._texture_params = {}
        self._pending_params = {}
        
        # Set default parameters for min and mag filter, otherwise an
        # image is not shown by default, since the default min_filter
        # is GL_NEAREST_MIPMAP_LINEAR
        self.set_parameter(gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        self.set_parameter(gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        
        # Set data?
        if data is None:
            pass
        elif isinstance(data, np.ndarray):
            self.set_data(data, format=format, clim=clim)
        elif isinstance(data, tuple):
            self.set_storage(data, format=format)
        else:
            raise ValueError('Invalid value to initialize Texture with.')
    
    
    def __call__(self, unit):
        """ Calling a texture sets the texture unit.
        """
        self._unit = int(unit)
        return self
    
    
    def set_parameter(self, param, value):
        """ Set texture parameter, can be called at any time. The param
        can be an OpenGL constant or a string that corresponds to such
        a constant. OpenGL ES 2.0 allows the following parameters:
        GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_WRAP_S,
        TEXTURE_WRAP_T, GL_TEXTURE_WRAP_R (with extension).
        """
        # Allow strings
        if isinstance(param, basestring):
            param = param.upper()
            if not param.startswith('GL'):
                param = 'GL_TEXTURE_' + param
            param = getattr(gl, param)
        # Set 
        self._pending_params[param] = value
        self._texture_params[param] = value
    
    
    def set_data(self, data, offset=None, level=0, format=None, clim=None):
        """ Set the data for this texture. This method can be called at any
        time (even if there is no context yet).
        
        If the shape of the given data matches the shape of the current
        texture, the data is updated in a fast manner.
        
        Parameters
        ----------
        data : numpy array
            The texture data to set.
        offset : tuple
            The offset for each dimension, to update part of the texture.
        level : int
            The mipmap level. Default 0.
        format : OpenGL enum
            The format representation of the data. If not given or None,
            it is decuced from the given data. Can be GL_RGB, GL_RGBA,
            GL_LUMINANCE, GL_LUMINANCE_ALPHA, GL_ALPHA.
        clim : (min, max)
            Contrast limits for the data. If specified, min will end
            up being 0.0 (black) and max will end up as 1.0 (white).
            If not given or None, clim is determined automatically. For
            floats they become (0.0, 1.0). For integers the are mapped to
            the full range of the type. 
        
        """
        
        # Reset if there was an error earlier
        if self._handle < 0:
            self._handle = 0
            self._texture_shape = None
        
        # Get ndim
        MAP = {gl.GL_TEXTURE_2D:2, gl.ext.GL_TEXTURE_3D:3}
        ndim = MAP.get(self._target, 0)
        
        # Check data
        if not isinstance(data, np.ndarray):
            raise ValueError("Data should be a numpy array.")
        shape = data.shape
        assert isinstance(shape, tuple)
        assert len(shape) in (ndim, ndim+1)
        
        # Check offset
        MAP = {gl.GL_TEXTURE_2D:2, gl.ext.GL_TEXTURE_3D:3}
        ndim = MAP.get(self._target, 0)
        if offset is not None:
            offset = [int(i) for i in offset]
            assert len(offset) == len(data.shape[:ndim])
        elif data.shape == self._texture_shape and self._handle > 0:
            # If data is of same shape as current texture, update is much faster
            offset = [0 for i in self._texture_shape[:ndim]]
        
        # Check level, format, clim
        assert isinstance(level, int) and level >= 0
        assert format in (None, gl.GL_RGB, gl.GL_RGBA, gl.GL_LUMINANCE, 
                            gl.GL_LUMINANCE_ALPHA, gl.GL_ALPHA)
        assert clim is None or (isinstance(clim, tuple) and len(clim)==2)
        
        # Set pending data ...
        self._pending_data = data, offset, level, format, clim
        self._texture_shape = data.shape
    
    
    def set_storage(self, shape, level=0, format=None):
        """ Allocate storage for this texture. This is useful if the texture
        is used as a render target for an FBO. 
        
        A call that only uses the shape argument does not result in an
        action if the call would not change the shape.
        
        Parameters
        ----------
        shape : tuple
            The shape of the "virtual" data. By specifying e.g. (20,20,3) for
            a Texture2D, one implicitly sets the format to GL_RGB. Note
            that shape[0] is height.
        level : int
            The mipmap level. Default 0.
        format : OpenGL enum
            The format representation of the data. If not given or None,
            it is decuced from the given data. Can be GL_RGB, GL_RGBA,
            GL_LUMINANCE, GL_LUMINANCE_ALPHA, GL_ALPHA.
        """
        
        # Reset if there was an error earlier
        if self._handle < 0:
            self._handle = 0
            self._texture_shape = None
        
        # Get ndim
        MAP = {gl.GL_TEXTURE_2D:2, gl.ext.GL_TEXTURE_3D:3}
        ndim = MAP.get(self._target, 0)
        
        # Is this already my shape?
        if format is None and level==0 and self._texture_shape is not None:
            if self._texture_shape[:ndim] == shape[:ndim]:
                return
        
        # Check shape
        assert isinstance(shape, tuple)
        assert len(shape) in (ndim, ndim+1)
        shape = tuple([int(i) for i in shape])
        assert all([i>0 for i in shape])
        
        # Check level, format, clim
        assert isinstance(level, int) and level >= 0
        assert format in (None, gl.GL_RGB, gl.GL_RGBA, gl.GL_LUMINANCE, 
                            gl.GL_LUMINANCE_ALPHA, gl.GL_ALPHA)
        
        # Set pending data ...
        self._pending_data = None, None, level, format, None
        self._texture_shape = shape
    
    
    def _enable(self):
        """ Overloaded _enable method to handle deferred uploading and
        preparing the texture. Does nothing is texture is invalid
        (self._handle < 0).
          * Upload pending data
          * Bind the texture.
        """
        # Error last time
        if self._handle < 0:
            return
        
        # If we use a 3D texture, we need an extension
        if self._target == gl.ext.GL_TEXTURE_3D:
            if not ext_available('GL_texture_3D'):
                self._handle = -1
                return
        
        # Need to update data?
        if self._pending_data:
            pendingData, self._pending_data = self._pending_data, None
            # Process pending data
            self._process_pending_data(*pendingData)
            # If not ok, warn (one time)
            if not gl.glIsTexture(self._handle):
                self._handle = -1
                print('Warning enabling texture, the texture is not valid.')
                return
        
        # Is the texture valid? It may simply not have been given data yet
        if self._handle == 0:
            return
        if not gl.glIsTexture(self._handle): 
            raise RuntimeError('This should not happen (texture is invalid)')
        
        # Enable
        _RawTexture._enable(self)
        
        # Need to update any parameters?
        while self._pending_params:
            param, value = self._pending_params.popitem()
            gl.glTexParameter(self._target, param, value)
    
    
    def _process_pending_data(self, data, offset, level, format, clim):
        """ Process the pending data. Uploading the data (i.e. create
        a new texture) or updating it (a subsection).
        """
        
        # Convert data type to one supported by OpenGL
        if data is not None:
            data = convert_data(data, clim)
        
        # Get shape
        if data is not None:
            shape = data.shape
        else:
            shape = self._texture_shape
        
        # Determine format (== internalformat) 
        if format is None:
            format = get_format(shape, self._target)
        
        if offset:
            # Update: fast!
            gl.glBindTexture(self._target, self._handle)
            if self._handle <= 0 or not gl.glIsTexture(self._handle):
                raise ValueError('Cannot update texture if there is no texture.')
            self._update(data, offset, format, level)
            
        else:
            # (re)upload: slower
            # We delete the existing texture first. In theory this
            # should not be necessary, but some implementations cause
            # memory leaks otherwise.
            self.delete() 
            self._create()
            gl.glBindTexture(self._target, self._handle)
            # Upload!
            if data is None:
                self._allocate(shape, format, level)
            else:
                self._upload(data, format, level)
            # Set all parameters that the user set
            for param, value in self._texture_params.items():
               gl.glTexParameter(self._target, param, value)
            self._pending_params = {} # We just applied all 
            # If all is well, the _handle, should now be a valid texture



class Texture2D(Texture):
    """ Representation of a 2D texture. Inherits Texture.
    """
    def __init__(self, *args, **kwargs):
        Texture.__init__(self, gl.GL_TEXTURE_2D, *args, **kwargs)



class Texture3D(Texture):
    """ Representation of a 3D texture. Note that for this the
    GL_texture_3D extension needs to be available. Inherits Texture.
    """
    def __init__(self, *args, **kwargs):
        Texture.__init__(self, gl.ext.GL_TEXTURE_3D, *args, **kwargs)



class TextureCubeMap(Texture):
    """ Representation of a cube map, to store texture data for the
    6 sided of a cube. Used for instance to create environment mappings.
    
    This class is not yet implemented.
    """
    # Note that width and height for these textures should be equal
    def __init__(self, *args, **kwargs):
        raise NotImplementedError()
        Texture.__init__(self, gl.GL_TEXTURE_CUBE_MAP, *args, **kwargs)



## Utility functions


def get_format(shape, target):
    """ Get format, based on the target and the shape. If the shape
    does not match with the texture type, an exception is raised.
    The only format that cannot be deduced from the shape is GL_ALPHA
    """
    
    if target == gl.GL_TEXTURE_2D:
        if len(shape)==2:
            format = gl.GL_LUMINANCE              
        elif len(shape)==3 and shape[2]==1:
            format = gl.GL_LUMINANCE
        elif len(shape)==3 and shape[2]==2:
            format = gl.GL_LUMINANCE_ALPHA
        elif len(shape)==3 and shape[2]==3:
            format = gl.GL_RGB
        elif len(shape)==3 and shape[2]==4:
            format = gl.GL_RGBA
        else:
            raise ValueError("Cannot determine format: data of invalid shape.")
    
    elif target == gl.ext.GL_TEXTURE_3D:
        if len(shape)==3:
            format = gl.GL_LUMINANCE
        elif len(shape)==4 and shape[3]==1:
            format = gl.GL_LUMINANCE
        elif len(shape)==4 and shape[3]==2:
            format = gl.GL_LUMINANCE_ALPHA
        elif len(shape)==4 and shape[3]==3:
            format = gl.GL_RGB
        elif len(shape)==4 and shape[3]==4:
            format = gl.GL_RGBA
        else:
            raise ValueError("Cannot determine format: data of invalid shape.")
    
    else:
        raise ValueError("Cannot determine format with these dimensions.")
    
    return format


def convert_data(data, clim=None):
    """ Convert data to a type that OpenGL can deal with.
    Also applies contrast limits if given.
    """
    
    # Prepare
    FLOAT32_SUPPORT = ext_available('texture_float')
    FLOAT16_SUPPORT = ext_available('texture_half_float')
    CONVERTING = False
    
    # Determine clim if not given, copy or make float32 if necessary.
    # Copies may be necessary because following operations are in-place.
    if data.dtype.name == 'bool':
        # Bools are ... unsigned ints
        data = data.astype(np.uint8)
        clim = None
    elif data.dtype.name == 'uint8':
        # Uint8 is what we need! If clim is None, no action required
        if clim is not None:
            data = data.astype(np.float32)
    elif data.dtype.name == 'float16':
        # Float16 may be allowed. If clim is None, no action is required
        if clim is not None:
            data = data.copy()
        elif not FLOAT16_SUPPORT:
            CONVERTING = True
            data = data.copy()
    elif data.dtype.name == 'float32':
        # Float32 may be allowed. If clim is None, no action is required
        if clim is not None:
            data = data.copy()
        elif not FLOAT32_SUPPORT:
            CONVERTING = True
            data = data.copy()
    elif 'float' in data.dtype.name:
        # All other floats are converted with relative ease
        CONVERTING = True
        data = data.astype(np.float32)
    elif data.dtype.name.startswith('int'):
        # Integers, we need to parse the dtype
        CONVERTING = True
        if clim is None:
            max = 2**int(data.dtype.name[3:])
            clim = -max//2, max//2-1
        data = data.astype(np.float32)
    elif data.dtype.name.startswith('uint'):
        # Unsigned integers, we need to parse the dtype
        CONVERTING = True
        if clim is None:
            max = 2**int(data.dtype.name[4:])
            clim = 0, max//2
        data = data.astype(np.float32)
    else:
        raise RuntimeError('Could not convert data type %s.' % data.dtype.name)
    
    # Apply limits if necessary
    if clim is not None:
        assert isinstance(clim, tuple)
        assert len(clim) == 2
        if clim[0] != 0.0:
            data -= clim[0]
        if clim[1]-clim[0] != 1.0:
            data *= 1.0 / (clim[1]-clim[0])
    
    #if CONVERTING:
    #    print('Warning, converting data.')
    
    # Convert if necessary
    if data.dtype == np.uint8:
        pass  # Always possible
    elif data.dtype == np.float16 and FLOAT16_SUPPORT:
        pass  # Yeah
    elif data.dtype == np.float32 and FLOAT32_SUPPORT:
        pass  # Yeah
    elif data.dtype in (np.float16, np.float32):
        # Arg, convert. Don't forget to clip
        data *= 256.0
        data[data<0.0] = 0.0
        data[data>256.0] = 256.0
        data = data.astype(np.uint8)
    else:
        raise RuntimeError('Error converting data type. This should not happen.')
    
    # Done
    return data
