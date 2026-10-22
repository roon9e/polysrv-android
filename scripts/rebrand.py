#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ребрендинг: Telegram -> PolySRV во всех пользовательских строках.

Правила:
  * бренд приложения ("Telegram" как название нашего клиента) -> PolySRV
  * НЕ трогаем: "Telegram Premium", ссылки (telegram.org, t.me/telegram, telegram.me),
    "Telegram Web/Desktop/macOS", "Telegram Ads"/"Telegram Ad Platform", "MTProto"
  * ключи строк (name="...") не переименовываем — только значения
  * во всех локалях меняются одни и те же ключи (список берём из values/strings.xml)

Использование:
    python3 scripts/rebrand.py [--brand PolySRV] [--dry-run]
"""

import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STRINGS = "TMessagesProj/src/main/res/values/strings.xml"

# куда НЕ подставляем бренд
KEEP = [
    "Telegram Premium",
    "Telegram Ads",
    "Telegram Ad Platform",
    "Telegram Web",
    "Telegram Desktop",
    "Telegram macOS",
    "Telegram for macOS",
    "telegram.org",
    "t.me/telegram",
    "telegram.me",
    "core.telegram.org",
    "MTProto",
    "Telegram-compatible",
    "TelegramWebProxy",
    "TelegramWebviewProxy",
    "Telegram-Android",
    "Official Telegram cloud",   # это про сам Telegram, а не про наш бренд
    "Only for Telegram-compatible",
]

STRING_RE = re.compile(r'(<string name="([^"]+)">)(.*?)(</string>)', re.S)


def should_rebrand(value):
    for k in KEEP:
        if k in value:
            return False
    return "Telegram" in value


def rebrand_value(value, brand):
    return value.replace("Telegram", brand)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", default="PolySRV")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    brand = args.brand

    # 1) определяем ключи по английской строке
    en_path = os.path.join(ROOT, STRINGS)
    with open(en_path, encoding="utf-8") as f:
        en = f.read()

    keys = set()
    for m in STRING_RE.finditer(en):
        if should_rebrand(m.group(3)):
            keys.add(m.group(2))
    print(f"ключей к ребрендингу: {len(keys)}")

    changed_files = 0
    changed_strings = 0

    # 2) применяем к каждой локали
    for path in sorted(glob.glob(os.path.join(ROOT, "TMessagesProj/src/main/res/values*/strings.xml"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        count = 0

        def repl(m):
            nonlocal count
            if m.group(2) in keys:
                new = rebrand_value(m.group(3), brand)
                if new != m.group(3):
                    count += 1
                    return m.group(1) + new + m.group(4)
            return m.group(0)

        new_text = STRING_RE.sub(repl, text)
        # 3) имя приложения
        new_text = new_text.replace(
            '<string name="AppName">PolySrv</string>',
            f'<string name="AppName">{brand}</string>')
        new_text = new_text.replace(
            '<string name="AppNameBeta">PolySrv Beta</string>',
            f'<string name="AppNameBeta">{brand} Beta</string>')
        if new_text != text:
            changed_files += 1
            changed_strings += count
            print(f"  {os.path.relpath(path, ROOT)}: {count} строк")
            if not args.dry_run:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_text)

    # 4) Java-литералы: только фразы (с пробелом), не ключи ресурсов
    java_changed = 0
    for path in glob.glob(os.path.join(ROOT, "TMessagesProj/src/main/java/**/*.java"), recursive=True):
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            continue
        out = []
        pos = 0
        modified = False
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', text):
            lit = m.group(1)
            if " " not in lit or not should_rebrand(lit):
                continue
            if "R.string." in lit or "window." in lit:
                continue  # это код/ключ ресурса, а не пользовательский текст
            new_lit = rebrand_value(lit, brand)
            if new_lit != lit:
                out.append(text[pos:m.start(1)])
                out.append(new_lit)
                pos = m.end(1)
                modified = True
                java_changed += 1
        if modified:
            out.append(text[pos:])
            new_text = "".join(out)
            print(f"  {os.path.relpath(path, ROOT)}: java-литерал")
            if not args.dry_run:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_text)

    print(f"итого: файлов {changed_files}, строк {changed_strings}, java-литералов {java_changed}")


if __name__ == "__main__":
    main()
