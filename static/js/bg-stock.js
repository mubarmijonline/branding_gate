/*
 * Where an item's stock stands against its own minimum.
 *
 * One reading, shared by the inventory list and the item page, so the badge on
 * a row and the badge on the item it opens can never disagree about whether
 * something is low.
 */
(function () {
  function bgStockState(item) {
    var stock = Number(item.quantity_in_stock || 0);
    var minLevel = Number(item.minimum_stock_level || 0);
    if (String(item.status || '').toLowerCase() === 'discontinued') {
      return { key: 'retired', label: 'Retired', badge: 'status-neutral', icon: 'fa-archive' };
    }
    if (stock <= 0) {
      return { key: 'out', label: 'Out of Stock', badge: 'status-danger', icon: 'fa-flag' };
    }
    if (minLevel > 0 && stock <= minLevel) {
      return { key: 'below', label: 'Below Minimum', badge: 'status-danger', icon: 'fa-flag' };
    }
    // Close enough to the minimum to be worth ordering before it is hit.
    if (minLevel > 0 && stock <= minLevel * 1.2) {
      return { key: 'near', label: 'Near Minimum', badge: 'status-warning', icon: 'fa-exclamation-triangle' };
    }
    return { key: 'ok', label: 'In Stock', badge: 'status-success', icon: '' };
  }

  window.bgStockState = bgStockState;
})();
