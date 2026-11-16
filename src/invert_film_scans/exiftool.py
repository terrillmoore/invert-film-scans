##############################################################################
#
# Name: exiftool.py
#
# Function:
#       ExifTool class: copies camera metadata from a raw file to an output
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import datetime
import json
import pathlib
import shutil
import subprocess


class ExifTool:
    """Run exiftool to copy metadata.

    annotate-film-scans expects the camera's metadata on each scan (it
    moves the camera and capture time to the scanner and scan-date tags),
    so we copy everything from the raw file, unchanged, except the ICC
    profile: the output's own profile must stay.
    """

    class Error(Exception):
        """Raised when exiftool is missing or fails."""

    def __init__(self, program: str = "exiftool") -> None:
        self.program = program

    def check(self) -> str:
        """Return the path to exiftool, or raise Error."""
        path = shutil.which(self.program)
        if path is None:
            raise self.Error(f"{self.program}: not found on PATH (install exiftool)")
        return path

    def capture_times(
        self, paths: list[pathlib.Path]
    ) -> dict[pathlib.Path, datetime.datetime | None]:
        """Return each file's capture time (with sub-seconds), or None.

        One exiftool run for all files. Files that exiftool can't read,
        or that carry no DateTimeOriginal, map to None.
        """
        program = self.check()
        out: dict[pathlib.Path, datetime.datetime | None] = dict.fromkeys(paths)
        if not paths:
            return out
        result = subprocess.run(
            [program, "-j", "-q", "-q", "-DateTimeOriginal", "-SubSecTimeOriginal",
             *[str(p) for p in paths]],
            capture_output=True,
            text=True,
        )  # fmt: skip
        try:
            records = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as e:
            raise self.Error(f"can't read exiftool output: {e}") from e
        by_name = {str(p): p for p in paths}
        for rec in records:
            path = by_name.get(rec.get("SourceFile", ""))
            stamp = rec.get("DateTimeOriginal")
            if path is None or not isinstance(stamp, str):
                continue
            try:
                t = datetime.datetime.strptime(stamp.strip(), "%Y:%m:%d %H:%M:%S")
            except ValueError:
                continue
            sub = str(rec.get("SubSecTimeOriginal", "")).strip()
            if sub.isdigit():
                t += datetime.timedelta(seconds=int(sub) / 10 ** len(sub))
            out[path] = t
        return out

    def copy_metadata(self, source: pathlib.Path, dest: pathlib.Path) -> None:
        """Copy all tags from source to dest, keeping dest's ICC profile."""
        program = self.check()
        result = subprocess.run(
            [
                program,
                "-q",
                "-q",
                "-overwrite_original",
                "-TagsFromFile",
                str(source),
                "-all:all",
                "--ICC_Profile",
                str(dest),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise self.Error(
                f"exiftool failed copying {source} to {dest}: {result.stderr.strip()}"
            )
