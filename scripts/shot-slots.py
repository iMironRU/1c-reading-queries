#!/usr/bin/env python3
"""Места для снимков экрана — видимой заглушкой.

Пока книга пишется, снимков ещё нет: в тексте стоят пометки
`<!-- СКРИН: что снять -->`. Читателю черновика они невидимы, и там, где
картинка обязана быть, страница просто молчит. Заглушка честнее: она говорит,
что здесь будет снимок и какой.

Пометки для стенда (`FIXME стенд`) остаются невидимыми — это записка автору,
а не пропущенная иллюстрация.

Скелет — разметкой, и она доживает до сайта, EPUB и HTML. Форматы, которые
html не понимают (FB2, DOCX, PDF), получают ту же заглушку строкой: флаг
`--plain`. Пустого места на странице не остаётся нигде.

Запуск: python3 scripts/shot-slots.py [--plain] <каталог> [ещё каталоги]
Файлы правятся на месте, поэтому запускать только на копии для сборки.
"""

import html
import os
import re
import sys

SHOT = re.compile(r"^[ \t]*<!--\s*СКРИН:\s*(.+?)\s*-->[ \t]*$", re.M)


# Скелет окна: полоса заголовка, колонка дерева и поля справа — очертания
# того, что будет на снимке. Разметка нарочно простая: блоки с ширинами,
# без флексов и сеток, иначе часть читалок EPUB разложит её по-своему.
SKELETON = (
    '<div class="shot-skeleton">'
    '<div class="shot-titlebar"></div>'
    '<div class="shot-toolbar">'
    '<span class="shot-chip"></span><span class="shot-chip"></span>'
    '<span class="shot-chip wide"></span>'
    '</div>'
    '<div class="shot-body">'
    '<div class="shot-tree">'
    '<div class="shot-line w80"></div><div class="shot-line w60"></div>'
    '<div class="shot-line w70"></div><div class="shot-line w45"></div>'
    '<div class="shot-line w65"></div>'
    '</div>'
    '<div class="shot-pane">'
    '<div class="shot-line w50"></div><div class="shot-field"></div>'
    '<div class="shot-line w40"></div><div class="shot-field"></div>'
    '<div class="shot-line w55"></div><div class="shot-field"></div>'
    '</div>'
    '</div>'
    '</div>'
)


def slot(match):
    text = html.escape(" ".join(match.group(1).split()), quote=True)
    return (
        '<div class="shot-slot">'
        + SKELETON
        + '<span class="shot-slot-label">Здесь будет снимок экрана</span>'
        + f'<span class="shot-slot-text">{text}</span>'
        + "</div>"
    )


def slot_plain(match):
    """Для форматов без html: заглушка обычной цитатой, но с той же подписью."""
    text = " ".join(match.group(1).split())
    return "> **Здесь будет снимок экрана.** " + text


def convert(path, plain=False):
    src = open(path, encoding="utf-8").read()
    out, count = SHOT.subn(slot_plain if plain else slot, src)
    if count:
        open(path, "w", encoding="utf-8").write(out)
    return count


def main():
    args = sys.argv[1:]
    plain = "--plain" in args
    roots = [a for a in args if a != "--plain"] or ["."]
    total = 0
    for root in roots:
        if os.path.isfile(root):
            total += convert(root, plain)
            continue
        for base, _dirs, files in os.walk(root):
            for name in sorted(files):
                if name.endswith(".md"):
                    total += convert(os.path.join(base, name), plain)
    print(f"Заглушек под снимки: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
