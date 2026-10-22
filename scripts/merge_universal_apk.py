#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Склейка single-ABI APK в один universal APK.

Берёт 4 APK (по одному на ABI), достаёт из каждого lib/<abi>/*,
кладёт всё в базовый APK, выравнивает (zipalign) и подписывает (apksigner)
нашим keystore.

Использование:
    python3 scripts/merge_universal_apk.py --apks armeabi-v7a=arm.apk arm64-v8a=arm64.apk ... \
        --keystore TMessagesProj/config/release.keystore --alias release \
        --ks-pass 88315900 --key-pass 88315900 --out app-universal.apk
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile


def find_build_tools(sdk_root):
    bt = os.path.join(sdk_root, "build-tools")
    if not os.path.isdir(bt):
        sys.exit(f"build-tools не найден в {bt}")
    versions = sorted(os.listdir(bt), reverse=True)
    for v in versions:
        p = os.path.join(bt, v)
        if os.path.isfile(os.path.join(p, "zipalign")) and os.path.isfile(os.path.join(p, "apksigner")):
            return p
    sys.exit(f"не найдены zipalign/apksigner в {bt}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apks", nargs="+", required=True, help="abi=path/to.apk (несколько)")
    ap.add_argument("--keystore", required=True)
    ap.add_argument("--alias", default="release")
    ap.add_argument("--ks-pass", default="")
    ap.add_argument("--key-pass", default="")
    ap.add_argument("--out", default="app-universal.apk")
    ap.add_argument("--sdk-root", default=os.environ.get("ANDROID_HOME", os.environ.get("ANDROID_SDK_ROOT", "")))
    args = ap.parse_args()

    pairs = []
    for item in args.apks:
        if "=" not in item:
            sys.exit(f"неверный формат: {item} (ожидается abi=путь)")
        abi, path = item.split("=", 1)
        if not os.path.isfile(path):
            sys.exit(f"APK не найден: {path}")
        pairs.append((abi, path))
    if not pairs:
        sys.exit("нет APK для склейки")

    build_tools = find_build_tools(args.sdk_root)
    print(f"build-tools: {build_tools}")

    # базовый APK: предпочитаем arm64, иначе первый
    base_abi, base_path = next((p for p in pairs if p[0] == "arm64-v8a"), pairs[0])
    print(f"базовый APK: {base_abi} ({base_path})")

    work = os.path.abspath("_merge_tmp")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)

    unsigned = os.path.join(work, "app-unsigned.apk")
    # распаковываем базовый и переносим lib/<abi> из остальных
    with zipfile.ZipFile(base_path) as z:
        z.extractall(work)
    for abi, path in pairs:
        if abi == base_abi:
            continue
        print(f"добавляю lib/{abi} из {path}")
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.startswith(f"lib/{abi}/"):
                    z.extract(name, work)
                elif name.startswith("lib/") and not os.path.isfile(os.path.join(work, name)):
                    # на случай, если в базовом не было этой abi
                    z.extract(name, work)

    # Сохраняем метод сжатия оригинала: .so и resources.arsc часто лежат без сжатия
    # (и должны остаться такими, иначе Android не сможет их распаковать/выровнять).
    stored = set()
    with zipfile.ZipFile(base_path) as z:
        for info in z.infolist():
            if info.compress_type == zipfile.ZIP_STORED:
                stored.add(info.filename)

    # пересобираем APK (подпись будет после zipalign)
    if os.path.exists(unsigned):
        os.remove(unsigned)
    with zipfile.ZipFile(unsigned, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(work):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, work)
                if rel == os.path.basename(unsigned):
                    continue
                method = zipfile.ZIP_STORED if rel in stored else zipfile.ZIP_DEFLATED
                z.write(full, rel, compress_type=method)

    # zipalign + подпись
    aligned = os.path.join(work, "app-aligned.apk")
    subprocess.run([os.path.join(build_tools, "zipalign"), "-f", "4", unsigned, aligned], check=True)
    subprocess.run([
        os.path.join(build_tools, "apksigner"), "sign",
        "--ks", args.keystore, "--ks-key-alias", args.alias,
        "--ks-pass", "pass:" + args.ks_pass, "--key-pass", "pass:" + args.key_pass,
        "--out", args.out, aligned,
    ], check=True)

    shutil.rmtree(work, ignore_errors=True)

    with zipfile.ZipFile(args.out) as z:
        abis = sorted({n.split("/")[1] for n in z.namelist() if n.startswith("lib/")})
    size = os.path.getsize(args.out) / (1024 * 1024)
    print(f"готово: {args.out} ({size:.1f} МБ), ABI: {', '.join(abis)}")


if __name__ == "__main__":
    main()
