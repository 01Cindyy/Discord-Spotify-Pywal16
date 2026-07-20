#!/usr/bin/env bash
# Installer for Pywal16-Discord-Spotify: theme Spotify (spicetify) and
# Discord (Vesktop/Vencord) from your wallpaper's pywal16 palette.
#
# pywal16 (the `wal` command) is the core dependency and is assumed to be
# installed already.
#
# Run from the cloned repo as your NORMAL user (not with sudo — it elevates
# only where needed):
#     ./install.sh
#
# It will:
#   1. ask what to install (both / Spotify only / Discord only)
#   2. copy the chosen sync script(s) and the `walchange` command to /usr/bin
#      and mark them executable
#   3. do the one-time spicetify backup so `spicetify apply` works
set -euo pipefail

SRC_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="/usr/bin"

# ------------------------------------------------------------------ choice --
echo "Pywal16 -> Spotify / Discord theme sync installer"
echo
echo "What would you like to install?"
echo "  0) Both (default)"
echo "  1) Spotify (spicetify) sync only"
echo "  2) Discord (Vesktop/Vencord) sync only"
echo
read -rp "Choice [0/1/2] (default 0): " choice
choice="${choice:-0}"
case "$choice" in
    0) targets=(spotify discord) ;;
    1) targets=(spotify) ;;
    2) targets=(discord) ;;
    *)
        echo "Invalid choice '$choice' — expected 0, 1 or 2. Nothing was installed." >&2
        exit 1
        ;;
esac

# -------------------------------------------------------------------- sudo --
SUDO=""
if [[ $EUID -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo "error: installing to $BIN_DIR needs root — install sudo or run as root." >&2
        exit 1
    fi
fi

# ----------------------------------------------------------------- pywal16 --
# Core dependency; just sanity-check it so a missing install is caught now
# rather than on the first walchange. (walchange also looks in ~/.local/bin.)
if ! command -v wal >/dev/null 2>&1 && [[ ! -x "$HOME/.local/bin/wal" ]]; then
    echo "warning: pywal16 (\`wal\`) not found — install it before running walchange" >&2
    echo "         (https://github.com/eylles/pywal16)." >&2
fi

# --------------------------------------------------------- install scripts --
install_one() {
    local src="$1" dest="$2" label="$3"
    if [[ ! -f "$src" ]]; then
        echo "error: $src not found — is the clone complete?" >&2
        exit 1
    fi
    $SUDO install -m 755 "$src" "$dest"
    echo "  installed $label -> $dest"
}

echo
for t in "${targets[@]}"; do
    case "$t" in
        spotify) install_one "$SRC_DIR/pywal-spicetify-sync.py" "$BIN_DIR/pywal-spicetify-sync" "Spotify (spicetify) sync" ;;
        discord) install_one "$SRC_DIR/pywal-discord-sync.py"  "$BIN_DIR/pywal-discord-sync"  "Discord (Vesktop/Vencord) sync" ;;
    esac
done
# walchange/walapply run whichever sync script(s) exist, so they're installed
# regardless of the choice above.
install_one "$SRC_DIR/walchange" "$BIN_DIR/walchange" "walchange command"
install_one "$SRC_DIR/walapply"  "$BIN_DIR/walapply"  "walapply command"

# --------------------------------------------------- one-time client setup --
find_spicetify() {
    local c
    if command -v spicetify >/dev/null 2>&1; then
        command -v spicetify
        return
    fi
    for c in "$HOME/.spicetify/spicetify" "$HOME/.local/bin/spicetify" \
             /usr/local/bin/spicetify /usr/bin/spicetify \
             /opt/spicetify/spicetify /opt/spicetify-cli/spicetify; do
        if [[ -x "$c" ]]; then
            echo "$c"
            return
        fi
    done
    return 1
}

if [[ " ${targets[*]} " == *" spotify "* ]]; then
    echo
    if SPICETIFY="$(find_spicetify)"; then
        # `spicetify apply` refuses to run until a backup of Spotify exists;
        # take it now so the first walchange just works. Fails harmlessly if
        # a backup is already there.
        if "$SPICETIFY" backup >/dev/null 2>&1; then
            echo "spicetify: created the one-time Spotify backup."
        else
            echo "spicetify: backup step skipped (one already exists, or Spotify wasn't found)."
            echo "           If the first walchange fails, run \`spicetify backup apply\` once."
        fi
    else
        echo "warning: spicetify not found — install it (https://spicetify.app) and re-run, or the Spotify sync will fail." >&2
    fi
fi

if [[ " ${targets[*]} " == *" discord "* ]]; then
    found=""
    for d in "${XDG_CONFIG_HOME:-$HOME/.config}/vesktop" "$HOME/.config/vesktop" \
             "$HOME/.var/app/dev.vencord.Vesktop/config/vesktop" \
             "${XDG_CONFIG_HOME:-$HOME/.config}/Vencord" "$HOME/.config/Vencord" \
             "$HOME/.var/app/com.discordapp.Discord/config/Vencord"; do
        if [[ -d "$d" ]]; then
            found="$d"
            break
        fi
    done
    echo
    if [[ -n "$found" ]]; then
        echo "discord: found Vencord config at $found."
    else
        echo "note: no Vesktop/Vencord config folder found yet — launch your Discord client once before running walchange."
    fi
fi

# -------------------------------------------------------------------- done --
echo
echo "Done. Theme everything from a wallpaper with:"
echo "    walchange /path/to/wallpaper.jpg"
echo
echo "Or re-apply the current palette without changing wallpaper:"
echo "    walapply"
echo
echo "First Discord run only: restart Discord/Vesktop once after your first"
echo "walchange (the theme gets enabled in its settings). After that every"
echo "walchange re-themes both apps live."
