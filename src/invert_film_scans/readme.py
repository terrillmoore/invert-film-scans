##############################################################################
#
# Name: readme.py
#
# Function:
#       ReadmeReader class: reads the bundled README.md and its sections
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import importlib.resources
import pathlib
import re


class ReadmeReader:
    """Read the README, whole or by marked section.

    Sections are marked with HTML comments, each on its own line:
    an opening `invert-film-scans:NAME:start` comment and a closing
    `invert-film-scans:NAME:end` comment.

    The wheel build copies README.md into the package's resources
    directory; in a source checkout we read it from the repository root.
    """

    class Error(Exception):
        """Raised when the README can't be found."""

    PREFIX = "invert-film-scans"
    SECTION = re.compile(
        r"<!--\s*" + PREFIX + r":(\S+):start\s*-->\s*\n"
        r"(.*?)\n\s*"
        r"<!--\s*" + PREFIX + r":\1:end\s*-->",
        re.DOTALL,
    )

    def __init__(self, content: str | None = None) -> None:
        self._content = content

    @property
    def content(self) -> str:
        if self._content is None:
            self._content = self._load()
        return self._content

    def _load(self) -> str:
        try:
            res = importlib.resources.files("invert_film_scans.resources").joinpath("README.md")
            return res.read_text(encoding="utf-8")
        except (FileNotFoundError, TypeError):
            pass
        import invert_film_scans

        # .../src/invert_film_scans/__init__.py -> repository root
        root = pathlib.Path(invert_film_scans.__file__).resolve().parent.parent.parent
        path = root / "README.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")
        raise self.Error("can't find README.md in the package or the source tree")

    def sections(self) -> dict[str, str]:
        return {m.group(1): m.group(2).strip() for m in self.SECTION.finditer(self.content)}

    def section_names(self) -> list[str]:
        return sorted(self.sections())

    def get_section(self, name: str) -> str | None:
        return self.sections().get(name)

    def print(self, *, section: str | None = None, raw: bool = False) -> bool:
        """Print the README or one section; return False if the section is missing."""
        text = self.content if section is None else self.get_section(section)
        if text is None:
            return False
        if raw:
            print(text)
        else:
            from rich.console import Console
            from rich.markdown import Markdown

            Console().print(Markdown(text))
        return True
