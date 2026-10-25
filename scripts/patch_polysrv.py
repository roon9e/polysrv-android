#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PolySrv patcher — накладывает наши изменения (PolySrv) поверх Telegram Android.

Изменения применяются как поиск/замена блоков текста (scripts/polysrv_edits.json),
а не как git-патч: если upstream немного отличается, скрипт не падает целиком,
а аккуратно сообщает, какие куски не нашлись, и продолжает.

Использование:
    python3 scripts/patch_polysrv.py --target ./Telegram
    python3 scripts/patch_polysrv.py --target ./Telegram --check
    python3 scripts/patch_polysrv.py --target ./Telegram --reverse

Требования: python3. Для сабмодулей нужен git.
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
DEFAULT_EDITS = os.path.join(HERE, "polysrv_edits.json")

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


# ---------------------------------------------------------------- поиск/замена

def _norm(text):
    """Нормализация для «мягкого» сравнения (пробелы/переводы строк)."""
    return re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()


def find_variants(old):
    """Варианты блока: сначала как есть, потом с обрезанным контекстом по краям."""
    lines = old.split("\n")
    variants = [old]
    # контекст = строки, одинаковые в old и new; обрезаем их с краёв
    for trim in range(1, 8):
        if len(lines) <= 2 * trim + 1:
            break
        trimmed = "\n".join(lines[trim:len(lines) - trim])
        if trimmed.strip():
            variants.append(trimmed)
    return variants


def apply_edit(text, old, new):
    """Заменяет old -> new. Возвращает (текст, True|False|None).
    None —old не найден вовсе."""
    if not old.strip():
        return text, None
    # 1) точное совпадение
    if old in text:
        return text.replace(old, new, 1), True
    # 2) с обрезанным контекстом
    for variant in find_variants(old)[1:]:
        if variant in text:
            return text.replace(variant, new, 1), True
    # 3) мягкое сравнение (пробелы/отступы могут отличаться)
    old_n = _norm(old)
    if not old_n:
        return text, None
    # ищем диапазон строк, совпадающий по нормализованному тексту
    old_lines = [l for l in old.split("\n")]
    n = len(old_lines)
    if n == 0 or n > 400:
        return text, None
    src_lines = text.split("\n")
    for i in range(0, max(0, len(src_lines) - n + 1)):
        chunk = src_lines[i:i + n]
        if _norm("\n".join(chunk)) == old_n:
            merged = src_lines[:i] + new.split("\n") + src_lines[i + n:]
            return "\n".join(merged), True
    return text, None


# ---------------------------------------------------------------- операции

