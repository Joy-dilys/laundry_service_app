from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import traceback
from datetime import datetime # Import for timestamps

# --- App Configuration ---
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for sessions and flash messages

# --- Database Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))  # Get the directory of the app
db_path = os.path.join(basedir, 'instance', 'laundry.db')  # Full path to database

# Configure SQLAlchemy to use SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Initialize Database ---
db = SQLAlchemy(app)

# --- User Model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'client' or 'business'
    # Adding a backref to link to business and client orders
    business_profile = db.relationship('Business', backref='owner_user', uselist=False)
    client_orders = db.relationship('Order', backref='client', lazy=True, foreign_keys='Order.client_id')

class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True) # Ensure one business per owner
    name = db.Column(db.String(150), nullable=False, unique=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    description = db.Column(db.Text)

    services = db.relationship('Service', backref='business', lazy=True)
    # Orders can be retrieved via services.orders or directly if business_id was on Order, but that's removed for better design
    # If you still want direct access, you'd need a more complex relationship or a query join

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)

    orders = db.relationship('Order', backref='service', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    
    quantity = db.Column(db.Float, nullable=False) # e.g., weight in kg, or number of items
    pickup_date = db.Column(db.DateTime, nullable=False)
    delivery_date = db.Column(db.DateTime, nullable=True) # Optional, can be set by business
    pickup_address = db.Column(db.String(255), nullable=False)
    delivery_address = db.Column(db.String(255), nullable=False) # Can be same as pickup

    status = db.Column(db.String(50), default='Pending', nullable=False) # e.g., Pending, Accepted, In Progress, Ready for Pickup/Delivery, Completed, Declined
    notes = db.Column(db.Text)
    total_price = db.Column(db.Float, nullable=True) # Can be calculated after business accepts

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# --- Ensure 'instance/' folder exists and create tables ---
with app.app_context():
    if not os.path.exists('instance'):
        os.makedirs('instance')
    db.create_all()

# --- Home Route ---
@app.route('/')
def home():
    return render_template('index.html', now=datetime.utcnow)

# --- Signup Route ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        # Check if username or email already exists
        existing_user_username = User.query.filter_by(username=username).first()
        existing_user_email = User.query.filter_by(email=email).first()

        if existing_user_username:
            flash("Error: Username already exists. Please choose a different username.", "danger")
            return render_template('signup.html')
        
        if existing_user_email:
            flash("Error: Email address is already registered. Please use a different email or log in.", "danger")
            return render_template('signup.html')

        hashed_password = generate_password_hash(password)

        new_user = User(username=username, email=email, password=hashed_password, role=role)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            traceback.print_exc() # This will print the error to your console/terminal
            flash("An unexpected error occurred during signup. Please try again.", "danger")
    
    return render_template('signup.html')

# --- Login Route ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(f"Welcome back, {user.username}!", "success")

            if user.role == 'business':
                return redirect(url_for('business_dashboard'))
            else:
                return redirect(url_for('client_dashboard'))
        else:
            flash("Invalid email or password.", "danger")
            return render_template('login.html') 
            
    return render_template('login.html')

# --- Client Dashboard Route ---
@app.route('/client_dashboard')
def client_dashboard():
    if 'user_id' not in session or session['role'] != 'client':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))
    
    # Clients are immediately directed to browse services
    return redirect(url_for('browse_services')) 

# --- Business Dashboard Route ---
@app.route('/business_dashboard')
def business_dashboard():
    if 'user_id' not in session or session['role'] != 'business':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    business = Business.query.filter_by(owner_id=session['user_id']).first()
    
    # Fetch orders relevant to this business's services
    # This involves joining Service and Order tables
    if business:
        business_orders = Order.query.join(Service).filter(Service.business_id == business.id).order_by(Order.created_at.desc()).all()
    else:
        business_orders = [] # No business profile yet, so no orders
        
    return render_template('business_dashboard.html', business=business, orders=business_orders)


