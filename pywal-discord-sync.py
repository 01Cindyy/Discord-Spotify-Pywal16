#!/usr/bin/env python3
"""Sync Discord (Vesktop/Vencord) to the current pywal 16-colour scheme.

Reads ~/.cache/wal/colors.json and writes a managed Vencord theme,
<vencord-config>/themes/pywal.theme.css, that reskins Discord by overriding
its CSS custom properties. It also makes sure that theme is enabled (and loads
last) in the client's settings. The client watches the themes folder, so once
the theme is enabled, re-running this while Discord is open reskins it live —
no restart needed after the first enable.

Portable version: instead of assuming ~/.config/vesktop, this locates the
active Vencord config folder itself — Vesktop or Vencord-on-Discord, native or
flatpak — and can be pinned with $PYWAL_DISCORD_DIR if it guesses wrong.

Companion to pywal-spicetify-sync.py; same accent philosophy.
"""
import colorsys
import json
import os
import sys
from pathlib import Path

WAL_COLORS = Path.home() / ".cache" / "wal" / "colors.json"
THEME_NAME = "pywal.theme.css"

# --- accent tuning (same idea as pywal-spicetify-sync) -----------------------
# pywal often yields muted palettes; nudge the single Discord accent (primary
# buttons, links, mentions, unread pills) toward something with life, but keep
# a ceiling so a vivid wallpaper doesn't produce a screaming accent.
#   ACCENT_SRC  "auto" = pick the most colourful pywal hue; or pin e.g. "color4"
#   SAT_BOOST   multiplies saturation (1.0 = unchanged)
#   MIN_SAT     floor so near-grey accents still get some colour
#   MAX_SAT     ceiling so already-vivid palettes stay restrained
#   LIGHT_GAIN  lifts very dark accents so they read on the dark surfaces
# These match pywal-spicetify-sync exactly, so Discord's accent == Spotify's.
ACCENT_SRC = "color4"
SAT_BOOST = 1.2
MIN_SAT = 0.30
MAX_SAT = 0.72
LIGHT_GAIN = 0.08

# Surfaces are built at FIXED dark HSL lightnesses rather than derived from the
# wallpaper's own background lightness, so the theme stays consistently dark no
# matter how light/washed-out pywal's palette is. Two independent knobs:
#   DARKNESS     scales every surface lightness — <1.0 darker, >1.0 lighter.
#   SURFACE_SAT  HSL saturation of every surface — higher = richer colour, lower
#                = greyer. (Very dark colours can only hold so much chroma, so to
#                get MORE colour without going lighter, raise this toward ~0.8.)
# Surfaces take their HUE from the palette background (accent hue if bg is grey).
DARKNESS = 1.0
SURFACE_SAT = 0.62

BLACK = "#000000"
WHITE = "#ffffff"


def find_vencord_dir():
    """Locate the active Vencord config folder (the one holding themes/ and
    settings/settings.json). Checks Vesktop and Vencord-on-Discord, both native
    and flatpak. When more than one exists, the one whose settings/settings.json
    was modified most recently wins — the client rewrites that file in normal
    use, so it tracks which install is actually active and a stale leftover
    folder loses. Set $PYWAL_DISCORD_DIR to override the autodetection."""
    env = os.environ.get("PYWAL_DISCORD_DIR")
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p
        sys.exit(f"pywal-discord-sync: $PYWAL_DISCORD_DIR={p} does not exist")

    home = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    candidates = []
    for cand in (
        xdg / "vesktop",
        home / ".config" / "vesktop",
        home / ".var" / "app" / "dev.vencord.Vesktop" / "config" / "vesktop",
        xdg / "Vencord",
        home / ".config" / "Vencord",
        home / ".var" / "app" / "com.discordapp.Discord" / "config" / "Vencord",
    ):
        if cand.is_dir() and cand not in candidates:
            candidates.append(cand)
    if not candidates:
        sys.exit(
            "pywal-discord-sync: no Vesktop/Vencord config folder found "
            "(looked under ~/.config, $XDG_CONFIG_HOME and the flatpak "
            "~/.var/app locations) — set $PYWAL_DISCORD_DIR to your Vencord "
            "config folder."
        )

    def freshness(d):
        s = d / "settings" / "settings.json"
        return s.stat().st_mtime if s.is_file() else -1.0

    # Ties (e.g. no settings.json anywhere) fall back to candidate order,
    # which prefers Vesktop.
    return max(candidates, key=freshness)


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def mix(hex_a, hex_b, amount):
    """Blend hex_a toward hex_b by `amount` (0-1)."""
    a, b = hex_to_rgb(hex_a), hex_to_rgb(hex_b)
    return rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * amount for i in range(3)))


