#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PolySrv patcher — накладывает наши изменения (PolySrv) поверх чистого Telegram Android.

Использование:
    # скачали DrKLO/Telegram, распаковали в ./Telegram
    python3 scripts/patch_polysrv.py --target ./Telegram

Что делает:
    * применяет polysrv.patch (все наши правки: нативка, Java, ресурсы, конфиг серверов);
    * при желании инициализирует сабмодули (--submodules);
    * при желании подставляет свои api_id/api_hash/keystore (--api-id, --api-hash, --keystore).

Требования: python3, git (для применения патча), git submodule (для сабмодулей).
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
DEFAULT_PATCH = os.path.join(REPO_ROOT, "polysrv.patch")

BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def info(msg):
    print(f"{GREEN}==>{RESET} {msg}")


def warn(msg):
    print(f"{YELLOW}warn:{RESET} {msg}")


def fail(msg):
    print(f"{RED}error:{RESET} {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, cwd=None, check=True, capture=False):
    res = subprocess.run(
        cmd, cwd=cwd, shell=isinstance(cmd, str),
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        text=True,
    )
    if check and res.returncode != 0:
        out = res.stdout if capture else ""
        fail(f"команда завершилась с кодом {res.returncode}: {' '.join(cmd) if isinstance(cmd, list) else cmd}\n{out or ''}")
    return res


def find_patch(custom):
    if custom:
        if not os.path.isfile(custom):
            fail(f"файл патча не найден: {custom}")
        return custom
    for candidate in (DEFAULT_PATCH, os.path.join(os.getcwd(), "polysrv.patch")):
        if os.path.isfile(candidate):
            return candidate
    fail("не найден polysrv.patch (положи его рядом со скриптом или укажи --patch)")


def check_project(target):
    if not os.path.isdir(target):
        fail(f"каталог не найден: {target}")
    gradle = os.path.join(target, "settings.gradle")
    if not os.path.isfile(gradle):
        fail(f"похоже, это не корень Telegram Android (нет settings.gradle): {target}")
    if not os.path.isdir(os.path.join(target, "TMessagesProj", "jni", "tgnet")):
        fail(f"не найден TMessagesProj/jni/tgnet — это не тот проект: {target}")


def is_git_repo(path):
    return os.path.isdir(os.path.join(path, ".git")) or os.path.isfile(os.path.join(path, ".git"))


def apply_patch(target, patch_path, dry_run=False, reverse=False, only=None, skip=None):
    cmd = ["git", "apply", "--binary", "-p1", "--whitespace=nowarn"]
    if dry_run:
        cmd.append("--check")
    if reverse:
        cmd.append("--reverse")
    if only:
        cmd += ["--include=" + p for p in only]
    if skip:
        cmd += ["--exclude=" + p for p in skip]
    cmd.append(patch_path)

    if is_git_repo(target):
        res = run(cmd, cwd=target, check=False, capture=True)
    else:
        # без git — используем системный patch
        cmd = ["patch", "-p1", "--forward", "--batch", "-i", patch_path]
        if dry_run:
            cmd.append("--dry-run")
        if reverse:
            cmd = ["patch", "-p1", "--reverse", "--batch", "-i", patch_path]
        res = run(cmd, cwd=target, check=False, capture=True)

    if res.returncode != 0:
        out = (res.stdout or "")
        if dry_run:
            fail("патч не применится к этому проекту:\n" + out)
        fail("ошибка применения патча:\n" + out)
    return True


def apply_api_credentials(target, api_id, api_hash):
    path = os.path.join(target, "TMessagesProj", "src", "main", "java", "org", "telegram", "messenger", "BuildVars.java")
    if not os.path.isfile(path):
        warn("BuildVars.java не найден — api_id/api_hash не подставлены")
        return
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"public static int APP_ID = \d+;",
                  f"public static int APP_ID = {api_id};", text, count=1)
    text = re.sub(r'public static String APP_HASH = "[^"]*";',
                  f'public static String APP_HASH = "{api_hash}";', text, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    info(f"api_id={api_id}, api_hash подставлены в BuildVars.java")


def copy_keystore(target, keystore_path):
    dest_dir = os.path.join(target, "TMessagesProj", "config")
    if not os.path.isdir(dest_dir):
        fail(f"нет каталога {dest_dir}")
    if not os.path.isfile(keystore_path):
        fail(f"keystore не найден: {keystore_path}")
    shutil.copy2(keystore_path, os.path.join(dest_dir, "release.keystore"))
    info(f"keystore скопирован: {keystore_path} -> TMessagesProj/config/release.keystore")


def init_submodules(target, depth=True):
    info("инициализирую сабмодули (это долго, несколько ГБ)...")
    cmd = ["git", "submodule", "update", "--init", "--recursive"]
    if depth:
        cmd.append("--depth=1")
    run(cmd, cwd=target)
    info("сабмодули готовы")


def print_next_steps(target):
    print()
    print(f"{BOLD}Что дальше{RESET}")
    print(f"  1. Создай local.properties:  echo 'sdk.dir=$HOME/Android/Sdk' > {target}/local.properties")
    print("  2. Собери:                   export JAVA_HOME=/opt/android-studio/jbr")
    print("                               ./gradlew :TMessagesProj_App:assembleAfatRelease")
    print(f"  3. Поставь:                  adb install -r TMessagesProj_App/build/outputs/apk/afat/release/app.apk")
    print()
    print("  Настройки, которые можно менять без пересборки:")
    print("    * servers.env  — URL конфига серверов (CDN) + список DC в SERVERS_JSON")
    print("    * servers.json — тот же список серверов (assets-фолбэк, офлайн)")
    print()


def main():
    ap = argparse.ArgumentParser(description="Накладывает изменения PolySrv поверх Telegram Android")
    ap.add_argument("--target", default=".", help="корень проекта Telegram (по умолчанию текущий каталог)")
    ap.add_argument("--patch", default=None, help="путь к polysrv.patch")
    ap.add_argument("--check", action="store_true", help="только проверить, что патч применится")
    ap.add_argument("--reverse", action="store_true", help="откатить изменения")
    ap.add_argument("--native-only", action="store_true", help="только нативная часть (jni/)")
    ap.add_argument("--java-only", action="store_true", help="только Java/ресурсы")
    ap.add_argument("--submodules", action="store_true", help="инициализировать сабмодули")
    ap.add_argument("--no-depth", action="store_true", help="качать сабмодули без --depth=1")
    ap.add_argument("--api-id", type=int, default=None, help="свой api_id (my.telegram.org)")
    ap.add_argument("--api-hash", default=None, help="свой api_hash")
    ap.add_argument("--keystore", default=None, help="свой release.keystore")
    args = ap.parse_args()

    target = os.path.abspath(os.path.expanduser(args.target))
    check_project(target)
    patch_path = find_patch(args.patch)

    only = None
    skip = None
    if args.native_only:
        only = ["TMessagesProj/jni/*"]
    elif args.java_only:
        skip = ["TMessagesProj/jni/*"]

    info(f"проект:  {target}")
    info(f"патч:    {patch_path}")
    if args.check:
        apply_patch(target, patch_path, dry_run=True, reverse=args.reverse, only=only, skip=skip)
        info("патч применится без конфликтов")
        return

    apply_patch(target, patch_path, reverse=args.reverse, only=only, skip=skip)
    info("патч применён" + (" (откат)" if args.reverse else ""))

    if args.api_id is not None and args.api_hash:
        apply_api_credentials(target, args.api_id, args.api_hash)
    if args.keystore:
        copy_keystore(target, os.path.abspath(os.path.expanduser(args.keystore)))

    if args.submodules and not args.reverse:
        init_submodules(target, depth=not args.no_depth)

    print_next_steps(target)


if __name__ == "__main__":
    main()
