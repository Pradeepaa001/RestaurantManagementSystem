from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime
import json
from dotenv import load_dotenv
from decimal import Decimal

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database configuration
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'restaurant_db')
}

def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            # Set autocommit to True to avoid transaction issues
            connection.autocommit = True
            return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        flash('Database connection error. Please try again later.', 'danger')
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Check customer credentials (only phone number)
            cursor.execute('SELECT * FROM customer WHERE c_phone = %s', (phone,))
            customer = cursor.fetchone()
            
            if customer:
                # Check if customer already has an assigned spot
                cursor.execute('SELECT * FROM spots WHERE cust_id = %s', (customer['cust_id'],))
                existing_spot = cursor.fetchone()
                
                if existing_spot:
                    # Customer already has a spot, log them in
                    session['user_id'] = customer['cust_id']
                    session['role'] = 'customer'
                    return redirect(url_for('menu'))
                
                # Find an available spot
                cursor.execute("""
                    SELECT s.* FROM spots s
                    WHERE s.availability = 1
                    LIMIT 1
                """)
                available_spot = cursor.fetchone()
                
                if available_spot:
                    # Assign spot to customer
                    cursor.execute("""
                        UPDATE spots 
                        SET availability = 0, cust_id = %s
                        WHERE table_id = %s
                    """, (customer['cust_id'], available_spot['table_id']))
                    conn.commit()
                    
                    # Log customer in
                    session['user_id'] = customer['cust_id']
                    session['role'] = 'customer'
                    return redirect(url_for('menu'))
                else:
                    # No spots available, show waiting room
                    return render_template('customer_waiting.html', 
                                        customer_name=customer['c_name'])
            
            flash('Phone number not found. Please register first.', 'danger')
            return redirect(url_for('customer_login'))
        
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
            return redirect(url_for('customer_login'))
        
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    return render_template('customer_login.html')

@app.route('/employee/login', methods=['GET', 'POST'])
def employee_login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            return render_template('employee_login.html', error="Database connection error")
            
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM employee WHERE e_phone = %s AND passwd = %s', 
                         (phone, password))
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user['emp_id']
                session['role'] = user['role']
                if user['role'] == 'waiter':
                    return redirect(url_for('waiter_dashboard'))
                elif user['role'] == 'chef':
                    return redirect(url_for('chef_dashboard'))
                elif user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
            
            flash('Invalid credentials', 'danger')
        except Error as e:
            flash(f'Database error: {str(e)}', 'danger')
        finally:
            cursor.close()
            conn.close()
            
    return render_template('employee_login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Check if phone number already exists
            cursor.execute('SELECT * FROM customer WHERE c_phone = %s', (phone,))
            existing_customer = cursor.fetchone()
            
            if existing_customer:
                flash('Phone number already registered. Please login.', 'danger')
                return redirect(url_for('customer_login'))
            
            # Insert new customer with default loyalty points
            cursor.execute('INSERT INTO customer (c_name, c_phone, loyal_pts) VALUES (%s, %s, 100)',
                         (name, phone))
            conn.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('customer_login'))
            
        except Exception as e:
            flash('An error occurred during registration. Please try again.', 'danger')
            print(f"Registration error: {str(e)}")
            return redirect(url_for('register'))
        finally:
            if 'conn' in locals():
                conn.close()
    
    return render_template('register.html')

