# Backend Structure — Design Decision

## Domain-Driven Microservices with Shared Kernel
Each independently deployable Express service owns its own routes, controllers, service logic, Mongoose models, and third-party adapter calls, grouped by business domain: auth-service, restaurant-service, order-service, payment-service, delivery-service, review-service, notification-service, admin-service, and search-service. A shared npm workspace package (shared-kernel) exports common Mongoose base schemas, JWT middleware, RBAC helpers, error classes, and validation utilities consumed by all services. A separate api-gateway entry point handles routing, rate-limiting, and token verification before proxying to the correct service.

**Pros**
- Directly satisfies NFR-15 and the architectural constraint that search and ordering scale independently — each service is truly isolated and deployable without touching others.
- Payment service can be PCI-scoped in isolation, minimising the audit surface for PCI DSS v4.0 compliance (NFR-10).
- External provider failures (payment, mapping, messaging) are naturally contained within their owning service, directly satisfying NFR-17.
- WebSocket (Socket.IO) namespace for real-time delivery tracking lives entirely inside delivery-service, keeping stateful concerns localised.
- Teams can own a single service end-to-end; auth, ordering, and search teams work in parallel with minimal merge conflicts.
- Each service can have its own MongoDB Atlas cluster or collection set, enabling independent schema evolution.

**Cons**
- High initial scaffolding cost — nine services plus a gateway and a shared-kernel package is a lot of boilerplate for a v1.0 single-city launch.
- Cross-service data consistency (e.g. order references a restaurant and a user from different services) requires careful design — either denormalisation into each document or inter-service HTTP calls that add latency and coupling.
- The shared Mongoose models in shared-kernel create a hidden tight coupling: a schema change forces coordinated releases across every service that imports it, partially negating the independence benefit.
- Operational complexity (service discovery, inter-service auth, distributed logging, health checks) is non-trivial to set up and maintain at an early-stage product.
- Running nine Node processes locally during development is resource-intensive and slows developer feedback cycles.

## Monolithic Layered Architecture (MVC + Service + Repository)
A single Express application with strict horizontal layers: routes → controllers → services → repositories → Mongoose models. Cross-cutting concerns (auth middleware, RBAC, rate-limit, error handling, Socket.IO hub, third-party adapters) live in dedicated top-level folders (middleware/, adapters/, config/, utils/). All Mongoose schemas are co-located in a models/ directory. The four role portals share the same process, differentiated only by RBAC middleware guards on their route groups.

**Pros**
- Fastest to build and iterate at v1.0 single-city scope — one codebase, one deployment, straightforward local development.
- No inter-service network calls; all data access goes through in-process repository calls, keeping queries simple and latency low.
- MongoDB document model with Mongoose fits a layered monolith well — each collection maps to a model file and a repository class with no cross-service schema sharing concerns.
- Single Socket.IO instance trivially supports real-time order and delivery events across all connected clients.
- Easier to enforce consistent RBAC, audit logging (AdminAuditLog), and rate-limiting in a single middleware chain.

**Cons**
- Violates the explicit architectural constraint requiring independently deployable services for search and ordering scalability; horizontal scaling means replicating the entire monolith.
- As the codebase grows across four portals and nine domain objects, the shared layers (especially services/ and models/) become large and cognitively expensive to navigate.
- Any change to a high-risk area (payment adapter, auth middleware) requires a full redeploy of the platform, increasing blast radius.
- PCI DSS scoping is harder — the entire monolith is in scope rather than just an isolated payment service.
- NFR-17 (provider failure isolation) must be achieved entirely through software patterns (circuit breakers, try/catch boundaries) with no process-level isolation.

## Feature-Modular Monorepo (Modular Monolith with Deployment Seams)
A single Node.js monorepo (e.g. pnpm workspaces) containing one deployable Express application whose internals are partitioned into feature modules — auth, restaurants, menus, cart, orders, payments, delivery, reviews, notifications, admin — each module owning its router, controller, service, Mongoose models/repositories, and any module-specific adapter wrappers inside its own directory. Cross-cutting concerns (config, JWT/RBAC middleware, error handling, Socket.IO setup, shared Mongoose connection, base adapter clients) live in a top-level shared/ package. The gateway is a thin Express entry point that mounts each module's router. Because module boundaries are strictly enforced (no module imports another module's internals directly — only through exported service interfaces), the seams exist to extract a module into a true microservice later without rewrites.

