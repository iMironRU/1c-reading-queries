#!/usr/bin/env python3
"""Прогон параграфа книги через обойму редакторов параллельно.

Обойма (каждый редактор видит только свою ось — это и есть смысл панели):
  - DeepSeek (deepseek-chat)   — фактчек платформы 1С
  - GPT-5.5  (structure)       — архитектура текста, переходы
  - GPT-5.5  (metaphor)        — устойчивость образов
  - GPT-5.5  (tone)            — звучание (опционально, флаг --tone)
  - GPT-5.5  (style)           — стиль и канон (опционально, флаг --style)
  - Gemini 2.5 Flash           — адверсар + читатель-первокурсник

Usage:
    python3 scripts/review.py 2.4            # § по номеру → chapters/*/02-04_*.md
    python3 scripts/review.py 02-04          # тот же приём, по префиксу файла
    python3 scripts/review.py chapters/02_semantika/02-04_perevod.md
    python3 scripts/review.py 2.4 --tone --style

Output: reviews/<label>/{deepseek,gpt55-structure,gpt55-metaphor,...}.md
Дальше Claude собирает synthesis.md из отчётов.

Требования:
  - Python 3, .env в корне с ключами:
      DEEPSEEK_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY
    (нужны только те ключи, чьи редакторы участвуют в прогоне)
"""
import os
import re
import sys
import json
import time
import glob
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent.resolve()
PROMPTS = ROOT / "scripts" / "prompts"
REVIEWS = ROOT / "reviews"
CHAPTERS = ROOT / "chapters"

# Модель семейства GPT, используется для ролевых редакторов.
# Переопределяется переменной окружения OPENAI_MODEL.
GPT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.5")


def load_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        sys.exit("Error: .env не найден в корне репозитория.")
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def http_post(url, headers, body, timeout=900, retries=3):
    data = json.dumps(body).encode("utf-8")
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            last_err = f"HTTP {e.code}: {err_body[:1500]}"
            if e.code in (429, 503) and attempt < retries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(last_err) from None
    raise RuntimeError(last_err)


def call_deepseek(system_prompt, user_content):
    key = os.environ["DEEPSEEK_API_KEY"]
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": 8000,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = http_post("https://api.deepseek.com/v1/chat/completions", headers, body)
    return resp["choices"][0]["message"]["content"]


def call_openai(model, system_prompt, user_content):
    """GPT-5.x семья использует max_completion_tokens вместо max_tokens."""
    key = os.environ["OPENAI_API_KEY"]
    is_gpt5 = model.startswith("gpt-5")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
    }
    if is_gpt5:
        body["max_completion_tokens"] = 8000
    else:
        body["temperature"] = 0.3
        body["max_tokens"] = 8000
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = http_post("https://api.openai.com/v1/chat/completions", headers, body)
    return resp["choices"][0]["message"]["content"]


