#!/bin/sh
# Install the hardening-review skill into the Hermes user skills directory.
#
# Usage:
#   ./install.sh            # install to ~/.hermes/skills/security/hardening-review
#   ./install.sh --dest DIR # install to a custom destination directory
#   ./install.sh --check    # verify the installed copy matches this source
set -eu

SKILL_NAME="hardening-review"
CATEGORY="security"
DEFAULT_DEST="${HOME}/.hermes/skills/${CATEGORY}/${SKILL_NAME}"

SRC_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
DEST="$DEFAULT_DEST"
MODE="install"

while [ $# -gt 0 ]; do
    case "$1" in
        --dest)
            [ $# -ge 2 ] || { echo "install.sh: --dest requires a directory argument" >&2; exit 2; }
            DEST="$2"
            shift 2
            ;;
        --check)
            MODE="check"
            shift
            ;;
        -h|--help)
            sed -n '2,7p' "$0"
            exit 0
            ;;
        *)
            echo "install.sh: unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

[ -f "${SRC_DIR}/SKILL.md" ] || {
    echo "install.sh: SKILL.md not found next to this script (${SRC_DIR})" >&2
    exit 2
}

if [ "$MODE" = "check" ]; then
    if [ ! -d "$DEST" ]; then
        echo "install.sh: not installed at ${DEST}" >&2
        exit 1
    fi
    if diff -r --exclude='__pycache__' "${SRC_DIR}" "${DEST}" > /dev/null 2>&1; then
        echo "install.sh: installed copy at ${DEST} is up to date"
        exit 0
    fi
    echo "install.sh: installed copy at ${DEST} differs from source; re-run ./install.sh" >&2
    exit 1
fi

mkdir -p "$(dirname -- "$DEST")"
rm -rf "${DEST}.tmp"
cp -R "$SRC_DIR" "${DEST}.tmp"
find "${DEST}.tmp" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf "$DEST"
mv "${DEST}.tmp" "$DEST"

echo "Installed ${SKILL_NAME} to ${DEST}"
echo "Next: run 'hermes skills reload' or restart your Hermes session to load it."
