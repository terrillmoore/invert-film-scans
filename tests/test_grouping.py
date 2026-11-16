##############################################################################
#
# Name: test_grouping.py
#
# Function:
#       Tests for FrameGrouper (grouping repeated captures by time) and
#       FrameStack (checking and averaging them)
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import datetime as dt
import pathlib

import numpy as np
import pytest
from scipy.ndimage import fourier_shift

from invert_film_scans.grouping import FrameGrouper
from invert_film_scans.stack import FrameStack

T0 = dt.datetime(2026, 11, 16, 11, 5, 16, 240000)


def _t(seconds: float) -> dt.datetime:
    return T0 + dt.timedelta(seconds=seconds)


def _p(name: str) -> pathlib.Path:
    return pathlib.Path(name)


class TestFrameGrouper:
    def test_groups_by_gap(self):
        items = [
            (_p("a"), _t(0)),
            (_p("b"), _t(1.4)),
            (_p("c"), _t(2.8)),
            (_p("d"), _t(30)),
            (_p("e"), _t(31.2)),
        ]
        groups = FrameGrouper(3.0).group(items)
        assert groups == [[_p("a"), _p("b"), _p("c")], [_p("d"), _p("e")]]

    def test_gap_is_from_previous_frame(self):
        # a long burst stays one group as long as each step is short
        items = [(_p(f"f{i}"), _t(2.0 * i)) for i in range(6)]
        assert FrameGrouper(3.0).group(items) == [[_p(f"f{i}") for i in range(6)]]

    def test_sorts_by_time(self):
        items = [(_p("b"), _t(1)), (_p("a"), _t(0)), (_p("c"), _t(20))]
        assert FrameGrouper(3.0).group(items) == [[_p("a"), _p("b")], [_p("c")]]

    def test_zero_gap_disables_grouping(self):
        items = [(_p("a"), _t(0)), (_p("b"), _t(0.5))]
        assert FrameGrouper(0).group(items) == [[_p("a")], [_p("b")]]

    def test_missing_time_stands_alone(self):
        items = [(_p("a"), _t(0)), (_p("x"), None), (_p("b"), _t(1))]
        groups = FrameGrouper(3.0).group(items)
        assert [_p("x")] in groups
        assert [_p("a"), _p("b")] in groups

    def test_rejects_negative_gap(self):
        with pytest.raises(FrameGrouper.Error):
            FrameGrouper(-1)


def _noisy(img: np.ndarray, seed: int, noise: float = 0.01) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(img * (1 + noise * rng.standard_normal(img.shape)), 0, 1).astype(np.float32)


def _shifted(img: np.ndarray, dy: float, dx: float) -> np.ndarray:
    out = np.empty_like(img)
    for c in range(3):
        f = fourier_shift(np.fft.fft2(img[..., c]), (dy, dx))
        out[..., c] = np.fft.ifft2(f).real
    return np.clip(out, 0, 1)


class TestFrameStack:
    def test_measures_subpixel_shift(self, synthetic):
        a = synthetic.negative
        dy, dx, _ = FrameStack.measure_shift(a, _shifted(a, 0.3, -0.2))
        assert dy == pytest.approx(0.3, abs=0.07)
        assert dx == pytest.approx(-0.2, abs=0.07)

    def test_averages_matching_frames(self, synthetic):
        frames = [_noisy(synthetic.negative, s) for s in range(4)]
        stack = FrameStack(frames[0])
        for f in frames[1:]:
            assert stack.add(f)
        assert stack.count == 4
        mean = stack.mean()
        # noise falls by about half
        err1 = np.std(frames[0] - synthetic.negative)
        err4 = np.std(mean - synthetic.negative)
        assert err4 < 0.6 * err1

    def test_refuses_moved_frame(self, synthetic):
        a = _noisy(synthetic.negative, 1)
        stack = FrameStack(a)
        assert not stack.add(_shifted(_noisy(synthetic.negative, 2), 2.0, 0.0))
        assert stack.count == 1
        assert "moved" in stack.last_reason

    def test_refuses_different_picture(self, synthetic):
        stack = FrameStack(synthetic.negative)
        other = synthetic.negative[::-1, ::-1].copy()
        assert not stack.add(other)
        assert stack.count == 1
        assert "match" in stack.last_reason

    def test_refuses_different_size(self, synthetic):
        stack = FrameStack(synthetic.negative)
        assert not stack.add(synthetic.negative[:-2])
        assert "size" in stack.last_reason
