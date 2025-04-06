from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime
import json
from dotenv import load_dotenv

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
        
        conn = get_db_connection()
        if not conn:
            return render_template('customer_login.html', error="Database connection error")
            
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM customer WHERE c_phone = %s', (phone,))
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user['cust_id']
                session['role'] = 'customer'
                return redirect(url_for('customer_dashboard'))
            
            flash('Phone number not found. Please register first.', 'danger')
        except Error as e:
            flash(f'Database error: {str(e)}', 'danger')
        finally:
            cursor.close()
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
        
        # Get current unpaid order
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
            
            for item in cursor.fetchall():
                status_color = {
                    'placed': 'warning',
                    'cooking': 'info',
                    'cooked': 'success',
                    'delivered': 'primary',
                    'billed': 'secondary'
                }.get(item['order_status'], 'secondary')
                
                current_order['order_items'].append({
                    'item_id': item['item_id'],
                    'item_name': item['item_name'],
                    'qty': item['qty'],
                    'order_status': item['order_status'],
                    'status_color': status_color
                })
        
        # Get order history (paid orders)
        cursor.execute('''
            SELECT o.order_id, o.time_stamp, o.paid_status,
                   GROUP_CONCAT(CONCAT(m.item_name, ':', od.qty) SEPARATOR '|') as items,
                   SUM(m.item_price * od.qty) as total
            FROM orders o
            JOIN order_details od ON o.order_id = od.order_id
            JOIN menu m ON od.item_id = m.item_id
            WHERE o.cust_id = %s AND o.paid_status = TRUE
            GROUP BY o.order_id, o.time_stamp, o.paid_status
            ORDER BY o.time_stamp DESC
        ''', (session['user_id'],))
        
        orders = []
        for row in cursor.fetchall():
            order_items = []
            if row['items']:  # Check if items exist
                for item in row['items'].split('|'):
                    name, qty = item.split(':')
                    order_items.append({'item_name': name, 'qty': int(qty)})
            
            orders.append({
                'order_id': row['order_id'],
                'time_stamp': row['time_stamp'],
                'order_items': order_items,
                'total': float(row['total']) if row['total'] else 0.0,
                'status': 'Completed',
                'status_color': 'success'
            })
        
        return render_template('customer/dashboard.html', 
                              customer=customer, 
                              current_order=current_order,
                              orders=orders)
        
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

@app.route('/waiter/dashboard')
def waiter_dashboard():
    if 'user_id' not in session or session['role'] != 'waiter':
        return redirect(url_for('employee_login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get waiter's spots and their orders
        cursor.execute('''
            SELECT s.*, c.c_name, o.order_id, o.paid_status,
                   GROUP_CONCAT(CONCAT(m.item_name, ':', od.qty, ':', od.order_status) SEPARATOR '|') as items,
                   COUNT(*) as total_items,
                   SUM(CASE WHEN od.order_status = 'billed' THEN 1 ELSE 0 END) as billed_items
            FROM spots s
            LEFT JOIN customer c ON s.cust_id = c.cust_id
            LEFT JOIN orders o ON c.cust_id = o.cust_id AND o.paid_status = FALSE
            LEFT JOIN order_details od ON o.order_id = od.order_id
            LEFT JOIN menu m ON od.item_id = m.item_id
            WHERE s.waiter_id = (SELECT waiter_id FROM waiter WHERE emp_id = %s)
            GROUP BY s.table_id, c.c_name, o.order_id, o.paid_status
        ''', (session['user_id'],))
        
        spots_data = []
        for row in cursor.fetchall():
            spot_data = {
                'spot_id': row['table_id'],
                'customer_name': row['c_name'],
                'order_id': row['order_id'],
                'items': [],
                'all_billed': False
            }
            
            if row['items']:
                for item in row['items'].split('|'):
                    name, qty, status = item.split(':')
                    spot_data['items'].append({
                        'item_name': name,
                        'qty': int(qty),
                        'order_status': status,
                        'status_color': {
                            'placed': 'warning',
                            'cooking': 'info',
                            'cooked': 'success',
                            'delivered': 'primary',
                            'billed': 'secondary'
                        }.get(status, 'secondary')
                    })
                
                # Check if all items are billed
                spot_data['all_billed'] = (row['total_items'] == row['billed_items'])
            
            spots_data.append(spot_data)
        
        return render_template('waiter/dashboard.html', spots_data=spots_data)
        
    except Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('employee_login'))
    finally:
        cursor.close()
        conn.close()

@app.route('/chef/dashboard')
def chef_dashboard():
    if 'user_id' not in session or session['role'] != 'chef':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get all pending orders
    cursor.execute('''
        SELECT od.*, m.item_name, m.prep_time, c.c_name
        FROM order_details od
        JOIN menu m ON od.item_id = m.item_id
        JOIN orders o ON od.order_id = o.order_id
        JOIN customer c ON o.cust_id = c.cust_id
        WHERE od.order_status IN ('placed', 'cooking')
    ''')
    
    orders = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('chef/dashboard.html', orders=orders)

@app.route('/update_order_status', methods=['POST'])
def update_order_status():
    data = request.json
    order_id = data.get('order_id')
    item_id = data.get('item_id')
    status = data.get('status')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE order_details 
            SET order_status = %s, chef_id = %s
            WHERE order_id = %s AND item_id = %s
        ''', (status, session.get('user_id'), order_id, item_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Error as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_bill', methods=['POST'])
def generate_bill():
    data = request.json
    order_id = data.get('order_id')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Calculate total amount
        cursor.execute('''
            SELECT SUM(m.item_price * od.qty) as total
            FROM order_details od
            JOIN menu m ON od.item_id = m.item_id
            WHERE od.order_id = %s
        ''', (order_id,))
        
        result = cursor.fetchone()
        total = result['total']
        tax = total * 0.18  # 18% tax
        final_amount = total + tax
        
        # Create bill
        cursor.execute('''
            INSERT INTO bill (tot_amt, tax, final_amt, pay_mode, order_id, waiter_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (total, tax, final_amount, 'online', order_id, session.get('user_id')))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'bill': {
                'total': total,
                'tax': tax,
                'final_amount': final_amount
            }
        })
    except Error as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been successfully logged out!', 'success')
    return redirect(url_for('index'))

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
                print(f"Updated item {item['id']} in order {order_id}")
            else:
                # Add new item to order
                cursor.execute('''
                    INSERT INTO order_details (order_id, item_id, qty, order_status)
                    VALUES (%s, %s, %s, 'placed')
                ''', (order_id, item['id'], item['quantity']))
                print(f"Added item {item['id']} to order {order_id}")
        
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
                print(f"Updated item {item['id']} in order {order_id}")
            else:
                # Add new item to order
                cursor.execute('''
                    INSERT INTO order_details (order_id, item_id, qty, order_status)
                    VALUES (%s, %s, %s, 'placed')
                ''', (order_id, item['id'], item['quantity']))
                print(f"Added item {item['id']} to order {order_id}")
        
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

if __name__ == '__main__':
    app.run(debug=True) 