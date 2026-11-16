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
