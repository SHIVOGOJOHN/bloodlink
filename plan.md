# BloodLink complete build plan

This plan is the implementation contract for the project. It covers product scope, architecture, technical constraints, data model, implementation order, verification checkpoints, and deployment. Every part of the platform will be built in this order unless a blocker requires a small adjustment.

## 1. Project goal
Build a Flask-based BloodLink platform for Kenya that helps connect blood donors, hospitals, and blood banks in a fast, explainable, and privacy-conscious way. The system must support:
- donor registration and eligibility tracking
- hospital blood request creation
- blood bank inventory workflows
- explainable donor matching
- national monitoring view of stock levels
- simple AI-based demand forecasting for planning support
- USSD and SMS engagement for non-smartphone users
- transport reimbursement workflow via Daraja sandbox

## 2. Non-negotiable constraints
These are fixed and must be respected throughout the build:
- Backend: Python 3, Flask, Flask blueprints
- Database: MySQL + SQLAlchemy ORM
- Auth: email/password login, Google OAuth, role-based access
- Forms: Flask-WTF with CSRF protection and server-side validation
- Frontend: Jinja2 templates, Bootstrap 5, vanilla JS
- Maps: Leaflet.js with a static Kenya counties GeoJSON file
- Charts: Chart.js
- ML: scikit-learn, RandomForestRegressor
- USSD/SMS: Africa’s Talking sandbox only
- Email: Flask-Mail with Gmail app password
- Deployment: Render.com free tier
- UI style: follow the same minimalist, non-gradient, no-emoji pattern used in the other app
- Performance: keep the app fast and lightweight; use Flask compression if needed
- Security: treat this as sensitive health-related data and build with privacy and data minimization in mind

## 3. Product scope and success criteria
The MVP must include these core experiences:
1. Donor portal
   - registration with consent checkbox
   - eligibility countdown based on 90-day rule
   - dashboard showing active nearby blood requests
   - donation history and simple badges
2. Hospital dashboard
   - view inventory
   - create urgent blood requests
   - view matched donors
   - confirm/fulfill donations
3. Blood bank dashboard
   - manage stock by blood type
   - accept/reject/fulfill hospital requests
4. Admin dashboard
   - manage users and data visibility
   - review notifications and reimbursement requests
   - view forecasting output
5. Matching engine
   - simple, transparent scoring based on compatibility, eligibility, and approximate county distance
6. National monitoring map
   - county-level stock view with green/yellow/red status
7. AI demand module
   - illustrate planning support with synthetic historical data and a clear warning label
8. USSD and SMS flow
   - donor registration and emergency response through USSD/SMS channel
9. Transport reimbursement flow
   - donation-linked reimbursement request, staff approval, Daraja sandbox disbursement, status logging
10. Privacy and compliance page
   - plain-language data policy with consent and retention/deletion language

## 4. Architecture plan
Use a Flask app factory pattern with a modular blueprint structure.

### Recommended structure
- app/__init__.py
- app/config.py
- app/extensions.py
- app/models.py
- app/seed.py
- app/utils/
  - auth.py
  - matching.py
  - forecast.py
  - notifications.py
  - reimbursement.py
- app/blueprints/
  - auth/
  - donor/
  - hospital/
  - bloodbank/
  - admin/
  - ussd/
  - api/
  - reimbursement/
- app/templates/
  - base.html
  - auth/
  - donor/
  - hospital/
  - bloodbank/
  - admin/
  - reimbursement/
  - policy/
- app/static/
  - css/
  - js/
  - img/
  - geojson/

### Configuration strategy
- Use separate development and production config classes
- Read all secrets from environment variables
- Keep secrets out of source control
- Create an example.env file for all required variables

### Environment variables required
- MySQL connection string
- Flask secret key
- Google OAuth client ID and secret
- Gmail SMTP credentials/app password
- Africa’s Talking username and API key
- Daraja consumer key, consumer secret, initiator name, security credential
- Render production base URL where relevant

## 5. Data model plan
Keep the data model minimal and compliant.

