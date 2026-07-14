# DB Schema — Design Decision

## Aggregate-Root Embedding
Each major domain aggregate owns its subordinate data fully embedded. Restaurant document embeds all MenuCategories and MenuItems. Order document embeds all OrderItems, a Payment subdocument, and a Delivery subdocument. User document embeds all saved Addresses. Cart is a standalone document referencing restaurantId and userId with items embedded. Reviews live in a separate collection referencing orderId and restaurantId, but a denormalised avgRating + reviewCount is stored on the Restaurant document.

**Pros**
- Restaurant menu reads (the dominant browse path) are single-document fetches with zero joins, ideal for the browsing and filtering features.
- Order lifecycle writes (place, accept, advance status, mark delivered) touch exactly one document, making atomic updates straightforward with MongoDB positional operators.
- Payment and Delivery are always read together with the Order; embedding eliminates extra round-trips during order tracking and admin lookups.
- Menu management by restaurant managers (add/edit/remove categories and items) is a targeted arrayFilters update on one document, keeping the manager portal fast.
- Embedded addresses on User keep profile reads simple and avoid a join for checkout address selection.
- Cart as a separate lightweight document avoids polluting the User document with volatile, frequently mutated data.

**Cons**
- A restaurant with a very large menu (hundreds of items across many categories) causes a large document; partial menu reads (single category) still fetch the whole doc unless projection is used carefully.
- Adding a review triggers two writes (insert Review doc + $inc avgRating on Restaurant) requiring application-level coordination or a two-phase approach; no native transaction needed but failure window exists.
- Embedding Delivery inside Order means the delivery agent's accepted/declined/reassignment history must also live there or be discarded, creating moderate complexity for the dispatch logic.
- Admin cross-platform search (REQ-40) across orders must query a single large orders collection — manageable with indexes but the embedded structure makes querying nested OrderItem fields (e.g. search by menu item name) require $elemMatch indexes.
- If Order documents accumulate many status-change log entries over time the document can grow, though for a food-delivery lifecycle (5-7 status hops) this is bounded and safe.

## Reference-Heavy Normalized Collections
Each entity becomes its own collection with ObjectId references between them: Users, Addresses, Restaurants, MenuCategories, MenuItems, Carts, CartItems, Orders, OrderItems, Payments, Deliveries, Reviews. Relationships are expressed as foreign-key-style references resolved at query time via $lookup aggregations or multiple sequential queries in the application layer. No significant embedding; documents are thin and normalized.

**Pros**
- Schema is clean and maps directly to the logical entity model, making it easy to query any entity in isolation without projecting away large embedded arrays.
- Updates to a MenuItem (price change, availability toggle) touch exactly one document with no risk of partial-update anomalies across embedded copies.
- Delivery collection is fully independent, allowing the dispatch microservice to own it without coupling to the Order document structure.
- Simpler to add new entity relationships (e.g. promotions, loyalty points) without restructuring large aggregate documents.
- Admin search across thin collections is straightforward; $lookup pipelines compose well for reporting.

**Cons**
- Restaurant + menu browse (the highest-traffic read path) requires multi-collection $lookup or N+1 application queries to assemble restaurant info, categories, and items — significant latency on the critical customer-facing path.
- Order placement and tracking require assembling data from Orders, OrderItems, Payments, and Deliveries collections — every tracking poll triggers multiple reads or a complex aggregation pipeline, hurting real-time feel.
- MongoDB $lookup does not benefit from the same horizontal-shard locality as embedded documents, making sharding across services more complex.
- Cart operations (add item, update qty, recalculate totals) require coordinated reads across CartItems and MenuItems collections to validate and price, increasing latency and error surface.
- Contradicts MongoDB's document model strengths; the application ends up doing what a relational DB does natively but without SQL query planner optimizations.

