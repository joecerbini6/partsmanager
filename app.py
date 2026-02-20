from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-for-local')  # Use env var on Render
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Redirects to /login if not logged in

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100))

class Part(db.Model):
    pn = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    price = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text, default='')
    tag = db.Column(db.String(50), default='')
    supplier_url = db.Column(db.String(200), default='')
    usage_history = db.Column(db.JSON, default=list)
    reorder_threshold = db.Column(db.Integer, default=10, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

    # Pre-seed users if none exist (change passwords!)
    if User.query.count() == 0:
        users = [
            User(username='joe', password=generate_password_hash('password123')),  # Change this!
            User(username='mike', password=generate_password_hash('pass123')),
            User(username='tech1', password=generate_password_hash('techpass')),
            # Add more for "all the guys" - change passwords after first login
        ]
        db.session.bulk_save_objects(users)
        db.session.commit()

    # Starter parts if empty
    if Part.query.count() == 0:
        starter = [
            Part(pn="SCR-001", name="Hex Screw", quantity=120, price=0.15,
                 description="M4 screw", tag="generator", supplier_url="",
                 usage_history=[], reorder_threshold=10),
            Part(pn="BLT-002", name="Carriage Bolt", quantity=45, price=0.50,
                 description="5/16 bolt", tag="transfer switch", supplier_url="",
                 usage_history=[], reorder_threshold=10),
        ]
        db.session.bulk_save_objects(starter)
        db.session.commit()

def parts_to_dict(parts):
    return {p.pn: {
        'name': p.name,
        'quantity': p.quantity,
        'price': p.price,
        'description': p.description,
        'tag': p.tag,
        'supplier_url': p.supplier_url,
        'usage_history': p.usage_history,
        'reorder_threshold': p.reorder_threshold
    } for p in parts}

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))  # NEW: Force login first
    return render_template('index.html', title="Dashboard")

@app.route('/view')
@login_required
def view_parts():
    category = request.args.get('category', 'all')
    title = "All Parts"
    query = Part.query

    if category == 'low':
        query = query.filter(Part.quantity > 0, Part.quantity < Part.reorder_threshold)
        title = "Low Stock Parts"
    elif category == 'out':
        query = query.filter(Part.quantity == 0)
        title = "Out of Stock Parts"
    elif category in ['generator', 'transfer switch', 'other']:
        if category == 'other':
            query = query.filter((Part.tag == '') | (Part.tag == 'other'))
        else:
            query = query.filter(Part.tag == category)
        title = f"{category.replace(' ', '_').capitalize()} Parts"

    parts_list = query.all()
    parts_dict = parts_to_dict(parts_list)

    return render_template('view.html', parts=parts_dict, title=title)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_part():
    if request.method == 'POST':
        pn = request.form['part_number'].strip().upper()
        if Part.query.get(pn):
            flash("Part number already exists!", "danger")
            return redirect(url_for('add_part'))

        try:
            threshold = int(request.form.get('reorder_threshold', 10))
            if threshold < 1:
                threshold = 10
                flash("Reorder threshold must be ≥ 1 — using 10.", "warning")
        except (ValueError, TypeError):
            threshold = 10
            flash("Invalid reorder threshold — using 10.", "warning")

        new_part = Part(
            pn=pn,
            name=request.form['name'].strip(),
            quantity=int(request.form.get('quantity', 0)),
            price=float(request.form.get('price', 0.0)),
            description=request.form.get('description', '').strip(),
            tag=request.form.get('tag', '').strip().lower(),
            supplier_url=request.form.get('supplier_url', '').strip(),
            usage_history=[],
            reorder_threshold=threshold
        )
        db.session.add(new_part)
        db.session.commit()
        flash("Part added successfully!", "success")
        return redirect(url_for('view_parts'))

    return render_template('add.html', title="Add New Part")

@app.route('/usage', methods=['GET', 'POST'])
@login_required
def record_usage():
    if request.method == 'POST':
        pn = request.form['part_number'].strip().upper()
        part = Part.query.get(pn)
        if not part:
            flash("Part not found!", "danger")
            return redirect(url_for('usage'))

        try:
            used = int(request.form['used'])
            if used <= 0 or used > part.quantity:
                flash("Invalid quantity used!", "danger")
                return redirect(url_for('usage'))

            part.quantity -= used
            part.usage_history = part.usage_history or []
            part.usage_history.append({
                "date": datetime.now().isoformat(),
                "quantity_used": used,
                "user": current_user.username
            })
            db.session.commit()
            flash(f"Recorded {used} used for {part.name} by {current_user.username}. New stock: {part.quantity}", "success")
        except ValueError:
            flash("Invalid number!", "danger")

        return redirect(url_for('view_parts'))

    return render_template('usage.html', title="Record Usage", inventory=Part.query.all())

@app.route('/reorder')
@login_required
def reorder():
    low_parts_query = Part.query.filter(Part.quantity < Part.reorder_threshold).all()
    low_parts_dict = parts_to_dict(low_parts_query)
    return render_template('reorder.html', title="Reorder Suggestions", parts=low_parts_dict)

@app.route('/delete/<pn>', methods=['POST'])
@login_required
def delete_part(pn):
    part = Part.query.get(pn)
    if part:
        name = part.name
        db.session.delete(part)
        db.session.commit()
        flash(f"Part {name} ({pn}) deleted.", "success")
    else:
        flash("Part not found.", "danger")
    return redirect(url_for('view_parts', **request.args))

@app.route('/edit/<pn>', methods=['GET', 'POST'])
@login_required
def edit_part(pn):
    part = Part.query.get(pn)
    if not part:
        flash("Part not found.", "danger")
        return redirect(url_for('view_parts'))

    if request.method == 'POST':
        part.name = request.form.get('name', part.name).strip()
        part.description = request.form.get('description', part.description).strip()
        part.tag = request.form.get('tag', part.tag).strip().lower()
        part.supplier_url = request.form.get('supplier_url', part.supplier_url).strip()

        try:
            part.price = float(request.form.get('price', part.price))
        except ValueError:
            flash("Invalid price — keeping original.", "warning")

        try:
            qty = int(request.form.get('quantity', part.quantity))
            part.quantity = max(0, qty)
        except ValueError:
            flash("Invalid quantity — keeping original.", "warning")

        try:
            threshold = int(request.form.get('reorder_threshold', part.reorder_threshold))
            part.reorder_threshold = max(1, threshold)
        except ValueError:
            flash("Invalid reorder threshold — keeping original.", "warning")

        db.session.commit()
        flash(f"{part.name} ({pn}) updated successfully!", "success")
        return redirect(url_for('view_parts'))

    return render_template('edit.html', part=part, pn=pn, title=f"Edit {part.name}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Logged in successfully!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")
    return render_template('login.html', title="Login")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "danger")
            return redirect(url_for('register'))

        new_user = User(
            username=username,
            password=generate_password_hash(password),
            email=email
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Account created! You can now log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html', title="Create Account")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for('login'))  # Redirect to login after logout


    
