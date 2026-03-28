from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import datetime
import io
import qrcode
from bson import ObjectId

# ------------------- Configuration -------------------
app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config["MONGO_URI"] = "mongodb://localhost:27017/parking_db"
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024  # 4MB limit for uploads
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

mongo = PyMongo(app)

# ------------------- Single Admin (from user's request) -------------------
ADMIN_USERNAME = "Vaishnavi"
ADMIN_EMAIL = "vaishnaviparasa@gmail.com"
ADMIN_PASSWORD = "vyshu123"

# Ensure an admin user exists in DB on startup (one-time upsert)
with app.app_context():
    users = mongo.db.users
    admin = users.find_one({"email": ADMIN_EMAIL})
    if not admin:
        users.insert_one({
            "username": ADMIN_USERNAME,
            "email": ADMIN_EMAIL,
            "password": generate_password_hash(ADMIN_PASSWORD),
            "is_admin": True,
            "profile_pic": None,
        })


@app.context_processor
def inject_session():
    return dict(session=session)


# ------------------- Helpers -------------------
def current_user():
    """Return user document for the logged-in user or None"""
    if not session.get('user_email'):
        return None
    return mongo.db.users.find_one({"email": session['user_email']})


# ------------------- Routes -------------------

@app.route('/')
def dashboard():
    user = current_user()
    is_admin = user and user.get('is_admin')

    if is_admin:
        return redirect(url_for('admin_dashboard'))

    is_logged_in = bool(user)
    username = user.get('username') if user else None

    return render_template(
        'abc.html',
        username=username,
        is_logged_in=is_logged_in
    )




# ------------------- Login/Register (No Changes) -------------------

@app.route('/login', methods=['GET','POST'])
def login_page():
    if request.method == 'POST':
        email_or_username = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        users = mongo.db.users
        user = users.find_one({"email": email_or_username}) or users.find_one({"username": email_or_username})

        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'})

        if check_password_hash(user['password'], password):
            session['logged_in'] = True
            session['user_email'] = user['email']
            session['username'] = user['username']

            redirect_url = url_for('admin_dashboard') if user.get('is_admin') else url_for('dashboard')

            return jsonify({'status': 'success', 'message': 'Login successful', 'redirect': redirect_url})
        else:
            return jsonify({'status': 'error', 'message': 'Incorrect password'})

    return render_template('SignUp_LogIn_Form.html', show='login')


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        users = mongo.db.users

        # Check duplicate username or email
        if users.find_one({"username": username}):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': 'Username already exists'})
            else:
                flash('Username already exists', 'error')
                return redirect(url_for('register_page'))

        if users.find_one({"email": email}):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': 'Email already exists'})
            else:
                flash('Email already exists', 'error')
                return redirect(url_for('register_page'))

        users.insert_one({
            'username': username,
            'email': email,
            'password': generate_password_hash(password),
            'is_admin': False,
            'profile_pic': None
        })

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'success', 'message': 'Signup successful'})
        else:
            flash('Signup successful! Please login.', 'success')
            return redirect(url_for('login_page'))

    return render_template('SignUp_LogIn_Form.html', show='register')


