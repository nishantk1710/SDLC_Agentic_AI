# glossary.md — design-pack artifact A3 (owner: M1 — Requirements & Scope)

Canonical vocabulary for the e-commerce shop. Every artifact uses these terms
and spellings exactly. Where a term maps to code, the wire name (camelCase,
openapi.yaml) and storage name (snake_case, schema.sql) are given.

| Term | Definition | Wire / storage names |
|------|------------|----------------------|
| **User** | A registered account holder. Identified by a unique email (BR-001). | `User` / table `users` |
| **Visitor** | Anyone browsing without being logged in. Can view Home, Products, Product Details only. | — |
| **Product** | A purchasable catalogue item, seeded out of band; read-only to the app. | `Product` / table `products` |
| **Catalogue** | The full set of active products (`isActive = true`). | — |
| **Category** | A product's single grouping label (e.g. Electronics, Kitchen); used for filtering. | `category` / `products.category` |
| **Stock (stock quantity)** | Units of a product currently available. Caps cart quantities (BR-003); decremented at order placement. | `stockQuantity` / `products.stock_quantity` |
| **Cart** | A user's single open container of intended purchases. Created at registration, one per user, emptied — never deleted — at checkout. | `Cart` / table `carts` |
| **Cart item (line)** | One product-in-cart with a quantity (1–99). One line per product per cart; adding an existing product merges quantities. | `CartItem` / table `cart_items` |
| **Item count** | Sum of all line quantities in the cart — the number shown in the header badge. | `itemCount` (computed) |
| **Subtotal** | Sum of line totals (unit price × quantity) before shipping. | `subtotal` / `orders.subtotal` |
| **Shipping fee** | Flat 5.00 USD added to every order (BR-006). | `shippingFee` / `orders.shipping_fee` |
| **Total** | `subtotal + shippingFee`, enforced by `orders_total_consistent`. | `total` / `orders.total` |
| **Checkout** | The act of turning the cart into an order: address entry + `POST /orders` (REQ-009). |
| **Order** | An immutable record of a completed checkout, owned by one user. | `Order` / table `orders` |
| **Order item** | One line of an order, carrying the **snapshot** of product name and unit price at placement (BR-005). | `OrderItem` / table `order_items` |
| **Order number** | Human-facing unique order reference, format `ORD-######` (e.g. ORD-000042). | `orderNumber` / `orders.order_number` |
| **Order status** | Lifecycle position of an order: one of PENDING, PAID, SHIPPED, DELIVERED, CANCELLED (BR-007; transitions in state-transitions.md). | `status` / enum `order_status` |
| — PENDING | Placed, awaiting (out-of-scope) payment. Initial status of every order. |
| — PAID | Payment confirmed. |
| — SHIPPED | Handed to the carrier. Cancellation no longer possible. |
| — DELIVERED | Received by the customer. Terminal. |
| — CANCELLED | Aborted from PENDING or PAID. Terminal. |
| **Snapshot** | Copying a value (product name, unit price) onto an order line so later catalogue edits can't rewrite history (BR-005). | `order_items.product_name`, `order_items.unit_price` |
| **Access token (JWT)** | Bearer credential returned by register/login; expires after 3600 s (NFR-001). Sent as `Authorization: Bearer <token>`. | `accessToken` |
| **Session** | The client-side state of holding a valid JWT. Ended by logout (REQ-012) or expiry. | — |
| **Error envelope** | The single error shape `{ "error": { code, message, details[] } }` used by every non-2xx response. Codes are registered in validation-rules.json. | `ErrorResponse` |
| **Validation message** | The exact user-facing string for a rule violation, defined once in validation-rules.json and reused verbatim in UI and API (NFR-007). | — |
| **Pagination** | `page`/`limit` query params with a `{ items, page, limit, total, totalPages }` response envelope; `limit` ≤ 100 (NFR-004). | `ProductListResponse`, `OrderListResponse` |
| **Breakpoint** | Viewport range switching the layout: Mobile ≤ 375 px, Tablet 376–768 px, Desktop ≥ 1024 px (NFR-005). | tokens.json `breakpoints` |
| **Design token** | A named visual constant (colour, spacing, radius, font) defined in tokens.json; mockup.html uses only token values. | tokens.json |
| **Empty state** | The screen variant shown when a list has no data (empty cart, no orders), with a call-to-action. | — |
| **Toast** | Transient notification; success toasts auto-dismiss after 3 s. | — |
| **Badge** | Small status label (order status colours) or counter (header cart badge). | — |
| **Design pack** | The 18-artifact bundle (this fixture) the Design service hands to the Implementation service; inventory in index.md. | — |
| **Handoff ID** | Contract identifier of an artifact within the design pack (A1–E6); mapping in index.md. | — |