def rgba(hex_c, alpha):
    """Translucent colour, for the *-mod-* / interactive overlay tokens: these
    sit on top of a surface as hover/selected tints, so they must let the
    surface beneath show through rather than fully cover it."""
    r, g, b = hex_to_rgb(hex_c)
    return f"rgba({r}, {g}, {b}, {alpha})"


def surface(hue_hex, lightness, sat):
    """A theme surface at an explicit dark `lightness`, taking hue from the
    palette and a fixed `sat`. Building surfaces from fixed lightness (rather
    than from the wallpaper's own bg lightness) keeps the UI consistently dark
    and tinted no matter how light or washed-out the generated palette is."""
    h, _, _ = colorsys.rgb_to_hls(*(v / 255 for v in hex_to_rgb(hue_hex)))
    r, g, b = colorsys.hls_to_rgb(h, min(1, max(0, lightness)), min(1, max(0, sat)))
    return rgb_to_hex((r * 255, g * 255, b * 255))


def colourfulness(hex_c):
    """Saturation weighted toward mid-lightness — used to auto-pick an accent."""
    r, g, b = (v / 255 for v in hex_to_rgb(hex_c))
    _, l, s = colorsys.rgb_to_hls(r, g, b)
    return s * (1 - abs(2 * l - 1))


def boost(hex_c):
    """Identical to pywal-spicetify-sync's boost so the accent matches Spotify:
    raise saturation (with a floor/ceiling) and lift very dark accents a touch."""
    r, g, b = (v / 255 for v in hex_to_rgb(hex_c))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    s = max(MIN_SAT, min(MAX_SAT, s * SAT_BOOST))
    if l < 0.5:
        l = min(0.6, l + LIGHT_GAIN)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return rgb_to_hex((r * 255, g * 255, b * 255))


def pick_accent(colors):
    c = colors["colors"]
    if ACCENT_SRC != "auto" and ACCENT_SRC in c:
        return c[ACCENT_SRC]
    keys = [f"color{i}" for i in (1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14)]
    return max((c[k] for k in keys if k in c), key=colourfulness)


def brand_scale(accent):
    """Discord's brand ramp: <500 tint toward white, >500 shade toward black,
    500 = the accent itself. Emitted for both --brand-* and --brand-experiment-*."""
    stops = [
        60, 100, 130, 160, 200, 230, 260, 300, 330, 345, 360, 400, 430, 460,
        500, 530, 560, 600, 630, 660, 700, 730, 760, 800, 830, 860, 900,
    ]
    out = {}
    for n in stops:
        if n <= 500:
            out[n] = mix(accent, WHITE, (500 - n) / 500 * 0.85)
        else:
            out[n] = mix(accent, BLACK, (n - 500) / 400 * 0.60)
    return out


