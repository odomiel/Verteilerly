# Verteilerly

*Deutsche Fassung: [README.md](README.md)*

Documentation for **LSA+ distribution frames** in telecommunications: cover
sheet, frame layout and strip sheets come out of **one data model** instead of
copied spreadsheets.

Whoever documents a frame with a spreadsheet keeps the same fact in several
places: the cable appears in the layout and on the strip sheet, the jumper at
both of its ends, the frame name in every title block. Verteilerly holds the
frame as a data model — bay, strip, pair, cable, jumper — and draws every
sheet from it. A jumper is **one** entry there that shows up at both ends; a
cable that is moved takes its wires and jumpers along.

The program runs on **Linux and Windows without installation**, saves into a
single project file and writes **PDF**, an **Excel workbook** and **CSV**. The
interface is German, English on request. Licence: **GPL-3.0-or-later**.

## What it does

**Create a frame.** Bays, strips per bay and pairs per strip — or from a
**frame template** that holds a recurring layout (two are supplied, your own
come from *Edit ▸ Save as template*). Strips are counted or carry letters; the
frame layout can be reversed where termination starts from the right.

**Terminate cables.** A cable lies on the strips in one or more sections, may
run past the end of a strip and may be **shortened** (a 6-pair cable with five
pairs terminated). The **cable type** brings the wire colours with it — the
usual colour sequences are supplied, your own types are a YAML file. In the
frame overview a cable can be **moved** with the mouse (copied with Ctrl), cut
and pasted; it takes colours, designations, remarks and jumpers along.
*Terminate remaining lines* takes on all shortened lines at once — where each
rest goes is up to you, prefilled with a proposal; a right click terminates a
single line at exactly the place clicked.

**Label the strips.** The strip view is the work surface: colour, designation,
jumper and remark per wire. A cell can be **split into two labelling fields**
(with a percentage), aligned, set bold or italic individually. Enter moves one
row down, Ctrl+C/X/V work on cells and blocks, and a click on a cable in the
layout jumps to its start.

**Jumper.** Targets are typed in the chosen notation (`3 2a`, `L3 2a`,
`L3-2a`) and kept at **both** ends. Besides targets the field accepts
**templates** — supplied are *direkt*, *defekt*, *12k*, and the list can be
changed. Everything else stays an error: a mistyped target should stand out.

**Lay out the sheets.** What stands on the sheets comes from the **project
data** (company, customer, installation and customer number, drawn, created,
revision, checked — plus freely named own fields); how it looks comes from the
**sheet template**: columns, margins, font sizes and the build of the title
block. Three templates are supplied, your own are a YAML file — or they come
out of the built-in **sheet template editor** with an immediate preview.
Before a template file is taken into use, *Tools* checks it and refreshes
outdated entries.

**Output.** The **preview** shows every sheet the way it will be printed
(zoomable up to true size). From it come a **PDF**, an **Excel workbook** in
the sheet layout together with data lists, and **CSV** lists for further
processing.

**A look for updates once a day** (*Settings*, switchable): the program asks
the public release list and says in the status bar when a newer version is
out. Nothing is downloaded, nothing is sent beyond the request; switched off
it **never** goes online. *Help ▸ Look for updates…* asks at the press of a
button and says in every case what came of it.

**And for everyday work.** Searching across the whole frame, undo and redo of
the last fifty steps, **opening read-only**, a light and a dark appearance,
backup and restore of all templates and settings, and a log that says what the
program did. It can be extended with your own Python modules.

## Installing

### Linux — AppImage

```bash
chmod +x Verteilerly-<version>-x86_64.AppImage
./Verteilerly-<version>-x86_64.AppImage
```

The image (about 40 MB) brings **Python 3.14 and Qt along**; all it asks for
is a glibc from 2.34 (Debian 12, Ubuntu 22.04 and newer). Nothing is
installed.

On first start the program puts its templates and settings into
`~/.config/Verteilerly`, and that is where it writes. Beyond that it reads a
folder `daten` **next to the image file**, and that one first — so Verteilerly
travels on a stick together with your own templates; where no user folder can
be written, it saves there as well.

```bash
./Verteilerly-<version>-x86_64.AppImage --selbsttest   # short report: version, paths, sample PDF
```

### Windows — .exe

