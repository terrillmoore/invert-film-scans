##############################################################################
#
# Name: test_flatfield.py
#
# Function:
#       Tests for the FlatField class (smooth fit to a blank frame)
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


class TestFlatField:
    def test_fit_recovers_falloff_and_base(self, synthetic):
        ff = FlatField.fit(synthetic.blank)
        surface = ff.evaluate(synthetic.blank.shape[:2])
        truth = synthetic.falloff * synthetic.base
        open_area = ~(synthetic.gate | synthetic.holes)
        err = surface[open_area] / truth[open_area] - 1
        assert np.abs(err).max() < 0.005

    def test_surface_is_finite_and_positive_over_gate(self, synthetic):
        ff = FlatField.fit(synthetic.blank)
        surface = ff.evaluate(synthetic.blank.shape[:2])
        assert np.isfinite(surface).all()
        assert (surface > 0).all()

    def test_evaluate_at_other_resolution(self, synthetic):
        # the surface is defined in normalized coordinates, so evaluating at
        # twice the size gives the same field
        ff = FlatField.fit(synthetic.blank)
        h, w = synthetic.blank.shape[:2]
        small = ff.evaluate((h, w))
        big = ff.evaluate((2 * h, 2 * w))
        assert np.allclose(big[1::2, 1::2], small, rtol=0.003)

    def test_peak_level_reports_brightest_fitted_value(self, synthetic):
        ff = FlatField.fit(synthetic.blank)
        peak = ff.peak_level()
        truth = (synthetic.falloff * synthetic.base).reshape(-1, 3).max(0)
        assert np.allclose(peak, truth, rtol=0.01)

    def test_falloff_in_stops_at_corners(self, synthetic):
        ff = FlatField.fit(synthetic.blank)
        stops = ff.falloff_stops()
        # over the film area, the darkest point relative to the brightest
        open_area = ~(synthetic.gate | synthetic.holes)
        f = synthetic.falloff[open_area]
        truth = np.log2(f.max(0) / f.min(0))
        assert stops == pytest.approx(truth, abs=0.02)

    def test_rejects_frame_with_no_film_area(self):
        dark = np.full((100, 100, 3), 0.001, np.float32)
        with pytest.raises(FlatField.Error):
            FlatField.fit(dark)

    def test_ignores_clipped_holes(self, synthetic):
        # holes are clipped at 1.0; a fit that used them would be pulled up
        # near the top edge
        ff = FlatField.fit(synthetic.blank)
        surface = ff.evaluate(synthetic.blank.shape[:2])
        truth = synthetic.falloff * synthetic.base
        top = slice(14, 30)
        assert np.abs(surface[top] / truth[top] - 1).max() < 0.005
