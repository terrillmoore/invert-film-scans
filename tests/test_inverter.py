##############################################################################
#
# Name: test_inverter.py
#
# Function:
#       Tests for the Inverter class (density-domain inversion)
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
import pytest

from invert_film_scans.flatfield import FlatField
from invert_film_scans.inverter import Inverter


@pytest.fixture
def flat(synthetic):
    return FlatField.fit(synthetic.blank).evaluate(synthetic.blank.shape[:2])


def _interior(synthetic, margin: int = 6) -> np.ndarray:
    """Scene pixels well away from the gate, holes and rebate."""
    bad = synthetic.gate | synthetic.holes | synthetic.rebate
    from scipy.ndimage import binary_dilation

    return ~binary_dilation(bad, iterations=margin)


class TestInverter:
    def test_recovers_scene_neutrally(self, synthetic, flat):
        result = Inverter().invert(synthetic.negative, flat)
        inner = _interior(synthetic)
        pos = result.positive[inner]
        scene = synthetic.scene[inner]
        for c in range(3):
            assert np.abs(pos[:, c] - scene).max() < 0.03
        # neutral: the three channels agree
        assert np.abs(pos[:, 0] - pos[:, 2]).max() < 0.03

    def test_endpoints_are_scene_densities(self, synthetic, flat):
        result = Inverter().invert(synthetic.negative, flat)
        assert result.black == pytest.approx([0.05, 0.05, 0.05], abs=0.01)
        assert result.white == pytest.approx(0.05 + synthetic.contrast, abs=0.01)

    def test_rebate_and_gate_do_not_set_endpoints(self, synthetic, flat):
        # the rebate is clear base (density 0) and the gate is nearly
        # opaque; neither is part of the picture
        result = Inverter().invert(synthetic.negative, flat)
        assert (result.black > 0.03).all()
        assert (result.white < 1.5).all()

    def test_soft_edges_do_not_set_endpoints(self, synthetic, flat):
        # An out-of-focus gate and the edge of the exposed frame fade over
        # several pixels. The fade passes through every density between
        # the gate (or clear base) and the picture; none of it is picture.
        # The fade is even in density, as with a real out-of-focus gate
        # (about 1.6% of the frame width on the GX85 captures).
        neg = synthetic.negative.copy()
        ramp = 6
        d_gate = -np.log10(0.002 / flat[:, 8])
        d_in = -np.log10(neg[:, 8 + ramp] / flat[:, 8 + ramp])
        d_reb = -np.log10(neg[23, 8:] / flat[23, 8:])
        d_pic = -np.log10(neg[24 + ramp, 8:] / flat[24 + ramp, 8:])
        for i in range(ramp):
            a = (i + 1) / (ramp + 1)
            # left gate edge: columns just inside the gate fade in
            neg[:, 8 + i] = flat[:, 8 + i] * 10 ** -(d_gate * (1 - a) + d_in * a)
            # bottom of the rebate strip: picture fades to clear base
            neg[24 + i, 8:] = flat[24 + i, 8:] * 10 ** -(d_reb * (1 - a) + d_pic * a)
        result = Inverter().invert(neg, flat)
        assert result.black == pytest.approx([0.05, 0.05, 0.05], abs=0.01)
        assert result.white == pytest.approx(0.05 + synthetic.contrast, abs=0.01)

    def test_deep_shadows_at_base_are_kept(self, synthetic, flat):
        # A picture whose shadows recorded nothing above base: the black
        # point should be base, not something lighter chosen because the
        # shadows were mistaken for rebate.
        neg = synthetic.negative.copy()
        patch = (slice(140, 180), slice(200, 260))
        neg[patch] = synthetic.blank[patch] * 0.999
        result = Inverter().invert(neg, flat)
        assert (result.black < 0.02).all()

    def test_output_range(self, synthetic, flat):
        result = Inverter().invert(synthetic.negative, flat)
        assert result.positive.dtype == np.float32
        assert result.positive.min() >= 0.0
        assert result.positive.max() <= 1.0

    def test_base_match_with_matching_blank(self, synthetic, flat):
        result = Inverter().invert(synthetic.negative, flat)
        assert result.base_ratio == pytest.approx([1, 1, 1], abs=0.02)
        assert result.rebate_variation_stops < 0.03

    def test_base_match_detects_wrong_flat(self, synthetic, flat):
        h, w = flat.shape[:2]
        tilt = np.linspace(0.85, 1.15, w)[None, :, None].astype(np.float32)
        result = Inverter().invert(synthetic.negative, flat * tilt)
        assert result.rebate_variation_stops > 0.2

    def test_step_between_rebate_strips_is_not_a_misfit(self, synthetic, flat):
        # Strips of rebate along different edges can differ by a fixed
        # amount (the gap between frames, the strip beside the holes).
        # That is the film, not the blank: only variation along a strip
        # counts.
        neg = synthetic.negative.copy()
        right = np.zeros(neg.shape[:2], bool)
        right[30:-14, -12:] = True
        clear = synthetic.base * synthetic.falloff[right] * 2 ** 0.06
        neg[right] = clear.astype(np.float32)
        result = Inverter().invert(neg, flat)
        assert result.rebate_variation_stops < 0.03

    def test_base_match_absent_without_rebate(self, synthetic, flat):
        neg = synthetic.negative.copy()
        neg[synthetic.rebate] *= 0.5  # no clear base anywhere now
        result = Inverter().invert(neg, flat)
        assert result.base_ratio is None
        assert result.rebate_variation_stops is None

    def test_percentiles_are_configurable(self, synthetic, flat):
        loose = Inverter(black_percentile=5, white_percentile=95).invert(synthetic.negative, flat)
        tight = Inverter().invert(synthetic.negative, flat)
        assert (loose.white <= tight.white + 1e-6).all()
        assert (loose.black >= tight.black - 1e-6).all()

    def test_rejects_bad_percentiles(self):
        with pytest.raises(Inverter.Error):
            Inverter(black_percentile=60, white_percentile=40)
