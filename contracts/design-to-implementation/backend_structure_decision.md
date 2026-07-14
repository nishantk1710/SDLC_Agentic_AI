# Backend Structure — Design Decision

## Domain-Driven Microservices (Service-per-Bounded-Context)
Each bounded domain (auth, catalog, ordering, payment, delivery, reviews, admin) is a fully independent Express service with its own routes, controllers, service logic, Mongoose models, and outbound integration adapters. A shared npm workspace package holds cross-cutting Mongoose base schemas, JWT utilities, RBAC middleware, error types, and event contracts. The API gateway routes inbound traffic and enforces TLS termination. Socket.IO lives inside the delivery service. Each service is deployed, versioned, and scaled independently.

**Pros**
- Directly satisfies NFR-15 and the architecture constraint of independently deployable, independently scalable services — search/catalog and ordering can scale without touching auth or reviews.
- Blast radius of a failure is bounded per service, directly implementing NFR-17 (external provider failure degrades only the dependent function).
- PCI DSS scope is minimized: only the payment service touches the payment gateway adapter, making audit surface tiny.
- Teams can own a full vertical slice (auth-service, delivery-service, etc.) without merge conflicts across domains.
- MongoDB document-per-entity model maps cleanly when each service owns exactly its collections (Orders in ordering-service, Deliveries in delivery-service).
- Fits the explicitly stated gateway-plus-services topology from section 7.2.

**Cons**
- Highest operational complexity for a v1.0 single-city launch: service discovery, inter-service HTTP calls (e.g. ordering must read restaurant from catalog), distributed tracing, and shared-schema versioning all need upfront investment.
- Cross-domain queries (admin dashboard aggregating users + orders + reviews) require either a dedicated aggregation service or multiple round-trips through the gateway.
- Shared Mongoose schema package creates an implicit coupling point; schema migrations must be coordinated across services.
- WebSocket (Socket.IO) in delivery-service needs sticky sessions or a Redis pub/sub adapter if load-balanced, adding infrastructure overhead early.

## Modular Monolith with Feature Modules
A single Express application whose source tree is partitioned into feature modules — auth, users, restaurants, menus, cart, orders, payments, delivery, reviews, admin — each owning its own router, controller, service, and Mongoose models folder. Cross-cutting concerns (config, middleware/auth-jwt, middleware/rbac, middleware/rateLimit, errors, sockets, integrations/paymentGateway, integrations/mappingApi, integrations/messaging) live in top-level shared directories. The application boots from a single entry point that mounts all module routers and a Socket.IO namespace. CI pipelines can later extract modules into separate services without rewriting business logic.

**Pros**
- Single deployable unit is appropriate for a v1.0 single-city launch, drastically reducing operational overhead while still enforcing clean internal boundaries.
- Feature modules mirror the bounded contexts exactly (one folder = one domain object cluster), making it straightforward to split out a service later when scale demands it.
- Shared middleware (RBAC, rate-limit, JWT, error handler) is applied once centrally, reducing duplication and making security audits simple.
- Mongoose models live adjacent to the feature that owns them, avoiding the implicit shared-schema coupling problem of the microservices approach.
- Integrations (payment, mapping, messaging) are isolated adapter classes in /integrations, so a provider swap touches one file per integration.
- Socket.IO namespace for delivery tracking is co-located in the delivery module and registered at app bootstrap — no cross-service messaging bus needed.

**Cons**
- Entire application must be redeployed for any change, violating NFR-15 in letter (though the constraint may be aspirational at launch scale).
- High-traffic modules (search inside restaurants, order placement) cannot be scaled independently without extracting them first.
- A poorly disciplined team can bypass module boundaries (e.g. orders/service importing from payments/repository directly), eroding the clean separation over time without enforced contracts.
- Single Node.js process means a catastrophic memory leak or unhandled exception in one module can affect the whole app.

## Layered Technical Architecture with Domain Subdirectories
A classic horizontal layering: routes/ (all Express routers), controllers/ (request/response shaping), services/ (business logic), repositories/ (Mongoose data access, one file per collection), models/ (Mongoose schemas), middlewares/, integrations/, config/, and sockets/. Within each layer, files are grouped by domain (e.g. services/orderService.js, repositories/orderRepository.js). Cross-cutting auth, RBAC, rate limiting, and error handling live in middlewares/.

