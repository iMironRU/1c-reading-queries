#!/usr/bin/env python3
"""
style-lint.py — механическая проверка канона стиля серии.

    scripts/style-lint.py [пути ...] [--format text|github] [--warnings-as-errors]

Без аргументов проверяет chapters/. Правила и их серьёзность настраиваются
в metadata.yaml книги:

    style_lint:
      enabled: true
      severity:
        address: warning      # error | warning | off
        abbrev: off
      allow:
        abbrev: ["ПВХ", "ПВР"]

Линтер ловит дёшево и грубо: детерминированное. Смысл — перегрузку терминов,
сломанные метафоры, ощущение голоса — судит панель ревью (scripts/review.py)
и человек. См. docs/style-guide.md и integration-roadmap.md §9.
"""
import os
import re
import sys
import glob

# ─── Загрузка конфигурации ───────────────────────────────────────────────────

DEFAULT_SEVERITY = {
    "address": "error",     # «ты», авторское «я»
    "abbrev": "error",      # РС / РН / РБ / РР в прозе
    "crossref": "warning",  # «см. §A3» вместо краткого повтора
    "clerical": "error",    # канцелярит
    "opener": "error",      # шаблонные зачины
    "filler": "warning",    # пустые усиления — сильно зависят от контекста
    "emoji": "warning",
    "heavy": "warning",     # разметки больше четверти объёма
}


def load_config(root):
    cfg = {"enabled": True, "severity": dict(DEFAULT_SEVERITY), "allow": {}}
    path = os.path.join(root, "metadata.yaml")
    if not os.path.exists(path):
        return cfg
    try:
        import yaml
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except Exception:
        return cfg
    section = data.get("style_lint") or {}
    cfg["enabled"] = section.get("enabled", True)
    cfg["severity"].update(section.get("severity") or {})
    cfg["allow"] = section.get("allow") or {}
    return cfg


# ─── Подготовка текста: прячем то, что проверять не нужно ────────────────────

