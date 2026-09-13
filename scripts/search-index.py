#!/usr/bin/env python3
"""Поисковый индекс для сайта книги.

Родной поиск mdBook русский текст не видит вовсе: индекс собирается
английским конвейером elasticlunr, и всё, что не латиница, отбрасывается
ещё на сборке — в готовом searchindex.json нет ни одного русского слова.
Поэтому индекс собираем сами.

Единица поиска — раздел параграфа (то, что под заголовком второго уровня):
читатель ищет «быстрый выбор», а попасть должен не на страницу, а в место.

Основы слов приводим здесь, на сборке, алгоритмом Портера для русского
(Snowball). Клиенту отдаём словарь «слово → основа», чтобы на странице не
пришлось повторять тот же алгоритм ещё раз на другом языке.

Запуск: python3 scripts/search-index.py book [metadata.yaml]
"""

import json
import os
import re
import sys
from html.parser import HTMLParser

# ─── Основы слов (Snowball, русский) ──────────────────────────────────────

VOWELS = set("аеиоуыэюяё")

PERFECTIVE_1 = ("вшись", "вши", "в")
PERFECTIVE_2 = ("ившись", "ывшись", "ивши", "ывши", "ив", "ыв")
ADJECTIVE = (
    "ими", "ыми", "его", "ого", "ему", "ому", "ее", "ие", "ые", "ое", "ей",
    "ий", "ый", "ой", "ем", "им", "ым", "ом", "их", "ых", "ую", "юю", "ая",
    "яя", "ою", "ею",
)
PARTICIPLE_1 = ("ющ", "нн", "вш", "ем", "щ")
PARTICIPLE_2 = ("ивш", "ывш", "ующ")
REFLEXIVE = ("ся", "сь")
VERB_1 = (
    "ешь", "нно", "ете", "йте", "ла", "на", "ли", "ем", "ло", "но", "ет",
    "ют", "ны", "ть", "й", "л", "н",
)
VERB_2 = (
    "ейте", "уйте", "ила", "ыла", "ена", "ите", "или", "ыли", "ило", "ыло",
    "ено", "ует", "уют", "ены", "ить", "ыть", "ишь", "ей", "уй", "ил", "ыл",
    "им", "ым", "ен", "ят", "ит", "ыт", "ую", "ю",
)
NOUN = (
    "иями", "ями", "ами", "иях", "ях", "ах", "ией", "иям", "ием", "ию", "ья",
    "ье", "ью", "ия", "ев", "ов", "ие", "еи", "ии", "ей", "ой", "ий", "ям",
    "ем", "ам", "ом", "а", "е", "и", "й", "о", "у", "ы", "ь", "ю", "я",
)
SUPERLATIVE = ("ейше", "ейш")
DERIVATIONAL = ("ость", "ост")


def _regions(word):
    """RV — после первой гласной, R2 — по правилу Snowball."""
    rv = r1 = r2 = len(word)
    for i in range(len(word)):
        if word[i] in VOWELS:
            rv = i + 1
            break
    for i in range(1, len(word)):
        if word[i] not in VOWELS and word[i - 1] in VOWELS:
            r1 = i + 1
            break
    for i in range(r1 + 1, len(word)):
        if word[i] not in VOWELS and word[i - 1] in VOWELS:
            r2 = i + 1
            break
    return rv, r2


def _cut(word, rv, endings, need_a_ya=False):
    """Снимает первое подходящее окончание, если оно целиком внутри RV."""
    for end in sorted(endings, key=len, reverse=True):
        if not word.endswith(end):
            continue
        cut = len(word) - len(end)
        if cut < rv:
            continue
        if need_a_ya:
            if cut == 0 or word[cut - 1] not in "ая":
                continue
            cut -= 1
        return word[:cut], True
    return word, False


def stem(word):
    word = word.replace("ё", "е")
    if len(word) < 4 or not re.match(r"^[а-я]+$", word):
        return word
    rv, r2 = _regions(word)

    base, done = _cut(word, rv, PERFECTIVE_2)
    if not done:
        base, done = _cut(word, rv, PERFECTIVE_1, need_a_ya=True)
    if not done:
        base, _ = _cut(word, rv, REFLEXIVE)
        for endings, need in (
            (PARTICIPLE_2, False), (PARTICIPLE_1, True),
            (ADJECTIVE, False),
            (VERB_2, False), (VERB_1, True),
            (NOUN, False),
        ):
            base, done = _cut(base, rv, endings, need_a_ya=need)
            if done:
                break

    if base.endswith("и") and len(base) - 1 >= rv:
        base = base[:-1]

    for end in DERIVATIONAL:
        if base.endswith(end) and len(base) - len(end) >= r2:
            base = base[: -len(end)]
            break

    if base.endswith("нн"):
        base = base[:-1]
    else:
        for end in SUPERLATIVE:
            if base.endswith(end):
                base = base[: -len(end)]
                break
        if base.endswith("нн"):
            base = base[:-1]
    if base.endswith("ь") and len(base) - 1 >= rv:
        base = base[:-1]

    return base if len(base) >= 3 else word


