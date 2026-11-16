##############################################################################
#
# Name: test_app.py
#
# Function:
#       Tests for the App class: options, README display, and runs on
#       synthetic captures
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

from __future__ import annotations

import logging
import pathlib

import numpy as np
import pytest
import tifffile

from invert_film_scans import __version__
from invert_film_scans.app import App
from invert_film_scans.exiftool import ExifTool
from invert_film_scans.rawloader import RawLoader

BOOLEANS = ["overwrite", "dry_run", "skip_metadata", "readme", "raw"]


class TestOptions:
    def test_defaults(self):
        a = App(["-b", "blank.RW2", "n1.RW2", "n2.RW2"]).args
        assert a.blank == pathlib.Path("blank.RW2")
        assert a.negatives == [pathlib.Path("n1.RW2"), pathlib.Path("n2.RW2")]
        assert a.output_dir is None
        assert a.suffix == "_inv"
        assert a.black_percentile == 0.3
        assert a.white_percentile == 99.7
        assert a.verbose == 0
        assert a.readme_section is None
        for name in BOOLEANS:
            assert getattr(a, name) is False

    def test_long_forms(self):
        a = App(
            [
                "--blank", "b.RW2", "--output-dir", "out", "--suffix", "_x",
                "--black-percentile", "1", "--white-percentile", "99", "-vv", "n.RW2",
            ]
        ).args  # fmt: skip
        assert a.blank == pathlib.Path("b.RW2")
        assert a.output_dir == pathlib.Path("out")
        assert a.suffix == "_x"
        assert a.black_percentile == 1.0
        assert a.white_percentile == 99.0
        assert a.verbose == 2

    @pytest.mark.parametrize("name", BOOLEANS)
    def test_boolean_forms(self, name):
        flag = "--" + name.replace("_", "-")
        assert getattr(App([flag], _testing=True).args, name) is True
        no_flag = "--no-" + name.replace("_", "-")
        assert getattr(App([no_flag], _testing=True).args, name) is False
        assert getattr(App([], _testing=True).args, name) is None

    def test_version(self, capsys):
        with pytest.raises(SystemExit) as e:
            App(["--version"]).args  # noqa: B018 -- allow bare attribute access; parsing exits
        assert e.value.code == 0
        assert __version__ in capsys.readouterr().out

    def test_requires_blank(self):
        with pytest.raises(App.Error, match="--blank"):
            App(["n.RW2"]).run()

    def test_requires_negatives(self):
        with pytest.raises(App.Error, match="negative"):
            App(["-b", "b.RW2"]).run()

    def test_rejects_bad_percentiles(self, tmp_path):
        with pytest.raises(App.Error, match="percentile"):
            App(["-b", "b", "--black-percentile", "50", "--white-percentile", "10", "n"]).run()


class TestReadme:
    def test_section_raw(self, capsys):
        assert App(["--readme-section", "usage", "--raw"]).run() == 0
        assert "--blank" in capsys.readouterr().out

    def test_whole_raw(self, capsys):
        assert App(["--readme", "--raw"]).run() == 0
        assert capsys.readouterr().out.startswith("# Invert Film Scans")

    def test_unknown_section(self, capsys):
        assert App(["--readme-section", "nope"]).run() == 1
        assert "capture" in capsys.readouterr().out


class _Captures:
    """Serve synthetic captures in place of decoding raw files."""

    def __init__(self, files: dict[str, np.ndarray]) -> None:
        self.files = files
        self.loaded: list[str] = []

    def load(self, path):
        name = pathlib.Path(path).name
        self.loaded.append(name)
        if name not in self.files:
            raise RawLoader.Error(f"{path}: can't decode raw file")
        return self.files[name]


@pytest.fixture
def captures(monkeypatch, synthetic, tmp_path):
    files = {"blank.RW2": synthetic.blank, "neg1.RW2": synthetic.negative}
    for name in files:
        (tmp_path / name).write_bytes(b"raw")
    cap = _Captures(files)
    monkeypatch.setattr(RawLoader, "load", lambda self, p: cap.load(p))
    return cap


def _run(tmp_path, *extra: str) -> int:
    return App(["-b", str(tmp_path / "blank.RW2"), "--skip-metadata", *extra]).run()


