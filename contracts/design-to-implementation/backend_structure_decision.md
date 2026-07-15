# Backend Structure — Design Decision

## Domain-Driven Microservice Modules (per-service feature ownership)
Each independently deployable Express service (auth, catalog, ordering, payment, delivery, reviews, admin) lives in its own top-level directory under /services. Within each service the layout is flat: routes → controller → service-logic → repository (Mongoose model). Cross-cutting concerns (JWT middleware, RBAC, rate-limiting, error handler, shared Mongoose base schemas, notification client, mapping client, payment client) live in a /packages/shared library consumed by all services via Node path alias or local npm package. The API gateway config and socket.io real-time layer are separate top-level entries.

**Pros**
- Directly mirrors the NFR-15 'independently deployable services' constraint — each service folder is a self-contained deployable unit with its own package.json, Dockerfile and env config
- High-traffic services (catalog/search and ordering) can be scaled in isolation without touching auth or reviews, satisfying the gateway-plus-independent-scaling architectural constraint
- PCI DSS isolation is natural: the payment service is a hard boundary; no other service ever touches raw card data or payment Mongoose models
- Service boundaries map 1-to-1 to the four role-based portals and their data objects, making ownership and on-call responsibility unambiguous
- NFR-17 (external provider failure isolation) is enforced structurally — the mapping client lives only inside delivery, messaging client only inside notifications, payment client only inside payment
- New features for one domain (e.g. dispute management inside admin) do not require touching ordering or catalog code

**Cons**
- Highest initial scaffolding cost: each service needs its own Express bootstrap, middleware wiring, health-check, and CI pipeline entry
- The shared Mongoose models package must be versioned carefully; a schema change to Order requires coordinating ordering, delivery, admin, and payment services
- Inter-service calls (e.g. ordering service needs restaurant availability from catalog) introduce HTTP or event overhead that would be a simple import in a monolith
- Local development requires running 6-7 Node processes simultaneously, increasing developer-machine complexity
- Risk of shared-package becoming a hidden monolith: if Mongoose schemas are truly shared, a breaking schema migration still propagates across all services

## Layered Monorepo Monolith (technical-role layers, all services in one Express app)
A single Express application with strictly enforced technical layers: /src/routes, /src/controllers, /src/services, /src/repositories, /src/models (Mongoose), /src/middleware, /src/config, /src/integrations (payment, mapping, messaging), /src/sockets. Each layer is a flat namespace; file names carry the domain prefix (order.controller.js, order.service.js). The API gateway becomes a thin nginx/Kong proxy in front of this single process. Real-time Socket.IO is mounted directly on the same Express HTTP server.

**Pros**
- Lowest bootstrapping effort — one package.json, one process, one MongoDB connection pool, one deployment unit; ideal for a v1.0 launch in a single metro area
- Refactoring across domains (e.g. moving order status logic that also touches delivery) is a single-repo file move with no inter-service contracts to update
- Mongoose model sharing is trivial and safe since there is only one runtime; no schema versioning across service boundaries
- Full-stack traces in a single log stream simplify debugging during early operations
- Socket.IO real-time layer shares the same process and can emit events synchronously from the order service without a message broker

**Cons**
- Violates NFR-15 and the explicit architectural constraint that search/ordering must scale independently — the entire monolith must be scaled together, wasting resources on low-traffic admin functions
- A bug or memory leak in the admin or reviews module can crash ordering and payment for all customers, breaking NFR-13 (99.9% uptime for customer-facing ordering)
- PCI DSS audit scope bleeds across the whole codebase; every developer and deployment touches payment code, increasing compliance surface
- As the team grows, merge conflicts across the flat /services and /controllers namespaces become frequent
- Migrating to independently deployable services later (when traffic demands it) requires significant refactoring investment

