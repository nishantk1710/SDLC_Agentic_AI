# DB Schema — Design Decision

## Aggregate-per-Lifecycle-Unit
Each major bounded lifecycle is one document: User (with embedded saved addresses and auth metadata), Restaurant (with fully embedded menu categories and items as nested arrays), Order (with embedded order items, a single embedded payment subdocument, and a single embedded delivery subdocument), Cart (standalone, one per customer per restaurant), and Review (standalone, referencing order and restaurant). Restaurants are referenced from Orders by ID only; aggregated rating is stored as a precomputed field on the Restaurant document and updated on each review write.

**Pros**
- Single-document read for the most critical customer path: loading a restaurant page fetches the full menu in one query with no joins.
- Order document is fully self-contained — items, payment status, delivery status, and status history are all present without extra lookups, which is essential for the order tracking WebSocket push.
- Cart reads and writes are atomic per document; recalculation on every cart change (REQ-15) touches exactly one document.
- Menu management (REQ-34, REQ-35) maps naturally to in-place updates of embedded arrays via $set/$pull on the Restaurant document.
- Precomputed avgRating on Restaurant supports filtering by minimum rating (REQ-10) without aggregation at read time.
- Restaurant open/closed toggle (REQ-35) is a single atomic field update on the Restaurant document.

**Cons**
- Restaurant document grows with every menu item added over time; very large menus (hundreds of items across many categories) push the 16 MB BSON limit and make partial menu updates chattier.
- Updating a single menu item's price requires addressing the correct position in a nested array, which becomes complex if categories and items are deeply nested.
- The embedded delivery subdocument in Order must store reassignment history (REQ-26 — agent declines, timeouts); this is a small but ever-appending array that must be bounded in practice.
- Payment subdocument embedded in Order means refund webhook updates from the gateway touch the Order document directly, increasing contention on that document during high-volume periods.
- Admin cross-entity search (REQ-40) across orders and users still requires multi-collection queries despite embedding.

## Normalized-References-with-Selective-Denormalization
Collections are: users, restaurants, menuCategories, menuItems, carts, orders, payments, deliveries, reviews. Every entity is its own collection and linked by ObjectId references. Orders embed only a snapshot array of order items (name, price, quantity at time of order — immutable after placement) rather than live references to menuItems, preventing price drift. Denormalized read-model fields (avgRating, deliveryFee, estimatedDeliveryTime) are stored on the Restaurant document and updated asynchronously. Cart stores references to menuItem IDs and resolves them at read time to get current prices.

**Pros**
- Menu categories and items are independently queryable documents — manager bulk edits, availability toggles, and search indexing (REQ-9) are clean operations on small documents.
- Payment is a first-class document, simplifying PCI-audit trails and gateway webhook upserts without contending on the Order document.
- Delivery is its own document, making agent assignment queries (REQ-25, REQ-26 proximity + load) straightforward aggregations over the deliveries collection.
- No risk of document size blowup regardless of how many menu items a restaurant accumulates.
- Admin cross-entity search (REQ-40) is natural — each collection is independently indexed and queryable.
- Order item snapshot pattern correctly freezes prices and item names at placement time (important for disputes, REQ-41).

**Cons**
- Loading a restaurant's menu page requires at minimum two queries (restaurant + menuItems filtered by restaurantId, possibly a third for categories) — acceptable with proper indexing but adds latency vs. embedding.
- Order tracking read (REQ-27, REQ-28) requires joining orders + deliveries at the application layer or via $lookup, adding complexity to the real-time WebSocket update path.
- Cart checkout requires resolving each menuItem reference to validate current price and availability before creating the order snapshot — more round-trips.
- More collections means more indexes to maintain and more surface area for consistency bugs when a menu item is toggled unavailable while a cart holds a reference to it.
- avgRating async update (REQ-32) introduces a brief window of stale data on the Restaurant document.