def call_gemini(system_prompt, user_content):
    key = os.environ["GEMINI_API_KEY"]
    model = "gemini-2.5-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8000},
    }
    headers = {"Content-Type": "application/json"}
    resp = http_post(url, headers, body)
    cands = resp.get("candidates") or []
    if not cands:
        return f"# Gemini вернул пустой ответ\n\n```\n{json.dumps(resp)[:2000]}\n```"
    parts = cands[0].get("content", {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts)


def read_optional(path):
    return path.read_text() if path.exists() else ""


def build_context(paragraph_text, paragraph_label):
    constitution  = read_optional(ROOT / "spec" / "constitution.md")
    specification = read_optional(ROOT / "spec" / "specification.md")
    claude_md     = read_optional(ROOT / "CLAUDE.md")
    style_guide   = read_optional(ROOT / "docs" / "style-guide.md")
    return f"""# КОНТЕКСТ КНИГИ

## CLAUDE.md (рабочие соглашения, канон, стиль)

```markdown
{claude_md}
```

## spec/constitution.md (контракт книги)

```markdown
{constitution}
```

## spec/specification.md (целевой читатель и метрики)

```markdown
{specification}
```

## docs/style-guide.md (требования к стилю)

```markdown
{style_guide}
```

---

# ПАРАГРАФ НА ПРОВЕРКУ: {paragraph_label}

```markdown
{paragraph_text}
```

---

Дай отчёт по своей роли строго в указанном формате. Отвечай по-русски.
"""


def resolve_path(arg):
    """Принимает: полный/относительный путь, либо § вида '2.4' / '02-04'.

    Для шортката ищет chapters/*/NN-MM_*.md по префиксу.
    """
    # 1. Явный путь
    p = Path(arg)
    if not p.is_absolute():
        p_abs = ROOT / p
    else:
        p_abs = p
    if p_abs.exists() and p_abs.is_file():
        rel = p_abs.resolve().relative_to(ROOT).as_posix()
        return rel, Path(rel).stem.split("_")[0]

    # 2. Шорткат § — нормализуем '2.4' / '2-4' / '02.04' → '02-04'
    m = re.fullmatch(r"(\d{1,2})[.\-](\d{1,2})", arg)
    if m:
        prefix = f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        matches = sorted(glob.glob(str(CHAPTERS / "*" / f"{prefix}_*.md")))
        if len(matches) == 1:
            rel = Path(matches[0]).resolve().relative_to(ROOT).as_posix()
            return rel, prefix
        if len(matches) > 1:
            sys.exit(f"Неоднозначно: '{arg}' → {matches}")

    sys.exit(
        f"Error: '{arg}' — не файл и не § вида '2.4'.\n"
        f"Примеры: 2.4 | 02-04 | chapters/02_semantika/02-04_perevod.md"
    )


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        sys.exit(f"Usage: {sys.argv[0]} <§ '2.4' | путь> [--tone] [--style]")
    load_env()

    rel_path, label = resolve_path(args[0])
    para_file = ROOT / rel_path
    paragraph_text = para_file.read_text()
    context = build_context(paragraph_text, f"§{label}  ({rel_path})")

    def gpt(role_prompt_file):
        return lambda: call_openai(
            GPT_MODEL, (PROMPTS / role_prompt_file).read_text(), context
        )

    # Базовая обойма
    editors = {
        "deepseek": (
            lambda: call_deepseek((PROMPTS / "deepseek-fact.md").read_text(), context),
            "DeepSeek — фактчек 1С",
        ),
        "gpt55-structure": (gpt("openai-structure.md"), "GPT — структура"),
        "gpt55-metaphor":  (gpt("openai-metaphor.md"),  "GPT — метафоры"),
        "gemini": (
            lambda: call_gemini((PROMPTS / "gemini-adversary.md").read_text(), context),
            "Gemini — адверсар + читатель",
        ),
    }
    # Опциональные редакторы
    if "--tone" in flags:
        editors["gpt55-tone"] = (gpt("openai-tone.md"), "GPT — тон и ритм")
    if "--style" in flags:
        editors["gpt55-style"] = (gpt("openai-style.md"), "GPT — стиль и канон")

    out_dir = REVIEWS / label
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n→ Параграф: §{label}  ({rel_path})")
    print(f"→ Редакторы: {len(editors)}  (параллельно)\n")

    results = {}
    with ThreadPoolExecutor(max_workers=len(editors)) as ex:
        futures = {ex.submit(fn): (name, lbl) for name, (fn, lbl) in editors.items()}
        for fut in futures:
            name, lbl = futures[fut]
            t0 = time.monotonic()
            try:
                results[name] = fut.result()
                secs = time.monotonic() - t0
                print(f"  ✓ {lbl:<34} {len(results[name]):>6} симв.  ({secs:.1f}s)")
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                results[name] = f"# ОШИБКА вызова\n\n```\n{err[:2000]}\n```\n"
                print(f"  ✗ {lbl:<34} {err[:80]}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for name, content in results.items():
        path = out_dir / f"{name}.md"
        path.write_text(f"<!-- generated {stamp} -->\n\n{content}\n")
        print(f"  → {path.relative_to(ROOT)}")

    print(
        f"\nГотово. Отчёты в {out_dir.relative_to(ROOT)}/. "
        f"Дальше — Claude собирает synthesis.md.\n"
    )


if __name__ == "__main__":
    main()
