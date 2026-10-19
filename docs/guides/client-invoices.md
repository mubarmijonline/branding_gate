# Client invoices and statements: how to use them

## For Finance (George)

Everything about clients is under **Finance > Clients**: *Client Accounts &
Statements*, *Invoices & Refunds*, *Combined Balances*; the same three tabs sit
at the top of each of those pages.

**1. Load the item list (once).**
Finance > Client Invoices > *Invoice Items* > **Import Excel**. The sheet needs
three columns: `كود`, `اسم المنتج`, `code name`. Existing codes are updated, new
ones added, nothing is deleted. Items can also be added or edited one by one
(**Add item**, or the pen on a row); untick *Active* to hide an item from new
invoices without losing it from old ones.

**Set the invoice series once.** On *Invoice Items*, **Next invoice number**:
enter the number after your last paper invoice (e.g. 2553) and **Set**. Every
new invoice takes the next number in the series as soon as it is drafted; a
cancelled draft gives its number back.

**2. Post invoices.**
You are notified when an account manager sends one. Finance > Client Invoices,
card **With Finance**, open the invoice:
- check the lines, item codes, prices, dates and the 1% tick; you may correct
  them in the window;
- **Post to client account**: confirm the number, choose the **payment method**
  the money came into, and the **amount received now** (the full total by
  default; 0 if the client has not paid yet), then **Post**. The invoice is
  locked and on the client's account, and the money received is booked in that
  payment method: it shows in the payment method's balance and in Finance's
  reports, and as a collection on the statement;
- or **Return** with what needs fixing; it goes back to its author.
Each line carries its SR item's id as its code, so nothing waits on the item list.

**3. Record what the client pays.** Open a posted invoice > **Record payment
received**: amount (the remaining balance is filled in), the payment method it
came into, date and cheque / transfer number. It becomes a *Client Payment* in
Finance (linked to the SR and client, referenced "Invoice N"), shows under
*Payments received* on the invoice, and is a credit on the statement once
approved.

**Refunds (فاتورة مرتجع).** Open a posted invoice > **Create refund**, tick the
items to refund; each ticked item is refunded in full (all of it not refunded
already), add the reason, **Create refund draft**. It is calculated at the
invoice's prices, VAT 14% and the 1% if the invoice had it. **Post refund**:
choose the payment method and the amount paid back to the client (0 if
nothing is paid back, e.g. the invoice was not paid). It is a credit on the
statement (*Refund R-n*); money paid back is a debit (*Refund paid back*) and
comes out of the payment method. Refunds have their own series (R-1, R-2 ...).

**4. Print.** Open the invoice > **Print** (the layout of your sample sheet).

