# Android app build modernization

## What changed (tooling-only bump)

The Android app was on retired tooling: AGP 2.3.2, Gradle 3.3, `jcenter()`,
`compile` dependencies, `compileSdk/targetSdk 23`, and a floating dependency
version. That combination no longer resolves on current machines (jcenter is
gone; Gradle 3.3 does not run on modern JDKs).

This change modernizes **only the build tooling**, deliberately keeping the app
on the legacy `android.support` library so **no application source had to
change**:

| Item | Before | After |
|---|---|---|
| Android Gradle Plugin | 2.3.2 | 7.4.2 |
| Gradle wrapper | 3.3 | 7.6.4 |
| Repositories | `jcenter()` | `google()` + `mavenCentral()` + vendored `app/local-repo` |
| Dependency configuration | `compile` | `implementation` |
| `compileSdk` / `targetSdk` | 23 / 23 | 28 / 28 |
| `minSdkVersion` | 24 | 21 |
| support-v4 / recyclerview-v7 | 23.4.0 | 28.0.0 (last support-lib release) |
| `eu.chainfire:libsuperuser` | `1.0.0.+` (floating) | `1.0.0.201704021214` (pinned) |
| Java source/target | 1.7 (nested in `defaultConfig`, ignored) | 1.8 (under `android{}`) |
| `namespace` | (manifest `package`) | set in `build.gradle` |
| `-XX:MaxPermSize` | present (fails on JDK 8+) | removed |
| `android.useDeprecatedNdk=true` | present (removed in AGP 7) | removed |

`targetSdk` is intentionally held at **28**, not 34: at targetSdk 34+ every
context-registered receiver must pass `RECEIVER_EXPORTED`/`RECEIVER_NOT_EXPORTED`,
which would break the signature-permission `registerReceiver(...)` calls added
as part of the broadcast-hardening work. Raising it is part of the follow-up
below.

`minSdk` is **21**. Java code avoids API 23+ calls: notifications use the API-20
`Notification.Action.Builder(int, ...)` constructor, and fragments use
`getActivity()`. Every JNI `Application.mk` and every utility targets
`android-21`.

### Native ABIs and API level

`app/app/src/main/Makefile` separates the two kinds of native output:

| Variable | Default | Selects |
|---|---|---|
| `APP_ABI` | `armeabi-v7a` | JNI libraries under `src/main/libs/<abi>` (packaged as `jniLibs`) |
| `ASSET_ABI` | `armeabi-v7a` | utilities copied into `assets/nexmon`; assets have no ABI subdirectories, so the APK ships one set |

`armeabi` is gone — NDK r17+ dropped it — so the build uses `armeabi-v7a` and
every module takes `$(TARGET_ARCH_ABI)` from ndk-build instead of hardcoding an
ABI in a path.

`arm64-v8a` cannot be built for the app yet: `libwireshark_helper` links the
2017 Wireshark/glib/gettext archives in
`external/src/libwireshark_helper/prebuildlibs/`, which are 32-bit ARM only.
The module fails fast with an explicit error for any other `APP_ABI`. The
utilities themselves are ABI-clean and do build for both. Enabling arm64 means
rebuilding that whole stack for arm64 *and* porting `wireshark_helper.c` to the
4.x API; `utilities/wireshark/build-android.sh` pins API 28 and glib 2.90, so it
is not an API-21 drop-in.

Verify any build with:

```sh
python3 buildtools/scripts/check_android_abi.py --max-api 21 \
    app/app/src/main/libs/armeabi-v7a
```

It reads the ELF machine type and `.note.android.ident` directly, so it needs
neither binutils nor the NDK, and exits non-zero on a wrong ABI or an API level
above the limit. CI runs it for both ABIs (`android-native` job);
`buildtools/scripts/android_smoke_test.sh` pushes binaries to an API 21
device/emulator and checks that the loader accepts them (`android-api21-smoke`
job, which builds the tools for x86 because GitHub's emulator images are x86).

Two API-21 specifics worth knowing:

- `utilities/socat` force-includes `pty_compat.h`, which declares `openpty()`
  for `__ANDROID_API__ < 23` on top of socat's own `openpty.c` (implemented with
  `posix_openpt`/`grantpt`/`unlockpt`/`ptsname_r`, all API 21).
