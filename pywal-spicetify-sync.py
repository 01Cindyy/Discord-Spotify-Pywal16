#!/usr/bin/env python3
"""Sync Spotify's spicetify theme to the current pywal 16-colour scheme.

Portable version: instead of assuming spicetify lives in ~/.spicetify and its
config in ~/.config/spicetify, this locates the spicetify binary (PATH first,
then the usual install spots) and asks spicetify itself where its config
folder is, falling back to $SPICETIFY_CONFIG / $XDG_CONFIG_HOME / ~/.config.
"""
import colorsys
import configparser
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

WAL_COLORS = Path.home() / ".cache" / "wal" / "colors.json"
THEME_NAME = "Pywal"
SCHEME_NAME = "pywal"

# Extends the elevated chrome tone (--spice-sidebar) to the top bar and the
# right now-playing panel, which the base spice vars don't cover, so all four
# surrounding bars share the same frame colour. Uses stable Root__ containers.
USER_CSS = """\
/* managed by pywal-spicetify-sync — chrome depth for top bar + right panel */
.Root__globalNav,
.Root__top-bar,
.Root__right-sidebar {
    background-color: var(--spice-sidebar) !important;
}
"""

# How much to bump accent colours. pywal often generates muted palettes;
# these push the accent/semantic slots toward something punchier without
# touching the background surfaces (which must stay cohesive).
#   ACCENT_SRC — palette slot to anchor the accent on; when that slot is empty
#                (partial palettes like Noctalia's leave color4 blank) the most
#                colourful populated slot is used instead
#   SAT_BOOST  — multiplies saturation (1.0 = unchanged)
#   MIN_SAT    — floor saturation so near-grey accents still get colour
#   MAX_SAT    — ceiling saturation so already-vivid palettes don't scream
#   LIGHT_GAIN — nudges very dark accents brighter so they read on dark bg
ACCENT_SRC = "color4"
SAT_BOOST = 1.2
MIN_SAT = 0.3
MAX_SAT = 0.72
LIGHT_GAIN = 0.08


def find_spicetify():
    """Locate the spicetify binary: PATH first, then common install locations
    (manual install, ~/.local/bin, distro packages, /opt)."""
    exe = shutil.which("spicetify")
    if exe:
        return Path(exe)
    for cand in (
        Path.home() / ".spicetify" / "spicetify",
        Path.home() / ".local" / "bin" / "spicetify",
        Path("/usr/local/bin/spicetify"),
        Path("/usr/bin/spicetify"),
        Path("/opt/spicetify/spicetify"),
        Path("/opt/spicetify-cli/spicetify"),
    ):
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    sys.exit(
        "pywal-spicetify-sync: spicetify binary not found on PATH or in the "
        "usual install locations — install spicetify or add it to PATH."
    )