@app.route('/customer/dashboard')
def customer_dashboard():
    if 'user_id' not in session or session['role'] != 'customer':
        return redirect(url_for('customer_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get customer details
        cursor.execute('SELECT * FROM customer WHERE cust_id = %s', (session['user_id'],))
        customer = cursor.fetchone()
        
        # Get current order (unpaid)
        cursor.execute('''
            SELECT o.order_id, o.time_stamp, o.paid_status
            FROM orders o
            WHERE o.cust_id = %s AND o.paid_status = FALSE
            ORDER BY o.time_stamp DESC
            LIMIT 1
        ''', (session['user_id'],))
        current_order = cursor.fetchone()
        
        # Initialize order_items list for current order
        if current_order:
            current_order['order_items'] = []
            
            # Get order details for current order
            cursor.execute('''
                SELECT od.order_id, od.item_id, od.qty, od.order_status, m.item_name, m.item_price
                FROM order_details od
                JOIN menu m ON od.item_id = m.item_id
                WHERE od.order_id = %s
            ''', (current_order['order_id'],))
            
            all_delivered = True
            for item in cursor.fetchall():
                status_color = {
                    'placed': 'warning',
                    'cooking': 'info',
                    'cooked': 'success',
                    'delivered': 'primary',
                    'billed': 'secondary'
                }.get(item['order_status'], 'secondary')
                
                # Check if all items are delivered
                if item['order_status'] != 'delivered' and item['order_status'] != 'billed':
                    all_delivered = False
                
                current_order['order_items'].append({
                    'item_id': item['item_id'],
                    'item_name': item['item_name'],
                    'qty': item['qty'],
                    'order_status': item['order_status'],
                    'status_color': status_color
                })
            
            # Add all_delivered flag to current_order
            current_order['all_delivered'] = all_delivered
        
        return render_template('customer/dashboard.html', 
                              customer=customer, 
                              current_order=current_order)
        
    except Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('customer_login'))
    finally:
        cursor.close()
        conn.close()

@app.route('/menu')
def menu():
    if 'user_id' not in session or session['role'] != 'customer':
        return redirect(url_for('customer_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get menu items grouped by category
        cursor.execute('''
            SELECT * FROM menu 
            WHERE availability = TRUE 
            ORDER BY FIELD(category, 'Tiffin', 'Lunch', 'Pizza', 'Burger', 'Salad', 'Drinks'), item_name
        ''')
        menu_items = cursor.fetchall()
        
        # Group items by category in the specified order
        category_order = ['Tiffin', 'Lunch', 'Pizza', 'Burger', 'Salad', 'Drinks']
        categories = {category: [] for category in category_order}
        
        for item in menu_items:
            if item['category'] in categories:
                categories[item['category']].append(item)
            else:
                # Handle any categories not in the predefined order
                if item['category'] not in categories:
                    categories[item['category']] = []
                categories[item['category']].append(item)
        
        # Get current order if exists
        cursor.execute('''
            SELECT o.order_id
            FROM orders o
            WHERE o.cust_id = %s AND o.paid_status = FALSE
            ORDER BY o.time_stamp DESC
            LIMIT 1
        ''', (session['user_id'],))
        current_order = cursor.fetchone()
        
        # If there's a current order, get its items to pre-populate the cart
        current_order_items = {}
        if current_order:
            cursor.execute('''
                SELECT od.item_id, od.qty
                FROM order_details od
                WHERE od.order_id = %s
            ''', (current_order['order_id'],))
            
            for item in cursor.fetchall():
                current_order_items[item['item_id']] = item['qty']
        
        return render_template('menu.html', 
                              categories=categories, 
                              current_order=current_order,
                              current_order_items=current_order_items)
    except Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('customer_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/place_order_simple', methods=['POST'])
def place_order_simple():
    if 'user_id' not in session or session['role'] != 'customer':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    items = data.get('items', [])
    
    if not items:
        return jsonify({'error': 'No items provided'}), 400
    
    # Create a new connection for this operation
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        # First, check if customer has an unpaid order
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT order_id FROM orders 
            WHERE cust_id = %s AND paid_status = FALSE
        ''', (session['user_id'],))
        existing_order = cursor.fetchone()
        cursor.close()
        
        if existing_order:
            order_id = existing_order['order_id']
        else:
            # Create new order
            cursor = conn.cursor(dictionary=True)
            cursor.execute('INSERT INTO orders (cust_id) VALUES (%s)', (session['user_id'],))
            order_id = cursor.lastrowid
            cursor.close()
        
        # Process each item separately
        for item in items:
            # Check if item already exists in order
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT qty FROM order_details 
                WHERE order_id = %s AND item_id = %s
            ''', (order_id, item['id']))
            existing_item = cursor.fetchone()
            cursor.close()
            
            if existing_item:
                # Update quantity if item exists
                cursor = conn.cursor(dictionary=True)
                cursor.execute('''
                    UPDATE order_details 
                    SET qty = %s 
                    WHERE order_id = %s AND item_id = %s
                ''', (item['quantity'], order_id, item['id']))
                cursor.close()
            else:
                # Add new item to order
                cursor = conn.cursor(dictionary=True)
                cursor.execute('''
                    INSERT INTO order_details (order_id, item_id, qty, order_status)
                    VALUES (%s, %s, %s, 'placed')
                ''', (order_id, item['id'], item['quantity']))
                cursor.close()
        
        return jsonify({'success': True, 'order_id': order_id})
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/remove_order_item', methods=['POST'])
def remove_order_item():
    if 'user_id' not in session or session['role'] != 'customer':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    order_id = data.get('order_id')
    item_id = data.get('item_id')
    
    if not order_id or not item_id:
        return jsonify({'error': 'Missing order_id or item_id'}), 400
    
    # Create a new connection for this operation
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        # Verify the order belongs to the current customer with a new cursor
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT cust_id FROM orders 
            WHERE order_id = %s AND cust_id = %s AND paid_status = FALSE
        ''', (order_id, session['user_id']))
        
        if not cursor.fetchone():
            cursor.close()
            return jsonify({'error': 'Order not found or not authorized'}), 403
        cursor.close()  # Close cursor after fetching results
        
        # Remove the item from order_details with a new cursor
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            DELETE FROM order_details 
            WHERE order_id = %s AND item_id = %s
        ''', (order_id, item_id))
        cursor.close()  # Close cursor after operation
        
        # Check if there are any items left in the order with a new cursor
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT COUNT(*) as count FROM order_details 
            WHERE order_id = %s
        ''', (order_id,))
        
        result = cursor.fetchone()
        item_count = result['count']
        cursor.close()  # Close cursor after fetching results
        
        # If no items left, delete the order with a new cursor
        if item_count == 0:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('DELETE FROM orders WHERE order_id = %s', (order_id,))
            cursor.close()  # Close cursor after operation
        
        return jsonify({'success': True})
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/request_bill', methods=['POST'])
def request_bill():
    if 'user_id' not in session or session.get('role') != 'customer':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    order_id = data.get('order_id')
    
    if not order_id:
        return jsonify({'error': 'Missing order_id'}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify the order belongs to the current customer
        cursor.execute("""
            SELECT o.order_id, o.cust_id, s.table_id, s.waiter_id
            FROM orders o
            JOIN spots s ON o.cust_id = s.cust_id
            WHERE o.order_id = %s AND o.cust_id = %s AND o.paid_status = 0
        """, (order_id, session['user_id']))
        
        order_data = cursor.fetchone()
        if not order_data:
            return jsonify({'error': 'Order not found or not authorized'}), 403
        
        # Check if all items are delivered
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END) as delivered
            FROM order_details
            WHERE order_id = %s
        """, (order_id,))
        
        result = cursor.fetchone()
        if result['total'] != result['delivered']:
            return jsonify({'error': 'All items must be delivered before requesting bill'}), 400
        
        # Update order bill_status to requested
        cursor.execute("""
            UPDATE orders 
            SET bill_status = 'requested'
            WHERE order_id = %s
        """, (order_id,))
        
        conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/waiter/dashboard')
def waiter_dashboard():
    if 'user_id' not in session or session.get('role') != 'waiter':
        return redirect(url_for('employee_login'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get waiter_id
        cursor.execute("SELECT waiter_id FROM waiter WHERE emp_id = %s", (session['user_id'],))
        waiter = cursor.fetchone()
        
        if not waiter:
            return redirect(url_for('employee_login'))
        
        # Get waiter's spots with pending bill requests
        cursor.execute("""
            SELECT s.table_id, s.availability, s.cust_id, c.c_name, c.c_phone, c.loyal_pts,
                   o.order_id, o.paid_status, o.bill_status,
                   (SELECT COUNT(*) FROM order_details od WHERE od.order_id = o.order_id) as total_items,
                   (SELECT COUNT(*) FROM order_details od WHERE od.order_id = o.order_id AND od.order_status = 'delivered') as delivered_items
            FROM spots s
            LEFT JOIN customer c ON s.cust_id = c.cust_id
            LEFT JOIN orders o ON s.cust_id = o.cust_id AND o.paid_status = 0
            WHERE s.waiter_id = %s
            ORDER BY s.table_id
        """, (waiter['waiter_id'],))
        
        spots = cursor.fetchall()
        
        # Process spots to add additional information
        for spot in spots:
            # Initialize order_items as an empty list
            spot['order_items'] = []
            
            if spot['order_id']:
                # Get order items
                cursor.execute("""
                    SELECT od.*, m.item_name, m.category, m.item_price
                    FROM order_details od
                    JOIN menu m ON od.item_id = m.item_id
                    WHERE od.order_id = %s
                """, (spot['order_id'],))
                
                items = cursor.fetchall()
                
                # Process each item
                for item in items:
                    # Add status color
                    status_colors = {
                        'placed': 'warning',
                        'cooking': 'info',
                        'cooked': 'success',
                        'delivered': 'primary',
                        'billed': 'secondary'
                    }
                    item['status_color'] = status_colors.get(item['order_status'], 'secondary')
                    spot['order_items'].append(item)
                
                # Check if all items are delivered
                spot['all_items_delivered'] = spot['total_items'] == spot['delivered_items'] and spot['total_items'] > 0
        
        # Check if there are any spots assigned to this waiter
        if not spots:
            # If no spots are assigned, assign up to 3 spots to this waiter
            cursor.execute("""
                UPDATE spots 
                SET waiter_id = %s
                WHERE waiter_id IS NULL
                LIMIT 3
            """, (waiter['waiter_id'],))
            conn.commit()
            
            # Get the updated spots
            cursor.execute("""
                SELECT s.table_id, s.availability, s.cust_id, c.c_name, c.c_phone, c.loyal_pts,
                       o.order_id, o.paid_status, o.bill_status,
                       (SELECT COUNT(*) FROM order_details od WHERE od.order_id = o.order_id) as total_items,
                       (SELECT COUNT(*) FROM order_details od WHERE od.order_id = o.order_id AND od.order_status = 'delivered') as delivered_items
                FROM spots s
                LEFT JOIN customer c ON s.cust_id = c.cust_id
                LEFT JOIN orders o ON s.cust_id = o.cust_id AND o.paid_status = 0
                WHERE s.waiter_id = %s
                ORDER BY s.table_id
            """, (waiter['waiter_id'],))
            
            spots = cursor.fetchall()
            
            # Process spots to add additional information
            for spot in spots:
                # Initialize order_items as an empty list
                spot['order_items'] = []
                
                if spot['order_id']:
                    # Get order items
                    cursor.execute("""
                        SELECT od.*, m.item_name, m.category, m.item_price
                        FROM order_details od
                        JOIN menu m ON od.item_id = m.item_id
                        WHERE od.order_id = %s
                    """, (spot['order_id'],))
                    
                    items = cursor.fetchall()
                    
                    # Process each item
                    for item in items:
                        # Add status color
                        status_colors = {
                            'placed': 'warning',
                            'cooking': 'info',
                            'cooked': 'success',
                            'delivered': 'primary',
                            'billed': 'secondary'
                        }
                        item['status_color'] = status_colors.get(item['order_status'], 'secondary')
                        spot['order_items'].append(item)
                    
                    # Check if all items are delivered
                    spot['all_items_delivered'] = spot['total_items'] == spot['delivered_items'] and spot['total_items'] > 0
        
        return render_template('waiter/dashboard.html', spots=spots)
    
    except Exception as e:
        import traceback
        print(f"Error in waiter_dashboard: {str(e)}")
        print(traceback.format_exc())
        return redirect(url_for('employee_login'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route('/update_order_status', methods=['POST'])
def update_order_status():
    if 'user_id' not in session or session.get('role') != 'waiter':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    order_id = data.get('order_id')
    item_id = data.get('item_id')
    status = data.get('status')
    
    if not all([order_id, item_id, status]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify the order belongs to a spot assigned to this waiter
        cursor.execute("""
            SELECT s.waiter_id 
            FROM spots s
            JOIN orders o ON s.cust_id = o.cust_id
            WHERE o.order_id = %s AND s.waiter_id = (
                SELECT waiter_id FROM waiter WHERE emp_id = %s
            )
        """, (order_id, session['user_id']))
        
        if not cursor.fetchone():
            return jsonify({'error': 'Order not found or not authorized'}), 403
        
        # Update the order status
        cursor.execute("""
            UPDATE order_details 
            SET order_status = %s
            WHERE order_id = %s AND item_id = %s
        """, (status, order_id, item_id))
        
        conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/generate_bill', methods=['POST'])
def generate_bill():
    if 'user_id' not in session or session.get('role') != 'customer':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    order_id = data.get('order_id')
    
    if not order_id:
        return jsonify({'error': 'Missing order_id'}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify the order belongs to the current customer
        cursor.execute("""
            SELECT o.order_id, o.cust_id, s.table_id, s.waiter_id
            FROM orders o
            JOIN spots s ON o.cust_id = s.cust_id
            WHERE o.order_id = %s AND o.cust_id = %s AND o.paid_status = 0
        """, (order_id, session['user_id']))
        
        order_data = cursor.fetchone()
        if not order_data:
            return jsonify({'error': 'Order not found or not authorized'}), 403
        
        # Check if all items are delivered
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END) as delivered
            FROM order_details
            WHERE order_id = %s
        """, (order_id,))
        
        result = cursor.fetchone()
        if result['total'] != result['delivered']:
            return jsonify({'error': 'All items must be delivered before generating bill'}), 400
        
        # Calculate total amount
        cursor.execute("""
            SELECT SUM(m.item_price * od.qty) as total
            FROM order_details od
            JOIN menu m ON od.item_id = m.item_id
            WHERE od.order_id = %s
        """, (order_id,))
        
        total_result = cursor.fetchone()
        total = total_result['total'] if total_result['total'] else 0
        tax = total * 0.18  # 18% tax
        final_amount = total + tax
        
        # Create bill
        cursor.execute("""
            INSERT INTO bill (tot_amt, tax, final_amt, pay_mode, order_id, waiter_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (total, tax, final_amount, 'online', order_id, order_data['waiter_id']))
        
        # Update order status to paid
        cursor.execute("""
            UPDATE orders 
            SET paid_status = 1
            WHERE order_id = %s
        """, (order_id,))
        
        # Update table availability
        cursor.execute("""
            UPDATE spots 
            SET availability = 1, cust_id = NULL
            WHERE table_id = %s
        """, (order_data['table_id'],))
        
        # Calculate and update loyalty points (1 point per ₹10 spent)
        points_earned = int(final_amount / 10)
        cursor.execute("""
            UPDATE customer 
            SET loyal_pts = loyal_pts + %s
            WHERE cust_id = %s
        """, (points_earned, session['user_id']))
        
        conn.commit()
        return jsonify({
            'success': True,
            'bill': {
                'total': total,
                'tax': tax,
                'final_amount': final_amount,
                'points_earned': points_earned
            }
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# @app.route('/logout')
# def logout():
#     session.clear()
#     flash('You have been successfully logged out!', 'success')
#     return redirect(url_for('index'))

@app.route('/waiter/approve_bill', methods=['POST'])
def approve_bill():
    if 'user_id' not in session or session.get('role') != 'waiter':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    order_id = data.get('order_id')
    
    if not order_id:
        return jsonify({'error': 'Missing order_id'}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get waiter_id
        cursor.execute("SELECT waiter_id FROM waiter WHERE emp_id = %s", (session['user_id'],))
        waiter = cursor.fetchone()
        
        if not waiter:
            return jsonify({'error': 'Waiter not found'}), 403
        
        # Verify the order belongs to a spot assigned to this waiter
        cursor.execute("""
            SELECT o.order_id, o.cust_id, s.table_id, s.waiter_id
            FROM orders o
            JOIN spots s ON o.cust_id = s.cust_id
            WHERE o.order_id = %s AND s.waiter_id = %s AND o.bill_status = 'requested'
        """, (order_id, waiter['waiter_id']))
        
        order_data = cursor.fetchone()
        if not order_data:
            return jsonify({'error': 'Order not found or not authorized'}), 403
        
        # Calculate total amount
        cursor.execute("""
            SELECT SUM(m.item_price * od.qty) as total
            FROM order_details od
            JOIN menu m ON od.item_id = m.item_id
            WHERE od.order_id = %s
        """, (order_id,))
        
        total_result = cursor.fetchone()
        total = total_result['total'] if total_result['total'] else 0
        
        # Convert to Decimal for consistent calculations
        total = Decimal(str(total))
        tax = total * Decimal('0.18')  # 18% tax
        final_amount = total + tax
        
        # Create bill
        cursor.execute("""
            INSERT INTO bill (tot_amt, tax, final_amt, pay_mode, order_id, waiter_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (float(total), float(tax), float(final_amount), 'online', order_id, waiter['waiter_id']))
        
        # Update order status to paid
        cursor.execute("""
            UPDATE orders 
            SET paid_status = 1, bill_status = 'paid'
            WHERE order_id = %s
        """, (order_id,))
        
        # Update all order items status to 'billed'
        cursor.execute("""
            UPDATE order_details 
            SET order_status = 'billed'
            WHERE order_id = %s
        """, (order_id,))
        
        # Update table availability
        cursor.execute("""
            UPDATE spots 
            SET availability = 1, cust_id = NULL
            WHERE table_id = %s
        """, (order_data['table_id'],))
        
        # Calculate and update loyalty points (1 point per ₹10 spent)
        points_earned = int(float(final_amount) / 10)
        cursor.execute("""
            UPDATE customer 
            SET loyal_pts = loyal_pts + %s
            WHERE cust_id = %s
        """, (points_earned, order_data['cust_id']))
        
        conn.commit()
        return jsonify({
            'success': True,
            'bill': {
                'total': float(total),
                'tax': float(tax),
                'final_amount': float(final_amount),
                'points_earned': points_earned
            }
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/chef/dashboard')
def chef_dashboard():
    if 'user_id' not in session or session.get('role') != 'chef':
        flash('Please login as chef to access this page.', 'error')
        return redirect(url_for('employee_login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get chef_id for the logged-in chef
        cursor.execute("""
            SELECT chef_id 
            FROM chef 
            WHERE emp_id = %s
        """, (session['user_id'],))
        chef = cursor.fetchone()
        
        if not chef:
            flash('Chef profile not found.', 'error')
            return redirect(url_for('employee_login'))
        
        # Get assigned orders for this chef
        cursor.execute("""
            SELECT od.order_id, od.item_id, od.qty, od.order_status,
                   m.item_name, m.category, m.prep_time
            FROM order_details od
            JOIN menu m ON od.item_id = m.item_id
            WHERE od.chef_id = %s
            AND od.order_status IN ('placed', 'cooking')
            ORDER BY od.order_id
        """, (chef['chef_id'],))
        
        assigned_orders = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('chef/dashboard.html', assigned_orders=assigned_orders)
        
    except Exception as e:
        print(f"Error in chef_dashboard: {str(e)}")
        flash('Error retrieving assigned orders. Please try again.', 'error')
        return redirect(url_for('employee_login'))

@app.route('/chef/manage_menu')
def chef_manage_menu():
    if 'user_id' not in session or session.get('role') != 'chef':
        flash('Please login as chef to access this page.', 'error')
        return redirect(url_for('employee_login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all menu items
        cursor.execute("""
            SELECT item_id, item_name, category, item_price, prep_time, availability
            FROM menu
            ORDER BY category, item_name
        """)
        
        menu_items = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('chef/manage_menu.html', menu_items=menu_items)
        
    except Exception as e:
        print(f"Error in chef_manage_menu: {str(e)}")
        flash('Error retrieving menu items. Please try again.', 'error')
        return redirect(url_for('chef_dashboard'))

@app.route('/chef/mark_cooked', methods=['POST'])
def chef_mark_cooked():
    if 'user_id' not in session or session.get('role') != 'chef':
        return jsonify({'success': False, 'error': 'Unauthorized access'})
    
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        item_id = data.get('item_id')
        
        if not order_id or not item_id:
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get chef_id for the logged-in chef
        cursor.execute("""
            SELECT chef_id 
            FROM chef 
            WHERE emp_id = %s
        """, (session['user_id'],))
        chef = cursor.fetchone()
        
        if not chef:
            return jsonify({'success': False, 'error': 'Chef not found'})
        
        # Update order status to cooked
        cursor.execute("""
            UPDATE order_details 
            SET order_status = 'cooked'
            WHERE order_id = %s AND item_id = %s AND chef_id = %s
        """, (order_id, item_id, chef['chef_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error in chef_mark_cooked: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/chef/toggle_menu_item', methods=['POST'])
def chef_toggle_menu_item():
    if 'user_id' not in session or session.get('role') != 'chef':
        return jsonify({'success': False, 'error': 'Unauthorized access'})
    
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        
        if not item_id:
            return jsonify({'success': False, 'error': 'Missing item ID'})
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get current availability
        cursor.execute("SELECT availability FROM menu WHERE item_id = %s", (item_id,))
        current = cursor.fetchone()
        
        if not current:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Item not found'})
        
        # Toggle availability
        new_status = not current['availability']
        cursor.execute("""
            UPDATE menu 
            SET availability = %s 
            WHERE item_id = %s
        """, (new_status, item_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error in chef_toggle_menu_item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('employee_login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'danger')
        return redirect(url_for('employee_login'))
        
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get employee counts
        cursor.execute('SELECT role, COUNT(*) as count FROM employee GROUP BY role')
        employee_counts = cursor.fetchall()
        
        # Get recent orders
        cursor.execute('''
            SELECT o.order_id, c.c_name, o.time_stamp, od.order_status
            FROM orders o
            JOIN customer c ON o.cust_id = c.cust_id
            JOIN order_details od ON o.order_id = od.order_id
            ORDER BY o.time_stamp DESC
            LIMIT 10
        ''')
        recent_orders = cursor.fetchall()
        
        return render_template('admin/dashboard.html', 
                              employee_counts=employee_counts,
                              recent_orders=recent_orders)
    except Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('employee_login'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/add_employee', methods=['GET', 'POST'])
def admin_add_employee():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('employee_login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        role = request.form.get('role')
        password = request.form.get('password')
        salary = request.form.get('salary')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if phone number already exists
            cursor.execute('SELECT * FROM employee WHERE e_phone = %s', (phone,))
            existing_employee = cursor.fetchone()
            
            if existing_employee:
                flash('Phone number already registered.', 'danger')
                return redirect(url_for('admin_add_employee'))
            
            # Insert new employee
            cursor.execute('''
                INSERT INTO employee (e_name, e_phone, role, passwd, salary) 
                VALUES (%s, %s, %s, %s, %s)
            ''', (name, phone, role, password, salary))
            
            # Get the newly inserted employee's ID
            emp_id = cursor.lastrowid
            
            # If role is waiter, add to waiter table
            if role == 'waiter':
                cursor.execute('INSERT INTO waiter (emp_id) VALUES (%s)', (emp_id,))
                print(f"Added waiter entry for employee {emp_id}")
            
            # If role is chef, add to chef table
            elif role == 'chef':
                cursor.execute('INSERT INTO chef (emp_id, specialization) VALUES (%s, %s)', 
                             (emp_id, 'General'))  # Default specialization
                print(f"Added chef entry for employee {emp_id}")
            
            conn.commit()
            flash('Employee added successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error adding employee: {str(e)}', 'danger')
            return redirect(url_for('admin_add_employee'))
        finally:
            cursor.close()
            conn.close()
    
    return render_template('admin/add_employee.html')

@app.route('/admin/manage_menu')
def admin_manage_menu():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('employee_login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get all menu items
        cursor.execute('SELECT * FROM menu ORDER BY category, item_name')
        menu_items = cursor.fetchall()
        
        return render_template('admin/manage_menu.html', menu_items=menu_items)
    except Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/add_menu_item', methods=['POST'])
def admin_add_menu_item():
    if not session.get('user_id') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    item_name = request.form.get('item_name')
    category = request.form.get('category')
    item_price = float(request.form.get('item_price'))
    prep_time = int(request.form.get('prep_time'))
    allergen = request.form.get('allergen')
    description = request.form.get('description')
    availability = 1 if request.form.get('availability') else 0
    image_url = "/static/images/default.jpeg"  # Default image URL
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO menu (item_name, category, item_price, prep_time, allergen, description, availability, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (item_name, category, item_price, prep_time, allergen, description, availability, image_url))
        conn.commit()
        flash('Menu item added successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error adding menu item: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_manage_menu'))

@app.route('/admin/toggle_menu_item', methods=['POST'])
def admin_toggle_menu_item():
    if not session.get('user_id') or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    item_id = data.get('item_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE menu SET availability = NOT availability WHERE item_id = %s', (item_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/edit_menu_item/<int:item_id>', methods=['GET', 'POST'])
def admin_edit_menu_item(item_id):
    if not session.get('user_id') or session.get('role') != 'admin':
        flash('Please login as admin to access this page.', 'error')
        return redirect(url_for('employee_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if request.method == 'POST':
            item_name = request.form.get('item_name')
            category = request.form.get('category')
            item_price = float(request.form.get('item_price'))
            prep_time = int(request.form.get('prep_time'))
            allergen = request.form.get('allergen')
            description = request.form.get('description')
            availability = 1 if request.form.get('availability') else 0
            
            cursor.execute('''
                UPDATE menu 
                SET item_name = %s, category = %s, item_price = %s, prep_time = %s, 
                    allergen = %s, description = %s, availability = %s
                WHERE item_id = %s
            ''', (item_name, category, item_price, prep_time, allergen, description, availability, item_id))
            conn.commit()
            flash('Menu item updated successfully!', 'success')
            return redirect(url_for('admin_manage_menu'))
        
        cursor.execute('SELECT * FROM menu WHERE item_id = %s', (item_id,))
        item = cursor.fetchone()
        if not item:
            flash('Menu item not found.', 'error')
            return redirect(url_for('admin_manage_menu'))
        
        return render_template('admin/edit_menu_item.html', item=item)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin_manage_menu'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/reports')
def admin_reports():
    if not session.get('user_id') or session.get('role') != 'admin':
        flash('Please login as admin to access this page.', 'error')
        return redirect(url_for('employee_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get sales data for the last 30 days
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT o.order_id) as total_orders,
                SUM(b.tot_amt) as total_sales,
                AVG(b.tot_amt) as avg_order_value,
                SUM(c.loyal_pts) as total_loyalty_points
            FROM orders o
            JOIN bill b ON o.order_id = b.order_id
            JOIN customer c ON o.cust_id = c.cust_id
            WHERE o.time_stamp >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
        ''')
        sales_data = cursor.fetchone()
        
        # Get top selling items
        cursor.execute('''
            SELECT 
                m.item_name,
                m.category,
                SUM(od.qty) as quantity_sold,
                SUM(od.qty * m.item_price) as revenue
            FROM order_details od
            JOIN menu m ON od.item_id = m.item_id
            JOIN orders o ON od.order_id = o.order_id
            WHERE o.time_stamp >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
            GROUP BY m.item_id, m.item_name, m.category
            ORDER BY quantity_sold DESC
            LIMIT 5
        ''')
        top_items = cursor.fetchall()
        
        # Get sales by category
        cursor.execute('''
            SELECT 
                m.category,
                SUM(od.qty) as items_sold,
                SUM(od.qty * m.item_price) as revenue,
                (SUM(od.qty * m.item_price) / (
                    SELECT SUM(od2.qty * m2.item_price)
                    FROM order_details od2
                    JOIN menu m2 ON od2.item_id = m2.item_id
                    JOIN orders o2 ON od2.order_id = o2.order_id
                    WHERE o2.time_stamp >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
                ) * 100) as percentage
            FROM order_details od
            JOIN menu m ON od.item_id = m.item_id
            JOIN orders o ON od.order_id = o.order_id
            WHERE o.time_stamp >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
            GROUP BY m.category
            ORDER BY revenue DESC
        ''')
        category_sales = cursor.fetchall()
        
        return render_template('admin/reports.html', 
                             sales_data=sales_data,
                             top_items=top_items,
                             category_sales=category_sales)
    except Exception as e:
        flash(f'Error generating reports: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/settings')
