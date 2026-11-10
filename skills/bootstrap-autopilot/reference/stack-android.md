# Android client: F01 scaffold

Used when the spec has a native Android app beside the Node server (`ANDROID` in bootstrap.json): Kotlin, Jetpack Compose, Room, WorkManager, CameraX, ML Kit text recognition, minSdk 26, sideloaded APK only. F01 builds both halves: `reference/stack-node.md` for the server and web client, this for `android/`. Everything below ran headless on kim-desktop on 2026-11-10 (scratch build); versions are the stable ones of that day, so bump them when you scaffold (current stable, then run every check).

## This machine

- **JDK 21** from pacman (`jdk21-openjdk`, in `packages/kim-desktop.txt`) beside the default JDK 27. Gradle's launcher runs fine on 27; `gradle/gradle-daemon-jvm.properties` puts the daemon on 21, and `jvmToolchain(21)` compiles and tests on 21. No `JAVA_HOME` anywhere.
- **Android SDK** in `~/Android/Sdk` (user-owned, so AGP downloads a missing platform itself; it fetched `android-37.0`). Command-line tools from developer.android.com's "Command line tools only" zip (sha256 checked) at `cmdline-tools/latest`, then `sdkmanager --licenses` and `sdkmanager --install platform-tools "platforms;android-<N>" "build-tools;<N.x.y>"`, run with `JAVA_HOME=/usr/lib/jvm/java-21-openjdk`. `sdkmanager` now prints a deprecation notice pointing at `android sdk`; it still works. Platform IDs gained minor levels (`android-37.0`, `android-37.2`).
- F01 writes `android/local.properties` (`sdk.dir=/home/kim/Android/Sdk`, gitignored). CI uses the runner's `ANDROID_HOME`.
- No emulator, no device, no adb, for sessions or the autopilot.

## Layout

```
android/                 its own Gradle build; every command runs from the repo root as
  gradlew, gradle/         android/gradlew -p android <task>
  settings.gradle.kts, build.gradle.kts, gradle.properties, .editorconfig, .gitignore
  gradle/libs.versions.toml, gradle/gradle-daemon-jvm.properties
  tools/fetch-ktlint.sh  the ktlint CLI for the format hook (into .tools/, gitignored)
  app/                   build.gradle.kts, proguard-rules.pro, schemas/ (Room, committed)
    src/main/kotlin/<package>/   src/test/kotlin/<package>/   src/test/resources/robolectric.properties
apk/.gitkeep             the release APK and version.json land here (scripts/apk-release.sh)
scripts/apk-release.sh   (the `APK_FEATURE`, from docs/deploy-kit/)
```

Ignore files: `android/.gitignore` has `.gradle/ .kotlin/ build/ local.properties .tools/ *.jks *.keystore *.p12`. Root `.gitignore` gains `/apk/*` and `!/apk/.gitkeep`. The Docker feature's `.dockerignore` lists `android` (the image gets the phone app only as `apk/`).

## Gradle wrapper

No system Gradle. Download the current distribution and check it, then generate the wrapper with the checksum pinned (`distributionSha256Sum`):

```bash
V=9.9.0
curl -fsSLo "$SCRATCH/gradle.zip" https://services.gradle.org/distributions/gradle-$V-bin.zip
SUM=$(curl -fsSL https://services.gradle.org/distributions/gradle-$V-bin.zip.sha256)   # -L: it redirects
[[ $SUM =~ ^[0-9a-f]{64}$ ]] && echo "$SUM  $SCRATCH/gradle.zip" | sha256sum -c
unzip -q "$SCRATCH/gradle.zip" -d "$SCRATCH/gradle-dist"
"$SCRATCH/gradle-dist/gradle-$V/bin/gradle" -q -p android wrapper --gradle-version $V --distribution-type bin --gradle-distribution-sha256-sum "$SUM"
```

Write `settings.gradle.kts` first (Gradle needs a build to run `wrapper` in). CI's `gradle/actions/setup-gradle` validates the wrapper jar.

