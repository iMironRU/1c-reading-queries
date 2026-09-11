#!/usr/bin/env python3
"""Ссылки в песочницу под исполнимыми запросами.

Каждый блок ```запрос,песочница``` получает под собой строку-ссылку: она
открывает песочницу с этим запросом и учебной базой книги. Ссылка живёт в
самом тексте, а не собирается на лету, поэтому одинаково работает во всех
форматах — сайт, EPUB, PDF, DOCX — и видна в истории правок.

Скрипт идемпотентен: ставит ссылку, где её нет, и обновляет, где текст
запроса изменился. Запускается ./book.sh sandbox-links; в CI прогоняется с
--check и падает, если ссылки разошлись с запросами.

Настройки — в metadata.yaml:

    sandbox:
      url: "https://imiron.ru/BSLexicon/query/"
      schema_src: "https://raw.githubusercontent.com/…/base.schema.yaml"
      data_src:   "https://raw.githubusercontent.com/…/base.data.yaml"

Значения параметров — в assets/sandbox/parameters.yaml, по строке на имя:

    НаДату: "d:2026-04-30T23:59:59"
    Склад:  "r:Справочник.Склады:w_main"

Если запрос содержит «&Имя», а значение для него задано, ссылка несёт его
параметром p.Имя — песочница откроется с уже заполненной панелью.
"""
import base64
import glob
import gzip
import os
import re
import sys
import urllib.parse

PARAMS_FILE = "assets/sandbox/parameters.yaml"
PARAM_IN_QUERY = re.compile(r"&([^\W\d]\w*)")

FENCE = re.compile(r"^```запрос,песочница\n(.*?)^```[ \t]*$", re.S | re.M)
LINK_LINE = re.compile(r"^\[▶ [^\]]*\]\(([^)]*)\)[ \t]*$", re.M)
LABEL = "▶ Выполнить в песочнице"


def read_meta(path="metadata.yaml"):
    """Плоское чтение нужных ключей: без PyYAML, его может не быть."""
    meta, section = {}, None
    for line in open(path, encoding="utf-8"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            section = line.split(":")[0].strip()
            value = line.split(":", 1)[1].strip().strip('"')
            if value:
                meta[section] = value
            continue
        key, _, value = line.strip().partition(":")
        meta[f"{section}.{key.strip()}"] = value.strip().strip('"')
    return meta


def read_params(path=PARAMS_FILE):
    """Плоский «Имя: "значение"» без PyYAML."""
    if not os.path.exists(path):
        return {}
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip('"')
    return out


def query_params(query, defaults):
    """Пары p.Имя=значение для параметров, встретившихся в запросе, по порядку."""
    seen, pairs = set(), []
    for name in PARAM_IN_QUERY.findall(query):
        if name in seen or name not in defaults:
            continue
        seen.add(name)
        pairs.append((f"p.{name}", defaults[name]))
    return pairs


def encode(query):
    packed = gzip.compress(query.encode("utf-8"), mtime=0)
    return base64.b64encode(packed).decode().replace("+", "-").replace("/", "_").rstrip("=")


def decode(gzq):
    """Обратно из параметра в текст запроса. Побайтно сжатие у разных
    сборок python отличается, поэтому ссылки сверяются по смыслу: что
    в них лежит, а не какими байтами это записано."""
    std = gzq.replace("-", "+").replace("_", "/")
    std += "=" * ((4 - len(std) % 4) % 4)
    try:
        return gzip.decompress(base64.b64decode(std)).decode("utf-8")
    except Exception:
        return None


def same_link(existing, query, meta, title, source, defaults=None):
    """Ведёт ли уже стоящая ссылка туда же, куда повела бы новая."""
    try:
        parts = urllib.parse.urlsplit(existing)
        params = dict(urllib.parse.parse_qsl(parts.query))
    except ValueError:
        return False
    if parts.scheme + "://" + parts.netloc + parts.path != meta.get(
            "sandbox.url", "https://imiron.ru/BSLexicon/query/"):
        return False
    if decode(params.get("gzq", "")) != query:
        return False
    for key, name in (("sandbox.schema_src", "schema-src"), ("sandbox.data_src", "data-src")):
        if params.get(name, "") != (meta.get(key) or ""):
            return False
    want = dict(query_params(query, defaults or {}))
    have = {k: v for k, v in params.items() if k.startswith("p.")}
    if want != have:
        return False
    return params.get("source", "") == (source or "") and params.get("title", "") == (title or "")


def page_url(site_url, path):
    """Адрес страницы книги на сайте — для баннера «из книги»."""
    if not site_url:
        return None
    rel = os.path.splitext(path)[0] + ".html"
    return site_url.rstrip("/") + "/" + rel.replace(os.sep, "/")


def build_link(meta, query, title, source, defaults=None):
    params = [("gzq", encode(query))]
    for key, name in (("sandbox.schema_src", "schema-src"), ("sandbox.data_src", "data-src")):
        if meta.get(key):
            params.append((name, meta[key]))
    params += query_params(query, defaults or {})
    if source:
        params.append(("source", source))
    if title:
        params.append(("title", title))
    base = meta.get("sandbox.url", "https://imiron.ru/BSLexicon/query/")
    return f"[{LABEL}]({base}?{urllib.parse.urlencode(params)})"


def process(path, meta, check, defaults):
    raw = open(path, encoding="utf-8").read()
    title = next(iter(re.findall(r"^# (.+)$", raw, re.M)), None)
    source = page_url(meta.get("site_url"), path)

    out, pos, changed = [], 0, 0
    for m in FENCE.finditer(raw):
        out.append(raw[pos:m.end()])
        pos = m.end()
        link = build_link(meta, m.group(1).strip(), title, source, defaults)

        tail = raw[pos:]
        existing = LINK_LINE.match(tail.lstrip("\n"))
        if existing:
            skip = len(tail) - len(tail.lstrip("\n")) + existing.end()
            if same_link(existing.group(1), m.group(1).strip(), meta, title, source, defaults):
                out.append(tail[:skip])
                pos += skip
                continue
            pos += skip
            changed += 1
        else:
            changed += 1
        out.append("\n\n" + link)
    out.append(raw[pos:])

    new = "".join(out)
    if new != raw and not check:
        open(path, "w", encoding="utf-8").write(new)
    return changed


def main():
    check = "--check" in sys.argv
    meta = read_meta()
    if not meta.get("sandbox.schema_src"):
        print("В metadata.yaml нет раздела sandbox — ссылки не ставлю.")
        return 0

    defaults = read_params()
    total = 0
    for path in sorted(glob.glob("chapters/*/*.md")):
        total += process(path, meta, check, defaults)

    if check and total:
        print(f"Ссылки в песочницу разошлись с запросами: {total}. Выполните ./book.sh sandbox-links")
        return 1
    print(f"Ссылок обновлено: {total}" if total else "Все ссылки на месте.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
