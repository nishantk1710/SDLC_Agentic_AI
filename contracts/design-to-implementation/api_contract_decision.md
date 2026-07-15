# API Contract — Design Decision

## Pure Resource-Oriented REST with Flat Paths
All resources are top-level collections (e.g. /users, /restaurants, /orders, /carts, /deliveries, /reviews, /disputes, /payments, /platform-config). State transitions (accept order, cancel order, mark delivered) are expressed as PATCH requests with a 'status' field in the body. Filtering, sorting, and pagination are expressed as query parameters on collection GET endpoints. Role gating is enforced in middleware by inspecting the JWT role claim on every request.

**Pros**
- Uniform, predictable URL space that is easy for client developers to reason about without deep knowledge of the domain model.
- Flat paths avoid deeply nested URLs that become brittle when resource ownership changes (e.g. if an order is later accessible by multiple roles).
- PATCH-based status updates are cache-friendly and integrate naturally with standard HTTP tooling and API gateways.
- Works well with MongoDB document model where documents are top-level collections anyway.
- Simpler routing configuration in Express; fewer route handlers to maintain across the four independently deployable services.

**Cons**
- PATCH /orders/:id with {status: 'accepted'} conflates many distinct business operations (accept, reject, cancel, prepare, ready) into one endpoint, making it hard to enforce per-transition business rules (e.g. require a reject reason, trigger refund on rejection) without complex conditional logic inside a single handler.
- State-machine guard logic (BR-1: free cancellation only before acceptance) must live inside the shared PATCH handler, making it harder to test individual transitions in isolation.
- Filtering restaurants by delivery address, open status, cuisine, rating, price, and ETA simultaneously produces very long query strings that are opaque and hard to validate.
- Cart resource is inherently tied to a (customer, restaurant) pair; a flat /carts path requires the client to know a cart ID upfront or do an extra lookup, which is awkward for a 'get or create active cart' pattern.
- Delivery agent location updates at high frequency via REST polling is inefficient; the design does not naturally express the WebSocket channel alongside REST endpoints, creating an impedance mismatch.

## Hybrid REST + Action Sub-Resources with Moderate Nesting
Core CRUD resources are modelled as REST collections at one level of nesting where ownership is clear (e.g. /restaurants/:id/menu-categories/:catId/items, /users/:id/addresses, /restaurants/:id/reviews). State transitions that carry domain significance and business rules are modelled as action sub-resources using POST (e.g. POST /orders/:id/accept, POST /orders/:id/cancel, POST /orders/:id/reject, POST /deliveries/:id/accept, POST /deliveries/:id/complete). The cart is a singleton sub-resource per customer per restaurant: GET/PUT /customers/:id/cart?restaurantId=. Filtering and search use query parameters on GET /restaurants and GET /orders with structured names (filter[cuisine], filter[minRating], sort, page, limit). Real-time updates travel over Socket.IO channels keyed by orderId/deliveryId; the REST layer handles commands and initial state fetches.

**Pros**
- Action sub-resources make each state transition a discrete HTTP endpoint with its own request schema, validation middleware, and business-rule guards — accept enforces restaurant-open check, reject enforces reason field and triggers refund, cancel enforces BR-1 window — keeping handlers small and independently testable.
- One level of nesting where it maps to real ownership (menu items under restaurant, addresses under user) reduces ambiguity about who owns what without creating deep URL hierarchies.
- Singleton cart pattern (one active cart per customer per restaurant) is explicitly modelled as a sub-resource, allowing the server to enforce BR-2 (single-restaurant cart) and return a 409 with the existing cart when a conflict occurs.
- Structured query parameters for restaurant discovery are self-documenting and easy to validate with a schema (Joi/Zod) without a long, opaque query string.
- Clear separation between REST (state fetch, CRUD) and WebSocket (real-time push) aligns with the Socket.IO architecture already chosen, since REST endpoints return current state and WS events carry deltas.
- Role gating is naturally per-action endpoint: POST /orders/:id/accept is middleware-guarded to restaurantManager only, POST /orders/:id/cancel to customer only before acceptance, making RBAC auditable and explicit.
- Admin audit log is a natural GET /admin/audit-logs collection; admin actions like POST /restaurants/:id/suspend or POST /users/:id/activate are explicit action endpoints rather than ambiguous status PATCHes.

