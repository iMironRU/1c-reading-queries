// Ответы под вопросами — на сайте, но не сразу.
// В бумажной книге ответы лежат в конце части: подсказка, увиденная сразу,
// отменяет попытку вспомнить. На сайте тот же порядок держит кнопка: сначала
// указание, и только потом ответ. Ответы берутся со страницы ответов главы,
// так что единственный источник остаётся один — файл NN-99.
(function () {
    'use strict';

    function normalize(text) {
        return text
            .replace(/[«»„“”"'`]/g, '')
            .replace(/\s+/g, ' ')
            .replace(/[.\s]+$/, '')
            .trim()
            .toLowerCase();
    }

    // У первого абзаца ответа убираем служебную пометку: её уже говорит кнопка.
    function trimLeading(p) {
        var em = p.querySelector('em');
        if (em) {
            em.remove();
        }
        while (p.firstChild && p.firstChild.nodeType === 3 && !p.firstChild.data.trim()) {
            p.removeChild(p.firstChild);
        }
        if (p.firstChild && p.firstChild.nodeType === 3) {
            p.firstChild.data = p.firstChild.data.replace(/^\s+/, '');
        }
    }

    function paragraphKey(text) {
        var m = text.match(/§\s*(\d+\.\d+)/);
        return m ? m[1] : null;
    }

    function answersUrl() {
        var parts = window.location.pathname.split('/');
        var file = parts[parts.length - 1];
        var m = file.match(/^(\d+)-(\d+)_/);
        if (!m || m[2] === '99') {
            return null;
        }
        parts[parts.length - 1] = m[1] + '-99_otvety.html';
        return parts.join('/');
    }

    // Разбирает страницу ответов на записи: «К вопросу N» и «К упражнению X».
    function parseAnswers(doc, key) {
        var content = doc.querySelector('main') || doc.body;
        var nodes = Array.prototype.slice.call(content.children);
        var inSection = false;
        var entries = {};
        var current = null;

        nodes.forEach(function (node) {
            if (node.tagName === 'H2') {
                inSection = paragraphKey(node.textContent) === key;
                current = null;
                return;
            }
            if (!inSection || node.tagName !== 'P') {
                return;
            }
            var strong = node.querySelector('strong');
            var head = strong ? strong.textContent.trim() : '';
            var question = head.match(/^(?:К вопросу|Вопрос)\s+(\d+)/);
            var exercise = head.match(/^(?:К упражнению|Упражнение)\s+(.+?)\.?$/);

            if (question || exercise) {
                var id = question
                    ? 'q' + question[1]
                    : 'e' + normalize(exercise[1]);
                current = { paragraphs: [] };
                entries[id] = current;
                var clone = node.cloneNode(true);
                clone.querySelector('strong').remove();
                current.paragraphs.push(clone);
                return;
            }
            if (current) {
                current.paragraphs.push(node.cloneNode(true));
            }
        });

        Object.keys(entries).forEach(function (id) {
            var list = entries[id].paragraphs;
            var first = list[0];
            var mark = first.querySelector('em');
            var role = mark ? normalize(mark.textContent) : '';
            if (role === 'указание' || role === 'ответ') {
                trimLeading(first);
            }
            if (role === 'указание') {
                entries[id].hint = first;
                entries[id].answer = list.slice(1);
            } else {
                entries[id].answer = list;
            }
        });

        return entries;
    }

    function makeBlock(entry) {
        var block = document.createElement('div');
        block.className = 'answer-block';

        var body = document.createElement('div');
        body.className = 'answer-body';
        body.hidden = true;

        var steps = [];
        if (entry.hint) {
            var hint = document.createElement('div');
            hint.className = 'answer-step answer-hint';
            hint.appendChild(entry.hint);
            hint.hidden = true;
            body.appendChild(hint);
            steps.push({ node: hint, label: 'Указание' });
        }
        var answer = document.createElement('div');
        answer.className = 'answer-step';
        entry.answer.forEach(function (p) {
            answer.appendChild(p);
        });
        answer.hidden = true;
        body.appendChild(answer);
        steps.push({ node: answer, label: 'Ответ' });

        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'answer-toggle';
        button.setAttribute('aria-expanded', 'false');
        button.textContent = entry.hint ? 'Указание' : 'Ответ';

        var shown = 0;
        button.addEventListener('click', function () {
            if (shown >= steps.length) {
                steps.forEach(function (step) {
                    step.node.hidden = true;
                });
                body.hidden = true;
                shown = 0;
                button.setAttribute('aria-expanded', 'false');
                button.textContent = steps[0].label;
                return;
            }
            body.hidden = false;
            steps[shown].node.hidden = false;
            shown += 1;
            button.setAttribute('aria-expanded', 'true');
            button.textContent = shown < steps.length ? steps[shown].label : 'Скрыть';
        });

        block.appendChild(button);
        block.appendChild(body);
        return block;
    }

    function sectionAfter(heading) {
        var out = [];
        var node = heading.nextElementSibling;
        while (node && node.tagName !== 'H2') {
            out.push(node);
            node = node.nextElementSibling;
        }
        return out;
    }

    function attach(entries) {
        var content = document.querySelector('main');
        if (!content) {
            return 0;
        }
        var placed = 0;

        Array.prototype.forEach.call(content.querySelectorAll('h2'), function (h2) {
            var title = normalize(h2.textContent);

            if (title === 'контрольные вопросы') {
                sectionAfter(h2).forEach(function (node) {
                    if (node.tagName !== 'OL') {
                        return;
                    }
                    Array.prototype.forEach.call(node.children, function (li, i) {
                        var entry = entries['q' + (i + 1)];
                        if (entry) {
                            li.appendChild(makeBlock(entry));
                            placed += 1;
                        }
                    });
                });
                return;
            }

            if (title === 'упражнения') {
                var groups = [];
                var group = null;
                sectionAfter(h2).forEach(function (node) {
                    if (node.tagName === 'P' && /^Ответы — в конце/.test(node.textContent.trim())) {
                        group = null;
                        return;
                    }
                    var strong = node.firstElementChild;
                    if (node.tagName === 'P' && strong && strong.tagName === 'STRONG') {
                        group = { entry: entries['e' + normalize(strong.textContent)], last: node };
                        groups.push(group);
                        return;
                    }
                    if (group) {
                        group.last = node;
                    }
                });
                groups.forEach(function (item) {
                    if (item.entry) {
                        item.last.insertAdjacentElement('afterend', makeBlock(item.entry));
                        placed += 1;
                    }
                });
            }
        });

        return placed;
    }

    // «Ответы — в конце части» — правда для бумаги; на сайте ответ уже здесь.
    function rewriteFooter(url) {
        var content = document.querySelector('main');
        if (!content) {
            return;
        }
        Array.prototype.forEach.call(content.querySelectorAll('p'), function (p) {
            if (!/^Ответы — в конце/.test(p.textContent.trim())) {
                return;
            }
            p.className = 'answers-note';
            p.innerHTML = 'Ответы раскрываются кнопкой под вопросом. ' +
                '<a href="' + url + '">Все ответы части</a> — на отдельной странице.';
        });
    }

    function start() {
        var heading = document.querySelector('main h1');
        if (!heading) {
            return;
        }
        var key = paragraphKey(heading.textContent);
        var url = answersUrl();
        if (!key || !url) {
            return;
        }

        fetch(url)
            .then(function (response) {
                return response.ok ? response.text() : Promise.reject(response.status);
            })
            .then(function (html) {
                var doc = new DOMParser().parseFromString(html, 'text/html');
                var entries = parseAnswers(doc, key);
                if (attach(entries) > 0) {
                    rewriteFooter(url);
                }
            })
            .catch(function () {
                /* нет страницы ответов или файл открыт локально — оставляем как есть */
            });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