**Pros**
- Balances v1.0 delivery speed with the architectural constraint: the entire app runs as one process today but the module boundaries make it straightforward to split high-traffic modules (orders, search) into separate services when traffic demands it, satisfying NFR-15 without premature complexity.
- Each feature module is self-contained — its Mongoose schema, business rules, and adapter calls are co-located, making the code easy to find and own by a small team without monolithic layer sprawl.
- RBAC middleware, rate-limiting, audit logging (AdminAuditLog), and PCI-adjacent payment adapter code each live in exactly one place (shared/ or the payments module), making security NFRs straightforward to audit.
- Single Socket.IO instance is simple to configure in shared/ and injected into the delivery module for real-time tracking, avoiding the distributed WebSocket complexity of full microservices.
- MongoDB document model maps cleanly — each module owns its Mongoose models and can embed related sub-documents (e.g. Menu items inside Restaurant) without cross-service schema leakage.
- One deployment pipeline, one set of environment variables, and one local dev server for v1.0; module extraction later requires only adding a new service entry point and an API gateway rule, not rewriting business logic.
- Admin portal concerns (audit log, platform config, disputes) are cleanly isolated in the admin module without polluting other modules.

**Cons**
- Requires discipline to enforce module boundaries in JavaScript/TypeScript — without tooling (e.g. ESLint import rules or NX boundary checks) developers will inadvertently cross-import between modules, eroding the architecture over time.
- Still a single process: a catastrophic bug in one module (e.g. a memory leak in order processing) can degrade the entire application until extraction is done.
- The shared/ package can become a dumping ground for miscellaneous utilities if not actively governed, recreating the 'big ball of mud' problem inside a different folder.
- Slightly more initial structure than a pure layered monolith, which could slow the very earliest days of development before the team has established the module scaffold pattern.

## Chosen: Feature-Modular Monorepo (Modular Monolith with Deployment Seams)
QuickBite v1.0 is a single-city launch with a small team that needs to move fast, yet the explicit architectural constraint demands independently scalable services for search and ordering, and NFR-15 requires that a change to one service not force a full redeploy. Full microservices satisfy scalability but impose enormous operational and scaffolding overhead for a first release, and the shared Mongoose schema problem negates much of the independence. A pure layered monolith is fastest to start but directly violates the scaling constraint and makes PCI scoping harder. The feature-modular approach threads the needle: each domain (auth, restaurants, orders, payments, delivery, reviews, notifications, admin) is a self-contained module with its own router, service, Mongoose models, and adapter wrappers, all enforced by strict import boundaries. The entire platform ships as one deployable Express process for v1.0, giving fast iteration and simple Socket.IO real-time delivery tracking. When order or search traffic demands independent scaling, the module's index exports are already the seam — a new Express entry point mounts only that module's router and the API gateway adds one routing rule, with zero business logic rewritten. Security NFRs (RBAC, rate-limiting, audit logging, PCI-scoped payment adapter) live in shared/ and the payments module respectively, keeping the audit surface small and the enforcement uniform.