### Core tables
- User
  - id, email, password_hash, google_id, role, full_name, phone, is_active, created_at
- Donor
  - id, user_id, name, phone, county, blood_type, last_donation_date, consent_given, consent_timestamp, created_at
- Hospital
  - id, user_id, name, county, contact_phone, created_at
- BloodBank
  - id, user_id, name, county, created_at
- BloodBankStock
  - id, blood_bank_id, blood_type, units_available, expiry_date, last_updated
- BloodRequest
  - id, hospital_id, blood_type, units_needed, urgency_level, status, created_at
- DonationRecord
  - id, donor_id, hospital_id, blood_request_id, blood_type, status, confirmed_at, confirmed_by_user_id
- Notification
  - id, recipient, channel, message, status, created_at
- ReimbursementRequest
  - id, donor_id, donation_id, amount, status, requested_at, approved_by_user_id, approved_at, mpesa_transaction_id, disbursed_at

### Data minimization rules
Do not store:
- medical history
- diagnoses
- ID numbers
- home addresses
- anything beyond the minimum required for donation coordination

### Business rules to enforce in model/service layers
- Donation eligibility is based on 90-day rule
- A donor cannot request more than one reimbursement per confirmed donation
- A confirmed donation still respects the 90-day eligibility rule regardless of reimbursement status
- Every donor-facing form must include consent and a policy link

## 6. Authentication and security plan
The auth stack must be built before any role-specific workflows.

### Authentication tasks
- create user model and role support
- implement email/password registration and login
- implement Google OAuth login flow
- implement password reset flow with email
- enforce role-based access decorators for donor, hospital, bloodbank, admin
- protect every form with CSRF
- create a secure session flow and logout handling

### Compliance and privacy tasks
- create a data policy page
- explain retention and deletion rights in plain language
- keep consent recorded at registration and on every donor-facing submission where relevant
- use secure password hashing and never store plain-text passwords
- add rate limiting for USSD and SMS-triggering endpoints

## 7. Build sequence and implementation order
This is the exact build order to follow.

### Phase 1 — Foundation and setup
Objectives:
- create the project folder structure
- set up Flask app factory
- create config classes for development and production
- initialize MySQL connection and SQLAlchemy
- create environment variable handling
- create the example.env file

Deliverables:
- working Flask app entrypoint
- config system
- database connection
- project skeleton

### Phase 2 — Core data model and seed data
Objectives:
- define all models in one pass
- create migration or table initialization flow
- create a seed script with realistic demo data
- include donors across counties, several blood types, and a few confirmed donations

Deliverables:
- working MySQL schema
- seed data for local demo

### Phase 3 — Authentication and shared UI shell
Objectives:
- build auth routes and templates
- build the base layout, navbar, flash handling, and dashboard shell
- ensure the UI matches the minimalist style from the other app
- add the policy route and consent components

Deliverables:
- login, register, logout, password reset, Google login flow
- base template for all roles
- data policy page

### Phase 4 — Role-based dashboards and CRUD flows
Objectives:
- build donor dashboard and registration workflow
- build hospital dashboard and blood request creation
- build blood bank inventory and request workflow
- build admin dashboard overview

Deliverables:
- donor registration and dashboard
- hospital request submission
- blood bank stock management
- admin control panel

### Phase 5 — Matching engine
Objectives:
- implement blood compatibility logic
- enforce 90-day eligibility filtering
- use a county-distance lookup table for ranking
- show why a donor matched

Deliverables:
- visible explainable match results for each blood request

### Phase 6 — National map and forecasting module
Objectives:
- build a Leaflet map of Kenya counties
- color counties based on stock status
- add clickable county stock breakdowns
- create synthetic historical demand data with weekday, weekend, holiday, and seasonal structure
- train a RandomForestRegressor model and display an illustrative forecast panel

Deliverables:
- stock map
- forecast view labeled as illustrative only

### Phase 7 — External integrations
Objectives:
- build the USSD callback route with proper session flow
- send SMS notifications to matched donors for emergency requests
- send email fallback notifications via Flask-Mail
- log every notification in the Notification table

