#!/usr/bin/env python3
"""Мета-теги для страниц сайта книги.

mdBook оставляет описание страницы пустым и ничего не знает про Open Graph,
поэтому ссылка на книгу, посланная в мессенджер, выглядела голым адресом.
Разметку дописываем после сборки: заголовок страницы, первый абзац как
описание, обложку как картинку ссылки и канонический адрес.

Запуск: python3 scripts/site-meta.py book [metadata.yaml]
"""

import html
import os
import re
import sys

SKIP = {"404.html", "print.html"}
LIMIT = 200                      # столько знаков описания показывают в выдаче
EMOJI = re.compile(r"^[\W\d_]*?([«A-Za-zА-Яа-я§])", re.U)


def meta(path):
    try:
        import yaml
        return yaml.safe_load(open(path, encoding="utf-8")) or {}
    except Exception:
        return {}


def text_of(chunk):
    chunk = re.sub(r"(?s)<(script|style).*?</\1>", " ", chunk)
    chunk = re.sub(r"(?s)<[^>]+>", " ", chunk)
    return re.sub(r"\s+", " ", html.unescape(chunk)).strip()


def first_paragraph(page):
    body = re.search(r"(?s)<main[^>]*>(.*?)</main>", page)
    if not body:
        return ""
    for raw in re.findall(r"(?s)<p[^>]*>(.*?)</p>", body.group(1)):
        line = text_of(raw)
        if len(line) >= 60:
            if len(line) > LIMIT:
                line = line[:LIMIT].rsplit(" ", 1)[0] + "…"
            return line
    return ""


def page_title(page):
    found = re.search(r"(?s)<title>(.*?)</title>", page)
    if not found:
        return ""
    title = text_of(found.group(1))
    # В оглавлении у черновиков стоит значок статуса: в заголовке ссылки
    # он ни к чему.
    start = EMOJI.match(title)
    return title[start.start(1):] if start else title


def canonical(site_url, rel):
    if rel == "index.html":
        return site_url
    return site_url + rel


def tags(site_url, rel, title, description, book, cover, author):
    url = html.escape(canonical(site_url, rel), quote=True)
    esc_title = html.escape(title, quote=True)
    esc_descr = html.escape(description, quote=True)
    out = [
        f'<meta name="description" content="{esc_descr}">',
        f'<meta name="author" content="{html.escape(author, quote=True)}">',
        f'<link rel="canonical" href="{url}">',
        '<meta property="og:type" content="article">',
        f'<meta property="og:site_name" content="{html.escape(book, quote=True)}">',
        f'<meta property="og:title" content="{esc_title}">',
        f'<meta property="og:description" content="{esc_descr}">',
        f'<meta property="og:url" content="{url}">',
        '<meta property="og:locale" content="ru_RU">',
    ]
    if cover:
        out += [
            f'<meta property="og:image" content="{html.escape(cover, quote=True)}">',
            '<meta name="twitter:card" content="summary_large_image">',
        ]
    else:
        out.append('<meta name="twitter:card" content="summary">')
    out += [
        f'<meta name="twitter:title" content="{esc_title}">',
        f'<meta name="twitter:description" content="{esc_descr}">',
    ]
    return "\n        ".join(out)


def main():
    book_dir = sys.argv[1] if len(sys.argv) > 1 else "book"
    meta_path = sys.argv[2] if len(sys.argv) > 2 else "metadata.yaml"
    data = meta(meta_path)

    site_url = str(data.get("site_url") or "").strip()
    if not site_url:
        print("В metadata.yaml нет site_url — мета-теги не дописаны", file=sys.stderr)
        return 0
    if not site_url.endswith("/"):
        site_url += "/"

    book = str(data.get("title") or "")
    author = str(data.get("author") or "")
    subtitle = str(data.get("subtitle") or "")
    # Обложка книги вертикальная, а ссылку показывают широкой карточкой;
    # если нарисована карточка, берём её.
    cover = ""
    for candidate in ("og.png", "cover.png"):
        if os.path.exists(os.path.join(book_dir, "assets", "img", candidate)):
            cover = site_url + "assets/img/" + candidate
            break

    touched = 0
    for root, _dirs, files in os.walk(book_dir):
        for name in sorted(files):
            if not name.endswith(".html") or name in SKIP:
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, book_dir).replace(os.sep, "/")
            page = open(path, encoding="utf-8", errors="ignore").read()
            if 'property="og:title"' in page:
                continue

            title = page_title(page) or book
            description = first_paragraph(page)
            if rel == "index.html":
                title = f"{book}. {subtitle}" if subtitle else book
                description = description or subtitle

            block = tags(site_url, rel, title, description, book, cover, author)
            if '<meta name="description" content="">' in page:
                page = page.replace('<meta name="description" content="">', block, 1)
            else:
                page = page.replace("</head>", "        " + block + "\n    </head>", 1)
            # Светлый цвет темы на тёмном сайте красит адресную строку телефона.
            page = page.replace(
                '<meta name="theme-color" content="#ffffff">',
                '<meta name="theme-color" content="#0e0f13">', 1)

            open(path, "w", encoding="utf-8").write(page)
            touched += 1

    print(f"Мета-теги: {touched} страниц")
    return 0


if __name__ == "__main__":
    sys.exit(main())
