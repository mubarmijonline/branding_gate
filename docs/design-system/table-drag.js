function getTableScrollTarget(origin) {
  if (!origin) return null;
  return origin.closest('.dataTables_scrollBody, .table-responsive, .dataTables_wrapper, table.finance-table, table.balances-table, table.expense-table, table.transfers-table');
}

document.addEventListener('pointerdown', function(e) {
  var target = getTableScrollTarget(e.target);
  var drag;

  if (e.tableDragHandled) return;
  e.tableDragHandled = true;
  if (!target || (e.pointerType === 'mouse' && e.button !== 0)) return;
  if (e.target.closest('button, a, input, select, textarea, label, .dropdown-menu')) return;
  if (target.scrollWidth <= target.clientWidth + 2) return;

  drag = {
    startX: e.clientX,
    scrollLeft: target.scrollLeft
  };

  target.classList.add('bg-table-dragging');
  if (target.setPointerCapture && e.pointerId !== undefined) {
    target.setPointerCapture(e.pointerId);
  }

  target.addEventListener('pointermove', moveTable, { passive: false });
  target.addEventListener('pointerup', stopTable, { once: true });
  target.addEventListener('pointercancel', stopTable, { once: true });
  target.addEventListener('lostpointercapture', stopTable, { once: true });

  function moveTable(moveEvent) {
    target.scrollLeft = drag.scrollLeft + (drag.startX - moveEvent.clientX);
    moveEvent.preventDefault();
  }

  function stopTable(upEvent) {
    target.removeEventListener('pointermove', moveTable);
    target.classList.remove('bg-table-dragging');
    if (target.releasePointerCapture && upEvent.pointerId !== undefined) {
      try {
        target.releasePointerCapture(upEvent.pointerId);
      } catch (ignore) {}
    }
  }

  e.preventDefault();
}, false);
