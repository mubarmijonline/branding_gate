"""
Branding Gate's chart of accounts (دليل الحسابات), the Finance Tree.

Six classes, their groups and accounts, with Finance's codes. A row's parent is
the entry whose code is the longest prefix of its own (1 -> 11 -> 1101).
Fixed from the sheet: قروض بنكية is 2201 (the sheet repeated 2101); spelling
of البيعية، الأثاث، المستحقة.

The system books into some accounts by id (client payments are category 1 all
over the code), so those rows keep their ids and become their accounts:
SYSTEM_IDS. Custody and staff loans are four sub-accounts of 1110.

    python finance_chart.py      # apply to the database (idempotent)
"""

# (code, name). Parents come before their children.
CHART = [
    ('1', 'الاصول'),
    ('11', 'الاصول المتداولة'),
    ('1101', 'الخزينة'),
    ('1102', 'البنك'),
    ('1103', 'العملاء'),
    ('1104', 'اوراق القبض'),
    ('1105', 'المخزون'),
    ('1106', 'ضريبة القيمة المضافة بالنسبة للمشتريات'),
    ('1107', 'ضريبة الخصم والتحصيل'),
    ('1108', 'دفعات مقدمة للموردين'),
    ('1109', 'مصروفات مدفوعة مقدما'),
    ('1110', 'سلف وعهد للموظفين'),
    ('111001', 'صرف عهدة للموظفين'),
    ('111002', 'تسوية عهدة الموظفين'),
    ('111003', 'سلف الموظفين'),
    ('111004', 'سداد سلف الموظفين'),
    ('1111', 'ايرادات مستحقة'),
    ('12', 'اصول ثابتة'),
    ('1201', 'الاراضى والمبانى'),
    ('1202', 'السيارات ووسائل النقل'),
    ('1203', 'الأثاث والتجهيزات'),
    ('1204', 'اجهزة الكمبيوتر والمعدات'),
    ('1205', 'مجمع اهلاك الاصول الثابتة'),
    ('2', 'الخصوم'),
    ('21', 'خصوم متداولة'),
    ('2101', 'الموردين'),
    ('2102', 'اوراق دفع'),
    ('2103', 'ضريبة القيمة المضافة للمبيعات'),
    ('2104', 'ضريبة الخصم والتحصيل المستحقة'),
    ('2105', 'ضريبة كسب العمل'),
    ('2106', 'التامينات الاجتماعية'),
    ('2107', 'ضرائب ورسوم اخرى (مثل الغرامات)'),
    ('2108', 'مصروفات مستحقة'),
    ('2109', 'مرتبات واجور مستحقة'),
    ('2110', 'دفعات مقدمة من العملاء'),
    ('2111', 'ايرادات مقبوضة مقدما'),
    ('22', 'خصوم طويلة الاجل'),
    ('2201', 'قروض بنكية'),
    ('3', 'حقوق الملكية'),
    ('3101', 'راس المال'),
    ('3102', 'الاحتياطى القانونى'),
    ('3103', 'الارباح او الخسائر المرحلة'),
    ('3104', 'جارى الشركاء'),
    ('4', 'الايرادات'),
    ('41', 'ايرادات النشاط'),
    ('4101', 'المبيعات'),
    ('4102', 'مردودات ومسموحات المبيعات'),
    ('4103', 'خصم نقدى مسموح به'),
    ('42', 'ايرادات اخرى'),
    ('4201', 'ايرادات اخرى متنوعة'),
    ('4202', 'فوائد دائنة'),
    ('4203', 'ارباح بيع الاصول'),
    ('5', 'تكلفة المبيعات'),
    ('5101', 'تكلفة البضاعة المباعة'),
    ('5102', 'فرق جرد هالك المخزون'),
    ('6', 'المصروفات'),
    ('61', 'المصروفات البيعية والتسويقية'),
    ('6101', 'دعاية واعلان'),
    ('6102', 'عمولة المبيعات'),
    ('6103', 'الشحن والتوصيل للعملاء'),
    ('62', 'المصروفات الادارية والعمومية'),
    ('6201', 'المرتبات والاجور'),
    ('6202', 'التامينات الاجتماعية'),
    ('6203', 'الايجارات'),
    ('6204', 'الكهرباء والمياه والغاز'),
    ('6205', 'التليفون والانترنت'),
    ('6206', 'صيانة'),
    ('6207', 'ادوات مكتبية ومطبوعات'),
    ('6208', 'اتعاب مهنية واستشارات'),
    ('6209', 'تامين'),
    ('6210', 'رسوم وتراخيص ومصروفات حكومية'),
    ('6211', 'ضيافة'),
    ('6212', 'انتقالات'),
    ('6213', 'ديون معدومة'),
    ('6214', 'مخصص ديون مشكوك فى تحصيلها'),
    ('63', 'الاهلاك'),
    ('6301', 'اهلاك الاصول الثابتة'),
    ('64', 'مصروفات تمويلية'),
    ('6401', 'فوائد مدينة'),
    ('6402', 'عمولات ومصروفات بنكية'),
]

