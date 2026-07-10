# ecommerce_missing_mandatory — broken-pack fixture (owner: M4)

A copy of `ecommerce_complete` with **two mandatory artifacts deleted**:

- `schema.sql` (handoff ID **D1**)
- `openapi.yaml` (handoff ID **D2**)

Purpose: testing the Implementation service's **manifest gate**. On this pack
the gate must REJECT with exactly `["D1", "D2"]` as the missing-ID list —
never guess, never partially proceed.

## The two manifest variants

| File | Variant | What it claims | What the gate must do |
|------|---------|----------------|------------------------|
| `index.md` | (a) honest | `[18/20 present] ❌ — missing: D1, D2` | Reject; report D1, D2 (agreement between manifest and disk). |
| `index.false-claim.md` | (b) lying | `[20/20 present] ✅` (byte-identical to the complete pack's manifest) | Reject anyway: the gate must verify files on disk, not trust the manifest. To run this case, swap the file in as `index.md` first. |

Test harness sketch:

```bash
# case (a): honest manifest
run_manifest_gate fixtures/ecommerce_missing_mandatory   # expect: REJECT, missing=[D1, D2]

# case (b): lying manifest
cd fixtures/ecommerce_missing_mandatory
mv index.md index.honest.md && mv index.false-claim.md index.md
run_manifest_gate .                                      # expect: REJECT, missing=[D1, D2]
mv index.md index.false-claim.md && mv index.honest.md index.md
```

This README is test tooling, not a design-pack artifact; the gate should
ignore files that are not in the handoff inventory.
