"""
SVHEC Canteen Order & Classroom Delivery System
------------------------------------------------
A Flask + SQLite project for pre-ordering canteen food/snacks and
stationery items, with time-slot delivery to classrooms and an
admin panel for canteen staff.

Run with:
    python app.py
Then open http://127.0.0.1:5000
"""

import os
import random
import string
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = "svhec-canteen-secret-key"  # change in production
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "canteen.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Config: hardcoded admin login + delivery time slots
# ---------------------------------------------------------------------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # change this for real use

TIME_SLOTS = [
    "10:30 AM - 10:45 AM (Short Break)",
    "12:45 PM - 1:30 PM (Lunch Break)",
    "3:15 PM - 3:30 PM (Short Break)",
]

STATUS_FLOW = ["Placed", "Preparing", "Out for Delivery", "Delivered"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    roll_no = db.Column(db.String(30), unique=True, nullable=False)
    department = db.Column(db.String(80))
    classroom = db.Column(db.String(40))
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(20), nullable=False)  # 'food' or 'stationery'
    price = db.Column(db.Float, nullable=False)
    available = db.Column(db.Boolean, default=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(12), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    time_slot = db.Column(db.String(80), nullable=False)
    classroom = db.Column(db.String(40))
    status = db.Column(db.String(20), default="Placed")
    total_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", backref="orders")
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_item.id"), nullable=False)
    name = db.Column(db.String(100))  # snapshot of name at order time
    price = db.Column(db.Float)       # snapshot of price at order time
    quantity = db.Column(db.Integer, default=1)

    menu_item = db.relationship("MenuItem")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def current_student():
    sid = session.get("student_id")
    if not sid:
        return None
    return Student.query.get(sid)


def login_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_student():
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Please log in as admin.", "error")
            return redirect(url_for("admin_login"))
        return view_func(*args, **kwargs)

    return wrapper


def generate_order_code():
    return "SVH-" + "".join(random.choices(string.digits, k=5))


def get_cart():
    return session.get("cart", {})  # {menu_item_id (str): quantity}


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


# ---------------------------------------------------------------------------
# Public / auth routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", student=current_student())


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll_no = request.form.get("roll_no", "").strip()
        department = request.form.get("department", "").strip()
        classroom = request.form.get("classroom", "").strip()
        password = request.form.get("password", "")

        if not name or not roll_no or not password:
            flash("Name, ID number and password are required.", "error")
            return redirect(url_for("register"))

        if Student.query.filter_by(roll_no=roll_no).first():
            flash("An account with this ID number already exists.", "error")
            return redirect(url_for("register"))

        student = Student(name=name, roll_no=roll_no, department=department, classroom=classroom)
        student.set_password(password)
        db.session.add(student)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        password = request.form.get("password", "")
        student = Student.query.filter_by(roll_no=roll_no).first()
        if student and student.check_password(password):
            session["student_id"] = student.id
            flash(f"Welcome back, {student.name}!", "success")
            return redirect(url_for("menu"))
        flash("Invalid ID number or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("student_id", None)
    session.pop("cart", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Menu + cart routes
# ---------------------------------------------------------------------------
@app.route("/menu")
@login_required
def menu():
    food_items = MenuItem.query.filter_by(category="food", available=True).all()
    stationery_items = MenuItem.query.filter_by(category="stationery", available=True).all()
    cart = get_cart()
    cart_count = sum(cart.values())
    return render_template(
        "menu.html", food_items=food_items, stationery_items=stationery_items,
        cart=cart, cart_count=cart_count, student=current_student()
    )


@app.route("/cart/add/<int:item_id>", methods=["POST"])
@login_required
def add_to_cart(item_id):
    item = MenuItem.query.get_or_404(item_id)
    cart = get_cart()
    key = str(item_id)
    cart[key] = cart.get(key, 0) + 1
    save_cart(cart)
    flash(f"Added {item.name} to cart.", "success")
    return redirect(request.referrer or url_for("menu"))


@app.route("/cart")
@login_required
def cart_view():
    cart = get_cart()
    cart_items = []
    total = 0.0
    for item_id_str, qty in cart.items():
        item = MenuItem.query.get(int(item_id_str))
        if not item:
            continue
        subtotal = item.price * qty
        total += subtotal
        cart_items.append({"item": item, "qty": qty, "subtotal": subtotal})
    return render_template(
        "cart.html", cart_items=cart_items, total=total,
        time_slots=TIME_SLOTS, student=current_student()
    )


@app.route("/cart/update/<int:item_id>", methods=["POST"])
@login_required
def update_cart(item_id):
    qty = int(request.form.get("quantity", 1))
    cart = get_cart()
    key = str(item_id)
    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = qty
    save_cart(cart)
    return redirect(url_for("cart_view"))


@app.route("/cart/remove/<int:item_id>")
@login_required
def remove_from_cart(item_id):
    cart = get_cart()
    cart.pop(str(item_id), None)
    save_cart(cart)
    return redirect(url_for("cart_view"))


@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    student = current_student()
    cart = get_cart()
    if not cart:
        flash("Your cart is empty.", "error")
        return redirect(url_for("menu"))

    time_slot = request.form.get("time_slot")
    classroom = request.form.get("classroom", student.classroom)
    if time_slot not in TIME_SLOTS:
        flash("Please choose a valid delivery time slot.", "error")
        return redirect(url_for("cart_view"))

    order = Order(
        order_code=generate_order_code(),
        student_id=student.id,
        time_slot=time_slot,
        classroom=classroom,
        status="Placed",
    )
    total = 0.0
    for item_id_str, qty in cart.items():
        item = MenuItem.query.get(int(item_id_str))
        if not item:
            continue
        order.items.append(OrderItem(menu_item_id=item.id, name=item.name, price=item.price, quantity=qty))
        total += item.price * qty
    order.total_amount = total

    db.session.add(order)
    db.session.commit()
    save_cart({})

    flash(f"Order placed! Your order code is {order.order_code}.", "success")
    return redirect(url_for("order_detail", order_id=order.id))


# ---------------------------------------------------------------------------
# Order history / status (student side)
# ---------------------------------------------------------------------------
@app.route("/orders")
@login_required
def order_history():
    student = current_student()
    orders = Order.query.filter_by(student_id=student.id).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=orders, student=student)


@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    student = current_student()
    order = Order.query.get_or_404(order_id)
    if order.student_id != student.id:
        flash("You cannot view this order.", "error")
        return redirect(url_for("order_history"))
    return render_template(
        "order_detail.html", order=order, status_flow=STATUS_FLOW, student=student
    )


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Logged in as canteen admin.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "error")
        return redirect(url_for("admin_login"))
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    status_filter = request.args.get("status", "")
    query = Order.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    orders = query.order_by(Order.created_at.desc()).all()
    return render_template(
        "admin_dashboard.html", orders=orders, status_flow=STATUS_FLOW,
        status_filter=status_filter
    )


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status")
    if new_status in STATUS_FLOW:
        order.status = new_status
        db.session.commit()
        flash(f"Order {order.order_code} marked as {new_status}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/menu")
@admin_required
def admin_menu():
    items = MenuItem.query.order_by(MenuItem.category, MenuItem.name).all()
    return render_template("admin_menu.html", items=items)


@app.route("/admin/menu/add", methods=["POST"])
@admin_required
def admin_menu_add():
    name = request.form.get("name", "").strip()
    category = request.form.get("category")
    price = request.form.get("price", "0")
    try:
        price = float(price)
    except ValueError:
        price = 0.0
    if name and category in ("food", "stationery"):
        db.session.add(MenuItem(name=name, category=category, price=price, available=True))
        db.session.commit()
        flash(f"Added {name} to the menu.", "success")
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/<int:item_id>/toggle", methods=["POST"])
@admin_required
def admin_menu_toggle(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.available = not item.available
    db.session.commit()
    return redirect(url_for("admin_menu"))


@app.route("/admin/menu/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_menu_delete(item_id):
    item = MenuItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Item removed from menu.", "success")
    return redirect(url_for("admin_menu"))


# ---------------------------------------------------------------------------
# Database init + seed data
# ---------------------------------------------------------------------------
def seed_menu():
    if MenuItem.query.first():
        return
    food = [
        ("Veg Puff", 15), ("Samosa", 12), ("Masala Dosa", 40),
        ("Idli (2 pcs)", 25), ("Veg Sandwich", 30), ("Tea", 10),
        ("Coffee", 12), ("Cold Drink (300ml)", 20), ("Curd Rice", 35),
        ("Biryani (Veg)", 60),
    ]
    stationery = [
        ("A4 Notebook", 40), ("Ball Pen (Blue)", 10), ("Pencil", 5),
        ("Eraser", 5), ("Graph Sheet", 8), ("A4 Bond Paper (10 sheets)", 15),
    ]
    for name, price in food:
        db.session.add(MenuItem(name=name, category="food", price=price, available=True))
    for name, price in stationery:
        db.session.add(MenuItem(name=name, category="stationery", price=price, available=True))
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_menu()


if __name__ == "__main__":
    app.run(debug=True)
