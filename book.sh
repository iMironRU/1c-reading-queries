#!/usr/bin/env bash
# =============================================================================
#  book.sh — единая точка входа для управления книгой
#  Использование:
#    ./book.sh                 интерактивное меню
#    ./book.sh <команда>       прямой вызов
#
#  Команды:
#    init      Инициализировать книгу (заполнить metadata.yaml)
#    status    Показать прогресс по главам
#    build     Собрать форматы локально
#    release   Выпустить версию (changelog + git tag)
#    sync      Проверить и применить обновления шаблона
#    help      Справка
# =============================================================================
set -euo pipefail

# ─── Цвета ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}→${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}!${RESET} $*"; }
error()   { echo -e "${RED}✗${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

# ─── Вспомогательные функции ────────────────────────────────────────────────
require_cmd() {
    for cmd in "$@"; do
        if ! command -v "$cmd" &>/dev/null; then
            error "Не найдена команда: $cmd"
            error "Установите недостающие зависимости и повторите."
            exit 1
        fi
    done
}

read_meta() {
    # Читает поле из metadata.yaml через Python
    python3 -c "
import yaml, sys
def get(obj, path, default=None):
    for k in path.split('.'):
        if isinstance(obj, dict): obj = obj.get(k, default)
        else: return default
    return obj
with open('metadata.yaml') as f:
    d = yaml.safe_load(f)
val = get(d, '$1', '${2:-}')
print('' if val is None else val)
"
}

check_metadata() {
    if [[ ! -f metadata.yaml ]]; then
        error "Файл metadata.yaml не найден. Запустите: ./book.sh init"
        exit 1
    fi
}

# ─── INIT ───────────────────────────────────────────────────────────────────
cmd_init() {
    header "Инициализация книги"

    # Разбор флагов
    local title="" author="" author_url="" language="ru" version="0.1.0"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title)    title="$2";      shift 2 ;;
            --author)   author="$2";     shift 2 ;;
            --url)      author_url="$2"; shift 2 ;;
            --lang)     language="$2";   shift 2 ;;
            *) warn "Неизвестный флаг: $1"; shift ;;
        esac
    done

    # Интерактивный ввод для незаполненных полей
    [[ -z "$title" ]]      && read -rp "  Название книги: " title
    [[ -z "$author" ]]     && read -rp "  Автор: " author
    [[ -z "$author_url" ]] && read -rp "  Ссылка на профиль (GitHub/сайт): " author_url

    echo ""
    echo "  Язык: ru (русский) / en (английский)"
    read -rp "  Язык [ru]: " lang_input
    [[ -n "$lang_input" ]] && language="$lang_input"

    # Какие форматы включить
    echo ""
    echo "  Форматы для сборки (нажмите Enter = оставить по умолчанию):"
    local epub=true fb2=true pdf_a5=true pdf_a4=false
    local html=true docx=true site=true

    ask_bool() {
        local _prompt="$1" _default="$2" _v
        read -rp "    ${_prompt} [${_default}]: " _v
        case "${_v:-$_default}" in
            y|Y|yes|YES|true|True|TRUE)    echo "true"  ;;
            n|N|no|NO|false|False|FALSE)   echo "false" ;;
            *)                             echo "$_default" ;;
        esac
    }
    epub=$(ask_bool "EPUB" "$epub")
    fb2=$(ask_bool "FB2" "$fb2")
    pdf_a5=$(ask_bool "PDF A5" "$pdf_a5")
    pdf_a4=$(ask_bool "PDF A4" "$pdf_a4")
    html=$(ask_bool "HTML (один файл)" "$html")
    docx=$(ask_bool "DOCX" "$docx")
    site=$(ask_bool "Сайт (mdBook, GitHub Pages)" "$site")

    # Параметры сайта
    local site_url=""
    if [[ "$site" == "true" ]]; then
        read -rp "  URL сайта (GitHub Pages): " site_url
    fi

    # Получить текущую версию шаблона из git tag
    local tmpl_ver
    tmpl_ver=$(git describe --tags --match "template-v*" --abbrev=0 2>/dev/null || echo "v0.1.0")

    # Записать metadata.yaml
    cat > metadata.yaml << YAML