# --- Business Profile Route ---
@app.route('/business_profile', methods=['GET', 'POST'])
def business_profile():
    if 'user_id' not in session or session['role'] != 'business':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    business = Business.query.filter_by(owner_id=session['user_id']).first()

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        address = request.form['address']
        description = request.form['description']

        if business:
            business.name = name
            business.phone = phone
            business.address = address
            business.description = description
        else:
            # Check for duplicate business name before creating
            existing_business_name = Business.query.filter_by(name=name).first()
            if existing_business_name:
                flash("Error: A business with this name already exists.", "danger")
                return render_template('business_profile.html', business=business)

            business = Business(
                owner_id=session['user_id'],
                name=name,
                phone=phone,
                address=address,
                description=description
            )
            db.session.add(business)

        try:
            db.session.commit()
            flash("Business profile saved successfully!", "success")
            return redirect(url_for('business_dashboard'))
        except Exception as e:
            traceback.print_exc()
            flash("Error saving business profile. Please ensure the business name is unique.", "danger")

    return render_template('business_profile.html', business=business)

# --- Add Service Route (Business) ---
@app.route('/add_service', methods=['GET', 'POST'])
def add_service():
    if 'user_id' not in session or session['role'] != 'business':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    business = Business.query.filter_by(owner_id=session['user_id']).first()
    if not business:
        flash("Please create your business profile first before adding services.", "warning")
        return redirect(url_for('business_profile'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']

        try:
            price = float(price)
            # Check for duplicate service name for this business
            existing_service = Service.query.filter_by(business_id=business.id, name=name).first()
            if existing_service:
                flash(f"Error: You already have a service named '{name}'.", "danger")
                return render_template('add_service.html', business=business)

            new_service = Service(name=name, description=description, price=price, business_id=business.id)
            db.session.add(new_service)
            db.session.commit()
            flash("Service added successfully!", "success")
            return redirect(url_for('manage_services')) # Redirect to a management page
        except ValueError:
            flash("Invalid price. Please enter a numerical value.", "danger")
        except Exception as e:
            traceback.print_exc()
            flash("An error occurred while adding the service.", "danger")

    return render_template('add_service.html', business=business) # Pass business to template for context


# --- Manage Services Route (Business) ---
@app.route('/manage_services')
def manage_services():
    if 'user_id' not in session or session['role'] != 'business':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    business = Business.query.filter_by(owner_id=session['user_id']).first()
    if not business:
        flash("Please complete your business profile to manage services.", "info")
        return redirect(url_for('business_profile'))

    services = Service.query.filter_by(business_id=business.id).all()
    return render_template('manage_services.html', services=services, business=business) # Pass business for nav links

# --- Delete Service Route (Business) ---
@app.route('/delete_service/<int:service_id>', methods=['POST']) # Changed to POST
def delete_service(service_id):
    if 'user_id' not in session or session['role'] != 'business':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    service = Service.query.get_or_404(service_id) # Use get_or_404 for cleaner handling
    
    # Ensure the service belongs to the logged-in business
    if service.business.owner_id != session['user_id']:
        flash("Unauthorized action: You cannot delete a service that doesn't belong to your business.", "danger")
        return redirect(url_for('manage_services'))

    try:
        # Check if there are any active orders for this service before deleting
        # This prevents breaking foreign key constraints
        active_orders = Order.query.filter_by(service_id=service.id).count()
        if active_orders > 0:
            flash(f"Cannot delete service '{service.name}'. There are {active_orders} associated orders.", "danger")
            return redirect(url_for('manage_services'))

        db.session.delete(service)
        db.session.commit()
        flash(f"Service '{service.name}' deleted successfully!", "success")
    except Exception as e:
        traceback.print_exc()
        flash("An error occurred while deleting the service.", "danger")

    return redirect(url_for('manage_services'))

# --- Browse Services (Client) ---
@app.route('/services')
def browse_services():
    # Clients can browse services even if not logged in, but can only book if logged in
    # This also handles search queries
    query = request.args.get('q')
    location = request.args.get('location')

    services_query = Service.query.join(Business)

    if query:
        services_query = services_query.filter(Service.name.ilike(f"%{query}%"))
    
    if location:
        services_query = services_query.filter(Business.address.ilike(f"%{location}%"))

    services = services_query.order_by(Service.name).all() # Order alphabetically
    return render_template('browse_services.html', services=services, current_search_q=query, current_search_location=location)


# --- Book Service Route (Client) ---
@app.route('/book/<int:service_id>', methods=['GET', 'POST'])
def book_service(service_id): # Renamed function for clarity
    if 'user_id' not in session or session['role'] != 'client':
        flash("Please log in as a client to book services.", "danger")
        return redirect(url_for('login'))

    service = Service.query.get_or_404(service_id) # Use get_or_404
    client_user = User.query.get(session['user_id']) # Get current client's user object

    if request.method == 'POST':
        try:
            quantity = float(request.form.get('quantity'))
            if quantity <= 0:
                flash("Quantity must be a positive number.", "danger")
                return render_template('book_service.html', service=service, client=client_user)

            pickup_date_str = request.form['pickup_date']
            pickup_time_str = request.form['pickup_time']
            pickup_address = request.form['pickup_address']
            delivery_address = request.form['delivery_address']
            notes = request.form.get('notes', '')

            # Combine date and time string for datetime object
            pickup_datetime_combined = f"{pickup_date_str} {pickup_time_str}"
            pickup_datetime = datetime.strptime(pickup_datetime_combined, '%Y-%m-%d %H:%M')

            # Calculate initial total price
            total_price = service.price * quantity

            new_order = Order(
                client_id=session['user_id'],
                service_id=service.id,
                quantity=quantity,
                pickup_date=pickup_datetime,
                pickup_address=pickup_address,
                delivery_address=delivery_address,
                notes=notes,
                total_price=total_price,
                status='Pending' # Initial status
            )
            db.session.add(new_order)
            db.session.commit()
            flash(f"Order for {service.name} placed successfully! Awaiting business confirmation.", "success")
            return redirect(url_for('client_orders'))
        except ValueError:
            flash("Invalid quantity or date/time format. Please check your input.", "danger")
        except Exception as e:
            traceback.print_exc()
            flash("An error occurred while placing your order. Please try again.", "danger")

    return render_template('book_service.html', service=service, client=client_user)


# --- Business Orders Route ---
@app.route('/business_orders')
def business_orders():
    if 'user_id' not in session or session['role'] != 'business':
        flash("Only businesses can view this page.", "danger")
        return redirect(url_for('login'))

    business = Business.query.filter_by(owner_id=session['user_id']).first()
    if not business:
        flash("Please complete your business profile to view orders.", "info")
        return redirect(url_for('business_profile'))
        
    # Fetch orders associated with services offered by this business
    orders = Order.query.join(Service).filter(Service.business_id == business.id).order_by(Order.created_at.desc()).all()
    return render_template('business_orders.html', orders=orders)


# --- Update Order Status (Business) ---
@app.route('/update_order_status/<int:order_id>/<action>', methods=['POST']) # Consistent naming
def update_order_status(order_id, action):
    if 'user_id' not in session or session['role'] != 'business':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)

    # Ensure the order's service belongs to the current business
    if order.service.business.owner_id != session['user_id']:
        flash("Unauthorized action: You cannot manage an order that doesn't belong to your business.", "danger")
        return redirect(url_for('business_orders'))

    valid_actions = ['accept', 'decline', 'in_progress', 'ready', 'complete']
    
    if action not in valid_actions:
        flash("Invalid order action.", "danger")
        return redirect(url_for('business_orders'))

    # Update status based on action
    if action == 'accept':
        order.status = 'Accepted'
        # Example: if you wanted business to set delivery date upon acceptance
        # delivery_date_str = request.form.get('delivery_date')
        # if delivery_date_str:
        #     order.delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d')
        flash(f"Order {order.id} for {order.client.username} has been Accepted.", "success")
    elif action == 'decline':
        order.status = 'Declined'
        flash(f"Order {order.id} for {order.client.username} has been Declined.", "info")
    elif action == 'in_progress':
        order.status = 'In Progress'
        flash(f"Order {order.id} is now In Progress.", "info")
    elif action == 'ready':
        order.status = 'Ready for Pickup/Delivery'
        flash(f"Order {order.id} is Ready for Pickup/Delivery.", "info")
    elif action == 'complete':
        order.status = 'Completed'
        flash(f"Order {order.id} has been Completed.", "success")
    
    try:
        db.session.commit()
    except Exception as e:
        traceback.print_exc()
        flash("Error updating order status.", "danger")

    return redirect(url_for('business_orders'))


# --- Client Orders Route ---
@app.route('/client_orders')
def client_orders():
    if 'user_id' not in session or session['role'] != 'client':
        flash("Only clients can view this page.", "danger")
        return redirect(url_for('login'))

    # Fetch orders placed by the logged-in client, ordered by creation date
    orders = Order.query.filter_by(client_id=session['user_id']).order_by(Order.created_at.desc()).all()
    return render_template('client_orders.html', orders=orders)


# --- Logout Route ---
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('home'))

# --- Run Flask Server ---
if __name__ == '__main__': # Corrected this line
    app.run(debug=True)