**5. Statement of account.** Finance > Client Accounts > open the company or
the client > tab **Statement of Account**: company, company code and client at
the top, then Date, Job code (SR), Invoice no., Description, Debit, Credit,
Balance. Collections read *Cash collection (safe)* or *Cheque / bank
collection (bank)* from the payment method they came into. **Set opening
balance** enters what the client owed before the system (رصيد أول المدة;
negative if you owe them). Posted invoices are debits,
approved payments received are credits, with a running balance. Use *From /
To* at the top for a period (earlier entries become the opening balance), and
**Export statement** for Excel (in your sheet's layout, right to left). The
figures at the top now include **Invoiced** and **Balance Due** (invoiced
minus collected).

**6. All client accounts together (مجمع حسابات العملاء).** Client Accounts >
**Combined balances**: every company (or, *By client*, every client) with
opening, debit, credit and balance for the period, totals, and Excel export.

## For account managers (Gamal, Sarah, Mariam ...)

1. Sales > **Invoices** > **New invoice**.
2. Choose the **Sales Request**. Its client, company and client-approved items
   fill the invoice, with their prices; a line already on another invoice is
   flagged.
3. Lines are the SR's client-approved items only, each coded with the item's
   own id (e.g. #6382), automatically: nothing is typed or chosen. Quantity, price and cash
   discount can be adjusted; a line can be removed and put back from
   *Add an item from this SR*.
4. Set the **invoice date** and **billing month**. Leave **Deduct 1%** ticked
   unless the client does not withhold the commercial profits tax.
5. **Save draft** to finish later, or **Save and send to Finance**.
6. If Finance returns it, you are notified with the reason; fix it and send
   again. Once posted you are notified with its number.

## The arithmetic
Per line: sales value = qty x price - cash discount; VAT = 14% of it.
Invoice: total before tax + VAT - 1% profits tax (when ticked) = total.
(Sample 2452: 157,600 + 22,064 - 1,576 = 178,088.)

---

# فواتير العملاء وكشوف الحساب: طريقة الاستخدام

## للمالية (جورج)
كل ما يخص العملاء في **المالية > العملاء**: حسابات العملاء وكشوف الحساب، الفواتير والمرتجعات، مجمع حسابات العملاء.
- **الترحيل:** اختر طريقة الدفع والمبلغ المستلم الآن (الإجمالي افتراضيًا، أو 0 إذا لم يدفع العميل)، فيُسجّل في رصيد طريقة الدفع وتقارير المالية.
- **المرتجع:** من فاتورة مرحّلة > إنشاء مرتجع، حدّد البنود المرتجعة (كل بند يُرتجع بالكامل)، ثم ترحيل المرتجع مع طريقة الدفع والمبلغ المردود. يظهر دائنًا في كشف الحساب، والمبلغ المردود مدينًا ويُخصم من طريقة الدفع.
1. **قائمة الأصناف (مرة واحدة):** المالية > فواتير العملاء > أصناف الفاتورة > استيراد Excel
   (أعمدة: كود، اسم المنتج، code name). يمكن الإضافة والتعديل يدويًا لاحقًا.
2. **ترحيل الفواتير:** يصلك إشعار عند الإرسال. افتح الفاتورة من بطاقة "لدى المالية"،
   راجعها ويمكنك التعديل، ثم "ترحيل إلى حساب العميل" وأكّد رقم الفاتورة (أول رقم متاح،
   غيّره مرة واحدة ليكمل تسلسلكم الحالي مثل 2453) ثم "ترحيل". أو "إرجاع" مع سبب.
   كود كل بند هو رقم البند في الطلب تلقائيًا.
3. **تسجيل التحصيل:** افتح فاتورة مرحّلة > "تسجيل دفعة مستلمة" (المبلغ المتبقي مكتوب تلقائيًا،
   وطريقة الدفع، والتاريخ، ورقم الشيك أو التحويل). تُسجّل كمدفوعات عملاء في المالية وتظهر في كشف الحساب.
4. **الطباعة:** افتح الفاتورة > طباعة (بنفس شكل النموذج).
5. **كشف الحساب:** المالية > حسابات العملاء > افتح الشركة أو العميل > تبويب "كشف الحساب":
   الفواتير المرحّلة مدينة والمدفوعات المعتمدة دائنة مع رصيد متحرك، وتحديد فترة، وتصدير Excel.
   وتظهر بالأعلى "المفوتر" و"الرصيد المستحق".

## لمديري الحسابات
1. المبيعات > الفواتير > فاتورة جديدة، واختر طلب المبيعات: تمتلئ البيانات والبنود المعتمدة بأسعارها.
2. كود كل بند هو رقم البند في الطلب تلقائيًا. يمكن تعديل الكمية أو السعر أو الخصم، وحذف بند وإعادته من بنود الطلب.
3. حدد تاريخ الفاتورة وشهر المطالبة، واترك "خصم 1%" مفعّلًا إلا إذا كان العميل لا يخصمها.
4. "حفظ كمسودة" أو "حفظ وإرسال للمالية". عند الإرجاع يصلك السبب، وعند الترحيل يصلك رقم الفاتورة.


## Suppliers (Finance > Suppliers)

**Supplier Accounts & Statements** lists every supplier with the balance
brought forward, purchases (the cost of SR items they supplied, once the client
approved), what was paid to them, and what we still owe. Pick a period, export
to Excel (مجمع حسابات الموردين). Click a supplier for its statement: Date, Job
code (SR), Entry, Description, Debit (paid), Credit (supplied), Balance owed;
Excel كشف حساب مورد.

- **Record payment:** choose the payment method the money leaves, the amount,
  the date, optionally the SR and a cheque / transfer reference. It is booked
  at once as an approved Supplier Payments expense, so it appears in Finance
  Management and the payment method's balance.
- **Opening balance:** what we owed the supplier before the system (negative
  for an advance we had paid).

**الموردون:** من **المالية > الموردون** تظهر حسابات كل الموردين (أول المدة،
المشتريات، المدفوع، المستحق) ويمكن تصديرها إكسل. اضغط على المورد لكشف حسابه.
**تسجيل دفعة** يخصم المبلغ من وسيلة الدفع ويظهر في الإدارة المالية كمدفوعات
موردين. **رصيد أول المدة** لما كان مستحقًا قبل النظام.

The bar at the top of every Finance page links all Finance pages (Overview,
Management, Approvals, Clients, Suppliers, Expenses).
