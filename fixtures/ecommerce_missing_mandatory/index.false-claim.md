# index.md — design-pack manifest (artifact M1, owner: M4 — Standards & Assembly)

Design pack **ecommerce_complete**, version 1.0.0, assembled 2026-07-09.
Sample application: e-commerce shop (User / Product / Cart / Order).
This manifest is written last; the Implementation service's manifest gate
verifies every mandatory item below against the files actually present and
must report the exact missing handoff IDs on any mismatch.

## Artifact inventory

| # | Handoff ID(s) | File | Owner | Present |
|---|---------------|------|-------|---------|
| 1 | A1, A4, A5, E1 | extracted-requirements.md | M1 | ✅ |
| 2 | A2, B1, B4 | user-features.md | M1 | ✅ |
| 3 | A3 | glossary.md | M1 | ✅ |
| 4 | B2 | routes.json | M3 | ✅ |
| 5 | D2 | openapi.yaml | M2 | ✅ |
| 6 | D5 | sample-payloads.json | M2 | ✅ |
| 7 | B3 | state-transitions.md | M3 | ✅ |
| 8 | C1, C2, C3, C5 | mockup.html | M3 | ✅ |
| 9 | C6 | tokens.json | M3 | ✅ |
| 10 | D1 | schema.sql | M2 | ✅ |
| 11 | D3 | api-mapping.csv | M3 | ✅ |
| 12 | D4 | validation-rules.json | M2 | ✅ |
| 13 | E2 | .env.example | M4 | ✅ |
| 14 | C4 | assets/ (logo.svg, 12 icons, 8 product images, assets-manifest.md) | M3 | ✅ |
| 15 | E4-FE | frontend-structure.json | M4 | ✅ |
| 16 | E4-BE | backend-structure.json | M4 | ✅ |
| 17 | E3 | architecture.md | M4 | ✅ |
| 18 | E5 | SKILL.md | M4 | ✅ |
| 19 | E6 | repository.json | M4 | ✅ |
| 20 | M1 | index.md (this file) | M4 | ✅ |

## Cross-file consistency (verified at assembly, 2026-07-09)

- Every REQ/NFR/BR ID used in any artifact is defined in
  extracted-requirements.md (26 IDs: REQ-001…012, NFR-001…007, BR-001…007). ✅
- Every route in routes.json has a screen section in mockup.html and rows in
  api-mapping.csv. ✅
- Every operationId/endpoint in api-mapping.csv exists in openapi.yaml
  (11 operations). ✅
- Every field in validation-rules.json carries a schemaRef consistent with
  schema.sql (schema executed clean on PostgreSQL 16, constraints verified). ✅
- Every colour/spacing/font in mockup.html resolves to tokens.json (zero
  stray hex values). ✅
- Every seed `image_url` in schema.sql resolves to a file in assets/products/. ✅
- Exact validation messages appear verbatim in mockup.html error states
  (NFR-007 spot-checked). ✅

## Reading order for implementers

extracted-requirements.md → glossary.md → user-features.md → schema.sql →
openapi.yaml (+ sample-payloads.json) → validation-rules.json → routes.json →
state-transitions.md → tokens.json → mockup.html (+ assets) → api-mapping.csv →
architecture.md → frontend/backend-structure.json → repository.json →
.env.example → SKILL.md.

Mandatory check: [20/20 present] ✅
