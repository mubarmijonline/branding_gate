"""
Client invoice arithmetic, kept apart from the routes so it can be checked on
its own against Finance's sample (invoice 2452).

Per line:   sales value = qty x unit price - cash discount
            VAT         = vat rate x sales value
Invoice:    subtotal    = sum of sales values
            VAT         = sum of line VAT
            profit tax  = profit-tax rate x subtotal, when the client withholds it
            total       = subtotal + VAT - profit tax

The 1% commercial-profits tax (أ.ت.ص) is withheld by the client, so it comes
off what they pay. Money is Decimal, rounded half-up to the piastre per line
and per total, the way the sample sheet rounds.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal('0.01')
DEFAULT_VAT_RATE = Decimal('14')
DEFAULT_PROFIT_TAX_RATE = Decimal('1')


def money(value):
    """A Decimal to the piastre; blanks are zero."""
    if value in (None, ''):
        return Decimal('0.00')
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def compute_line(qty, unit_price, cash_discount=0, vat_rate=DEFAULT_VAT_RATE):
    """{'sales_value', 'vat', 'line_total'} for one line. Refuses negatives."""
    qty = Decimal(str(qty or 0))
    price = money(unit_price)
    discount = money(cash_discount)
    if qty < 0 or price < 0 or discount < 0:
        raise ValueError('Quantity, price and discount cannot be negative')
    sales_value = money(qty * price - discount)
    if sales_value < 0:
        raise ValueError('The discount is larger than the line')
    vat = money(sales_value * Decimal(str(vat_rate)) / 100)
    return {'sales_value': sales_value, 'vat': vat, 'line_total': sales_value + vat}


def compute_invoice(lines, vat_rate=DEFAULT_VAT_RATE, profit_tax_rate=DEFAULT_PROFIT_TAX_RATE,
                    apply_profit_tax=True):
    """
    `lines`: iterables of dicts with qty, unit_price and optional cash_discount.
    Returns the lines' figures and the invoice totals.
    """
    computed = [compute_line(l.get('qty'), l.get('unit_price'), l.get('cash_discount'), vat_rate)
                for l in lines]
    subtotal = sum((c['sales_value'] for c in computed), Decimal('0.00'))
    discount = sum((money(l.get('cash_discount')) for l in lines), Decimal('0.00'))
    vat = sum((c['vat'] for c in computed), Decimal('0.00'))
    profit_tax = money(subtotal * Decimal(str(profit_tax_rate)) / 100) if apply_profit_tax else Decimal('0.00')
    return {
        'lines': computed,
        'subtotal': subtotal,
        'cash_discount_total': discount,
        'vat_total': vat,
        'profit_tax_total': profit_tax,
        'total': subtotal + vat - profit_tax,
    }


if __name__ == '__main__':
    # Finance's sample, invoice 2452: LED Screen 105,600 + stage 52,000.
    sample = compute_invoice([{'qty': 1, 'unit_price': '105600'}, {'qty': 1, 'unit_price': '52000'}])
    assert sample['lines'][0]['vat'] == Decimal('14784.00')
    assert sample['lines'][0]['line_total'] == Decimal('120384.00')
    assert sample['subtotal'] == Decimal('157600.00')
    assert sample['vat_total'] == Decimal('22064.00')
    assert sample['profit_tax_total'] == Decimal('1576.00')
    assert sample['total'] == Decimal('178088.00')
    assert compute_invoice([{'qty': 1, 'unit_price': 100}], apply_profit_tax=False)['total'] == Decimal('114.00')
    print('invoicing: sample 2452 ok')