**Pros**
- Immediately familiar to any Express/Node.js developer; zero ramp-up time on where to find or add code.
- Clean separation of HTTP concerns (controllers) from business logic (services) from persistence (repositories) makes unit testing each layer straightforward.
- Mongoose repositories abstract query logic so swapping or sharding collections only affects the repository layer.

**Cons**
- Adding a new feature (e.g. reviews) requires touching four or five separate top-level directories simultaneously, making pull requests sprawling and code review harder.
- The structure does not reflect the domain model: understanding the full order lifecycle requires reading across routes/, controllers/, services/, and repositories/ simultaneously.
- Provides no natural boundary for future service extraction — splitting out ordering would require surgically cutting across all horizontal layers.
- Cross-domain service dependencies (orderService calling restaurantRepository) become invisible and hard to detect, leading to a tightly coupled big ball of mud over time.
- Poor alignment with the app's stated microservices-oriented architecture goal and the independently-deployable NFR-15 requirement.

## Chosen: Modular Monolith with Feature Modules
QuickBite v1.0 targets a single metropolitan area with a team that must ship quickly. A full microservices deployment topology (approach 1) carries high operational overhead — distributed tracing, inter-service auth, schema versioning, Socket.IO adapters — that is premature at this scale and risks delaying launch. The layered technical architecture (approach 3) is the simplest to start but actively works against the platform's stated goal of independent deployability and makes future service extraction painful. The modular monolith threads the needle: each of the eight feature domains (auth, users, restaurants, menus, cart, orders, payments, delivery, reviews, admin) owns its router, controller, service, and Mongoose models in a single cohesive folder, mirroring the bounded contexts that would eventually become microservices. Cross-cutting security concerns — JWT verification, RBAC middleware, rate limiting on auth and payment endpoints, centralized error handling — live in a top-level shared/middleware directory and are applied once at app bootstrap, directly satisfying NFR-8, NFR-11, and NFR-12 with minimal duplication. The three external integrations (payment gateway, mapping API, messaging provider) are isolated adapters under /integrations, limiting PCI DSS audit scope and satisfying NFR-17's fault-isolation requirement. Socket.IO delivery tracking is registered as a namespace inside the delivery module and mounted at startup, keeping real-time concerns co-located with their domain logic. When traffic in the single city grows to justify it, the ordering and catalog modules can be extracted into standalone Express services with minimal rewriting because the internal contracts are already clean.

