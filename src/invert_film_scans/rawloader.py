##############################################################################
#
# Name: rawloader.py
#
# Function:
#       RawLoader class: decodes camera raw files to linear camera RGB
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import pathlib

import numpy as np
import rawpy


class RawLoader:
    """Decode a raw file to linear camera RGB.

    Densities must come from the sensor's own channels: a camera-to-
    standard color matrix mixes the channels before the log, which
    distorts hues after inversion. So we ask LibRaw for raw color, no
    white balance, no tone curve and no brightening. The result is
    scaled so that 1.0 is the sensor's white level (after black-level
    subtraction).
    """

    class Error(Exception):
        """Raised when a raw file can't be read."""

    def load(self, path: pathlib.Path) -> np.ndarray:
        """Return an H x W x 3 float32 image, 1.0 = white level."""
        path = pathlib.Path(path)
        if not path.is_file():
            raise self.Error(f"{path}: file not found")
        try:
            with rawpy.imread(str(path)) as raw:
                rgb = raw.postprocess(
                    gamma=(1, 1),
                    no_auto_bright=True,
                    bright=1.0,
                    output_bps=16,
                    user_wb=[1, 1, 1, 1],
                    output_color=rawpy.ColorSpace.raw,
                    highlight_mode=rawpy.HighlightMode.Clip,
                    user_flip=0,
                )
        except (rawpy.LibRawError, OSError) as e:
            raise self.Error(f"{path}: can't decode raw file: {e}") from e
        out = rgb.astype(np.float32)
        out /= 65535.0
        return out
