#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор scripts/polysrv_edits.json — список наших правок в виде
"найди старый блок -> замени новым", чтобы патчер не зависел от git apply
(и не падал на конфликтах, а аккуратно сообщал, что не нашлось).

Использование (из корня репозитория):
    python3 scripts/generate_polysrv_edits.py [base_commit]
"""

import base64
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "polysrv_edits.json")
DEFAULT_BASE = "0aae95980"  # upstream 13.0.3 (7183) — база, на которой считались правки

# Принудительные правила: применяются всегда, независимо от того, что было в базе.
# Нужны, чтобы параметры подписи/пакета не зависели от состояния апстрима.
FORCE_RULES = {
    "gradle.properties": [
        (r"^RELEASE_KEY_PASSWORD=.*$", "RELEASE_KEY_PASSWORD=88315900"),
        (r"^RELEASE_KEY_ALIAS=.*$", "RELEASE_KEY_ALIAS=release"),
        (r"^RELEASE_STORE_PASSWORD=.*$", "RELEASE_STORE_PASSWORD=88315900"),
        (r"^APP_PACKAGE=.*$", "APP_PACKAGE=org.polysrv.messenger"),
    ],
}


def git(*args, binary=False):
    res = subprocess.run(["git", "-C", REPO_ROOT] + list(args), stdout=subprocess.PIPE, check=True)
    return res.stdout if binary else res.stdout.decode("utf-8", "replace")


def parse_diff(diff_text):
    """Разбирает unified diff -> {path: {"mode":..., "hunks":[...]}}"""
    files = {}
    path = None
    mode = "modify"
    hunks = []
    hunk = None

    def flush_hunk():
        nonlocal hunk
        if hunk is not None and (hunk["old"] or hunk["new"]):
            hunks.append(hunk)
        hunk = None

    def flush_file():
        nonlocal path, mode, hunks
        flush_hunk()
        if path is not None:
            files[path] = {"mode": mode, "hunks": hunks}
        path, mode, hunks = None, "modify", []

    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            flush_file()
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            path = m.group(2) if m else None
            mode = "modify"
        elif line.startswith("new file mode"):
            mode = "new"
        elif line.startswith("deleted file mode"):
            mode = "delete"
        elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            if path:
                files[path] = {"mode": "binary", "hunks": []}
            path = None
        elif line.startswith("@@"):
            flush_hunk()
            hunk = {"old": [], "new": []}
        elif hunk is not None and line[:1] in (" ", "+", "-"):
            if line.startswith("+"):
                hunk["new"].append(line[1:])
            elif line.startswith("-"):
                hunk["old"].append(line[1:])
            else:
                hunk["old"].append(line[1:])
                hunk["new"].append(line[1:])
    flush_file()
    return files


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    diff = git("diff", "--no-color", "-U3", f"{base}..HEAD", "--", ".",
               ":(exclude)polysrv.patch", ":(exclude)scripts", ":(exclude).github")
    parsed = parse_diff(diff)

    out = {"base": base, "files": {}}
    for path, info in parsed.items():
        if info["mode"] == "binary":
            blob = git("show", f"HEAD:{path}", binary=True)
            out["files"][path] = {"mode": "binary", "base64": base64.b64encode(blob).decode()}
            continue
        if info["mode"] == "new":
            content = git("show", f"HEAD:{path}")
            out["files"][path] = {"mode": "new", "content": content}
            continue
        if info["mode"] == "delete":
            out["files"][path] = {"mode": "delete"}
            continue
        edits = []
        for h in info["hunks"]:
            edits.append({"old": "\n".join(h["old"]), "new": "\n".join(h["new"])})
        if edits:
            out["files"][path] = {"mode": "modify", "edits": edits}

    force = {}
    for path, rules in FORCE_RULES.items():
        force[path] = [{"pattern": pat, "replacement": rep} for pat, rep in rules]
    out["force"] = force

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    total = sum(len(v.get("edits", [])) for v in out["files"].values())
    print(f"записано {OUT}: {len(out['files'])} файлов, {total} правок")


if __name__ == "__main__":
    main()
