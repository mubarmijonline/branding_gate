/*
 * One row per item name, on every page that adds inventory items.
 *
 * The server refuses a new item whose name matches an existing one (spelling
 * variants included) with 409 and the existing item. This file
 *   - warns while the name is typed:   bgItemTwin.watch(input, contextFn)
 *   - turns the refusal into a choice: bgItemTwin.resolve(result, {quantity, unitCost, lotCode})
 *     -> "Add to existing stock" (a stock-in on the existing item) or "Discard".
 * resolve() returns a Promise of true when the duplicate was dealt with
 * (added or discarded), false when the result was not a duplicate.
 */
(function () {
    'use strict';

    function esc(v) {
        return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function num(v) { return Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 2 }); }

    function describe(twin) {
        return '<b data-no-i18n>' + esc(twin.item_name) + '</b> <span data-no-i18n>(' + esc(twin.item_code) + ')</span>' +
            ' &middot; Current stock: <b>' + num(twin.quantity_in_stock) + '</b> ' + esc(twin.unit_of_measure || '');
    }

    function addToExisting(twin, quantity, unitCost, lotCode) {
        // The code typed for the new item (e.g. "10") becomes the code its
        // stock sits under inside the existing item.
        var req = twin.is_credit && twin.credit_id
            ? { url: '/api/inventory/credit-items/' + twin.credit_id + '/add-quantity',
                body: { quantity: quantity, cost_per_item: unitCost || 0, lot_code: lotCode || null,
                        notes: 'Added from a duplicate entry' } }
            : { url: '/api/inventory/transactions/add',
                body: { item_id: twin.id, transaction_type: 'purchase', quantity: quantity, lot_code: lotCode || null,
                        unit_cost: unitCost || 0, notes: 'Added from a duplicate entry' } };
        return fetch(req.url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(req.body) })
            .then(function (r) { return r.json(); });
    }

    function resolve(result, entry) {
        var twin = result && result.duplicate;
        if (!twin) return Promise.resolve(false);
        var quantity = parseFloat(entry && entry.quantity) || 0;
        var unitCost = parseFloat(entry && entry.unitCost) || 0;
        var canAdd = quantity > 0;
        var lotCode = String((entry && entry.lotCode) || '').trim();
        if (lotCode && lotCode === twin.item_code) lotCode = '';
        return Swal.fire({
            icon: 'warning',
            title: 'Item already exists',
            html: '<div style="text-align:start">' + describe(twin) + '<br><br>' +
                (canAdd ? 'Add the <b>' + num(quantity) + '</b> you entered to its stock' +
                    (lotCode ? ' under code <b data-no-i18n>' + esc(lotCode) + '</b>' : '') + ', or discard this entry.'
                        : 'An item cannot be created twice. Open the existing one, or discard this entry.') + '</div>',
            showDenyButton: true,
            showCancelButton: false,
            confirmButtonText: canAdd ? 'Add to existing stock' : 'Open existing item',
            denyButtonText: 'Discard',
            confirmButtonColor: '#10b981',
            denyButtonColor: '#64748b',
            allowOutsideClick: false
        }).then(function (choice) {
            if (choice.isDenied || !choice.isConfirmed) return true;
            if (!canAdd) {
                if (!twin.is_credit) window.location.href = '/inventory/item/' + twin.id;
                return true;
            }
            return addToExisting(twin, quantity, unitCost, lotCode).then(function (res) {
                if (res && res.success) {
                    Swal.fire('Stock updated', 'Added ' + num(quantity) + ' to ' + twin.item_name + '.', 'success');
                } else {
                    Swal.fire('Error', (res && (res.error || res.message)) || 'Could not update the stock', 'error');
                }
                return true;
            });
        });
    }

    function watch(input, contextFn) {
        var $input = $(input);
        if (!$input.length || $input.data('twinWatch')) return;
        $input.data('twinWatch', 1);
        var note = $('<div class="bg-twin-note" style="display:none"></div>').insertAfter($input);
        var timer, last = '';
        $input.on('input', function () {
            clearTimeout(timer);
            var name = $input.val().trim();
            if (!name) { note.hide(); last = ''; return; }
            timer = setTimeout(function () {
                if (name === last) return;
                last = name;
                var ctx = (contextFn && contextFn()) || {};
                var q = new URLSearchParams({ name: name });
                if (ctx.entity_id) q.set('entity_id', ctx.entity_id);
                if (ctx.credit) q.set('credit', '1');
                if (ctx.exclude_id) q.set('exclude_id', ctx.exclude_id);
                fetch('/api/inventory/items/name-check?' + q.toString())
                    .then(function (r) { return r.json(); })
                    .then(function (res) {
                        if ($input.val().trim() !== name) return;
                        if (res && res.duplicate) {
                            note.html('<i class="fas fa-exclamation-triangle"></i> Already exists: ' + describe(res.duplicate) +
                                '. Saving will offer to add to its stock.').show();
                        } else {
                            note.hide();
                        }
                    })
                    .catch(function () { note.hide(); });
            }, 350);
        });
    }

    window.bgItemTwin = { watch: watch, resolve: resolve };

    var style = document.createElement('style');
    style.textContent = '.bg-twin-note{margin-top:6px;padding:8px 10px;border-radius:8px;background:#fff7ed;' +
        'border:1px solid #fdba74;color:#9a3412;font-size:12.5px;line-height:1.5}';
    document.head.appendChild(style);
})();
