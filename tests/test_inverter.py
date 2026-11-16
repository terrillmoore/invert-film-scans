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

    def test_output_range(self, synthetic, flat):
        result = Inverter().invert(synthetic.negative, flat)
        assert result.positive.dtype == np.float32
        assert result.positive.min() >= 0.0
        assert result.positive.max() <= 1.0

    def test_base_match_with_matching_blank(self, synthetic, flat):
        result = Inverter().invert(synthetic.negative, flat)
        assert result.base_ratio == pytest.approx([1, 1, 1], abs=0.02)
        assert result.base_spread_stops < 0.03

    def test_base_match_detects_wrong_flat(self, synthetic, flat):
        h, w = flat.shape[:2]
        tilt = np.linspace(0.85, 1.15, w)[None, :, None].astype(np.float32)
        result = Inverter().invert(synthetic.negative, flat * tilt)
        assert result.base_spread_stops > 0.2

    def test_base_match_absent_without_rebate(self, synthetic, flat):
        neg = synthetic.negative.copy()
        neg[synthetic.rebate] *= 0.5  # no clear base anywhere now
        result = Inverter().invert(neg, flat)
        assert result.base_ratio is None
        assert result.base_spread_stops is None

    def test_percentiles_are_configurable(self, synthetic, flat):
        loose = Inverter(black_percentile=5, white_percentile=95).invert(synthetic.negative, flat)
        tight = Inverter().invert(synthetic.negative, flat)
        assert (loose.white <= tight.white + 1e-6).all()
        assert (loose.black >= tight.black - 1e-6).all()

    def test_rejects_bad_percentiles(self):
        with pytest.raises(Inverter.Error):
            Inverter(black_percentile=60, white_percentile=40)
