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

-- Tables table
CREATE TABLE IF NOT EXISTS tables (
    table_id INT PRIMARY KEY AUTO_INCREMENT,
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

-- Order table
CREATE TABLE IF NOT EXISTS `order` (
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
    FOREIGN KEY (order_id) REFERENCES `order`(order_id),
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
    FOREIGN KEY (order_id) REFERENCES `order`(order_id),
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

INSERT INTO tables (QR_code, waiter_id) VALUES
('table1_qr', 1),
('table2_qr', 1);

-- Insert sample menu items
INSERT INTO menu (item_name, allergen, rating, category, item_price, prep_time, image_url) VALUES
-- Pizza Category
('Margherita Pizza', 'Dairy, Gluten', 4.5, 'Pizza', 299.00, 15, '/static/images/pizza/margherita.jpg'),
('Pepperoni Pizza', 'Dairy, Gluten, Pork', 4.8, 'Pizza', 399.00, 18, '/static/images/pizza/pepperoni.jpg'),
('Vegetarian Supreme', 'Dairy, Gluten', 4.6, 'Pizza', 349.00, 20, '/static/images/pizza/veg-supreme.jpg'),
('BBQ Chicken Pizza', 'Dairy, Gluten, Egg', 4.7, 'Pizza', 449.00, 20, '/static/images/pizza/bbq-chicken.jpg'),

-- Burgers Category
('Classic Burger', 'Gluten, Egg', 4.3, 'Burgers', 199.00, 10, '/static/images/burgers/classic.jpg'),
('Cheese Burger', 'Dairy, Gluten, Egg', 4.4, 'Burgers', 249.00, 12, '/static/images/burgers/cheese.jpg'),
('Veg Burger', 'Gluten, Egg', 4.2, 'Burgers', 179.00, 8, '/static/images/burgers/veg.jpg'),
('Chicken Burger', 'Gluten, Egg', 4.5, 'Burgers', 299.00, 15, '/static/images/burgers/chicken.jpg'),

-- Salads Category
('Caesar Salad', 'Egg, Dairy', 4.0, 'Salads', 149.00, 5, '/static/images/salads/caesar.jpg'),
('Greek Salad', 'Dairy', 4.1, 'Salads', 169.00, 5, '/static/images/salads/greek.jpg'),
('Chicken Salad', 'Egg', 4.3, 'Salads', 199.00, 8, '/static/images/salads/chicken.jpg'),
('Quinoa Salad', NULL, 4.2, 'Salads', 179.00, 7, '/static/images/salads/quinoa.jpg'),

-- Tiffin Category
('Veg Thali', NULL, 4.4, 'Tiffin', 199.00, 15, '/static/images/tiffin/veg-thali.jpg'),
('Non-Veg Thali', 'Egg', 4.6, 'Tiffin', 299.00, 20, '/static/images/tiffin/non-veg-thali.jpg'),
('South Indian Thali', NULL, 4.5, 'Tiffin', 249.00, 18, '/static/images/tiffin/south-indian.jpg'),
('Chinese Thali', 'Egg', 4.3, 'Tiffin', 279.00, 20, '/static/images/tiffin/chinese.jpg'),

-- Lunch Category
('Butter Chicken', 'Dairy', 4.7, 'Lunch', 349.00, 25, '/static/images/lunch/butter-chicken.jpg'),
('Paneer Butter Masala', 'Dairy', 4.6, 'Lunch', 299.00, 20, '/static/images/lunch/paneer.jpg'),
('Biryani', 'Egg', 4.8, 'Lunch', 279.00, 25, '/static/images/lunch/biryani.jpg'),
('Dal Makhani', 'Dairy', 4.5, 'Lunch', 199.00, 20, '/static/images/lunch/dal.jpg'),

-- Drinks Category
('Fresh Lime Soda', NULL, 4.2, 'Drinks', 49.00, 2, '/static/images/drinks/lime-soda.jpg'),
('Masala Chai', 'Dairy', 4.5, 'Drinks', 39.00, 3, '/static/images/drinks/masala-chai.jpg'),
('Fresh Juice', NULL, 4.4, 'Drinks', 79.00, 5, '/static/images/drinks/fresh-juice.jpg'),
('Cold Coffee', 'Dairy', 4.3, 'Drinks', 89.00, 4, '/static/images/drinks/cold-coffee.jpg'); 