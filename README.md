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
General rules:

- Use one setup for the roll: same lens, extension, aperture, focus, holder
  position and light. Changing any of them changes the falloff.
- Use the electronic shutter. On the GX85, the mechanical shutter adds an
  uneven exposure of 1 to 2% across the frame at short speeds. A DC-powered
  light source doesn't flicker, so the electronic shutter is safe with it.
- Expose as much as the film base allows: about 90% of full scale in the
  brightest channel of the raw data. Every part of the picture is denser than
  the base, so nothing in it clips if the base doesn't, and more light means
  less sensor noise. The camera's histogram is drawn from its JPEG, after a
  tone curve, and is a poor guide; check a raw frame of clear film instead.
  The program warns if the blank frame comes within 5% of clipping. Sprocket
  holes clip; that's expected and harmless.
- Shoot one frame of blank film from the same roll (leader, or an unexposed
  frame), with the film in the holder, at the same exposure as the negatives.
  It can be shot before or after the negatives. The film's position in the
  holder doesn't matter: the blank supplies the falloff of the lens and light
  and the color of the base, and the base is even across the film. Shoot a new
  blank if you change the lens, extension, aperture, focus or light.
- Take several captures of each negative, a second or two apart, without
  touching the camera or film: a burst, or repeated presses from the phone
  app. The program averages them, which cuts sensor noise by the square root
  of the number of captures. Eight cut it to about a third. This matters most
  in the dense parts of the negative (skies and highlights), where few
  photons reach the sensor. Advance the film between negatives; that takes
  longer than the averaging gap, so the captures of different negatives stay
  apart.
- Frame the whole negative with a little rebate around it. On Micro Four
  Thirds that is a magnification of about 0.44 (a 39 x 29.5 mm field).
- Stop down more than you'd expect. Below 1:1 the film sees a smaller
  aperture than the f-number (f/11 at 0.44 is about f/36 as seen from the
  film), but a holder that doesn't hold the film flat needs the depth of
  field. Measure before deciding; see below.

The setup these rules came from, tested in November 2026: Panasonic GX85
(16 MP, no low-pass filter), Canon FL 50 mm f/3.5 Macro, 100 mm of Valoi
extension tubes (magnification 0.439), Valoi easy35 holder, battery-powered
DC light.

- Aperture: f/11. Fine detail measured 30 to 50% higher than at f/8, and
  higher still compared with f/3.5. The holder rocks about 0.75 mm in its
  seat and its film path bows the frame, so depth of field matters more than
  diffraction. Between f/3.5 and about f/5 the light doesn't change with the
  aperture (the light source's cone, not the iris, limits it); from f/5.6 down
  the iris takes over.
- Holder: a shim of about 0.75 mm (an old gift card) in the gap on the side of
  the insert nearer the lens takes up the play.
- Focus: at f/5.6 and 10x on the grain, at a point about a third of the way in
  from the left edge (as seen on the camera's screen), then stop down to f/11
  without touching the ring. The bow leaves the edges about one focus step
  farther than the center; focusing off-center splits the error.
- Exposure: 1/60 s at f/11 with the light freshly charged put the base at
  about 90% of full scale. The light dims as its battery runs down, so check
  the blank's level now and then.
- Eight captures per negative, triggered from the phone (Panasonic Image App,
  connected through the home network).

To check a holder for tilt and bow, shoot a focus series on the dark (fogged)
end of a leader: two frames at each of a dozen focus positions, stepped in one
direction, exposed so the leader reaches at least 15% of full scale.
<!-- invert-film-scans:capture:end -->

## Usage

<!-- invert-film-scans:usage:start -->
```bash
invert-film-scans [options] --blank BLANK.RW2 NEGATIVE.RW2 ...
```

Captures taken within a few seconds of each other are treated as repeats of
one negative and averaged. For each negative, the program writes
`NAME_inv.tif`, named after its first capture (16-bit, with an Adobe RGB
(1998) compatible profile, deflate compressed), next to the raw files or in
`--output-dir`, and copies the first capture's metadata into it.

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
- `--group-gap SECONDS`: captures taken within this many seconds of the
  previous one are averaged. Default: 3. `0` turns averaging off. Reading the
  capture times needs exiftool.
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

The blank frame is skipped if it also appears in the list of negatives, so
`invert-film-scans -b _1010756.RW2 *.RW2` works.

Before a capture is added to an average, the program checks that it lines up
with the first capture of its group. If the film moved more than half a pixel,
or the capture shows a different picture, it starts a new output of its own
and the program says so.
<!-- invert-film-scans:usage:end -->

## What the messages mean

<!-- invert-film-scans:messages:start -->
For each negative the program prints the output name, how many captures were
averaged, the black and white points (density above base, red, green, blue),
and two checks of the blank frame against the negative's rebate:

- **base**: rebate level divided by the blank frame's level, per channel. Near
  1.00 when the blank was shot in the same session at the same shutter speed.
  A different session or shutter shows up here as a few percent; that doesn't
  affect the result.
- **rebate varies**: how much the rebate still varies along one edge of the
  frame after the falloff correction, in stops, for the worst edge. Strips
  along different edges can differ by a fixed amount (the gap between frames,
  the strip beside the holes); that is the film, so only variation along a
  strip counts. Above 0.05 stop the program warns: the blank's falloff doesn't
  fit this frame, usually because the lens, extension or light changed. Shoot
  a new blank.

If a frame has no clear rebate, these checks are skipped.

The program also warns if the blank frame's brightest film area is within 5%
of clipping in any channel.
<!-- invert-film-scans:messages:end -->

## How it works

<!-- invert-film-scans:method:start -->
1. Each raw file is decoded to linear camera RGB, with no color matrix, white
   balance or tone curve. Densities must come from the sensor's own channels;
   a color matrix mixes the channels before the log and distorts hues after
   inversion. Repeated captures of one negative are checked for movement
   (phase correlation, refined to about 0.05 pixel) and averaged.
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

2026-11-16: Version 0.2. Averages repeated captures; the rebate check looks
at variation along each edge. Tested on Panasonic GX85 captures of 35 mm C-41
film.

### License

Released under the MIT license. See [LICENSE.md](LICENSE.md).