## Hybrid-Bounded-Aggregates-with-Separate-Operational-Collections
Restaurant document embeds menu categories and items (because menu is always read/written as a unit by the manager and served as a unit to the customer). User document embeds saved addresses (bounded, max ~10 per user). Order document embeds the immutable order-item snapshot and status history array, but Payment and Delivery are separate collections referenced by ID from the Order. Cart is a standalone document per customer-restaurant pair. Review is a standalone collection. Restaurant carries denormalized avgRating, reviewCount, estimatedDeliveryTime, and deliveryFee for browse/filter queries. A 2dsphere index on Restaurant.location enables geospatial delivery-radius filtering (BR-4).

**Pros**
- Restaurant+Menu remains one atomic document for the most frequent read (browse + menu display), eliminating joins on the hot customer path.
- Separating Payment into its own collection isolates gateway webhook writes and refund state transitions from the Order document — reduces write contention and simplifies PCI audit.
- Separating Delivery into its own collection allows the delivery-tracking service to maintain agent location, reassignment attempts, and proof-of-delivery photo reference without polluting the Order document; the WebSocket tracker queries deliveries directly by orderId index.
- Order document stays compact: immutable item snapshot + status history (bounded by the fixed lifecycle states) + references to payment and delivery IDs.
- Geospatial index on Restaurant.location natively supports REQ-8 (deliver to address), REQ-25 (agent proximity), and BR-4 (delivery radius).
- User embedded addresses (REQ-6) are bounded and read atomically with the user profile; no separate collection needed.
- Menu management writes (REQ-34, REQ-35) are positional array updates on a single Restaurant document — no cross-collection transactions needed.
- Reviews are separate — admin removal (REQ-33) is a single document delete; avgRating update on Restaurant is an atomic $inc on reviewCount and $set on avgRating using a running-average formula.

**Cons**
- Very large restaurants with hundreds of menu items across many categories will produce larger Restaurant documents; mitigation is a practical item count limit enforced at the application layer, which is acceptable for a single-metro v1.
- Order status transitions (REQ-37) write to the Order document while related payment state may be updating concurrently; application-level sequencing or optimistic concurrency (version field) is required.
- Menu item availability toggle must also invalidate any active Cart documents referencing that item — requires an application-side check at cart-read or checkout time, not an automatic cascade.
- Two-collection reads (Order + Delivery) are needed for the full order-tracking view, but this is a single indexed lookup and acceptable given the separation-of-concerns benefit.
- Slightly more complex Mongoose schema setup than pure embedding due to the mixed strategy.

## Chosen: Hybrid-Bounded-Aggregates-with-Separate-Operational-Collections
This approach aligns document boundaries precisely with the application's distinct read/write patterns and operational concerns. The restaurant+menu embedding serves the single most frequent and latency-sensitive read path (customer browsing) without any joins. Embedding addresses in User is safe because the entity is genuinely bounded (a person maintains only a handful of addresses). The Order document carries the immutable item snapshot — correctly freezing prices for dispute resolution — plus a compact status-history array whose length is strictly bounded by the defined lifecycle states, eliminating unbounded-array risk. Separating Payment decouples gateway webhook processing (an asynchronous, externally-triggered write) from customer-facing order reads and prevents gateway latency from creating lock contention on the Order document, which is also important for PCI audit trail isolation. Separating Delivery lets the real-time tracking service (WebSocket, REQ-27, REQ-28) query and update a focused document — including agent location, reassignment attempts, and proof-of-delivery photo reference — without touching the Order document on every location ping. Reviews as a standalone collection support admin moderation queries and running-average updates cleanly. The 2dsphere geospatial index on Restaurant.location is native to MongoDB and directly satisfies delivery-radius filtering (BR-4) and agent-proximity assignment (REQ-25). Together, this design avoids the document-size and write-contention pitfalls of full embedding while avoiding the multi-collection join overhead of full normalization, making it the best fit for a MERN-stack food-delivery platform at single-metro v1 scale.