# Pywal16 → Discord + Spotify

Theme **Spotify** (via [spicetify](https://spicetify.app)) and **Discord**
(via [Vencord](https://vencord.dev) or [Vesktop](https://github.com/Vencord/Vesktop))
from your wallpaper with [pywal16](https://github.com/eylles/pywal16).

One command — `walchange <wallpaper>` — generates the palette and reskins
both apps to match, live.

## Disclaimer

This is mainly a personal project and for my own use.
The code in this repo is also mainly written by claude.
This could very well be buggy or completely non funcitonal for some users, so please use at your *own* risk.
However feel free to use this and improve it yourself as you wish!

## Requirements

- For now this only works on Linux, in theory it should work on all distros but has only been tested on arch based distros for now.
- A pywal-style palette at `~/.cache/wal/colors.json`. Either:
  - **[pywal16](https://github.com/eylles/pywal16)** installed (`wal` on your
    PATH or in `~/.local/bin`) — needed for `walchange`, which runs `wal -i`; or
  - any tool that writes that file — e.g. [Noctalia](https://noctalia.dev)'s
    Material You export. Partial palettes (missing `special`, blank accent
    slots) are handled: the accent is taken from whatever colour slots are
    populated and the rest is derived. Use `walapply` for these (see below).
- **Spotify** with **spicetify** set up (for the Spotify half)
- **Discord** with **Vencord**, or **Vesktop** — native or flatpak (for the Discord half)

## Install

```sh
git clone https://github.com/01Cindyy/Discord-Spotify-Pywal16
cd Discord-Spotify-Pywal16
chmod +x install.sh
./install.sh
```

Run it as your normal user — it uses `sudo` only where it has to.
The installer asks what to set up:

| Choice        | Installs                              |
| ------------- | ------------------------------------- |
| `0` (default) | Both syncs                            |
| `1`           | Spotify (spicetify) sync only         |
| `2`           | Discord (Vesktop/Vencord) sync only   |

It then copies the scripts to `/usr/bin` (`pywal-spicetify-sync`,
`pywal-discord-sync`, `walchange`) and makes them executable, and takes the
one-time spicetify backup that `spicetify apply` requires. Re-run it any
time to update.

## Usage

```sh
walchange ~/Pictures/wallpaper.jpg
```

This:

1. runs `wal -i` on the image to build the 16-colour palette (wal also sets
   the wallpaper on setups it supports),
2. rebuilds and applies the spicetify `Pywal` theme (Spotify restarts itself),
3. rewrites the Vencord `pywal.theme.css` and makes sure it's enabled.

> **First Discord run only:** restart Discord/Vesktop once after your first
> `walchange` so the theme gets picked up. After that, every `walchange`
> re-themes it live — no restart.

Extra `wal` flags pass straight through:

```sh
walchange img.png --backend colorz
```
### Re-apply without a new wallpaper

`walapply` re-themes Spotify and Discord from the palette already in
`~/.cache/wal/colors.json` — it does **not** run `wal` or change your
wallpaper:

```sh
walapply
```

## How it finds your apps

Both sync scripts auto-detect where things live, so one install works across
system configs:

- **spicetify** — binary from `PATH` or the usual install spots
  (`~/.spicetify`, `~/.local/bin`, `/usr/bin`, `/opt/…`); config folder by
  asking spicetify itself, falling back to `$SPICETIFY_CONFIG` and
  `~/.config/spicetify`.
- **Discord** — checks Vesktop and Vencord config folders, native and
  flatpak. If more than one exists, the most recently **used** one wins
  (by `settings.json` modification time). Pin it manually if it ever guesses
  wrong:

  ```sh
  PYWAL_DISCORD_DIR=~/.config/vesktop walchange img.png
  ```

## Tweaking

Colour behaviour is tunable at the top of each installed script
(`/usr/bin/pywal-spicetify-sync`, `/usr/bin/pywal-discord-sync`):

- `SAT_BOOST`, `MIN_SAT`, `MAX_SAT`, `LIGHT_GAIN` — accent punchiness. The
  `MAX_SAT` ceiling is what actually tames loud accents on vivid wallpapers.
- Discord only: `DARKNESS` (scales how dark every surface is) and
  `SURFACE_SAT` (how colourful vs. grey the surfaces are — raise it toward
  ~0.8 for more colour without getting lighter).

Both scripts anchor the accent on pywal's `color4` so Spotify and Discord end
up with the *same* accent colour.

**Note:** other enabled Vencord themes that force their own colours 
load alongside and can override the pywal theme — disable them
if Discord doesn't change.

## Uninstall

```sh
./uninstall.sh
```

Removes the installed commands from `/usr/bin`, then asks whether to also
delete the generated theme files (the spicetify `Pywal` theme folder and the
Vencord `pywal.theme.css`, de-registering it from your client's
`settings.json`).

By hand instead:

```sh
sudo rm /usr/bin/{pywal-spicetify-sync,pywal-discord-sync,walchange,walapply}
```
