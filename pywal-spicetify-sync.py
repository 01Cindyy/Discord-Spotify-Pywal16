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
#   SAT_BOOST  — multiplies saturation (1.0 = unchanged)
#   MIN_SAT    — floor saturation so near-grey accents still get colour
#   MAX_SAT    — ceiling saturation so already-vivid palettes don't scream
#   LIGHT_GAIN — nudges very dark accents brighter so they read on dark bg
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


def load_palette(colors):
    """Return (colors_dict, background, foreground), tolerating a colors.json
    that omits the `special` block (some pywal-compatible generators, and some
    restored/partial caches, do) by falling back to the 16-colour palette:
    color0 is the background, color15 (or color7) the foreground — which is what
    pywal's own `special` block mirrors anyway."""
    c = colors.get("colors") or {}
    if not c:
        sys.exit("pywal colors.json has no `colors` block — not a valid palette.")
    special = colors.get("special") or {}
    bg = special.get("background") or c.get("color0")
    fg = special.get("foreground") or c.get("color15") or c.get("color7")
    if not bg or not fg:
        sys.exit("pywal colors.json is missing background/foreground and has no "
                 "color0/color15 to fall back to — is it a valid pywal palette?")
    return c, bg, fg


def build_scheme(colors):
    c, bg, fg = load_palette(colors)

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

    # Semantic slots pull from the 16-colour palette. color4 is the accent
    # (boosted for punch); button-active is a lighter shade of that same
    # accent so the normal/hover pair stays one consistent hue. color1/color2
    # map to pywal's red/green slots for error/notification. Change color4
    # below if you'd rather anchor the accent on a different slot.
    accent = boost(c["color4"])
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
