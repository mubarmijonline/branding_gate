ALTER TABLE negotiation_requests
    MODIFY COLUMN status ENUM(
        'pending_sales_head',
        'sales_head_approved',
        'sales_head_declined',
        'pending_costing',
        'pending_pricing',
        'pricing_completed',
        'pricing_declined',
        'pending_selling_price',
        'completed'
    ) NOT NULL DEFAULT 'pending_sales_head';
