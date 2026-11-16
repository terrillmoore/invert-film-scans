# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project

invert-film-scans is a CLI tool that turns raw camera captures of color
negatives into positive 16-bit TIFFs. It uses one capture of blank film from
the same roll and setup to remove illumination falloff and the film base, then
inverts in the density domain with per-channel black and white points read
from the same pixels. It copies the raw file's metadata into each TIFF with
exiftool, for annotate-film-scans.

## Build and Run

Requires Python >= 3.13, `uv`, and `exiftool` (installed separately).

```bash
make test        # uv run pytest
make lint        # uv run ruff check src tests
make build       # build distribution in dist/
make clean       # remove caches and egg-info
make distclean   # clean + remove dist/
```

Run directly:

```bash
uv run invert-film-scans -b BLANK.RW2 NEGATIVE.RW2 ...
```

After cloning, enable the hooks: `git config core.hooksPath .githooks`.

## Tests

pytest, in `tests/`. Write tests first (red/green).

- **conftest.py**: `SyntheticFactory` builds captures that behave like the
  real setup: off-center per-channel falloff, a gate on two sides, clipped
  sprocket holes, a clear rebate strip, and a negative made from a known
  scene with different contrast in each dye layer.
- **test_icc.py**, **test_flatfield.py**, **test_inverter.py**: the units.
- **test_io.py**: RawLoader (with a stand-in for rawpy), TiffWriter, and
  ExifTool (skipped without exiftool).
- **test_app.py**, **test_main.py**: options and end-to-end runs, with
  `RawLoader.load` replaced by synthetic captures.
- **test_real_files.py**: runs on real raw files when
  `INVERT_FILM_SCANS_TEST_BLANK` and `INVERT_FILM_SCANS_TEST_NEGATIVE` name
  them; skipped otherwise. Raw files are too big for the repository.

Unit tests aren't enough for changes to the inversion or the masks; also run
real frames and look at the results. Soft edges (an out-of-focus gate, the
fade at the edge of the exposed frame) are the usual trouble: they pass
through every density and can set false endpoints.

## Architecture

Source modules in `src/invert_film_scans/`:

- **app.py**: `App` class. Argument parsing, checks, and the loop over
  negatives. `__main__.main()` creates `App()` and calls `App.run()`.
- **rawloader.py**: `RawLoader`. LibRaw decode to linear camera RGB (raw
  color, unit white balance, no curve), 1.0 = white level.
- **flatfield.py**: `FlatField`. Degree-6 polynomial in the log of each
  channel of the blank frame, in normalized coordinates; evaluated
  separably.
- **inverter.py**: `Inverter`. Density above base, the picture mask,
  same-pixel endpoints, rescaling, and the rebate check.
- **icc.py**: `IccProfile`. Builds an Adobe RGB (1998) compatible matrix/TRC
  profile, so we don't ship Adobe's file.
- **tiffwriter.py**: `TiffWriter`. 16-bit deflate TIFF with the profile.
- **exiftool.py**: `ExifTool`. Copies all tags from the raw file except the
  ICC profile.
- **readme.py**: `ReadmeReader`. Prints the README or a marked section; the
  wheel bundles README.md under `resources/`.

## Key Conventions

- Every source file starts with the standard header block (name, function,
  copyright reference to LICENSE.md, author).
- No bare functions outside classes, except `main()` in `__main__.py`.
- On/off options use `argparse.BooleanOptionalAction` with `default=False`;
  `App(..., _testing=True)` makes them default to `None` for tests.
- Dependencies are constrained as `>=X.Y, ==X.*` (pre-1.0: pin the minor).
- Linter suppressions need an explanation: `# noqa: CODE -- what; why`. Ask
  before adding markdownlint suppressions; wrap Markdown at 80 columns.
- Version is defined only in `pyproject.toml`; bump it with each feature.
- Densities come from camera RGB, never after a color matrix.
- Never change the copied camera tags: annotate-film-scans relies on them.
- README sections marked `invert-film-scans:NAME:start` / `:end` are printed
  by `--readme-section`; keep the list in the usage section in sync.
