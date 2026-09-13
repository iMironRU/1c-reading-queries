// Навигация внутри параграфа: оглавление разделов и кнопка «наверх».
//
// Параграф книги — это пять-восемь разделов и два экрана текста. Боковое
// меню показывает параграфы, но не то, что внутри; вернуться к началу, чтобы
// перечитать «Главное в одном абзаце», было нечем.
//
// На широком экране оглавление стоит справа от текста и подсвечивает раздел,
// который читатель видит сейчас. На узком — свёрнутой строкой под заголовком:
// там дорог каждый экран.
(function () {
    'use strict';

    var MIN_SECTIONS = 3;
    var SHOW_TOP_AFTER = 600;

    function sections(content) {
        return Array.prototype.filter.call(content.querySelectorAll('h2'), function (h2) {
            return !!h2.id || !!h2.querySelector('a.header');
        });
    }

    function anchorOf(h2) {
        if (h2.id) {
            return h2.id;
        }
        var link = h2.querySelector('a.header');
        var href = link ? link.getAttribute('href') || '' : '';
        return href.indexOf('#') === 0 ? href.slice(1) : '';
    }

    function buildToc(content, list) {
        var nav = document.createElement('nav');
        nav.className = 'page-toc';
        nav.setAttribute('aria-label', 'Разделы параграфа');

        var label = document.createElement('button');
        label.type = 'button';
        label.className = 'page-toc-label';
        label.textContent = 'В этом параграфе';
        label.setAttribute('aria-expanded', 'false');

        var items = document.createElement('ol');
        items.className = 'page-toc-list';

        list.forEach(function (h2) {
            var id = anchorOf(h2);
            if (!id) {
                return;
            }
            var li = document.createElement('li');
            var a = document.createElement('a');
            a.href = '#' + id;
            a.textContent = (h2.textContent || '').trim();
            a.dataset.target = id;
            li.appendChild(a);
            items.appendChild(li);
        });

        label.addEventListener('click', function () {
            var open = nav.classList.toggle('is-open');
            label.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        items.addEventListener('click', function () {
            nav.classList.remove('is-open');
            label.setAttribute('aria-expanded', 'false');
        });

        nav.appendChild(label);
        nav.appendChild(items);

        var title = content.querySelector('h1');
        if (title && title.nextSibling) {
            title.parentNode.insertBefore(nav, title.nextSibling);
        } else {
            content.insertBefore(nav, content.firstChild);
        }
        return nav;
    }

    // Подсветка текущего раздела: следим за тем, что пересекает верхнюю треть
    // экрана, — именно туда смотрит читатель.
    function spy(nav, list) {
        var links = {};
        Array.prototype.forEach.call(nav.querySelectorAll('a'), function (a) {
            links[a.dataset.target] = a;
        });
        var seen = {};

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                seen[anchorOf(entry.target)] = entry.isIntersecting
                    ? entry.boundingClientRect.top
                    : null;
            });
            var current = null;
            list.forEach(function (h2) {
                var id = anchorOf(h2);
                if (seen[id] !== null && seen[id] !== undefined) {
                    current = current || id;
                }
            });
            if (!current) {
                return;
            }
            Object.keys(links).forEach(function (id) {
                links[id].classList.toggle('is-current', id === current);
            });
        }, { rootMargin: '-80px 0px -66% 0px', threshold: 0 });

        list.forEach(function (h2) {
            observer.observe(h2);
        });
    }

    function topButton() {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'to-top';
        button.title = 'Наверх';
        button.setAttribute('aria-label', 'Наверх');
        button.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512" ' +
            'width="1em" height="1em" fill="currentColor" aria-hidden="true">' +
            '<path d="M214.6 41.4c-12.5-12.5-32.8-12.5-45.3 0l-160 160c-12.5 12.5-12.5 32.8 0 ' +
            '45.3s32.8 12.5 45.3 0L160 141.2V448c0 17.7 14.3 32 32 32s32-14.3 32-32V141.2L329.4 ' +
            '246.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3l-160-160z"/></svg>';
        button.addEventListener('click', function () {
            var scroller = document.querySelector('.content') || window;
            if (scroller === window) {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                scroller.scrollTo({ top: 0, behavior: 'smooth' });
            }
            document.documentElement.scrollTo({ top: 0, behavior: 'smooth' });
        });
        document.body.appendChild(button);

        var ticking = false;
        function check() {
            ticking = false;
            var y = window.scrollY || document.documentElement.scrollTop || 0;
            button.classList.toggle('is-shown', y > SHOW_TOP_AFTER);
        }
        window.addEventListener('scroll', function () {
            if (!ticking) {
                ticking = true;
                window.requestAnimationFrame(check);
            }
        }, { passive: true });
        check();
    }

    function start() {
        var content = document.querySelector('main');
        if (!content) {
            return;
        }
        topButton();

        var list = sections(content);
        if (list.length < MIN_SECTIONS) {
            return;
        }
        var nav = buildToc(content, list);
        if (window.IntersectionObserver) {
            spy(nav, list);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
