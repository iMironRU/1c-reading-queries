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
    # Ссылка назад по номеру. ВЫКЛЮЧЕНО по умолчанию: отличить вредный голый
    # указатель («Подробно — в § 2.2») от безвредной ссылки с пересказом рядом
    # («В § 1.4 мы собрали скелет — измерения, ресурсы, реквизиты») машина не
    # умеет — нужно человеческое суждение. Включайте разово, для аудита:
    #   style_lint: {severity: {backref: warning}}
    "backref": "off",
    "telling": "warning",   # рассказ там, где нужен показ
    "clerical": "error",    # канцелярит
    "opener": "error",      # шаблонные зачины
    "filler": "warning",    # пустые усиления — сильно зависят от контекста
    "emoji": "warning",
    "heavy": "warning",
    "wide": "warning",
    "kitchen": "error",
    "agree": "warning",     # разметки больше четверти объёма
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
    # ВАЖЕН ПОРЯДОК. Реплики диалога вычищаем ПЕРВЫМИ, по исходным началам строк.
    # Если сделать наоборот, затёртая многострочная кавычка оставит в начале
    # строки пробелы и тире — и правило про диалог съест обычный текст вместе
    # с нарушениями в нём.
    text = re.sub(r"^[—–]\s.*$", blank, text, flags=re.M)
    # Содержимое кавычек-ёлочек: имена объектов, прямые цитаты дерева и речь
    # персонажей. Канон выводит их из-под правил тона и аббревиатур.
    # Кавычка может охватывать несколько строк; длина ограничена, чтобы
    # непарная « не съела полглавы.
    text = re.sub(r"«[^»]{0,600}»", blank, text, flags=re.S)
    # Выноска целиком курсивом («> *Считай сумму покупки…*») — цитата-образец:
    # словесная задача, чужая формулировка, требование «как его написал заказчик».
    # Это предъявляемый материал, а не речь автора.
    text = re.sub(r"^\s*>\s*\*[^*\n]+\*\s*$", blank, text, flags=re.M)
    return text


# ─── Правила ─────────────────────────────────────────────────────────────────

# Существительные на -шь: не глаголы, в правило адресации не попадают.
NOT_VERBS = {"мышь", "рожь", "ложь", "глушь", "фальшь", "брошь", "тушь", "сушь",
             "блажь", "дрожь", "мощь", "помощь", "ночь", "дочь", "плешь", "гуашь"}

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
    # Повелительное наклонение единственного числа — та же адресация на «ты».
    # Список явный: регекс по окончанию задел бы существительные на -и/-й/-ь.
    ("address",
     r"(?<![А-Яа-яЁё])(назови|опиши|объясни|сформулируй|перечисли|укажи|приведи|"
     r"выпиши|раздели|сравни|проверь|подумай|заметь|попробуй|посмотри|представь|"
     r"вспомни|запиши|нарисуй|начерти|исправь|дополни|переделай|отметь|выдели|"
     r"поставь|реши|разбери|собери|напиши|прочитай|перечитай|отложи|запомни|"
     r"учти|возьми|найди|открой|создай|добавь|проведи|выбери|скажи|спроси|"
     r"держи|начни|смотри|лезь|заведи|используй|давай|дай|сделай|прочти|"
     r"спроектируй|придумай|посчитай|определи|выясни|составь|заполни|настрой|"
     r"измени|замени|перенеси|сохрани|закрой|включи|выключи|нажми|введи|"
     r"выполни|запусти|установи|разверни|сверни|обрати|"
     r"возвращайся|вернись|обратись|присмотрись|приглядись|разберись|"
     r"зови|оборачивай|подставляй|смешивай|соединяй|путай|забывай|клади|ищи|бери|"
     r"убедись|попытайся|остановись|задумайся)"
     r"(?![А-Яа-яЁёйьте])",
     "повелительное наклонение «{m}» в единственном числе — форма на «вы»"),
    ("abbrev", r"(?<![А-Яа-яЁё])(РС|РН|РБ|РР)(?![А-Яа-яЁё])(?!\.[А-ЯЁ])",
     "аббревиатура «{m}» в прозе — пишите полное название"),
    # Ссылки на параграфы проверяются отдельно, с учётом направления —
    # см. check_backrefs(): назад нельзя, вперёд можно.
    ("emoji", "[\U0001F300-\U0001FAFF☀-➿]",
     "эмодзи «{m}» в основном тексте"),
]


