#!/bin/bash
# Symlink this repo's skills into ~/.claude/skills and its scripts into ~/.local/bin. Safe to re-run.
#
#   ./install.sh          create or repair every link
#   ./install.sh --check  only report links that are missing or wrong
#
# Every skills/<name> and bin/<name> is linked; a new one needs no edit here. A real file or
# directory already at a target is moved aside to <target>.pre-install, never deleted. A link
# pointing elsewhere is replaced.

set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILLS_DIR="${HOME}/.claude/skills"
BIN_DIR="${HOME}/.local/bin"

check_only=false
case "${1-}" in
  "") ;;
  --check) check_only=true ;;
  *) echo "usage: ${0##*/} [--check]" >&2; exit 2 ;;
esac

links=()
for src in "$REPO"/skills/*/; do links+=("${src%/}|${SKILLS_DIR}/$(basename "$src")"); done
for src in "$REPO"/bin/*; do [[ -f $src ]] && links+=("$src|${BIN_DIR}/$(basename "$src")"); done

status=0
for entry in "${links[@]}"; do
  src="${entry%%|*}"
  dest="${entry#*|}"

  if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
    continue
  fi

  if $check_only; then
    if [[ -L "$dest" ]]; then
      echo "wrong link:  $dest -> $(readlink "$dest")"
    elif [[ -e "$dest" ]]; then
      echo "not a link:  $dest"
    else
      echo "missing:     $dest"
    fi
    status=1
    continue
  fi

  mkdir -p "$(dirname "$dest")"
  if [[ -L "$dest" ]]; then
    rm "$dest" # a symlink pointing somewhere else: replacing it loses nothing
  elif [[ -e "$dest" ]]; then
    backup="${dest}.pre-install"
    [[ -e "$backup" ]] && backup="${backup}.$(date +%Y%m%d-%H%M%S)"
    mv "$dest" "$backup"
    echo "moved aside: $dest -> $backup"
  fi
  ln -s "$src" "$dest"
  echo "linked:      $dest -> $src"
done

exit "$status"
