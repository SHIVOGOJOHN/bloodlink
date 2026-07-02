I'm building "BloodLink" — a blood donation coordination platform for a 5-day 
school project (Kenya-based). Build this as a Flask web application. Follow 
these constraints exactly; do not suggest a mobile app, Daraja/M-Pesa 
integration, or paid third-party services.

TECH STACK (strict — no substitutions):
- Backend: Python 3, Flask, Flask-Blueprints for modular routes
- Database: MySQL + SQLAlchemy ORM
- Auth: Google-auth (role-based: donor, hospital_staff, bloodbank_staff, admin)
- Forms: Flask-WTF with CSRF protection and server-side validation
- Frontend: Jinja2 templates + Bootstrap 5 + vanilla JS (no React/Vue)
- Maps: Leaflet.js with a static Kenya counties GeoJSON file
- Charts: Chart.js
- ML: scikit-learn, RandomForestRegressor
- USSD/SMS: Africa's Talking Python SDK, sandbox mode only
  (account.africastalking.com/apps/sandbox — free, no business registration)
- Email: Flask-Mail via Gmail SMTP app password (real, free notification channel)
- Deployment target: Render.com free tier

PROJECT STRUCTURE:
Set up a Flask app factory pattern with blueprints: /donor, /hospital, 
/bloodbank, /admin, /ussd, /api. Config should support separate 
development/production settings and read secrets (Gmail app password, 
Africa's Talking API key/username) from environment variables — never 
hardcode credentials.

DATA MODEL (data-minimal by design — this is a compliance requirement, 
not a style choice):
- Donor: id, name, phone, county, blood_type, last_donation_date, 
  eligibility_status (computed field, not stored raw), consent_given (bool), 
  consent_timestamp, created_at
- Hospital: id, name, county, contact_phone
- BloodBank: id, name, county, stock levels per blood type, last_updated
- BloodRequest: id, hospital_id, blood_type, units_needed, urgency_level, 
  status, created_at
- Do NOT create any field for medical history, diagnoses, ID numbers, or 
  home addresses. County-level location only.
- Every donor-facing form must include a consent checkbox before submission 
  and link to a one-page Data Policy explaining retention and deletion rights.

CORE FEATURE 1 — Donor Portal:
Registration form (name, phone, county, blood type, last donation date, 
consent checkbox). Dashboard showing: eligibility countdown (90-day rule), 
nearby active blood requests filtered by county, personal donation history, 
simple achievement badges (e.g. "First Donation", "3+ Donations").

CORE FEATURE 2 — Hospital Dashboard:
Hospital staff can view blood bank inventory, submit an emergency blood 
request (blood type, units, urgency level), view a list of matched 
eligible donors for their request, and mark a donation as confirmed/fulfilled.

CORE FEATURE 3 — Blood Bank Dashboard:
Shows current stock per blood type, expiry date tracking, and incoming 
requests from hospitals with an accept/reject/fulfill workflow.

CORE FEATURE 4 — Matching Engine:
Simple, explainable scoring — no black-box logic. Given a BloodRequest:
1. Filter donors where blood_type is compatible (implement standard donor 
   compatibility rules, e.g. O- is universal donor)
2. Filter donors where last_donation_date is more than 90 days ago
3. Rank remaining donors by a county-distance lookup table (static dict of 
   approximate distances between Kenyan counties — not real geocoding)
4. Return ranked list with a visible breakdown of why each donor matched 
   (compatible type + eligible + distance score) — judges should be able 
   to see the logic, not just a black-box score

CORE FEATURE 5 — National Monitoring Map:
Leaflet map of Kenya counties, colored by blood bank stock level 
(green = sufficient, yellow = low, red = critical) based on BloodBank 
stock data. Clicking a county shows a popup with stock breakdown by type.

CORE FEATURE 6 — AI Demand Prediction Module:
Generate synthetic historical demand data with DELIBERATE realistic 
structure (not pure random) — weekday vs weekend variation, holiday 
spikes, seasonal patterns. Train a RandomForestRegressor to predict 
blood demand per county/blood-type over the next 48 hours using 
features: day_of_week, is_holiday, county, blood_type, previous_demand. 
Display predictions on the admin dashboard with a clear label: 
"Illustrative forecast based on synthetic training data — demonstrates 
the pipeline that would connect to real hospital data in production." 
Do not present output as medically authoritative.

CORE FEATURE 7 — USSD via Africa's Talking Sandbox:
Build a Flask route (/ussd) implementing the Africa's Talking USSD 
callback protocol (session_id, phone_number, text params; return 
CON/END-prefixed responses). Menu: 1) Register as donor 2) Check 
eligibility 3) View nearby blood requests 4) Find nearest blood bank. 
Use the africastalking Python SDK conventions for building the response 
string correctly.

