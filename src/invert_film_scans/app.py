##############################################################################
#
# Name: app.py
#
# Function:
#       App class: command-line parsing and orchestration
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from collections.abc import Sequence

import numpy as np

from .__version__ import __version__
from .exiftool import ExifTool
from .flatfield import FlatField
from .grouping import FrameGrouper
from .icc import IccProfile
from .inverter import Inverter
from .rawloader import RawLoader
from .readme import ReadmeReader
from .stack import FrameStack
from .tiffwriter import TiffWriter

Job = tuple[list[pathlib.Path], pathlib.Path]  # frames to average, output path


class App:
    """The invert-film-scans application."""

    class Error(Exception):
        """A user error: reported plainly, without a traceback."""

    PROGNAME = "invert-film-scans"
    CLIP_WARNING = 0.95  # warn if the blank's film area reaches this level
    VARIATION_WARNING = 0.05  # warn if rebate varies more than this along an edge (stops)

    def __init__(self, argv: Sequence[str] | None = None, *, _testing: bool = False) -> None:
        """Parse the command line.

        `_testing` makes on/off options default to None, so tests can tell
        "not given" from "turned off".
        """
        self._argv = list(argv) if argv is not None else sys.argv[1:]
        self._testing = _testing
        self.args = self._parse(self._argv)
        level = max(logging.DEBUG, logging.WARNING - 10 * (self.args.verbose or 0))
        logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
        self.log = logging.getLogger("invert_film_scans")
        self.log.setLevel(level)

    # ------------------------------------------------------------------
    # command line
    # ------------------------------------------------------------------
    def _parse(self, argv: list[str]) -> argparse.Namespace:
        off = None if self._testing else False
        p = argparse.ArgumentParser(
            prog=self.PROGNAME,
            description="Invert raw camera captures of color negatives into positive TIFFs.",
            epilog="Use --readme for the full documentation.",
        )
        p.add_argument("negatives", nargs="*", type=pathlib.Path, help="raw negatives")
        p.add_argument(
            "-b", "--blank", type=pathlib.Path, help="raw capture of blank film (required)"
        )
        p.add_argument(
            "-o", "--output-dir", type=pathlib.Path, help="output directory (default: beside input)"
        )
        p.add_argument("--suffix", default="_inv", help="added to output names (default: _inv)")
        p.add_argument(
            "--overwrite",
            action=argparse.BooleanOptionalAction,
            default=off,
            help="replace existing outputs",
        )
        p.add_argument(
            "--dry-run",
            action=argparse.BooleanOptionalAction,
            default=off,
            help="show what would be done",
        )
        p.add_argument(
            "--skip-metadata",
            action=argparse.BooleanOptionalAction,
            default=off,
            help="don't copy metadata with exiftool",
        )
        p.add_argument(
            "--black-percentile",
            type=float,
            default=0.3,
            metavar="P",
            help="darkest P percent sets black (default: 0.3)",
        )
        p.add_argument(
            "--white-percentile",
            type=float,
            default=99.7,
            metavar="P",
            help="areas above percentile P set white (default: 99.7)",
        )
        p.add_argument(
            "--group-gap",
            type=float,
            default=3.0,
            metavar="SECONDS",
            help="average captures taken within this many seconds of each other "
            "(default: 3; 0 turns averaging off)",
        )
        p.add_argument("-v", "--verbose", action="count", default=0, help="more detail")
        p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
        p.add_argument(
            "--readme",
            action=argparse.BooleanOptionalAction,
            default=off,
            help="print the README and exit",
        )
        p.add_argument("--readme-section", metavar="NAME", help="print one README section")
        p.add_argument(
            "--raw",
            action=argparse.BooleanOptionalAction,
            default=off,
            help="with --readme: print Markdown source",
        )
        return p.parse_args(argv)

    # ------------------------------------------------------------------
    # top level
    # ------------------------------------------------------------------
    def run(self) -> int:
        """Run the command; return the exit status."""
        a = self.args
        if a.readme or a.readme_section:
            return self._show_readme()
        if a.blank is None:
            raise self.Error("--blank is required")
        if not a.negatives:
            raise self.Error("no negative files given")
        try:
            inverter = Inverter(a.black_percentile, a.white_percentile)
        except Inverter.Error as e:
            raise self.Error(f"bad percentile settings: {e}") from e

        try:
            grouper = FrameGrouper(a.group_gap)
        except FrameGrouper.Error as e:
            raise self.Error(str(e)) from e

        for path in [a.blank, *a.negatives]:
            if not path.is_file():
                raise self.Error(f"{path}: file not found")
        exiftool = ExifTool()
        if a.group_gap > 0:
            try:
                exiftool.check()
            except ExifTool.Error as e:
                raise self.Error(
                    f"{e}; it reads capture times for averaging; or use --group-gap 0"
                ) from e
        if not a.skip_metadata and not a.dry_run:
            try:
                exiftool.check()
            except ExifTool.Error as e:
                raise self.Error(f"{e}; or use --skip-metadata") from e

        jobs = self._plan(grouper, exiftool)
        if a.dry_run:
            for frames, dst in jobs:
                print(f"{', '.join(f.name for f in frames)} -> {dst}")
            return 0

        loader = RawLoader()
        try:
            flat = FlatField.fit(loader.load(a.blank))
        except (RawLoader.Error, FlatField.Error) as e:
            raise self.Error(f"blank frame {a.blank}: {e}") from e
        self._check_blank(flat)

        writer = TiffWriter(IccProfile.adobe_rgb_compatible().to_bytes())
        status = 0
        for frames, dst in jobs:
            try:
                self._process_group(frames, dst, loader, flat, inverter, writer, exiftool)
            except (RawLoader.Error, Inverter.Error, ExifTool.Error, OSError) as e:
                self.log.error("%s: %s", frames[0], e)
                status = 1
        return status

    def _show_readme(self) -> int:
        reader = ReadmeReader()
        if reader.print(section=self.args.readme_section, raw=bool(self.args.raw)):
            return 0
        print(f"No README section named {self.args.readme_section!r}. Sections:")
        for name in reader.section_names():
            print(f"  {name}")
        return 1

    # ------------------------------------------------------------------
    # steps
    # ------------------------------------------------------------------
    def _output_path(self, src: pathlib.Path) -> pathlib.Path:
        a = self.args
        out_dir = a.output_dir if a.output_dir is not None else src.parent
        return out_dir / f"{src.stem}{a.suffix}.tif"

    def _plan(self, grouper: FrameGrouper, exiftool: ExifTool) -> list[Job]:
        a = self.args
        blank = a.blank.resolve()
        negatives = []
        for src in a.negatives:
            if src.resolve() == blank:
                self.log.info("%s: the blank frame; skipped", src)
            elif src not in negatives:
                negatives.append(src)
        if a.group_gap > 0:
            times = exiftool.capture_times(negatives)
            for src, t in times.items():
                if t is None:
                    self.log.warning("%s: no capture time; not averaged with others", src)
            groups = grouper.group((src, times[src]) for src in negatives)
        else:
            groups = [[src] for src in negatives]

        jobs = []
        for frames in groups:
            dst = self._output_path(frames[0])
            if dst.exists() and not a.overwrite:
                self.log.warning("%s: exists; skipped (use --overwrite to replace)", dst)
                continue
            jobs.append((frames, dst))
        return jobs

    def _check_blank(self, flat: FlatField) -> None:
        peak = flat.peak_level()
        stops = flat.falloff_stops()
        self.log.info(
            "blank: peak level R %.2f G %.2f B %.2f; falloff %.2f/%.2f/%.2f stops",
            *peak,
            *stops,
        )
        if (peak >= self.CLIP_WARNING).any():
            self.log.warning(
                "blank frame is near clipping (peak R %.2f G %.2f B %.2f of full scale); "
                "use less exposure",
                *peak,
            )

    def _process_group(
        self,
        frames: list[pathlib.Path],
        dst: pathlib.Path,
        loader: RawLoader,
        flat_field: FlatField,
        inverter: Inverter,
        writer: TiffWriter,
        exiftool: ExifTool,
    ) -> None:
        """Average a group of captures and invert it.

        A frame that doesn't line up with the first one of its stack (the
        film moved, or it is another picture) starts a new stack, which is
        written separately under its own name.
        """
        stack = FrameStack(loader.load(frames[0]))
        members = [frames[0]]
        for src in frames[1:]:
            img = loader.load(src)
            if stack.add(img):
                members.append(src)
                continue
            self.log.warning("%s: %s; written separately", src, stack.last_reason)
            self._finish(stack, members, dst, flat_field, inverter, writer, exiftool)
            dst = self._output_path(src)
            if dst.exists() and not self.args.overwrite:
                self.log.warning("%s: exists; skipped (use --overwrite to replace)", dst)
            stack = FrameStack(img)
            members = [src]
        self._finish(stack, members, dst, flat_field, inverter, writer, exiftool)

    def _finish(
        self,
        stack: FrameStack,
        members: list[pathlib.Path],
        dst: pathlib.Path,
        flat_field: FlatField,
        inverter: Inverter,
        writer: TiffWriter,
        exiftool: ExifTool,
    ) -> None:
        if dst.exists() and not self.args.overwrite:
            return
        negative = stack.mean()
        del stack
        flat = flat_field.evaluate(negative.shape[:2])
        result = inverter.invert(negative, flat)
        del negative, flat
        dst.parent.mkdir(parents=True, exist_ok=True)
        writer.write(dst, result.positive)
        src = members[0]
        if not self.args.skip_metadata:
            exiftool.copy_metadata(src, dst)

        name = src.name if len(members) == 1 else f"{src.name} ({len(members)} frames)"
        line = (
            f"{name} -> {dst}: black {self._fmt(result.black)}, "
            f"white {self._fmt(result.white)}"
        )
        if result.base_ratio is not None and result.rebate_variation_stops is not None:
            line += (
                f", base {self._fmt(result.base_ratio)}, "
                f"rebate varies {result.rebate_variation_stops:.3f} stop along an edge"
            )
            if result.rebate_variation_stops > self.VARIATION_WARNING:
                self.log.warning(
                    "%s: rebate varies %.2f stop along an edge after correction; "
                    "the blank frame may not fit this frame's setup",
                    src,
                    result.rebate_variation_stops,
                )
        else:
            line += ", no clear rebate found"
        print(line)

    @staticmethod
    def _fmt(v: np.ndarray) -> str:
        return "/".join(f"{x:.3f}" for x in v)
