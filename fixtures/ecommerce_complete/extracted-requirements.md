# extracted-requirements.md — design-pack artifacts A1 · A4 · A5 · E1 (owner: M1 — Requirements & Scope)

Sample application: **e-commerce shop**. This file is the single source of truth
for every `REQ-###`, `NFR-###`, and `BR-###` identifier used anywhere in the
design pack. **IDs are permanent** — a statement may be edited, but an ID is
never renumbered or reused. Every other artifact references these IDs.

Entities (canonical names, singular): **User, Product, Cart, Order** — plus the
join tables `cart_items` and `order_items` (see glossary.md for definitions and
schema.sql for columns).

---

## 1 · Scope overview

Users register, log in, browse a seeded product catalogue, manage a single
personal cart, place orders, and review their order history. There is **no
admin UI, no payment processing, and no email sending** — see §5.

---

## 2 · Functional requirements (A1)

Priority: M = Must have, S = Should have. All requirements below are Must
unless marked otherwise.

| ID | Requirement | Screen(s) | Endpoint(s) |
|----|-------------|-----------|-------------|
| REQ-001 | A visitor can register an account with full name, email, and password. Registration signs the user in immediately (returns a JWT) and creates their empty cart. | Register | `POST /auth/register` |
| REQ-002 | A registered user can log in with email and password and receive a JWT access token. | Login | `POST /auth/login` |
| REQ-003 | Any visitor (no login required) can browse the product catalogue: paginated list with search by name, filter by category, and sorting (newest, price asc/desc, name asc/desc). | Home, Products | `GET /products` |
| REQ-004 | Any visitor can view a single product's details: name, description, price, stock availability, image, category. | Product Details | `GET /products/{productId}` |
| REQ-005 | A logged-in user can add a product to their cart with a chosen quantity. Adding a product already in the cart merges quantities. | Product Details | `POST /cart/items` |
| REQ-006 | A logged-in user can view their cart: line items with product name, unit price, quantity, line total, plus cart subtotal and total item count. | Cart, Checkout, header badge | `GET /cart` |
| REQ-007 | A logged-in user can change the quantity of a cart line. | Cart | `PATCH /cart/items/{itemId}` |
| REQ-008 | A logged-in user can remove a line from their cart (with confirmation). | Cart | `DELETE /cart/items/{itemId}` |
| REQ-009 | A logged-in user can place an order from their non-empty cart by providing a shipping address. Placing the order snapshots prices, adds the flat shipping fee, empties the cart, and creates the order in status PENDING. | Checkout | `POST /orders` |
| REQ-010 | A logged-in user can view a paginated list of their own orders, newest first, showing order number, status, total, item count, and date. | My Orders | `GET /orders` |
| REQ-011 | A logged-in user can view the full details of one of their own orders: lines, amounts, shipping address, status. This screen doubles as the post-checkout confirmation. | Order Confirmation | `GET /orders/{orderId}` |
| REQ-012 | A logged-in user can log out. Logout is client-side only: the stored JWT is discarded; no API call is made. | Header (all screens) | — |

---

## 3 · Non-functional requirements (A4)

| ID | Requirement |
|----|-------------|
| NFR-001 | Authentication uses JWT bearer tokens that expire 3600 seconds after issue. Protected endpoints return HTTP 401 with code `UNAUTHORIZED` when the token is missing, invalid, or expired. |
| NFR-002 | Passwords are stored only as bcrypt hashes with cost factor 12. Plaintext passwords never reach the database or logs. |
| NFR-003 | API endpoints respond within 300 ms at the 95th percentile under 50 concurrent users on the reference deployment (single node, local PostgreSQL). |
| NFR-004 | All list endpoints are paginated; `limit` is capped at 100 items per page. |
| NFR-005 | The UI is responsive at three breakpoints: Mobile ≤ 375 px, Tablet 376–768 px, Desktop ≥ 1024 px (widths 769–1023 px render the Tablet layout — documented assumption). Product grid shows 1 / 2 / 4 columns respectively; the Products sidebar collapses to a hamburger drawer on Mobile. |
| NFR-006 | Text and interactive elements meet WCAG 2.1 AA contrast against their backgrounds using the palette in tokens.json. Every input has a visible label and a visible focus state. |
| NFR-007 | Every user-facing validation or error message uses the exact text defined in validation-rules.json — identical in API responses and UI. |

---

## 4 · Business rules (A5)

| ID | Rule | Enforced by |
|----|------|-------------|
| BR-001 | Each email address may be registered to at most one account. Violation → HTTP 409, code `EMAIL_TAKEN`. | `users_email_unique` (schema.sql) |
| BR-002 | Passwords are 8–72 characters and contain at least one letter and one number. | API layer, pre-hash (validation-rules.json) |
| BR-003 | A cart line's quantity is an integer from 1 to 99 and may never exceed the product's current stock. Stock is re-checked at order placement. Violation → HTTP 409, code `INSUFFICIENT_STOCK`. | `cart_items_quantity_range` + service-layer stock check |
| BR-004 | An order can only be placed from a non-empty cart; placing the order empties the cart. Violation → HTTP 409, code `CART_EMPTY`. | `orders_subtotal_positive` + service layer |
| BR-005 | Product name and unit price are snapshotted onto `order_items` at placement; later catalogue edits never change past orders. | `order_items.product_name`, `order_items.unit_price` |
| BR-006 | A flat shipping fee of 5.00 USD applies to every order; `total = subtotal + shippingFee`. | `orders.shipping_fee DEFAULT 5.00`, `orders_total_consistent` |
| BR-007 | Order status follows PENDING → PAID → SHIPPED → DELIVERED. CANCELLED is reachable only from PENDING or PAID (i.e. before shipping). No other transitions exist. Full table: state-transitions.md. | `order_status` enum + service layer |

---

## 5 · Assumptions & constraints (E1)

- **Tech stack is fixed:** React 18 + TypeScript + Vite + Tailwind (frontend);
  Node 20 + NestJS REST (backend); PostgreSQL 16; JWT auth. Base API path `/api/v1`.
- **Single currency:** all amounts are USD with exactly 2 decimal places.
- **Catalogue is seeded out of band** (schema.sql seed block). There are no
  admin endpoints or screens; products are read-only to the application.
- **One open cart per user**, created at registration, emptied (never deleted)
  at checkout.
- **Payment is out of scope.** Orders are created in PENDING; the
  PAID/SHIPPED/DELIVERED transitions exist in the data model and state table so
  the Testing team can exercise them, but no payment integration is designed.
- **No email flows:** no address verification, no password reset, no order
  confirmation emails.
- **Guest browsing:** Home, Products, and Product Details are public; Cart,
  Checkout, and Orders require login (redirect to `/login?next=<path>`).
- Wire format is camelCase JSON; the database is snake_case (mechanical mapping).

### Out of scope (explicitly)

Password reset · email verification · admin panel · product reviews/ratings ·
wishlists · coupons/discounts · saved address book · multiple carts ·
inventory management UI · payment providers · internationalisation.

---

## 6 · Traceability

- Features and acceptance criteria: user-features.md (A2, B1, B4)
- Terms and canonical names: glossary.md (A3)
- DB constraints: schema.sql (D1) — constraint names appear in §4 above
- Endpoints: openapi.yaml (D2) — each operation carries `x-req-ids`
- Field rules & message text: validation-rules.json (D4)
- Screens & routes: routes.json (B2), mockup.html (C1–C3, C5)
