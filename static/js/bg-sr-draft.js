/*
 * New sales request: a draft kept while it is being filled in (Gamal,
 * 2026-10-29). Cancel, the X, a closed tab or a dropped connection used to
 * lose everything typed; now the form is saved on this device a moment after
 * every change (and every 10 s), comes back when the form is reopened, and is
 * deleted once the request is saved.
 *
 * The form builds itself as it is filled (template sections per request type,
 * item rows), so a draft is replayed rather than poured back: tick the types,
 * wait for their sections, add as many item rows, then set every value in page
 * order. Values are keyed by name with the numbers taken out (items[7][name]
 * -> items[#][name]) and matched by position, because row numbers change
 * between sessions.
 *
 * ponytail: this device only (localStorage); a server-side draft if people
 * start a request on one device and finish it on another. Photos and files are
 * not kept (a browser cannot store a picked file).
 */
(function () {
  var KEY = window.SR_DRAFT_KEY || 'bgSrDraft';
  var FORM = '#addRequestForm', MODAL = '#addRequestModal';
  var MAX_AGE = 7 * 24 * 3600 * 1000;
  var busy = false, done = false, timer = null, ticker = null;
  var T = function (x) { return window.bgT ? window.bgT(x) : x; };

  function controls() {
    // The inventory search fills the row from the catalogue; its own value is
    // not something to restore, and files cannot be.
    return $(FORM).find('input, select, textarea')
      .not('[type=file], [type=hidden], .item-template-select, .select2-search__field');
  }
  function keyOf(el) {
    var cls = (el.className || '').split(/\s+/).filter(function (c) {
      return c && !/^(form-control|custom-control-input|select2-hidden-accessible|is-(in)?valid)/.test(c);
    }).join('.');
    return (el.name || el.id || cls || el.tagName).replace(/\d+/g, '#') +
           (el.type === 'radio' || el.type === 'checkbox' ? '=' + el.value : '');
  }
  function snapshot() {
    var values = [];
    controls().each(function () {
      var box = this.type === 'checkbox' || this.type === 'radio';
      values.push({ k: keyOf(this), v: box ? this.checked : $(this).val() });
    });
    return {
      at: Date.now(),
      types: $(MODAL + ' .request-type-checkbox:checked').map(function () { return this.value; }).get(),
      // Item rows per list: each template section has its own (#items_1_Booth),
      // the plain form one list (#itemsContainer).
      items: $(MODAL + ' #itemsContainer, ' + MODAL + ' [id^="items_"]').get().reduce(function (acc, el) {
        var n = $(el).children('.item-row').length;
        if (n) { acc[el.id] = n; }
        return acc;
      }, {}),
      values: values
    };
  }
  function meaningful(d) {
    return d.types.length || Object.keys(d.items).length || d.values.some(function (x) {
      return x.k.indexOf('request-type') < 0 && x.v && x.v !== true && String(x.v).trim() &&
             !/priority|sell_type|unit/.test(x.k);
    });
  }
  function read() {
    try {
      var d = JSON.parse(localStorage.getItem(KEY) || 'null');
      return d && typeof d.items === 'object' && Date.now() - d.at < MAX_AGE ? d : null;
    } catch (e) { return null; }
  }
  function save() {
    if (busy || done || !$(MODAL).hasClass('show')) return;
    var d = snapshot();
    try {
      // An empty form never overwrites a draft: the page empties the form
      // itself when it opens, and only a save or Start fresh ends a draft.
      if (meaningful(d)) { localStorage.setItem(KEY, JSON.stringify(d)); stamp(d.at); }
    } catch (e) { /* storage full or blocked: the form still works */ }
  }
  function clear() {
    done = true;
    try { localStorage.removeItem(KEY); } catch (e) {}
    stamp(null);
  }
  function time(at) {
    var t = new Date(at);
    return t.toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  }
  function stamp(at) {
    var $s = $('#srDraftStamp');
    if (!$s.length) {
      $s = $('<small id="srDraftStamp" class="text-muted mr-auto"></small>');
      $(MODAL + ' .modal-footer').prepend($s);
    }
    $s.html(at ? '<i class="fas fa-save mr-1"></i>' + T('Draft saved {0}').replace('{0}', time(at)) : '');
  }

  function waitFor(test, ms) {
    return new Promise(function (resolve) {
      var end = Date.now() + ms;
      (function poll() { if (test() || Date.now() > end) resolve(); else setTimeout(poll, 150); })();
    });
  }
  function fill(d, selects) {
    var seen = {};
    var byKey = {};
    d.values.forEach(function (x) { (byKey[x.k] = byKey[x.k] || []).push(x.v); });
    controls().each(function () {
      var k = keyOf(this), n = seen[k] = (seen[k] || 0) + 1, list = byKey[k];
      if (!list || list.length < n) return;
      var v = list[n - 1], $el = $(this);
      if (this.type === 'checkbox' || this.type === 'radio') {
        if (this.checked !== v) { $el.prop('checked', v).trigger('change'); }
      } else if (this.tagName === 'SELECT') {
        if (selects && String($el.val()) !== String(v)) { $el.val(v).trigger('change'); }
      } else if (!selects && $el.val() !== v) {
        $el.val(v).trigger('input');
      }
    });
  }
  function restore(d) {
    busy = true;
    d.types.forEach(function (t) {
      $(MODAL + ' .request-type-checkbox').filter(function () { return this.value === t; })
        .prop('checked', true).trigger('change');
    });
    var sections = function () { return $(MODAL + ' .template-instance').length > 0; };
    return waitFor(function () { return !d.types.length || sections(); }, 5000)
      .then(function () { return new Promise(function (r) { setTimeout(r, 600); }); })
      .then(function () {
        Object.keys(d.items || {}).forEach(function (id) {
          var $list = $('#' + id);
          var $add = id === 'itemsContainer' ? $('#addItemBtn')
                   : $(MODAL + ' .add-item-per-type-btn[data-instance-id="' + id.replace(/^items_/, '') + '"]').first();
          for (var i = $list.children('.item-row').length; i < d.items[id]; i++) { $add.trigger('click'); }
        });
        fill(d, true);                     // selects first: company before client, units...
        return new Promise(function (r) { setTimeout(r, 400); });
      })
      .then(function () { fill(d, false); fill(d, true); })
      .then(function () { busy = false; stamp(d.at); }, function () { busy = false; });
  }

  $(document).on('input change', FORM, function () {
    clearTimeout(timer);
    timer = setTimeout(save, 600);
  });
  // Quiet from opening until the draft is back (the page's own reset fires
  // change events that must not be saved over it).
  $(MODAL).on('show.bs.modal', function () { busy = true; });
  $(MODAL).on('shown.bs.modal', function () {
    done = false;
    stamp(null);
    $('#srDraftNote').remove();
    clearInterval(ticker);
    ticker = setInterval(save, 10000);
    var d = read();
    if (!d) { setTimeout(function () { busy = false; }, 250); return; }
    // The page resets the form 100 ms after opening; restore after that.
    setTimeout(function () {
      restore(d).then(function () {
        $('<div id="srDraftNote" class="alert alert-info d-flex align-items-center justify-content-between py-2 mb-3">' +
          '<span><i class="fas fa-history mr-2"></i>' + T('Your unsaved request from {0} is back.').replace('{0}', time(d.at)) +
          (Object.keys(d.items).length ? ' ' + T('Photos and files need adding again.') : '') + '</span>' +
          '<button type="button" class="btn btn-sm btn-outline-secondary ml-2" id="srDraftFresh">' + T('Start fresh') + '</button></div>')
          .prependTo(MODAL + ' .modal-body');
        $(MODAL + ' .modal-body').scrollTop(0);
        $(MODAL).scrollTop(0);
      });
    }, 250);
  });
  $(MODAL).on('hide.bs.modal', function () { clearInterval(ticker); clearTimeout(timer); save(); });
  $(document).on('click', '#srDraftFresh', function () {
    clear();
    $('#srDraftNote').remove();
    if (typeof window.resetRequestForm === 'function') { window.resetRequestForm(); }
    done = false;
  });
  window.addEventListener('pagehide', save);

  window.bgSrDraft = { clear: clear, save: save, read: read };
})();
