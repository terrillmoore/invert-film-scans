# Invert Film Scans

`invert-film-scans` turns raw camera captures of color negatives into
positive 16-bit TIFF files, ready for spotting, Lightroom, and
[annotate-film-scans](https://github.com/terrillmoore/annotate-film-scans).

<!-- TOC depthFrom:2 updateOnSave:true -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Capturing the negatives](#capturing-the-negatives)
- [Usage](#usage)
- [What the messages mean](#what-the-messages-mean)
- [How it works](#how-it-works)
- [Meta](#meta)

<!-- /TOC -->

## Introduction

If you digitize color negatives with a camera, a macro lens and a light
source, every frame needs the same three corrections before it looks like a
photograph: remove the light falloff of the lens and light source, remove the
orange mask of the film base, and invert the negative with the right contrast
in each dye layer. This program does all three, in batch, from the camera's
raw files.

It needs one extra capture per roll: a frame of blank film (processed but
unexposed, such as the leader) shot with the same setup. That single frame
gives both the falloff and the base color.

The output files carry the camera's metadata, copied from the raw file, so
annotate-film-scans can move the camera and capture time to the scanner tags
as usual.

## Prerequisites

- Python 3.13 or later, run with [uv](https://docs.astral.sh/uv/).
- [exiftool](https://exiftool.org/), installed separately (Homebrew, apt, or
  scoop). Needed only to copy metadata.
- Raw files that LibRaw can read. Tested with Panasonic RW2 files from a
  DMC-GX85.

To run from a clone:

```bash
git clone https://github.com/terrillmoore/invert-film-scans
cd invert-film-scans
uv run invert-film-scans --help
```

## Capturing the negatives

<!-- invert-film-scans:capture:start -->
- Use one setup for the roll: same lens, extension, aperture, focus, holder
  position and light. Changing any of them changes the falloff.
- Use the electronic shutter. On the GX85, the mechanical shutter adds an
  uneven exposure of 1 to 2% across the frame at short speeds. A DC-powered
  light source doesn't flicker, so the electronic shutter is safe with it.
- Expose so that clear film base stays well below clipping in every channel.
  The program warns if the blank frame comes within 5% of clipping. Sprocket
  holes clip; that's expected and harmless.
- Shoot one or two frames of blank film from the same roll (leader, or an
  unexposed frame), with the film in the holder, at the same shutter speed as
  the negatives. Don't move the holder between the blank and the negatives if
  you can help it. A blank shot later works if the holder sits close to where
  it was; the program checks this for each frame.
- Frame the whole negative with a little rebate around it. On Micro Four
  Thirds that is a magnification of about 0.44 (a 39 x 29.5 mm field).
<!-- invert-film-scans:capture:end -->

## Usage

<!-- invert-film-scans:usage:start -->
```bash
invert-film-scans [options] --blank BLANK.RW2 NEGATIVE.RW2 ...
```

For each negative, writes `NAME_inv.tif` (16-bit, with an Adobe RGB (1998)
compatible profile, deflate compressed) next to the raw file, or in
`--output-dir`, and copies the raw file's metadata into it.

Options:

- `-b FILE`, `--blank FILE`: raw capture of blank film from the same roll and
  setup. Required.
- `-o DIR`, `--output-dir DIR`: write the TIFFs here (created if needed).
  Default: next to each raw file.
- `--suffix TEXT`: added to each output name. Default: `_inv`.
- `--overwrite`: replace existing output files. Without it, existing files are
  skipped.
- `--dry-run`: check the inputs and show what would be written, without
  decoding anything.
- `--skip-metadata`: don't copy metadata (no exiftool needed).
- `--black-percentile P`: the darkest P percent of the picture, by mean
  density, sets black. Default: 0.3.
- `--white-percentile P`: the areas above percentile P set white. Default:
  99.7.
- `-v`, `--verbose`: more detail; repeat for more.
- `--version`: print the version and exit.
- `--readme`: print this README and exit.
- `--readme-section NAME`: print one section of this README (`capture`,
  `usage`, `messages`, `method`) and exit.
- `--raw`: with `--readme` or `--readme-section`, print the Markdown source.

Every on/off option also has a `--no-` form.

Example:

```bash
invert-film-scans -b _1010753.RW2 -o inverted _1010752.RW2 _1010754.RW2
```

The blank frame is skipped if it also appears in the list of negatives.
<!-- invert-film-scans:usage:end -->

## What the messages mean

<!-- invert-film-scans:messages:start -->
For each frame the program prints the output name, the black and white points
(density above base, red, green, blue), and two checks of the blank frame
against the negative's rebate:

- **base**: rebate level divided by the blank frame's level, per channel. Near
  1.00 when the blank was shot in the same session at the same shutter speed.
  A different session or shutter shows up here as a few percent; that doesn't
  affect the result.
- **rebate spread**: how much the rebate still varies across the frame after
  the falloff correction, in stops. Above 0.05 stop the program warns: the
  blank doesn't fit this frame, usually because the holder or lens moved.
  Shoot a new blank.

If a frame has no clear rebate, these checks are skipped.

The program also warns if the blank frame's brightest film area is within 5%
of clipping in any channel.
<!-- invert-film-scans:messages:end -->

## How it works

<!-- invert-film-scans:method:start -->
1. Each raw file is decoded to linear camera RGB, with no color matrix, white
   balance or tone curve. Densities must come from the sensor's own channels;
   a color matrix mixes the channels before the log and distorts hues after
   inversion.
2. A smooth surface (a degree-6 polynomial in the log of each channel) is
   fitted to the blank frame, leaving out the gate, sprocket holes and a margin
   around them.
3. Each negative is divided by that surface. The result is transmittance
   relative to the film base, with the falloff removed. Its negative log is
   density above base.
4. Black and white points are read from the same pixels in all three channels:
   the darkest and lightest areas of the picture by mean density. Reading each
   channel's own percentiles picks different objects in each channel and gives
   a color cast.
5. Each channel's density is rescaled so black is 0 and white is 1, and
   written as gamma-encoded Adobe RGB values. This gives each dye layer its own
   contrast, the way a print does.
<!-- invert-film-scans:method:end -->

## Meta

### Git repo (for code and issues)

<https://github.com/terrillmoore/invert-film-scans>

### Author

Terry Moore

### Status

2026-11-16: First version. Tested on Panasonic GX85 captures of 35 mm C-41
film.

### License

Released under the MIT license. See [LICENSE.md](LICENSE.md).
