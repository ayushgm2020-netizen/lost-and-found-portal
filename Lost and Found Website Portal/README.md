# SmartRecover – Smart Lost and Found Management System

> **Tagline:** *"Lost Today, Found Tomorrow."*  
> **Architecture:** Multi-Institution Full-Stack Web Application  
> **Tech Stack:** Python 3.11+, Flask, MySQL / SQLite Unified DB Engine, HTML5, CSS3, Vanilla JavaScript, Jinja2 Templates

---

## 🌟 1. Project Overview

**SmartRecover** is a centralized, multi-institution lost and found management platform designed to connect people who have lost belongings with those who have found them. 

Unlike traditional bulletin boards or static listings, SmartRecover features a **Python-powered Smart Matching Engine** that automatically calculates mathematical similarity scores between lost and found reports within the same institution, ranking possible matches and giving clear factor breakdowns.

### Key Pillars:
1. **Multi-Institution Logical Isolation:** Students and staff only see items and receive matches from their registered college or university campus.
2. **Python Smart Matching Engine:** Transparent 5-factor weighted algorithm comparing Item Title & Keywords (30%), Category (20%), Description (25%), Location (15%), and Date Proximity (10%).
3. **Secure Ownership Verification:** Private serial numbers, lock screens, and hidden details remain completely confidential and are only visible to authorized reviewers during claim evaluation.
4. **End-to-End Recovery Tracking:** Visual lifecycle tracker (`Reported` ➔ `Match Found` ➔ `Claim Submitted` ➔ `Under Verification` ➔ `Approved` ➔ `Recovered`).
5. **Role-Based Access Control:** Distinct user dashboard and institution-scoped administrative console.

---

## 🎨 2. UI/UX Design System

Designed with a modern SaaS aesthetic inspired by **Linear**, **Stripe**, and premium university enterprise software:
- **Primary Navy:** `#142B4A`
- **Royal Blue Accent:** `#2563EB`
- **Accent Light Blue:** `#60A5FA` / `#EFF6FF`
- **Background:** `#F8FAFC`
- **Card Surface:** `#FFFFFF` with soft shadows
- **Typography:** Inter & Plus Jakarta Sans with crisp font metrics
- **Icons:** Lucide Icons (CDN embedded)

---

## 📁 3. Project Directory Structure

```
Lost and Found Website Portal/
├── app.py                     # Main Flask application & routes
├── config.py                  # Environment & Flask configuration
├── requirements.txt           # Python dependencies
├── .env                       # Active environment variables
├── .env.example               # Template environment configuration
├── README.md                  # Complete documentation & viva guide
│
├── database/
│   ├── schema.sql             # Full MySQL Workbench import schema & seeds
│   ├── db.py                  # Unified DB connection (MySQL with fallback)
│   └── smartrecover.db        # Auto-initialized local DB
│
├── matching/
│   ├── __init__.py            # Package initialization
│   └── matcher.py             # 5-Factor weighted Python matching algorithm
│
├── templates/                 # Jinja2 Reusable HTML Templates
│   ├── base.html              # Master layout & navigation
│   ├── index.html             # Public SaaS landing page & live stats
│   ├── login.html             # Sign in with 1-click demo helpers
│   ├── register.html          # Campus member registration
│   ├── dashboard.html         # User dashboard & metrics
│   ├── report_lost.html       # Report lost item form
│   ├── report_found.html      # Report found item form
│   ├── browse_items.html      # Search, filter, and item directory
│   ├── item_details.html      # Item details & recovery timeline
│   ├── matches.html           # Signature Smart Matches & factor gauges
│   ├── claim_submit.html      # Ownership claim submission
│   ├── claims.html            # Claims management & verification
│   ├── notifications.html     # User notifications center
│   ├── profile.html           # User profile & college affiliation
│   └── admin/
│       └── dashboard.html     # Institutional administrator dashboard
│
├── static/
│   ├── css/
│   │   └── style.css          # Design system & responsive styles
│   ├── js/
│   │   └── main.js            # Image previews, live search, modals
│   └── uploads/               # Uploaded item photographs
│
└── tests/
    └── test_smartrecover.py   # Unit tests for matching engine & routes
```