**Cons**
- More route handlers to define and maintain compared to pure REST; developers must learn which operations are action sub-resources vs. PATCH operations.
- Moderate nesting (e.g. /restaurants/:id/menu-categories/:catId/items/:itemId) can produce long URLs for menu item operations, though this reflects genuine ownership and rarely exceeds two levels.
- Requires clear API documentation to distinguish when to use PATCH (edit name/price of a menu item) vs. POST to an action sub-resource (toggle availability), which may confuse contributors initially.
- Cart singleton URL with a query parameter for restaurantId (/customers/:id/cart?restaurantId=) is slightly unconventional and may require explanation in docs.

## RPC-Style Action-Centric API
All operations are expressed as verb-oriented POST endpoints grouped by domain area (e.g. POST /auth/register, POST /auth/login, POST /menu/addItem, POST /orders/place, POST /orders/acceptOrder, POST /orders/cancelOrder, POST /delivery/assignAgent, POST /delivery/markDelivered, POST /reviews/submit, POST /admin/issueRefund). Resources are fetched via corresponding GET endpoints (GET /menu/getItems?restaurantId=, GET /orders/getOrder?orderId=). Filtering is handled via request body on POST /restaurants/search.

**Pros**
- Every business operation maps directly to a named endpoint, making the API surface read like a service contract that non-HTTP-specialist developers (e.g. full-stack JS developers on a MERN project) can immediately understand.
- Business rule enforcement is trivially co-located with the named action: acceptOrder handler contains all acceptance logic, cancelOrder contains BR-1 window check, no shared PATCH handler needed.
- Avoids HTTP verb semantics debates entirely; all mutations are POST, which simplifies client-side code generation and avoids PUT vs. PATCH confusion.
- Works naturally for operations that do not map to a single resource (e.g. POST /delivery/assignAgent which touches Order, Delivery, and Agent simultaneously).

**Cons**
- Abandons HTTP caching entirely for resource reads since GET endpoints with query-string-encoded fields or POST-based searches are not cacheable by standard CDN or browser caches, hurting performance for high-traffic restaurant browse and search endpoints.
- Violates REST constraints that the API gateway, load balancer, and monitoring tooling are likely configured to exploit (e.g. health checks, rate limiting by method).
- URL namespace grows unbounded and lacks the self-describing structure of resource paths; new developers cannot discover available operations without full documentation.
- Inconsistent with the stated architecture ('Services expose RESTful HTTPS APIs' per tech stack section 7.2), creating friction with the existing team decisions.
- Pagination, sorting, and filtering conventions must be invented ad hoc per endpoint rather than following a uniform pattern, increasing client-side complexity.
- RBAC middleware cannot rely on URL path patterns to scope permissions; every handler must duplicate role-checking logic or use a complex permission map.

## Chosen: Hybrid REST + Action Sub-Resources with Moderate Nesting
This app has a well-defined state machine across orders and deliveries (Pending → Accepted → Preparing → Ready → Out for Delivery → Delivered, plus cancel/reject branches), each transition carrying distinct business rules, required payloads, and downstream side effects (refunds, agent assignment, notifications). Expressing these as dedicated POST action sub-resources (POST /orders/:id/accept, POST /orders/:id/reject, POST /orders/:id/cancel, POST /deliveries/:id/complete) gives each transition its own Express route handler with scoped validation middleware, RBAC guard, and business-rule enforcement — directly addressing BR-1, BR-6, BR-7, and REQ-38 without conditional branching inside a shared PATCH handler. CRUD operations (menu items, addresses, restaurant settings) remain conventional REST with GET/POST/PATCH/DELETE, keeping the design familiar. The moderate nesting reflects genuine ownership (menu items belong to a restaurant, addresses belong to a user) without exceeding two levels. The singleton cart pattern enforces BR-2 at the URL level. Structured query parameters on GET /restaurants support the rich filtering in REQ-10 in a cacheable, standard way. The design aligns with the stated tech stack ('RESTful HTTPS APIs' + Socket.IO for real-time), supports independent service decomposition behind the API gateway, and gives the RBAC middleware clean URL patterns to guard by role — satisfying NFR-11 and REQ-7 without duplicating permission logic across dozens of RPC endpoints.