- `utilities/aircrack-ng` drops `-D_FILE_OFFSET_BITS=64` when targeting
  `android-21`: with it, bionic redirects `fseek()` to `fseeko64()` (API 24),
  which libc++'s `<fstream>` cannot use. The cost is a 2 GiB file limit, which
  no capture on a phone approaches.
- `utilities/iperf` and `utilities/iperf3` stay on `android-24`: they call
  `getifaddrs()`/`freeifaddrs()`, which bionic only provides from API 24. They
  are not shipped in the APK.

Three more things in the native build need explaining:

- **`external/aircrack-legacy/`** is a snapshot of the pre-1.7 aircrack-ng
  `src/` tree (taken from git at the commit before `aircrack-ng: update to 1.7`).
  The four JNI helpers (`libmyaircrackwep`, `libmyairdecap-ng`,
  `libmyfakeauth`, `libmyivstools`) are forks of that code and use its API —
  globals `opt`/`wep`, `struct pcap_pkthdr.tv_sec`, its own `pcap.h`/`version.h`,
  `struct ivs2_*`. `utilities/aircrack-ng` still builds 1.7 for the CLI tools.
  Porting the helpers to 1.7 is a separate migration.
- **`libwireshark_helper`** links the 2017 glib archive, which was compiled
  without `-fPIC` for ARMv5TE. `-Wl,--exclude-libs,ALL` localises archive
  symbols so lld resolves its `R_ARM_REL32` relocations at link time — the
  result has no `TEXTREL`, which Android would otherwise refuse to load for
  targetSdk ≥ 23. `sync_compat.c` supplies `__sync_synchronize()` and
  `__sync_val_compare_and_swap_4()`, which those ARMv5TE objects call but
  compiler-rt does not export.
- `utilities/libsqlite/version` was renamed to `VERSION.txt`: the libsqlite
  include directory is on the `-I` path, and a bare file named `version`
  shadowed C++'s `<version>` header used by `linecount.cpp`.

Every `Application.mk` now declares `APP_PLATFORM := android-21` explicitly.
Passing `TARGET_PLATFORM=android-21` on the `ndk-build` command line does not
set it, which is why NDK 30 warned `APP_PLATFORM not set`.

## Verification

CI builds the app on JDK 17 with the Android SDK (API 28) and runs
`./gradlew assembleDebug` (see `.github/workflows/ci.yml`, `android` job).
Locally, with JDK 17 and an Android SDK (API 28 platform + build-tools 30.0.3):

```sh
cd app
./gradlew assembleDebug        # expect BUILD SUCCESSFUL
./gradlew lint                 # informational (abortOnError is false)
```

SDK levels are declared only in `app/build.gradle`; the stale `<uses-sdk>`
block was removed from the manifest so it can no longer disagree with Gradle.
`android:allowBackup` is `false` because app data includes capture files.
`versionCode` comes from `git rev-list --count HEAD`; shallow clones report 1,
so release jobs must use `fetch-depth: 0` or set `NEXMON_VERSION_CODE`.

If `namespace` + the manifest `package` attribute both being present triggers a
hard error on your AGP point release (it is a warning on 7.4.2), remove
`package="de.tu_darmstadt.seemoo.nexmon"` from `app/src/main/AndroidManifest.xml`.

## Follow-up: AndroidX + SDK 34 (separate, source-touching effort)

Going past support-lib 28 requires a full AndroidX migration — jetifier only
rewrites third-party libraries, not this app's own `import android.support.*`
lines. That effort, best done in Android Studio ("Migrate to AndroidX"), is:

1. `android.useAndroidX=true`, add `androidx.*` dependencies in place of
   `com.android.support:*`, and let the IDE rewrite all source imports.
2. Bump to AGP 8.x + a matching Gradle + JDK 17 (AGP 8 drops jetifier).
3. Raise `compileSdk`/`targetSdk` to 34.
4. **Coordinate with the broadcast hardening:** replace the signature-permission
   `registerReceiver(receiver, filter, PERMISSION_INTERNAL_BROADCAST, null)`
   calls with `ContextCompat.registerReceiver(ctx, receiver, filter, ContextCompat.RECEIVER_NOT_EXPORTED)`
   (sites: `stations/AttackService`, `net/MonitorModeService`,
   `gui/AttackInfoFragment`, `gui/SharkFragment`, `gui/APfragment`). Same-app
   sends still reach a NOT_EXPORTED receiver; other apps are blocked, matching
   today's behavior.
5. Reconsider `minifyEnabled`/`abortOnError` once the build is green.
