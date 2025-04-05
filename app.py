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
        
        # Get order history
        cursor.execute('''
            SELECT o.order_id, o.time_stamp, od.order_status,
                   GROUP_CONCAT(CONCAT(m.item_name, ':', od.qty) SEPARATOR '|') as items,
                   SUM(m.item_price * od.qty) as total
            FROM `order` o
            JOIN order_details od ON o.order_id = od.order_id
            JOIN menu m ON od.item_id = m.item_id
            WHERE o.cust_id = %s
            GROUP BY o.order_id, o.time_stamp, od.order_status
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
                'status': row['order_status'],
                'status_color': 'success' if row['order_status'] == 'delivered' else 'warning'
            })
        
        return render_template('customer/dashboard.html', customer=customer, orders=orders)
        
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
            ORDER BY category, item_name
        ''')
        menu_items = cursor.fetchall()
        
        # Group items by category
        categories = {}
        for item in menu_items:
            if item['category'] not in categories:
                categories[item['category']] = []
            categories[item['category']].append(item)
        
        # Convert to a regular dictionary to avoid the 'items' method conflict
        categories_dict = {}
        for category, menu_items_list in categories.items():
            categories_dict[category] = menu_items_list
        
        return render_template('menu.html', categories=categories_dict)
    except Error as e:
        flash(f'Database error: {str(e)}', 'danger')
        return redirect(url_for('customer_dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session or session['role'] != 'customer':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    items = data.get('items', [])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create new order
        cursor.execute('INSERT INTO `order` (cust_id) VALUES (%s)', (session['user_id'],))
        order_id = cursor.lastrowid
        
        # Add order details
        for item in items:
            cursor.execute('''
                INSERT INTO order_details (order_id, item_id, qty)
                VALUES (%s, %s, %s)
            ''', (order_id, item['id'], item['quantity']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'order_id': order_id})
    except Error as e:
        return jsonify({'error': str(e)}), 500

@app.route('/waiter/dashboard')
def waiter_dashboard():
    if 'user_id' not in session or session['role'] != 'waiter':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get waiter's tables and their orders
    cursor.execute('''
        SELECT t.*, c.c_name, od.order_id, od.item_id, od.order_status, m.item_name
        FROM tables t
        LEFT JOIN customer c ON t.cust_id = c.cust_id
        LEFT JOIN `order` o ON c.cust_id = o.cust_id
        LEFT JOIN order_details od ON o.order_id = od.order_id
        LEFT JOIN menu m ON od.item_id = m.item_id
        WHERE t.waiter_id = (SELECT waiter_id FROM waiter WHERE emp_id = %s)
    ''', (session['user_id'],))
    
    tables_data = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('waiter/dashboard.html', tables_data=tables_data)

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
        JOIN `order` o ON od.order_id = o.order_id
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
            FROM `order` o
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

if __name__ == '__main__':
    app.run(debug=True) 