## Resulting layout
```
src/
  app.js  — Express app factory — mounts global middleware, feature routers, Socket.IO, and error handler
  server.js  — Entry point — creates HTTP server, connects Mongoose, starts listening
  config/
    index.js  — Loads and exports all environment-validated config values (port, DB URI, JWT secret, etc.)
    cors.js  — CORS options for browser clients
    rateLimits.js  — Rate-limit configurations for auth and payment endpoints
    socket.js  — Socket.IO server init and namespace registration
  modules/
    auth/
      auth.router.js  — POST /auth/register, /auth/login, /auth/refresh, /auth/logout routes
      auth.controller.js  — Request/response handling for auth endpoints
      auth.service.js  — Registration, login, token issuance and refresh logic
      auth.validator.js  — Joi/Zod schemas for auth request bodies
      auth.test.js  — Unit and integration tests for auth module
    users/
      users.router.js  — GET/PUT /users/:id, address sub-resource routes
      users.controller.js  — Request/response handling for user profile and address operations
      users.service.js  — Profile updates, saved-address CRUD, role-specific profile resolution
      users.validator.js  — Validation schemas for user update payloads
      users.test.js  — Unit tests for users module
    restaurants/
      restaurants.router.js  — GET /restaurants (search/browse), GET /restaurants/:id, partner management routes
      restaurants.controller.js  — Request/response handling for restaurant discovery and partner ops
      restaurants.service.js  — Geo-filtered search, delivery radius checks, restaurant CRUD for managers
      restaurants.validator.js  — Validation schemas for restaurant payloads
      restaurants.test.js  — Unit tests for restaurants module
    menus/
      menus.router.js  — GET /restaurants/:id/menu, POST/PUT/DELETE menu item routes for managers
      menus.controller.js  — Request/response handling for menu browsing and management
      menus.service.js  — Menu item CRUD, availability toggling, allergen/dietary field management
      menus.validator.js  — Validation schemas for menu item payloads
      menus.test.js  — Unit tests for menus module
    cart/
      cart.router.js  — GET/PUT/DELETE /cart routes scoped to authenticated customer
      cart.controller.js  — Request/response handling for cart operations
      cart.service.js  — Add/remove items, quantity updates, cart-to-order transition logic
      cart.validator.js  — Validation schemas for cart payloads
      cart.test.js  — Unit tests for cart module
    orders/
      orders.router.js  — POST /orders, GET /orders/:id, status-update routes for all roles
      orders.controller.js  — Request/response handling for order placement and lifecycle
      orders.service.js  — Order creation from cart, status machine transitions, restaurant acceptance logic
      orders.validator.js  — Validation schemas for order payloads
      orders.test.js  — Unit and integration tests for orders module
    payments/
      payments.router.js  — POST /payments/authorize, /payments/capture, /payments/refund, /payments/webhook routes
      payments.controller.js  — Request/response handling for payment flows and gateway webhooks
      payments.service.js  — Orchestrates gateway adapter calls, persists tokenized payment records, handles refund logic
      payments.validator.js  — Validation schemas for payment request bodies
      payments.test.js  — Unit tests for payments module
    delivery/
      delivery.router.js  — GET/PUT /deliveries/:id, agent assignment and status-update routes
      delivery.controller.js  — Request/response handling for delivery management
      delivery.service.js  — Agent assignment, location updates, ETA via mapping adapter, proof-of-delivery handling
      delivery.socket.js  — Socket.IO /delivery namespace — emits real-time order and location events to customers and agents
      delivery.validator.js  — Validation schemas for delivery update payloads
      delivery.test.js  — Unit tests for delivery module
    reviews/
      reviews.router.js  — POST /orders/:id/review, GET /restaurants/:id/reviews routes
      reviews.controller.js  — Request/response handling for review submission and retrieval
      reviews.service.js  — Review creation gated on completed order, aggregate rating computation
      reviews.validator.js  — Validation schemas for review payloads
      reviews.test.js  — Unit tests for reviews module
    admin/
      admin.router.js  — Admin-only routes for users, partners, disputes, and platform config
      admin.controller.js  — Request/response handling for admin operations
      admin.service.js  — Platform-wide management logic, audit log writes, config updates
      admin.validator.js  — Validation schemas for admin request bodies
      admin.test.js  — Unit tests for admin module
  models/
    User.model.js  — Mongoose schema/model for base User (roles: customer, manager, agent, admin) with bcrypt hook
    Customer.model.js  — Mongoose discriminator/schema extension for Customer profile and saved addresses
    RestaurantManager.model.js  — Mongoose discriminator/schema extension for RestaurantManager profile
    DeliveryAgent.model.js  — Mongoose discriminator/schema extension for DeliveryAgent profile and availability
    Restaurant.model.js  — Mongoose schema/model for Restaurant including geo-point, delivery radius, and hours
    MenuItem.model.js  — Mongoose schema/model for MenuItem with allergen, dietary, and availability fields
    Cart.model.js  — Mongoose schema/model for Cart with item snapshots and reference to customer
    Order.model.js  — Mongoose schema/model for Order with status enum and embedded item snapshot
    Payment.model.js  — Mongoose schema/model for Payment storing gateway token, status, and amounts — no raw card data
    Delivery.model.js  — Mongoose schema/model for Delivery with agent ref, location history, and proof-of-delivery URL
    Review.model.js  — Mongoose schema/model for Review linked to Order and Restaurant
    PlatformConfig.model.js  — Mongoose schema/model for singleton platform configuration document
    AuditLog.model.js  — Mongoose schema/model for admin action audit log entries
  middleware/
    authenticate.js  — JWT verification middleware — attaches decoded user to req.user
    authorize.js  — RBAC factory middleware — accepts allowed roles array, enforces on req.user.role
    rateLimiter.js  — express-rate-limit instances for auth and payment route groups
    requestLogger.js  — HTTP request/response logging middleware
    errorHandler.js  — Centralized Express error handler — formats and returns consistent error responses
    notFound.js  — 404 catch-all handler for unmounted routes
    webhookRawBody.js  — Middleware to preserve raw request body for payment gateway webhook signature verification
  integrations/
    paymentGateway/
      paymentGateway.client.js  — Axios wrapper for outbound payment gateway HTTPS/REST calls
      paymentGateway.adapter.js  — Maps QuickBite domain calls (authorize, capture, refund) to gateway API contracts
      paymentGateway.webhook.js  — Parses and validates inbound settlement/refund webhook payloads
    mappingApi/
      mappingApi.client.js  — Axios wrapper for outbound mapping/geocoding HTTPS/REST calls
      mappingApi.adapter.js  — Maps domain needs (geocode address, get ETA, get polyline) to mapping API contracts
    messagingProvider/
      messagingProvider.client.js  — Axios wrapper for outbound messaging provider HTTPS/REST calls
      messagingProvider.adapter.js  — Maps domain notification events (order confirmed, status update) to provider template calls
  shared/
    constants.js  — Platform-wide enums: order statuses, roles, payment statuses, etc.
    errors.js  — Custom error classes (AppError, NotFoundError, UnauthorizedError, ValidationError, etc.)
    logger.js  — Winston/Pino logger instance shared across modules
    pagination.js  — Mongoose query helper for cursor/offset pagination
    asyncHandler.js  — Wraps async route handlers to forward errors to Express error middleware
    tokenUtils.js  — JWT sign and verify helpers using config secret
tests/
  integration/
    auth.integration.test.js  — Full HTTP integration tests for auth flows using supertest
    orders.integration.test.js  — Full HTTP integration tests for order placement and status transitions
    payments.integration.test.js  — Full HTTP integration tests for payment and webhook flows
    delivery.integration.test.js  — Full HTTP integration tests for delivery lifecycle and Socket.IO events
  fixtures/
    users.fixture.js  — Seed data factories for test users across all roles
    restaurants.fixture.js  — Seed data factories for test restaurants and menus
    orders.fixture.js  — Seed data factories for test orders and carts
  helpers/
    dbSetup.js  — Connects to in-memory MongoDB (mongodb-memory-server) before tests and tears down after
    authHelper.js  — Generates signed JWT tokens for test users of each role
.env.example  — Template of required environment variables (DB URI, JWT secret, gateway keys, mapping key, messaging key)
.eslintrc.js  — ESLint configuration for Node.js/Express codebase
.prettierrc  — Prettier formatting configuration
jest.config.js  — Jest configuration pointing at src and tests directories
package.json  — Dependencies (express, mongoose, socket.io, jsonwebtoken, bcrypt, axios, joi, express-rate-limit, winston, etc.) and npm scripts
```

