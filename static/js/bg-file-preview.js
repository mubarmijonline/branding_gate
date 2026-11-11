/*
 * Image attachments open in a viewer on the page instead of a new tab.
 *
 * One delegated handler for every page that extends main.html: any link that
 * opens a new tab and shows an image (an <img> inside it, or an image file
 * name) is previewed here. The other images in the same group (the link's
 * parent) become the gallery, so arrows step through all the receipts of one
 * request. PDFs and other files keep opening in a new tab; Ctrl/Cmd/middle
 * click still opens a new tab; data-no-preview on a link opts it out.
 */
(function () {
    'use strict';
    var IMG_NAME = /\.(png|jpe?g|gif|webp|bmp|svg|avif|heic)(\?|#|$)/i;
    var list = [], at = 0, box = null;

    function isImageLink(a) {
        if (!a || a.hasAttribute('data-no-preview') || !a.getAttribute('href')) return false;
        if (a.querySelector('img')) return true;
        return IMG_NAME.test(a.getAttribute('href')) || IMG_NAME.test(a.getAttribute('title') || '') ||
            IMG_NAME.test(a.getAttribute('download') || '');
    }
    function nameOf(a) {
        var t = a.getAttribute('title') || a.getAttribute('download') || '';
        if (!t) { var s = a.querySelector('small, .bg-xf-name'); t = s ? s.textContent : ''; }
        if (!t) { var tile = a.closest('.bg-xf-tile'); var n = tile && tile.querySelector('.bg-xf-name'); t = n ? n.textContent : ''; }
        return (t || a.href.split('/').pop() || '').trim();
    }
    function group(a) {
        // The gallery is the images of the same file list (one request's receipts),
        // never the whole page: a list class, else the link's own parent.
        var scope = a.closest('.bg-xf-grid, .sa-files, .sc-files, .qa-files, .dr-files, .gt-files, [data-preview-group]') || a.parentElement;
        var links = Array.prototype.filter.call(scope.querySelectorAll('a[href]'), isImageLink);
        return links.indexOf(a) < 0 ? [a] : links;
    }

    function build() {
        box = document.createElement('div');
        box.className = 'bg-fp';
        box.setAttribute('role', 'dialog');
        box.setAttribute('aria-modal', 'true');
        box.innerHTML =
            '<div class="bg-fp-bar"><span class="bg-fp-name" data-no-i18n></span><span class="bg-fp-count"></span>' +
            '<a class="bg-fp-btn bg-fp-open" target="_blank" rel="noopener" title="Open in a new tab"><i class="fas fa-external-link-alt"></i></a>' +
            '<a class="bg-fp-btn bg-fp-dl" download title="Download"><i class="fas fa-download"></i></a>' +
            '<button type="button" class="bg-fp-btn bg-fp-close" title="Close"><i class="fas fa-times"></i></button></div>' +
            '<div class="bg-fp-stage"><img alt=""><div class="bg-fp-wait"><i class="fas fa-spinner fa-spin"></i></div></div>' +
            '<button type="button" class="bg-fp-nav bg-fp-prev" title="Previous"><i class="fas fa-chevron-left"></i></button>' +
            '<button type="button" class="bg-fp-nav bg-fp-next" title="Next"><i class="fas fa-chevron-right"></i></button>';
        document.body.appendChild(box);
        var img = box.querySelector('img');
        img.addEventListener('load', function () { box.classList.remove('loading'); });
        img.addEventListener('error', function () { box.classList.remove('loading'); box.classList.add('failed'); });
        img.addEventListener('click', function (e) { e.stopPropagation(); box.classList.toggle('zoom'); });
        box.querySelector('.bg-fp-close').addEventListener('click', close);
        box.querySelector('.bg-fp-prev').addEventListener('click', function (e) { e.stopPropagation(); show(at - 1); });
        box.querySelector('.bg-fp-next').addEventListener('click', function (e) { e.stopPropagation(); show(at + 1); });
        box.querySelector('.bg-fp-stage').addEventListener('click', function (e) { if (e.target === this) close(); });
    }

    function show(i) {
        at = (i + list.length) % list.length;
        var a = list[at], url = a.href, name = nameOf(a);
        box.classList.remove('zoom', 'failed');
        box.classList.add('loading');
        box.classList.toggle('single', list.length < 2);
        box.querySelector('img').src = url;
        box.querySelector('.bg-fp-name').textContent = name;
        box.querySelector('.bg-fp-count').textContent = list.length > 1 ? (at + 1) + ' / ' + list.length : '';
        box.querySelector('.bg-fp-open').href = url;
        var dl = box.querySelector('.bg-fp-dl');
        dl.href = url;
        dl.setAttribute('download', name);
    }
    function open(a) {
        if (!box) build();
        list = group(a);
        var i = list.indexOf(a);
        box.classList.add('show');
        document.documentElement.classList.add('bg-fp-lock');
        show(i < 0 ? 0 : i);
        box.querySelector('.bg-fp-close').focus();
    }
    function close() {
        if (!box) return;
        box.classList.remove('show');
        document.documentElement.classList.remove('bg-fp-lock');
        box.querySelector('img').removeAttribute('src');
    }

    // Capture phase, so it runs before page handlers and before a Swal or
    // Bootstrap modal sees the click.
    document.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
        var a = e.target.closest && e.target.closest('a[href]');
        if (!a || (box && box.contains(a)) || a.target !== '_blank' || !isImageLink(a)) return;
        e.preventDefault();
        e.stopPropagation();
        open(a);
    }, true);
    document.addEventListener('keydown', function (e) {
        if (!box || !box.classList.contains('show')) return;
        var rtl = document.documentElement.dir === 'rtl';
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
        else if (e.key === 'ArrowRight') show(at + (rtl ? -1 : 1));
        else if (e.key === 'ArrowLeft') show(at + (rtl ? 1 : -1));
    }, true);

    window.bgPreviewImage = function (url, name) {
        var a = document.createElement('a');
        a.href = url; a.title = name || '';
        if (!box) build();
        list = [a];
        box.classList.add('show');
        document.documentElement.classList.add('bg-fp-lock');
        show(0);
    };

    var css = '' +
        '.bg-fp{position:fixed;inset:0;z-index:20000;display:none;background:rgba(2,6,23,.92);color:#fff}' +
        '.bg-fp.show{display:block}' +
        'html.bg-fp-lock,html.bg-fp-lock body{overflow:hidden}' +
        '.bg-fp-bar{position:absolute;inset:0 0 auto;height:56px;display:flex;align-items:center;gap:10px;padding:0 12px 0 18px;background:linear-gradient(rgba(2,6,23,.75),transparent);z-index:2}' +
        '.bg-fp-name{flex:1;min-width:0;font-weight:700;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
        '.bg-fp-count{font-size:13px;color:#cbd5e1;font-variant-numeric:tabular-nums}' +
        '.bg-fp-btn{width:40px;height:40px;border-radius:10px;border:0;background:rgba(255,255,255,.12);color:#fff;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:16px;text-decoration:none}' +
        '.bg-fp-btn:hover{background:rgba(255,255,255,.24);color:#fff;text-decoration:none}' +
        '.bg-fp-stage{position:absolute;inset:56px 64px 24px;display:flex;align-items:center;justify-content:center;overflow:auto}' +
        '.bg-fp-stage img{max-width:100%;max-height:100%;object-fit:contain;border-radius:6px;box-shadow:0 20px 60px rgba(0,0,0,.5);cursor:zoom-in;background:#fff}' +
        '.bg-fp.zoom .bg-fp-stage{align-items:flex-start;justify-content:flex-start}' +
        '.bg-fp.zoom .bg-fp-stage img{max-width:none;max-height:none;cursor:zoom-out;margin:auto}' +
        '.bg-fp-wait{position:absolute;font-size:28px;color:#cbd5e1;display:none}' +
        '.bg-fp.loading .bg-fp-wait{display:block}.bg-fp.loading .bg-fp-stage img{opacity:0}' +
        '.bg-fp.failed .bg-fp-stage::after{content:"This image could not be loaded. Use the download button.";color:#fecaca;font-weight:600}' +
        '.bg-fp.failed .bg-fp-stage img{display:none}' +
        '.bg-fp-nav{position:absolute;top:50%;transform:translateY(-50%);width:48px;height:48px;border-radius:50%;border:0;background:rgba(255,255,255,.14);color:#fff;font-size:18px;cursor:pointer;z-index:2}' +
        '.bg-fp-nav:hover{background:rgba(255,255,255,.28)}' +
        '.bg-fp-prev{left:10px}.bg-fp-next{right:10px}' +
        '[dir=rtl] .bg-fp-prev{left:auto;right:10px}[dir=rtl] .bg-fp-next{right:auto;left:10px}' +
        '[dir=rtl] .bg-fp-nav i{transform:scaleX(-1)}' +
        '.bg-fp.single .bg-fp-nav{display:none}' +
        '@media (max-width:640px){.bg-fp-stage{inset:56px 8px 72px}.bg-fp-nav{top:auto;bottom:12px;transform:none}}';
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
})();
