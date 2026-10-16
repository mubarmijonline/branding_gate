/*
 * Arabic for every page, without touching the pages.
 *
 * The server puts lang="ar" on <html> when the visitor chose Arabic and loads
 * the dictionary (window.BG_AR, English -> Arabic) before this file. Every
 * text node, placeholder, tooltip and button label is looked up as it reaches
 * the document, including what scripts render later (tables, SweetAlert
 * popups, select2 lists), so pages need no markup changes.
 *
 * Lookup order: exact text, text without decorative punctuation, the Arabic
 * half of an existing "English | عربي" label, " · " / " | " segments, then
 * templates with {0}-style holes ("{0} items", "Approve {0}?").
 *
 * Opt out per element with data-no-i18n (names, codes, user content).
 *
 * ponytail: text-level dictionary, not gettext. A string the extractor missed
 * stays English until it is added to static/i18n; the upgrade path is marking
 * strings at source if coverage ever matters more than zero page edits.
 */
(function () {
    'use strict';
    var root = document.documentElement;
    var lang = (root.getAttribute('lang') || 'en').toLowerCase();
    window.bgLang = lang;
    if (lang !== 'ar' || !window.BG_AR) {
        root.classList.remove('i18n-pending');
        return;
    }

    var DICT = window.BG_AR;
    var LATIN = /[A-Za-z]/;
    var ARABIC = /[؀-ۿ]/;
    var LEAD = /^[\s:*·|\-–•]+/;
    var TRAIL = /[\s:*·|•]+$/;
    var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, CODE: 1, PRE: 1, NOSCRIPT: 1, SVG: 1 };
    var ATTRS = ['placeholder', 'title', 'aria-label', 'data-original-title', 'alt', 'data-placeholder'];

    // Templates: keys with {n} holes, bucketed by their longest literal word so
    // a miss costs a handful of regex tests, not hundreds. Words are compared
    // without digits and punctuation, so "4d" finds the "{0}d ago" bucket.
    function bareWord(w) { return w.toLowerCase().replace(/[^a-z]/g, ''); }
    var buckets = {};
    Object.keys(DICT).forEach(function (key) {
        if (key.indexOf('{0}') < 0) return;
        var parts = key.split(/\{\d\}/);
        var words = parts.join(' ').split(/\s+/).map(bareWord).filter(Boolean);
        if (!words.length) return;
        var word = words.reduce(function (a, b) { return b.length > a.length ? b : a; });
        var order = (key.match(/\{\d\}/g) || []).map(function (p) { return +p.charAt(1); });
        var rx = new RegExp('^' + parts.map(function (p) {
            return p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        }).join('(.+?)') + '$');
        (buckets[word] = buckets[word] || []).push({ rx: rx, order: order, ar: DICT[key] });
    });

    var cache = new Map();
    // Badges print raw values ("approved", "PENDING"): short labels also match
    // regardless of case.
    var FOLDED = new Map();
    Object.keys(DICT).forEach(function (key) {
        if (key.indexOf('{') < 0 && key.split(' ').length <= 4 && !FOLDED.has(key.toLowerCase())) {
            FOLDED.set(key.toLowerCase(), DICT[key]);
        }
    });

    function exact(s) {
        if (Object.prototype.hasOwnProperty.call(DICT, s)) return DICT[s];
        var folded = FOLDED.get(s.toLowerCase());
        return folded === undefined ? null : folded;
    }

    function fromTemplate(s) {
        var seen = {};
        var words = s.split(/\s+/).map(bareWord);
        for (var w = 0; w < words.length; w++) {
            if (!words[w] || seen[words[w]]) continue;
            seen[words[w]] = 1;
            var list = buckets[words[w]];
            if (!list) continue;
            for (var i = 0; i < list.length; i++) {
                var m = list[i].rx.exec(s);
                if (!m) continue;
                var values = {};
                list[i].order.forEach(function (n, idx) {
                    var v = m[idx + 1];
                    values[n] = exact(v) || exact(v.trim()) || v;
                });
                return list[i].ar.replace(/\{(\d)\}/g, function (_, n) {
                    return values[n] != null ? values[n] : '';
                });
            }
        }
        return null;
    }

    function core(s) {
        var hit = exact(s);
        if (hit != null) return hit;
        var lead = (s.match(LEAD) || [''])[0];
        var rest = s.slice(lead.length);
        var trail = (rest.match(TRAIL) || [''])[0];
        var mid = rest.slice(0, rest.length - trail.length);
        if (mid && mid !== s) {
            hit = exact(mid);
            if (hit != null) return lead + hit + trail;
        }
        // Separated pieces ("Added by X · 2 day(s) ago") are translated one by
        // one before any template may swallow the separator into a hole.
        if (/\s[·|—]\s/.test(s)) {
            var changed = false;
            var segs = s.split(/(\s[·|—]\s)/).map(function (seg, i) {
                if (i % 2) return seg;
                var t = core(seg.trim());
                if (t != null) { changed = true; return t; }
                return seg;
            });
            if (changed) return segs.join('');
        }
        hit = fromTemplate(s);
        if (hit != null) return hit;
        if (mid && mid !== s) {
            hit = fromTemplate(mid);
            if (hit != null) return lead + hit + trail;
        }
        return null;
    }

    function translate(text) {
        if (!text || !LATIN.test(text)) return null;
        var s = text.replace(/\s+/g, ' ').trim();
        if (!s || s.length > 400) return null;
        if (cache.has(s)) return cache.get(s);
        var out = null;
        if (ARABIC.test(s) && s.indexOf(' | ') > 0) {
            // Labels already written "English | عربي": keep the Arabic half.
            var halves = s.split(' | ').filter(function (h) { return ARABIC.test(h) && !LATIN.test(h); });
            if (halves.length) out = halves.join(' | ');
        }
        if (out == null) out = core(s);
        cache.set(s, out);
        return out;
    }
    window.bgT = function (s) { return translate(s) || s; };

    function skipped(el) {
        for (var n = el; n && n.nodeType === 1; n = n.parentNode) {
            if (SKIP_TAGS[n.nodeName.toUpperCase()]) return true;
            if (n.hasAttribute('data-no-i18n') || n.isContentEditable) return true;
        }
        return false;
    }

    // What this file wrote into each text node, so its own edits coming back
    // through the observer are not translated a second time.
    var written = new WeakMap();

    function doText(node) {
        var v = node.nodeValue;
        if (!v || written.get(node) === v || !LATIN.test(v) || !node.parentNode || skipped(node.parentNode)) return;
        var t = translate(v);
        if (t == null) return;
        var lead = v.match(/^\s*/)[0];
        var trail = v.match(/\s*$/)[0];
        var next = lead + t + trail;
        written.set(node, next);
        node.nodeValue = next;
    }

    function doElement(el) {
        // A textarea's text is the user's, but its placeholder is ours
        // (select2 renders its search box as one).
        if (el.nodeName === 'TEXTAREA' ? skipped(el.parentNode) : skipped(el)) return;
        for (var i = 0; i < ATTRS.length; i++) {
            var v = el.getAttribute(ATTRS[i]);
            if (v && LATIN.test(v)) {
                var t = translate(v);
                if (t != null) el.setAttribute(ATTRS[i], t);
            }
        }
        if (el.nodeName === 'INPUT' && /^(button|submit|reset)$/i.test(el.type) && LATIN.test(el.value)) {
            var tv = translate(el.value);
            if (tv != null) el.value = tv;
        }
    }

    function walk(rootNode) {
        if (rootNode.nodeType === 3) return doText(rootNode);
        if (rootNode.nodeType !== 1 && rootNode.nodeType !== 9 && rootNode.nodeType !== 11) return;
        if (rootNode.nodeType === 1) {
            if (rootNode.nodeName === 'TEXTAREA') return doElement(rootNode);
            if (skipped(rootNode)) return;
            doElement(rootNode);
        }
        var tw = document.createTreeWalker(rootNode, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
            acceptNode: function (n) {
                if (n.nodeType === 1 && (SKIP_TAGS[n.nodeName.toUpperCase()] || n.hasAttribute('data-no-i18n'))) {
                    if (n.nodeName === 'TEXTAREA') doElement(n);
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        var n;
        while ((n = tw.nextNode())) {
            if (n.nodeType === 3) doText(n); else doElement(n);
        }
    }

    function translateTitle() {
        var t = translate(document.title);
        if (t != null) document.title = t;
    }

    var observer = new MutationObserver(function (records) {
        for (var i = 0; i < records.length; i++) {
            var r = records[i];
            if (r.type === 'childList') {
                for (var j = 0; j < r.addedNodes.length; j++) walk(r.addedNodes[j]);
            } else if (r.type === 'characterData') {
                doText(r.target);
            } else if (r.type === 'attributes') {
                doElement(r.target);
            }
        }
    });
    observer.observe(root, {
        childList: true, subtree: true, characterData: true,
        attributes: true, attributeFilter: ATTRS
    });

    // Native dialogs never reach the DOM.
    ['alert', 'confirm', 'prompt'].forEach(function (name) {
        var native = window[name];
        if (typeof native !== 'function') return;
        window[name] = function (message) {
            var args = Array.prototype.slice.call(arguments);
            if (typeof message === 'string') args[0] = translate(message) || message;
            return native.apply(window, args);
        };
    });

    function ready() {
        walk(document.body || root);
        translateTitle();
        root.classList.remove('i18n-pending');
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', ready);
    } else {
        ready();
    }
    // Never leave the page hidden if something above throws.
    setTimeout(function () { root.classList.remove('i18n-pending'); }, 2500);
    new MutationObserver(translateTitle).observe(document.querySelector('title') || root, { childList: true });
})();