title: "${title}"
subtitle: ""
author: "${author}"
author_url: "${author_url}"
language: ${language}
license: "CC BY 4.0"
version: "0.1.0"

template_repo: "https://github.com/iMironRU/book-template"
template_version: "${tmpl_ver}"

formats:
  epub:     ${epub}
  fb2:      ${fb2}
  pdf_a5:   ${pdf_a5}
  pdf_a4:   ${pdf_a4}
  html:     ${html}
  docx:     ${docx}
  docx_a4:  false
  site:     ${site}

release_filter: "review"
nightly_filter: "all"

artifacts: []

site_url: "${site_url}"

nightly:
  enabled: true
  branch: "main"

pdf:
  font_main: "PT Serif"
  font_mono: "JetBrains Mono"
  font_size: "11pt"
  margin_a5: "top=20mm,right=15mm,bottom=20mm,left=20mm"
  margin_a4: "top=25mm,right=20mm,bottom=25mm,left=25mm"
YAML

    # Очистить placeholder-главу
    rm -f chapters/00_intro/00-01_primer.md
    cat > chapters/00_intro/00-01_vvedenie.md << MD
---
status: draft
---

# Введение

> Замените этот текст содержимым первой главы.
MD

    # Заменить README шаблона на README книги (reader-first формат)
    cat > README.md << BOOKREADME
# ${title}

<img src="assets/img/cover.png" width="180" align="right" alt="Обложка">

> Краткое описание книги — замените этот текст одной строкой.