## Build files

`settings.gradle.kts`: `pluginManagement` and `dependencyResolutionManagement` repositories `google()`, `mavenCentral()` (plus `gradlePluginPortal()` for plugins), `RepositoriesMode.FAIL_ON_PROJECT_REPOS`, `include(":app")`.

`build.gradle.kts` (root): every plugin below with `apply false`.

`gradle.properties`:

```properties
org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8
org.gradle.configuration-cache=true
org.gradle.caching=true
kotlin.compiler.execution.strategy=in-process
android.useAndroidX=true
# Every testDebugUnitTest run writes fresh screenshots for review; nothing compares them.
roborazzi.test.record=true
```

`gradle/gradle-daemon-jvm.properties`: `toolchainVersion=21`.

`gradle/libs.versions.toml` (the 2026-11-10 set; AGP 9 has Kotlin built in, so there is no `kotlin-android` plugin, only the Compose compiler plugin at the Kotlin version):

```toml
[versions]
agp = "9.5.1"
kotlin = "2.4.21"
ksp = "2.3.13"
ktlintPlugin = "14.2.0"
ktlint = "1.8.0"
composeBom = "2026.09.00"
activity = "1.13.0"
lifecycle = "2.11.0"
core = "1.19.1"
room = "2.8.5"
work = "2.12.0"
camera = "1.6.2"
mlkitText = "16.0.1"
junit = "4.13.2"
androidxTestJunit = "1.3.0"
robolectric = "4.17"
roborazzi = "1.78.0"

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
kotlin-compose = { id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }
ksp = { id = "com.google.devtools.ksp", version.ref = "ksp" }
ktlint = { id = "org.jlleitschuh.gradle.ktlint", version.ref = "ktlintPlugin" }
room = { id = "androidx.room", version.ref = "room" }
roborazzi = { id = "io.github.takahirom.roborazzi", version.ref = "roborazzi" }
```

Libraries: `androidx.core:core-ktx`, `androidx.activity:activity-compose`, `androidx.lifecycle:lifecycle-runtime-compose`, the Compose BOM with `ui`, `material3`, `ui-tooling-preview` (`ui-tooling` and `ui-test-manifest` as `debugImplementation`), `room-runtime`, `room-ktx`, `room-compiler` (`ksp`), `work-runtime-ktx`, `camera-camera2`, `camera-lifecycle`, `camera-view`, `com.google.mlkit:text-recognition` (the **bundled** Latin model: works with no signal, no Play Services download). Tests: `junit`, `androidx.test.ext:junit`, `robolectric`, the BOM with `ui-test-junit4`, `roborazzi`, `roborazzi-compose`. F01 adds only what the scaffold uses if the spec defers camera or sync to later features; each later one adds its own with a one-line reason.

`app/build.gradle.kts`, the parts that matter:

```kotlin
// Release signing and the version come from the environment (the deploy workflow); without
// them the release build is unsigned and versionCode is 1.
fun env(name: String) = providers.environmentVariable(name)

android {
    compileSdk = 37 // current AndroidX libraries refuse anything lower (checkAarMetadata)
    defaultConfig {
        minSdk = 26
        targetSdk = 37
        versionCode = env("APP_VERSION_CODE").orElse("1").get().toInt()
        versionName = "1.0.$versionCode" // scripts/apk-release.sh writes the same into version.json
        // Phones only: x86 libraries would double the APK (the bundled ML Kit model is native).
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
    }
    signingConfigs {
        create("release") {
            env("ANDROID_KEYSTORE").orNull?.let { path ->
                storeFile = file(path)
                storePassword = env("ANDROID_KEYSTORE_PASSWORD").get()
                keyAlias = env("ANDROID_KEY_ALIAS").get()
                keyPassword = storePassword // PKCS12: one password
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = if (env("ANDROID_KEYSTORE").isPresent) signingConfigs.getByName("release") else null
        }
    }
    buildFeatures { compose = true }
    testOptions {
        unitTests.isIncludeAndroidResources = true
        // Robolectric's SDK 36 sandbox reads jdk.internal.access (FileDescriptor internals).
        unitTests.all { it.jvmArgs("--add-opens=java.base/jdk.internal.access=ALL-UNNAMED") }
    }
}
kotlin { jvmToolchain(21) }
ktlint { version.set(libs.versions.ktlint) }
// Committed schemas: Room migrations are tested against them.
room { schemaDirectory("$projectDir/schemas") }
```

