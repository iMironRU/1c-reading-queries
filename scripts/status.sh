#!/usr/bin/env bash
# status.sh — просмотр и управление статусом рецензий
#
# Использование:
#   ./scripts/status.sh                              — таблица всех параграфов
#   ./scripts/status.sh detail <файл>               — история рецензий файла
#   ./scripts/status.sh set <файл> <decision> [note] — выставить решение
#
# decision: approved | needs_revision | skip
#
# Примеры:
#   ./scripts/status.sh
#   ./scripts/status.sh detail chapters/04_patterny/04-02_poisk_elementa.md
#   ./scripts/status.sh set chapters/04_patterny/04-02_poisk_elementa.md approved "Всё хорошо"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

MODE="${1:-table}"
CHAPTER_ARG="${2:-}"
DECISION_ARG="${3:-}"
NOTE_ARG="${4:-}"

SCRIPT_DIR="$SCRIPT_DIR" ROOT_DIR="$ROOT_DIR" \
MODE="$MODE" CHAPTER_ARG="$CHAPTER_ARG" DECISION_ARG="$DECISION_ARG" NOTE_ARG="$NOTE_ARG" \
python3 - << 'PYTHON_EOF'
import sys, os, json, re
from pathlib import Path
from datetime import date

root_dir     = Path(os.environ["ROOT_DIR"])
mode         = os.environ["MODE"]
chapter_arg  = os.environ["CHAPTER_ARG"]
decision_arg = os.environ["DECISION_ARG"]
note_arg     = os.environ["NOTE_ARG"]

status_path  = root_dir / "docs" / "review-status.json"
chapters_dir = root_dir / "chapters"

# --- ANSI цвета ---
GREEN  = "\x1b[32m"
YELLOW = "\x1b[33m"
RED    = "\x1b[31m"
GRAY   = "\x1b[90m"
BOLD   = "\x1b[1m"
RESET  = "\x1b[0m"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def visible_len(s):
    return len(ANSI_RE.sub("", s))

def ljust_visible(s, width):
    pad = width - visible_len(s)
    return s + " " * max(pad, 0)

# --- Загрузить статус ---
status = json.loads(status_path.read_text()) if status_path.exists() else {}

# --- Собрать все параграфы из chapters/ ---
all_chapters = sorted(chapters_dir.rglob("*.md"))

def decision_cell(entry):
    d = entry.get("decision", "")
    if d == "approved":
        return GREEN + "approved" + RESET
    if d == "needs_revision":
        return YELLOW + "revision" + RESET
    if d == "skip":
        return GRAY + "skip" + RESET
    return ""

def reviewed_cell(entry):
    lr = entry.get("last_reviewed", "")
    if lr:
        return lr
    return GRAY + "—" + RESET

# =====================================================================
if mode == "table":
    col_file     = 55
    col_reviewed = 12
    col_decision = 14

    header_file     = BOLD + "Файл" + RESET
    header_reviewed = BOLD + "Дата" + RESET
    header_decision = BOLD + "Решение" + RESET

    sep = (
        ljust_visible(BOLD + "─" * col_file + RESET, col_file + 4)
        + " " + "─" * col_reviewed
        + " " + "─" * col_decision
    )

    print()
    print(
        ljust_visible(header_file, col_file + 4)
        + " " + ljust_visible(header_reviewed, col_reviewed)
        + " " + header_decision
    )
    print(sep)

    for ch in all_chapters:
        rel = ch.relative_to(root_dir)
        key = str(rel)
        entry = status.get(key, {})

        file_cell     = str(rel)
        reviewed_str  = reviewed_cell(entry)
        decision_str  = decision_cell(entry)

        print(
            ljust_visible(file_cell, col_file)
            + "  "
            + ljust_visible(reviewed_str, col_reviewed + 4)
            + " " + decision_str
        )
    print()

# =====================================================================
elif mode == "detail":
    if not chapter_arg:
        print("Укажи файл: ./scripts/status.sh detail <файл>", file=sys.stderr)
        sys.exit(1)

    ch = Path(chapter_arg)
    if not ch.is_absolute():
        ch = Path.cwd() / ch
    key = str(ch.relative_to(root_dir))
    entry = status.get(key, {})

    print(f"\n{BOLD}{key}{RESET}")
    print(f"  Последняя рецензия: {entry.get('last_reviewed', '—')}")
    print(f"  Модель:             {entry.get('last_model', '—')}")
    d = entry.get("decision", "")
    print(f"  Решение:            {decision_cell(entry) if d else GRAY + 'не выставлено' + RESET}")
    if entry.get("decision_note"):
        print(f"  Примечание:         {entry['decision_note']}")
    history = entry.get("history", [])
    if history:
        print(f"\n  История рецензий ({len(history)}):")
        for h in history:
            print(f"    {h.get('date','')}  {h.get('model','')}  → {h.get('file','')}")
    else:
        print(f"\n  {GRAY}Рецензий нет.{RESET}")
    print()

# =====================================================================
elif mode == "set":
    if not chapter_arg or not decision_arg:
        print("Использование: ./scripts/status.sh set <файл> <decision> [note]", file=sys.stderr)
        sys.exit(1)
    if decision_arg not in ("approved", "needs_revision", "skip"):
        print(f"Допустимые значения: approved | needs_revision | skip", file=sys.stderr)
        sys.exit(1)

    ch = Path(chapter_arg)
    if not ch.is_absolute():
        ch = Path.cwd() / ch
    key = str(ch.relative_to(root_dir))

    entry = status.get(key, {})
    entry["decision"] = decision_arg
    if note_arg:
        entry["decision_note"] = note_arg
        entry["decision_date"] = date.today().isoformat()
    elif "decision_note" in entry:
        del entry["decision_note"]
    entry["decision_date"] = date.today().isoformat()
    status[key] = entry

    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    print(f"Выставлено: {key} → {decision_arg}" + (f" ({note_arg})" if note_arg else ""))

else:
    print(f"Неизвестный режим: {mode}. Используй: table | detail | set", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF
