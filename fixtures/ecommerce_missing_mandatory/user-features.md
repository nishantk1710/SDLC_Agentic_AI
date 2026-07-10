# user-features.md — design-pack artifacts A2 · B1 · B4 (owner: M1 — Requirements & Scope)

Features (A2), user flows (B1), and acceptance criteria (B4) for the e-commerce
shop. Requirement IDs resolve in extracted-requirements.md; exact message
strings resolve in validation-rules.json; screens resolve in routes.json and
mockup.html.

---

## 1 · Features & user stories (A2)

| Feature | REQ | User story |
|---------|-----|------------|
| F-01 Registration | REQ-001 | As a visitor, I want to create an account so that I can shop and track my orders. |
| F-02 Login | REQ-002 | As a returning user, I want to log in so that I can access my cart and orders. |
| F-03 Browse catalogue | REQ-003 | As a visitor, I want to browse, search, filter, and sort products so that I can find what I need. |
| F-04 Product details | REQ-004 | As a visitor, I want to see a product's full details so that I can decide whether to buy it. |
| F-05 Add to cart | REQ-005 | As a shopper, I want to add a product (with a quantity) to my cart so that I can buy it later. |
| F-06 View cart | REQ-006 | As a shopper, I want to see everything in my cart with a running subtotal so that I know what I'll pay. |
| F-07 Update quantity | REQ-007 | As a shopper, I want to change a line's quantity so that I can buy more or fewer of an item. |
| F-08 Remove item | REQ-008 | As a shopper, I want to remove an item (with a confirmation step) so that I don't buy it by mistake. |
| F-09 Checkout | REQ-009 | As a shopper, I want to enter a shipping address and place my order so that my items are delivered. |
| F-10 Order history | REQ-010 | As a customer, I want to see a list of my past orders so that I can track what I've bought. |
| F-11 Order details / confirmation | REQ-011 | As a customer, I want to see one order's full details (and a confirmation right after checkout) so that I can verify it. |
| F-12 Logout | REQ-012 | As a logged-in user, I want to log out so that my session ends on this device. |

---

## 2 · User flows (B1)

Route ids below are from routes.json; operation ids from openapi.yaml.

### Flow 1 — Register & land signed-in (F-01)
1. Visitor opens `register` and submits full name, email, password.
2. Client validates per validation-rules.json (`register` form); invalid fields
   show inline errors on blur/submit.
3. `registerUser` → 201: store JWT, header switches to logged-in state (cart
   badge = 0), redirect to `?next` or `home`.
4. 409 `EMAIL_TAKEN` → inline error on the email field: **"An account with this
   email already exists."**

### Flow 2 — Log in (F-02)
1. Visitor opens `login` (possibly redirected with `?next=<path>`), submits
   email + password.
2. `loginUser` → 200: store JWT, redirect to `next` or `home`.
3. 401 → form-level error: **"Invalid email or password."** (never reveals
   which field was wrong).

### Flow 3 — Browse → details → add to cart (F-03, F-04, F-05)
1. `home` shows the 4 newest products (`listProducts?limit=4&sort=newest`);
   `products` shows the full paginated grid with search/category/sort controls
   in a sidebar (hamburger drawer on Mobile).
2. Clicking a card opens `product-details` (`getProduct`).
3. User picks a quantity (stepper, 1–99, capped at `stockQuantity`) and clicks
   **Add to Cart** → button enters loading state (spinner + disabled).
4. `addCartItem` → 201: success toast **"Added to cart."** (auto-dismisses
   after 3 s), header badge updates to the returned `itemCount`.
5. If not logged in, the click redirects to `/login?next=/products/:productId`.
6. 409 `INSUFFICIENT_STOCK` → error toast with the exact message, e.g.
   **"Only 3 left in stock."**

### Flow 4 — Manage cart (F-06, F-07, F-08)
1. `cart` loads `getCart`; empty carts show the empty state with a
   **Browse products** button.
2. Stepper +/− on a line calls `updateCartItem`; the response cart re-renders
   totals. Values outside 1–99 are blocked in the UI before any request.
3. The trash icon opens the confirm modal (fade + slide-up 200 ms):
   "Remove **{productName}** from your cart?" → **Remove** calls
   `removeCartItem`; the response cart re-renders.
4. **Proceed to Checkout** navigates to `checkout` (disabled when cart empty).

### Flow 5 — Checkout (F-09)
1. `checkout` shows the read-only order summary (`getCart`) and the shipping
   address form (`checkout` form rules in validation-rules.json).
2. **Place Order** → loading state → `placeOrder`.
3. 201 → navigate to `order-confirmation` for the new order id; success toast
   **"Order placed."**; header badge resets to 0 (cart was emptied, BR-004).
4. 409 `CART_EMPTY` → error banner: **"Your cart is empty. Add items before
   checking out."**
5. 409 `INSUFFICIENT_STOCK` → error banner with the exact per-product message,
   e.g. **"Only 2 left in stock for Terra Ceramic Mug."**; user returns to cart.

### Flow 6 — Order history (F-10, F-11)
1. `my-orders` loads `listOrders` (10 per page, newest first); each row links
   to `order-confirmation` for that order.
