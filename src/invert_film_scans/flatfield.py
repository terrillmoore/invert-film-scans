##############################################################################
#
# Name: flatfield.py
#
# Function:
#       FlatField class: smooth fit to a capture of blank (unexposed,
#       processed) film, used to correct illumination falloff and to
#       normalize each frame to its base
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

import numpy as np
from scipy.ndimage import binary_erosion


class FlatField:
    """A smooth model of a blank-frame capture.

    The model is a 2-D polynomial in the log of each channel, in
    coordinates normalized to [-1, 1] across the image, so it can be
    evaluated at any resolution. Dividing a negative's capture by the
    model gives its transmittance relative to the film base, with the
    illumination falloff removed.

    Areas that aren't film are left out of the fit: the holder's gate
    (dark), sprocket holes (clipped), and a margin around both.
    """

    class Error(Exception):
        """Raised when a blank frame can't be fitted."""

    DEGREE = 6
    TARGET_GRID = 256  # fit on a grid about this many cells wide
    CLIP_LEVEL = 0.98  # fraction of white level treated as clipped
    DARK_FRACTION = 0.5  # cells below this fraction of the film level are gate
    MIN_VALID_FRACTION = 0.05

    def __init__(
        self,
        coefficients: np.ndarray,
        valid: np.ndarray,
    ) -> None:
        """Create from fitted coefficients (3 x nterms) and the fit mask."""
        self.coefficients = coefficients
        self.valid = valid

    # ------------------------------------------------------------------
    # polynomial helpers
    # ------------------------------------------------------------------
    @classmethod
    def _exponents(cls) -> list[tuple[int, int]]:
        return [(i, j) for i in range(cls.DEGREE + 1) for j in range(cls.DEGREE + 1 - i)]

    @classmethod
    def _terms(cls, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.stack([x**i * y**j for i, j in cls._exponents()], -1)

    @staticmethod
    def _coords(n: int, cells: int, step: float) -> np.ndarray:
        # normalized coordinate of the center of each cell
        return ((np.arange(cells) + 0.5) * step) / n * 2 - 1

    # ------------------------------------------------------------------
    # fitting
    # ------------------------------------------------------------------
    @classmethod
    def fit(cls, blank: np.ndarray) -> FlatField:
        """Fit a blank-frame capture (H x W x 3, linear, 1.0 = white level)."""
        h, w, _ = blank.shape
        step = max(1, math.ceil(w / cls.TARGET_GRID))
        hb, wb = h // step, w // step
        crop = blank[: hb * step, : wb * step].astype(np.float64)
        cells = crop.reshape(hb, step, wb, step, 3)
        mean = cells.mean((1, 3))
        clipped = (cells >= cls.CLIP_LEVEL).any((1, 3, 4))

        level = np.percentile(mean[..., 1], 90)
        if level <= 0.01:
            raise cls.Error("blank frame is too dark to fit (no film area found)")
        dark = (mean < cls.DARK_FRACTION * np.percentile(mean, 90, axis=(0, 1))).any(-1)
        valid = binary_erosion(~(dark | clipped), iterations=1, border_value=1)
        if valid.mean() < cls.MIN_VALID_FRACTION:
            raise cls.Error("blank frame has too little film area to fit")

        ys = cls._coords(h, hb, step)
        xs = cls._coords(w, wb, step)
        gx, gy = np.meshgrid(xs, ys)
        terms = cls._terms(gx[valid], gy[valid])
        coefficients = []
        for c in range(3):
            target = np.log(np.maximum(mean[..., c][valid], 1e-6))
            keep = np.ones(len(target), bool)
            for _ in range(3):
                co, *_ = np.linalg.lstsq(terms[keep], target[keep], rcond=None)
                resid = target - terms @ co
                keep = np.abs(resid) < 4 * max(resid[keep].std(), 1e-6)
            coefficients.append(co)
        return cls(np.array(coefficients), valid)

    # ------------------------------------------------------------------
    # evaluation
    # ------------------------------------------------------------------
    def evaluate(self, shape: tuple[int, int]) -> np.ndarray:
        """Return the model at each pixel of an image of the given shape.

        The polynomial is separable into powers of x and of y, so we
        evaluate it as a small matrix product instead of term by term.
        """
        h, w = shape
        x = self._coords(w, w, 1.0)
        y = self._coords(h, h, 1.0)
        n = self.DEGREE + 1
        xp = np.stack([x**i for i in range(n)], -1)  # (w, n)
        yp = np.stack([y**j for j in range(n)], -1)  # (h, n)
        out = np.empty((h, w, 3), np.float32)
        for c in range(3):
            cmat = np.zeros((n, n))
            for (i, j), v in zip(self._exponents(), self.coefficients[c], strict=True):
                cmat[i, j] = v
            out[..., c] = np.exp(yp @ cmat.T @ xp.T)
        return out

    def _valid_surface(self) -> np.ndarray:
        hb, wb = self.valid.shape
        return self.evaluate((hb, wb))[self.valid]

    def peak_level(self) -> np.ndarray:
        """Brightest fitted value per channel, over the film area."""
        return self._valid_surface().max(0)

    def falloff_stops(self) -> np.ndarray:
        """Brightest to darkest fitted value over the film area, in stops."""
        s = self._valid_surface()
        return np.log2(s.max(0) / s.min(0))