@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = mongo.db.users.find_one({'email': email})
        if not user:
            flash('Email not found')
            return redirect(url_for('forgot_password'))

        flash('Password reset instructions sent to your email.')
        return redirect(url_for('login_page'))

    return render_template('forrr.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('dashboard'))



# ------------------- User Interaction Routes -------------------

@app.route('/book', methods=['GET','POST'])
def book_slot():
    user = current_user()
    if not user:
        return redirect(url_for('login_page'))

    if request.method == 'POST':
        location = request.form.get('location')
        date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        vehicle_type = request.form.get('vehicle_type')
        plate_number = request.form.get('plate_number')
        parking_type = request.form.get('parking_type')

        if not all([location, date, start_time, end_time, plate_number]):
            flash('Missing required booking details. Please fill out the form.', 'error')
            return redirect(url_for('book_slot'))

        start_dt = f"{date} {start_time}"
        end_dt = f"{date} {end_time}"

        booking = {
            'user_email': user['email'],
            'username': user['username'],
            'location': location,
            'date': date,
            'start_time': start_dt,
            'end_time': end_dt,
            'vehicle_type': vehicle_type,
            'plate_number': plate_number,
            'parking_type': parking_type,
            'created_at': datetime.datetime.utcnow(),
            'paid': False,
            'transaction_id': None,
            'user_qr': None
        }
        result = mongo.db.bookings.insert_one(booking)
        session['pending_booking_id'] = str(result.inserted_id)
        flash('Booking details saved. Proceed to payment.', 'success')

        return redirect(url_for('payment_page'))

    return render_template('get.html')


@app.route('/see_details')
def see_details():
    user = current_user()
    if not user:
        return redirect(url_for('login_page'))
    # fetch all bookings for this user
    bookings = list(mongo.db.bookings.find({'user_email': user['email']}).sort('created_at', -1))
    return render_template('see.html', bookings=bookings, username=user.get('username'))


slot_data = {
    "narsapur": 5,
    "bhimavaram": 7,
    "palakollu": 0,
    "vizag": 10,
    "hyderabad": 0,
    "visakapatnam": 3,
    "kakinada": 15,
    "vijayawada": 0,
    "phagwara": 10,
    "jalandar": 0,
    "delhi": 50,
}

@app.route('/check_slots')
def check_slots():
    place = request.args.get('place', '').strip().lower()
    count = slot_data.get(place, 0)
    return jsonify({
        "available": count > 0,
        "count": count
    })


@app.route('/payment', methods=['GET','POST'])
def payment_page():
    user = current_user()
    if not user:
        return redirect(url_for('login_page'))

    booking_id = session.get('pending_booking_id')
    if not booking_id:
        flash('No pending booking found. Please book a slot.', 'error')
        return redirect(url_for('book_slot'))

    if request.method == 'POST':
        txid = request.form.get('transaction_id')
        if not txid:
            flash('Please enter transaction id', 'error')
            return redirect(url_for('payment_page'))

        # Save TXID to session temporarily (paid=False)
        session['txid'] = txid
        return redirect(url_for('book_waiting'))

    # GET: Show payment instructions (Merchant QR + TXID form)
    merchant_qr = 'qrcode.png'
    return render_template('payment.html', merchant_qr=merchant_qr)


@app.route('/book_waiting')
def book_waiting():
    user = current_user()
    if not user:
        return redirect(url_for('login_page'))

    booking_id = session.get('pending_booking_id')
    txid = session.get('txid')
    if not booking_id or not txid:
        flash('Missing booking or transaction info.', 'error')
        return redirect(url_for('book_slot'))

    # Fetch booking from DB
    b = mongo.db.bookings.find_one({'_id': ObjectId(booking_id)})
    if not b:
        flash('Booking not found.', 'error')
        return redirect(url_for('book_slot'))

    # Generate QR code
    qr_data = f"booking:{booking_id}|tx:{txid}|user:{user['email']}"
    qr_img = qrcode.make(qr_data)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format='PNG')
    qr_buf.seek(0)
    filename = f'user_qr_{booking_id}.png'
    qr_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(qr_path, 'wb') as f:
        f.write(qr_buf.read())

    # Update booking with QR & TXID, but keep paid=False for waiting
    mongo.db.bookings.update_one(
        {'_id': ObjectId(booking_id)},
        {'$set': {'user_qr': f'uploads/{filename}', 'transaction_id': txid}}
    )

    # Render waiting page
    return render_template(
        'book.html',
        booking_id=booking_id,
        generated_qr_url=url_for('static', filename=f'uploads/{filename}')
    )




@app.route('/payment_success/<booking_id>')
def payment_success(booking_id):
    """Final payment success page after book.html countdown"""
    user = current_user()
    if not user:
        return redirect(url_for('login_page'))

    b = mongo.db.bookings.find_one({'_id': ObjectId(booking_id)})
    if not b:
        flash('Booking not found.', 'error')
        return redirect(url_for('book_slot'))

    # Mark as paid
    mongo.db.bookings.update_one({'_id': ObjectId(booking_id)}, {'$set': {'paid': True}})

    qr_url = url_for('static', filename=b['user_qr'])
    ticket_url = b.get('ticket_pdf') or '#'

    current_time = datetime.datetime.now().strftime("%H:%M")

    # Pass the booking object to template
    return render_template('payment_success.html', booking=b, qr_url=qr_url, ticket_url=ticket_url, current_time=current_time)



