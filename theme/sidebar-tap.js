// Тап по тексту закрывает боковое меню.
// На узком экране меню накрывает страницу, и промах по кнопке оставляет
// читателя в меню. Клик по видимой части текста возвращает его к чтению.
(function () {
    'use strict';

    var NARROW = 1080; // ниже этой ширины mdBook кладёт меню поверх текста

    // В свежем mdBook идентификаторы получили приставку mdbook-; поддерживаем оба.
    function pick(selector) {
        return document.querySelector(selector);
    }

    // Открыто ли меню: в свежем mdBook об этом говорит класс на <html>,
    // в прежнем — только скрытый флажок, которым управляет кнопка.
    function isOpen() {
        var anchor = pick('#mdbook-sidebar-toggle-anchor, #sidebar-toggle-anchor');
        if (anchor) {
            return anchor.checked;
        }
        return document.documentElement.classList.contains('sidebar-visible');
    }

    function hide() {
        var anchor = pick('#mdbook-sidebar-toggle-anchor, #sidebar-toggle-anchor');
        if (anchor && anchor.checked) {
            anchor.checked = false;
            anchor.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }
        var toggle = pick('#mdbook-sidebar-toggle, #sidebar-toggle');
        if (toggle) {
            toggle.click();
            return true;
        }
        return false;
    }

    function start() {
        var wrapper = pick('#mdbook-page-wrapper, #page-wrapper, .page-wrapper');
        var sidebar = pick('#mdbook-sidebar, #sidebar');
        if (!wrapper || !sidebar) {
            return;
        }

        wrapper.addEventListener('click', function (event) {
            if (window.innerWidth >= NARROW) {
                return;
            }
            if (!isOpen()) {
                return;
            }
            if (sidebar.contains(event.target)) {
                return;
            }
            var toggle = pick('#mdbook-sidebar-toggle, #sidebar-toggle');
            if (toggle && toggle.contains(event.target)) {
                return; // кнопка сама умеет закрывать
            }
            if (hide()) {
                event.preventDefault();
                event.stopPropagation();
            }
        }, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
