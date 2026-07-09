# index.md — design-pack manifest (artifact M1, owner: M4 — Standards & Assembly)

Design pack **ecommerce_missing_mandatory**, version 1.0.0, assembled 2026-07-09.
Sample application: e-commerce shop (User / Product / Cart / Order).
⚠ This pack is INCOMPLETE: two mandatory artifacts are absent. The
Implementation service's manifest gate must reject this pack and return the
exact missing handoff IDs listed below.

## Artifact inventory

| # | Handoff ID(s) | File | Owner | Present |
|---|---------------|------|-------|---------|
| 1 | A1, A4, A5, E1 | extracted-requirements.md | M1 | ✅ |
| 2 | A2, B1, B4 | user-features.md | M1 | ✅ |
| 3 | A3 | glossary.md | M1 | ✅ |
| 4 | B2 | routes.json | M3 | ✅ |
| 5 | D2 | openapi.yaml | M2 | ❌ MISSING |
| 6 | D5 | sample-payloads.json | M2 | ✅ |
| 7 | B3 | state-transitions.md | M3 | ✅ |
| 8 | C1, C2, C3, C5 | mockup.html | M3 | ✅ |
| 9 | C6 | tokens.json | M3 | ✅ |
| 10 | D1 | schema.sql | M2 | ❌ MISSING |
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

Mandatory check: [18/20 present] ❌ — missing: D1 (schema.sql), D2 (openapi.yaml)