def para_key(s):
    """«C1» → (2, 1); «2.4» → (0, 2, 4). Позволяет сравнить два номера параграфа."""
    m = re.fullmatch(r"([A-ZА-Я]?)\s*(\d+)(?:[.\-](\d+))?", s.strip())
    if not m:
        return None
    letter = m.group(1)
    phase = ord(letter) - ord("A") + 1 if letter and letter.isascii() else 0
    return (phase, int(m.group(2)), int(m.group(3) or 0))


def check_mixed_address(text, path, sev):
    """Глагол 2 лица единственного числа в одной фразе с «вы» — рассогласование:
    «вы не идёшь». Само по себе «бежишь глазами по странице» законно: это
    обобщённо-личное предложение, оно значит «любой», а не «ты». Отличить их
    можно только по соседству с «вы», поэтому проверяем именно его."""
    findings = []
    # Markdown переносит строки жёстко, поэтому одна фраза часто разорвана на
    # две строки. Ищем по абзацу целиком, номер строки считаем по смещению.
    for pm in re.finditer(r"(?:^|\n\n)(.+?)(?=\n\n|$)", text, re.S):
        para, base = pm.group(1), text[:pm.start(1)].count("\n") + 1
        flat = para.replace("\n", " ")
        for sent in re.split(r"(?<=[.!?;])\s+", flat):
            if not re.search(r"(?<![А-Яа-яЁё])(вы|вас|вам|ваш\w*)(?![А-Яа-яЁё])", sent, re.I):
                continue
            for m in re.finditer(r"(?<![А-Яа-яЁё])([А-Яа-яЁё]{2,}(?:ешься|ёшься|ишься|ешь|ёшь|ишь))(?![А-Яа-яЁё])", sent):
                if m.group(1).lower() in NOT_VERBS:
                    continue
                off = para.find(m.group(1))
                line_no = base + (para[:off].count("\n") if off >= 0 else 0)
                findings.append((sev, path, line_no, 1, "address",
                                 f"«{m.group(1)}» — глагол единственного числа рядом с «вы»"))
    return findings


