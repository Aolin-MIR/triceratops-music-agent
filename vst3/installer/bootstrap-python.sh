#!/bin/bash
# Called by setup-macos.sh; stdout contains only the chosen Python path.
set -euo pipefail
data="$1"
mode="${TRICERATOPS_DOWNLOAD_SOURCE:-auto}"
case "$mode" in auto|official|china) ;; *) echo 'Invalid download source' >&2; exit 1;; esac
valid_python() {
  "$1" -c 'import platform,sys,tarfile; assert platform.machine()=="arm64"; assert (3,10)<=sys.version_info<(3,12); assert hasattr(tarfile,"data_filter")' >/dev/null 2>&1
}
if [[ -n "${TRICERATOPS_PYTHON:-}" ]]; then
  valid_python "$TRICERATOPS_PYTHON" || { echo 'Selected Python must be native ARM64 3.10/3.11 with current security updates.' >&2; exit 1; }
  command -v "$TRICERATOPS_PYTHON"
  exit
fi
if [[ "${TRICERATOPS_PORTABLE_PYTHON:-0}" != 1 ]]; then
for candidate in python3.11 /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 python3.10; do
  if command -v "$candidate" >/dev/null 2>&1 && valid_python "$candidate"; then
    command -v "$candidate"
    exit
  fi
done
fi
sha=d81d757a9785850393cd695a9a686c765a6370fbdc83738589ef2ecd3e5c44b3
url='https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.11.17%2B20261013-aarch64-apple-darwin-install_only.tar.gz'
destination="$data/runtimes/python-3.11.17-20261013"
if [[ -f "$destination/.triceratops-files.sha256" ]] && (cd "$destination" && /usr/bin/shasum -a 256 -c .triceratops-files.sha256 >/dev/null 2>&1) && valid_python "$destination/python/bin/python3.11"; then
  echo "$destination/python/bin/python3.11"
  exit
fi
[[ ! -e "$destination" ]] || { echo 'Private Python was modified; preserve it for diagnosis and choose a clean runtime directory.' >&2; exit 1; }
mkdir -p "$data/downloads" "$data/runtimes"
archive="$data/downloads/$sha.tar.gz"
verified() { [[ -f "$archive" ]] && [[ "$(/usr/bin/shasum -a 256 "$archive" | cut -d ' ' -f 1)" == "$sha" ]]; }
urls=("$url" "https://ghfast.top/$url" "https://gh-proxy.com/$url")
if [[ "$mode" == china ]]; then urls=("https://ghfast.top/$url" "https://gh-proxy.com/$url" "$url"); fi
if [[ "$mode" == official ]]; then urls=("$url"); fi
if ! verified; then
  temporary="$(mktemp "$data/downloads/.python-XXXXXX")"
  trap 'rm -f "$temporary"' EXIT
  for source in "${urls[@]}"; do
    echo "Downloading native Python: $source" >&2
    if /usr/bin/curl --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --speed-limit 1024 --speed-time 30 --max-time 900 --retry 1 --output "$temporary" "$source" >&2 && [[ "$(/usr/bin/shasum -a 256 "$temporary" | cut -d ' ' -f 1)" == "$sha" ]]; then
      mv "$temporary" "$archive"
      break
    fi
    echo 'Source failed or SHA-256 mismatch; trying the next source.' >&2
  done
fi
verified || { echo 'Python download failed. Rerun the installer and select another source.' >&2; exit 1; }
stage="$(mktemp -d "$data/runtimes/.python-XXXXXX")"
# Extract only this exact hash-verified upstream distribution.
/usr/bin/tar -xzf "$archive" -C "$stage"
valid_python "$stage/python/bin/python3.11" || { rm -rf "$stage"; exit 1; }
(cd "$stage" && find python -type f ! -name '*.pyc' -exec /usr/bin/shasum -a 256 {} + > .triceratops-files.sha256)
mv "$stage" "$destination"
echo "$destination/python/bin/python3.11"