# The rows the code books into by id, and the account each one now is.
SYSTEM_IDS = {
    1: '1103',     # Client Payments
    2: '4201',     # Other Income
    3: '111004',   # Pay Loan
    4: '3101',     # Opening Balance
    10: '2101',    # Supplier Payments
    11: '111003',  # Loan
    16: '111001',  # Internal Transfer (custody out)
    44: '111002',  # Internal Transfer (custody settled)
    46: '4102',    # Client Refunds
}
# Further accounts the system reads or books by code (invoices: 1107, 2103, 4101);
# they cannot be renamed or deleted.
SYSTEM_CODES = {'1', '2', '3', '4', '5', '6', '1101', '1102', '1107', '1110', '2103', '2104', '4101'} | set(SYSTEM_IDS.values())

CLASS_TYPE = {'1': 'asset', '2': 'liability', '3': 'equity', '4': 'income', '5': 'expense', '6': 'expense'}
# Debit-normal classes grow with money out; credit-normal ones with money in.
DEBIT_NORMAL = {'1', '5', '6'}


def parent_code(code, codes):
    """The longest proper prefix of `code` among `codes`, or None for a class."""
    for n in range(len(code) - 1, 0, -1):
        if code[:n] in codes:
            return code[:n]
    return None


def next_code(parent, sibling_codes):
    """The code a new account under `parent` takes: one past its siblings, or the first."""
    siblings = sorted((c for c in sibling_codes if c.startswith(parent) and c != parent), key=int)
    if siblings:
        last = siblings[-1]
        return str(int(last) + 1).zfill(len(last))
    return parent + ('1' if len(parent) == 1 else '01')


def migrate(cur):
    """Schema and data: the chart replaces the old categories. Safe to run again."""
    cur.execute("SHOW COLUMNS FROM finance_categories LIKE 'account_code'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE finance_categories ADD COLUMN account_code VARCHAR(12) NULL AFTER category_code, "
                    "ADD UNIQUE KEY uq_finance_account_code (account_code)")
    cur.execute("""ALTER TABLE finance_categories MODIFY category_type
                   ENUM('income','expense','asset','liability','equity') NOT NULL""")
    codes = {c for c, _ in CHART}
    by_code = {}
    system_by_code = {v: k for k, v in SYSTEM_IDS.items()}
    for order, (code, name) in enumerate(CHART, start=1):
        parent = parent_code(code, codes)
        values = (name, code, by_code.get(parent), CLASS_TYPE[code[0]], int(code in SYSTEM_CODES), order)
        row_id = system_by_code.get(code)
        if row_id is None:
            cur.execute("SELECT id FROM finance_categories WHERE account_code = %s", (code,))
            row = cur.fetchone()
            row_id = (row['id'] if isinstance(row, dict) else row[0]) if row else None
        if row_id is None:
            cur.execute("""INSERT INTO finance_categories (category_name, account_code, parent_id, category_type, is_system,
                               display_order, category_code, is_active, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 'chart')""", values + ('ACC_' + code,))
            row_id = cur.lastrowid
        else:
            cur.execute("""UPDATE finance_categories SET category_name = %s, account_code = %s, parent_id = %s,
                               category_type = %s, is_system = %s, display_order = %s, is_active = 1 WHERE id = %s""",
                        values + (row_id,))
        by_code[code] = row_id
    # The old categories go; any still referenced by a transaction is only hidden.
    cur.execute("""SELECT id FROM finance_categories fc WHERE account_code IS NULL
                   AND NOT EXISTS (SELECT 1 FROM finance_transactions ft WHERE fc.id IN (ft.category_id, ft.subcategory_id))
                   AND NOT EXISTS (SELECT 1 FROM expense_tracking_items ei WHERE fc.id IN (ei.category_id, ei.subcategory_id))""")
    unused = [r['id'] if isinstance(r, dict) else r[0] for r in cur.fetchall()]
    if unused:
        marks = ','.join(['%s'] * len(unused))
        cur.execute("UPDATE finance_categories SET parent_id = NULL WHERE id IN (%s)" % marks, unused)
        cur.execute("DELETE FROM finance_categories WHERE id IN (%s)" % marks, unused)
    cur.execute("UPDATE finance_categories SET is_active = 0, parent_id = NULL WHERE account_code IS NULL")
    return by_code


if __name__ == '__main__':
    import branding_gate
    conn, cur = branding_gate.connection()
    accounts = migrate(cur)
    conn.commit()
    print('chart applied: %d accounts' % len(accounts))
