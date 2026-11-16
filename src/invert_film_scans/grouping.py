##############################################################################
#
# Name: grouping.py
#
# Function:
#       FrameGrouper class: groups repeated captures of one negative by
#       capture time
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
from collections.abc import Iterable


class FrameGrouper:
    """Group captures taken close together in time.

    Several captures of one negative, averaged, have less sensor noise.
    They are taken a second or two apart; moving the film to the next
    frame takes longer. So frames whose capture times are within `gap`
    seconds of the previous frame belong to one group.
    """

    class Error(Exception):
        """Raised for invalid settings."""

    def __init__(self, gap_seconds: float) -> None:
        if gap_seconds < 0:
            raise self.Error(f"group gap must be zero or more seconds, not {gap_seconds}")
        self.gap = dt.timedelta(seconds=gap_seconds)

    def group(
        self, items: Iterable[tuple[pathlib.Path, dt.datetime | None]]
    ) -> list[list[pathlib.Path]]:
        """Return groups of paths, in capture order.

        Frames without a capture time stand alone, after the others.
        """
        items = list(items)
        timed = sorted(((t, p) for p, t in items if t is not None), key=lambda x: x[0])
        untimed = [p for p, t in items if t is None]

        grouping = self.gap.total_seconds() > 0
        groups: list[list[pathlib.Path]] = []
        last: dt.datetime | None = None
        for t, p in timed:
            if grouping and groups and last is not None and t - last <= self.gap:
                groups[-1].append(p)
            else:
                groups.append([p])
            last = t
        groups.extend([p] for p in untimed)
        return groups
