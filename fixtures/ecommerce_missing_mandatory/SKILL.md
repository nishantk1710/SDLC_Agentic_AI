# SKILL.md — design-pack artifact E5 (owner: M4 — Standards & Assembly)

Coding guidelines for generating the e-commerce shop from this design pack.
These rules bind the Implementation service (and any human contributor). When
a rule here conflicts with a data artifact (schema.sql, openapi.yaml,
validation-rules.json, tokens.json), **the data artifact wins**.

## 1 · Source-of-truth precedence

1. schema.sql — database shape; entities/migrations must mirror it exactly.
2. openapi.yaml — endpoint paths, verbs, status codes, payload shapes, operationIds.
3. validation-rules.json — every rule and its exact message text (NFR-007).
4. tokens.json — every colour/spacing/radius/type value in the UI.
5. routes.json / mockup.html — screens, layout, interaction behaviour.
6. This file — style and structure.

Never invent endpoints, fields, columns, colours, or messages that are not in
the pack. If something seems missing, it is a design-pack bug: report it,
don't improvise.

## 2 · TypeScript (both apps)

- `strict: true`, no `any` (use `unknown` + narrowing), no non-null `!` unless
  provably safe with a comment.
- Named exports only; no default exports.
- Files: components `PascalCase.tsx`, hooks `useX.ts`, everything else
  `camelCase.ts`. One React component per file.
- Interfaces for object shapes; wire types mirror openapi.yaml names exactly
  (camelCase on the wire ↔ snake_case in DB; conversion only at the ORM edge).

## 3 · API & errors

- Base path `/api/v1`. Controllers implement openapi.yaml operations 1:1 —
  same paths, verbs, and status codes; operationId becomes the handler name.
- All failures use the ErrorResponse envelope with a registered code
  (validation-rules.json `errorCodes`). Field failures → 400
  `VALIDATION_ERROR` with `details[]` carrying the exact messages.
- Ownership scoping: cart/order lookups always filter by the JWT user id;
  a miss is 404 `NOT_FOUND` — never 403, never a different message.
- Cart mutations return the full updated Cart; clients render from the
  response and never recompute totals.

## 4 · Money & time

- Money is `NUMERIC(10,2)` USD. No floating-point arithmetic on amounts:
  compute in the database or on integer cents; serialize as numbers with
  exactly 2 decimals; render with `formatMoney` (lib/format.ts) only.
- Timestamps are `TIMESTAMPTZ` stored UTC, serialized ISO-8601 (`...Z`), and
  formatted only at the UI edge.

## 5 · Security

- bcrypt cost 12 (NFR-002); plaintext passwords never logged nor returned.
- JWT: 3600 s expiry (NFR-001); secret from `JWT_SECRET` env only. No secrets
  in code or fixtures — `.env.example` carries placeholders.
- All input validated server-side per validation-rules.json regardless of any
  client-side checks; use parameterized queries only (ORM defaults).
- Login failure is always the single message "Invalid email or password."
  regardless of cause.

## 6 · Frontend behaviour

- Styling exclusively via Tailwind classes generated from tokens.json — raw
  hex/px values in components are a review blocker.
- Every data screen implements the four async states (loading / success /
  empty / error) per state-transitions.md §4.
- Interactions follow mockup.html annotations: hover darken 8% (precomputed
  hover tokens), click scale 0.98, submit buttons spinner+disabled while
  pending, success toasts auto-dismiss 3000 ms, modals fade+slide-up 200 ms.
- Accessibility (NFR-006): every input has a `<label>`, interactive elements
  are keyboard-reachable with the focusRing token visible, icons get
  `aria-label`s, modals trap focus and close on Escape.

## 7 · Traceability

- Implementation sites of a requirement or rule carry a comment with the ID:
  `// BR-003: merged quantity may not exceed stock`.
- Tests reference acceptance criteria: `it('AC-05.3 rejects add beyond stock')`.
- PR descriptions list the REQ/BR/NFR IDs they implement.

## 8 · Testing

- Backend: unit tests for every service branch that can produce a distinct
  error code; e2e (supertest) covering each acceptance criterion in
  user-features.md §3.
- Frontend: Vitest for lib/ and ui components; Playwright for the six B1
  flows (register, login, browse→add, cart, checkout, orders).
- Tests seed with the fixed-UUID products from schema.sql so assertions can
  use stable ids/amounts (e.g. subtotal 63.25 → total 68.25).

## 9 · Git & reviews

- Conventional Commits (`feat:`, `fix:`, `test:`, `chore:`); reference IDs in
  the body. Branch names `feature/<req-id>-<slug>`.
- CI gate: typecheck + lint + unit + e2e must pass; no direct pushes to
  protected branches (repository.json).
- Renaming anything defined in the pack (endpoint, field, column, token,
  message) requires a design-pack change first — code follows the pack, never
  the reverse.
