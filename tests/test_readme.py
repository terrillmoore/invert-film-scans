##############################################################################
#
# Name: test_readme.py
#
# Function:
#       Tests for the ReadmeReader class
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

from invert_film_scans.readme import ReadmeReader

SAMPLE = """# Title

Intro.

<!-- invert-film-scans:usage:start -->
## Usage

Run it.
<!-- invert-film-scans:usage:end -->

<!-- invert-film-scans:capture:start -->
Shoot a blank frame.
<!-- invert-film-scans:capture:end -->
"""


class TestReadmeReader:
    def test_loads_project_readme(self):
        text = ReadmeReader().content
        assert text.startswith("# Invert Film Scans")

    def test_get_section(self):
        r = ReadmeReader(content=SAMPLE)
        assert r.get_section("usage") == "## Usage\n\nRun it."
        assert r.get_section("capture") == "Shoot a blank frame."

    def test_missing_section(self):
        assert ReadmeReader(content=SAMPLE).get_section("nope") is None

    def test_section_names(self):
        assert ReadmeReader(content=SAMPLE).section_names() == ["capture", "usage"]

    def test_print_raw(self, capsys):
        ReadmeReader(content=SAMPLE).print(raw=True)
        assert capsys.readouterr().out == SAMPLE + "\n"

    def test_print_section_raw(self, capsys):
        assert ReadmeReader(content=SAMPLE).print(section="capture", raw=True)
        assert capsys.readouterr().out == "Shoot a blank frame.\n"

    def test_print_unknown_section(self, capsys):
        assert not ReadmeReader(content=SAMPLE).print(section="nope", raw=True)

    def test_print_formatted(self, capsys):
        assert ReadmeReader(content=SAMPLE).print(section="usage")
        assert "Run it." in capsys.readouterr().out

    def test_project_readme_has_sections(self):
        names = ReadmeReader().section_names()
        assert {"usage", "capture", "method"} <= set(names)
