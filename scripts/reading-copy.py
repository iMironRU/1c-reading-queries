#!/usr/bin/env python3
"""Копия параграфа для чтения.

В исходнике пометки стоят html-комментариями: в книге и на сайте они невидимы,
но просмотрщик файлов показывает их как текст и склеивает со следующим абзацем.
Читать такое невозможно, поэтому автору уходит не исходник, а копия:

- `<!-- СКРИН: … -->` становится видимой строкой отдельным блоком;
- `<!-- FIXME стенд: … -->` уходит из текста и собирается списком в конце;
- фронтматтер снимается.

Запуск: python3 scripts/reading-copy.py chapters/02_anatomiya/02-03_*.md [ещё]
Копии складываются в dist/reading/.
"""

import os
import re
import sys

FRONT = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n\s*", re.S)
SHOT = re.compile(r"^[ \t]*<!--\s*СКРИН:\s*(.+?)\s*-->[ \t]*$", re.M | re.S)
CHECK = re.compile(r"^[ \t]*<!--\s*FIXME стенд:\s*(.+?)\s*-->[ \t]*\n?", re.M | re.S)


def convert(path, out_dir):
    text = open(path, encoding="utf-8").read()
    text = FRONT.sub("", text)

    text = SHOT.sub(
        lambda m: "> **Здесь будет снимок экрана.** " + " ".join(m.group(1).split()),
        text,
    )

    checks = [" ".join(m.group(1).split()) for m in CHECK.finditer(text)]
    text = CHECK.sub("", text)
    # после снятой пометки остаются тройные переводы строк
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"

    if checks:
        text += "\n---\n\n## На стенде проверить\n\n"
        text += "".join(f"{i}. {c}\n" for i, c in enumerate(checks, 1))

    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(path))
    open(out, "w", encoding="utf-8").write(text)
    return out, len(checks)


def main():
    paths = sys.argv[1:]
    if not paths:
        print("нечего копировать", file=sys.stderr)
        return 1
    for path in paths:
        out, checks = convert(path, os.path.join("dist", "reading"))
        print(f"{out} — пометок для стенда вынесено: {checks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
