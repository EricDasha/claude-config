#!/usr/bin/env python3
"""distilling-sessions: mine opencode session history from SQLite.

Subcommands:
  paths                  Locate opencode.db candidates and report schema presence
  list                   Session inventory (title, directory, tokens, time)
  extract --out FILE     User messages grouped by session (UTF-8, sanitized)
  extract --session ID   Deep-dive a single session

Read-only by design. Output is written as UTF-8 files to avoid Windows
console (GBK) mojibake. Sensitive patterns are redacted before writing.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

REDACT_PATTERNS = [
    re.compile(r"\b\d{8,10}:AA[\w-]{30,}"),                # Telegram bot token
    re.compile(r"\b(vless|vmess|trojan|ss)://[^\s]+"),      # proxy URIs
    re.compile(r"\b(plink|ssh)\s+\S+\s+\S+\s+(\S+)"),       # ssh with password
]

SKIP_PREFIXES = ("<local-command", "<system-reminder")


def redact(text: str) -> str:
    for pat in REDACT_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def find_dbs() -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".local" / "share" / "opencode" / "opencode.db",
        home / "AppData" / "Local" / "opencode" / "opencode.db",
        home / ".local" / "share" / "opencode" / "storage",
    ]
    return [p for p in candidates if p.exists()]


def open_db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return con


def cmd_paths(_args) -> None:
    for p in find_dbs():
        print(f"FOUND: {p}")
    print("Note: older opencode versions stored sessions as JSON under storage/")


def cmd_list(args) -> None:
    con = open_db(Path(args.db))
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id, title, directory, agent, model, tokens_input, tokens_output, time_created "
        "FROM session ORDER BY time_created"
    ).fetchall()
    out = Path(args.out) if args.out else None
    lines = []
    for sid, title, directory, agent, model, ti, to, tc in rows:
        try:
            model_id = json.loads(model or "{}").get("id", "?") if model and model.strip().startswith("{") else (model or "?")
        except json.JSONDecodeError:
            model_id = "?"
        lines.append(
            f"[{sid[:12]}] {title}\n"
            f"  dir={directory} agent={agent} model={model_id}\n"
            f"  tokens: in={ti} out={to} created={tc}\n"
        )
    text = "\n".join(lines)
    if out:
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))


def cmd_extract(args) -> None:
    con = open_db(Path(args.db))
    cur = con.cursor()
    out = Path(args.out)
    if not out:
        out = Path("session_digest.md")

    prefix = f"{(args.session or '')}%"
    query = (
        "SELECT m.id, m.session_id, m.data FROM message m "
        "WHERE (? IS NULL OR m.session_id LIKE ?) ORDER BY m.time_created"
    )
    msgs = cur.execute(query, (args.session, prefix)).fetchall()

    with open(out, "w", encoding="utf-8") as fh:
        for mid, sid, mdata in msgs:
            try:
                role = json.loads(mdata or "{}").get("role", "?")
            except json.JSONDecodeError:
                continue
            if role != "user":
                continue
            parts = cur.execute(
                "SELECT data FROM part WHERE message_id=? ORDER BY time_created", (mid,)
            ).fetchall()
            for (pdata,) in parts:
                try:
                    p = json.loads(pdata)
                except json.JSONDecodeError:
                    continue
                if p.get("type") != "text":
                    continue
                txt = p.get("text", "")
                if any(txt.startswith(pre) for pre in SKIP_PREFIXES):
                    continue
                if "<system-reminder" in txt[:300]:
                    continue
                fh.write(f"\n## [{sid[:12]}] USER\n{redact(txt[:4000])}\n")
    print(f"wrote {out}")


def main() -> None:
    default_db = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
    ap = argparse.ArgumentParser(description="Mine opencode session history (read-only)")
    ap.add_argument("--db", default=str(default_db), help="Path to opencode.db")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("paths")
    p_list = sub.add_parser("list")
    p_list.add_argument("--out", default=None)
    p_ex = sub.add_parser("extract")
    p_ex.add_argument("--out", default=None)
    p_ex.add_argument("--session", default=None, help="Filter by session id prefix")

    args = ap.parse_args()
    {"paths": cmd_paths, "list": cmd_list, "extract": cmd_extract}[args.cmd](args)


if __name__ == "__main__":
    main()
