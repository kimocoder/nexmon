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