2. `order-confirmation` loads `getOrder` and renders lines, subtotal, shipping
   fee (5.00, BR-006), total, address, and a status Badge (colour mapping in
   state-transitions.md).
3. An order id that doesn't exist **or belongs to another user** renders the
   404 state: **"Order not found."**

### Flow 7 — Logout (F-12)
1. Header **Log out** discards the stored JWT (no API call), resets cart badge,
   redirects to `home`.

### Session expiry (NFR-001)
Any 401 `UNAUTHORIZED` response while signed in discards the token and
redirects to `/login?next=<current path>` with the toast
**"Authentication required. Please log in."**

---

## 3 · Acceptance criteria (B4)

Format: Given / When / Then. Message strings must match validation-rules.json
byte-for-byte (NFR-007).

### F-01 Registration
- **AC-01.1** Given a new email, when I submit valid name/email/password, then
  I receive 201 with a JWT and my user object, and I am signed in.
- **AC-01.2** Given the email `ava.sharma@example.com` is registered, when I
  register with it again, then I see "An account with this email already
  exists." on the email field (409 EMAIL_TAKEN, BR-001).
- **AC-01.3** When I submit password `short1`, then I see "Password must be at
  least 8 characters." (BR-002) and no request reaches the server.
- **AC-01.4** When I submit password `abcdefgh` (no digit), then I see
  "Password must contain at least one letter and one number."

### F-02 Login
- **AC-02.1** Given valid credentials, when I log in, then I receive 200 with a
  JWT valid for 3600 s (NFR-001).
- **AC-02.2** Given a wrong password, when I log in, then I see "Invalid email
  or password." and the response is 401 INVALID_CREDENTIALS.

### F-03 Browse catalogue
- **AC-03.1** Given 8 seeded products, when I open the Products page, then I
  see all 8 on page 1 (default limit 12, sort newest).
- **AC-03.2** When I search `mouse`, then only "Nimbus Wireless Mouse" is shown.
- **AC-03.3** When I filter category `Electronics`, then exactly 3 products
  are shown.
- **AC-03.4** When I sort `price_asc`, then the first product is "Luna
  Notebook Set" (12.75).
- **AC-03.5** At viewport 375 px the grid is 1 column and the sidebar is a
  hamburger drawer; at 768 px it is 2 columns; at 1024 px it is 4 columns
  (NFR-005).

### F-04 Product details
- **AC-04.1** When I open a valid product, then name, description, price, image,
  category, and stock indication are visible.
- **AC-04.2** When I open a non-existent product id, then the 404 state shows
  "Product not found."

### F-05 Add to cart
- **AC-05.1** Given I am logged in, when I add quantity 2 of a product, then
  the response is 201 with the full cart and the header badge shows the new
  `itemCount`, and I see the toast "Added to cart." for 3 s.
- **AC-05.2** Given the product is already in my cart with quantity 2, when I
  add 1 more, then the line's quantity is 3 (merge, not a second line).
- **AC-05.3** Given a product with `stockQuantity` 3, when I try to add 5, then
  I see "Only 3 left in stock." (409 INSUFFICIENT_STOCK, BR-003).
- **AC-05.4** Given I am not logged in, when I click Add to Cart, then I am
  redirected to `/login?next=<product page>`.

### F-06 View cart
- **AC-06.1** Given items in my cart, when I open the Cart page, then each line
  shows name, unit price, quantity stepper, line total, and the subtotal equals
  the sum of line totals.
- **AC-06.2** Given an empty cart, then I see the empty state and the Checkout
  button is disabled.

### F-07 Update quantity
- **AC-07.1** When I change a line from 2 to 3, then the line total and
  subtotal update from the PATCH response.
- **AC-07.2** The stepper's − is disabled at 1 and + is disabled at
  min(99, stockQuantity) — values violating BR-003 are unreachable in the UI.

### F-08 Remove item
- **AC-08.1** When I click the trash icon, then a confirm modal appears
  (fade + slide-up 200 ms); Cancel closes it without a request.
- **AC-08.2** When I confirm, then the line disappears and totals update from
  the DELETE response.

### F-09 Checkout
- **AC-09.1** Given a valid address and a non-empty cart, when I place the
  order, then I receive 201 with status PENDING, `shippingFee` 5.00, and
  `total = subtotal + 5.00` (BR-006), and I land on the confirmation screen.
- **AC-09.2** After placement my cart is empty (badge 0) — BR-004.
- **AC-09.3** With postal code `!!`, I see "Enter a valid postal code." and no
  order is created.
- **AC-09.4** The order's lines carry the prices at placement time; changing
  the catalogue afterwards does not alter them (BR-005).

### F-10 Order history
- **AC-10.1** Given 2 past orders, when I open My Orders, then both appear
  newest-first with order number, status badge, total, item count, and date.
- **AC-10.2** Another user's orders never appear in my list.

### F-11 Order details / confirmation
- **AC-11.1** Immediately after checkout I see the confirmation header, order
  number (e.g. ORD-000042), all lines, amounts, address, and a PENDING badge.
- **AC-11.2** Opening another user's order id shows "Order not found." (404 —
  never 403, to avoid leaking existence).

### F-12 Logout
- **AC-12.1** When I log out, then the token is gone from storage, the header
  shows Login/Register, and protected routes redirect to login.
