from flask import Flask, render_template, request, redirect, url_for, flash
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "your_secret_key_change_me_123"  # Change this to something random

DATA_FILE = "inventory.json"
LOW_STOCK = 10

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    # Default starter data
    return {
        "SCR-001": {"name": "Hex Screw", "quantity": 120, "price": 0.15, "description": "M4 screw", "tag": "generator", "supplier_url": "", "usage_history": []},
        "BLT-002": {"name": "Carriage Bolt", "quantity": 45, "price": 0.50, "description": "5/16 bolt", "tag": "transfer switch", "supplier_url": "", "usage_history": []},
    }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

inventory = load_data()

@app.route('/')
def index():
    return render_template('index.html', title="Dashboard")

@app.route('/view')
def view_parts():
    category = request.args.get('category', 'all')
    title = "All Parts"
    parts = inventory

    if category == 'low':
        parts = {k: v for k, v in inventory.items() if 0 < v['quantity'] < LOW_STOCK}
        title = "Low Stock Parts"
    elif category == 'out':
        parts = {k: v for k, v in inventory.items() if v['quantity'] == 0}
        title = "Out of Stock Parts"
    elif category in ['generator', 'transfer switch', 'other']:
        parts = {k: v for k, v in inventory.items() if v.get('tag', 'other') == category}
        title = f"{category.capitalize()} Parts"

    return render_template('view.html', parts=parts, title=title, category=category)

@app.route('/add', methods=['GET', 'POST'])
def add_part():
    if request.method == 'POST':
        pn = request.form['part_number'].strip().upper()
        if pn in inventory:
            flash("Part number already exists!", "danger")
            return redirect(url_for('add_part'))

        inventory[pn] = {
            'name': request.form['name'].strip(),
            'quantity': int(request.form.get('quantity', 0)),
            'price': float(request.form.get('price', 0.0)),
            'description': request.form.get('description', '').strip(),
            'tag': request.form.get('tag', '').strip().lower(),
            'supplier_url': request.form.get('supplier_url', '').strip(),
            'usage_history': []
        }
        save_data(inventory)
        flash("Part added successfully!", "success")
        return redirect(url_for('view_parts'))

    return render_template('add.html', title="Add New Part")

@app.route('/usage', methods=['GET', 'POST'])
def record_usage():
    if request.method == 'POST':
        pn = request.form['part_number'].strip().upper()
        if pn not in inventory:
            flash("Part not found!", "danger")
            return redirect(url_for('record_usage'))

        try:
            used = int(request.form['used'])
            if used <= 0 or used > inventory[pn]['quantity']:
                flash("Invalid quantity used!", "danger")
                return redirect(url_for('record_usage'))

            inventory[pn]['quantity'] -= used
            inventory[pn]['usage_history'].append({
                "date": datetime.now().isoformat(),
                "quantity_used": used
            })
            save_data(inventory)
            flash(f"Recorded {used} used for {inventory[pn]['name']}. New stock: {inventory[pn]['quantity']}", "success")
        except ValueError:
            flash("Invalid number!", "danger")

        return redirect(url_for('view_parts'))

    return render_template('usage.html', title="Record Usage", inventory=inventory)

# Placeholder for Reorder Suggestions (expand later)
@app.route('/reorder')
def reorder():
    low_parts = {k: v for k, v in inventory.items() if v['quantity'] < LOW_STOCK}
    return render_template('reorder.html', title="Reorder Suggestions", parts=low_parts)
@app.route('/delete/<pn>', methods=['POST'])
def delete_part(pn):
    if pn in inventory:
        name = inventory[pn]['name']
        del inventory[pn]
        save_data(inventory)
        flash(f"Part {name} ({pn}) deleted.", "success")
    else:
        flash("Part not found.", "danger")
    return redirect(url_for('view_parts', **request.args))
@app.route('/edit/<pn>', methods=['GET', 'POST'])
def edit_part(pn):
    if pn not in inventory:
        flash("Part not found.", "danger")
        return redirect(url_for('view_parts'))

    part = inventory[pn]

    if request.method == 'POST':
        part['name'] = request.form.get('name', part['name']).strip()
        part['description'] = request.form.get('description', part['description']).strip()
        part['tag'] = request.form.get('tag', part.get('tag', '')).strip().lower()
        part['supplier_url'] = request.form.get('supplier_url', part.get('supplier_url', '')).strip()

        try:
            part['price'] = float(request.form.get('price', part['price']))
        except ValueError:
            flash("Invalid price — keeping original.", "warning")

        try:
            part['quantity'] = int(request.form.get('quantity', part['quantity']))
            if part['quantity'] < 0:
                part['quantity'] = 0
                flash("Quantity cannot be negative — set to 0.", "warning")
        except ValueError:
            flash("Invalid quantity — keeping original.", "warning")

        save_data(inventory)
        flash(f"{part['name']} ({pn}) updated successfully!", "success")
        return redirect(url_for('view_parts'))

    return render_template('edit.html', part=part, pn=pn, title=f"Edit {part['name']}")
if __name__ == '__main__':
    app.run(debug=True)
    