TOKEN = re.compile(r"[0-9a-zа-яё]+", re.I)


def tokens(text):
    return [t.lower().replace("ё", "е") for t in TOKEN.findall(text)]


# ─── Разбор собранных страниц ─────────────────────────────────────────────

SKIP_TAGS = {"script", "style", "nav"}
BLOCK_TAGS = {
    "p", "li", "h1", "h2", "h3", "h4", "td", "th", "pre", "blockquote", "div",
    "tr", "br",
}


class PageReader(HTMLParser):
    """Достаёт из страницы mdBook разделы: заголовок, якорь и текст."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # глубина внутри <main>
        self.skip = 0
        self.title = ""
        self.sections = []      # [{'h': заголовок, 'a': якорь, 'x': [куски]}]
        self._cur = None
        self._heading = None    # уровень собираемого заголовка
        self._anchor = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "main":
            self.depth = 1
            return
        if not self.depth:
            return
        self.depth += 1
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if tag in BLOCK_TAGS and self._cur is not None and not self._heading:
            self._cur["x"].append(" ")
        if tag in ("h1", "h2"):
            self._heading = tag
            self._anchor = attrs.get("id", "")
            self._cur = {"h": [], "a": self._anchor, "x": []}
            if tag == "h2":
                self.sections.append(self._cur)
        elif tag == "a" and self._heading and not self._anchor:
            href = attrs.get("href", "")
            if href.startswith("#"):
                self._anchor = href[1:]
                if self._cur is not None:
                    self._cur["a"] = self._anchor

    def handle_endtag(self, tag):
        if tag == "main":
            self.depth = 0
            return
        if not self.depth:
            return
        self.depth -= 1
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1
            return
        if tag in BLOCK_TAGS and self._cur is not None and not self._heading:
            self._cur["x"].append(" ")
        if tag in ("h1", "h2") and self._heading == tag:
            if tag == "h1":
                self.title = " ".join("".join(self._cur["h"]).split())
                # Текст до первого подзаголовка — это «Открытие» параграфа, а в
                # некоторых книгах и весь параграф: без него поиск слеп.
                self._cur = {"h": "", "a": "", "x": []}
                self.sections.append(self._cur)
            else:
                self._cur["h"] = " ".join("".join(self._cur["h"]).split())
            self._heading = None

    def handle_data(self, data):
        if not self.depth or self.skip:
            return
        if self._heading:
            self._cur["h"].append(data)
        elif self._cur is not None:
            self._cur["x"].append(data)

    def close_page(self):
        for s in self.sections:
            if isinstance(s["h"], list):
                s["h"] = " ".join("".join(s["h"]).split())
            s["x"] = " ".join("".join(s["x"]).split())
        return self.sections


def chapter_titles(meta_path):
    try:
        import yaml
        meta = yaml.safe_load(open(meta_path, encoding="utf-8")) or {}
        return {str(k): str(v) for k, v in (meta.get("modules") or {}).items()}
    except Exception:
        return {}


def build(book_dir, meta_path):
    chapters = chapter_titles(meta_path)
    docs = []

    for root, _dirs, files in os.walk(book_dir):
        for name in sorted(files):
            if not name.endswith(".html") or name in ("404.html", "print.html"):
                continue
            path = os.path.join(root, name)
            url = os.path.relpath(path, book_dir).replace(os.sep, "/")
            html = open(path, encoding="utf-8", errors="ignore").read()
            reader = PageReader()
            reader.feed(html)
            sections = reader.close_page()
            if not reader.title and not sections:
                continue
            folder = url.split("/")[1] if url.startswith("chapters/") else ""
            chapter = chapters.get(folder, "")
            for s in sections:
                text = s["x"][:2500]
                if not text and not s["h"]:
                    continue
                docs.append({
                    "u": url + ("#" + s["a"] if s["a"] else ""),
                    "t": reader.title,
                    "c": chapter,
                    "h": s["h"],
                    "x": text,
                })

    words = {}
    for d in docs:
        for w in tokens(d["t"] + " " + d["h"] + " " + d["x"]):
            if w not in words:
                words[w] = stem(w)

    return {
        "v": 1,
        "docs": docs,
        # словарь строкой: так он вдвое короче, чем объектом JSON
        "w": "\n".join(f"{w}\t{s}" for w, s in sorted(words.items()) if w != s),
    }


def main():
    book_dir = sys.argv[1] if len(sys.argv) > 1 else "book"
    meta_path = sys.argv[2] if len(sys.argv) > 2 else "metadata.yaml"
    if not os.path.isdir(book_dir):
        print(f"Нет каталога {book_dir} — индекс не собран", file=sys.stderr)
        return 1

    index = build(book_dir, meta_path)
    out = os.path.join(book_dir, "search-index.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(out) // 1024
    print(f"Поисковый индекс: {len(index['docs'])} разделов, {size} КБ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