## Modular Monolith with Extracted High-Traffic Services (hybrid bounded-context approach)
Three deployment units share one git monorepo under /services: (1) core-api — a single Express app owning auth, restaurant-catalog, cart, reviews, admin, and disputes with internal feature modules (each module has its own routes/, controller.js, service.js, repository.js, and *.model.js under /services/core-api/src/modules/<domain>/); (2) ordering-service — standalone Express + Socket.IO service owning the Order, Payment, and Delivery lifecycles where real-time and scaling demands are highest; (3) api-gateway — thin Express-http-proxy/Kong config. Cross-cutting packages (JWT auth, RBAC middleware, rate-limiter, error handler, notification client, mapping client, payment client, shared Mongoose base plugin) live in /packages/* and are referenced as local workspace packages (npm/yarn workspaces). Each service has its own MongoDB connection but uses the shared model definitions from /packages/db-models.

**Pros**
- Satisfies the independent-scaling constraint precisely where it matters: ordering + payment + delivery (the hot path) runs in its own process and can be horizontally scaled without touching catalog or admin
- PCI DSS audit scope is narrowed to ordering-service and the payment integration package — a small, reviewable surface
- Feature modules inside core-api give clear domain ownership without the 6-7 process local-dev overhead of full microservices; one npm start per service (2 backend processes total)
- NFR-17 failure isolation: ordering-service outage does not take down restaurant browsing or admin; catalog outage does not affect in-flight orders already placed
- Real-time Socket.IO collocated with ordering-service means order and delivery WebSocket events are emitted in-process without a message broker for v1.0
- Shared /packages/db-models with Mongoose schemas gives a single source of truth for data shapes while each service owns its own connection pool and migration cadence
- Monorepo workspace tooling (npm workspaces / turborepo) gives unified linting, testing, and CI without duplicating config six times
- Feature module structure (domain folder with own routes, controller, service, repository, model) makes it straightforward to extract a module into its own service later if load warrants it

**Cons**
- Slightly more initial setup than a pure monolith: workspace config, two Dockerfiles, gateway routing rules, and inter-service HTTP calls between core-api and ordering-service for admin order lookup
- Shared /packages/db-models still requires coordinated migrations when Order or Delivery schema changes affect both services; must enforce a backwards-compatible migration discipline
- Socket.IO in ordering-service means if the customer app is connected to a core-api load-balanced instance for catalog then switches to ordering-service for real-time tracking, the client must connect to two origins (mitigated by routing at the gateway level)
- Team must agree on and enforce module boundaries inside core-api; without discipline the modules can become coupled, defeating the purpose

## Chosen: Modular Monolith with Extracted High-Traffic Services (hybrid bounded-context approach)
QuickBite v1.0 has an explicit architectural constraint to independently scale search and ordering, a PCI DSS obligation that demands a narrow payment code surface, and a real-time WebSocket requirement tightly coupled to the order lifecycle — all of which the pure layered monolith fails to address. Full microservices satisfy those constraints but impose disproportionate operational overhead for a single-metro launch with a team that is still establishing domain boundaries. The hybrid approach extracts exactly the two high-pressure concerns (ordering + payment + delivery into ordering-service) while keeping the lower-traffic, lower-risk domains (auth, catalog, admin, reviews) as well-structured feature modules inside core-api. This gives independent scaling and PCI scope isolation where they matter most, keeps local development to two backend processes, and creates a clear extraction path for any module that later needs its own service. The monorepo workspace with /packages/db-models and shared middleware packages prevents duplication without creating a hidden runtime dependency — each service retains its own connection pool and deploy cadence.

## Resulting layout
```
package.json  — root workspace package.json defining npm workspaces for all packages and services
package-lock.json  — lockfile
.env.example  — template for all environment variables across services
.gitignore  — root gitignore
docker-compose.yml  — local dev orchestration: MongoDB, core-api, ordering-service, gateway
packages/
  db-models/
    package.json  — package descriptor — name: @quickbite/db-models
    src/
      connection.js  — creates and exports a Mongoose connection factory used by each service
      models/
        User.model.js  — Mongoose schema and model for User — embeds savedAddresses, location, agentProfile, currentLocation, notificationPreferences
        Restaurant.model.js  — Mongoose schema and model for Restaurant — embeds address, location, operatingHours, menuCategories, items (with allergen/dietary fields per NFR-5)
        Cart.model.js  — Mongoose schema and model for Cart — embeds items subdocument array
        Order.model.js  — Mongoose schema and model for Order — embeds deliveryAddress, location, items, statusHistory
        Payment.model.js  — Mongoose schema and model for Payment — embeds refunds subdocument array; no raw card fields
        Delivery.model.js  — Mongoose schema and model for Delivery — embeds restaurantLocation, deliveryLocation, agentCurrentLocation, assignmentAttempts
        Review.model.js  — Mongoose schema and model for Review — top-level collection
        Dispute.model.js  — Mongoose schema and model for Dispute — top-level collection
        PlatformConfig.model.js  — Mongoose schema and model for PlatformConfig — singleton-style collection for platform-wide settings including per-restaurant delivery radius config
        AdminAuditLog.model.js  — Mongoose schema and model for AdminAuditLog — records actor, timestamp, action, affected entity (NFR-11)
      index.js  — barrel export for all models and connection factory
  shared-middleware/
    package.json  — package descriptor — name: @quickbite/shared-middleware
    src/
      auth/
        jwt.middleware.js  — verifies JWT from Authorization header; attaches decoded user to req.user
        rbac.middleware.js  — role-based access control factory — enforces allowed roles per route (NFR-11)
      rateLimiter.js  — express-rate-limit configurations for auth and payment endpoints (NFR-12)
      requestLogger.js  — structured HTTP request logging middleware
      errorHandler.js  — global Express error-handling middleware; maps domain errors to HTTP status codes
      validate.js  — Joi/Zod schema validation middleware factory
      index.js  — barrel export
  shared-utils/
    package.json  — package descriptor — name: @quickbite/shared-utils
    src/
      jwt.utils.js  — sign and verify JWT tokens using shared secret/config
      password.utils.js  — bcrypt hash and compare helpers (NFR-9)
      pagination.utils.js  — cursor/offset pagination helpers for list endpoints
      asyncHandler.js  — wraps async route handlers to forward errors to Express error handler
      index.js  — barrel export
services/
  api-gateway/
    package.json  — dependencies: http-proxy-middleware, express, helmet, cors, express-rate-limit
    src/
      index.js  — entry point — starts gateway on configured port
      app.js  — Express app: global TLS enforcement, CORS, helmet, rate limiting, route proxying
      proxy.config.js  — maps URL path prefixes to upstream services (core-api, ordering-service) with health-check awareness
  core-api/
    package.json  — dependencies: express, mongoose, @quickbite/db-models, @quickbite/shared-middleware, @quickbite/shared-utils, socket.io (for auth status notifications), jsonwebtoken, bcrypt, nodemailer/messaging-sdk, axios
    src/
      index.js  — entry point — connects Mongoose, starts HTTP server
      app.js  — Express app factory: registers middleware, mounts feature routers
      config/
        index.js  — loads and validates environment variables (DB URI, JWT secret, messaging provider keys, mapping API key)
      modules/
        auth/
          auth.routes.js  — POST /auth/register, /auth/login, /auth/logout, /auth/verify-email, /auth/forgot-password, /auth/reset-password
          auth.controller.js  — thin handler — delegates to auth.service, returns HTTP responses
          auth.service.js  — registration, login (bcrypt verify + JWT sign), email verification token logic, password reset flow
          auth.validators.js  — Joi/Zod schemas for auth request bodies
        users/
          users.routes.js  — GET/PATCH /users/me, GET/PATCH /users/me/notification-preferences; admin: GET /users, GET /users/:id, PATCH /users/:id/status
          users.controller.js  — profile read/update, notification preferences, admin user management handlers
          users.service.js  — business logic for profile updates, address management (read/write through User model embeds), notification preference updates
          users.validators.js  — request body and param validation schemas
        restaurants/
          restaurants.routes.js  — GET /restaurants (browse/search with geo filter), GET /restaurants/:id (detail + menu); manager: PATCH /restaurants/:id/settings; admin: GET /admin/restaurants, POST /admin/restaurants (onboard), PATCH /admin/restaurants/:id, DELETE /admin/restaurants/:id
          restaurants.controller.js  — browse, search, detail, settings update, admin CRUD handlers
          restaurants.service.js  — geospatial queries, operating-hours logic, delivery radius config read from PlatformConfig or Restaurant document; all menu data accessed through Restaurant model
          restaurants.validators.js  — validation schemas for restaurant create/update
        menus/
          menus.routes.js  — POST/PATCH/DELETE /restaurants/:id/categories, POST/PATCH/DELETE /restaurants/:id/items — all mutations go through Restaurant document (embedded menuCategories and items)
          menus.controller.js  — menu category and item CRUD handlers; allergen/dietary flag management (NFR-5)
          menus.service.js  — reads and writes menuCategories/items sub-arrays inside the Restaurant aggregate via Restaurant.model; no separate Menu collection
          menus.validators.js  — item schema validation including allergen fields
        reviews/
          reviews.routes.js  — POST /reviews (submit), GET /restaurants/:id/reviews, GET /admin/reviews; admin: DELETE /reviews/:id
          reviews.controller.js  — submit review after order completion check, fetch restaurant reviews, admin moderation
          reviews.service.js  — create Review document, compute aggregated rating, admin list/remove
          reviews.validators.js  — review submission schema
        admin/
          admin.routes.js  — GET /admin/audit-logs, GET/PATCH /admin/platform-config, GET/PATCH /admin/disputes, admin user and agent onboarding endpoints
          admin.controller.js  — audit log queries, platform config management, dispute resolution, agent onboarding
          admin.service.js  — platform config CRUD via PlatformConfig model, audit log writes via AdminAuditLog model, dispute workflow via Dispute model
          admin.validators.js  — platform config and dispute update schemas
        disputes/
          disputes.routes.js  — POST /disputes (raise), GET /disputes/:id; admin routes registered in admin module
          disputes.controller.js  — raise dispute, fetch dispute detail
          disputes.service.js  — create Dispute document linked to Order; update status via admin flows
          disputes.validators.js  — dispute creation schema
        notifications/
          notifications.service.js  — sends SMS, push, and email via Messaging Provider REST client; called internally by other services — not a routed module
          messaging.client.js  — axios wrapper for Messaging Provider outbound HTTPS calls with retry and failure isolation (NFR-17)
        geocoding/
          geocoding.service.js  — wraps Mapping/Geocoding API calls for address resolution, distance/ETA, route polylines
          mapping.client.js  — axios wrapper for Mapping API outbound HTTPS calls with error isolation
    tests/
      unit/
        auth.service.test.js  — unit tests for auth service
        users.service.test.js  — unit tests for user/address logic
        restaurants.service.test.js  — unit tests for restaurant and menu service
        reviews.service.test.js  — unit tests for review logic
        admin.service.test.js  — unit tests for admin and config logic
      integration/
        auth.routes.test.js  — integration tests for auth endpoints with in-memory MongoDB
        restaurants.routes.test.js  — integration tests for browse/search/menu endpoints
        menus.routes.test.js  — integration tests for menu management via Restaurant aggregate
        reviews.routes.test.js  — integration tests for review submission and listing
  ordering-service/
    package.json  — dependencies: express, mongoose, @quickbite/db-models, @quickbite/shared-middleware, @quickbite/shared-utils, socket.io, axios
    src/
      index.js  — entry point — connects Mongoose, starts HTTP + Socket.IO server
      app.js  — Express app factory: mounts ordering, payment, delivery routers; initialises Socket.IO
      config/
        index.js  — loads env vars: DB URI, JWT secret, payment gateway keys/webhooks, mapping API key, messaging keys
      modules/
        cart/
          cart.routes.js  — GET /cart, PUT /cart (upsert), DELETE /cart — customer's active cart
          cart.controller.js  — cart read and upsert handlers
          cart.service.js  — creates or updates Cart document; validates item references against Restaurant.items embeds; no separate item collection
          cart.validators.js  — cart item array schema
        orders/
          orders.routes.js  — POST /orders (place), GET /orders/:id, GET /orders (customer history), PATCH /orders/:id/status (restaurant manager / internal); admin: GET /admin/orders, GET /admin/orders/:id
          orders.controller.js  — order placement, status update, history, admin list/detail handlers
          orders.service.js  — converts Cart to Order document (embeds deliveryAddress, items snapshot, statusHistory); emits Socket.IO events on status change; calls notification service; links to Payment and Delivery
          orders.validators.js  — order placement and status update schemas
        payments/
          payments.routes.js  — POST /payments/initiate, POST /payments/capture, POST /payments/refund, POST /payments/webhook (gateway settlement callback); admin: GET /admin/payments, GET /admin/payments/:id
          payments.controller.js  — payment initiation, capture, refund, webhook ingestion, admin list/detail
          payments.service.js  — orchestrates Payment document lifecycle; calls payment.client; stores gateway token references only (PCI-DSS — no raw card data); embeds refund sub-documents into Payment
          payment.client.js  — axios wrapper for outbound Payment Gateway HTTPS/REST calls; handles auth headers, retries, failure isolation (NFR-17)
          payments.validators.js  — payment request schemas; webhook signature verification
        deliveries/
          deliveries.routes.js  — POST /deliveries (create after order confirmed), GET /deliveries/:id, PATCH /deliveries/:id/status (agent updates), PATCH /deliveries/:id/location (agent GPS ping); admin: GET /admin/deliveries
          deliveries.controller.js  — delivery creation, agent status/location update, tracking fetch handlers
          deliveries.service.js  — creates Delivery document (embeds restaurantLocation, deliveryLocation, agentCurrentLocation, assignmentAttempts); assignment algorithm; calls geocoding service for ETA; emits real-time location events via Socket.IO (NFR-6 single-tap updates)
          deliveries.validators.js  — delivery status and location update schemas
        realtime/
          socket.manager.js  — initialises Socket.IO on the HTTP server; manages rooms per orderId; broadcasts order-status and agent-location events to subscribed customers and restaurant managers
          socket.auth.js  — authenticates Socket.IO handshake using JWT before allowing room subscription
    tests/
      unit/
        cart.service.test.js  — unit tests for cart upsert logic
        orders.service.test.js  — unit tests for order placement and status machine
        payments.service.test.js  — unit tests for payment lifecycle and refund embed logic
        deliveries.service.test.js  — unit tests for delivery assignment and location update
      integration/
        orders.routes.test.js  — integration tests for order placement flow with mocked payment client
        payments.routes.test.js  — integration tests for payment initiate/capture/webhook with mocked gateway
        deliveries.routes.test.js  — integration tests for delivery status and location update flow
```

## Notes
- Each service (core-api, ordering-service) connects to MongoDB independently with its own Mongoose connection pool; the shared @quickbite/db-models package supplies schemas/models only — it does not create connections itself.
- No SQL migrations exist; MongoDB schema evolution is handled via Mongoose schema versioning and application-level migration scripts if required.
- Embedded entities (savedAddresses, location, agentProfile, currentLocation, notificationPreferences on User; address, location, operatingHours, menuCategories, items on Restaurant; items on Cart; deliveryAddress, location, items, statusHistory on Order; refunds on Payment; restaurantLocation, deliveryLocation, agentCurrentLocation, assignmentAttempts on Delivery) have NO separate Mongoose models, collections, or repositories — all reads and writes go through the parent model.
- The menus module performs all menu category and item CRUD by querying and mutating subdocument arrays within the Restaurant aggregate — there is no separate Menu collection.
- PCI DSS compliance is enforced in payments.service.js and payment.client.js: only gateway-issued tokens are stored; the Payment model schema must not define fields for raw card numbers, CVV, or full PAN.
- Socket.IO is instantiated only in ordering-service; core-api may emit low-volume auth events but does not run a second Socket.IO server.
- The api-gateway is a thin reverse proxy (http-proxy-middleware); it is not responsible for business logic or JWT verification — each service validates tokens independently via shared-middleware.
- Rate limiting (express-rate-limit) is applied at both the gateway level (global) and at the service level on /auth/* and /payments/* routes specifically (NFR-12).
- AdminAuditLog writes should be triggered as a cross-cutting concern via a service-layer wrapper or event hook whenever a privileged administrative action succeeds, ensuring actor, timestamp, and affected entity are always captured (NFR-11).
- The delivery radius per restaurant is stored as a field inside the Restaurant document or referenced from PlatformConfig; deliveries.service.js and restaurants.service.js both read this value — coordinate how the configurable delivery radius (constraint 4) is modelled before finalising schemas.
- For the single-metro v1.0 launch, a single MongoDB replica set satisfies NFR-7 (durable committed order/payment data on single-node failure); sharding is an extraction path for future growth.
- docker-compose.yml is provided for local development only; production deployment topology (e.g. separate containers/pods per service) should be configured in a separate infra repository or Helm chart.