## Resulting layout
```
package.json  — root dependencies and npm scripts (start, dev, test, lint)
package-lock.json  — locked dependency tree
.env.example  — documented environment variable template
.eslintrc.js  — ESLint config enforcing import boundaries between modules
.prettierrc  — code style config
jest.config.js  — Jest root config with per-module test projects
Dockerfile  — production container image definition
docker-compose.yml  — local dev stack: app + MongoDB
src/
  server.js  — Express app factory — mounts API gateway router, Socket.IO, and graceful-shutdown logic
  app.js  — creates and exports the configured Express application instance
  socket.js  — Socket.IO server initialization and room/event registration for order and delivery updates
  config/
    index.js  — centralised config loader — reads and validates env vars via joi/zod, exports typed config object
    db.js  — Mongoose connection factory with retry logic and connection-event logging
    rateLimiter.js  — express-rate-limit presets (auth, payment, general API)
  shared/
    models/
      User.model.js  — Mongoose schema/model for User (all roles, bcrypt password hook, role enum)
      Restaurant.model.js  — Mongoose schema/model for Restaurant (location, delivery radius, hours, status)
      Menu.model.js  — Mongoose schema/model for Menu categories and items (allergens, dietary flags, availability)
      Cart.model.js  — Mongoose schema/model for Cart (userId ref, line items, expiry TTL index)
      Order.model.js  — Mongoose schema/model for Order (status state machine, embedded snapshot of items and prices)
      Payment.model.js  — Mongoose schema/model for Payment (gateway token, status, no raw card fields)
      Delivery.model.js  — Mongoose schema/model for Delivery (agentId ref, status, location history, ETA)
      Review.model.js  — Mongoose schema/model for Review (orderId ref, ratings, text, moderation status)
      PlatformConfig.model.js  — Mongoose schema/model for PlatformConfig (singleton-style key-value operational settings)
      AdminAuditLog.model.js  — Mongoose schema/model for AdminAuditLog (actor, action, entity, timestamp, diff)
    middleware/
      authenticate.js  — JWT verification middleware — attaches decoded user to req.user
      authorize.js  — RBAC middleware factory — authorize(roles[]) returns Express middleware
      auditLog.js  — middleware/helper that writes AdminAuditLog entries for privileged mutations
      rateLimiters.js  — exports named rate-limiter middleware instances from config/rateLimiter.js
      requestLogger.js  — HTTP request/response logger (morgan or pino-http)
      errorHandler.js  — global Express error-handling middleware — formats and returns RFC 7807 errors
      notFound.js  — catch-all 404 handler mounted after all routers
      validateBody.js  — generic request-body validation middleware factory wrapping Joi/Zod schemas
    utils/
      jwt.js  — sign and verify JWT access and refresh tokens
      password.js  — bcrypt hash and compare helpers
      paginate.js  — MongoDB skip/limit pagination helper
      asyncHandler.js  — wraps async route handlers to forward errors to next()
      ApiError.js  — custom error class with HTTP status code and error code fields
      ApiResponse.js  — standard success response envelope helper
      logger.js  — pino/winston logger singleton
    adapters/
      paymentGateway.js  — outbound adapter for Payment Gateway REST API (authorize, capture, refund, webhook verify)
      mappingApi.js  — outbound adapter for Mapping/Geocoding REST API (geocode, distanceETA, routePolyline)
      messagingProvider.js  — outbound adapter for Messaging Provider REST API (sendSMS, sendPush, sendEmail)
  modules/
    auth/
      auth.router.js  — Express router: POST /register, POST /login, POST /logout, POST /refresh-token, POST /forgot-password, POST /reset-password, GET /verify-email
      auth.controller.js  — request/response handling for all auth endpoints
      auth.service.js  — registration, login, token lifecycle, email-verification, and password-reset business logic
      auth.validation.js  — Joi/Zod schemas for register, login, reset-password request bodies
    users/
      users.router.js  — Express router: GET/PATCH /me, GET/POST/PUT/DELETE /me/addresses (customer profile and saved addresses)
      users.controller.js  — request/response handling for profile and address management
      users.service.js  — profile read/update and address CRUD business logic
      users.validation.js  — Joi/Zod schemas for profile and address request bodies
    restaurants/
      restaurants.router.js  — Express router: GET / (browse+filter), GET /search, GET /:id, GET /:id/menu — customer-facing; PATCH /:id and settings routes for managers
      restaurants.controller.js  — request/response handling for restaurant and menu browsing and partner settings
      restaurants.service.js  — geo-filtered restaurant listing, search, menu retrieval, delivery-radius logic, and partner settings updates
      restaurants.validation.js  — Joi/Zod schemas for search query params and settings update bodies
    menu/
      menu.router.js  — Express router: POST/PUT/DELETE /restaurants/:id/categories and /categories/:catId/items — restaurant-manager menu management
      menu.controller.js  — request/response handling for category and item CRUD
      menu.service.js  — menu category and item create, update, delete, and availability-toggle business logic
      menu.validation.js  — Joi/Zod schemas for category and item request bodies (including allergens)
    cart/
      cart.router.js  — Express router: GET /cart, PUT /cart, DELETE /cart, POST /cart/items, PATCH /cart/items/:itemId, DELETE /cart/items/:itemId
      cart.controller.js  — request/response handling for cart operations
      cart.service.js  — cart read, upsert, and item manipulation; price re-validation against current menu on checkout
      cart.validation.js  — Joi/Zod schemas for cart and item request bodies
    orders/
      orders.router.js  — Express router: POST / (place order), GET / (history), GET /:id, PATCH /:id/status — served for customer, restaurant-manager, and admin roles
      orders.controller.js  — request/response handling for order placement, status updates, and history
      orders.service.js  — order creation from cart snapshot, status-machine transitions, order-queue logic for restaurants, real-time Socket.IO event emission
      orders.events.js  — Socket.IO event names and room helpers for order status broadcasts
      orders.validation.js  — Joi/Zod schemas for place-order and status-update request bodies
    payments/
      payments.router.js  — Express router: POST /payments/initiate, POST /payments/confirm, POST /payments/:id/refund, POST /payments/webhook (gateway callback)
      payments.controller.js  — request/response handling for payment initiation, confirmation, refund, and webhook ingestion
      payments.service.js  — orchestrates gateway adapter calls, persists Payment document (tokens only), links payment to order, issues refunds
      payments.validation.js  — Joi/Zod schemas for payment request bodies; webhook signature verification
    delivery/
      delivery.router.js  — Express router: GET /delivery/jobs (agent queue), PATCH /delivery/:id/status, POST /delivery/:id/location, GET /delivery/:id (tracking detail), POST /delivery/:id/proof
      delivery.controller.js  — request/response handling for delivery assignment, status updates, location pings, and proof-of-delivery upload
      delivery.service.js  — delivery-agent assignment, status transitions, ETA recalculation via mapping adapter, location history persistence, single-tap status update logic
      delivery.events.js  — Socket.IO event names and room helpers for live delivery location broadcasts
      delivery.validation.js  — Joi/Zod schemas for status update and location ping request bodies
    reviews/
      reviews.router.js  — Express router: POST /reviews (submit), GET /restaurants/:id/reviews, GET /reviews (admin list)
      reviews.controller.js  — request/response handling for review submission and listing
      reviews.service.js  — review eligibility check (completed order), persistence, and moderation-flag logic
      reviews.validation.js  — Joi/Zod schemas for review submission body
    notifications/
      notifications.service.js  — internal service consumed by other modules — composes and dispatches SMS, push, and email via messaging adapter; handles receipt logging and failure isolation
      notifications.templates.js  — message template definitions for all platform notification events
    admin/
      admin.router.js  — Express router: dashboard stats, restaurant CRUD and onboarding, user management, order and payment oversight, dispute management, review moderation, delivery-agent management, platform config, and audit-log endpoints — all guarded by authorize(['admin'])
      admin.controller.js  — request/response handling for all admin operations
      admin.service.js  — admin business logic: aggregate dashboard metrics, dispute resolution, restaurant approval, platform config reads and writes, audit-log queries
      admin.validation.js  — Joi/Zod schemas for admin request bodies (onboard restaurant, resolve dispute, update config)
  routes/
    index.js  — API gateway router — mounts all module routers under /api/v1 with appropriate path prefixes
tests/
  unit/
    auth.service.test.js  — unit tests for auth service (registration, token logic, password reset)
    orders.service.test.js  — unit tests for order placement and status-machine transitions
    payments.service.test.js  — unit tests for payment orchestration and webhook handling
    delivery.service.test.js  — unit tests for agent assignment and ETA logic
    cart.service.test.js  — unit tests for cart price re-validation
  integration/
    auth.routes.test.js  — integration tests for auth API endpoints using supertest + in-memory MongoDB
    restaurants.routes.test.js  — integration tests for restaurant and menu browse endpoints
    orders.routes.test.js  — integration tests for order placement flow
    payments.webhook.test.js  — integration tests for webhook ingestion and signature verification
    admin.routes.test.js  — integration tests for admin-only endpoints and RBAC enforcement
  fixtures/
    users.fixture.js  — reusable test user documents for all roles
    restaurants.fixture.js  — reusable test restaurant and menu documents
    orders.fixture.js  — reusable test order documents
  helpers/
    dbSetup.js  — mongodb-memory-server lifecycle helpers for integration tests
    jwtHelper.js  — generates signed test JWTs for each role
```

