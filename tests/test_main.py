##############################################################################
#
# Name: test_main.py
#
# Function:
#       Tests for the command entry point
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

from invert_film_scans.__main__ import main


class TestMain:
    def test_user_error_is_reported_plainly(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["invert-film-scans", "n.RW2"])
        assert main() == 1
        err = capsys.readouterr().err
        assert err.startswith("invert-film-scans: error:")
        assert "Traceback" not in err

    def test_success_status(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["invert-film-scans", "--readme-section", "usage", "--raw"])
        assert main() == 0
