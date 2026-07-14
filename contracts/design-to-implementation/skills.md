## 16. Coding Guidelines
**Satisfies:** E5 (Coding Guidelines)
**Format:** `SKILL.md` (Markdown) — framed as an agent skill so the implementation agent reads it as authoritative convention.
**Contains:** the team's conventions so all generated code reads as one author.

```markdown
- Source every color, spacing, typography, border-radius, and shadow value from the shared design-token file; never hard-code hex values, px sizes, or font strings inline.
- Never log, store, or transmit raw card numbers, CVVs, or full PANs anywhere in the codebase; accept only the gateway-issued token and last-four digits.
- Enforce RBAC via a dedicated requireRole(...roles) middleware applied at the router level before every privileged route — never inline role checks inside controllers.
- Use Mongoose query builders or parameterized filter objects exclusively — never build query strings through string concatenation or template literals.
- Hash all passwords with bcrypt (minimum cost factor 12) before persistence; never store or log plaintext credentials.
- Log all administrative actions as structured JSON with fields: actorId, role, action, affectedEntityId, and ISO-8601 timestamp.
- Wrap all external provider calls (payment gateway, mapping, messaging) in a try/catch with a provider-specific error boundary so failures degrade only that feature.
- Apply express-rate-limit to all /auth/* and /payments/* route groups with environment-configurable window and max values.
```

> Conventions for MERN stack (MongoDB + Mongoose, Express.js, React SPA, Node.js) with Socket.IO, JWT/RBAC auth, PCI-DSS tokenized payments, and a shared design-token component library across four browser SPAs. Generated code must read as one author.

### Project Structure & Naming
- Name React component files and component functions in PascalCase (e.g. OrderCard.jsx); name all other JS/TS files in kebab-case (e.g. order-service.js).
- Organize each Express service as gateway → router → controller → service → repository; no business logic in routers, no DB calls in controllers.
- Place shared Mongoose schemas/models in a single @quickbite/data-access package imported by all services — never duplicate schema definitions.
- Co-locate each React feature under src/features/<feature>/ containing its components, hooks, slice, and styles; shared UI lives in src/components/.
- Name Socket.IO event constants in SCREAMING_SNAKE_CASE from a shared events.js enum file (e.g. ORDER_STATUS_UPDATED); never use bare string literals in emit/on calls.

### Components & UI
- Write all React components as named functional components with hooks — no class components.
- Source every color, spacing, typography, border-radius, and shadow value from the shared design-token file; never hard-code hex values, px sizes, or font strings inline.
- Apply responsive breakpoints using the token-defined breakpoint variables; customer and delivery-agent layouts must render correctly at mobile widths without separate components.
- Delivery-agent action buttons must be single-tap confirmable — no multi-step dialogs for in-progress status updates.
- Display allergen and dietary flags on every MenuItemCard directly from the item's data model; never suppress or omit them when the field is present.

### API & Real-Time Layer
- Every Express route handler must pass errors to next(err) — no unhandled promise rejections; use a single global error-handling middleware per service.
- Wrap all external provider calls (payment gateway, mapping, messaging) in a try/catch with a provider-specific error boundary so failures degrade only that feature.
- Enforce RBAC via a dedicated requireRole(...roles) middleware applied at the router level before every privileged route — never inline role checks inside controllers.
- Apply express-rate-limit to all /auth/* and /payments/* route groups with environment-configurable window and max values.
- Validate and sanitize all inbound request bodies with a schema-validation middleware (e.g. express-validator or Joi) before the request reaches the controller.
- All outbound HTTP calls to third-party APIs must use HTTPS endpoints only — reject any configuration specifying http://.

### Data Access & Security
- Use Mongoose query builders or parameterized filter objects exclusively — never build query strings through string concatenation or template literals.
- Never log, store, or transmit raw card numbers, CVVs, or full PANs anywhere in the codebase; accept only the gateway-issued token and last-four digits.
- Hash all passwords with bcrypt (minimum cost factor 12) before persistence; never store or log plaintext credentials.
- Sign JWTs with a secret sourced from environment variables; verify signature, expiry, and role claim in the requireRole middleware on every protected request.
- Encrypt sensitive fields at rest (e.g. PII beyond email) using the platform encryption utility — never store them as plaintext in MongoDB documents.
- Write every confirmed order and payment mutation inside a Mongoose session/transaction to guarantee durability across document collections.

### Logging, Auditing & Error Handling
- Log all administrative actions (refunds, review removal, user management) as structured JSON with fields: actorId, role, action, affectedEntityId, and ISO-8601 timestamp.
- Use a structured logger (e.g. pino or winston JSON transport) for all server-side logging — never use console.log in production code paths.
- Never log JWT payloads, passwords, raw card data, or full PII fields; redact or omit them explicitly in log serializers.
- Return RFC 7807 Problem Detail JSON ({type, title, status, detail}) from all Express error handlers — never leak stack traces to API consumers.

### Configuration & Environment
- Source all secrets, API keys, DB URIs, rate-limit thresholds, and commission rates from environment variables via a validated config module — no hard-coded values in source.
- Store restaurant delivery-radius and commission-rate values in the DB configuration collection, not in code, so they are configurable without a redeploy.
- All service-to-service and service-to-gateway communication must use TLS 1.2+ endpoints; reject connections that negotiate below TLS 1.2 at the HTTP client configuration level.

---