def patch_project(target, edits_file, reverse=False, check=False, only=None, skip=None):
    with open(edits_file, encoding="utf-8") as f:
        data = json.load(f)
    files = data.get("files", {})
    force = data.get("force", {})

    applied, skipped, created, binary_ok = 0, 0, 0, 0
    skipped_list = []

    for rel, spec in files.items():
        if only and not any(rel.startswith(p) for p in only):
            continue
        if skip and any(rel.startswith(p) for p in skip):
            continue
        path = os.path.join(target, rel)
        mode = spec.get("mode")

        if mode == "new":
            content = spec.get("content", "")
            if reverse:
                if os.path.isfile(path):
                    os.remove(path)
                    created += 1
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.isfile(path) and open(path, encoding="utf-8", errors="replace").read() == content:
                continue
            if check:
                created += 1
                continue
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            created += 1
            continue

        if mode == "binary":
            if reverse:
                continue
            blob = base64.b64decode(spec["base64"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if check:
                binary_ok += 1
                continue
            with open(path, "wb") as f:
                f.write(blob)
            binary_ok += 1
            continue

        if mode == "delete":
            if not reverse and os.path.isfile(path):
                os.remove(path)
            continue

        if not os.path.isfile(path):
            skipped += 1
            skipped_list.append(f"{rel}: файл не найден")
            continue

        with open(path, encoding="utf-8") as f:
            text = f.read()
        had_final_newline = text.endswith("\n")

        file_ok, file_skip = 0, 0
        for edit in spec.get("edits", []):
            # regexp-правка: не зависит от изменчивых строк апстрима
            if "old_regex" in edit:
                if reverse:
                    file_skip += 1
                    skipped_list.append(f"{rel}: regexp-правка не поддерживает --reverse")
                    continue
                text, count = re.subn(edit["old_regex"], edit["new"], text, count=1, flags=re.M)
                if count:
                    file_ok += 1
                else:
                    file_skip += 1
                continue
            old, new = edit["old"], edit["new"]
            if reverse:
                old, new = new, old
            text, res = apply_edit(text, old, new)
            if res:
                file_ok += 1
            else:
                file_skip += 1
        # принудительные правила (всегда, независимо от diff)
        for rule in force.get(rel, []):
            pattern, replacement = rule["pattern"], rule["replacement"]
            new_text, count = re.subn(pattern, replacement, text, flags=re.M)
            if count:
                text = new_text
                file_ok += 1
            else:
                file_skip += 1
                skipped_list.append(f"{rel}: не найдено правило {pattern}")

        applied += file_ok
        skipped += file_skip
        if file_skip:
            skipped_list.append(f"{rel}: не найдено кусков — {file_skip}")

        if not check and file_ok:
            if had_final_newline and not text.endswith("\n"):
                text += "\n"
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

    return applied, skipped, created, binary_ok, skipped_list


# ---------------------------------------------------------------- опции

def check_project(target):
    if not os.path.isdir(target):
        fail(f"каталог не найден: {target}")
    if not os.path.isfile(os.path.join(target, "settings.gradle")):
        fail(f"похоже, это не корень Telegram Android (нет settings.gradle): {target}")
    if not os.path.isdir(os.path.join(target, "TMessagesProj", "jni", "tgnet")):
        fail(f"не найден TMessagesProj/jni/tgnet — это не тот проект: {target}")


def find_edits(custom):
    if custom:
        if not os.path.isfile(custom):
            fail(f"файл правок не найден: {custom}")
        return custom
    for candidate in (DEFAULT_EDITS, os.path.join(os.getcwd(), "polysrv_edits.json")):
        if os.path.isfile(candidate):
            return candidate
    fail("не найден polysrv_edits.json (положи его рядом со скриптом или укажи --edits)")


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
    info("инициализирую сабмодули (долго, несколько ГБ)...")
    cmd = ["git", "-C", target, "submodule", "update", "--init", "--recursive"]
    if depth:
        cmd.append("--depth=1")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        warn("сабмодули инициализированы с ошибками (попробуй вручную: git submodule update --init --recursive)")
    else:
        info("сабмодули готовы")


def print_next_steps(target):
    print()
    print(f"{BOLD}Что дальше{RESET}")
    print(f"  1. echo 'sdk.dir=$HOME/Android/Sdk' > {target}/local.properties")
    print("  2. export JAVA_HOME=/opt/android-studio/jbr")
    print("     ./gradlew :TMessagesProj_App:assembleAfatRelease")
    print("  3. adb install -r TMessagesProj_App/build/outputs/apk/afat/release/app.apk")
    print()
    print("  Меняется без пересборки:")
    print("    * servers.env — URL конфига (CDN) + список DC в SERVERS_JSON")
    print("    * servers.json — тот же список (assets-фолбэк, офлайн)")
    print()


def main():
    ap = argparse.ArgumentParser(description="Накладывает изменения PolySrv поверх Telegram Android")
    ap.add_argument("--target", default=".", help="корень проекта Telegram (по умолчанию текущий каталог)")
    ap.add_argument("--edits", default=None, help="путь к polysrv_edits.json")
    ap.add_argument("--check", action="store_true", help="только проверить, что всё найдётся")
    ap.add_argument("--reverse", action="store_true", help="откатить изменения")
    ap.add_argument("--strict", action="store_true", help="считать неудачные замены ошибкой")
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
    edits_file = find_edits(args.edits)

    only = None
    skip = None
    if args.native_only:
        only = ["TMessagesProj/jni/"]
    elif args.java_only:
        skip = ["TMessagesProj/jni/"]

    info(f"проект: {target}")
    info(f"правки: {edits_file}")

    applied, skipped, created, binary_ok, skipped_list = patch_project(
        target, edits_file, reverse=args.reverse, check=args.check, only=only, skip=skip)

    info(f"применено замен: {applied}, новых файлов: {created}, бинарных: {binary_ok}, не найдено: {skipped}")
    if skipped_list:
        warn("не нашлись следующие куски (проверь вручную):")
        for line in skipped_list[:20]:
            print(f"    - {line}")
        if len(skipped_list) > 20:
            print(f"    ... ещё {len(skipped_list) - 20}")
    if args.strict and skipped:
        fail("есть ненайденные куски (см. список выше)")

    if args.check:
        info("проверка завершена (файлы не менялись)")
        return

    if args.api_id is not None and args.api_hash:
        apply_api_credentials(target, args.api_id, args.api_hash)
    if args.keystore:
        copy_keystore(target, os.path.abspath(os.path.expanduser(args.keystore)))
    if args.submodules and not args.reverse:
        init_submodules(target, depth=not args.no_depth)

    print_next_steps(target)


if __name__ == "__main__":
    main()
