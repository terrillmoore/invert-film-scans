##############################################################################
#
# Name: conftest.py
#
# Function:
#       Pytest fixtures: synthetic blank frames and negatives
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest


@dataclass
class Synthetic:
    """Synthetic captures, normalized to the sensor's white level (1.0)."""

    falloff: np.ndarray  # true illumination falloff, per channel, 1.0 at center
    base: np.ndarray  # transmittance-weighted level of clear base, per channel
    gate: np.ndarray  # True where the holder's gate blocks the light
    holes: np.ndarray  # True at sprocket holes
    blank: np.ndarray  # capture of blank (unexposed, processed) film
    scene: np.ndarray  # scene luminance pattern, 0..1, used for the negative
    negative: np.ndarray  # capture of an exposed frame
    contrast: np.ndarray  # density per unit log exposure, per channel


class SyntheticFactory:
    """Build synthetic captures that behave like the real setup."""

    H = 240
    W = 320

    def __init__(self, seed: int = 1) -> None:
        self.rng = np.random.default_rng(seed)

    def build(self, *, noise: float = 0.002) -> Synthetic:
        h, w = self.H, self.W
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
        # falloff centered left of and above the sensor center, slightly
        # different per channel, about 0.57 stop at the far corner
        cx, cy = 0.45 * w, 0.45 * h
        r2 = ((xx - cx) ** 2 + (yy - cy) ** 2) / (0.5 * w) ** 2
        k = np.array([0.20, 0.21, 0.22])
        falloff = np.exp(-r2[..., None] * k)

        base = np.array([0.55, 0.68, 0.30])

        gate = np.zeros((h, w), bool)
        gate[:, :8] = True
        gate[-14:, :] = True
        holes = np.zeros((h, w), bool)
        for x0 in range(20, w - 20, 50):
            holes[2:12, x0 : x0 + 18] = True

        def capture(transmittance: np.ndarray) -> np.ndarray:
            img = transmittance * falloff
            img = img * (1 + noise * self.rng.standard_normal(img.shape))
            img[gate] = 0.002
            img[holes] = 1.0
            return np.clip(img, 0, 1).astype(np.float32)

        blank = capture(np.broadcast_to(base, (h, w, 3)))

        # scene: horizontal ramp of log exposure with a bright and a dark patch
        scene = np.tile(np.linspace(0.0, 1.0, w), (h, 1))
        scene[60:100, 60:120] = 1.0
        scene[140:180, 200:260] = 0.0
        contrast = np.array([0.45, 0.65, 0.85])  # density range per channel
        density = 0.05 + scene[..., None] * contrast  # density above base
        negative = capture(base * 10.0 ** (-density))

        return Synthetic(falloff, base, gate, holes, blank, scene, negative, contrast)


@pytest.fixture
def synthetic() -> Synthetic:
    return SyntheticFactory().build()
