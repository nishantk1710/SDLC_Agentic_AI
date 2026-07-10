# assets-manifest.md — design-pack artifact C4 (owner: M3 — UI & Frontend)

Inventory of every binary/vector asset in `assets/`. All assets are original
SVG placeholder art created for this fixture (icon geometry follows the MIT-
licensed Feather Icons set). **No external requests, fonts, or stock imagery.**
All colours resolve to tokens.json: #2563EB primary, #1A1A1A text,
#6B7280 textSecondary, #F9FAFB surfaceAlt, #E5E7EB border.

## Logo

| File | Size | Usage |
|------|------|-------|
| `logo.svg` | 140×32 | App header (all screens), links to `/`. Shopping-bag mark in primary + "ShopKit" wordmark in text colour. |

## Icons (`assets/icons/`)

24×24, `viewBox="0 0 24 24"`, `stroke="currentColor"`, stroke-width 2, no fill.
They inherit the surrounding text colour — hover/disabled colouring comes free
from the button/link styles.

| File | Usage |
|------|-------|
| `cart.svg` | Header cart link (with itemCount pill), empty-cart state |
| `user.svg` | Header account affordance (logged-in indicator) |
| `search.svg` | Products sidebar search input |
| `menu.svg` | Hamburger — Mobile nav + Mobile "Filters & sort" toggle (NFR-005) |
| `close.svg` | Modal close, drawer close, dismissable toast |
| `plus.svg` | Quantity stepper increase |
| `minus.svg` | Quantity stepper decrease |
| `trash.svg` | Cart line remove (opens confirm modal) |
| `chevron-left.svg` | Pagination previous, breadcrumb back |
| `chevron-right.svg` | Pagination next, order-row affordance |
| `check-circle.svg` | Success toast, order-confirmation banner, in-stock indicator |
| `alert-circle.svg` | Error toast/banner, field error indicator |

## Product images (`assets/products/`)

400×300 placeholders, one per seeded product. The API serves their paths in
`Product.imageUrl` (see schema.sql seed — paths match these files exactly).

| File | Product (seed UUID suffix) |
|------|----------------------------|
| `aurora-desk-lamp.svg` | Aurora Desk Lamp (…0001) |
| `nimbus-wireless-mouse.svg` | Nimbus Wireless Mouse (…0002) |
| `atlas-laptop-stand.svg` | Atlas Laptop Stand (…0003) |
| `terra-ceramic-mug.svg` | Terra Ceramic Mug (…0004) |
| `zephyr-mechanical-keyboard.svg` | Zephyr Mechanical Keyboard (…0005) |
| `luna-notebook-set.svg` | Luna Notebook Set (…0006) |
| `orion-usb-c-hub.svg` | Orion USB-C Hub (…0007) |
| `sol-water-bottle.svg` | Sol Water Bottle (…0008) |

## Serving convention

The frontend serves `assets/` statically at the site root, so
`imageUrl: /assets/products/<slug>.svg` and
`<img src="/assets/icons/cart.svg">` resolve without a build step.
In the Vite app the folder is copied to `public/assets/` (see
frontend-structure.json). Icons are typically inlined as React components
instead (SVGR) — both approaches are acceptable; paths must not change.