def strip_uncheckable(text):
    """Заменяет frontmatter, блоки кода, инлайн-код, ссылки и HTML-комментарии
    пробелами той же длины — номера строк и колонок сохраняются."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))

    text = re.sub(r"\A---\n.*?\n---\n", blank, text, flags=re.S)
    text = re.sub(r"^```.*?^```", blank, text, flags=re.S | re.M)
    text = re.sub(r"^~~~.*?^~~~", blank, text, flags=re.S | re.M)
    text = re.sub(r"`[^`\n]+`", blank, text)
    text = re.sub(r"^(?: {4}|\t).*$", blank, text, flags=re.M)   # код отступом
    text = re.sub(r"<!--.*?-->", blank, text, flags=re.S)
    text = re.sub(r"\]\([^)\n]*\)", blank, text)                 # цели ссылок
    # Содержимое кавычек-ёлочек: имена объектов, прямые цитаты дерева и речь
    # персонажей. Канон выводит их из-под правил тона и аббревиатур.
    # Кавычка может охватывать несколько строк (реплика, рассуждение студента).
    # Длина ограничена, чтобы непарная « не съела полглавы.
    text = re.sub(r"«[^»]{0,600}»", blank, text, flags=re.S)
    # Реплики диалога («— Ты что? Где хлеб?») — прямая речь персонажей,
    # а не обращение к читателю
    text = re.sub(r"^\s*[—–]\s.*$", blank, text, flags=re.M)
    return text


# ─── Правила ─────────────────────────────────────────────────────────────────

# Строго по docs/style-guide.md §3 «Голос и тон» — ничего сверх канона.
# Три группы канона проверяются раздельно: канцелярит и шаблонные зачины
# однозначны, пустые усиления зависят от контекста («не так очевидно, как
# кажется» — законная фраза), поэтому у них своя, более мягкая серьёзность.
PHRASES = {
    "clerical": (["следует отметить", "представляется целесообразным",
                  "осуществляется", "производится"],
                 "канцелярит"),
    "opener":   (["в данном параграфе мы рассмотрим", "в данном разделе мы рассмотрим",
                  "в этом разделе мы рассмотрим", "в этом параграфе мы рассмотрим"],
                 "шаблонный зачин"),
    "filler":   (["по сути своей", "безусловно", "несомненно", "очевидно"],
                 "пустое усиление"),
}

RULES = [
    # (код, регулярное выражение, сообщение)
    ("address", r"(?<![А-Яа-яЁё0-9%\-])(ты|тебя|тебе|тобой|твой|твоя|твоё|твои|твоего|твоей|твоих)(?![А-Яа-яЁё])",
     "обращение «{m}» — канон серии: авторское «мы» + «вы»"),
    # Дефис и цифра слева исключают числовые окончания: «10%-я скидка», «2-я форма»
    ("address", r"(?<![А-Яа-яЁё0-9%\-])я(?![А-Яа-яЁё])",
     "авторское «я» — используйте «мы»"),
    ("address", r"(?<![А-Яа-яЁё0-9%\-])(меня|мне|мной|мною|мой|моя|моё|мои|моего|моей|моих|моим)(?![А-Яа-яЁё])",
     "первое лицо единственного числа «{m}» — канон серии: «мы» / «нас» / «наш»"),
    # Точка с заглавной справа — синтаксис платформы («РН.Остатки»), не проза
    ("abbrev", r"(?<![А-Яа-яЁё])(РС|РН|РБ|РР)(?![А-Яа-яЁё])(?!\.[А-ЯЁ])",
     "аббревиатура «{m}» в прозе — пишите полное название"),
    ("crossref", r"(см\.\s*§|как было в\s*§|как мы видели в\s*§|вернитесь к\s*§)",
     "ссылка «{m}» вместо краткого повтора здесь же"),
    ("emoji", "[\U0001F300-\U0001FAFF☀-➿]",
     "эмодзи «{m}» в основном тексте"),
]


def check_file(path, cfg):
    raw = open(path, encoding="utf-8").read()
    text = strip_uncheckable(raw)
    lines = text.split("\n")
    findings = []
    allow = {k: set(v) for k, v in (cfg.get("allow") or {}).items()}

    def sev(code):
        return cfg["severity"].get(code, DEFAULT_SEVERITY.get(code, "warning"))

    for code, pattern, msg in RULES:
        if sev(code) == "off":
            continue
        for i, line in enumerate(lines, 1):
            for m in re.finditer(pattern, line, re.I):
                hit = m.group(0)
                if hit in allow.get(code, ()):
                    continue
                findings.append((sev(code), path, i, m.start() + 1, code,
                                 msg.format(m=hit)))

    for code, (phrases, label) in PHRASES.items():
        if sev(code) == "off":
            continue
        for i, line in enumerate(lines, 1):
            for phrase in phrases:
                # Границы слова с учётом кириллицы: «неочевидно» не ловится
                # на «очевидно», «производится» — на «водится»
                pat = r"(?<![А-Яа-яЁё])" + re.escape(phrase) + r"(?![А-Яа-яЁё])"
                m = re.search(pat, line, re.I)
                if m:
                    findings.append((sev(code), path, i, m.start() + 1, code,
                                     f"{label}: «{phrase}»"))

    # Тяжёлое форматирование. Канон возражает против дробления мысли на короткие
    # пункты, а не против нумерации как таковой: пункт списка длиной в абзац —
    # это проза, и в метрику он не идёт. Порог длины «короткого» пункта — 200
    # символов, примерно два предложения.
    if sev("heavy") != "off":
        body = "\n".join(l for l in lines if l.strip())
        if len(body) > 500:
            marked = sum(len(m.group(0)) for m in re.finditer(r"\*\*[^*\n]+\*\*", body))
            for l in body.split("\n"):
                if re.match(r"\s*([-*+]|\d+\.)\s", l) and len(l.strip()) < 200:
                    marked += len(l)
            share = marked / len(body)
            if share > 0.25:
                findings.append((sev("heavy"), path, 1, 1, "heavy",
                                 f"короткие пункты и жирный — {share:.0%} объёма "
                                 f"(канон: не более 25%, книга — проза)"))
    return findings


# ─── Вывод ───────────────────────────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    fmt = "text"
    if "--format" in argv:
        fmt = argv[argv.index("--format") + 1]
    strict = "--warnings-as-errors" in argv
    paths = [a for a in argv if not a.startswith("--")
             and a not in ("text", "github")]

    root = os.getcwd()
    cfg = load_config(root)
    if not cfg["enabled"]:
        print("style-lint: отключён в metadata.yaml (style_lint.enabled: false)")
        return 0

    files = []
    for p in (paths or ["chapters"]):
        if os.path.isdir(p):
            files += sorted(glob.glob(os.path.join(p, "**", "*.md"), recursive=True))
        elif p.endswith(".md"):
            files.append(p)
    if not files:
        print("style-lint: не найдено ни одного .md")
        return 0

    findings = []
    for f in files:
        findings += check_file(f, cfg)

    errors = [f for f in findings if f[0] == "error"]
    warns = [f for f in findings if f[0] == "warning"]

    for severity, path, line, col, code, msg in findings:
        if fmt == "github":
            kind = "error" if severity == "error" else "warning"
            print(f"::{kind} file={path},line={line},col={col},title={code}::{msg}")
        else:
            mark = "✗" if severity == "error" else "!"
            print(f"{mark} {path}:{line}:{col}  [{code}] {msg}")

    print(f"\nstyle-lint: {len(files)} файлов, "
          f"{len(errors)} ошибок, {len(warns)} предупреждений")
    if errors:
        return 1
    if strict and warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