def find_theme_dir(spicetify):
    """Locate spicetify's config folder (the one holding Themes/ and
    config-xpui.ini) and return <config>/Themes/Pywal.

    spicetify knows best where its own config lives, so ask it first:
    `spicetify path userdata` (newer versions) prints the config folder, and
    `spicetify -c` (all versions) prints the config-xpui.ini path. Only if
    both fail do we fall back to the standard locations."""
    for args, is_file in ((["path", "userdata"], False), (["-c"], True)):
        try:
            out = subprocess.run(
                [str(spicetify), *args],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        p = Path(out)
        if is_file:
            p = p.parent
        if p.is_dir():
            return p / "Themes" / THEME_NAME

    fallbacks = []
    if os.environ.get("SPICETIFY_CONFIG"):
        fallbacks.append(Path(os.environ["SPICETIFY_CONFIG"]))
    if os.environ.get("XDG_CONFIG_HOME"):
        fallbacks.append(Path(os.environ["XDG_CONFIG_HOME"]) / "spicetify")
    fallbacks.append(Path.home() / ".config" / "spicetify")
    for cand in fallbacks:
        if cand.is_dir():
            return cand / "Themes" / THEME_NAME
    sys.exit(
        "pywal-spicetify-sync: could not locate spicetify's config folder — "
        "run `spicetify` once so it creates its config, or set "
        "$SPICETIFY_CONFIG to the folder containing config-xpui.ini."
    )


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "".join(f"{max(0, min(255, c)):02x}" for c in rgb)


def mix(hex_a, hex_b, amount):
    """Blend hex_a toward hex_b by `amount` (0-1)."""
    a, b = hex_to_rgb(hex_a), hex_to_rgb(hex_b)
    return rgb_to_hex(tuple(round(a[i] + (b[i] - a[i]) * amount) for i in range(3)))


def boost(hex_c):
    """Make an accent colour bolder: raise saturation (with a floor) and
    lift very dark colours slightly so they stand out on a dark background."""
    r, g, b = (v / 255 for v in hex_to_rgb(hex_c))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    s = max(MIN_SAT, min(MAX_SAT, s * SAT_BOOST))
    if l < 0.5:
        l = min(0.6, l + LIGHT_GAIN)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return rgb_to_hex((round(r * 255), round(g * 255), round(b * 255)))


def _is_hex(v):
    """True if v is a '#rrggbb' / 'rrggbb' colour string (not '' or None)."""
    if not isinstance(v, str):
        return False
    s = v.lstrip("#")
    return len(s) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in s)


def colourfulness(hex_c):
    """Saturation weighted toward mid-lightness — used to auto-pick an accent."""
    r, g, b = (v / 255 for v in hex_to_rgb(hex_c))
    _, l, s = colorsys.rgb_to_hls(r, g, b)
    return s * (1 - abs(2 * l - 1))


def load_palette(colors):
    """Return (colors, background, foreground, accent), completing a PARTIAL
    palette so the rest of the theming always has valid values to work with.

    Real pywal caches fill all 16 colour slots plus a `special` block. Some
    generators export far less — Noctalia (Material You) is the motivating case:
    it writes color0/color15 and a couple of accent tones, leaves color1/2/4/6/8…
    as empty strings, and omits `special` entirely. Rather than crash deep in the
    colour maths on a blank slot, resolve and backfill everything here:
      * background = special.background, else color0
      * foreground = special.foreground, else color15, else color7
      * accent     = the ACCENT_SRC slot when it holds a real colour, otherwise
                     the most colourful populated slot (ignoring the structural
                     background/grey/foreground slots)
      * any empty/invalid colorN is filled in — accent slots inherit the accent,
        the grey slots (7, 8) a fg/bg mix — so c["colorN"] is always valid below.
    On a full pywal cache nothing needs filling, so this passes through unchanged
    and the accent stays ACCENT_SRC exactly as before."""
    c_raw = colors.get("colors") or {}
    if not c_raw:
        sys.exit("pywal colors.json has no `colors` block — not a valid palette.")
    special = colors.get("special") or {}

    bg = special.get("background") if _is_hex(special.get("background")) else None
    bg = bg or (c_raw["color0"] if _is_hex(c_raw.get("color0")) else None)
    fg = special.get("foreground") if _is_hex(special.get("foreground")) else None
    fg = fg or next((c_raw[k] for k in ("color15", "color7") if _is_hex(c_raw.get(k))), None)
    if not bg or not fg:
        sys.exit("pywal colors.json has no usable background/foreground "
                 "(special block or color0/color15) — is it a valid palette?")

    # color0/7/8/15 carry the background, greys and foreground, not accent hues.
    structural = {"color0", "color7", "color8", "color15"}
    accent = c_raw.get(ACCENT_SRC) if _is_hex(c_raw.get(ACCENT_SRC)) else None
    if accent is None:
        cand = [v for k, v in c_raw.items()
                if k.startswith("color") and k not in structural and _is_hex(v)]
        accent = max(cand, key=colourfulness) if cand else mix(fg, bg, 0.6)

    grey = c_raw["color8"] if _is_hex(c_raw.get("color8")) else mix(fg, bg, 0.45)
    c = {}
    for i in range(16):
        k = f"color{i}"
        if _is_hex(c_raw.get(k)):
            c[k] = c_raw[k]
        elif i == 0:
            c[k] = bg
        elif i in (7, 8):
            c[k] = grey
        elif i == 15:
            c[k] = fg
        else:
            c[k] = accent
    return c, bg, fg, accent


