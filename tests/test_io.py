##############################################################################
#
# Name: test_io.py
#
# Function:
#       Tests for RawLoader, TiffWriter and ExifTool
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import io
import shutil
import subprocess

import numpy as np
import pytest
import tifffile
from PIL import ImageCms

from invert_film_scans.exiftool import ExifTool
from invert_film_scans.icc import IccProfile
from invert_film_scans.rawloader import RawLoader
from invert_film_scans.tiffwriter import TiffWriter


class _FakeRaw:
    """Stands in for a rawpy.RawPy object."""

    def __init__(self, data: np.ndarray) -> None:
        self.data = data
        self.kwargs: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def postprocess(self, **kwargs):
        self.kwargs = kwargs
        return self.data


class TestRawLoader:
    def test_decodes_linear_camera_rgb(self, monkeypatch, tmp_path):
        data = np.array([[[0, 32768, 65535]]], np.uint16)
        fake = _FakeRaw(data)
        monkeypatch.setattr("invert_film_scans.rawloader.rawpy.imread", lambda p: fake)
        path = tmp_path / "x.RW2"
        path.write_bytes(b"")
        img = RawLoader().load(path)
        assert img.dtype == np.float32
        assert img[0, 0] == pytest.approx([0.0, 0.5, 1.0], abs=1e-4)
        import rawpy

        k = fake.kwargs
        assert k["gamma"] == (1, 1)
        assert k["no_auto_bright"] is True
        assert k["output_bps"] == 16
        assert k["user_wb"] == [1, 1, 1, 1]
        assert k["output_color"] == rawpy.ColorSpace.raw
        assert k["user_flip"] == 0

    def test_reports_unreadable_file(self, tmp_path):
        bad = tmp_path / "bad.RW2"
        bad.write_bytes(b"not a raw file")
        with pytest.raises(RawLoader.Error, match="bad.RW2"):
            RawLoader().load(bad)

    def test_reports_missing_file(self, tmp_path):
        with pytest.raises(RawLoader.Error, match="missing.RW2"):
            RawLoader().load(tmp_path / "missing.RW2")


class TestTiffWriter:
    def test_writes_16_bit_with_profile(self, tmp_path):
        img = np.linspace(0, 1, 4 * 5 * 3, dtype=np.float32).reshape(4, 5, 3)
        icc = IccProfile.adobe_rgb_compatible().to_bytes()
        out = tmp_path / "a.tif"
        TiffWriter(icc).write(out, img)
        with tifffile.TiffFile(out) as t:
            page = t.pages[0]
            data = page.asarray()
            assert data.dtype == np.uint16
            assert data.shape == (4, 5, 3)
            assert bytes(page.tags[34675].value) == icc
        assert data[0, 0, 0] == 0
        assert data[-1, -1, -1] == 65535
        assert np.abs(data / 65535 - img).max() < 1e-4

    def test_clips_out_of_range(self, tmp_path):
        img = np.array([[[-0.5, 0.5, 1.5]]], np.float32)
        out = tmp_path / "b.tif"
        TiffWriter(IccProfile.adobe_rgb_compatible().to_bytes()).write(out, img)
        assert tifffile.imread(out)[0, 0].tolist() == [0, 32768, 65535]

    def test_profile_readable(self, tmp_path):
        icc = IccProfile.adobe_rgb_compatible().to_bytes()
        out = tmp_path / "c.tif"
        TiffWriter(icc).write(out, np.zeros((2, 2, 3), np.float32))
        with tifffile.TiffFile(out) as t:
            prof = ImageCms.ImageCmsProfile(io.BytesIO(bytes(t.pages[0].tags[34675].value)))
        assert "Adobe RGB" in ImageCms.getProfileDescription(prof)


needs_exiftool = pytest.mark.skipif(shutil.which("exiftool") is None, reason="needs exiftool")


class TestExifTool:
    @needs_exiftool
    def test_copies_camera_tags_and_keeps_profile(self, tmp_path):
        icc = IccProfile.adobe_rgb_compatible().to_bytes()
        writer = TiffWriter(icc)
        src = tmp_path / "src.tif"
        dst = tmp_path / "dst.tif"
        tifffile.imwrite(src, np.zeros((2, 2, 3), np.uint16), photometric="rgb")
        subprocess.run(
            [
                "exiftool", "-q", "-overwrite_original",
                "-Make=Panasonic", "-Model=DMC-GX85",
                "-DateTimeOriginal=2026:11:04 02:23:00", str(src),
            ],
            check=True,
        )  # fmt: skip
        writer.write(dst, np.zeros((2, 2, 3), np.float32))
        ExifTool().copy_metadata(src, dst)
        out = subprocess.run(
            ["exiftool", "-s3", "-Make", "-Model", "-DateTimeOriginal", str(dst)],
            capture_output=True, text=True, check=True,
        ).stdout.split("\n")  # fmt: skip
        assert out[:3] == ["Panasonic", "DMC-GX85", "2026:11:04 02:23:00"]
        with tifffile.TiffFile(dst) as t:
            assert bytes(t.pages[0].tags[34675].value) == icc

    @needs_exiftool
    def test_reports_failure(self, tmp_path):
        with pytest.raises(ExifTool.Error):
            ExifTool().copy_metadata(tmp_path / "nope.RW2", tmp_path / "nope.tif")

    def test_missing_program(self):
        with pytest.raises(ExifTool.Error, match="not found"):
            ExifTool(program="no-such-exiftool-program").check()