## Notes
- MongoDB discriminators are suggested for Customer, RestaurantManager, and DeliveryAgent to share the users collection while maintaining role-specific fields; confirm this is preferred over separate collections.
- MenuItem is modeled as a separate collection referenced from Restaurant rather than embedded, to support efficient per-item availability updates — validate this access pattern is acceptable.
- Socket.IO is initialized in config/socket.js and the /delivery namespace is registered from delivery.socket.js at app bootstrap; a Redis adapter will be needed if horizontal scaling of the Node process is required in the future.
- The payments module applies webhookRawBody middleware only on the /payments/webhook route to satisfy payment gateway signature verification requirements without affecting other routes.
- AuditLog writes are triggered from admin.service.js for all administrative actions; confirm whether audit logging scope should extend to other privileged operations (e.g. manager menu edits).
- No SQL migrations are present because MongoDB/Mongoose is schema-optional; Mongoose schema validation serves as the data contract. A seeding script (not shown) should be added under scripts/ to bootstrap PlatformConfig and an initial admin user.
- The API gateway layer is not represented here — this tree covers the single Express application. If a gateway (e.g. nginx, AWS API Gateway, or a dedicated gateway service) is introduced, it sits in front of this service.
- Rate limiting config in config/rateLimits.js should be reviewed for appropriate window and max values before go-live on auth and payment endpoints (NFR-12).
- mongodb-memory-server is assumed for unit/integration test isolation; confirm the team has this devDependency approved.
- Proof-of-delivery photograph upload (from delivery agent camera) will require an object storage integration (e.g. S3-compatible); a placeholder adapter should be added under integrations/ when that provider is chosen.