def build_css(colors):
    special, c = colors["special"], colors["colors"]
    bg, fg = special["background"], special["foreground"]
    muted = c.get("color8", mix(fg, bg, 0.50))
    accent = boost(pick_accent(colors))     # buttons/links/mentions/unread

    # Tint hue comes from the palette background, unless it's essentially
    # greyscale (unreliable hue) — then borrow the accent's hue.
    _, _, bg_sat = colorsys.rgb_to_hls(*(v / 255 for v in hex_to_rgb(bg)))
    hue = bg if bg_sat >= 0.08 else accent

    # Fixed dark lightness ladder (HSL L), darkest -> lightest, scaled by
    # DARKNESS. Fixed values keep the theme uniformly dark whatever the
    # wallpaper's brightness; SURFACE_SAT sets how colourful vs washed-out.
    # `chrome` (all bars) stays darkest, the chat sits just above it.
    chrome        = surface(hue, 0.030 * DARKNESS, SURFACE_SAT)  # every bar/frame
    main          = surface(hue, 0.050 * DARKNESS, SURFACE_SAT)  # chat content
    main_elevated = surface(hue, 0.070 * DARKNESS, SURFACE_SAT)  # inputs, raised
    card          = surface(hue, 0.092 * DARKNESS, SURFACE_SAT)  # cards, popouts, DM profile
    highlight     = surface(hue, 0.116 * DARKNESS, SURFACE_SAT)  # menus, tooltips

    link = mix(accent, fg, 0.40)            # lifted for readable link text
    mention = mix(bg, accent, 0.20)
    mention_hover = mix(bg, accent, 0.28)
    scroll = surface(hue, 0.150 * DARKNESS, SURFACE_SAT * 0.8)

    brand = "\n".join(
        f"  --brand-{n}: {v} !important;\n  --brand-experiment-{n}: {v} !important;"
        for n, v in brand_scale(accent).items()
    )

    return f"""\
/**
 * @name Pywal
 * @description Auto-generated from the current pywal 16-colour scheme.
 *   Managed by pywal-discord-sync — edits here are overwritten on every wallpaper change.
 * @author pywal-discord-sync
 * @version 1.0.0
 */

/* Applied to every Discord theme class (including .theme-light) so Discord
   always follows pywal regardless of its own light/dark toggle. Drop
   .theme-light below if you want to keep Discord's native light mode. */
:root,
.theme-dark,
.theme-darker,
.theme-midnight,
.theme-light,
.visual-refresh {{
  /* ---- base surfaces (legacy vars) ---- */
  --background-primary: {main} !important;
  --background-secondary: {chrome} !important;
  --background-secondary-alt: {chrome} !important;
  --background-tertiary: {chrome} !important;
  --background-floating: {card} !important;
  --background-nested-floating: {highlight} !important;
  --background-accent: {accent} !important;
  --background-message-hover: {rgba(fg, 0.03)} !important;
  --background-modifier-hover: {rgba(fg, 0.04)} !important;
  --background-modifier-active: {rgba(fg, 0.07)} !important;
  --background-modifier-selected: {rgba(fg, 0.09)} !important;
  --background-modifier-accent: {rgba(fg, 0.06)} !important;
  --background-mentioned: {mention} !important;
  --background-mentioned-hover: {mention_hover} !important;
  --channeltextarea-background: {main_elevated} !important;
  --input-background: {main_elevated} !important;
  --deprecated-card-bg: {card} !important;
  --deprecated-quickswitcher-input-background: {main_elevated} !important;
  --activity-card-background: {card} !important;

  /* ---- surfaces (visual-refresh primitives — the CURRENT Discord UI) ----
     base-*  = structural frame; all set to `chrome` so every bar is the same
               dark tone as Spotify's, with the chat (base-low) at `main`.
     surface-* = raised elements (inputs, popouts, modals) above the base.
     mod-* / interactive-background-* = translucent hover/selected overlays. */
  --background-base-lowest: {chrome} !important;
  --background-base-lower: {chrome} !important;
  --background-base-low: {main} !important;
  --background-surface-high: {main_elevated} !important;
  --background-surface-higher: {card} !important;
  --background-surface-highest: {highlight} !important;
  --background-mod-subtle: {rgba(fg, 0.03)} !important;
  --background-mod-faint: {rgba(fg, 0.04)} !important;
  --background-mod-normal: {rgba(fg, 0.06)} !important;
  --background-mod-muted: {rgba(fg, 0.05)} !important;
  --background-mod-strong: {rgba(fg, 0.10)} !important;
  --interactive-background-hover: {rgba(fg, 0.05)} !important;
  --interactive-background-active: {rgba(fg, 0.08)} !important;
  --interactive-background-selected: {rgba(fg, 0.10)} !important;
  --card-background-default: {main_elevated} !important;
  --card-background-secondary: {card} !important;
  --modal-background: {card} !important;
  --modal-footer-background: {chrome} !important;
  --custom-channel-members-bg: {chrome} !important;

  /* ---- profiles (popout body + banner fallback) ---- */
  --profile-body-background-color: {card} !important;
  --profile-gradient-primary-color: {chrome} !important;
  --profile-gradient-secondary-color: {main_elevated} !important;

  /* ---- text ---- */
  --text-normal: {fg} !important;
  --text-default: {fg} !important;
  --text-primary: {fg} !important;
  --text-secondary: {mix(fg, bg, 0.30)} !important;
  --text-tertiary: {mix(fg, bg, 0.45)} !important;
  --text-muted: {muted} !important;
  --text-faint: {mix(fg, bg, 0.55)} !important;
  --header-primary: {mix(fg, WHITE, 0.10)} !important;
  --header-secondary: {mix(fg, bg, 0.32)} !important;
  --interactive-normal: {mix(fg, bg, 0.26)} !important;
  --interactive-hover: {fg} !important;
  --interactive-active: {mix(fg, WHITE, 0.12)} !important;
  --interactive-muted: {mix(fg, bg, 0.52)} !important;
  --channels-default: {mix(fg, bg, 0.30)} !important;
  --channel-icon: {mix(fg, bg, 0.40)} !important;
  --white-500: {fg} !important;
  --text-link: {link} !important;
  --text-link-low-saturation: {link} !important;
  --text-brand: {link} !important;

  /* ---- accent / brand ---- */
  --brand-experiment: {accent} !important;
  --brand-500: {accent} !important;
  --brand-560: {mix(accent, BLACK, 0.10)} !important;
  --control-brand-foreground: {link} !important;
  --mention-foreground: {link} !important;
  --mention-background: {mention} !important;
  --focus-primary: {accent} !important;
{brand}

  /* ---- scrollbars ---- */
  --scrollbar-thin-thumb: {scroll} !important;
  --scrollbar-thin-track: transparent !important;
  --scrollbar-auto-thumb: {scroll} !important;
  --scrollbar-auto-track: {main} !important;
  --scrollbar-auto-scrollbar-color-thumb: {scroll} !important;
  --scrollbar-auto-scrollbar-color-track: {main} !important;
}}

/* Surfaces that paint their own background via class rather than reading a
   variable — matched by class-name substrings because Discord appends a build
   hash to each class (e.g. channelTextArea_ab12cd). This is what finally themes
   the message box and the profile popouts. */
[class*="channelTextArea"] [class*="themedBackground"] {{
  background-color: {main_elevated} !important;
}}
[class*="profileCard"],
[class*="accountProfileCard"],
[class*="userProfileOuter"],
[class*="userProfileInner"],
[class*="userPopoutOuter"],
[class*="userPopoutInner"],
[class*="userProfileSidebar"],
[class*="userProfilePanel"],
[class*="profilePanel"],
[class*="profileSidebar"],
[class*="userProfileModalInner"],
[class*="biteSize"] {{
  background-color: {card} !important;
}}
/* The DM profile card's colour is a per-user gradient painted on the profile
   "theme" container, which overrides the --profile-* vars. The `background`
   shorthand flattens that gradient (image -> none) so every profile follows
   pywal instead of the viewed user's own colours. */
[class*="themeContainer"] {{
  background: {card} !important;
}}
[class*="bannerContainer"] {{
  background-color: {chrome} !important;
}}
"""


