# FrameFlow Doors & Windows

An internal Streamlit product configurator for made-to-measure doors and windows.

## Included

- Door and window categories
- Opening-style browser cards for doors and windows
- Product effect and detail imagery
- Opening direction, glass and finish options
- Color selection inside product configuration
- Inventory display below the configured product options
- Product color and stock information sections
- Manual width and height entry
- Area-based pricing with minimum prices
- Shopping cart
- Customer contact and project address form
- PDF quote generation
- Local quote history
- Customer CRM for active leads, ordered customers and lost customers
- Inventory entry for product stock, received date, warehouse, location and reserved quantity
- Live stock availability in product configuration, cart and customer wishlist records
- Customer wishlist tracking from manual product choices or exact shopping cart configurations
- Customer-linked carts and quotes
- Follow-up progress tracking, on-hold status and overdue reminders
- Order payment tracking and installation follow-up reminders
- Finance dashboard for monthly, quarterly and yearly sales, salesperson contribution, second-payment forecast, receivables and CSV export
- Lost-customer reason tracking
- After-sales search by customer, quote/order product selection, service request submission and repair timeline tracking
- Optional SMTP email delivery
- Password-protected product administration
- Add, edit, hide and delete products in the browser
- Upload and replace product images

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`.

## Email setup

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add your SMTP account values. The real secrets file is excluded from Git.

After a quote PDF is generated, checkout shows an editable email draft. Review or change the subject and message, then send the PDF quote directly from the configured work email account.

## Employee login

The whole website is protected by an employee login. Customers, inventory, quotes and after-sales records are hidden until a staff member signs in.

For a quick shared login, set this in `.streamlit/secrets.toml` or your deployment platform's Secrets:

```toml
EMPLOYEE_PASSWORD = "replace-with-a-strong-employee-password"
```

For individual staff accounts, use:

```toml
MANAGER_USERS = ["manager"]

[EMPLOYEE_USERS]
sales = "strong-password-for-sales"
warehouse = "strong-password-for-warehouse"
manager = "strong-password-for-manager"
```

`MANAGER_USERS` controls who can see manager-only views such as Finance and Admin. Until employee credentials are configured, local development uses built-in demo accounts such as `Mia / frameflow-mia` and `Kevin / frameflow-kevin`. These demo accounts are disabled automatically as soon as `EMPLOYEE_PASSWORD` or `[EMPLOYEE_USERS]` is configured.

Change all demo credentials before putting the website online.

## Admin setup

The **Admin** page lets you change product names, descriptions, pricing, options and images without editing code.

Set `ADMIN_PASSWORD` in `.streamlit/secrets.toml`. Until you do, the local development password is:

```text
frameflow-admin
```

Change it before putting the website online.

## Replace product images

The first launch generates sample images in `assets/products/`. Images uploaded from the Admin page are compressed to WebP and saved in `assets/products/uploads/`.

Every uploaded product image is automatically centered and cropped to a consistent **3:2 ratio (1500 × 1000 pixels)**. Original uploads are retained in `assets/products/originals/` as backups.

Product information is stored in `data/products.json`. Back up this file and the uploaded image folder regularly.

## Customer CRM

Open the **Customers** tab to manage customers in three buckets:

- **Following**: first follow-up date, next follow-up date, stage, priority and on-hold status
- **Ordered**: order date, first and second payment records, total paid and installation reminders
- **Lost**: lost date, reason and internal notes

Use **Save cart as customer wishlist** from the cart page to attach the current configured products to a customer record. The wishlist keeps product names, dimensions, glass, frame, quantity and estimated amount.

Use **Work on this customer's cart** from a customer card to load that customer's saved cart. Products added from the catalog will be saved back to that customer cart, and quotes generated from checkout will stay linked to the customer profile.

When a quote is generated from checkout, the customer name, email, phone and address are automatically saved into the CRM. If a matching customer already exists by email or phone, that record is updated; otherwise a new following customer is created. Checkout also records first and second follow-up dates on the customer timeline.

Customer records are stored locally in `quotes.db` in the `customers` table.

## Finance dashboard

Open the **Finance** tab to review company-wide financial information by month, quarter or year.

The dashboard shows ordered sales by order date, each salesperson's contribution, payments collected in the selected period, unpaid second payments expected in the selected period, open receivable balances, overdue payment counts and a CSV export for finance handoff.

Finance data is calculated from ordered customer records, quote totals, wishlist/order totals and the first/second payment schedule stored in `quotes.db`.

## Inventory

Open the **Inventory** tab to record stock as it arrives. Each inventory item can store the product, SKU or batch number, received date, warehouse, location, dimensions, color, glass, frame, opening direction, quantity, reserved quantity, unit cost, status and notes.

The catalog configuration page, cart, and customer wishlist automatically compare requested products against available inventory. Available stock is calculated as:

```text
quantity - reserved quantity
```

Inventory records are stored locally in `quotes.db` in the `inventory_items` table.

## After-sales

Open the **After-sales** tab to search a customer, review their saved quote or order products, select one product, and submit a service request.

Each service request records the customer, project address, quote number, product configuration, damaged part, damage reason, issue description, appointment date, priority, assigned team/person and internal notes.

The service dashboard shows open requests for leadership or the after-sales team. Update the timeline as the request moves through new request, reviewing, appointment scheduled, repairing, waiting parts, completed and closed.

After-sales records are stored locally in `quotes.db` in the `service_requests` and `service_timeline` tables.

## Pricing

Sample pricing can be edited from the Admin page and is stored in `data/products.json`. The estimated unit price is:

```text
max(width × height in square feet × base rate × option factors, minimum price)
```

Replace these sample rates with your company’s actual pricing rules before using quotes commercially.