Measured: the release APK with CameraX and bundled ML Kit is 43 MB for four ABIs, 20 MB with the ARM filter.

`.editorconfig`: `root = true`, and under `[*.{kt,kts}]` `ktlint_function_naming_ignore_when_annotated_with = Composable` (Composables are PascalCase).

`AndroidManifest.xml`: `CAMERA` needs `<uses-feature android:name="android.hardware.camera" android:required="true" />` (lint fails without it); `android:allowBackup="false"` (the phone's records must not leave it through Google backup); add `INTERNET`, and `REQUEST_INSTALL_PACKAGES` with a FileProvider when the updater lands.

## Seams

Everything a device or the network does sits behind an interface with a fake used in tests and development: `PlateCamera` (CameraX), `PlateReader` (ML Kit), `AppInstaller` (the package installer), `SyncApi` (the server), and an injected `java.time.Clock`. Room runs for real under Robolectric (in-memory database). WorkManager workers are tested with `work-testing`'s `TestListenableWorkerBuilder`. Business rules (fees, plate normalisation, sync merge) are plain Kotlin with plain JUnit tests.

## UI tests and screenshots

Robolectric replaces the emulator and Roborazzi replaces the Playwright playtest for the phone app:

```kotlin
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(qualifiers = "w360dp-h800dp-xxhdpi") // DESIGN.md's phone; add a fontScale=1.3 case for dense text
class GateScreenTest {
    @get:Rule
    val compose = createComposeRule() // androidx.compose.ui.test.junit4.v2 (the v1 one is deprecated)

    @Test
    fun showsCountAndCarIn() {
        var taps = 0
        compose.setContent { AppTheme { GateScreen(carsInside = 23, onCarIn = { taps++ }) } }
        compose.onNodeWithText("23 cars inside").assertIsDisplayed()
        compose.onNodeWithText("Car in").performClick()
        assertEquals(1, taps)
        compose.onRoot().captureRoboImage()
    }
}
```

`src/test/resources/robolectric.properties`: `sdk=36` (Robolectric 4.17's newest; it runs fine under `compileSdk` 37). Screenshots land in `android/app/build/outputs/roborazzi/<class>.<test>.png` (1080×2400 for the qualifiers above). They are review artifacts, never compared: the ui-reviewer and the session Read them against DESIGN.md.

## ktlint

The Gradle plugin's `ktlintCheck` is the gate and `ktlintFormat` is part of `FORMAT_CMD`. The format-on-edit hook needs a CLI that takes one file, at the same version: `android/tools/fetch-ktlint.sh` pins `VERSION` and `SHA256`, checks the catalog agrees, and installs `android/.tools/ktlint`. Run it in F01 and after any ktlint bump. Pinning a new version: download `ktlint` and `ktlint.asc` from the release, import the signing key the ktlint docs name ("Verification of download": `ADBC987D1A7B91DB6B0AAA81995EFBF4A3D20BEB` for 0.32–1.8; 2.x moves to the `ktlint/ktlint` org with key `0F631C1DD2A656869B1F47350FDF10E71780F7FD`) from keyserver.ubuntu.com into a throwaway `GNUPGHOME`, `gpg --verify`, then pin its sha256. The script as proven:

```bash
VERSION=1.8.0
SHA256=a3fd620207d5c40da6ca789b95e7f823c54e854b7fade7f613e91096a3706d75
cd "$(dirname "$0")/.."
catalog=$(sed -n 's/^ktlint = "\(.*\)"$/\1/p' gradle/libs.versions.toml)
[[ $catalog == "$VERSION" ]] || { echo "catalog has ktlint $catalog, this script pins $VERSION" >&2; exit 1; }
# then: skip if .tools/ktlint matches SHA256; else download to a temp file, sha256sum -c, chmod +x, mv
```

The CLI's output matched `ktlintCheck` on a deliberately messy file.

## Release APK and updates

`scripts/apk-release.sh` (from `docs/deploy-kit/`, in the `APK_FEATURE` feature) runs `assembleRelease`, checks the signature with the newest `apksigner` when `ANDROID_KEYSTORE` is set, and writes `apk/<app>-<code>.apk` and `apk/version.json` (`{versionCode, versionName, sha256, apk}`). `APP_VERSION_CODE` defaults to `git rev-list --count HEAD -- android`: it rises only when the phone app changes, so a server-only deploy prompts no update, and an image rollback serves a lower code that phones ignore. Unsigned locally (sessions run it to catch R8 breakage); the deploy signs with the keystore from GitHub secrets.

The server serves `GET /apk/version.json` (`Cache-Control: no-cache`) and the APK (`application/vnd.android.package-archive`) from `APK_DIR`; no `version.json` means no update offered. The app checks at each sync, shows "Update available", downloads into its cache, compares sha256, and hands the file to the installer (`AppInstaller`). Android itself refuses an update signed with another key.

## bootstrap.json values for a hybrid app

The Node values from `stack-node.md`, with these changes:

```json
"ANDROID": true,
"APK_FEATURE": "F22",
"STACK_SUMMARY": "Node 24 + TypeScript, Express API, Vite + React client, vitest; Android app in Kotlin + Compose (android/)",
"CHECKS": [
  { "name": "format:check", "cmd": "npm run format:check", "ciName": "format check" },
  { "name": "lint", "cmd": "npm run lint" },
  { "name": "typecheck", "cmd": "npm run typecheck" },
  { "name": "test", "cmd": "npm test", "ciName": "tests" },
  { "name": "build", "cmd": "npm run build", "ci": false },
  { "name": "android:ktlint", "cmd": "android/gradlew -p android ktlintCheck", "ciName": "android ktlint" },
  { "name": "android:lint", "cmd": "android/gradlew -p android lintDebug", "ciName": "android lint" },
  { "name": "android:test", "cmd": "android/gradlew -p android testDebugUnitTest", "ciName": "android tests" },
  { "name": "android:build", "cmd": "android/gradlew -p android assembleDebug", "ci": false }
],
"FORMAT_CMD": "npm run format && android/gradlew -p android ktlintFormat",
"FORMATTER": [
  { "bin": "node_modules/.bin/prettier", "args": ["--write", "--log-level", "warn"], "exts": [".ts", ".tsx", ".js", ".mjs", ".json", ".css", ".md"] },
  { "name": "kotlin", "bin": "android/.tools/ktlint", "args": ["--format", "--log-level=none"], "exts": [".kt", ".kts"] }
],
"TYPECHECK": [
  { "cmd": ["npm", "run", "typecheck"], "exts": [".ts", ".tsx"], "needs": "node_modules/.bin/tsc" },
  { "name": "kotlin", "cmd": ["android/gradlew", "-p", "android", "-q", "compileDebugUnitTestKotlin"], "exts": [".kt", ".kts"], "needs": "android/gradlew" }
],
"TEST_GLOBS": ["**/*.test.ts", "**/*.test.tsx", "android/**/src/test/**"],
"EXTRA_ALLOW": ["npm install", "npm uninstall", "npx tsx", "npx tsc", "npx eslint", "npx prettier", "npx playwright install", "android/gradlew", "android/tools/fetch-ktlint.sh", "scripts/apk-release.sh"]
```

`android:build` stays out of CI like the Node build: the deploy builds the release APK. A warm daemon runs the four Gradle checks in seconds; a cold one takes a minute or two (lint is the slowest), and the autopilot stops its daemons between sessions.
