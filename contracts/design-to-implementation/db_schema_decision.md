# DB Schema — Design Decision

## Aggregate-Per-Lifecycle
Model each major lifecycle entity (User, Restaurant+Menu, Order, Cart, Delivery, Review) as its own top-level collection with rich embedding of stable sub-entities and referencing across lifecycle boundaries. Users embed their saved addresses. Restaurants embed their full menu hierarchy (categories → items) as a nested array since the manager owns and reads the whole menu together. Orders embed a snapshot of ordered items (name, price at time of order) plus a payment subdocument and reference restaurantId, customerId, deliveryAgentId, and deliveryId as ObjectId refs. Cart is a separate lightweight collection keyed by customerId+restaurantId and discarded on order placement. Delivery is its own collection referenced from Order. Reviews are a separate collection referencing orderId and restaurantId, with the restaurant document storing a denormalised avgRating and reviewCount updated on each write.

**Pros**
- Restaurant menu read (the dominant browse query) fetches one document: no joins, ideal for the high-traffic search/browse service.
- Order document is a self-contained audit record: item names and prices are snapshotted at placement time, satisfying financial and dispute-resolution needs without historical price tracking.
- Menu management (add/edit/remove items and categories) is a single findOneAndUpdate on the restaurant document, keeping the manager portal simple.
- Saved addresses embedded in User keep the checkout address-picker to a single document fetch.
- Separate Delivery collection avoids embedding ever-changing location pings inside Order and keeps the order document stable for status reads.
- Cart as a separate ephemeral collection (TTL index) avoids polluting the order history and is trivially dropped on placement.

**Cons**
- Restaurant document can grow large for menus with hundreds of items across many categories; updates to a single item still rewrite the array element (mitigated by positional $ operators, but document size is a real concern at scale).
- avgRating denormalisation on the restaurant document requires a two-document write (new Review + $inc on Restaurant) that must be made resilient to partial failure (e.g. via application-level retry or a change-stream worker).
- Cross-collection queries for admin dashboards (orders + users + payments) require $lookup aggregation pipelines, which are costlier in MongoDB than equivalent relational joins.
- Delivery agent location updates are frequent; if stored inside Delivery they grow the document; a separate location-ping sub-collection or capped collection is needed.

## Order-Centric Mega-Document
Treat the Order as the central aggregate and embed almost everything that belongs to a single order lifecycle: full item snapshots, payment record, delivery record (including status history), and a reference to the review. Restaurant and User remain separate collections but are denormalised heavily into Order at placement time (restaurant name, address, customer name, delivery address snapshot). Menu is embedded inside Restaurant. Cart is transient and merged into the Order document on placement. Reviews are embedded as a single subdocument inside the Order (one review per order, BR-6).

**Pros**
- A single Order document read satisfies every order detail, tracking, receipt, and dispute-resolution view without any $lookup.
- Payment and delivery lifecycle data live with the order they belong to, making audit trails trivial.
- Review embedded in Order enforces BR-6 (one review per order) structurally at the document level.
- Reduces collection count and inter-collection coordination for the most critical operational flow.

**Cons**
- Order documents grow unboundedly if delivery status history or location pings are embedded; a 'Delivered' order with full ping history could exceed MongoDB's 16 MB document limit for very long deliveries.
- Computing restaurant average rating requires scanning all Order documents or maintaining a separate counter, since reviews are buried inside orders rather than in a queryable collection — REQ-32 and REQ-40 (admin review search) become expensive.
- Admin search across orders, users, and transactions (REQ-40) must navigate deeply nested structures in aggregation pipelines, making indexing complex.
- Delivery agent's active job list requires scanning Order collection by agentId and status rather than a dedicated Delivery collection, complicating REQ-25/REQ-26 assignment logic.
- Updating a single nested status field (e.g. advancing to 'Preparing') still touches the whole large document, increasing write amplification.

## Normalised-References with Selective Embedding
Use well-normalised separate collections for all major entities: Users, Restaurants, MenuCategories, MenuItems, Carts, Orders, OrderItems, Payments, Deliveries, Reviews. MenuCategories and MenuItems are separate collections referencing restaurantId, not embedded. OrderItems reference menuItemId but store a price snapshot. Restaurant stores aggregated avgRating and reviewCount. Cart references restaurantId and customerId with item subdocuments. Delivery is separate from Order. This mirrors a relational schema translated to documents, using $lookup-heavy aggregation pipelines for reads.

**Pros**
- Easiest to evolve: adding a field to MenuItem does not touch any other collection.
- No risk of unbounded document growth anywhere; all arrays are bounded or absent.
- Menu item availability toggle (REQ-35) is a single targeted document update on one MenuItem document rather than a positional update inside a large restaurant array.
- OrderItems as a separate collection supports fine-grained querying (e.g. 'which items were most ordered this week') without unwinding large embedded arrays.

**Cons**
- Restaurant menu browse (the highest-traffic read) requires a $lookup from Restaurants → MenuCategories → MenuItems: two pipeline stages and three collections, significantly increasing latency compared to a single document fetch — this is the dominant use case.
- Cart assembly and checkout involve reads across Restaurants, MenuItems, and Cart collections, adding round-trips or complex aggregation at a latency-sensitive moment.
- MongoDB is not optimised for relational-style multi-collection joins; this approach forgoes the primary advantage of a document store and suffers from the worst of both worlds.
- Shared Mongoose schema library must coordinate schema versions across MenuCategories and MenuItems separately, increasing operational complexity for a v1 product.

## Chosen: Aggregate-Per-Lifecycle
This approach best matches QuickBite's dominant read and write patterns within MongoDB's document model. The highest-traffic operation — restaurant and menu browsing (REQ-8 through REQ-12) — becomes a single document fetch with no joins, which is critical given the requirement for an independently scalable search/browse service. The embedded menu-within-restaurant model is safe because each restaurant's menu is bounded (dozens to low hundreds of items at launch in a single metro area) and is always read and managed as a whole by the restaurant manager. Snapshotting item prices and names inside the Order document satisfies financial audit and dispute-resolution needs (REQ-23, REQ-24, REQ-41) without complex historical price tracking. Keeping Delivery, Cart, and Review as separate collections prevents any single document from growing unboundedly (avoiding the fatal flaw of the Mega-Document approach) while still allowing the order status flow to be driven by lightweight status-field updates. The denormalised avgRating on the restaurant document (updated via a change-stream worker or application-level two-phase write) makes the browse filter by rating (REQ-10, REQ-11) index-efficient. This approach avoids the excessive $lookup chains of the Normalised-References model while keeping enough separation to support admin cross-entity queries via aggregation pipelines on clearly bounded collections — the right trade-off for a v1 MERN application launching in a single city.