CORE FEATURE 8 — SMS Notifications via Africa's Talking Sandbox:
When a new emergency BloodRequest is created, send an SMS via the 
africastalking SDK (sandbox mode) to matched eligible donors, and also 
send a real email via Flask-Mail as a backup/parallel channel. Log all 
sent notifications to a Notification table (recipient, channel, message, 
status, timestamp) visible on the admin dashboard.

SECURITY/COMPLIANCE:
- Hash all passwords with werkzeug.security
- CSRF protection on every form
- Role-based access control decorators for each blueprint
- Rate-limit the /ussd and SMS-triggering endpoints to prevent abuse
- Include a /data-policy route with a plain-language statement referencing 
  Kenya's Data Protection Act, 2019 — data minimization, consent, and 
  retention/deletion terms

Start by scaffolding the Flask app factory, config, and folder structure. 
Then build models.py with SQLAlchemy models for the data model above. Wait 
for my confirmation before moving to routes/templates so I can review the 
structure first.

ADDITIONAL FEATURE — Transport Reimbursement (M-Pesa via Daraja B2C Sandbox):

This is NOT payment for blood — it is a flat, capped reimbursement for 
verified travel costs incurred while donating. Frame all code, comments, 
and UI copy accordingly. Do not implement anything that scales the amount 
to blood volume or donation frequency.

DATA MODEL ADDITION:
- ReimbursementRequest: id, donor_id, donation_id (FK to a confirmed 
  donation record, required — no request without a confirmed donation), 
  amount (fixed constant, not user-editable, e.g. KES 300), status 
  (pending/approved/rejected/disbursed), requested_at, approved_by 
  (hospital/bloodbank staff user id), approved_at, mpesa_transaction_id, 
  disbursed_at
- Enforce at the model/service layer: a donor cannot have more than one 
  reimbursement per confirmed donation, and confirmed donations still 
  respect the 90-day eligibility rule regardless of reimbursement status

WORKFLOW:
1. Donor's confirmed donation record (set by hospital/bloodbank staff) 
   unlocks a "Request transport reimbursement" action on the donor dashboard
2. Request goes to a staff approval queue (hospital or admin role) — 
   nothing disburses automatically without human approval
3. On approval, trigger a Daraja B2C sandbox call to disburse the fixed 
   amount to the donor's registered phone number
4. Log the full Daraja response (including sandbox transaction ID, 
   result code, result description) to the ReimbursementRequest record
5. Show disbursement status on both the donor dashboard and an admin 
   reimbursements log page

DARAJA INTEGRATION SPECIFICS:
- Use Safaricom's Daraja API, SANDBOX environment only 
  (sandbox.safaricom.co.ke), B2C product
- Use an individual developer account on developer.safaricom.co.ke — 
  no business KYC needed for sandbox
- Read Consumer Key, Consumer Secret, Initiator Name, and Security 
  Credential from environment variables, using the standard sandbox test 
  credentials from the Daraja test_credentials page — never hardcode
- Implement OAuth token generation (Daraja requires a bearer token before 
  any B2C call), then the B2C request itself with CommandID 
  "BusinessPayment" (this is a reimbursement, not a salary or promotion 
  payment — use the correct CommandID semantically)
- Implement the required ResultURL and QueueTimeOutURL callback routes 
  (e.g. /mpesa/b2c/result and /mpesa/b2c/timeout) that Daraja will POST 
  to asynchronously — the initial B2C call only returns an acknowledgment, 
  the actual result arrives via callback, so disbursed_at should only be 
  set when the ResultURL callback confirms success
- Handle and log failure result codes distinctly from success (e.g. 
  insufficient sandbox float, invalid phone format) so the admin log 
  shows real failure states, not just success

UI/COPY REQUIREMENTS:
- Every screen referencing this feature must use the phrase "transport 
  reimbursement," never "payment for blood" or "donation fee"
- Include a visible note wherever this feature appears: "Reimbursement 
  uses Safaricom's Daraja B2C sandbox for demonstration. Production 
  deployment would require a registered business shortcode and 
  Safaricom's go-live approval process."
- The reimbursement amount must be displayed as a fixed, non-editable 
  value on both the request form and approval screen

Wire this in as a new blueprint (/reimbursement) following the same app 
factory pattern as the rest of the app. Wait for my confirmation before 
generating code, same as before — I want to review the model and workflow 
structure first.