def ensure_enabled(settings):
    """Make sure pywal.theme.css is in enabledThemes and loads last. Best-effort:
    the client may rewrite settings.json, but this self-heals on the next run."""
    try:
        data = json.loads(settings.read_text())
    except FileNotFoundError:
        return f"settings.json not found at {settings}; enable the Pywal theme manually"
    except Exception as e:  # noqa: BLE001 - never let this break the wal pipeline
        return f"could not read settings.json ({e}); enable the Pywal theme manually"

    themes = [t for t in data.get("enabledThemes", []) if t != THEME_NAME]
    was_present = len(themes) != len(data.get("enabledThemes", []))
    themes.append(THEME_NAME)  # last => wins over other enabled themes
    if themes == data.get("enabledThemes", []):
        return "already-enabled"
    data["enabledThemes"] = themes
    settings.write_text(json.dumps(data, indent=4))
    return "reordered" if was_present else "enabled"


def main():
    if not WAL_COLORS.exists():
        sys.exit(f"pywal-discord-sync: {WAL_COLORS} not found — run wal first")

    vencord_dir = find_vencord_dir()
    theme_file = vencord_dir / "themes" / THEME_NAME
    settings = vencord_dir / "settings" / "settings.json"

    colors = json.loads(WAL_COLORS.read_text())
    theme_file.parent.mkdir(parents=True, exist_ok=True)
    theme_file.write_text(build_css(colors))
    print(f"pywal-discord-sync: wrote {theme_file}")

    status = ensure_enabled(settings)
    if status == "enabled":
        print("pywal-discord-sync: enabled the Pywal theme — restart the Discord "
              "client once; after that it hot-reloads live on every wal change.")
    elif status not in ("already-enabled", "reordered"):
        print(f"pywal-discord-sync: note — {status}")


if __name__ == "__main__":
    main()
