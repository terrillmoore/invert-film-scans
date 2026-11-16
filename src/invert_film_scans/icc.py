##############################################################################
#
# Name: icc.py
#
# Function:
#       IccProfile class: builds small matrix/TRC ICC v2 display profiles
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class IccProfile:
    """A matrix/TRC RGB display profile (ICC v2.1).

    The output TIFFs need an embedded profile. We build our own instead of
    shipping Adobe's file: the colorants, white point and tone curve are
    the published Adobe RGB (1998) values, so color-managed applications
    treat the data identically.
    """

    description: str
    copyright: str
    white: tuple[float, float, float]
    red: tuple[float, float, float]
    green: tuple[float, float, float]
    blue: tuple[float, float, float]
    gamma: float

    # PCS illuminant (D50), required in every profile header
    D50 = (0.9642, 1.0, 0.8249)

    @classmethod
    def adobe_rgb_compatible(cls) -> IccProfile:
        """Return a profile with the Adobe RGB (1998) primaries and gamma."""
        return cls(
            description="Adobe RGB (1998) compatible (invert-film-scans)",
            copyright="No copyright, use freely",
            white=(0.950455, 1.0, 1.08905),
            red=(0.609741, 0.311111, 0.019470),
            green=(0.205276, 0.625671, 0.060867),
            blue=(0.149185, 0.063217, 0.744568),
            gamma=563 / 256,
        )

    @staticmethod
    def _s15f16(v: float) -> bytes:
        return struct.pack(">i", round(v * 65536))

    def _xyz(self, v: tuple[float, float, float]) -> bytes:
        return b"XYZ " + b"\0" * 4 + b"".join(self._s15f16(c) for c in v)

    def _curv(self) -> bytes:
        # one entry: gamma as u8Fixed8Number
        return b"curv" + b"\0" * 4 + struct.pack(">IH", 1, round(self.gamma * 256))

    @staticmethod
    def _text(s: str) -> bytes:
        return b"text" + b"\0" * 4 + s.encode("ascii") + b"\0"

    @staticmethod
    def _desc(s: str) -> bytes:
        a = s.encode("ascii") + b"\0"
        # ASCII part, then empty Unicode and ScriptCode parts
        unicode_part = b"\0" * 8  # language code and count
        script_part = b"\0" * 3 + b"\0" * 67  # code, count, and 67-byte string
        return b"desc" + b"\0" * 4 + struct.pack(">I", len(a)) + a + unicode_part + script_part

    def to_bytes(self) -> bytes:
        """Serialize the profile."""
        curv = self._curv()
        tags = [
            (b"desc", self._desc(self.description)),
            (b"cprt", self._text(self.copyright)),
            (b"wtpt", self._xyz(self.white)),
            (b"rXYZ", self._xyz(self.red)),
            (b"gXYZ", self._xyz(self.green)),
            (b"bXYZ", self._xyz(self.blue)),
            (b"rTRC", curv),
            (b"gTRC", curv),
            (b"bTRC", curv),
        ]
        data_start = 128 + 4 + 12 * len(tags)
        table = b""
        data = b""
        for sig, body in tags:
            while (data_start + len(data)) % 4:
                data += b"\0"
            table += sig + struct.pack(">II", data_start + len(data), len(body))
            data += body
        body = struct.pack(">I", len(tags)) + table + data
        size = 128 + len(body)
        header = (
            struct.pack(">I", size)
            + b"none"  # preferred CMM: none
            + bytes([2, 0x10, 0, 0])  # version 2.1
            + b"mntrRGB XYZ "
            + struct.pack(">6H", 2026, 1, 1, 0, 0, 0)
            + b"acsp"
            + b"\0" * 4  # platform
            + b"\0" * 4  # flags
            + b"\0" * 4  # manufacturer
            + b"\0" * 4  # model
            + b"\0" * 8  # attributes
            + struct.pack(">I", 0)  # rendering intent: perceptual
            + b"".join(self._s15f16(c) for c in self.D50)
            + b"\0" * 4  # creator
            + b"\0" * 44  # profile ID and reserved
        )
        return header + body