class TestRun:
    def test_writes_positive(self, tmp_path, captures, synthetic, capsys):
        assert _run(tmp_path, str(tmp_path / "neg1.RW2")) == 0
        out = tmp_path / "neg1_inv.tif"
        data = tifffile.imread(out)
        assert data.shape == synthetic.negative.shape
        assert data.dtype == np.uint16
        text = capsys.readouterr().out
        assert "neg1_inv.tif" in text
        assert "base" in text

    def test_output_dir_and_suffix(self, tmp_path, captures):
        dest = tmp_path / "out" / "deeper"
        assert _run(tmp_path, "-o", str(dest), "--suffix", "_p", str(tmp_path / "neg1.RW2")) == 0
        assert (dest / "neg1_p.tif").is_file()

    def test_dry_run_decodes_nothing(self, tmp_path, captures, capsys):
        assert _run(tmp_path, "--dry-run", str(tmp_path / "neg1.RW2")) == 0
        assert captures.loaded == []
        assert not (tmp_path / "neg1_inv.tif").exists()
        assert "neg1_inv.tif" in capsys.readouterr().out

    def test_skips_existing_without_overwrite(self, tmp_path, captures, caplog):
        out = tmp_path / "neg1_inv.tif"
        out.write_bytes(b"old")
        assert _run(tmp_path, str(tmp_path / "neg1.RW2")) == 0
        assert out.read_bytes() == b"old"
        assert "exists" in caplog.text

    def test_overwrite(self, tmp_path, captures):
        out = tmp_path / "neg1_inv.tif"
        out.write_bytes(b"old")
        assert _run(tmp_path, "--overwrite", str(tmp_path / "neg1.RW2")) == 0
        assert out.read_bytes() != b"old"

    def test_blank_in_negatives_is_skipped(self, tmp_path, captures):
        assert _run(tmp_path, str(tmp_path / "blank.RW2"), str(tmp_path / "neg1.RW2")) == 0
        assert not (tmp_path / "blank_inv.tif").exists()
        assert (tmp_path / "neg1_inv.tif").exists()

    def test_missing_negative_is_an_error(self, tmp_path, captures):
        with pytest.raises(App.Error, match="missing.RW2"):
            _run(tmp_path, str(tmp_path / "missing.RW2"))

    def test_bad_negative_continues(self, tmp_path, captures, caplog):
        (tmp_path / "bad.RW2").write_bytes(b"raw")
        assert _run(tmp_path, str(tmp_path / "bad.RW2"), str(tmp_path / "neg1.RW2")) == 1
        assert (tmp_path / "neg1_inv.tif").exists()
        assert "bad.RW2" in caplog.text

    def test_warns_when_blank_near_clipping(self, tmp_path, captures, synthetic, caplog):
        captures.files["blank.RW2"] = np.clip(synthetic.blank * 1.4, 0, 1)
        caplog.set_level(logging.WARNING)
        _run(tmp_path, str(tmp_path / "neg1.RW2"))
        assert "clipping" in caplog.text

    def test_warns_when_blank_does_not_fit(self, tmp_path, captures, synthetic, caplog):
        w = synthetic.negative.shape[1]
        tilt = np.linspace(0.8, 1.15, w, dtype=np.float32)[None, :, None]
        captures.files["neg1.RW2"] = synthetic.negative * tilt
        caplog.set_level(logging.WARNING)
        _run(tmp_path, str(tmp_path / "neg1.RW2"))
        assert "rebate" in caplog.text

    def test_copies_metadata(self, tmp_path, captures, monkeypatch):
        calls = []
        monkeypatch.setattr(ExifTool, "check", lambda self: "exiftool")
        monkeypatch.setattr(ExifTool, "copy_metadata", lambda self, s, d: calls.append((s, d)))
        rc = App(["-b", str(tmp_path / "blank.RW2"), str(tmp_path / "neg1.RW2")]).run()
        assert rc == 0
        assert calls == [(tmp_path / "neg1.RW2", tmp_path / "neg1_inv.tif")]

    def test_checks_exiftool_before_work(self, tmp_path, captures, monkeypatch):
        def missing(self):
            raise ExifTool.Error("exiftool: not found")

        monkeypatch.setattr(ExifTool, "check", missing)
        with pytest.raises(App.Error, match="exiftool"):
            App(["-b", str(tmp_path / "blank.RW2"), str(tmp_path / "neg1.RW2")]).run()
        assert captures.loaded == []
