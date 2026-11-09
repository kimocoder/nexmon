#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
# Deliberately use the focused mock for both platform signature contracts.
jni_include=-Itests/jni/mock
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT HUP INT TERM
for platform in host android; do
platform_flag=
[ "$platform" != android ] || platform_flag=-D__ANDROID__
for lib in libbeaconflood libauthflood libcountermeasures libwids libcowpatty; do
  extra=
  [ "$lib" != libcowpatty ] || extra=-DCOW
  src=app/app/src/main/external/src/$lib/src
  gcc -std=c99 -Wall -Wextra -Werror -pthread $platform_flag $extra $jni_include -I"$src" tests/jni/callback_test.c "$src/infomessage.c" -o "$out/$lib"
  "$out/$lib"
  echo "$platform $lib JNI lifecycle: PASS"
done
done
