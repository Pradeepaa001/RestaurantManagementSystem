-- Create database
CREATE DATABASE IF NOT EXISTS restaurant_db;
USE restaurant_db;

-- Customer table
CREATE TABLE IF NOT EXISTS customer (
    cust_id INT PRIMARY KEY AUTO_INCREMENT,
    c_phone VARCHAR(15) UNIQUE NOT NULL,
    c_name VARCHAR(100) NOT NULL,
    loyal_pts INT DEFAULT 100
);

-- Employee table
CREATE TABLE IF NOT EXISTS employee (
    emp_id INT PRIMARY KEY AUTO_INCREMENT,
    e_name VARCHAR(100) NOT NULL,
    role ENUM('admin', 'chef', 'waiter') NOT NULL,
    e_phone VARCHAR(15) UNIQUE NOT NULL,
    passwd VARCHAR(255) NOT NULL,
    e_status ENUM('active', 'inactive') DEFAULT 'active',
    salary DECIMAL(10,2) NOT NULL
);

-- Chef table
CREATE TABLE IF NOT EXISTS chef (
    chef_id INT PRIMARY KEY AUTO_INCREMENT,
    emp_id INT,
    specialization VARCHAR(100),
    FOREIGN KEY (emp_id) REFERENCES employee(emp_id)
);

-- Waiter table
CREATE TABLE IF NOT EXISTS waiter (
    waiter_id INT PRIMARY KEY AUTO_INCREMENT,
    emp_id INT,
    FOREIGN KEY (emp_id) REFERENCES employee(emp_id)
);

-- Spots table (renamed from tables)
CREATE TABLE IF NOT EXISTS spots (
    spot_id INT PRIMARY KEY AUTO_INCREMENT,
    availability BOOLEAN DEFAULT TRUE,
    QR_code VARCHAR(255) UNIQUE NOT NULL,
    cust_id INT,
    waiter_id INT,
    FOREIGN KEY (cust_id) REFERENCES customer(cust_id),
    FOREIGN KEY (waiter_id) REFERENCES waiter(waiter_id)
);

-- Menu table
CREATE TABLE IF NOT EXISTS menu (
    item_id INT PRIMARY KEY AUTO_INCREMENT,
    item_name VARCHAR(100) NOT NULL,
    allergen VARCHAR(255),
    rating DECIMAL(3,2) DEFAULT 0,
    category VARCHAR(50) NOT NULL,
    availability BOOLEAN DEFAULT TRUE,
    item_price DECIMAL(10,2) NOT NULL,
    prep_time INT NOT NULL,
    image_url VARCHAR(255)
);

-- Orders table (renamed from order)
CREATE TABLE IF NOT EXISTS orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    paid_status BOOLEAN DEFAULT FALSE,
    time_stamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cust_id INT,
    FOREIGN KEY (cust_id) REFERENCES customer(cust_id)
);

-- Order details table
CREATE TABLE IF NOT EXISTS order_details (
    order_id INT,
    item_id INT,
    order_status ENUM('placed', 'cooking', 'cooked', 'delivered', 'billed') DEFAULT 'placed',
    chef_id INT,
    qty INT NOT NULL,
    PRIMARY KEY (order_id, item_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (item_id) REFERENCES menu(item_id),
    FOREIGN KEY (chef_id) REFERENCES chef(chef_id)
);

-- Bill table
CREATE TABLE IF NOT EXISTS bill (
    bill_id INT PRIMARY KEY AUTO_INCREMENT,
    tot_amt DECIMAL(10,2) NOT NULL,
    tax DECIMAL(10,2) NOT NULL,
    discount DECIMAL(10,2) DEFAULT 0,
    final_amt DECIMAL(10,2) NOT NULL,
    pay_mode ENUM('cash', 'online') NOT NULL,
    order_id INT,
    waiter_id INT,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (waiter_id) REFERENCES waiter(waiter_id)
);

-- Insert sample data
INSERT INTO customer (c_phone, c_name, loyal_pts) VALUES
('9876543210', 'John Doe', 150),
('9876543211', 'Jane Smith', 200);

INSERT INTO employee (e_name, role, e_phone, passwd, salary) VALUES
('Admin User', 'admin', '9876543212', 'admin123', 50000),
('Chef Gordon', 'chef', '9876543213', 'chef123', 45000),
('Waiter Tom', 'waiter', '9876543214', 'waiter123', 30000);

INSERT INTO chef (emp_id, specialization) VALUES
(2, 'Italian Cuisine');

INSERT INTO waiter (emp_id) VALUES
(3);

INSERT INTO spots (QR_code, waiter_id) VALUES
('spot1_qr', 1),
('spot2_qr', 1);

-- Insert sample menu items
INSERT INTO menu (item_name, allergen, rating, category, item_price, prep_time, image_url) VALUES
('Margherita Pizza', 'Dairy, Gluten', 4.5, 'Pizza', 299.00, 15, '/static/images/pizza.jpeg'),
('Chicken Burger', 'Egg, Gluten', 4.2, 'Burgers', 199.00, 10, '/static/images/burger.jpeg'),
('Caesar Salad', 'Egg, Dairy', 4.0, 'Salads', 149.00, 5, '/static/images/salad.jpeg'); 
INSERT INTO menu (item_name, allergen, rating, category, item_price, prep_time, image_url) VALUES
('Dosa', 'Ghee, oil', 4.5, 'Tiffin', 99.00, 10, '/static/images/dosa.jpg');
-- Tiffin Category
('Idly', NULL, 4.9, 'Tiffin', 69.00, 15, '/static/images/idly.jpeg'),
('Chapthi', 'Maida', 4.6, 'Tiffin', 49.00, 6, '/static/images/chapathi.jpeg'),

-- Lunch Category
('Veg Thali', 'Dairy', 4.7, 'Lunch', 349.00, 25, '/static/images/veg-thali.jpeg'),
('Biryani', 'Cashew, Spices', 4.8, 'Lunch', 279.00, 25, '/static/images/biryani.jpeg'),

-- Drinks Category
('Fresh Lime Soda', NULL, 4.2, 'Drinks', 49.00, 2, '/static/images/soda.jpeg'),
('Filter Coffee', 'Dairy', 4.5, 'Drinks', 39.00, 3, '/static/images/coffee.jpeg');