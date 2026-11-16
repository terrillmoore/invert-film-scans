##############################################################################
#
# Name: test_real_files.py
#
# Function:
#       End-to-end test on real raw files, when the environment names them
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import os
import pathlib
import re

import pytest
import tifffile

from invert_film_scans.app import App

BLANK = os.environ.get("INVERT_FILM_SCANS_TEST_BLANK")
NEGATIVE = os.environ.get("INVERT_FILM_SCANS_TEST_NEGATIVE")

pytestmark = pytest.mark.skipif(
    not (BLANK and NEGATIVE),
    reason="set INVERT_FILM_SCANS_TEST_BLANK and INVERT_FILM_SCANS_TEST_NEGATIVE to raw files",
)


class TestRealFiles:
    def test_inverts_real_negative(self, tmp_path, capsys):
        negative = pathlib.Path(NEGATIVE)
        rc = App(["-b", BLANK, "-o", str(tmp_path), "--skip-metadata", NEGATIVE]).run()
        assert rc == 0
        out = tmp_path / f"{negative.stem}_inv.tif"
        data = tifffile.imread(out)
        assert data.ndim == 3 and data.shape[2] == 3
        # the picture uses most of the output range
        assert data.min() < 2000 and data.max() > 63000
        line = capsys.readouterr().out
        m = re.search(r"rebate varies ([0-9.]+) stop", line)
        if m:
            assert float(m.group(1)) < App.VARIATION_WARNING
