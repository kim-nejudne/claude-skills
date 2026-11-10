#!/usr/bin/env bash
# Release APK for {{APP_TITLE}} ({{APK_FEATURE}}): build android/ in release mode and put the APK
# and apk/version.json where the image picks them up (the Dockerfile copies apk/; the server
# serves both).
#
#   scripts/apk-release.sh
#
# The deploy workflow runs it with the release keystore from GitHub secrets. Without one (feature
# sessions, local runs) the APK is unsigned: phones refuse to install it, but the build still
# proves R8 and resource shrinking.
#
# Environment: APP_VERSION_CODE (default: the number of commits that changed android/, so it
# rises only when the phone app changes), ANDROID_KEYSTORE, ANDROID_KEYSTORE_PASSWORD,
# ANDROID_KEY_ALIAS.
set -euo pipefail

cd "$(dirname "$0")/.."
export APP_VERSION_CODE=${APP_VERSION_CODE:-$(git rev-list --count HEAD -- android)}
[[ $APP_VERSION_CODE =~ ^[1-9][0-9]*$ ]] || {
  echo "APP_VERSION_CODE must be a positive integer, got '$APP_VERSION_CODE'" >&2
  exit 1
}

android/gradlew -p android --console=plain -q assembleRelease

out=android/app/build/outputs/apk/release
if [[ -n ${ANDROID_KEYSTORE:-} ]]; then
  apk=$out/app-release.apk
  sdk=${ANDROID_HOME:-$(sed -n 's/^sdk\.dir=//p' android/local.properties 2>/dev/null)}
  apksigner=$(find "$sdk/build-tools" -name apksigner -type f 2>/dev/null | sort -V | tail -1)
  [[ -n $apksigner ]] || { echo "apksigner not found under $sdk/build-tools" >&2; exit 1; }
  "$apksigner" verify --print-certs "$apk" | grep -E 'SHA-256' || { echo "$apk is not signed" >&2; exit 1; }
else
  apk=$out/app-release-unsigned.apk
  echo "ANDROID_KEYSTORE is unset: the APK is unsigned (the deploy signs it)."
fi

name={{APP}}-$APP_VERSION_CODE.apk
mkdir -p apk
find apk -maxdepth 1 -name '*.apk' -delete
cp -- "$apk" "apk/$name"
sha=$(sha256sum "apk/$name" | cut -d' ' -f1)
# versionName matches android/app/build.gradle.kts ("1.0.<versionCode>").
printf '{"versionCode": %s, "versionName": "1.0.%s", "sha256": "%s", "apk": "%s"}\n' \
  "$APP_VERSION_CODE" "$APP_VERSION_CODE" "$sha" "$name" >apk/version.json
echo "apk/$name ($(du -h "apk/$name" | cut -f1)), apk/version.json:"
cat apk/version.json
