##############################################################################
#
# Name: inverter.py
#
# Function:
#       Inverter class: turns a flat-fielded negative into a positive by
#       rescaling each channel's density between black and white points
#       read from the same pixels
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import binary_erosion


@dataclass
class Inversion:
    """Result of inverting one negative."""

    positive: np.ndarray  # H x W x 3 float32, 0..1, gamma-encoded output values
    black: np.ndarray  # density above base mapped to black, per channel
    white: np.ndarray  # density above base mapped to white, per channel
    base_ratio: np.ndarray | None  # rebate level / blank-frame level, per channel
    base_spread_stops: float | None  # unevenness of the rebate after flat-fielding


class Inverter:
    """Invert a negative in the density domain.

    The negative's capture is divided by the blank-frame model, giving
    transmittance relative to the base; its negative log is density
    above base. Each channel's density is then rescaled so that the
    picture's darkest areas become 0 and its lightest become 1; the
    result is written as gamma-encoded values. This matches what
    grain2pixel and similar tools do.

    The black and white points are read from the same pixels in all
    three channels: the lightest and darkest areas by mean density.
    Choosing each channel's own percentiles instead picks different
    objects in different channels and gives a color cast.

    The rebate, the gate and clipped sprocket holes are left out of
    the endpoint search, along with a margin around them.
    """

    class Error(Exception):
        """Raised for invalid settings."""

    ENDPOINT_GRID = 1024  # bin to about this many cells wide for endpoints
    BASE_DENSITY = 0.013  # mean density below this is treated as clear base
    GATE_DENSITY = 2.0  # mean density above this is treated as the gate
    CLIP_LEVEL = 0.98
    BASE_CANDIDATE = 0.92  # transmittance above this may be rebate
    TILES = 8

    def __init__(self, black_percentile: float = 0.3, white_percentile: float = 99.7) -> None:
        if not 0 <= black_percentile < white_percentile <= 100:
            raise self.Error(
                f"need 0 <= black percentile ({black_percentile}) < "
                f"white percentile ({white_percentile}) <= 100"
            )
        self.black_percentile = black_percentile
        self.white_percentile = white_percentile

    # ------------------------------------------------------------------
    def invert(self, negative: np.ndarray, flat: np.ndarray) -> Inversion:
        """Invert a negative capture, given the blank-frame model.

        Both are H x W x 3 linear camera RGB, 1.0 = white level.
        """
        clipped = (negative >= self.CLIP_LEVEL).any(-1)
        density = np.divide(negative, flat, dtype=np.float32)
        base_ratio, spread = self._base_match(density, clipped)
        np.clip(density, 1e-4, None, out=density)
        np.log10(density, out=density)
        np.negative(density, out=density)

        black, white = self._endpoints(density, clipped)

        positive = density  # reuse the buffer
        positive -= black.astype(np.float32)
        positive /= (white - black).astype(np.float32)
        np.clip(positive, 0.0, 1.0, out=positive)
        return Inversion(positive, black, white, base_ratio, spread)

    # ------------------------------------------------------------------
    def _endpoints(
        self, density: np.ndarray, clipped: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        h, w, _ = density.shape
        step = max(1, math.ceil(w / self.ENDPOINT_GRID))
        hb, wb = h // step, w // step
        cells = density[: hb * step, : wb * step].reshape(hb, step, wb, step, 3).mean((1, 3))
        clip_cells = clipped[: hb * step, : wb * step].reshape(hb, step, wb, step).any((1, 3))
        mean = cells.mean(-1)
        picture = (mean > self.BASE_DENSITY) & (mean < self.GATE_DENSITY) & ~clip_cells
        margin = max(2, round(0.004 * wb))
        picture = binary_erosion(picture, iterations=margin, border_value=0)
        if picture.sum() < 100:
            raise self.Error("no picture area found in the negative")
        values = cells[picture]
        lum = values.mean(-1)
        lo, hi = np.percentile(lum, [self.black_percentile, self.white_percentile])
        black = np.median(values[lum <= lo], 0)
        white = np.median(values[lum >= hi], 0)
        if (white - black <= 0.01).any():
            raise self.Error("the negative has almost no density range")
        return black.astype(np.float64), white.astype(np.float64)

    # ------------------------------------------------------------------
    def _base_match(
        self, transmittance: np.ndarray, clipped: np.ndarray
    ) -> tuple[np.ndarray | None, float | None]:
        """Compare clear base (rebate) in the negative with the blank model.

        In each tile, take the brightest unclipped pixels as base. If the
        blank frame matches this frame's setup, every tile reads about the
        same; a spread means the blank's falloff doesn't fit this frame.
        """
        h, w, _ = transmittance.shape
        th, tw = h // self.TILES, w // self.TILES
        need = max(20, int(0.01 * th * tw))
        tile_values = []
        for ty in range(self.TILES):
            for tx in range(self.TILES):
                sl = (slice(ty * th, (ty + 1) * th), slice(tx * tw, (tx + 1) * tw))
                t = transmittance[sl]
                ok = ~clipped[sl] & (t.min(-1) > self.BASE_CANDIDATE)
                if ok.sum() < need:
                    continue
                v = t[ok]
                g = v[:, 1]
                top = g >= np.percentile(g, 50)
                tile_values.append(np.median(v[top], 0))
        if not tile_values:
            return None, None
        tv = np.array(tile_values)
        spread = float(np.log2(tv[:, 1].max() / tv[:, 1].min()))
        return np.median(tv, 0), spread