def build_scheme(colors):
    c, bg, fg, accent_src = load_palette(colors)

    # Structural surfaces are derived from the background so they stay
    # cohesive regardless of how saturated the generated palette is.
    # The blend amounts set how far each surface sits from the base
    # background toward the foreground — larger gaps == more visible
    # separation between stacked UI layers.
    main = bg
    main_elevated = mix(bg, fg, 0.09)
    card = mix(bg, fg, 0.15)
    highlight = mix(bg, fg, 0.21)
    highlight_elevated = mix(bg, fg, 0.27)
    shadow = mix(bg, "#000000", 0.55)
    selected_row = mix(bg, fg, 0.24)

    # The surrounding chrome (left nav, bottom player, top bar, right panel)
    # shares one tone that sits slightly DARKER than the main content, so the
    # bars recede as a distinct frame. sidebar/player carry it via the standard
    # spice vars; user.css reuses --spice-sidebar for the top bar and right panel.
    chrome = mix(bg, "#000000", 0.32)

    # Semantic slots pull from the (completed) palette. The accent is ACCENT_SRC,
    # or the most colourful populated slot when that's blank (partial palettes),
    # boosted for punch. button-active is a lighter shade of the same accent so
    # the normal/hover pair stays one hue. color1/color2 are pywal's red/green
    # error/notification slots (they fall back to the accent on partial palettes).
    accent = boost(accent_src)
    accent_hover = mix(accent, fg, 0.22)
    return {
        "text": fg,
        "subtext": c["color8"],
        "main": main,
        "main-elevated": main_elevated,
        "highlight": highlight,
        "highlight-elevated": highlight_elevated,
        "sidebar": chrome,
        "player": chrome,
        "card": card,
        "shadow": shadow,
        "selected-row": selected_row,
        "button": accent,
        "button-active": accent_hover,
        "button-disabled": c["color8"],
        "tab-active": accent,
        "notification": boost(c["color2"]),
        "notification-error": boost(c["color1"]),
        "misc": c["color8"],
    }


def write_theme(scheme, theme_dir):
    color_ini = theme_dir / "color.ini"
    ini = configparser.ConfigParser()
    ini.optionxform = str  # preserve key case
    if color_ini.exists():
        ini.read(color_ini)
    ini[SCHEME_NAME] = {k: v.lstrip("#") for k, v in scheme.items()}
    theme_dir.mkdir(parents=True, exist_ok=True)
    with open(color_ini, "w") as f:
        ini.write(f)
    (theme_dir / "user.css").write_text(USER_CSS)
    return color_ini


def run_spicetify(spicetify, *args):
    subprocess.run([str(spicetify), *args], check=True)


def main():
    if not WAL_COLORS.exists():
        sys.exit(f"pywal colors not found at {WAL_COLORS} — run `wal` first.")

    spicetify = find_spicetify()
    theme_dir = find_theme_dir(spicetify)

    colors = json.loads(WAL_COLORS.read_text())
    scheme = build_scheme(colors)
    color_ini = write_theme(scheme, theme_dir)

    run_spicetify(spicetify, "config", "current_theme", THEME_NAME,
                  "color_scheme", SCHEME_NAME)
    run_spicetify(spicetify, "apply")
    print(f"Applied pywal colours to spicetify ({color_ini}).")


if __name__ == "__main__":
    main()