Deliverables:
- working sandbox USSD flow
- email and SMS notifications
- notification log UI

### Phase 8 — Transport reimbursement workflow
Objectives:
- add donation-linked reimbursement requests
- add staff approval queue
- implement Daraja B2C sandbox request flow
- implement ResultURL and QueueTimeOutURL callbacks
- show reimbursement status in donor/admin views

Deliverables:
- reimbursement request and approval flow
- Daraja sandbox integration and callback logging

### Phase 9 — Deployment and hardening
Objectives:
- deploy the app to Render
- verify environment variables in production
- test the full end-to-end flow
- prepare fallback screenshots or recordings for demo situations

Deliverables:
- live deployment
- end-to-end demo readiness

## 8. Specific implementation notes by feature

### Donor portal
- registration form: name, phone, county, blood type, last donation date, consent checkbox
- dashboard displays eligibility countdown and relevant active requests
- show a simple donation history and achievement badges

### Hospital dashboard
- allow staff to view stock summary and submit blood requests
- show matched donors for each request with explainable reasons
- allow confirmation of fulfilled donations

### Blood bank dashboard
- manage stock by blood type and expiry date
- handle incoming hospital requests with accept/reject/fulfill actions

### Admin dashboard
- user overview
- request overview
- notification overview
- reimbursement overview
- forecasting display

### Matching engine logic
Use this order:
1. compatibility filter
2. eligibility filter
3. county-distance ranking
4. score breakdown shown to the user

### Forecasting module
- generate synthetic data with structure, not pure randomness
- use day of week, holiday flag, county, blood type, and previous demand as features
- present the output as illustrative planning support only

### USSD flow
Support a simple menu such as:
- register as donor
- check eligibility
- view nearby blood requests
- find nearest blood bank

### SMS and email
- trigger on new emergency requests
- send alerts to relevant eligible donors
- log each attempt in the notification table

### Reimbursement flow
- reimbursement is capped and fixed, not volume-based
- the request is only possible after a confirmed donation
- approval is required before any disbursement
- Daraja callbacks must be logged and reflected in the UI

## 9. Testing and verification checklist
Every phase should be verified before moving forward.

### Functional checks
- auth works for email/password and Google
- role-based access is enforced correctly
- donor registration saves consent properly
- hospital requests create matching candidates
- blood bank stock changes update correctly
- admin can view all relevant logs
- notifications are logged
- reimbursement requests follow the approval/disbursement flow

### Security checks
- no plain-text passwords
- forms include CSRF protection
- sensitive views require correct role checks
- rate limiting is active on USSD and alert-triggering routes

### Demo readiness checks
- seed data looks realistic
- matching results are understandable
- the map loads and updates correctly
- forecast panel clearly states it is illustrative
- USSD/SMS flow can be demonstrated in sandbox mode
- reimbursement flow can be demonstrated with sandbox callbacks

## 10. Risk plan and mitigation
### Highest risk areas
- external integrations: Africa’s Talking, Gmail SMTP, Daraja sandbox
- callback handling and asynchronous flows
- production environment variables and Render hosting

### Mitigation plan
- build and test integration modules early, not at the end
- keep fallback demo assets ready
- maintain a simple, explainable architecture rather than overengineering
- avoid adding extra features that distract from the core platform

## 11. Delivery plan for the project
Use this order for delivery:
1. scaffold the app factory and config
2. build the data model and seed data
3. complete auth and shared shell
4. finish donor, hospital, bloodbank, and admin dashboards
5. add matching, map, and forecasting
6. wire USSD, SMS, and email
7. add reimbursement and sandbox callbacks
8. deploy and rehearse the demo

## 12. Definition of done
The project is complete when:
- the Flask app runs locally and on Render
- all required user roles work
- donor, hospital, bloodbank, and admin workflows are functional
- matching logic is explainable and visible
- map and forecasting components are present and labeled correctly
- USSD/SMS/email flows work in sandbox mode
- reimbursement requests can be created, approved, and logged through Daraja sandbox
- the app follows the required UI and privacy constraints
- the demo can be run end to end without major surprises

