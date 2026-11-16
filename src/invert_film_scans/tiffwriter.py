##############################################################################
#
# Name: tiffwriter.py
#
# Function:
#       TiffWriter class: writes 16-bit RGB TIFFs with an embedded profile
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
import tifffile


class TiffWriter:
    """Write 16-bit RGB TIFFs (deflate compressed) with an ICC profile."""

    ICC_TAG = 34675

    def __init__(self, icc_profile: bytes) -> None:
        self.icc_profile = icc_profile

    def write(self, path: pathlib.Path, image: np.ndarray) -> None:
        """Write an H x W x 3 image with values 0..1 (clipped)."""
        data = np.clip(image, 0.0, 1.0)
        data = (data * 65535.0 + 0.5).astype(np.uint16)
        tifffile.imwrite(
            pathlib.Path(path),
            data,
            photometric="rgb",
            compression="zlib",
            predictor=True,
            extratags=[(self.ICC_TAG, "B", len(self.icc_profile), self.icc_profile, True)],
        )