A single file, startable without installation: `Verteilerly_<version>.exe`.
The basic equipment is inside it; on first start the program puts it into a
folder `daten` **next to** the file, where it can be changed. For the stick
there is the PortableApps edition with its launcher.

Project files (`.vtly`) are linked by *Tools ▸ Link project files…* at the
press of a button — for the signed-in user only, without elevated rights. What
is registered is the **launcher**, not the program behind it: that is why the
link survives an update. The plain `.exe` carries its version in its name —
where the registered file is gone after an update, the start carries the link
over by itself; where it is still there, the start only reports it and the
dialog offers *Renew the link*. Where someone has chosen “Open with ▸ Always use this
app”, that choice still wins — it cannot be set from outside.

### From the source tree

```bash
python3 -m venv --without-pip .venv                 # Debian: ensurepip is missing
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python3
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 -m verteilerly
```

What is needed is a current Python 3 — development and builds use **3.14** —
and the four packages from `requirements.txt`: PySide6 (interface), ReportLab
(PDF), openpyxl (Excel) and PyYAML (templates). The tests add pypdf, packaging
adds PyInstaller.

## Building

One call, two platforms — building always happens **on** the target platform,
PyInstaller packs the Python that calls it:

```bash
.venv/bin/python3 werkzeuge/bauen.py                 # AppImage (Linux) or .exe (Windows)
.venv/bin/python3 werkzeuge/bauen.py --sauber        # empty build and output folder first
.venv/bin/python3 werkzeuge/bauen.py --ohne-pruefung # without looking at PyPI
```

The result lands in `auslieferung/`. The first build of a day looks whether
there are newer versions of the dependencies or of the Python base and reports
them — it never aborts over that, and without a network it carries on.

**Linux** (`werkzeuge/appimage.py`): the base is a python-appimage with Python
3.14; the system libraries come from Debian bookworm instead of from the build
machine, so that the glibc floor stays the same. Qt is cut down to what the
program touches — that keeps it at 40 instead of 60 MB.

**Windows** (`build_windows.ps1` with `Verteilerly.spec`), on a Windows
machine:

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
```

The version is the release date (`year.month.day`, further builds of the same
day with `b2`, `b3` …). It is set from the git tags:

```bash
.venv/bin/python3 werkzeuge/release.py            # show the next version
.venv/bin/python3 werkzeuge/release.py --setzen   # write, commit, tag
```

A **release** is made from the built files. Where the repository is mirrored,
the mirror only carries branches and tags — releases and their attachments are
added by `werkzeuge/github_release.py`:

```bash
python3 werkzeuge/github_release.py --probe auslieferung/Verteilerly-*   # show first
python3 werkzeuge/github_release.py auslieferung/Verteilerly-*           # then create
```

It waits until the tag has arrived, creates the release (or takes an existing
one), uploads the files and verifies each by SHA256. The repository slug and
the token live **outside** the repository — in `$VERTEILERLY_GITHUB_SLUG` and
`$GITHUB_TOKEN` or as `github_repo` and `github_token` in the working folder;
the token only needs *Contents: Read and write*.

## Manual

The user manual is the documentation the program shows under *Help ▸
Documentation*. It is set as a PDF with:

```bash
.venv/bin/python3 werkzeuge/handbuch.py              # German and English
.venv/bin/python3 werkzeuge/handbuch.py --sprache en # one language only
```

The files land in `auslieferung/` — `Verteilerly-Handbuch-<version>.pdf` and
`Verteilerly-Manual-<version>.pdf`, with a title page, a table of contents and
page numbers.

## Tests

Checking is done with `unittest`, without a screen (the GUI tests run
offscreen). The whole suite takes about two minutes:

```bash
.venv/bin/python3 -m unittest discover -s tests -t .   # all tests
.venv/bin/python3 -m unittest tests.test_layout        # one file
```

## Licence

Large parts of this project were created with the help of AI (Claude Code).

Verteilerly is under the **GPL-3.0-or-later** (`LICENSE`). The bundled
components are under LGPL, BSD, MIT and PSF; their texts are in `lizenzen/`,
every source with its address in `lizenzen/QUELLEN.txt`. *Help ▸ About
Verteilerly* shows in the program what is currently loaded, with version and
licence.