## Endpoints (65)
- 🌐 `POST /auth/register` — Register a new user account
- 🌐 `POST /auth/verify` — Verify email or phone with a one-time token
- 🌐 `POST /auth/resend-verification` — Resend verification token
- 🌐 `POST /auth/login` — Authenticate and receive JWT
- 🔒 `POST /auth/logout` — Invalidate current session token [customer, restaurantManager, deliveryAgent, platformAdmin]
- 🌐 `POST /auth/forgot-password` — Request a password-reset link
- 🌐 `POST /auth/reset-password` — Reset password using a time-limited token
- 🔒 `GET /users/me` — Get the authenticated user's profile [customer, restaurantManager, deliveryAgent, platformAdmin]
- 🔒 `PATCH /users/me` — Update the authenticated user's profile [customer, restaurantManager, deliveryAgent, platformAdmin]
- 🔒 `PATCH /users/me/agent-profile` — Update delivery-agent-specific profile fields [deliveryAgent]
- 🔒 `GET /users/me/addresses` — List saved delivery addresses [customer]
- 🔒 `POST /users/me/addresses` — Add a new saved delivery address [customer]
- 🔒 `PATCH /users/me/addresses/{addressId}` — Edit a saved delivery address [customer]
- 🔒 `DELETE /users/me/addresses/{addressId}` — Remove a saved delivery address [customer]
- 🔒 `GET /users` — List and search all users (admin) [platformAdmin]
- 🔒 `GET /users/{userId}` — Get a specific user's details (admin) [platformAdmin]
- 🔒 `PATCH /users/{userId}/status` — Suspend or reactivate a user (admin) [platformAdmin]
- 🌐 `GET /restaurants` — Browse open restaurants with filtering and sorting
- 🌐 `GET /restaurants/{restaurantId}` — Get restaurant detail including full menu
- 🔒 `POST /restaurants` — Onboard a new restaurant partner (admin) [platformAdmin]
- 🔒 `PATCH /restaurants/{restaurantId}` — Update restaurant settings [restaurantManager, platformAdmin]
- 🔒 `PATCH /restaurants/{restaurantId}/status` — Suspend or reactivate a restaurant (admin) [platformAdmin]
- 🔒 `PATCH /restaurants/{restaurantId}/open` — Toggle restaurant open/closed status [restaurantManager]
- 🌐 `GET /restaurants/{restaurantId}/reviews` — List published reviews for a restaurant
- 🌐 `GET /restaurants/{restaurantId}/menu-categories` — List all menu categories for a restaurant
- 🔒 `POST /restaurants/{restaurantId}/menu-categories` — Create a new menu category [restaurantManager]
- 🔒 `PATCH /restaurants/{restaurantId}/menu-categories/{categoryId}` — Edit a menu category [restaurantManager]
- 🔒 `DELETE /restaurants/{restaurantId}/menu-categories/{categoryId}` — Remove a menu category [restaurantManager]
- 🔒 `POST /restaurants/{restaurantId}/menu-categories/{categoryId}/items` — Add a menu item to a category [restaurantManager]
- 🔒 `PATCH /restaurants/{restaurantId}/menu-categories/{categoryId}/items/{itemId}` — Edit a menu item [restaurantManager]
- 🔒 `DELETE /restaurants/{restaurantId}/menu-categories/{categoryId}/items/{itemId}` — Remove a menu item [restaurantManager]
- 🔒 `PATCH /restaurants/{restaurantId}/menu-categories/{categoryId}/items/{itemId}/availability` — Toggle per-item availability [restaurantManager]
- 🔒 `GET /cart` — Get the customer's active cart [customer]
- 🔒 `PUT /cart/items` — Add or update an item in the cart [customer]
- 🔒 `DELETE /cart/items/{menuItemId}` — Remove an item from the cart [customer]
- 🔒 `DELETE /cart` — Clear the entire cart [customer]
- 🔒 `PATCH /cart/fulfillment` — Set delivery or pickup and delivery address [customer]
- 🔒 `POST /orders` — Checkout cart and place an order [customer]
- 🔒 `GET /orders` — List orders (scoped by caller role) [customer, restaurantManager, platformAdmin]
- 🔒 `GET /orders/{orderId}` — Get full order details [customer, restaurantManager, deliveryAgent, platformAdmin]
- 🔒 `POST /orders/{orderId}/cancel` — Customer cancels an order [customer, platformAdmin]
- 🔒 `POST /orders/{orderId}/accept` — Restaurant accepts an incoming order [restaurantManager]
- 🔒 `POST /orders/{orderId}/reject` — Restaurant rejects an incoming order [restaurantManager]
- 🔒 `POST /orders/{orderId}/advance` — Advance order to Preparing or Ready [restaurantManager]
- 🔒 `GET /payments/{paymentId}` — Get payment details for an order [customer, platformAdmin]
- 🔒 `GET /payments` — List and search all payments (admin) [platformAdmin]
- 🔒 `POST /payments/{paymentId}/refund` — Issue a full or partial refund (admin) [platformAdmin]
- 🔒 `GET /deliveries/{deliveryId}` — Get delivery status and agent location [customer, deliveryAgent, restaurantManager, platformAdmin]
- 🔒 `POST /deliveries/{deliveryId}/respond` — Agent accepts or declines a delivery offer [deliveryAgent]
- 🔒 `PATCH /deliveries/{deliveryId}/location` — Agent pushes a live location update [deliveryAgent]
- 🔒 `POST /deliveries/{deliveryId}/pickup` — Agent confirms order picked up from restaurant [deliveryAgent]
- 🔒 `POST /deliveries/{deliveryId}/complete` — Agent marks order delivered with optional proof-of-delivery [deliveryAgent]
- 🔒 `GET /deliveries` — List delivery history for the authenticated agent [deliveryAgent, platformAdmin]
- 🔒 `POST /reviews` — Submit a rating and review for a delivered order [customer]
- 🌐 `GET /reviews/{reviewId}` — Get a single review
- 🔒 `GET /reviews` — List all reviews (admin) [platformAdmin]
- 🔒 `POST /reviews/{reviewId}/remove` — Remove a review for policy violation (admin) [platformAdmin]
- 🔒 `POST /disputes` — Customer submits a dispute for an order [customer]
- 🔒 `GET /disputes` — List disputes (scoped by caller role) [customer, platformAdmin]
- 🔒 `GET /disputes/{disputeId}` — Get dispute detail [customer, platformAdmin]
- 🔒 `POST /disputes/{disputeId}/resolve` — Admin records a resolution and optionally issues a refund [platformAdmin]
- 🔒 `GET /platform-config` — Retrieve current platform configuration [platformAdmin]
- 🔒 `PATCH /platform-config` — Update platform configuration parameters [platformAdmin]
- 🔒 `GET /audit-logs` — List administrative audit log entries [platformAdmin]
- 🔒 `GET /audit-logs/{logId}` — Get a single audit log entry [platformAdmin]