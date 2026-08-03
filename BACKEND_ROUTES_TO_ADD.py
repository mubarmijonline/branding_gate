# Sales Head Approval Backend Routes
# Add these routes to branding_gate.py after the client approval routes

# =============================================================================
# SALES HEAD APPROVAL ROUTES
# =============================================================================

@app.route('/sales-head-approval')
@role_required('sales_head', 'admin')
def sales_head_approval_page():
    """Sales Head Approval page"""
    return render_template('sales_head_approval.html')

@app.route('/api/sales-head/negotiations', methods=['GET'])
@role_required('sales_head', 'admin')
def get_sales_head_negotiations():
    """Get all negotiation requests for sales head review"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        status = request.args.get('status', 'pending_sales_head')
        client_id = request.args.get('client_id')
        date_range = request.args.get('date_range', 'all')
        
        conn, cur = connection()
        
        # Build WHERE clause
        where_clauses = []
        params = []
        
        if status:
            where_clauses.append("nr.status = %s")
            params.append(status)
        
        if client_id:
            where_clauses.append("sr.client_id = %s")
            params.append(client_id)
        
        # Date filter
        if date_range == 'today':
            where_clauses.append("DATE(nr.created_at) = CURDATE()")
        elif date_range == 'week':
            where_clauses.append("nr.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)")
        elif date_range == 'month':
            where_clauses.append("nr.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get negotiations with item and request details
        query = f"""
            SELECT 
                nr.*,
                sri.name as item_name,
                sri.qty as quantity,
                sri.unit,
                sri.sell_per_item as current_selling_price,
                sri.cost_per_item as current_cost_price,
                sri.negotiation_count,
                sr.id as request_id,
                c.client_name
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            INNER JOIN sales_request sr ON nr.request_id = sr.id
            LEFT JOIN client c ON sr.client_id = c.id
            WHERE {where_sql}
            ORDER BY nr.created_at DESC
        """
        
        cur.execute(query, params)
        negotiations = cur.fetchall()
        
        # Convert to list of dicts
        result = []
        for neg in negotiations:
            result.append({
                'id': neg['id'],
                'item_id': neg['item_id'],
                'request_id': neg['request_id'],
                'item_name': neg['item_name'],
                'quantity': float(neg['quantity']) if neg['quantity'] else 0,
                'unit': neg['unit'],
                'client_expected_price': float(neg['client_expected_price']) if neg['client_expected_price'] else 0,
                'client_reason': neg['client_reason'],
                'current_selling_price': float(neg['current_selling_price']) if neg['current_selling_price'] else 0,
                'current_cost_price': float(neg['current_cost_price']) if neg['current_cost_price'] else 0,
                'status': neg['status'],
                'sales_head_decision': neg['sales_head_decision'],
                'sales_head_notes': neg['sales_head_notes'],
                'client_name': neg['client_name'],
                'negotiation_count': neg['negotiation_count'] or 0,
                'created_at': neg['created_at'].strftime('%Y-%m-%d %H:%M:%S') if neg['created_at'] else None
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'negotiations': result
        })
        
    except Exception as e:
        print(f"Error getting negotiations: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-head/negotiations/statistics', methods=['GET'])
@role_required('sales_head', 'admin')
def get_sales_head_statistics():
    """Get statistics for sales head dashboard"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Pending count
        cur.execute("""
            SELECT COUNT(*) as count
            FROM negotiation_requests
            WHERE status = 'pending_sales_head'
        """)
        pending = cur.fetchone()['count']
        
        # Approved today
        cur.execute("""
            SELECT COUNT(*) as count
            FROM negotiation_requests
            WHERE status = 'sales_head_approved'
            AND DATE(sales_head_decision_date) = CURDATE()
        """)
        approved_today = cur.fetchone()['count']
        
        # Declined today
        cur.execute("""
            SELECT COUNT(*) as count
            FROM negotiation_requests
            WHERE status = 'sales_head_declined'
            AND DATE(sales_head_decision_date) = CURDATE()
        """)
        declined_today = cur.fetchone()['count']
        
        # Potential savings (difference between current price and expected price for pending)
        cur.execute("""
            SELECT 
                SUM((sri.sell_per_item - nr.client_expected_price) * sri.qty) as savings
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            WHERE nr.status = 'pending_sales_head'
            AND sri.sell_per_item IS NOT NULL
        """)
        savings_result = cur.fetchone()
        potential_savings = float(savings_result['savings']) if savings_result['savings'] else 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'pending': pending,
                'approved_today': approved_today,
                'declined_today': declined_today,
                'potential_savings': potential_savings
            }
        })
        
    except Exception as e:
        print(f"Error getting statistics: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-head/negotiations/<int:negotiation_id>/approve', methods=['POST'])
@role_required('sales_head', 'admin')
def approve_sales_head_negotiation(negotiation_id):
    """Approve negotiation - send to pricing team"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        notes = data.get('notes', '')
        user_id = session.get('user_id')
        user_name = session.get('name', 'Sales Head')
        
        conn, cur = connection()
        
        # Get negotiation details
        cur.execute("""
            SELECT nr.*, sri.name as item_name, sri.request_id
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            WHERE nr.id = %s
        """, (negotiation_id,))
        
        negotiation = cur.fetchone()
        
        if not negotiation:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation not found'}), 404
        
        if negotiation['status'] != 'pending_sales_head':
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation already processed'}), 400
        
        # Update negotiation status
        cur.execute("""
            UPDATE negotiation_requests
            SET status = 'pending_pricing',
                sales_head_decision = 'approved',
                sales_head_notes = %s,
                sales_head_user_id = %s,
                sales_head_decision_date = NOW()
            WHERE id = %s
        """, (notes, user_id, negotiation_id))
        
        # Log the approval
        cur.execute("""
            INSERT INTO negotiation_logs
            (negotiation_id, action, actor_user_id, actor_name, notes)
            VALUES (%s, 'sales_head_approved', %s, %s, %s)
        """, (negotiation_id, user_id, user_name, notes or 'Approved by sales head'))
        
        # Update item status - keep as pending_negotiation but mark for pricing
        cur.execute("""
            UPDATE sales_request_items
            SET negotiation_status = 'pending_negotiation',
                client_feedback = CONCAT(COALESCE(client_feedback, ''), ' | Sales Head Approved. Sent to Pricing Team.')
            WHERE id = %s
        """, (negotiation['item_id'],))
        
        # Log in main change log
        log_item_change(
            request_id=negotiation['request_id'],
            item_id=negotiation['item_id'],
            item_name=negotiation['item_name'],
            request_type='Negotiation',
            action_type='SALES_HEAD_APPROVED',
            action_by=user_name,
            old_data={'status': 'pending_sales_head'},
            new_data={'status': 'pending_pricing', 'notes': notes},
            change_description=f"[Sales Head] Approved negotiation for '{negotiation['item_name']}'. Sent to Pricing Team. Expected price: EGP {float(negotiation['client_expected_price'])}",
            conn=conn,
            cur=cur
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Negotiation approved and sent to Pricing Team'
        })
        
    except Exception as e:
        print(f"Error approving negotiation: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-head/negotiations/<int:negotiation_id>/decline', methods=['POST'])
@role_required('sales_head', 'admin')
def decline_sales_head_negotiation(negotiation_id):
    """Decline negotiation - return to client approval"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        reason = data.get('reason', '')
        user_id = session.get('user_id')
        user_name = session.get('name', 'Sales Head')
        
        if not reason:
            return jsonify({'success': False, 'error': 'Reason is required'}), 400
        
        conn, cur = connection()
        
        # Get negotiation details
        cur.execute("""
            SELECT nr.*, sri.name as item_name, sri.request_id
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            WHERE nr.id = %s
        """, (negotiation_id,))
        
        negotiation = cur.fetchone()
        
        if not negotiation:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation not found'}), 404
        
        if negotiation['status'] != 'pending_sales_head':
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation already processed'}), 400
        
        # Update negotiation status
        cur.execute("""
            UPDATE negotiation_requests
            SET status = 'sales_head_declined',
                sales_head_decision = 'declined',
                sales_head_notes = %s,
                sales_head_user_id = %s,
                sales_head_decision_date = NOW()
            WHERE id = %s
        """, (reason, user_id, negotiation_id))
        
        # Log the decline
        cur.execute("""
            INSERT INTO negotiation_logs
            (negotiation_id, action, actor_user_id, actor_name, notes)
            VALUES (%s, 'sales_head_declined', %s, %s, %s)
        """, (negotiation_id, user_id, user_name, reason))
        
        # Update item status - return to pending client approval
        cur.execute("""
            UPDATE sales_request_items
            SET approval_status = 'pending',
                negotiation_status = 'none',
                client_feedback = CONCAT(COALESCE(client_feedback, ''), ' | Sales Head Declined: ', %s)
            WHERE id = %s
        """, (reason, negotiation['item_id']))
        
        # Log in main change log
        log_item_change(
            request_id=negotiation['request_id'],
            item_id=negotiation['item_id'],
            item_name=negotiation['item_name'],
            request_type='Negotiation',
            action_type='SALES_HEAD_DECLINED',
            action_by=user_name,
            old_data={'status': 'pending_sales_head'},
            new_data={'status': 'declined', 'reason': reason},
            change_description=f"[Sales Head] Declined negotiation for '{negotiation['item_name']}'. Reason: {reason}. Returned to Pending Client Approval.",
            conn=conn,
            cur=cur
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Negotiation declined and returned to Pending Client Approval'
        })
        
    except Exception as e:
        print(f"Error declining negotiation: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
