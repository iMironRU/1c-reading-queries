// Поиск по книге, который понимает русский.
//
// Родной поиск mdBook русского текста не видит: индекс собирается английским
// конвейером, и кириллица отбрасывается ещё на сборке. Здесь свой поиск —
// по индексу, который делает scripts/search-index.py. Основы слов посчитаны
// на сборке, сюда приезжает словарь «слово → основа»: на странице тот же
// алгоритм заново не пишем.
//
// Единица выдачи — раздел параграфа, а не страница: читатель ищет «быстрый
// выбор» и должен попасть в место, а не в начало главы.
(function () {
    'use strict';

    var TOKEN = /[0-9a-zа-яё]+/gi;
    var LIMIT = 30;
    var TEASER = 240;

    var root = (typeof path_to_root === 'string' ? path_to_root : '');
    var state = { index: null, loading: null, docs: [], stems: null };
    var ui = {};

    function tokenize(text) {
        var out = [];
        var m;
        TOKEN.lastIndex = 0;
        while ((m = TOKEN.exec(text)) !== null) {
            out.push({ w: m[0].toLowerCase().replace(/ё/g, 'е'), at: m.index });
        }
        return out;
    }

    function stemOf(word) {
        var s = state.stems && state.stems.get(word);
        return s || word;
    }

    // Совпадение по основе, но снисходительное: основы однокоренных слов
    // иногда расходятся на одну букву («реквизит» и «реквизиты»), а пока
    // читатель печатает, слово вообще недописано.
    function hits(tokenStem, queryStem) {
        if (tokenStem === queryStem) {
            return true;
        }
        if (queryStem.length >= 3 && tokenStem.indexOf(queryStem) === 0) {
            return true;
        }
        return tokenStem.length >= 3 && queryStem.indexOf(tokenStem) === 0;
    }

    function load() {
        if (state.loading) {
            return state.loading;
        }
        state.loading = fetch(root + 'search-index.json')
            .then(function (r) {
                if (!r.ok) {
                    throw new Error(r.status);
                }
                return r.json();
            })
            .then(function (data) {
                state.stems = new Map();
                (data.w || '').split('\n').forEach(function (line) {
                    var pair = line.split('\t');
                    if (pair.length === 2) {
                        state.stems.set(pair[0], pair[1]);
                    }
                });
                state.docs = data.docs.map(function (d) {
                    var body = tokenize(d.x);
                    return {
                        u: d.u,
                        t: d.t,
                        c: d.c,
                        h: d.h,
                        x: d.x,
                        head: tokenize(d.t + ' ' + d.h).map(function (t) {
                            return stemOf(t.w);
                        }),
                        body: body.map(function (t) {
                            return stemOf(t.w);
                        }),
                        at: body.map(function (t) {
                            return t.at;
                        })
                    };
                });
                state.index = true;
                return state;
            });
        return state.loading;
    }

    function search(query) {
        var asked = tokenize(query).map(function (t) {
            return stemOf(t.w);
        });
        if (!asked.length) {
            return [];
        }

        var found = [];
        state.docs.forEach(function (doc) {
            var score = 0;
            var places = [];
            for (var q = 0; q < asked.length; q += 1) {
                var here = 0;
                var first = -1;
                for (var i = 0; i < doc.head.length; i += 1) {
                    if (hits(doc.head[i], asked[q])) {
                        here += 3;
                    }
                }
                for (var j = 0; j < doc.body.length; j += 1) {
                    if (hits(doc.body[j], asked[q])) {
                        here += 1;
                        if (first < 0) {
                            first = doc.at[j];
                        }
                    }
                }
                if (!here) {
                    return; // спрошенное слово в разделе не встречается
                }
                score += here;
                if (first >= 0) {
                    places.push(first);
                }
            }
            // Длинный раздел набирает попаданий просто потому, что он длинный.
            // Делим на длину, иначе «Контрольные вопросы» обходят параграф,
            // который и правда об этом.
            score /= Math.sqrt(doc.body.length + 20);
            // Ответы — не то, что читатель ищет первым: он ищет объяснение.
            if (doc.u.indexOf('_otvety') >= 0) {
                score *= 0.5;
            }
            // Вопросы и упражнения слово повторяют, но ничего не объясняют.
            if (doc.h === 'Контрольные вопросы' || doc.h === 'Упражнения') {
                score *= 0.5;
            }
            found.push({ doc: doc, score: score, at: places.length ? Math.min.apply(null, places) : 0 });
        });

        found.sort(function (a, b) {
            return b.score - a.score;
        });
        return found.slice(0, LIMIT);
    }

    function escapeHtml(text) {
        return text.replace(/[&<>"]/g, function (ch) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch];
        });
    }

    function teaser(doc, at, asked) {
        var from = Math.max(0, at - 60);
        var cut = doc.x.slice(from, from + TEASER);
        if (from > 0) {
            cut = '…' + cut.replace(/^\S*\s/, '');
        }
        if (from + TEASER < doc.x.length) {
            cut = cut.replace(/\s\S*$/, '') + '…';
        }
        var out = '';
        var last = 0;
        tokenize(cut).forEach(function (t) {
            var stem = stemOf(t.w);
            var lit = asked.some(function (q) {
                return hits(stem, q);
            });
            if (!lit) {
                return;
            }
            out += escapeHtml(cut.slice(last, t.at));
            out += '<mark>' + escapeHtml(cut.substr(t.at, t.w.length)) + '</mark>';
            last = t.at + t.w.length;
        });
        return out + escapeHtml(cut.slice(last));
    }

    function render(query) {
        var results = search(query);
        var asked = tokenize(query).map(function (t) {
            return stemOf(t.w);
        });

        if (!results.length) {
            ui.results.innerHTML = '<p class="search-empty">Ничего не нашлось. ' +
                'Попробуйте другое слово — ищется по всем словам сразу.</p>';
            ui.count.textContent = '';
            return;
        }

        ui.count.textContent = results.length === LIMIT
            ? 'первые ' + LIMIT
            : results.length + ' ' + plural(results.length, 'раздел', 'раздела', 'разделов');

        ui.results.innerHTML = results.map(function (r, i) {
            var crumb = [r.doc.c, r.doc.t].filter(Boolean).join(' · ');
            return '<a class="search-hit' + (i === 0 ? ' is-current' : '') + '" href="' +
                root + r.doc.u + '?q=' + encodeURIComponent(query) + '">' +
                '<span class="search-crumb">' + escapeHtml(crumb) + '</span>' +
                '<span class="search-head">' + escapeHtml(r.doc.h || r.doc.t) + '</span>' +
                '<span class="search-teaser">' + teaser(r.doc, r.at, asked) + '</span>' +
                '</a>';
        }).join('');
    }

    function plural(n, one, few, many) {
        var mod10 = n % 10;
        var mod100 = n % 100;
        if (mod10 === 1 && mod100 !== 11) {
            return one;
        }
        if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
            return few;
        }
        return many;
    }

    // ─── Оболочка ─────────────────────────────────────────────────────────

    function build() {
        var panel = document.createElement('div');
        panel.className = 'search-panel';
        panel.hidden = true;
        panel.innerHTML =
            '<div class="search-box">' +
            '<input type="search" class="search-input" placeholder="Поиск по книге" ' +
            'autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Поиск по книге">' +
            '<span class="search-count"></span>' +
            '</div>' +
            '<div class="search-results"></div>';
        document.body.appendChild(panel);

        ui.panel = panel;
        ui.input = panel.querySelector('.search-input');
        ui.results = panel.querySelector('.search-results');
        ui.count = panel.querySelector('.search-count');

        var timer = null;
        ui.input.addEventListener('input', function () {
            clearTimeout(timer);
            var query = ui.input.value.trim();
            if (query.length < 2) {
                ui.results.innerHTML = '';
                ui.count.textContent = '';
                return;
            }
            timer = setTimeout(function () {
                load().then(function () {
                    render(query);
                }).catch(function () {
                    ui.results.innerHTML = '<p class="search-empty">Указатель не загрузился.</p>';
                });
            }, 120);
        });

        ui.input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                close();
            } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                move(event.key === 'ArrowDown' ? 1 : -1);
            } else if (event.key === 'Enter') {
                var current = ui.results.querySelector('.is-current');
                if (current) {
                    event.preventDefault();
                    window.location.href = current.href;
                }
            }
        });

        panel.addEventListener('click', function (event) {
            if (event.target === panel) {
                close();
            }
        });
    }

    function move(step) {
        var all = Array.prototype.slice.call(ui.results.querySelectorAll('.search-hit'));
        if (!all.length) {
            return;
        }
        var at = all.findIndex(function (el) {
            return el.classList.contains('is-current');
        });
        if (at >= 0) {
            all[at].classList.remove('is-current');
        }
        var next = (at + step + all.length) % all.length;
        all[next].classList.add('is-current');
        all[next].scrollIntoView({ block: 'nearest' });
    }

    function open() {
        ui.panel.hidden = false;
        document.documentElement.classList.add('search-open');
        ui.input.focus();
        ui.input.select();
        load();
    }

    function close() {
        ui.panel.hidden = true;
        document.documentElement.classList.remove('search-open');
    }

    function button() {
        var host = document.querySelector('.menu-bar .left-buttons');
        if (!host) {
            return;
        }
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'icon-button search-button';
        b.title = 'Поиск по книге';
        b.setAttribute('aria-label', 'Поиск по книге');
        b.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" ' +
            'width="1em" height="1em" fill="currentColor" aria-hidden="true">' +
            '<path d="M416 208c0 45.9-14.9 88.3-40 122.7L502.6 457.4c12.5 12.5 12.5 32.8 0 ' +
            '45.3s-32.8 12.5-45.3 0L330.7 376c-34.4 25.2-76.8 40-122.7 40C93.1 416 0 322.9 0 ' +
            '208S93.1 0 208 0S416 93.1 416 208zM208 352a144 144 0 1 0 0-288 144 144 0 1 0 0 288z"/>' +
            '</svg>';
        b.addEventListener('click', open);
        host.appendChild(b);
    }

    function shortcuts() {
        document.addEventListener('keydown', function (event) {
            var tag = (event.target.tagName || '').toLowerCase();
            if (tag === 'input' || tag === 'textarea' || event.target.isContentEditable) {
                return;
            }
            if (event.key === '/' || event.key === 's' || event.key === 'ы') {
                event.preventDefault();
                open();
            } else if (event.key === 'Escape') {
                clearMarks(); // подсветка после перехода из поиска мешает перечитывать
            }
        });
    }

    // Читатель приходит по ссылке из выдачи в середину страницы — подсветим
    // там то, что он искал, иначе нужное слово приходится искать глазами.
    function highlightArrival() {
        var query = new URLSearchParams(window.location.search).get('q');
        var content = document.querySelector('main');
        if (!query || !content) {
            return;
        }
        load().then(function () {
            var asked = tokenize(query).map(function (t) {
                return stemOf(t.w);
            });
            var walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
            var nodes = [];
            var node;
            while ((node = walker.nextNode())) {
                if (node.parentElement.closest('.answer-body, mark, a')) {
                    continue;
                }
                if (node.nodeValue.trim()) {
                    nodes.push(node);
                }
            }
            nodes.forEach(function (text) {
                var parts = tokenize(text.nodeValue).filter(function (t) {
                    var stem = stemOf(t.w);
                    return asked.some(function (q) {
                        return hits(stem, q);
                    });
                });
                if (!parts.length) {
                    return;
                }
                var frag = document.createDocumentFragment();
                var last = 0;
                parts.forEach(function (t) {
                    frag.appendChild(document.createTextNode(text.nodeValue.slice(last, t.at)));
                    var mark = document.createElement('mark');
                    mark.textContent = text.nodeValue.substr(t.at, t.w.length);
                    frag.appendChild(mark);
                    last = t.at + t.w.length;
                });
                frag.appendChild(document.createTextNode(text.nodeValue.slice(last)));
                text.parentNode.replaceChild(frag, text);
            });
        });
    }

    function clearMarks() {
        var content = document.querySelector('main');
        if (!content) {
            return;
        }
        Array.prototype.forEach.call(content.querySelectorAll('mark'), function (mark) {
            var text = document.createTextNode(mark.textContent);
            mark.parentNode.replaceChild(text, mark);
        });
        content.normalize();
    }

    function start() {
        build();
        button();
        shortcuts();
        highlightArrival();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