[![Статус](https://img.shields.io/badge/статус-черновик-yellow)](CHANGELOG.md)
[![Версия](https://img.shields.io/badge/версия-0.1.0-blue)](CHANGELOG.md)
[![Лицензия](https://img.shields.io/badge/лицензия-CC_BY_4.0-green)](https://creativecommons.org/licenses/by/4.0/)

<br clear="right">

---

## Как читать

| Формат | Ссылка |
|--------|--------|
| 🌐 Онлайн | [Открыть сайт](${site_url}) |
| 📖 EPUB | [Releases → последняя версия](../../releases/latest) |
| 📄 PDF A5 | [Releases → последняя версия](../../releases/latest) |
| 📋 FB2 | [Releases → последняя версия](../../releases/latest) |
| 📝 DOCX | [Releases → последняя версия](../../releases/latest) |

---

## О книге

Замените этот раздел кратким описанием: для кого книга, главная идея, что читатель получит.

---

## Прогресс

| Модуль | Название | §§ | Статус |
|:------:|----------|:--:|:------:|
| 0 | Введение | 1 | ✏️ черновик |

---

## Обратная связь

Замечания, ошибки, предложения — [открыть Issue](../../issues/new).

---

## Лицензия

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — читать, распространять, адаптировать с указанием авторства.

---

<details>
<summary>Для контрибьюторов и разработчиков</summary>

### Собрать локально

Требования: \`pandoc\`, \`python3\` + \`pyyaml\`, \`mdbook\`.

\`\`\`bash
git clone <этот-репозиторий> && cd <папка>
./book.sh status   # прогресс по главам
./book.sh build    # собрать все форматы
\`\`\`

### Структура репозитория

\`\`\`
chapters/      — параграфы (NN_модуль/NN-MM_параграф.md)
assets/img/    — обложка и иллюстрации
spec/          — конституция, спецификация, журнал решений
\`\`\`

### Сборка на GitHub

При создании тега \`v*\` GitHub Actions автоматически собирает все форматы и публикует Release.

### Автор

[${author}](${author_url})

</details>
BOOKREADME

    success "Книга инициализирована!"
    echo ""
    info "Следующие шаги:"
    echo "   1. Заполните spec/constitution.md — принципы книги"
    echo "   2. Заполните spec/specification.md — для кого и о чём"
    echo "   3. Откройте chapters/ и начните писать"
    echo "   4. Запустите ./book.sh status — чтобы видеть прогресс"
}

# ─── STATUS ─────────────────────────────────────────────────────────────────
cmd_status() {
    check_metadata

    header "Прогресс книги: $(read_meta 'title')"
    echo ""

    local total=0 ready=0 review=0 draft=0
    local col_w=50

    printf "  %-${col_w}s %-8s\n" "Глава" "Статус"
    printf "  %s\n" "$(printf '─%.0s' $(seq 1 $((col_w + 10))))"

    # Перебрать все md-файлы в chapters/ по порядку
    while IFS= read -r -d '' file; do
        local rel="${file#chapters/}"

        # Извлечь статус из frontmatter
        local status
        status=$(python3 -c "
import sys, re
content = open('${file}').read()
m = re.search(r'^---.*?status:\s*(\w+).*?---', content, re.DOTALL)
print(m.group(1) if m else 'unknown')
" 2>/dev/null || echo "unknown")

        # Заголовок первой # строки
        local title_line
        title_line=$(grep -m1 "^# " "$file" 2>/dev/null | sed 's/^# //' || echo "$rel")

        # Иконка статуса
        local icon color
        case "$status" in
            ready)   icon="✅"; color="$GREEN"; ((ready++)) ;;
            review)  icon="🔍"; color="$YELLOW"; ((review++)) ;;
            draft)   icon="✏️ "; color="$BLUE"; ((draft++)) ;;
            *)       icon="❓"; color="$RED" ;;
        esac

        printf "  ${color}%-${col_w}s${RESET} %s %s\n" \
            "${title_line:0:$((col_w-1))}" "$icon" "$status"
        ((total++))

    done < <(find chapters -name "*.md" ! -name "_*.md" -print0 | sort -z)

    echo ""
    printf "  %s\n" "$(printf '─%.0s' $(seq 1 $((col_w + 10))))"
    printf "  Итого: ${BOLD}%d${RESET} глав   " "$total"
    printf "${GREEN}%d ready${RESET}  " "$ready"
    printf "${YELLOW}%d review${RESET}  " "$review"
    printf "${BLUE}%d draft${RESET}\n\n" "$draft"

    # Процент завершения
    if [[ $total -gt 0 ]]; then
        local pct=$(( (ready * 100) / total ))
        local bar_len=40
        local filled=$(( (ready * bar_len) / total ))
        local bar
        bar=$(printf '█%.0s' $(seq 1 $filled))$(printf '░%.0s' $(seq 1 $((bar_len - filled))))
        printf "  Готово: [${GREEN}%s${RESET}] %d%%\n\n" "$bar" "$pct"
    fi
}

# ─── BUILD ───────────────────────────────────────────────────────────────────
cmd_build() {
    check_metadata
    require_cmd python3 pandoc

    local filter="${1:-all}"
    header "Сборка книги (фильтр: ${filter})"

    local title version
    title=$(read_meta 'title')
    version=$(read_meta 'version')
    # Явный slug из metadata.yaml — приоритет
    local slug
    slug=$(read_meta 'slug' '')
    if [[ -z "$slug" ]]; then
        slug=$(echo "$title" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
        # Фолбек для кириллических названий (нет букв латиницы) — имя папки репо
        if [[ ! "$slug" =~ [a-z]{2,} ]]; then
            slug=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
        fi
    fi

    mkdir -p dist

    # Собрать список файлов по статусу
    local file_list=()
    while IFS= read -r -d '' file; do
        local status
        status=$(python3 -c "
import re
content = open('${file}').read()
m = re.search(r'^---.*?status:\s*(\w+).*?---', content, re.DOTALL)
print(m.group(1) if m else 'ready')
" 2>/dev/null || echo "ready")
        case "$filter" in
            ready)  [[ "$status" == "ready" ]] && file_list+=("$file") ;;
            review) [[ "$status" == "ready" || "$status" == "review" ]] && file_list+=("$file") ;;
            all)    file_list+=("$file") ;;
        esac
    done < <(find chapters -name "*.md" ! -name "_*.md" -print0 | sort -z)

    if [[ ${#file_list[@]} -eq 0 ]]; then
        warn "Нет файлов для сборки с фильтром '${filter}'"
        exit 0
    fi

    info "Собирается ${#file_list[@]} глав..."

    local rev="${version}"
    local base="dist/${slug}_v${rev}"

    # Общие флаги pandoc
    local pandoc_flags=(
        --metadata-file=metadata.yaml
        --toc
        --toc-depth=3
        --standalone
    )

    # Cover image
    [[ -f assets/img/cover.png ]] && \
        pandoc_flags+=(--epub-cover-image=assets/img/cover.png)

    fmt() { read_meta "formats.$1"; }

    # EPUB
    if [[ "$(fmt epub)" == "True" || "$(fmt epub)" == "true" ]]; then
        info "EPUB..."
        pandoc "${file_list[@]}" "${pandoc_flags[@]}" -o "${base}.epub"
        success "→ ${base}.epub"
    fi

    # FB2
    if [[ "$(fmt fb2)" == "True" || "$(fmt fb2)" == "true" ]]; then
        info "FB2..."
        pandoc "${file_list[@]}" --metadata-file=metadata.yaml --toc -o "${base}.fb2"
        success "→ ${base}.fb2"
    fi

    # HTML
    if [[ "$(fmt html)" == "True" || "$(fmt html)" == "true" ]]; then
        info "HTML..."
        pandoc "${file_list[@]}" "${pandoc_flags[@]}" \
            --embed-resources -o "${base}.html"
        success "→ ${base}.html"
    fi

    # DOCX
    if [[ "$(fmt docx)" == "True" || "$(fmt docx)" == "true" ]]; then
        info "DOCX..."
        pandoc "${file_list[@]}" "${pandoc_flags[@]}" -o "${base}.docx"
        success "→ ${base}.docx"
    fi

    # PDF A5
    if [[ "$(fmt pdf_a5)" == "True" || "$(fmt pdf_a5)" == "true" ]]; then
        if command -v xelatex &>/dev/null; then
            info "PDF A5..."
            local margin; margin=$(read_meta 'pdf.margin_a5')
            if pandoc "${file_list[@]}" "${pandoc_flags[@]}" \
                -V papersize=a5 \
                -V "geometry:${margin}" \
                -V mainfont="$(read_meta 'pdf.font_main')" \
                -V monofont="$(read_meta 'pdf.font_mono')" \
                -V fontsize="$(read_meta 'pdf.font_size')" \
                --pdf-engine=xelatex \
                -o "${base}_a5.pdf"; then
                success "→ ${base}_a5.pdf"
            else
                warn "PDF A5 не собран — ошибка xelatex (см. лог выше)"
            fi
        else
            warn "xelatex не найден, PDF пропущен. Установите TeX Live."
        fi
    fi

    # PDF A4
    if [[ "$(fmt pdf_a4)" == "True" || "$(fmt pdf_a4)" == "true" ]]; then
        if command -v xelatex &>/dev/null; then
            info "PDF A4..."
            local margin_a4; margin_a4=$(read_meta 'pdf.margin_a4')
            if pandoc "${file_list[@]}" "${pandoc_flags[@]}" \
                -V papersize=a4 \
                -V "geometry:${margin_a4}" \
                -V mainfont="$(read_meta 'pdf.font_main')" \
                -V monofont="$(read_meta 'pdf.font_mono')" \
                -V fontsize="$(read_meta 'pdf.font_size')" \
                --pdf-engine=xelatex \
                -o "${base}_a4.pdf"; then
                success "→ ${base}_a4.pdf"
            else
                warn "PDF A4 не собран — ошибка xelatex (см. лог выше)"
            fi
        else
            warn "xelatex не найден, PDF A4 пропущен."
        fi
    fi

    # DOCX A4 (требует assets/reference-a4.docx для полей; без него — стандартный DOCX)
    if [[ "$(fmt docx_a4)" == "True" || "$(fmt docx_a4)" == "true" ]]; then
        info "DOCX A4..."
        local ref_arg=()
        [[ -f assets/reference-a4.docx ]] && ref_arg=(--reference-doc=assets/reference-a4.docx)
        pandoc "${file_list[@]}" "${pandoc_flags[@]}" "${ref_arg[@]}" -o "${base}_a4.docx"
        success "→ ${base}_a4.docx"
    fi

    # Сайт mdBook
    if [[ "$(fmt site)" == "True" || "$(fmt site)" == "true" ]]; then
        if command -v mdbook &>/dev/null; then
            info "Сайт (mdBook)..."
            _generate_summary "$filter"
            _inject_version "$version"
            mdbook build
            success "→ book/ (mdBook site)"
        else
            warn "mdbook не найден. Установите: https://rust-lang.github.io/mdBook/guide/installation.html"
        fi
    fi

    echo ""
    success "Сборка завершена. Файлы в dist/"
}

_generate_summary() {
    local filter="${1:-all}"
    info "Генерация SUMMARY.md..."
    {
        echo "# Содержание"
        echo ""
        echo "- [О книге](README.md)"
        echo ""
        local prev_module=""
        while IFS= read -r -d '' file; do
            local status
            status=$(python3 -c "
import re
content = open('${file}').read()
m = re.search(r'^---.*?status:\s*(\w+).*?---', content, re.DOTALL)
print(m.group(1) if m else 'ready')
" 2>/dev/null || echo "ready")
            local include=false
            case "$filter" in
                ready)  [[ "$status" == "ready" ]] && include=true ;;
                review) [[ "$status" == "ready" || "$status" == "review" ]] && include=true ;;
                all)    include=true ;;
            esac
            [[ "$include" != "true" ]] && continue

            local rel="${file}"
            local module; module=$(echo "$file" | cut -d/ -f2)
            local title_line; title_line=$(grep -m1 "^# " "$file" 2>/dev/null | sed 's/^# //')
            [[ -z "$title_line" ]] && title_line=$(basename "${file%.md}" | sed 's/^[0-9-]*_*//')

            if [[ "$module" != "$prev_module" ]]; then
                local module_title; module_title=$(echo "$module" | sed 's/^[0-9]*_//' | tr '_' ' ')
                [[ -n "$prev_module" ]] && echo ""
                echo "## $module_title"
                echo ""
                prev_module="$module"
            fi

            # Добавить иконку статуса
            local label="$title_line"
            [[ "$status" == "draft" ]] && label="✏️ $title_line (черновик)"
            [[ "$status" == "review" ]] && label="🔍 $title_line"

            echo "- [${label}](${rel})"
        done < <(find chapters -name "*.md" ! -name "_*.md" -print0 | sort -z)
    } > SUMMARY.md
}

_inject_version() {
    local version="$1"
    # Создать файл с версией, который mdBook включает в footer
    mkdir -p theme
    cat > theme/version.js << JS
document.addEventListener('DOMContentLoaded', function() {
    var footer = document.querySelector('.nav-wrapper') || document.body;
    var versionBadge = document.createElement('div');
    versionBadge.style.cssText = 'text-align:center;padding:8px;font-size:0.8em;opacity:0.6;';
    versionBadge.innerHTML = 'Версия <strong>v${version}</strong> · <a href="../CHANGELOG.md">Что изменилось</a>';
    document.body.appendChild(versionBadge);
});
JS
}

# ─── RELEASE ─────────────────────────────────────────────────────────────────
cmd_release() {
    check_metadata
    require_cmd git python3

    local current_version; current_version=$(read_meta 'version')
    header "Выпуск новой версии (текущая: v${current_version})"

    # Уровень версии
    echo ""
    echo "  Выберите уровень изменений:"
    echo "    patch  — исправления, уточнения, опечатки"
    echo "    minor  — новые главы, значительная переработка"
    echo "    major  — структурная реорганизация, смена концепции"
    read -rp "  Уровень [patch]: " level
    level="${level:-patch}"

    # Вычислить новую версию
    IFS='.' read -r major minor patch <<< "$current_version"
    case "$level" in
        patch) ((patch++)) ;;
        minor) ((minor++)); patch=0 ;;
        major) ((major++)); minor=0; patch=0 ;;
        *) error "Неверный уровень: $level"; exit 1 ;;
    esac
    local new_version="${major}.${minor}.${patch}"

    echo ""
    info "Новая версия: ${BOLD}v${new_version}${RESET}"
    echo ""

    # Changelog
    echo "  Что изменилось в этой версии?"
    echo "  (Введите пункты по одному, пустая строка — завершить)"
    echo ""
    local changes=()
    while true; do
        read -rp "  > " line
        [[ -z "$line" ]] && break
        changes+=("$line")
    done

    if [[ ${#changes[@]} -eq 0 ]]; then
        warn "Changelog пуст. Продолжить без записей? (y/N)"
        read -rp "  " confirm
        [[ "$confirm" != "y" && "$confirm" != "Y" ]] && { info "Отменено."; exit 0; }
    fi

    # Добавить запись в CHANGELOG.md
    local date; date=$(date +%Y-%m-%d)
    # Запись в файл — обходит проблему спецсимволов (кавычки, слэши) в Python
    local entry_file; entry_file=$(mktemp)
    {
        printf "## [v%s] — %s\n\n" "${new_version}" "${date}"
        for change in "${changes[@]}"; do
            printf "- %s\n" "${change}"
        done
        printf "\n"
    } > "$entry_file"

    if [[ -f CHANGELOG.md ]]; then
        # Вставить после первого заголовка
        ENTRY_FILE="$entry_file" python3 - << 'PY'
import os, re
entry = open(os.environ['ENTRY_FILE']).read()
with open('CHANGELOG.md', 'r') as f:
    content = f.read()
m = re.search(r'^(# .+\n)', content, re.MULTILINE)
if m:
    new_content = content[:m.end()] + '\n' + entry + content[m.end():]
else:
    new_content = entry + content
with open('CHANGELOG.md', 'w') as f:
    f.write(new_content)
PY
    else
        { printf "# Журнал изменений\n\n"; cat "$entry_file"; } > CHANGELOG.md
    fi
    rm -f "$entry_file"

    # Обновить версию в metadata.yaml
    python3 - << PY
import yaml, re
with open('metadata.yaml', 'r') as f:
    content = f.read()
new_content = re.sub(r'^version:\s*"[^"]*"', 'version: "${new_version}"', content, flags=re.MULTILINE)
with open('metadata.yaml', 'w') as f:
    f.write(new_content)
PY

    # Git
    echo ""
    local dirty; dirty=$(git status --porcelain 2>/dev/null | grep -v "^??" || true)
    if [[ -n "$dirty" ]]; then
        warn "Есть незакоммиченные изменения:"
        echo "$dirty" | sed 's/^/     /'
        echo ""
        warn "Они НЕ попадут в релизный коммит. Продолжить? (y/N)"
        read -rp "  " _confirm
        [[ "$_confirm" != "y" && "$_confirm" != "Y" ]] && { info "Отменено."; exit 0; }
    fi
    info "Создаю коммит и тег..."
    git add metadata.yaml CHANGELOG.md
    git commit -m "release: v${new_version}"
    git tag -a "v${new_version}" -m "v${new_version}"

    echo ""
    success "Версия v${new_version} готова!"
    echo ""
    info "Для отправки на GitHub:"
    echo "   git push && git push origin v${new_version}"
    echo ""
    info "GitHub Actions соберёт все форматы и создаст Release."
}

# ─── SYNC ────────────────────────────────────────────────────────────────────
cmd_sync() {
    check_metadata
    require_cmd python3 curl

    local tmpl_repo; tmpl_repo=$(read_meta 'template_repo')
    local current_tmpl; current_tmpl=$(read_meta 'template_version')

    header "Синхронизация с шаблоном"
    info "Текущая версия шаблона: ${current_tmpl}"
    info "Источник: ${tmpl_repo}"
    echo ""

    # Получить список релизов через GitHub API
    local repo_path; repo_path=$(echo "$tmpl_repo" | sed 's|https://github.com/||')
    local api_url="https://api.github.com/repos/${repo_path}/releases"

    local releases_json
    releases_json=$(curl -sf "$api_url" 2>/dev/null || echo "[]")

    local latest_tag tmp_json; tmp_json=$(mktemp)
    printf '%s' "$releases_json" > "$tmp_json"
    latest_tag=$(python3 - "$tmp_json" 2>/dev/null << 'PY'
import json, sys
with open(sys.argv[1]) as f:
    releases = json.load(f)
tags = [r['tag_name'] for r in releases if not r.get('prerelease')]
print(tags[0] if tags else '')
PY
) || latest_tag=""
    rm -f "$tmp_json"

    if [[ -z "$latest_tag" ]]; then
        warn "Не удалось получить информацию о релизах шаблона."
        warn "Проверьте подключение или откройте ${tmpl_repo}/releases вручную."
        exit 1
    fi

    if [[ "$latest_tag" == "$current_tmpl" ]]; then
        success "Шаблон актуален (${current_tmpl})"
        exit 0
    fi

    info "Доступна новая версия шаблона: ${BOLD}${latest_tag}${RESET}"
    echo ""

    # Получить список изменённых файлов из template-changes.yaml шаблона
    local raw_base; raw_base=$(echo "$tmpl_repo" | sed 's|github.com|raw.githubusercontent.com|')
    local changes_url="${raw_base}/main/template-changes.yaml"
    local changes_yaml
    changes_yaml=$(curl -sf "$changes_url" 2>/dev/null || echo "")

    if [[ -z "$changes_yaml" ]]; then
        warn "Не найден файл template-changes.yaml в шаблоне."
        warn "Обновите шаблон вручную: ${tmpl_repo}"
        exit 1
    fi

    # Найти файлы изменившиеся с current_tmpl по latest_tag
    local changed_files tmp_yaml; tmp_yaml=$(mktemp)
    printf '%s' "$changes_yaml" > "$tmp_yaml"
    changed_files=$(python3 - "$tmp_yaml" "$current_tmpl" "$latest_tag" << 'PY'
import yaml, sys
with open(sys.argv[1]) as f:
    changes = yaml.safe_load(f) or {}
current = sys.argv[2]
latest  = sys.argv[3]

versions = sorted(changes.keys())
collecting = False
files = set()
for v in versions:
    if v == current:
        collecting = True
        continue
    if collecting:
        for action in ['added', 'changed']:
            files.update(changes.get(v, {}).get(action, []))
    if v == latest:
        break

for f in sorted(files):
    print(f)
PY
)
    rm -f "$tmp_yaml"

    if [[ -z "$changed_files" ]]; then
        warn "Нет данных об изменениях. Просмотрите CHANGELOG шаблона вручную."
        exit 0
    fi

    echo "  Файлы, изменившиеся в шаблоне с ${current_tmpl} по ${latest_tag}:"
    echo ""

    local applied=()
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        local file_url="${raw_base}/main/${file}"
        echo -n "  Применить ${BOLD}${file}${RESET}? (y/N/d для просмотра diff): "
        read -rn1 answer; echo ""
        case "$answer" in
            d|D)
                local remote_content; remote_content=$(curl -sf "$file_url" || echo "")
                diff <(cat "$file" 2>/dev/null || echo "") <(echo "$remote_content") || true
                echo -n "  Применить? (y/N): "
                read -rn1 apply; echo ""
                [[ "$apply" == "y" || "$apply" == "Y" ]] && {
                    mkdir -p "$(dirname "$file")"
                    curl -sf "$file_url" > "$file"
                    applied+=("$file")
                }
                ;;
            y|Y)
                mkdir -p "$(dirname "$file")"
                curl -sf "$file_url" > "$file"
                applied+=("$file")
                ;;
        esac
    done <<< "$changed_files"

    if [[ ${#applied[@]} -gt 0 ]]; then
        echo ""
        success "Применено файлов: ${#applied[@]}"

        # Обновить template_version в metadata.yaml
        python3 - << PY
import re
with open('metadata.yaml', 'r') as f:
    content = f.read()
new_content = re.sub(
    r'^template_version:\s*"[^"]*"',
    'template_version: "${latest_tag}"',
    content, flags=re.MULTILINE
)
with open('metadata.yaml', 'w') as f:
    f.write(new_content)
PY
        success "template_version обновлена до ${latest_tag}"
    else
        info "Ничего не применено."
    fi
}

# ─── HELP ────────────────────────────────────────────────────────────────────
show_help() {
    echo ""
    echo -e "  ${BOLD}book.sh${RESET} — управление книгой"
    echo ""
    echo "  Команды:"
    echo -e "    ${CYAN}init${RESET}              Инициализировать книгу (заполнить metadata.yaml)"
    echo -e "    ${CYAN}status${RESET}            Показать прогресс по главам"
    echo -e "    ${CYAN}build [фильтр]${RESET}    Собрать форматы (ready | review | all)"
    echo -e "    ${CYAN}release${RESET}           Выпустить версию (changelog + git tag)"
    echo -e "    ${CYAN}sync${RESET}              Проверить и применить обновления шаблона"
    echo -e "    ${CYAN}help${RESET}              Эта справка"
    echo ""
    echo "  Флаги для init:"
    echo "    --title «Название»"
    echo "    --author «Автор»"
    echo "    --url https://github.com/профиль"
    echo "    --lang ru | en"
    echo ""
}

# ─── Интерактивное меню ──────────────────────────────────────────────────────
show_menu() {
    header "📚 Управление книгой"
    [[ -f metadata.yaml ]] && echo "   $(read_meta 'title') v$(read_meta 'version')" || echo "   (книга не инициализирована)"
    echo ""
    echo "   1. Инициализировать книгу"
    echo "   2. Прогресс по главам"
    echo "   3. Собрать форматы локально"
    echo "   4. Выпустить версию"
    echo "   5. Проверить обновления шаблона"
    echo "   0. Выход"
    echo ""
    read -rp "  Выбор: " choice
    case "$choice" in
        1) cmd_init ;;
        2) cmd_status ;;
        3) read -rp "  Фильтр (ready/review/all) [all]: " f; cmd_build "${f:-all}" ;;
        4) cmd_release ;;
        5) cmd_sync ;;
        0) exit 0 ;;
        *) warn "Неверный выбор" ;;
    esac
}

# ─── Точка входа ─────────────────────────────────────────────────────────────
COMMAND="${1:-}"
shift 2>/dev/null || true

case "$COMMAND" in
    init)    cmd_init "$@" ;;
    status)  cmd_status ;;
    build)   cmd_build "${1:-all}" ;;
    release) cmd_release ;;
    sync)    cmd_sync ;;
    help)    show_help ;;
    "")      show_menu ;;
    *)       error "Неизвестная команда: ${COMMAND}"; show_help; exit 1 ;;
esac
