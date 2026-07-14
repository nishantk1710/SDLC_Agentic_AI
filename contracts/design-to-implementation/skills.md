## 16. Coding Guidelines
**Satisfies:** E5 (Coding Guidelines)
**Format:** `SKILL.md` (Markdown) — framed as an agent skill so the implementation agent reads it as authoritative convention.
**Contains:** the team's conventions so all generated code reads as one author.

```markdown
- Every privileged route must pass through authenticate JWT middleware then authorizeRoles(...roles) RBAC middleware before any controller logic.
- Never log, persist, or pass raw card numbers, CVVs, or full PANs anywhere in the codebase; accept and store only the payment gateway token.
- Use Mongoose query builders and parameterized conditions exclusively — never concatenate user input into a query string or $where clause.
- Source every color, spacing, typography, border-radius, and shadow value from the shared design-token file — never hard-code hex values, px literals, or raw font sizes.
- Apply express-rate-limit to every /auth/* and /payments/* route at the router level; it is not sufficient to apply it globally.
- Log every administrative action as a structured audit record containing actorId, role, action, affectedEntityId, and ISO-8601 timestamp written to the audit collection.
- Store passwords exclusively as bcrypt hashes (saltRounds ≥ 12); plain-text or reversibly-encrypted passwords in any layer are forbidden.
- Wrap all external provider calls (payment, mapping, messaging) in a provider-specific error class so failures degrade only that function and never crash unrelated services.
```

> Conventions for MERN stack (MongoDB/Mongoose, Express.js, Node.js, React) with Socket.IO, JWT/RBAC auth, PCI-compliant payment tokenization, and a shared design-token component library across four browser SPAs. Generated code must read as one author.

### Project Structure & Naming
- Name React component files PascalCase (e.g. MenuItemCard.jsx); all other JS/TS files kebab-case (e.g. order-service.js).
- Organize each Express service as gateway → router → controller → service → repository; no business logic in routers or controllers.
- Place shared Mongoose schemas/models in a single shared data-access package imported by all services — never duplicate schema definitions.
- Prefix Socket.IO event name constants with the domain namespace (e.g. ORDER_STATUS_UPDATED, DELIVERY_LOCATION_CHANGED) and define them in a shared constants file.
- Co-locate each React feature under src/features/<feature>/ containing its components, hooks, and slice — no flat global components folder for feature-specific code.

### React & Component Library
- Write only functional React components with hooks; class components are forbidden.
- Source every color, spacing, typography, border-radius, and shadow value from the shared design-token file — never hard-code hex values, px literals, or raw font sizes.
- Use the shared component library for all UI primitives (buttons, inputs, modals); only extend, never rewrite, primitives inline per-feature.
- Manage all async server state with a data-fetching library (e.g. React Query or SWR); do not store server responses directly in useState or Redux.
- Mark delivery-agent tap targets with a minimum 48 × 48 px touch target enforced via design tokens; single-tap confirmation actions must require no secondary interaction.
- Gate browser Geolocation and MediaDevices/getUserMedia calls behind explicit permission prompts; handle denied/unavailable states with a visible fallback UI, never a silent failure.

### Express Services & API Design
- Every privileged route must pass through the authenticate JWT middleware then the authorizeRoles(...roles) RBAC middleware before any controller logic.
- Apply express-rate-limit to every /auth/* and /payments/* route at the router level, not globally.
- Return errors using a single centralized error-handler middleware; controllers must call next(err) — never res.send error objects directly.
- Validate and sanitize all inbound request bodies with a schema-validation library (e.g. Joi or Zod) at the router layer before the controller is invoked.
- Wrap all external provider calls (payment gateway, mapping API, messaging provider) in a try/catch with a provider-specific error class; let errors propagate as ServiceUnavailableError so failures degrade only that function.
- Expose only RESTful HTTPS endpoints; all inter-service calls go through the API gateway, never direct service-to-service HTTP.

### Data Access & MongoDB
- Use Mongoose query builders and parameterized conditions exclusively — never concatenate user input into a query string or $where clause.
- Define all collection schemas in the shared data-access package with explicit field types, required flags, and index declarations; no schemaless ad-hoc inserts.
- Use Mongoose transactions for any operation that writes to more than one collection (e.g. order + payment + inventory) to satisfy durability requirements.
- Never log, persist, or pass raw card numbers, CVVs, or full PANs anywhere in the codebase; accept and store only the payment gateway's token and last-four/brand metadata.
- Store passwords exclusively as bcrypt hashes (saltRounds ≥ 12); plain-text or reversibly-encrypted passwords in any layer are forbidden.

### Security & Compliance
- Set JWT expiry to ≤ 15 minutes for access tokens; supply a separate refresh-token flow — never extend expiry by re-signing with the same payload.
- Log every administrative action (refunds, review removal, user bans) as a structured audit record containing actorId, role, action, affectedEntityId, and ISO-8601 timestamp; write to the audit collection, never only to stdout.
- Enforce TLS 1.2+ at the API gateway and reject any inbound connection that negotiates a lower protocol version.
- Set HTTP security headers (helmet defaults) on every Express service; additionally set Content-Security-Policy, Referrer-Policy, and Permissions-Policy headers.
- Sensitive environment variables (JWT secret, payment API key, DB URI) must be injected via environment variables; committing secrets to source control is forbidden and enforced by pre-commit hook.

### Real-Time, Error Handling & Observability
- Emit Socket.IO events only from the service layer after a confirmed database write; never emit optimistically before persistence.
- All Socket.IO event handlers must authenticate the socket on connection using the same JWT middleware used by REST routes.
- Catch and handle all unhandledRejection and uncaughtException events at the Node.js process level; log structured JSON then exit — never swallow them silently.
- Emit structured JSON logs (level, timestamp, serviceId, traceId, message) from every service; do not use unstructured console.log in production paths.
- Instrument search and order-placement code paths with latency timers and emit metrics that can be compared against the 2 s / 3 s p95 SLA targets.

---
