# Govind Nagar Suraksha Samiti Portal

A fully connected Flask + SQLite app for managing:
- House/shop member database
- Yearly maintenance charges (₹700 house, ₹1200 shop)
- Payment entries and pending reminders via SMS/WhatsApp (simulation log)
- Complaint number box + complaint workflow
- Income, expense sheet, and yearly balance sheet
- Security guard KYC + monthly salary payouts (cash/UPI)
- Admin team management and visibility settings

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open:
- `http://127.0.0.1:5000/setup` (creates default admin once)
- Login credentials: `9999999999` / `admin123`

## Core Modules

- **Authentication**: secure login/logout, admin/member roles.
- **Member DB**: add/edit/search members, address/mobile/property type, charge auto-calculation.
- **Payments**: year-wise maintenance entries with status and method.
- **Reminders**: send SMS/WhatsApp reminder action; saves reminder log in DB.
- **Complaints**: auto complaint number (e.g., `CMP-2026-0001`) and status updates.
- **Finance**:
  - Income from member payments + other income
  - Expense sheet (guards salary, repairings, maintenance, utilities, other)
  - Yearly balance sheet summary
- **Guards**: KYC + salary records with cash/UPI option.
- **Admin Team**: add new admins.
- **Settings**: control visibility options for members.

## Database Schema (high-level)

- `User` (members/admins)
- `Payment`
- `OtherIncome`
- `Expense`
- `Complaint`
- `Guard`
- `GuardSalaryPayment`
- `ReminderLog`
- `AdminSetting`

All modules are connected to the same central SQLite database (`instance/govind_nagar.db`).

## Notes

- “Members editing not saving” issue is addressed via committed edit route (`/members/<id>/edit`) that updates and persists records.
- Reminder sending is integrated as a logged simulation hook; can be replaced with real SMS/WhatsApp API provider credentials.
