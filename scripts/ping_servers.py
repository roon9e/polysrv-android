#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пингует серверы из servers.json (TCP-connect по host:port) и записывает
результат прямо в файл: "pingMs", "online", "checkedAt".

Использование:
    python3 scripts/ping_servers.py site/servers.json [--timeout 3]
"""

import argparse
import json
import socket
import time
from datetime import datetime, timezone


def resolve_endpoint(server):
    """Эндпоинт сервера: явные host/port либо домашний DC из списка dc."""
    host = server.get("host")
    port = server.get("port")
    if host:
        return host, int(port or 443)
    dcs = server.get("dc") or []
    if dcs:
        main = server.get("mainDcId") or 0
        for d in dcs:
            if main and d.get("id") == main:
                return d.get("host"), int(d.get("port") or 443)
        d = dcs[0]
        return d.get("host"), int(d.get("port") or 443)
    return None, None


def ping(host, port, timeout):
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return int((time.monotonic() - t0) * 1000)
    except Exception:
        return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="путь к servers.json")
    ap.add_argument("--timeout", type=float, default=3.0)
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as f:
        data = json.load(f)

    for s in data.get("servers", []):
        if s.get("pingManual"):
            # значение задано вручную (например, сервер недоступен с CI-раннера)
            print(f"  {s.get('name') or s.get('id')}: ручной пинг, пропускаем")
            continue
        host, port = resolve_endpoint(s)
        if not host:
            continue
        ms = ping(host, port, args.timeout)
        s["pingMs"] = ms
        s["online"] = ms >= 0
        print(f"  {s.get('name') or s.get('id')}: {host}:{port} -> " + (f"{ms} ms" if ms >= 0 else "offline"))

    data["checkedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(args.file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"обновлён {args.file} (проверено {data['checkedAt']})")


if __name__ == "__main__":
    main()
