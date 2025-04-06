from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Customer(UserMixin, db.Model):
    __tablename__ = 'customer'
    cust_id = db.Column('cust_id', db.Integer, primary_key=True)
    c_phone = db.Column('c_phone', db.String(15), unique=True, nullable=False)
    c_name = db.Column('c_name', db.String(100), nullable=False)
    loyal_pts = db.Column('loyal_pts', db.Integer, default=100)
    orders = db.relationship('Order', backref='customer', lazy=True)

    def get_id(self):
        return str(self.cust_id)
        
    @property
    def id(self):
        return self.cust_id

class MenuItem(db.Model):
    __tablename__ = 'menu'
    item_id = db.Column('item_id', db.Integer, primary_key=True)
    item_name = db.Column('item_name', db.String(100), nullable=False)
    allergen = db.Column('allergen', db.String(255))
    rating = db.Column('rating', db.Numeric(3, 2), default=0)
    category = db.Column('category', db.String(50), nullable=False)
    availability = db.Column('availability', db.Boolean, default=True)
    item_price = db.Column('item_price', db.Numeric(10, 2), nullable=False)
    prep_time = db.Column('prep_time', db.Integer, nullable=False)
    image_url = db.Column('image_url', db.String(255))
    order_items = db.relationship('OrderItem', backref='menu_item', lazy=True)

class Order(db.Model):
    __tablename__ = 'orders'
    order_id = db.Column('order_id', db.Integer, primary_key=True)
    paid_status = db.Column('paid_status', db.Boolean, default=False)
    time_stamp = db.Column('time_stamp', db.DateTime, default=datetime.utcnow)
    cust_id = db.Column('cust_id', db.Integer, db.ForeignKey('customer.cust_id'), nullable=False)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    __tablename__ = 'order_details'
    order_id = db.Column('order_id', db.Integer, db.ForeignKey('orders.order_id'), primary_key=True)
    item_id = db.Column('item_id', db.Integer, db.ForeignKey('menu.item_id'), primary_key=True)
    order_status = db.Column('order_status', db.Enum('placed', 'cooking', 'cooked', 'delivered', 'billed'), default='placed')
    chef_id = db.Column('chef_id', db.Integer, db.ForeignKey('chef.chef_id'))
    qty = db.Column('qty', db.Integer, nullable=False) 