## Notes
- Each module is a self-contained vertical slice (router → controller → service → shared models). To extract a module into a standalone Express process for independent scaling, add a new entry point that imports only that module's router and the shared middleware — no business logic changes required.
- All Mongoose models live in shared/models/ and are imported by whichever modules need them; this mirrors the 'shared data-access layer' called out in the architecture and avoids duplication while keeping module services focused.
- The payments module never stores raw card data; Payment.model.js holds only gateway tokens and status fields, satisfying PCI DSS scoping.
- Socket.IO rooms follow the pattern order:{orderId} and delivery:{deliveryId}; the orders and delivery modules emit events from their service layer after persisting state changes.
- Rate limiting presets in config/rateLimiter.js are applied per-router in the auth and payments routers, and the shared rateLimiters.js middleware exports them for easy mounting.
- The auditLog middleware in shared/middleware/ is applied selectively to admin-router mutating endpoints and writes AdminAuditLog documents synchronously before responding, satisfying NFR-11.
- The notifications module is intentionally internal (no router); other modules import notifications.service.js directly. External provider failures are caught and logged within the adapter, isolating them from the calling module (NFR-17).
- Proof-of-delivery photo uploads (Delivery Agent) should be routed through a multipart handler in delivery.controller.js and stored in cloud object storage (e.g. S3); a presigned-URL approach is recommended so binary data never passes through the Express process in production.
- docker-compose.yml spins up a local MongoDB replica set (single node) to support Mongoose transactions, which are used in the order-placement and payment-confirmation flows to ensure atomicity (NFR-7).
- The .eslintrc.js should use eslint-plugin-import with restricted paths to prevent cross-module direct imports (e.g. orders module must not import from payments service directly; inter-module calls go through the service layer).