@app.route('/admin')
def admin_dashboard():
    user = current_user()
    if not user or not user.get('is_admin'):
        return redirect(url_for('login_page'))

    # --- Booking Stats ---
    total_bookings = mongo.db.bookings.count_documents({})
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    today_bookings = mongo.db.bookings.count_documents({'date': today_date})

    recent_bookings = list(mongo.db.bookings.find().sort('created_at', -1).limit(10))

    # --- Contact Messages ---
    recent_messages = list(mongo.db.contacts.find().sort('created_at', -1).limit(5))

    stats = {
        'total_bookings': total_bookings,
        'today_bookings': today_bookings,
        'recent_bookings': recent_bookings,
        'recent_messages': recent_messages
    }

    return render_template(
        'admin_dashboard.html',
        username=user.get('username'),
        stats=stats,
        profile_pic=user.get('profile_pic') or url_for('static', filename='default_admin.png')
    )


@app.route('/admin/manage_users')
def manage_users():
    user = current_user()
    if not user or not user.get('is_admin'):
        return redirect(url_for('login_page'))

    # Only fetch non-admin users
    users = list(mongo.db.users.find({'is_admin': False}))
    return render_template('admin_manage_users.html', users=users)


@app.route('/admin/delete_users', methods=['POST'])
def delete_users():
    user = current_user()
    if not user or not user.get('is_admin'):
        return redirect(url_for('login_page'))

    user_ids = request.form.getlist('user_ids[]')
    from bson.objectid import ObjectId
    for uid in user_ids:
        target_user = mongo.db.users.find_one({'_id': ObjectId(uid)})
        if target_user and not target_user.get('is_admin'):
            mongo.db.users.delete_one({'_id': ObjectId(uid)})

    flash(f"{len(user_ids)} user(s) deleted successfully.", "success")
    return redirect(url_for('manage_users'))




@app.route('/admin/booking/<booking_id>')
def admin_view_booking(booking_id):
    user = current_user()
    if not user or not user.get('is_admin'):
        return redirect(url_for('login_page'))
    try:
        b = mongo.db.bookings.find_one({'_id': ObjectId(booking_id)})
    except:
        b = None
    if not b:
        flash('Booking not found', 'error')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_view_booking.html', booking=b)


# ------------------- Profile & Change Password -------------------
@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect(url_for("login_page"))
    user = mongo.db.users.find_one({"username": session["username"]})
    return render_template("profile.html", user=user)


@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "username" not in session:
        return redirect(url_for("login_page"))
    username = request.form["username"]
    email = request.form["email"]
    mongo.db.users.update_one({"username": session["username"]}, {"$set": {"username": username, "email": email}})
    session["username"] = username
    user = mongo.db.users.find_one({"username": username})
    return render_template("profile.html", user=user, success="Profile updated successfully!")


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    # Determine where the user came from
    next_page = request.args.get('next', None)

    if request.method == "POST":
        username = request.form.get("username")
        new_password = request.form.get("new_password")

        user = mongo.db.users.find_one({"username": username})
        if not user:
            flash("Username not found. Please check and try again.", "error")
            return redirect(request.referrer or url_for("change_password"))

        hashed = generate_password_hash(new_password)
        mongo.db.users.update_one({"username": username}, {"$set": {"password": hashed}})
        flash("Password updated successfully! You can now log in.", "success")

        # Redirect after update
        return redirect(url_for("login_page"))

    # GET request → render template with next_page info
    return render_template("forrr.html", next_page=next_page)




# ------------------- Utility Routes -------------------

@app.route('/download_qr/<filename>')
def download_qr(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(path):
        return 'File not found', 404
    return send_file(path, as_attachment=True)


@app.route('/api/check_user', methods=['POST'])
def api_check_user():
    data = request.json or {}
    email = data.get('email')
    if not email:
        return jsonify({'ok': False, 'error': 'email required'}), 400
    u = mongo.db.users.find_one({'email': email})
    return jsonify({'ok': bool(u)})


import smtplib
import os
from email.message import EmailMessage

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('fullName') or 'Anonymous'
    email = request.form.get('emailAddress') or ''
    subject = request.form.get('subjectText') or 'No Subject'
    message = request.form.get('messageArea') or ''

    if not email:
        flash('Please enter a valid email address.', 'error')
        return redirect(request.referrer)

    mongo.db.contacts.insert_one({
        'name': name,
        'email': email,
        'subject': subject,
        'message': message,
        'created_at': datetime.datetime.utcnow()
    })

    flash('Your message has been sent successfully!', 'success')
    return redirect(request.referrer)


# ------------------- Run -------------------
if __name__ == '__main__':
    app.run(debug=True)