def check_backrefs(raw, text, path, sev):
    """Ссылка назад по номеру заставляет читателя идти искать и терять мысль.
    Вперёд — обещание, искать нечего. Отличаем одно от другого по номерам."""
    findings = []
    h1 = re.search(r"^#\s*§?\s*([A-ZА-Я]?\s*\d+(?:[.\-]\d+)?)", raw, re.M)
    here = para_key(h1.group(1)) if h1 else None
    for i, line in enumerate(text.split("\n"), 1):
        for m in re.finditer(r"§\s?([A-ZА-Я]?\s?\d+(?:[.\-]\d+)?)", line):
            there = para_key(m.group(1))
            if not there or not here or there >= here:
                continue          # вперёд или в себя — не трогаем

            # Ссылка назад вредна не сама по себе, а когда идёт БЕЗ содержания.
            # «В § 1.4 мы собрали скелет — измерения, ресурсы, реквизиты» безвредно:
            # напомнили тут же. «Подробно — в § 2.2» вредно: читателю велено идти.
            # Надёжный признак голого указателя — короткая фраза, в которую
            # содержание просто не помещается.
            sent = re.split(r"(?<=[.!?;])\s+", line)
            sent = next((s for s in sent if f"§" in s and m.group(1) in s), line)
            if len(sent.split()) >= 9:
                continue

            findings.append((sev, path, i, m.start() + 1, "backref",
                             f"голая ссылка назад «§{m.group(1)}» — повторите нужное "
                             f"кратко здесь: читатель помнит содержание, а не номер"))
    return findings


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
                if hit in allow.get(code, ()) or hit.lower() in NOT_VERBS:
                    continue
                findings.append((sev(code), path, i, m.start() + 1, code,
                                 msg.format(m=hit)))

    if sev("address") != "off":
        findings += check_mixed_address(text, path, sev("address"))

    if sev("backref") != "off":
        findings += check_backrefs(raw, text, path, sev("backref"))

    # Плотность показа: канон просит один артефакт примерно на 130 слов прозы.
    # Считаем только основной текст — в упражнениях и ответах своя логика.
    if sev("telling") != "off":
        body = re.split(r"^##\s*(?:Контрольные вопросы|Упражнения)", raw, flags=re.M)[0]
        arte = len(re.findall(r"```", body)) // 2
        # Таблица — такой же показ, как блок кода. Считаем блоками, а не
        # строками: раньше стояло «and 1», и десять таблиц шли за одну.
        arte += len(re.findall(r"(?:^\s*\|.*\|\s*$\n)+", body, re.M))
        prose = re.sub(r"```.*?```", " ", body, flags=re.S)
        prose = re.sub(r"^\s*\|.*\|\s*$", " ", prose, flags=re.M)
        prose_words = len(prose.split())
        if prose_words > 400:
            per = prose_words // max(arte, 1)
            if per > 250:
                findings.append((sev("telling"), path, 1, 1, "telling",
                                 f"один показ на {per} слов прозы — канон просит "
                                 f"около 130: параграф рассказывает там, где мог бы показать"))

    # Проектный словарь в тексте главы: книга не рассказывает читателю о себе.
    # Обсуждать подходы можно где угодно, кроме самих глав.
    if sev("kitchen") != "off" and "/docs/" not in path.replace("\\", "/"):
        KITCHEN = [
            (r"фаз[аеыу]\s+[ABC]\b", "«фаза A/B/C» — проектное слово: пишите «первая часть», «§ 2.3»"),
            # «домен» бывает и законным: DNS-домен, домен Windows. Ловим только
            # наш методический смысл — «предметная область», — и потому смотрим
            # на соседние слова, а не на само слово.
            # «домен» бывает законным — DNS-домен, домен Windows, — поэтому он
            # только предупреждение: отличить наш методический смысл от сетевого
            # машина не берётся, это решает человек.
            (r"(?<![А-Яа-яЁё])домен\w*", "«домен»: если это про предметную область — пишите «платформа», «учёт»",
             None, "warning"),
            # «крючок» → «крючка», «крючки»: беглая гласная, ловим по корню
            (r"(?<![А-Яа-яЁё])(лейбл|супра-метафор|крючо?к|крючк)\w*", "проектное слово вместо русского"),
            (r"когнитивн\w+\s+нагрузк", "методика книги — не предмет книги"),
            (r"педагогическ\w+\s+(приём|трюк|упрощени)", "методика книги — не предмет книги"),
            (r"^##\s*Мостик", "«Мостик» — не рубрика: переход пишется абзацем курсивом после ---"),
            # Заголовок называет то, что получит читатель, а не то, что делает автор.
            # «Чистка терминов», «врезка», «оговорка» — слова из редакторской кухни.
            (r"^#{2,4}[^\n]*(чистк|врезк|оговорк|анонс|ремарк|отступлени|удочк|прототип)\w*[^\n]*$",
             "заголовок описывает работу автора, а не содержание для читателя"),
            # Наши слова для отложенного объяснения. Читатель их не знает: для него
            # это просто раздел книги, а не «удочка», которую автор куда-то закинул.
            (r"(?<![А-Яа-яЁё])(удочк|зацепк|затравк|тизер|болванк|врезк)\w*",
             "наше слово для отложенного объяснения — читателю оно ничего не говорит",
             None, "warn"),
            # Словарь этапа планирования. Читатель в наших обсуждениях не участвовал.
            (r"(?<![А-Яа-яЁё])(фаза [ABCАБВ]|модул[ья] \d|концепт(?!уал)|предметк|"
             r"перв(?:ый|ого) заход|втор(?:ой|ого) заход|реврейм|минимальн\w+ доз|"
             r"дорожн\w+ карт|веха|вехи)\w*",
             "слово из нашего планирования — в книгу оно не идёт",
             None, "warn"),
            # Авторское первое лицо: канон требует «мы» и «вы».
            (r"(?<![А-Яа-яЁё])(рассказыва|объясня|показыва|разбира|напомин|замеча|поясня)ю(?![А-Яа-яЁё])",
             "первое лицо единственного числа — в книге говорят «мы»"),
        ]
        for rule in KITCHEN:
            pat, why = rule[0], rule[1]
            allow = rule[2] if len(rule) > 2 else None
            level = rule[3] if len(rule) > 3 else sev("kitchen")
            for m in re.finditer(pat, text, flags=re.M | re.I):
                if allow:
                    near = text[max(0, m.start() - 160):m.end() + 160]
                    if re.search(allow, near, flags=re.I):
                        continue
                line = text[:m.start()].count("\n") + 1
                col = m.start() - text.rfind("\n", 0, m.start())
                findings.append((level, path, line, col, "kitchen",
                                 f"«{m.group(0).strip()[:26]}» — {why}"))

    # Согласование рода после массовых замен. Проверяем по склеенному тексту:
    # в исходнике фраза часто разорвана переносом строки, и построчный поиск её
    # не видит — именно так «один общий устройство» дожил до готового EPUB.
    if sev("agree") != "off":
        flat = re.sub(r"\s+", " ", text)
        AGREE = r"(?<![А-Яа-яЁё])(тот|этот|один|общий|такой|весь|наш|каждый|любой)\s+устройств\w*"
        for m in re.finditer(AGREE, flat, flags=re.I):
            findings.append((sev("agree"), path, 1, 1, "agree",
                             f"«{m.group(0)}» — род не согласован: «устройство» среднего рода"))

    # Ширина артефакта. На телефоне в моноширинный блок влезает около 46
    # знаков. Если строка длиннее, читалка её переносит — и правая колонка
    # уезжает под левую. Для двух колонок это смерть: пары рассыпаются.
    if sev("wide") != "off":
        for m in re.finditer(r"^```([^\n]*)\n(.*?)^```", raw, flags=re.S | re.M):
            block = m.group(2)
            widest = max((len(l) for l in block.split("\n")), default=0)
            if widest <= 46:
                continue
            line = raw[:m.start()].count("\n") + 1
            rows = [l for l in block.split("\n") if l.strip()]
            lang = m.group(1).strip()
            # У кода отступы и продолжения строк выглядят как колонки, но ими не
            # являются: с ним поможет только перенос, а не таблица. И у схемы
            # с ветвлением колонок тоже нет.
            is_code = lang.startswith("bsl")
            is_scheme = any(ch in block for ch in "│┌└├┤┬┴┼┐┘↓↑→←⇒▓░")
            two_col = (not is_code and not is_scheme
                       and sum(1 for l in rows if re.search(r"\S {3,}\S", l)) >= max(2, len(rows) // 2))
            if two_col:
                findings.append((sev("wide"), path, line, 1, "wide",
                                 f"две колонки шириной {widest} знаков — на телефоне "
                                 f"правая уедет под левую; нужна настоящая таблица"))
            else:
                findings.append((sev("wide"), path, line, 1, "wide",
                                 f"артефакт шириной {widest} знаков — на телефоне "
                                 f"строка переносится (влезает около 46)"))

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
