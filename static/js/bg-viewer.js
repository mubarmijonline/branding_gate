/*
 * One photo viewer for the whole site (Ahmed, 2026-10-29). Photos used to open
 * with window.open or a target=_blank link, which on the home-screen app does
 * nothing or leaves the app; now a photo opens full screen on the page, over
 * any modal, and closes with a tap, the X or Escape.
 *
 * Catches, without touching the pages: window.open(<photo>), a link to a photo
 * (attachments), and a tap anywhere on an item's thumbnail (its "View Full"
 * strip covers part of the picture). Other files open as before.
 *
 *   bgViewImage(src)  -> opens the viewer
 *
 * ponytail: photos only; PDFs still open in the browser's own viewer.
 */
(function () {
    'use strict';
    var PHOTO = /\.(jpe?g|png|gif|webp|bmp|svg|avif|heic)([?#]|$)/i;
    var T = function (x) { return window.bgT ? window.bgT(x) : x; };
    function esc(v) {
        return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function isPhoto(url) { return typeof url === 'string' && PHOTO.test(url.split('?')[0]) || /^data:image\//.test(url || ''); }

    window.bgViewImage = function (src) {
        $('.bg-viewer').remove();
        var $lb = $('<div class="bgc-lightbox bg-viewer" role="dialog" aria-modal="true" style="background: rgba(11, 20, 26, .98)">' +
            '<div class="bgc-lightbox-bar">' +
            '<a class="bgc-icon-btn" href="' + esc(src) + '" download title="' + esc(T('Download')) + '"><i class="fas fa-download"></i></a>' +
            '<button type="button" class="bgc-icon-btn" title="' + esc(T('Close')) + '"><i class="fas fa-times"></i></button></div>' +
            '<div class="bgc-lightbox-img"><img alt="" src="' + esc(src) + '"></div></div>');
        $lb.on('click', function (e) { if (!$(e.target).closest('a').length) { $lb.remove(); } });
        $('body').append($lb);
    };

    var open = window.open;
    window.open = function (url) {
        if (isPhoto(url)) { window.bgViewImage(url); return null; }
        return open.apply(window, arguments);
    };

    // Capture phase: before the page's own onclick and before a modal sees it.
    document.addEventListener('click', function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
        var thumb = e.target.closest && e.target.closest('.enhanced-image-thumbnail');
        var img = thumb && thumb.querySelector('img');
        var a = !thumb && e.target.closest && e.target.closest('a[href]:not([download])');
        var src = img ? img.getAttribute('src') : a && isPhoto(a.getAttribute('href')) ? a.getAttribute('href') : null;
        if (!src || (a && a.closest('.bgc-lightbox'))) return;
        e.preventDefault();
        e.stopPropagation();
        window.bgViewImage(src);
    }, true);
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && $('.bg-viewer').length) { e.stopPropagation(); $('.bg-viewer').remove(); }
    }, true);
})();
