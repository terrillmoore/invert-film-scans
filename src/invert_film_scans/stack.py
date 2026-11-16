##############################################################################
#
# Name: stack.py
#
# Function:
#       FrameStack class: checks that repeated captures line up, and
#       averages them
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import numpy as np


class FrameStack:
    """Average repeated captures of one negative.

    Averaging N captures cuts sensor noise by the square root of N, but
    only if the film didn't move between them: a shift blurs the average.
    So each frame is compared with the first before it is added. Frames
    that moved more than MAX_SHIFT pixels, or that don't match at all
    (the film was advanced, or it is a different picture), are refused,
    and the caller starts a new stack with them.
    """

    MAX_SHIFT = 0.5  # pixels
    MIN_MATCH = 0.9  # correlation after alignment below this: not the same picture
    REGION = 1024  # compare a central square at most this size

    def __init__(self, first: np.ndarray) -> None:
        self._sum = first.astype(np.float32)
        self._ref = self._signature(first)
        self.count = 1
        self.shifts: list[tuple[float, float]] = [(0.0, 0.0)]
        self.last_reason = ""

    # ------------------------------------------------------------------
    @classmethod
    def _signature(cls, img: np.ndarray) -> np.ndarray:
        """Log of the green channel in a central square, windowed."""
        h, w = img.shape[:2]
        n = min(h, w, cls.REGION)
        y0, x0 = (h - n) // 2, (w - n) // 2
        g = np.log(np.clip(img[y0 : y0 + n, x0 : x0 + n, 1].astype(np.float64), 1e-4, None))
        g -= g.mean()
        win = np.outer(np.hanning(n), np.hanning(n))
        return g * win

    @staticmethod
    def _upsampled_dft(
        data: np.ndarray, size: int, factor: int, offsets: tuple[float, float]
    ) -> np.ndarray:
        """Inverse DFT of `data` on a fine grid, without padding the array.

        Evaluates a size x size patch at 1/factor pixel spacing, starting
        `offsets` (in fine-grid units) before zero, by matrix
        multiplication (Guizar-Sicairos, Thurman and Fienup, Opt. Lett. 33,
        156, 2008; the same arrangement as scikit-image).
        """
        out = data
        for axis_len, offset in reversed(list(zip(data.shape, offsets, strict=True))):
            kernel = (np.arange(size) - offset)[:, None] * np.fft.fftfreq(axis_len, factor)
            out = np.tensordot(np.exp(-2j * np.pi * kernel), out, axes=(1, -1))
        return out

    @classmethod
    def _shift(cls, ref: np.ndarray, sig: np.ndarray) -> tuple[float, float, float]:
        """Return (dy, dx, coefficient): the shift of sig relative to ref.

        Phase correlation finds the whole-pixel peak; the cross-power,
        upsampled 20 times around it, refines it to about 0.05 pixel.
        The coefficient is the correlation of the two signatures after the
        whole-pixel alignment: near 1 for repeated captures, low for a
        different picture.
        """
        product = np.fft.fft2(ref) * np.conj(np.fft.fft2(sig))
        c = np.fft.ifft2(product / (np.abs(product) + 1e-12)).real
        peak = np.array(np.unravel_index(int(c.argmax()), c.shape), dtype=np.float64)
        dims = np.array(c.shape)
        peak[peak > dims // 2] -= dims[peak > dims // 2]  # shift that registers sig to ref

        rolled = np.roll(sig, tuple(int(v) for v in peak), axis=(0, 1))
        coef = float(np.corrcoef(ref.ravel(), rolled.ravel())[0, 1])

        factor = 20
        size = int(np.ceil(factor * 1.5))
        center = np.trunc(size / 2.0)
        offsets = center - peak * factor
        fine = np.abs(np.conj(cls._upsampled_dft(np.conj(product), size, factor, tuple(offsets))))
        fpeak = np.array(np.unravel_index(int(fine.argmax()), fine.shape), dtype=np.float64)
        register = peak + (fpeak - center) / factor
        return float(-register[0]), float(-register[1]), coef

    @classmethod
    def measure_shift(cls, ref: np.ndarray, img: np.ndarray) -> tuple[float, float, float]:
        """Return (dy, dx, coefficient): how far img is shifted from ref.

        Shift in pixels; the coefficient is near 1 for the same picture.
        """
        return cls._shift(cls._signature(ref), cls._signature(img))

    # ------------------------------------------------------------------
    def add(self, img: np.ndarray) -> bool:
        """Add a frame if it lines up with the first; return whether it did."""
        if img.shape != self._sum.shape:
            self.last_reason = f"size {img.shape} differs from {self._sum.shape}"
            return False
        dy, dx, coef = self._shift(self._ref, self._signature(img))
        if coef < self.MIN_MATCH:
            self.last_reason = f"doesn't match the first frame (correlation {coef:.2f})"
            return False
        if max(abs(dy), abs(dx)) > self.MAX_SHIFT:
            self.last_reason = f"moved {dy:+.1f}, {dx:+.1f} pixels from the first frame"
            return False
        self._sum += img
        self.count += 1
        self.shifts.append((dy, dx))
        self.last_reason = ""
        return True

    def mean(self) -> np.ndarray:
        return self._sum / np.float32(self.count)