def admin_settings():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('employee_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute('SELECT * FROM settings')
        settings = cursor.fetchone()
        return render_template('admin/settings.html', settings=settings)
    except Exception as e:
        flash(f'Error loading settings: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/update_loyalty_settings', methods=['POST'])
def admin_update_loyalty_settings():
    if not session.get('user_id') or session.get('role') != 'admin':
        flash('Please login as admin to access this page.', 'error')
        return redirect(url_for('employee_login'))
    
    points_per_rupee = float(request.form.get('points_per_rupee'))
    rupee_per_point = float(request.form.get('rupee_per_point'))
    min_points_redemption = int(request.form.get('min_points_redemption'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE settings 
            SET points_per_rupee = %s, rupee_per_point = %s, min_points_redemption = %s
        ''', (points_per_rupee, rupee_per_point, min_points_redemption))
        conn.commit()
        flash('Loyalty settings updated successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating loyalty settings: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_settings'))

@app.route('/admin/update_tax_settings', methods=['POST'])
def admin_update_tax_settings():
    if not session.get('user_id') or session.get('role') != 'admin':
        flash('Please login as admin to access this page.', 'error')
        return redirect(url_for('employee_login'))
    
    tax_rate = float(request.form.get('tax_rate'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE settings SET tax_rate = %s', (tax_rate,))
        conn.commit()
        flash('Tax settings updated successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating tax settings: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_settings'))

@app.route('/admin/update_table_settings', methods=['POST'])
def admin_update_table_settings():
    if not session.get('user_id') or session.get('role') != 'admin':
        flash('Please login as admin to access this page.', 'error')
        return redirect(url_for('employee_login'))
    
    total_tables = int(request.form.get('total_tables'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE settings SET total_tables = %s', (total_tables,))
        conn.commit()
        flash('Table settings updated successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating table settings: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_settings'))

@app.route('/admin/update_system_settings', methods=['POST'])
def admin_update_system_settings():
    if not session.get('user_id') or session.get('role') != 'admin':
        flash('Please login as admin to access this page.', 'error')
        return redirect(url_for('employee_login'))
    
    restaurant_name = request.form.get('restaurant_name')
    restaurant_address = request.form.get('restaurant_address')
    restaurant_phone = request.form.get('restaurant_phone')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE settings 
            SET restaurant_name = %s, restaurant_address = %s, restaurant_phone = %s
        ''', (restaurant_name, restaurant_address, restaurant_phone))
        conn.commit()
        flash('System settings updated successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating system settings: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_settings'))

@app.route('/close_order', methods=['POST'])
def close_order():
    if 'user_id' not in session or session['role'] != 'waiter':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    order_id = data.get('order_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if all items in the order are billed
        cursor.execute('''
            SELECT COUNT(*) as total_items, 
                   SUM(CASE WHEN order_status = 'billed' THEN 1 ELSE 0 END) as billed_items
            FROM order_details
            WHERE order_id = %s
        ''', (order_id,))
        
        result = cursor.fetchone()
        total_items = result[0]
        billed_items = result[1]
        
        if total_items == billed_items:
            # All items are billed, close the order
            cursor.execute('''
                UPDATE orders 
                SET paid_status = TRUE 
                WHERE order_id = %s
            ''', (order_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Order closed successfully'})
        else:
            return jsonify({'error': 'Not all items have been billed yet'}), 400
            
    except Error as e:
        return jsonify({'error': str(e)}), 500

@app.route('/place_order_new', methods=['POST'])
def place_order_new():
    if 'user_id' not in session or session['role'] != 'customer':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    items = data.get('items', [])
    
    if not items:
        return jsonify({'error': 'No items provided'}), 400
    
    # Create a new connection for this operation
    conn = None
    cursor = None
    
    try:
        # Create a new connection
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database']
        )
        
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        # Start transaction
        conn.start_transaction()
        
        # First, check if customer has an unpaid order
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT order_id FROM orders 
            WHERE cust_id = %s AND paid_status = FALSE
        ''', (session['user_id'],))
        existing_order = cursor.fetchone()
        
        if existing_order:
            order_id = existing_order['order_id']
            print(f"Using existing order: {order_id}")
        else:
            # Create new order
            cursor.execute('INSERT INTO orders (cust_id) VALUES (%s)', (session['user_id'],))
            order_id = cursor.lastrowid
            print(f"Created new order: {order_id}")
        
        # Process each item separately
        for item in items:
            # Check if item already exists in order
            cursor.execute('''
                SELECT qty FROM order_details 
                WHERE order_id = %s AND item_id = %s
            ''', (order_id, item['id']))
            existing_item = cursor.fetchone()
            
            if existing_item:
                # Update quantity if item exists
                cursor.execute('''
                    UPDATE order_details 
                    SET qty = %s 
                    WHERE order_id = %s AND item_id = %s
                ''', (item['quantity'], order_id, item['id']))
                cursor.close()
                print(f"Updated item {item['id']} in order {order_id}")
            else:
                # Add new item to order
                cursor.execute('''
                    INSERT INTO order_details (order_id, item_id, qty, order_status)
                    VALUES (%s, %s, %s, 'placed')
                ''', (order_id, item['id'], item['quantity']))
                cursor.close()
        
        # Commit the transaction
        conn.commit()
        print(f"Transaction committed for order {order_id}")
        
        return jsonify({'success': True, 'order_id': order_id})
    except Error as e:
        # Rollback the transaction in case of error
        if conn:
            conn.rollback()
            print(f"Transaction rolled back due to error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("Database connection closed")

@app.route('/place_order_final', methods=['POST'])
def place_order_final():
    if 'user_id' not in session or session['role'] != 'customer':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    items = data.get('items', [])
    
    if not items:
        return jsonify({'error': 'No items provided'}), 400
    
    # Create a new connection for this operation
    conn = None
    cursor = None
    
    try:
        # Create a new connection with specific settings to avoid "Unread result found" error
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            autocommit=True,  # Enable autocommit to avoid transaction issues
            consume_results=True  # Automatically consume results
        )
        
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(dictionary=True)
        
        # Get total number of chefs
        cursor.execute("SELECT COUNT(*) as chef_count FROM chef")
        chef_count = cursor.fetchone()['chef_count']
        
        if chef_count == 0:
            return jsonify({'error': 'No chefs available in the system'}), 500
        
        # First, check if customer has an unpaid order
        cursor.execute('''
            SELECT order_id FROM orders 
            WHERE cust_id = %s AND paid_status = FALSE
        ''', (session['user_id'],))
        existing_order = cursor.fetchone()
        
        if existing_order:
            order_id = existing_order['order_id']
            print(f"Using existing order: {order_id}")
        else:
            # Create new order
            cursor.execute('INSERT INTO orders (cust_id) VALUES (%s)', (session['user_id'],))
            order_id = cursor.lastrowid
            print(f"Created new order: {order_id}")
        
        # Process each item separately
        for item in items:
            # Check if item already exists in order
            cursor.execute('''
                SELECT qty FROM order_details 
                WHERE order_id = %s AND item_id = %s
            ''', (order_id, item['id']))
            existing_item = cursor.fetchone()
            
            if existing_item:
                # Update quantity if item exists
                cursor.execute('''
                    UPDATE order_details 
                    SET qty = %s 
                    WHERE order_id = %s AND item_id = %s
                ''', (item['quantity'], order_id, item['id']))
                print(f"Updated item {item['id']} in order {order_id}")
            else:
                # Get chef_id based on order_id and total chefs (round-robin assignment)
                chef_position = (order_id % chef_count) + 1
                cursor.execute("""
                    SELECT chef_id
                    FROM chef
                    LIMIT 1 OFFSET %s
                """, (chef_position - 1,))
                chef = cursor.fetchone()
                
                if not chef:
                    return jsonify({'error': 'Could not assign chef to order'}), 500
                
                # Add new item to order with chef assignment
                cursor.execute('''
                    INSERT INTO order_details (order_id, item_id, qty, order_status, chef_id)
                    VALUES (%s, %s, %s, 'placed', %s)
                ''', (order_id, item['id'], item['quantity'], chef['chef_id']))
                print(f"Added item {item['id']} to order {order_id} with chef {chef['chef_id']}")
        
        return jsonify({'success': True, 'order_id': order_id})
    except Error as e:
        print(f"Error in place_order_final: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("Database connection closed")

@app.route('/waiter/spot/<int:table_id>')
def waiter_spot_details(table_id):
    if 'user_id' not in session or session.get('role') != 'waiter':
        flash('Please login as a waiter to access this page.', 'danger')
        return redirect(url_for('employee_login'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # First, get the waiter_id
        cursor.execute("SELECT waiter_id FROM waiter WHERE emp_id = %s", (session['user_id'],))
        waiter = cursor.fetchone()
        
        if not waiter:
            flash('Waiter not found.', 'danger')
            return redirect(url_for('employee_login'))
        
        # Get spot details
        cursor.execute("""
            SELECT s.*, c.c_name, c.c_phone, c.loyal_pts
            FROM spots s
            LEFT JOIN customer c ON s.cust_id = c.cust_id
            WHERE s.table_id = %s AND s.waiter_id = %s
        """, (table_id, waiter['waiter_id']))
        
        spot = cursor.fetchone()
        
        if not spot:
            flash('Spot not found or not assigned to you.', 'danger')
            return redirect(url_for('waiter_dashboard'))
        
        # Initialize order as None
        order = None
        
        # Get current order if exists
        if not spot['availability'] and spot['cust_id']:
            cursor.execute("""
                SELECT o.order_id, o.time_stamp, o.paid_status
                FROM orders o
                WHERE o.cust_id = %s AND o.paid_status = 0
                ORDER BY o.time_stamp DESC
                LIMIT 1
            """, (spot['cust_id'],))
            
            order_data = cursor.fetchone()
            
            if order_data:
                # Create a new dictionary for the order
                order = {
                    'order_id': order_data['order_id'],
                    'time_stamp': order_data['time_stamp'],
                    'paid_status': order_data['paid_status'],
                    'items': []  # Initialize as an empty list
                }
                
                # Get order items with chef information
                cursor.execute("""
                    SELECT od.*, m.item_name, m.category, m.item_price, e.e_name as chef_name
                    FROM order_details od
                    JOIN menu m ON od.item_id = m.item_id
                    LEFT JOIN employee e ON od.chef_id = e.emp_id
                    WHERE od.order_id = %s
                """, (order_data['order_id'],))
                
                items = cursor.fetchall()
                
                # Process order items
                for item in items:
                    # Add status color
                    status_colors = {
                        'placed': 'warning',
                        'cooking': 'info',
                        'cooked': 'success',
                        'delivered': 'primary',
                        'billed': 'secondary'
                    }
                    item['status_color'] = status_colors.get(item['order_status'], 'secondary')
                    order['items'].append(item)
                
                # Check if all items are billed
                order['all_billed'] = all(item['order_status'] == 'billed' for item in order['items'])
        
        return render_template('waiter/spot_details.html', spot=spot, order=order)
    
    except Exception as e:
        import traceback
        print(f"Error in waiter_spot_details: {str(e)}")
        print(traceback.format_exc())
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('waiter_dashboard'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/customer/bill/<int:order_id>')
def customer_bill(order_id):
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('customer_login'))
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify the order belongs to the current customer
        cursor.execute("""
            SELECT o.order_id, o.cust_id, o.bill_status, s.table_id, s.waiter_id
            FROM orders o
            JOIN spots s ON o.cust_id = s.cust_id
            WHERE o.order_id = %s AND o.cust_id = %s AND o.paid_status = 0
        """, (order_id, session['user_id']))
        
        order_data = cursor.fetchone()
        if not order_data:
            flash('Order not found or not authorized', 'danger')
            return redirect(url_for('customer_dashboard'))
        
        # Get order items
        cursor.execute("""
            SELECT od.*, m.item_name, m.item_price
            FROM order_details od
            JOIN menu m ON od.item_id = m.item_id
            WHERE od.order_id = %s
        """, (order_id,))
        
        items = cursor.fetchall()
        
        # Calculate totals
        subtotal = sum(item['item_price'] * item['qty'] for item in items)
        tax = subtotal * Decimal('0.18')  # 18% tax
        total = subtotal + tax
        
        # Calculate loyalty points (1 point per ₹10 spent)
        points_earned = int(float(total) / 10)
        
        # Check if bill has been requested
        bill_requested = order_data['bill_status'] == 'requested'
        
        return render_template('customer/bill.html', 
                              order=order_data,
                              items=items,
                              subtotal=subtotal,
                              tax=tax,
                              total=total,
                              points_earned=points_earned,
                              bill_requested=bill_requested)
    
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/admin/employee_details')
def admin_employee_details():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin to access this page.', 'error')
        return redirect(url_for('employee_login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get all employees with correct column names based on the actual schema
        cursor.execute("""
            SELECT emp_id as employee_id, e_name as full_name, e_phone as phone, 
                   role, e_status as is_active, salary 
            FROM employee 
            ORDER BY role, e_name
        """)
        
        employees = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('admin/employee_details.html', employees=employees)
        
    except Exception as e:
        print(f"Error in admin_employee_details: {str(e)}")  # Add logging
        flash('Error retrieving employee details. Please try again.', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_employee_status', methods=['POST'])
def admin_toggle_employee_status():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized access'})
    
    try:
        data = request.get_json()
        employee_id = data.get('employee_id')
        
        if not employee_id:
            return jsonify({'success': False, 'error': 'Employee ID is required'})
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get current status
        cursor.execute("SELECT e_status FROM employee WHERE emp_id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Employee not found'})
        
        # Toggle status between 'active' and 'inactive'
        new_status = 'inactive' if employee['e_status'] == 'active' else 'active'
        
        # Update the status
        cursor.execute("""
            UPDATE employee 
            SET e_status = %s 
            WHERE emp_id = %s
        """, (new_status, employee_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error in toggle_employee_status: {str(e)}")  # Add logging
        return jsonify({'success': False, 'error': str(e)})

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been successfully logged out!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True) 