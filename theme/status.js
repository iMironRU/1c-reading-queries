document.addEventListener('DOMContentLoaded', function () {
    var host = document.querySelector('main');
    if (!host) return;
    var b = document.createElement('div');
    b.className = 'book-status book-status--wip';
    b.textContent = "Книга пишется: 62 из 75 параграфов прошли вычитку. Черновики открыты нарочно — их можно читать, но они ещё изменятся.";
    host.insertBefore(b, host.firstChild);
});
