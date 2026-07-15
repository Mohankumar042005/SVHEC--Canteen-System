# SVHEC Canteen Order & Classroom Delivery System

A Flask + SQLite mini project that lets students pre-order canteen food,
snacks and stationery, choose a permitted break time slot, and have the
order delivered to their classroom — with an admin panel for canteen staff.

## Features (MVP scope)
- Student registration & login (ID number + password)
- Menu with prices, split into **Food & Snacks** and **Stationery**
- Cart with quantity edit
- Time-slot selection at checkout (only permitted break times)
- Classroom delivery address on each order
- Order status tracking: **Placed → Preparing → Out for Delivery → Delivered**
- Order history for each student
- Admin panel: view/filter all orders, update status, manage menu items
  (add, hide/show, delete)

## Tech stack
- Python 3, Flask
- Flask-SQLAlchemy (SQLite database, file: `canteen.db`, created automatically)
- Server-rendered HTML templates (Jinja2), plain CSS — no JS framework needed

## Setup

```bash
cd canteen_system
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

The database (`canteen.db`) and a starter menu are created automatically
the first time you run the app.

## Demo logins

- **Student:** register your own account from the "Register" page.
- **Admin panel:** go to `/admin/login`
  - Username: `admin`
  - Password: `admin123`

  (Change `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `app.py` before using this
  for anything beyond a demo.)

## Project structure

```
canteen_system/
├── app.py                  # routes, models, app logic
├── requirements.txt
├── static/
│   └── style.css
└── templates/
    ├── base.html            # shared layout + nav
    ├── index.html           # landing page
    ├── register.html / login.html
    ├── menu.html            # browse food/stationery
    ├── cart.html            # cart + checkout (time slot, classroom)
    ├── orders.html          # student order history
    ├── order_detail.html    # single order "ticket" with status tracker
    ├── admin_login.html
    ├── admin_dashboard.html # all orders, filter + update status
    └── admin_menu.html      # add/hide/delete menu items
```

## How the flow matches "order → confirm → prepare → deliver"

1. **Order** — student logs in, adds items from the menu to the cart.
2. **Confirm** — at checkout, student picks a time slot + classroom;
   an order code (e.g. `SVH-48213`) is generated.
3. **Prepare** — canteen admin sees the order on the dashboard and marks
   it "Preparing".
4. **Deliver** — admin updates status to "Out for Delivery" then
   "Delivered"; the student sees live status on their order ticket page.

## Ideas for extending later
- Payment integration (UPI/Razorpay sandbox) instead of pay-on-delivery
- Push/email notification when status changes
- Daily sales report for admin (best-selling items, revenue by day)
- QR code on the order ticket for pickup/delivery confirmation
- Full campus delivery (multiple canteens/stalls, delivery staff assignment)
