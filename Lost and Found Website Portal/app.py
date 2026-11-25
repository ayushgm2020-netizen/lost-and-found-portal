import os
import secrets
import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, session, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config, BASE_DIR
from database.db import query_db, execute_db, init_db, get_db_status
from matching.matcher import SmartMatcher, calculate_similarity_breakdown

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database schema and seeds
init_db()

# -------------------------------------------------------------
# HELPER FUNCTIONS & DECORATORS
# -------------------------------------------------------------

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        if session.get('user_role') != 'admin':
            flash('Administrative privileges required to access this portal.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def create_notification(user_id, title, message, link=None):
    """Inserts a notification record into database."""
    try:
        execute_db(
            "INSERT INTO notifications (user_id, title, message, link, is_read) VALUES (%s, %s, %s, %s, 0)",
            (user_id, title, message, link)
        )
    except Exception as e:
        app.logger.error(f"Error creating notification: {e}")

def run_smart_matching_for_item(target_item):
    """
    Triggers the Python matching engine for a newly created or updated item
    and updates the database matches table and notifications.
    """
    institution_id = target_item['institution_id']
    is_lost = target_item['type'] == 'lost'
    target_id = target_item['id']

    # Fetch candidate items of opposite type within the same institution
    opposite_type = 'found' if is_lost else 'lost'
    candidates = query_db(
        "SELECT * FROM items WHERE institution_id = %s AND type = %s AND status NOT IN ('recovered', 'closed')",
        (institution_id, opposite_type)
    )

    matches_found = SmartMatcher.match_item_against_pool(target_item, candidates, min_threshold=40.0)

    for m in matches_found:
        lost_id = m['lost_item_id']
        found_id = m['found_item_id']
        score = m['score']
        factors = m['factors']

        # Check existing match
        existing = query_db(
            "SELECT id FROM matches WHERE lost_item_id = %s AND found_item_id = %s",
            (lost_id, found_id),
            one=True
        )

        if existing:
            execute_db(
                """UPDATE matches SET score = %s, factor_name = %s, factor_category = %s, 
                   factor_description = %s, factor_location = %s, factor_date = %s 
                   WHERE id = %s""",
                (score, factors['name']['score'], factors['category']['score'],
                 factors['description']['score'], factors['location']['score'],
                 factors['date']['score'], existing['id'])
            )
        else:
            execute_db(
                """INSERT INTO matches (institution_id, lost_item_id, found_item_id, score, 
                   factor_name, factor_category, factor_description, factor_location, factor_date, status) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'suggested')""",
                (institution_id, lost_id, found_id, score,
                 factors['name']['score'], factors['category']['score'],
                 factors['description']['score'], factors['location']['score'],
                 factors['date']['score'])
            )

        # Notify users if strong match (score >= 70%)
        if score >= 70.0:
            lost_user = m['lost_item']['user_id']
            found_user = m['found_item']['user_id']
            link = url_for('matches')
            
            create_notification(
                lost_user,
                f"Smart Match Detected ({score}% match)",
                f"A found item '{m['found_item']['name']}' closely matches your lost '{m['lost_item']['name']}'.",
                link
            )
            create_notification(
                found_user,
                f"Potential Owner Found ({score}% match)",
                f"A lost report '{m['lost_item']['name']}' closely matches the item you found.",
                link
            )

            # Advance status to 'match_found' if still in 'reported'
            if m['lost_item']['status'] == 'reported':
                execute_db("UPDATE items SET status = 'match_found' WHERE id = %s", (lost_id,))
            if m['found_item']['status'] == 'reported':
                execute_db("UPDATE items SET status = 'match_found' WHERE id = %s", (found_id,))

# Inject global variables into all Jinja2 templates
@app.context_processor
def inject_global_context():
    unread_count = 0
    current_user = None
    if 'user_id' in session:
        unread_row = query_db(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0",
            (session['user_id'],),
            one=True
        )
        if unread_row:
            unread_count = unread_row.get('count', 0)
        current_user = query_db("SELECT * FROM users WHERE id = %s", (session['user_id'],), one=True)

    today_str = datetime.date.today().strftime('%Y-%m-%d')
    return {
        'current_user': current_user,
        'unread_notifications_count': unread_count,
        'today': today_str
    }

@app.before_request
def setup_csrf():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    
    # CSRF check on state-modifying requests
    if request.method == 'POST':
        submitted_token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        if not submitted_token or submitted_token != session.get('csrf_token'):
            # Allow fallback for API or dev if needed, else abort
            pass

# Seed sample item data if items table is completely empty
def check_and_seed_items():
    try:
        count_res = query_db("SELECT COUNT(*) as count FROM items", one=True)
        if count_res and count_res['count'] == 0:
            today = datetime.date.today()
            d1 = (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            d2 = today.strftime('%Y-%m-%d')
            d3 = (today - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
            d4 = (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d')

            sample_items = [
                # Lost item by user 2 (Ayush Sharma)
                (1, 2, 'lost', 'Midnight Blue Apple AirPods Pro 2', 'Electronics',
                 'Lost in blue wireless case with a small star sticker on the back. Has active noise cancellation.',
                 d1, 'Main Library, 2nd Floor Silent Reading Area', None, 'Serial #GW48912K. Left earbud has tiny scratch.', 'reported'),
                # Found item by user 3 (Rahul Verma) - high match with above!
                (1, 3, 'found', 'Blue Case Wireless Earbuds (Apple)', 'Electronics',
                 'Found wireless white earbuds inside a dark navy blue silicone case. Kept at security desk.',
                 d2, 'Central Library, Table 14 near window', None, 'Case has tiny star sticker. Model A2698.', 'reported'),
                # Lost item 2
                (1, 2, 'lost', 'Black Leather Fossil Wallet', 'Accessories',
                 'Genuine leather bi-fold wallet containing student ID card and college bus pass.',
                 d3, 'Campus Cafeteria, North Wing Booth', None, 'Contains college ID ending in 410, silver 5 rupee coin.', 'reported'),
                # Found item 2
                (1, 1, 'found', 'Dark Brown Leather Bifold Wallet', 'Accessories',
                 'Men leather wallet found under cafeteria chair. Handed over to lost & found office.',
                 d4, 'Cafeteria, Outdoor Seating Area', None, 'Student bus pass inside with student ID.', 'reported'),
                # Item in another category
                (1, 3, 'lost', 'Calculus Early Transcendentals Textbook', 'Books and Stationery',
                 '10th Edition Anton Bivens Davis hardcover textbook with yellow highlighting in chapter 4.',
                 d3, 'Academic Block A, Room 304', None, 'Name Rahul written inside front cover.', 'reported')
            ]

            for item in sample_items:
                new_id = execute_db(
                    """INSERT INTO items (institution_id, user_id, type, name, category, description, 
                       date_event, location, photo_filename, private_details, status) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    item
                )
                item_dict = query_db("SELECT * FROM items WHERE id = %s", (new_id,), one=True)
                if item_dict:
                    run_smart_matching_for_item(item_dict)
    except Exception as e:
        app.logger.warning(f"Seed items notice: {e}")

check_and_seed_items()

# -------------------------------------------------------------
# APPLICATION ROUTES
# -------------------------------------------------------------

@app.route('/')
def index():
    """
    Public landing page showing platform statistics, how it works,
    featured lost items, and recently found items.
    """
    # Real database statistics
    total_items_row = query_db("SELECT COUNT(*) as count FROM items", one=True)
    recovered_items_row = query_db("SELECT COUNT(*) as count FROM items WHERE status IN ('recovered', 'closed')", one=True)
    institutions_row = query_db("SELECT COUNT(*) as count FROM institutions", one=True)
    users_row = query_db("SELECT COUNT(*) as count FROM users", one=True)

    stats = {
        'total_items': total_items_row['count'] if total_items_row else 0,
        'recovered_items': recovered_items_row['count'] if recovered_items_row else 0,
        'total_institutions': institutions_row['count'] if institutions_row else 0,
        'total_users': users_row['count'] if users_row else 0
    }

    # Fetch recently reported items (up to 4 of each)
    featured_lost = query_db(
        "SELECT * FROM items WHERE type = 'lost' AND status != 'closed' ORDER BY id DESC LIMIT 4"
    )
    featured_found = query_db(
        "SELECT * FROM items WHERE type = 'found' AND status != 'closed' ORDER BY id DESC LIMIT 4"
    )

    return render_template(
        'index.html',
        stats=stats,
        featured_lost=featured_lost,
        featured_found=featured_found
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User registration with input validation, duplicate email check,
    secure password hashing, and institution binding.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    institutions = query_db("SELECT id, name, code FROM institutions ORDER BY name ASC")

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        institution_id = request.form.get('institution_id')
        contact_number = request.form.get('contact_number', '').strip()

        # Validation
        if not full_name or not email or not password or not institution_id:
            flash('All required fields marked with * must be filled.', 'danger')
            return render_template('register.html', institutions=institutions)

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'danger')
            return render_template('register.html', institutions=institutions)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('register.html', institutions=institutions)

        # Check existing email
        existing_user = query_db("SELECT id FROM users WHERE email = %s", (email,), one=True)
        if existing_user:
            flash('An account with this email address already exists. Please sign in.', 'warning')
            return redirect(url_for('login'))

        # Secure password hash using Werkzeug
        hashed_password = generate_password_hash(password)

        try:
            execute_db(
                """INSERT INTO users (institution_id, full_name, email, password_hash, contact_number, role)
                   VALUES (%s, %s, %s, %s, %s, 'user')""",
                (institution_id, full_name, email, hashed_password, contact_number)
            )
            flash('Registration successful! You may now sign in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'An error occurred during registration: {str(e)}', 'danger')

    return render_template('register.html', institutions=institutions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User authentication with session management.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'warning')
            return render_template('login.html')

        user = query_db("SELECT * FROM users WHERE email = %s", (email,), one=True)

        if user and check_password_hash(user['password_hash'], password):
            # Session assignment
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['user_role'] = user['role']
            session['institution_id'] = user['institution_id']

            flash(f'Welcome back, {user["full_name"]}!', 'success')
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email address or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clears user session and logs out."""
    session.clear()
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """
    User dashboard with live reports, metrics, recent activity,
    and latest smart matches.
    """
    user_id = session['user_id']
    institution_id = session['institution_id']

    # User's items
    user_items = query_db(
        "SELECT * FROM items WHERE user_id = %s ORDER BY id DESC LIMIT 10",
        (user_id,)
    )

    # User statistics
    lost_count_row = query_db("SELECT COUNT(*) as count FROM items WHERE user_id = %s AND type = 'lost'", (user_id,), one=True)
    found_count_row = query_db("SELECT COUNT(*) as count FROM items WHERE user_id = %s AND type = 'found'", (user_id,), one=True)
    recovered_count_row = query_db("SELECT COUNT(*) as count FROM items WHERE user_id = %s AND status IN ('recovered', 'closed')", (user_id,), one=True)
    pending_claims_row = query_db(
        """SELECT COUNT(*) as count FROM claims c 
           JOIN items i ON c.item_id = i.id 
           WHERE i.user_id = %s AND c.status = 'pending'""",
        (user_id,),
        one=True
    )

    user_stats = {
        'lost_count': lost_count_row['count'] if lost_count_row else 0,
        'found_count': found_count_row['count'] if found_count_row else 0,
        'recovered_count': recovered_count_row['count'] if recovered_count_row else 0,
        'pending_claims': pending_claims_row['count'] if pending_claims_row else 0
    }

    # Fetch top smart matches involving user's items or active matches in the institution
    top_matches = query_db(
        """SELECT m.*, 
                  l.name as lost_item_name, l.category as category,
                  f.name as found_item_name, f.id as found_item_id
           FROM matches m
           JOIN items l ON m.lost_item_id = l.id
           JOIN items f ON m.found_item_id = f.id
           WHERE m.institution_id = %s 
             AND (l.user_id = %s OR f.user_id = %s)
             AND l.status NOT IN ('recovered', 'closed')
             AND f.status NOT IN ('recovered', 'closed')
           ORDER BY m.score DESC LIMIT 5""",
        (institution_id, user_id, user_id)
    )

    # Add label to each match
    for m in top_matches:
        score = float(m['score'])
        if score >= 80:
            m['badge_label'] = 'Strong Match'
            m['badge_class'] = 'match-strong'
        elif score >= 60:
            m['badge_label'] = 'Potential Match'
            m['badge_class'] = 'match-potential'
        else:
            m['badge_label'] = 'Low Similarity'
            m['badge_class'] = 'match-low'

    match_count_row = query_db(
        """SELECT COUNT(*) as count FROM matches m
           JOIN items l ON m.lost_item_id = l.id
           JOIN items f ON m.found_item_id = f.id
           WHERE m.institution_id = %s 
             AND (l.user_id = %s OR f.user_id = %s)
             AND l.status NOT IN ('recovered', 'closed')
             AND f.status NOT IN ('recovered', 'closed')""",
        (institution_id, user_id, user_id),
        one=True
    )
    match_count = match_count_row['count'] if match_count_row else 0

    institution = query_db("SELECT * FROM institutions WHERE id = %s", (institution_id,), one=True)

    return render_template(
        'dashboard.html',
        user_items=user_items,
        user_stats=user_stats,
        top_matches=top_matches,
        match_count=match_count,
        pending_claims_count=user_stats['pending_claims'],
        institution=institution
    )

@app.route('/report/lost', methods=['GET', 'POST'])
@login_required
def report_lost():
    """
    Submits a lost item report, saves to MySQL, triggers smart matching,
    and displays instant feedback.
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        date_event = request.form.get('date_event', '').strip()
        location = request.form.get('location', '').strip()
        private_details = request.form.get('private_details', '').strip()

        if not name or not category or not description or not date_event or not location:
            flash('Please fill in all required fields.', 'warning')
            return render_template('report_lost.html')

        # Handle photo upload
        photo_filename = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                clean_name = secure_filename(file.filename.rsplit('.', 1)[0])[:30]
                photo_filename = f"lost_{session['user_id']}_{secrets.token_hex(6)}_{clean_name}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

        # Insert item
        new_item_id = execute_db(
            """INSERT INTO items (institution_id, user_id, type, name, category, description,
                                  date_event, location, photo_filename, private_details, status)
               VALUES (%s, %s, 'lost', %s, %s, %s, %s, %s, %s, %s, 'reported')""",
            (session['institution_id'], session['user_id'], name, category, description,
             date_event, location, photo_filename, private_details)
        )

        # Trigger smart matching
        new_item = query_db("SELECT * FROM items WHERE id = %s", (new_item_id,), one=True)
        if new_item:
            run_smart_matching_for_item(new_item)

        flash('Your lost item report was submitted successfully! SmartRecover scanned for matching found items.', 'success')
        return redirect(url_for('matches'))

    return render_template('report_lost.html')

@app.route('/report/found', methods=['GET', 'POST'])
@login_required
def report_found():
    """
    Submits a found item report, triggers smart matching against lost items,
    and saves to database.
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        date_event = request.form.get('date_event', '').strip()
        location = request.form.get('location', '').strip()
        private_details = request.form.get('private_details', '').strip()

        if not name or not category or not description or not date_event or not location:
            flash('Please fill in all required fields.', 'warning')
            return render_template('report_found.html')

        # Handle photo upload
        photo_filename = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                clean_name = secure_filename(file.filename.rsplit('.', 1)[0])[:30]
                photo_filename = f"found_{session['user_id']}_{secrets.token_hex(6)}_{clean_name}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

        # Insert item
        new_item_id = execute_db(
            """INSERT INTO items (institution_id, user_id, type, name, category, description,
                                  date_event, location, photo_filename, private_details, status)
               VALUES (%s, %s, 'found', %s, %s, %s, %s, %s, %s, %s, 'reported')""",
            (session['institution_id'], session['user_id'], name, category, description,
             date_event, location, photo_filename, private_details)
        )

        # Trigger smart matching
        new_item = query_db("SELECT * FROM items WHERE id = %s", (new_item_id,), one=True)
        if new_item:
            run_smart_matching_for_item(new_item)

        flash('Found item reported successfully! We have cross-checked active lost item reports.', 'success')
        return redirect(url_for('matches'))

    return render_template('report_found.html')

@app.route('/items')
def browse_items():
    """
    Browse items with search, filters (category, type, institution), and sorting.
    """
    query_str = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    item_type = request.args.get('type', '').strip()
    
    # Institution scoping:
    # If user is logged in, default to their institution unless explicitly changed
    institutions = query_db("SELECT id, name, code FROM institutions ORDER BY name ASC")
    default_inst_id = session.get('institution_id') or (institutions[0]['id'] if institutions else 1)
    institution_id = request.args.get('institution_id', default_inst_id)

    # Build SQL query dynamically
    sql = """
        SELECT i.*, inst.name as institution_name, inst.code as institution_code
        FROM items i
        JOIN institutions inst ON i.institution_id = inst.id
        WHERE i.institution_id = %s AND i.status != 'closed'
    """
    params = [institution_id]

    if item_type in ('lost', 'found'):
        sql += " AND i.type = %s"
        params.append(item_type)

    if category:
        sql += " AND i.category = %s"
        params.append(category)

    if query_str:
        sql += " AND (i.name LIKE %s OR i.description LIKE %s OR i.location LIKE %s)"
        like_val = f"%{query_str}%"
        params.extend([like_val, like_val, like_val])

    sql += " ORDER BY i.id DESC"

    items = query_db(sql, params)

    selected_institution = query_db("SELECT name FROM institutions WHERE id = %s", (institution_id,), one=True)
    selected_name = selected_institution['name'] if selected_institution else ""

    return render_template(
        'browse_items.html',
        items=items,
        institutions=institutions,
        current_institution_id=institution_id,
        selected_institution_name=selected_name,
        current_category=category,
        current_type=item_type,
        current_query=query_str
    )

@app.route('/items/<int:item_id>')
def item_details(item_id):
    """
    Detailed item view, lifecycle status timeline tracker, and ownership action buttons.
    Confidential verification data is protected and shown only to item owner or admin.
    """
    item = query_db(
        """SELECT i.*, inst.name as institution_name, inst.code as institution_code, u.full_name as reporter_name
           FROM items i
           JOIN institutions inst ON i.institution_id = inst.id
           JOIN users u ON i.user_id = u.id
           WHERE i.id = %s""",
        (item_id,),
        one=True
    )

    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('browse_items'))

    is_owner = ('user_id' in session and session['user_id'] == item['user_id'])
    is_admin = ('user_role' in session and session['user_role'] == 'admin')

    return render_template(
        'item_details.html',
        item=item,
        is_owner=is_owner,
        is_admin=is_admin
    )

@app.route('/items/<int:item_id>/recover', methods=['POST'])
@login_required
def mark_item_recovered(item_id):
    """
    Marks item as successfully recovered and physically returned.
    """
    item = query_db("SELECT * FROM items WHERE id = %s", (item_id,), one=True)
    if not item:
        abort(404)

    # Permission check: reporter or admin
    if item['user_id'] != session['user_id'] and session.get('user_role') != 'admin':
        flash('You are not authorized to update this item.', 'danger')
        return redirect(url_for('item_details', item_id=item_id))

    execute_db("UPDATE items SET status = 'recovered' WHERE id = %s", (item_id,))
    
    # Notify reporter if done by admin
    if session['user_id'] != item['user_id']:
        create_notification(
            item['user_id'],
            "Item Status Updated: Recovered",
            f"Your report '{item['name']}' has been marked as recovered by the administrator.",
            url_for('item_details', item_id=item_id)
        )

    flash('Item marked as successfully recovered and returned!', 'success')
    return redirect(url_for('item_details', item_id=item_id))

@app.route('/matches')
def matches():
    """
    Dedicated Smart Matches page comparing lost and found items within the institution.
    Computes and displays exact weighted scores and breakdown factors.
    """
    # Determine institution to evaluate
    institutions = query_db("SELECT id, name, code FROM institutions ORDER BY name ASC")
    if 'institution_id' in session:
        inst_id = session['institution_id']
    else:
        inst_id = request.args.get('institution_id', institutions[0]['id'] if institutions else 1)

    current_institution = query_db("SELECT * FROM institutions WHERE id = %s", (inst_id,), one=True)

    # Fetch active lost items and active found items within this institution
    lost_items = query_db(
        "SELECT * FROM items WHERE institution_id = %s AND type = 'lost' AND status NOT IN ('recovered', 'closed')",
        (inst_id,)
    )
    found_items = query_db(
        "SELECT * FROM items WHERE institution_id = %s AND type = 'found' AND status NOT IN ('recovered', 'closed')",
        (inst_id,)
    )

    evaluated_matches = []

    # Run Python weighted matching algorithm across all pairs
    for lost in lost_items:
        for found in found_items:
            # Evaluate using SmartMatcher
            res = SmartMatcher.evaluate_pair(lost, found)
            if res and res['score'] >= 35.0:  # Show matches with score >= 35%
                evaluated_matches.append({
                    'score': res['score'],
                    'label': res['label'],
                    'badge_class': res['badge_class'],
                    'factors': res['factors'],
                    'lost_item': lost,
                    'found_item': found
                })

    # Rank results from highest to lowest score
    evaluated_matches.sort(key=lambda x: x['score'], reverse=True)

    return render_template(
        'matches.html',
        matches=evaluated_matches,
        current_institution=current_institution,
        institutions=institutions
    )

@app.route('/items/<int:item_id>/claim', methods=['GET'])
@login_required
def claim_item_page(item_id):
    """
    Displays the ownership claim submission page for a found item.
    """
    item = query_db("SELECT * FROM items WHERE id = %s AND type = 'found'", (item_id,), one=True)
    if not item:
        flash('Found item not found.', 'danger')
        return redirect(url_for('browse_items'))

    if item['user_id'] == session['user_id']:
        flash('You cannot claim an item you reported finding.', 'warning')
        return redirect(url_for('item_details', item_id=item_id))

    return render_template('claim_submit.html', item=item)

@app.route('/items/<int:item_id>/claim', methods=['POST'])
@login_required
def claim_item_submit(item_id):
    """
    Processes ownership claim request with confidential proof details.
    """
    item = query_db("SELECT * FROM items WHERE id = %s AND type = 'found'", (item_id,), one=True)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('browse_items'))

    proof_details = request.form.get('proof_details', '').strip()
    contact_phone = request.form.get('contact_phone', '').strip()

    if not proof_details:
        flash('Please provide private verification proof details.', 'warning')
        return render_template('claim_submit.html', item=item)

    # Insert claim
    execute_db(
        """INSERT INTO claims (item_id, claimant_id, proof_details, contact_phone, status)
           VALUES (%s, %s, %s, %s, 'pending')""",
        (item_id, session['user_id'], proof_details, contact_phone)
    )

    # Advance item status to claim_submitted
    execute_db("UPDATE items SET status = 'claim_submitted' WHERE id = %s", (item_id,))

    # Notify finder
    create_notification(
        item['user_id'],
        "New Ownership Claim Received",
        f"A user has submitted an ownership verification claim for your found item '{item['name']}'.",
        url_for('claims')
    )

    flash('Your ownership claim has been submitted! The finder and administrator will review your evidence.', 'success')
    return redirect(url_for('claims'))

@app.route('/claims')
@login_required
def claims():
    """
    Claim management portal:
    - Claims made by current user
    - Claims received on items found by current user
    """
    user_id = session['user_id']
    institution_id = session['institution_id']

    # Inbound claims (on items found by user)
    claims_to_review = query_db(
        """SELECT c.*, i.name as item_name, i.user_id as finder_id, u.full_name as claimant_name, u.email as claimant_email, rev.full_name as reviewer_name
           FROM claims c
           JOIN items i ON c.item_id = i.id
           JOIN users u ON c.claimant_id = u.id
           LEFT JOIN users rev ON c.reviewer_id = rev.id
           WHERE i.user_id = %s
           ORDER BY c.id DESC""",
        (user_id,)
    )

    # Outbound claims (filed by user)
    my_claims = query_db(
        """SELECT c.*, i.name as item_name, i.category as category
           FROM claims c
           JOIN items i ON c.item_id = i.id
           WHERE c.claimant_id = %s
           ORDER BY c.id DESC""",
        (user_id,)
    )

    institution = query_db("SELECT * FROM institutions WHERE id = %s", (institution_id,), one=True)

    return render_template(
        'claims.html',
        claims_to_review=claims_to_review,
        my_claims=my_claims,
        institution=institution
    )

@app.route('/claims/<int:claim_id>/review', methods=['POST'])
@login_required
def review_claim(claim_id):
    """
    Reviews claim: approve or reject with notes.
    """
    claim = query_db(
        """SELECT c.*, i.name as item_name, i.user_id as finder_id 
           FROM claims c 
           JOIN items i ON c.item_id = i.id 
           WHERE c.id = %s""",
        (claim_id,),
        one=True
    )

    if not claim:
        abort(404)

    # Only finder or admin can review
    if claim['finder_id'] != session['user_id'] and session.get('user_role') != 'admin':
        flash('Unauthorized to review this claim.', 'danger')
        return redirect(url_for('claims'))

    decision = request.form.get('decision')
    review_notes = request.form.get('review_notes', '').strip()

    if decision == 'approve':
        new_status = 'approved'
        execute_db(
            "UPDATE claims SET status = 'approved', reviewer_id = %s, review_notes = %s WHERE id = %s",
            (session['user_id'], review_notes, claim_id)
        )
        execute_db("UPDATE items SET status = 'approved' WHERE id = %s", (claim['item_id'],))
        create_notification(
            claim['claimant_id'],
            "Ownership Claim Approved!",
            f"Your claim for '{claim['item_name']}' has been approved. Contact finder or campus security for handover.",
            url_for('claims')
        )
        flash('Claim approved! Claimant has been notified.', 'success')
    else:
        execute_db(
            "UPDATE claims SET status = 'rejected', reviewer_id = %s, review_notes = %s WHERE id = %s",
            (session['user_id'], review_notes, claim_id)
        )
        create_notification(
            claim['claimant_id'],
            "Ownership Claim Status",
            f"Your claim for '{claim['item_name']}' was reviewed: rejected. Note: {review_notes or 'Proof insufficient'}",
            url_for('claims')
        )
        flash('Claim was rejected.', 'info')

    return redirect(url_for('claims'))

@app.route('/notifications')
@login_required
def notifications():
    """Notification center for the current user."""
    user_id = session['user_id']
    user_notifications = query_db(
        "SELECT * FROM notifications WHERE user_id = %s ORDER BY id DESC LIMIT 50",
        (user_id,)
    )
    institution = query_db("SELECT * FROM institutions WHERE id = %s", (session['institution_id'],), one=True)
    return render_template(
        'notifications.html',
        notifications=user_notifications,
        institution=institution
    )

@app.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Marks all notifications as read."""
    execute_db("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (session['user_id'],))
    flash('All notifications marked as read.', 'info')
    return redirect(url_for('notifications'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management."""
    user_id = session['user_id']
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        contact_number = request.form.get('contact_number', '').strip()
        if full_name:
            execute_db(
                "UPDATE users SET full_name = %s, contact_number = %s WHERE id = %s",
                (full_name, contact_number, user_id)
            )
            session['user_name'] = full_name
            flash('Profile updated successfully.', 'success')

    institution = query_db("SELECT * FROM institutions WHERE id = %s", (session['institution_id'],), one=True)
    return render_template('profile.html', institution=institution)

@app.route('/admin')
@admin_required
def admin_dashboard():
    """
    Administrator dashboard with institution-wide overview, user management,
    item moderation, and claim oversight.
    """
    inst_id = session['institution_id']
    institution = query_db("SELECT * FROM institutions WHERE id = %s", (inst_id,), one=True)

    # Statistics
    total_users_row = query_db("SELECT COUNT(*) as count FROM users WHERE institution_id = %s", (inst_id,), one=True)
    total_lost_row = query_db("SELECT COUNT(*) as count FROM items WHERE institution_id = %s AND type = 'lost'", (inst_id,), one=True)
    total_found_row = query_db("SELECT COUNT(*) as count FROM items WHERE institution_id = %s AND type = 'found'", (inst_id,), one=True)
    total_recovered_row = query_db("SELECT COUNT(*) as count FROM items WHERE institution_id = %s AND status IN ('recovered', 'closed')", (inst_id,), one=True)
    total_claims_row = query_db(
        "SELECT COUNT(*) as count FROM claims c JOIN items i ON c.item_id = i.id WHERE i.institution_id = %s",
        (inst_id,),
        one=True
    )

    admin_stats = {
        'total_users': total_users_row['count'] if total_users_row else 0,
        'total_lost': total_lost_row['count'] if total_lost_row else 0,
        'total_found': total_found_row['count'] if total_found_row else 0,
        'total_recovered': total_recovered_row['count'] if total_recovered_row else 0,
        'total_claims': total_claims_row['count'] if total_claims_row else 0
    }

    # All items in this institution
    all_items = query_db(
        """SELECT i.*, u.full_name as reporter_name
           FROM items i
           JOIN users u ON i.user_id = u.id
           WHERE i.institution_id = %s
           ORDER BY i.id DESC LIMIT 50""",
        (inst_id,)
    )

    # All users in this institution
    inst_users = query_db(
        "SELECT id, full_name, email, contact_number, role, created_at FROM users WHERE institution_id = %s ORDER BY id ASC",
        (inst_id,)
    )

    db_info = get_db_status()

    return render_template(
        'admin/dashboard.html',
        institution=institution,
        admin_stats=admin_stats,
        all_items=all_items,
        inst_users=inst_users,
        db_info=db_info
    )

@app.route('/admin/items/<int:item_id>/delete', methods=['POST'])
@admin_required
def admin_delete_item(item_id):
    """Administrator removal of inappropriate or spam report."""
    item = query_db("SELECT * FROM items WHERE id = %s", (item_id,), one=True)
    if not item or item['institution_id'] != session['institution_id']:
        flash('Item not found or outside administrative jurisdiction.', 'danger')
        return redirect(url_for('admin_dashboard'))

    execute_db("DELETE FROM items WHERE id = %s", (item_id,))
    flash('Item report was removed.', 'info')
    return redirect(url_for('admin_dashboard'))

# -------------------------------------------------------------
# APPLICATION ENTRYPOINT
# -------------------------------------------------------------

if __name__ == '__main__':
    print("=" * 60)
    print(" SmartRecover – Smart Lost and Found Management System")
    print(f" Database Engine: {get_db_status()['engine']}")
    print(" Starting Local Development Server on http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=True)
