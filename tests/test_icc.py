##############################################################################
#
# Name: test_icc.py
#
# Function:
#       Tests for the IccProfile class
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
import struct

from PIL import Image, ImageCms

from invert_film_scans.icc import IccProfile


class TestIccProfile:
    def _tags(self, data: bytes) -> dict[bytes, bytes]:
        count = struct.unpack(">I", data[128:132])[0]
        tags = {}
        for i in range(count):
            sig, off, length = struct.unpack(">4sII", data[132 + 12 * i : 144 + 12 * i])
            tags[sig] = data[off : off + length]
        return tags

    def test_header_size_matches_length(self):
        data = IccProfile.adobe_rgb_compatible().to_bytes()
        assert struct.unpack(">I", data[:4])[0] == len(data)
        assert data[36:40] == b"acsp"
        assert data[12:16] == b"mntr"

    def test_lcms_accepts_profile_and_reads_description(self):
        data = IccProfile.adobe_rgb_compatible().to_bytes()
        prof = ImageCms.ImageCmsProfile(io.BytesIO(data))
        assert "Adobe RGB (1998)" in ImageCms.getProfileDescription(prof)

    def test_gamma_is_563_over_256(self):
        tags = self._tags(IccProfile.adobe_rgb_compatible().to_bytes())
        for sig in (b"rTRC", b"gTRC", b"bTRC"):
            assert tags[sig][:4] == b"curv"
            assert tags[sig][8:14] == b"\x00\x00\x00\x01\x02\x33"

    def test_gray_maps_to_gray_in_srgb(self):
        data = IccProfile.adobe_rgb_compatible().to_bytes()
        src = ImageCms.ImageCmsProfile(io.BytesIO(data))
        dst = ImageCms.createProfile("sRGB")
        xform = ImageCms.buildTransform(src, dst, "RGB", "RGB")
        for v in (32, 128, 220):
            r, g, b = ImageCms.applyTransform(Image.new("RGB", (1, 1), (v, v, v)), xform).getpixel(
                (0, 0)
            )
            assert max(r, g, b) - min(r, g, b) <= 1
            # Adobe RGB and sRGB tone curves are close: within a few counts
            assert abs(g - v) <= 6

    def test_primaries_match_adobe_rgb(self):
        tags = self._tags(IccProfile.adobe_rgb_compatible().to_bytes())

        def xyz(sig: bytes) -> list[float]:
            return [v / 65536 for v in struct.unpack(">3i", tags[sig][8:20])]

        assert [round(v, 3) for v in xyz(b"rXYZ")] == [0.610, 0.311, 0.019]
        assert [round(v, 3) for v in xyz(b"gXYZ")] == [0.205, 0.626, 0.061]
        assert [round(v, 3) for v in xyz(b"bXYZ")] == [0.149, 0.063, 0.745]
        assert [round(v, 3) for v in xyz(b"wtpt")] == [0.950, 1.000, 1.089]
