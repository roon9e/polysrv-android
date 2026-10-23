# [PolySRV][polysrv] – Multiserver Messenger for Android

**One familiar app. Any MTProto server you trust.**

**PolySRV** is a fork of the official [Telegram for Android][telegram_android] source code,
based on the [Telegram API][telegram_api] and the [MTProto][telegram_proto] secure protocol.

On top of the regular Telegram cloud, the client can connect to **any number of independent
MTProto servers**: pick one on the login screen, or add your own by address and public key.
The server list is not hardcoded — it is loaded from a remote JSON file, so servers can be
added, removed or re-pinged without shipping a new APK.

> 🔗 Built on **MTProto API layer 231**.

[![Build](https://github.com/roon9e/polysrv-android/actions/workflows/sync-upstream.yml/badge.svg)](https://github.com/roon9e/polysrv-android/actions/workflows/sync-upstream.yml)
[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](LICENSE)

## Why you'll like it

* 🌐 **Multiservers** — the official network, your own server, or any community node.
* 🧩 **Server list from the CDN** — edit `servers.json` and the app picks it up, no rebuild.
* 🏠 **Your own infrastructure** — self-hosted MTProto servers are first-class citizens.
* 👥 **Clean isolation** — accounts, sessions and caches are separated per server.
* 🆓 **Open source** — read it, audit it, build it yourself.

## Multiservers

* **Server picker at login** — dot (online/offline), name, `ip:port`, DC count; ping is measured
  with a real TCP connect.
* **Add your own server** from the app: address, port, RSA public key; the fingerprint is computed
  from the key and verified during the handshake.
* **`srv://` links** — server addresses are a linkable scheme, like `tg://` for Telegram.
* **Remote server list** — `servers.json` is served from GitHub Pages / CDN and cached locally;
  the app refreshes it in the background, so the list can be edited without rebuilding.
* **Per-server isolation** — accounts, sessions, caches and DC tables are separate for every server.
* **Live ping** — measured by CI with a TCP connect every 30 minutes and published to the site.

## Supported systems

Android 6.0 (API 23) and above.

The universal APK contains all four ABIs:

* `arm64-v8a`
* `armeabi-v7a`
* `x86`
* `x86_64`

Single-ABI builds are also supported for smaller APKs (see below).

## Upstream sync

This repository tracks [`DrKLO/Telegram`][upstream]. A GitHub Actions workflow (`.github/workflows/sync-upstream.yml`)
runs every 6 hours, fetches the upstream tip, re-applies our changes and, when the resulting tree
differs, pushes it to the `upstream-sync` branch.

Our changes are stored as **string replacements** in [`scripts/polysrv_edits.json`](scripts/polysrv_edits.json)
and applied by [`scripts/patch_polysrv.py`](scripts/patch_polysrv.py) — no fragile `git apply` of patches.
If an upstream refactor breaks a replacement, the patcher reports exactly which ones no longer match
instead of silently dropping them. Regenerate the JSON after changing our sources:

```bash
python3 scripts/generate_polysrv_edits.py
```

The same workflow builds the APKs (one job per ABI in parallel, then a job that merges them
into a universal APK) with Gradle build cache and `ccache` for the native code, so warm builds
take minutes instead of an hour.

## Build instructions

You will require Android Studio 2025.1.4, Android NDK 27.2.12479018, Android SDK 36 and JDK 21.

1. Clone the source code with its submodules:
   ```bash
   git clone --recursive --shallow-submodules https://github.com/roon9e/polysrv-android.git PolySRV
   ```
   In case you forgot the `--recursive` flag, run inside the directory:
   ```bash
   git submodule init && git submodule update --init --recursive --depth=1
   ```
2. Copy your `release.keystore` into `TMessagesProj/config`.
3. Fill out `RELEASE_KEY_PASSWORD`, `RELEASE_KEY_ALIAS`, `RELEASE_STORE_PASSWORD` in `gradle.properties`.
4. Create Firestore/FCM apps with the package name from `APP_PACKAGE` in `gradle.properties` and put
   `google-services.json` next to `TMessagesProj`.
5. Open the project in Android Studio (open it, do **not** import it).
6. Fill out `TMessagesProj/src/main/java/org/telegram/messenger/BuildVars.java` — `APP_ID` and
   `APP_HASH` from [my.telegram.org](https://my.telegram.org).
7. Build from the command line:
   ```bash
   ./gradlew :TMessagesProj_App:assembleAfatRelease
   ```
   The APK is at `TMessagesProj_App/build/outputs/apk/afat/release/app.apk`.

Single ABI:

```bash
./gradlew :TMessagesProj_App:assembleAfatRelease -PabiFilters=arm64-v8a
```

### Server list configuration

* `servers.json` — the servers shown in the app (official Telegram + your own).
* `servers.env` — where the app fetches `servers.json` and `update.json` from (primary URL + fallback).
  Values end up in `BuildConfig.SERVERS_CONFIG_URL` / `SERVERS_CONFIG_URL_FALLBACK`.

The public site is published from the `gh-pages` branch:
<https://roon9e.github.io/polysrv-android/>.

## Third-party

* OpenSSL ([Apache License 2.0](https://openssl-library.org/source/license/apache-license-2.0.txt))
* FFmpeg ([LGPL](https://www.ffmpeg.org/legal.html))
* WebRTC ([New BSD License](https://github.com/desktop-app/tg_owt/blob/master/LICENSE))
* BoringSSL ([OpenSSL License](https://boringssl.googlesource.com/boringssl/+/HEAD/LICENSE))
* libvpx ([BSD License](https://github.com/webmproject/libvpx/blob/main/LICENSE))
* dav1d ([BSD License](https://code.videolan.org/videolan/dav1d/-/blob/master/COPYING))
* libyuv ([BSD License](https://chromium.googlesource.com/libyuv/libyuv/+/refs/heads/main/LICENSE))
* OpenH264 ([BSD License](https://github.com/cisco/openh264/blob/master/LICENSE))
* WAMR ([Apache License 2.0](https://github.com/bytecodealliance/wasm-micro-runtime/blob/main/LICENSE))
* SQLite ([public domain](https://www.sqlite.org/copyright.html))
* TDLib / MTProto libraries ([Boost Software License](https://github.com/tdlib/td/blob/master/LICENSE_1_0.txt))
* zlib ([zlib License](http://www.zlib.net/zlib_license.html))
* Open Sans font ([Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0.html))
* Vazirmatn font ([SIL Open Font License 1.1](https://github.com/rastikerdar/vazirmatn/blob/master/OFL.txt))

## License

The source code is published under the GNU General Public License v2, the license is available
[here][license]. The original client is developed by Telegram FZ-LLC and the Telegram Android team;
this fork keeps their copyright notices intact.

## Thanks to

* [DrKLO/Telegram][upstream] — the official Telegram for Android sources this project is based on.
* [**OwpenGram Android**](https://github.com/owpengram/owpengram-android-client) — for the idea of a
  multiservers Android client on top of the open Telegram sources.
* The Telegram Desktop and TDLib teams — for the protocol documentation and reference implementations.
* GitHub Actions — for the runners that sync, ping and build everything.

---

⭐ If PolySRV is useful to you, a star on GitHub helps a lot.

[//]: # (LINKS)
[polysrv]: https://roon9e.github.io/polysrv-android/
[telegram_android]: https://github.com/DrKLO/Telegram
[upstream]: https://github.com/DrKLO/Telegram
[telegram_api]: https://core.telegram.org
[telegram_proto]: https://core.telegram.org/mtproto
[license]: LICENSE
