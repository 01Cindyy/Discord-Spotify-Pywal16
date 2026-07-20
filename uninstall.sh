#!/usr/bin/env bash
# Uninstaller for Pywal16-Discord-Spotify. Removes the commands install.sh put
# in /usr/bin, and can optionally delete the generated theme files.
#
# Run from the repo as your NORMAL user (it elevates only where needed):
#     ./uninstall.sh
set -euo pipefail

BIN_DIR="/usr/bin"
COMMANDS=(pywal-spicetify-sync pywal-discord-sync walchange walapply)

# -------------------------------------------------------------------- sudo --
SUDO=""
if [[ $EUID -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo "error: removing from $BIN_DIR needs root — install sudo or run as root." >&2
        exit 1
    fi
fi

# --------------------------------------------------------- remove commands --
echo "Removing installed commands from $BIN_DIR:"
removed=0
for cmd in "${COMMANDS[@]}"; do
    if [[ -e "$BIN_DIR/$cmd" ]]; then
        $SUDO rm -f "$BIN_DIR/$cmd"
        echo "  removed $BIN_DIR/$cmd"
        removed=1
    fi
done
if [[ $removed -eq 0 ]]; then
    echo "  (nothing to remove)"
fi

# -------------------------------------------------- optional theme cleanup --
echo
read -rp "Also delete the generated theme files? [y/N]: " yn
if [[ "${yn:-N}" =~ ^[Yy]$ ]]; then
    echo
    # Spotify: <spicetify-config>/Themes/Pywal — check the same spots the
    # sync script's fallback uses.
    for base in "${SPICETIFY_CONFIG:-}" \
                "${XDG_CONFIG_HOME:-$HOME/.config}/spicetify" \
                "$HOME/.config/spicetify"; do
        [[ -n "$base" ]] || continue
        theme="$base/Themes/Pywal"
        if [[ -d "$theme" ]]; then
            rm -rf "$theme"
            echo "  removed $theme"
        fi
    done

    # Discord: <vencord-dir>/themes/pywal.theme.css in every candidate config
    # folder, plus de-register it from that folder's settings.json.
    for dir in "${PYWAL_DISCORD_DIR:-}" \
               "${XDG_CONFIG_HOME:-$HOME/.config}/vesktop" "$HOME/.config/vesktop" \
               "$HOME/.var/app/dev.vencord.Vesktop/config/vesktop" \
               "${XDG_CONFIG_HOME:-$HOME/.config}/Vencord" "$HOME/.config/Vencord" \
               "$HOME/.var/app/com.discordapp.Discord/config/Vencord"; do
        [[ -n "$dir" ]] || continue
        theme="$dir/themes/pywal.theme.css"
        [[ -f "$theme" ]] || continue
        rm -f "$theme"
        echo "  removed $theme"
        settings="$dir/settings/settings.json"
        if [[ -f "$settings" ]] && command -v python3 >/dev/null 2>&1; then
            if python3 - "$settings" <<'PY'
import json, sys
path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except Exception:
    sys.exit(0)
themes = data.get("enabledThemes")
if isinstance(themes, list) and "pywal.theme.css" in themes:
    data["enabledThemes"] = [t for t in themes if t != "pywal.theme.css"]
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
PY
            then
                echo "    de-registered pywal.theme.css from $settings"
            fi
        fi
    done

    echo
    echo "note: if you used the Spotify sync, spicetify may still be set to the"
    echo "      now-removed Pywal theme — switch to another and re-apply, e.g."
    echo "      \`spicetify config current_theme <name> && spicetify apply\`."
fi

echo
echo "Done."
