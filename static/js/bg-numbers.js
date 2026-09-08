/*
 * Numbers, read and typed the same way everywhere.
 *
 * Two jobs, both of which were being done differently on every page:
 *
 *   Reading   a table cell that says "292975" is a number nobody can read at a
 *             glance. Every amount is grouped: 292,975.
 *   Typing    an amount is typed with separators and stored without them, so
 *             the grouping is applied to the digits as they are typed and
 *             stripped again on the way to the server.
 *
 * There were four copies of this logic in four templates and a dozen places
 * with no formatting at all. This is the one copy.
 */
(function (window, document) {
  'use strict';

  function isBlank(value) {
    return value === null || value === undefined || value === '' ||
           (typeof value === 'string' && value.trim() === '');
  }

  /* A number for reading. Whole by default, because most amounts here are
     whole; pass decimals when the fraction matters. */
  function bgNumber(value, decimals) {
    if (isBlank(value)) { return '-'; }
    var n = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
    if (!isFinite(n)) { return String(value); }
    var places = decimals === undefined || decimals === null ? 0 : decimals;
    return n.toLocaleString('en-US', {
      minimumFractionDigits: places,
      maximumFractionDigits: places
    });
  }

  /* Money for reading: two decimals, and the currency in front of it. */
  function bgMoney(value, currency) {
    if (isBlank(value)) { return '-'; }
    var body = bgNumber(value, 2);
    if (body === '-') { return body; }
    return (currency === undefined ? 'EGP ' : (currency ? currency + ' ' : '')) + body;
  }

  /* The digits of a half-typed amount, grouped. Applied to the digits only, so
     the caret keeps its place and the value stays a string the server can
     parse once the separators come out. */
  function bgGroupDigits(text) {
    var negative = /^\s*-/.test(text);
    var cleaned = String(text === null || text === undefined ? '' : text)
                    .replace(/[^0-9.]/g, '');
    var parts = cleaned.split('.');
    var whole = parts.shift().replace(/^0+(?=\d)/, '');
    var rest = parts.length ? '.' + parts.join('').slice(0, 2) : '';
    if (whole === '') { return negative ? '-' : (rest ? '0' + rest : ''); }
    return (negative ? '-' : '') +
           whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + rest;
  }

  /* What the server should be given: the same string without the separators. */
  function bgPlainNumber(text) {
    if (isBlank(text)) { return ''; }
    return String(text).replace(/,/g, '').trim();
  }

  /* Group as it is typed, keeping the caret where the typist left it. */
  function groupInPlace(input) {
    var before = input.value;
    var grouped = bgGroupDigits(before);
    if (grouped === before) { return; }
    var caretFromEnd = before.length - (input.selectionStart || 0);
    input.value = grouped;
    var caret = Math.max(0, grouped.length - caretFromEnd);
    try { input.setSelectionRange(caret, caret); } catch (e) { /* not focusable */ }
  }

  /* Which inputs want grouping. `type=number` cannot hold a comma, so an
     amount field that wants separators has to be a text field -- marking one
     switches it over rather than silently doing nothing. */
  var SELECTOR = 'input.bg-amount, input[data-group-digits]';

  function prepare(input) {
    if (input.getAttribute('type') === 'number') {
      input.setAttribute('type', 'text');
      input.setAttribute('inputmode', 'decimal');
    }
    if (input.value) { input.value = bgGroupDigits(input.value); }
  }

  function bgAttachGrouping(root) {
    var scope = root && root.querySelectorAll ? root : document;
    Array.prototype.forEach.call(scope.querySelectorAll(SELECTOR), prepare);
  }

  /* Delegated, so an input rendered into a modal five minutes from now needs
     no wiring of its own. */
  document.addEventListener('input', function (event) {
    var input = event.target;
    if (input && input.matches && input.matches(SELECTOR)) { groupInPlace(input); }
  }, true);

  document.addEventListener('focusin', function (event) {
    var input = event.target;
    if (input && input.matches && input.matches(SELECTOR)) { prepare(input); }
  }, true);

  /* A form must never post "1,250" to a route that calls float() on it. The
     separators come out on the way past, and go back afterwards so the field
     the user is looking at does not flicker. */
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form || !form.querySelectorAll) { return; }
    Array.prototype.forEach.call(form.querySelectorAll(SELECTOR), function (input) {
      var shown = input.value;
      input.value = bgPlainNumber(shown);
      setTimeout(function () { input.value = shown; }, 0);
    });
  }, true);

  document.addEventListener('DOMContentLoaded', function () { bgAttachGrouping(document); });

  window.bgNumber = bgNumber;
  window.bgMoney = bgMoney;
  window.bgGroupDigits = bgGroupDigits;
  window.bgPlainNumber = bgPlainNumber;
  window.bgAttachGrouping = bgAttachGrouping;
}(window, document));