---

## ⚙️ 4. Quick Installation & Setup

### Prerequisites:
- Python 3.10 or Python 3.11+
- (Optional for development) MySQL 8.0+ or MySQL Workbench / XAMPP

### Step 1: Install Dependencies
Open your terminal in this project directory:
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment (`.env`)
The project comes pre-configured with a `.env` file. If using MySQL:
```ini
SECRET_KEY=smartrecover_local_secret_key_college_project_2026
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=smartrecover_db
FLASK_DEBUG=True
```

### Step 3: MySQL Database Setup (Optional if using MySQL)
1. Open **MySQL Workbench** or your MySQL command line.
2. Open `database/schema.sql` and execute the entire script.
3. It will create `smartrecover_db`, all 6 tables, indexes, and initial sample institutions and users.

> **💡 Zero-Friction Development Guarantee:**  
> If MySQL is not running on your machine when you launch the application, SmartRecover's intelligent database adapter (`database/db.py`) automatically falls back to a local SQLite database (`database/smartrecover.db`) with identical schema and tables! You can demonstrate the application immediately without database setup errors.

### Step 4: Run the Application
```bash
python app.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🔑 5. Pre-Configured Demo Accounts

For presentations, college demonstrations, and examiner reviews, the following sample accounts are ready to use:

| Role | Email Address | Password | Campus Affiliation |
|---|---|---|---|
| **Admin** | `admin@aiet.edu` | `password123` | Apex Institute of Engineering & Technology |
| **Student 1** | `ayush@aiet.edu` | `password123` | Apex Institute of Engineering & Technology |
| **Student 2** | `rahul@aiet.edu` | `password123` | Apex Institute of Engineering & Technology |

*(The Sign In page also provides convenient 1-click credential fill buttons for fast testing!)*

---

## 🧠 6. Python Smart Matching Engine Breakdown

The signature feature of SmartRecover is its mathematical, transparent matching algorithm located in `matching/matcher.py`:

$$\text{Total Score} = (0.30 \times \text{Name}) + (0.20 \times \text{Category}) + (0.25 \times \text{Description}) + (0.15 \times \text{Location}) + (0.10 \times \text{Date})$$

### Factor Breakdown:
1. **Item Title & Keywords (30%):** Cleans text, removes common English stopwords, and computes token overlap combined with `difflib.SequenceMatcher`.
2. **Category Alignment (20%):** 1.0 (100%) for exact match, 0.75 for hierarchical sub-category, 0.0 otherwise.
3. **Description Similarity (25%):** Analyzes feature descriptions, colors, and physical attributes.
4. **Location Proximity (15%):** Identifies campus buildings, rooms, cafeteria zones, and libraries.
5. **Date Proximity (10%):** Exponential chronological decay (e.g. 0-2 days difference = 100%, within 7 days = 75%, >30 days = 10%).

### Match Classifications:
- **80% – 100%:** `Strong Possible Match` (Green Badge)
- **60% – 79%:** `Potential Match` (Amber Badge)
- **Below 60%:** `Low Similarity` (Slate Badge)

---

## 🧪 7. Running Automated Unit Tests

To run the automated test suite verifying the matching weights, cross-institution isolation, and route integrity:
```bash
python -m unittest discover tests
```
Result:
```
......
----------------------------------------------------------------------
Ran 6 tests in 0.20s

OK
```

---

## 🎓 8. College Project Evaluation & Viva Guide

When explaining this project to professors, evaluators, or in an individual defense:
1. **Highlight the Full-Stack Integration:** Not just a frontend mock—features a genuine Flask backend, parameterized SQL queries, secure password hashing, and active session handling.
2. **Explain the Matching Algorithm:** Emphasize that it is an explainable Python weighted matching engine, avoiding black-box claims while providing students and campus security with mathematical ranking.
3. **Point Out Privacy & Verification Security:** Show how confidential serial numbers or lock-screen details are concealed from public directory cards and only revealed during authorized verification claim review.
4. **Demonstrate Institutional Boundaries:** Mention that students at "Apex Institute" never have their lost items mixed with "Metro State University", ensuring clean scalability across multiple campuses.