## Hybrid Bounded-Context Embedding with Selective Denormalisation
Documents are shaped around service/read boundaries rather than pure aggregates or pure normalization. Restaurant document embeds MenuCategories with MenuItems as a nested array (menu is managed and read as a unit). Order document embeds OrderItems as a snapshot (name, price, qty frozen at order time) but references Payment and Delivery as separate documents, since Payment is gateway-event-driven and Delivery has its own independent lifecycle and real-time update pattern. User embeds Addresses (bounded, rarely exceeds 5-10). Cart is ephemeral: one document per (userId, restaurantId) pair with embedded item lines, TTL-indexed for automatic expiry. Reviews are a separate collection; Restaurant stores denormalised avgRating + reviewCount updated via $inc. A snapshot of key restaurant fields (name, logoUrl, estimatedDeliveryTime) is denormalised into each Order document to preserve historical accuracy.

**Pros**
- Menu browse and restaurant discovery are single-document reads; the embedded menu structure supports efficient $elemMatch queries on availability and category, and a 2dsphere index on Restaurant.location powers the geospatial delivery-radius filter (REQ-8, BR-4).
- Order items are snapshotted at placement time (correct for food delivery — prices and names must not change retroactively), keeping Order self-contained for customer history, receipts, and admin audit without joins.
- Payment and Delivery as separate documents let the payment service and dispatch service own their collections independently, matching the stated microservice architecture and independent-scaling constraint.
- Real-time delivery tracking (REQ-28) writes only to the small Delivery document (agent location, ETA, status) avoiding contention with the Order document which restaurant managers and customers also read.
- Cart TTL index automatically cleans up abandoned carts without a cron job, keeping storage lean.
- Denormalised avgRating on Restaurant is updated with an atomic $inc / recalculate on Review insert, giving fast reads for the browse/filter path (REQ-10, REQ-11, REQ-32) with only one extra write per review.
- Documents stay within practical size bounds: menus are updated infrequently and can be paginated by category; orders are bounded by the number of items in one meal; delivery docs are small.
- Addresses embedded in User (max ~10) stay well within document limits and make checkout address selection a single-document read.
- Aligns cleanly with Mongoose schema definitions shared across services as stated in the tech stack.

**Cons**
- Requires application-level coordination for the two-write review flow (insert Review + $inc on Restaurant.avgRating); a failed second write leaves the rating stale until the next review corrects it — mitigated by a retry or a Mongoose post-save hook, but no single-document atomicity.
- MenuItem price denormalised into CartItem and snapshotted into OrderItem means a price change does not retroactively update open carts — acceptable business behaviour but the application must re-validate prices at checkout time.
- Splitting Payment and Delivery into separate collections means order tracking page requires two additional reads (or a parallel Promise.all) beyond the Order document — acceptable latency trade-off but slightly more complex than full embedding.
- Restaurant menu document could grow large for ghost kitchens with 200+ items; mitigation is to structure MenuCategories as an array of objects each containing an items array, and use projection by category slug for the menu detail page.
- Requires careful index planning: compound indexes on (restaurantId, status) for order lists, 2dsphere on restaurant location, text index on restaurant name and menu item name for search (REQ-9).

## Chosen: Hybrid Bounded-Context Embedding with Selective Denormalisation
This approach is the best fit because it aligns document boundaries with actual read and write patterns rather than forcing either a monolithic aggregate or an artificial normalisation. The two dominant high-traffic paths — restaurant/menu discovery and real-time order tracking — are each served by single-document reads with no joins. The two independent operational lifecycles that have genuinely different write patterns — payment gateway events and delivery agent location updates — get their own collections, which also maps cleanly to the independently-scalable microservices architecture mandated by the constraints. OrderItem snapshotting is non-negotiable in food delivery (historical price accuracy, receipts, dispute resolution) and this model makes it natural. Cart TTL expiry handles a real operational concern with zero extra infrastructure. The avgRating denormalisation on Restaurant is a well-understood, low-risk pattern for a field that is read on every browse result card but updated only once per completed order. Compared to Aggregate-Root Embedding it avoids contention between delivery-agent writes and order-status reads on the same document; compared to Reference-Heavy Normalization it avoids the multi-collection assembly cost on the critical customer-facing browse and tracking paths. The bounded document sizes and the alignment with Mongoose schema sharing across Node.js services make it practical to implement and maintain on the MERN stack.