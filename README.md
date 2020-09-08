# Un-GameBoy

**Un-GameBoy** is an interactive tool to help with reverse-engineering
games for the Nintendo Game Boy and Game Boy Color.

Un-GameBoy is still under development; use it at your own risk. Until a
more stable release is cut, I cannot guarantee that your work won't be
lost because of some random bug or change at any time.

This project was inspired by [BadBoy] by daid. You should check it out!

### Contents:

* [Installation](#installation)
* [Basic Usage](#basic-usage)
* [F.A.Q.](#faq)
* [Roadmap](#roadmap)

## Installation

In its current state, Un-GameBoy does not have a clear installation
process; one may come later. If you know how to install Python and know
what a virtual environment is, you're good to go.

Install steps:

1. Make sure that you have Python 3.7 or above installed.
2. Download this code using `git clone` or whichever way you prefer.
3. Create a virtual environment, and activate it.
4. From the project's root directory (where `setup.py` is), run:
   ```
   python -m pip install .
   ```
5. Start the editor with:
   ```
   ungameboy <path_to_rom>
   ```

## Basic Usage

* `Ctrl-D`: Exit immediately (does not save automatically!)
* `:` (colon): Open command prompt
* `c`: enter cursor mode
* `Enter`: jump to the "destination" under the cursor position
* `u` (lowercase): un-do the last jump, go back to previous position
* `U` (uppercase): re-do the last jump after an un-do

When the prompt is active:

* `Enter`: run command, quits prompt if command is empty
* `Ctrl-C`: quit prompt
* `Tab`: auto-complete, works with commands, addresses and labels

Address inputs all accept the following forms:

* `$NNNN`/`0xNNNN`: Interprets the value as an address in the GB's
  memory space (e.g. `$fe00` is OAM). If that address space is banked,
  the bank is assumed unknown (which may not be allowed).
* `BB:NNNN`: Interprets the value as an offset within a ROM bank.
  Banks 1 and up start at `$4000`, only bank 0 uses `$0-3FFF`.
* `TYPE.BB:NNNN`: Fully qualified address. Type my be `ROM`, `VRAM`,
  `SRAM`, `WRAM`, `OAM`, `IOR` or `HRAM`. The bank number can be
  omitted if the bank in the given range is unambiguous (e.g bank 0
  of WRAM in `$C000-CFFF`)
* Any known label is considered a valid address.

Labels follow the [RGBDS] conventions: the period `.` is significant
and separates global labels from the local labels. Global labels must
be unique, while local labels only need to be unique within the scope
of a global label.

A few useful commands:

* `seek` (shortcut: `g`): go to a location
* `project save <name>`: save your progress, you can resume it later by
  starting the editor with `ungameboy -p <name>`

Here's a quick list of the commands that somewhat work:

* `context clear ADDR`
* `context set scalar ADDR`
* `context set bank ADDR N`
* `data create palette ADDR [LEN]`
* `data create rle ADDR`
* `data create simple ADDR LEN`
* `data create table ADDR ROWS STRUCTURE`
* `data delete ADDR`
* `inspect ADDR`
* `label auto ADDR`
* `label create ADDR NAME`
* `label delete NAME`
* `label rename NAME NAME`
* `xref auto ADDR`
* `xref clear ADDR`
* `xref declare call ORIG DEST`
* `xref declare jump ORIG DEST`
* `xref declare read ORIG DEST`
* `xref declare write ORIG DEST`

## F.A.Q.

**Q: Isn't there already radare2 for that?**

A: Yes. If you are already using [radare2], you should probably keep
doing so. This is more like a fun project for me.

**Q: Does this do things that r2 doesn't?**

A: In fact, yes! The biggest improvement is that Un-GameBoy is aware of
the Game Boy address space and how banking affects it. More generally,
I dropped (or am too lazy to add) most of r2's features that seemed
specifically designed for decompiling C/C++, and added tools that are
designed with the Game Boy in mind. Most is still WIP though.

**Q: Aren't you just creating your disassembly tool because you can't
figure out how to use radare2 properly?**

A: Yes.

## Roadmap

This is a project I'm working on for fun, but also improving along the
way as I progress on an ongoing disassembly project. So I'll be adding
features and making changes when I need them.

That being said, here are a few things I would like to add:

* [ ] Comments, both in-line and paragraphs
* [ ] ASCII-art arrows to illustrate relative jumps
* [ ] References and labels navigation window
* [ ] Support for various MBC configurations (currently MBC5 is assumed)
* [ ] Sections
* [ ] Configurable display options
* [ ] Support for special data blocks (jump tables, SGB packets, etc.)
* [ ] Dynamic help window (e.g instruction documentation)
* [ ] General UX improvements: Navigation HUD, quit confirmation, more
  intelligent auto-complete, dynamic display of shortcuts, etc.

---

Copyright ©2020 Xavier Villaneau,
distributed under the Mozilla Public License 2.0


[BadBoy]: https://github.com/daid/BadBoy
[radare2]: https://rada.re/n/radare2.html
[RGBDS]: https://github.com/rednex/rgbds
