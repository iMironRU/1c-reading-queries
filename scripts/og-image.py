#!/usr/bin/env python3
"""Картинка для ссылки на книгу (Open Graph).

Обложка книги вертикальная, а ссылку мессенджеры показывают широкой
карточкой: в неё обложка не встаёт. Рисуем отдельную карточку 1200×630 в том
же оформлении, что и обложка серии.

Картинка меняется редко — файл кладётся в assets/img/og.png и коммитится,
на сборочной машине браузера нет.

Запуск: python3 scripts/og-image.py [metadata.yaml]
"""

import html
import os
import subprocess
import sys
import tempfile

CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
]

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
  :root {{ --paper:#E4C68D; --navy:#16283A; --red:#A02D26; --ink:#12202E; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ width:1200px; height:630px; overflow:hidden; }}
  body {{ background:var(--paper); color:var(--navy); position:relative;
         font-family:"Arial Narrow", Arial, sans-serif; }}
  .grain {{ position:absolute; inset:0; opacity:.10; pointer-events:none;
    background-image:radial-gradient(#8a6a3a 1px,transparent 1px),
                     radial-gradient(#fff 1px,transparent 1px);
    background-size:7px 7px,11px 11px; background-position:0 0,3px 5px; }}
  .spine {{ position:absolute; left:0; top:0; bottom:0; width:26px;
    background:linear-gradient(90deg,#0d1a26,#16283A 60%,#0f1d2b); }}
  .page {{ position:absolute; left:26px; right:0; top:0; bottom:0;
    padding:44px 56px; display:flex; flex-direction:column; }}
  .rule {{ background:var(--navy); height:8px; }}
  .rule.red {{ background:var(--red); height:5px; margin-top:6px; }}
  .kicker {{ font-family:Impact,"Arial Narrow",sans-serif; font-size:30px;
    letter-spacing:.08em; text-transform:uppercase; padding:26px 0 0; color:var(--ink); }}
  .title {{ font-family:Impact,"Arial Narrow",sans-serif; text-transform:uppercase;
    line-height:.94; letter-spacing:.005em; font-size:{size}px; padding-top:16px; }}
  .title .mark {{ color:var(--red); }}
  .sub {{ font-family:Impact,"Arial Narrow",sans-serif; color:var(--red);
    font-size:40px; letter-spacing:.02em; text-transform:uppercase; padding-top:18px; }}
  .pitch {{ font-size:31px; line-height:1.34; color:var(--ink); padding-top:30px;
    max-width:920px; }}
  .foot {{ margin-top:auto; display:flex; justify-content:space-between;
    align-items:flex-end; font-size:26px; letter-spacing:.03em; }}
  .foot .author {{ font-family:Impact,"Arial Narrow",sans-serif; font-size:30px;
    letter-spacing:.05em; }}
  .foot .site {{ font-family:Menlo,"Courier New",monospace; font-size:22px; color:var(--ink); }}
</style></head><body>
  <div class="spine"></div>
  <div class="page">
    <div class="rule"></div><div class="rule red"></div>
    <div class="kicker">{series}</div>
    <div class="title">{title}</div>
    <div class="sub">{subtitle}</div>
    <div class="pitch">{pitch}</div>
    <div class="foot">
      <span class="author">{author}</span>
      <span class="site">{site}</span>
    </div>
    <div class="rule red" style="margin-top:22px"></div><div class="rule"></div>
  </div>
  <div class="grain"></div>
</body></html>
"""


def chrome():
    for path in CHROME:
        if os.path.exists(path):
            return path
        found = subprocess.run(["which", path], capture_output=True, text=True)
        if found.returncode == 0:
            return found.stdout.strip()
    return None


def readme_pitch(path="README.md", limit=180):
    """Одно предложение о книге: берём из README, чтобы не заводить копию."""
    import re
    if not os.path.exists(path):
        return ""
    text = re.sub(r"(?s)\A---.*?---\n", "", open(path, encoding="utf-8").read())
    # README, оставшийся от шаблона, рассказывает про шаблон, а не про книгу
    if re.search(r"^#\s.*book-template", text, flags=re.M):
        return ""
    for block in text.split("\n\n"):
        # по канону серии строка о книге стоит цитатой сразу под названием
        block = " ".join(re.sub(r"(?m)^>\s?", "", block).split())
        # значки статуса, ссылки и таблицы — не текст о книге
        if len(block) < 60 or not block or block[0] in "#*[|-!":
            continue
        if "](" in block or "http" in block:
            continue
        block = re.sub(r"<[^>]+>", "", block)
        block = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", block)
        block = re.sub(r"[*_`]", "", block).strip()
        # README, который ещё не переписан под книгу, рассказывает о шаблоне
        if "Шаблон репозитория" in block or "Use this template" in block:
            continue
        if len(block) < 60:
            continue
        if len(block) > limit:
            block = block[:limit].rsplit(" ", 1)[0] + "…"
        return block
    return ""


def main():
    meta_path = sys.argv[1] if len(sys.argv) > 1 else "metadata.yaml"
    import yaml
    data = yaml.safe_load(open(meta_path, encoding="utf-8")) or {}

    title = str(data.get("title") or "Книга")
    subtitle = str(data.get("subtitle") or "")
    author = str(data.get("author") or "")
    author = author.split("(")[0].strip()
    site = str(data.get("site_url") or "").replace("https://", "").rstrip("/")
    # Строка серии — только если книга и правда в серии.
    series = str(data.get("series") or "")
    pitch = str(data.get("pitch") or "") or readme_pitch()

    # «1С» в названии — красным, как на обложке
    marked = title.replace("1С", '<span class="mark">1С</span>')
    size = 104 if len(title) <= 18 else (86 if len(title) <= 26 else 62)

    page = PAGE.format(title=marked, subtitle=html.escape(subtitle),
                       author=html.escape(author), site=html.escape(site),
                       series=html.escape(series), size=size,
                       pitch=html.escape(pitch))

    out_dir = os.path.join("assets", "img")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "og.png")

    binary = chrome()
    if not binary:
        print("Chrome не найден — карточка не нарисована", file=sys.stderr)
        return 1

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as tmp:
        tmp.write(page)
        tmp_path = tmp.name
    try:
        subprocess.run([
            binary, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--window-size=1200,630", f"--screenshot={out}", f"file://{tmp_path}",
        ], check=True, capture_output=True)
    finally:
        os.unlink(tmp_path)

    print(f"Карточка ссылки: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
