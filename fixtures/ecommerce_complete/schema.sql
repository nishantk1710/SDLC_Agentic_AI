-- ============================================================================
-- schema.sql — design-pack artifact D1 (owner: M2 — Data & API)
-- Sample application: e-commerce shop · PostgreSQL 16
-- ============================================================================
-- Conventions
--   * All identifiers snake_case. API layer exposes camelCase (see openapi.yaml
--     "Naming" note); the column-by-column mapping is mechanical snake↔camel.
--   * Primary keys: UUID v4 via gen_random_uuid() (built into PostgreSQL 16).
--   * Money: NUMERIC(10,2), currency USD, no floats anywhere.
--   * Timestamps: TIMESTAMPTZ, stored UTC.
--   * Every CHECK/UNIQUE constraint is named; validation-rules.json (D4)
--     references these names in its `schemaRef` fields with the exact
--     user-facing message for each violation.
--   * Requirement cross-refs (REQ-###/BR-###/NFR-###) point at
--     extracted-requirements.md (A1).
--
-- Business rules enforced here:
--   BR-001 e-mail unique per account            → users_email_unique
--   BR-003 cart quantity 1–99                   → cart_items_quantity_range
--   BR-004 order requires non-empty cart        → orders_subtotal_positive
--                                                 (an order row can only exist
--                                                 with at least one order_item)
--   BR-005 price/name snapshotted at placement  → order_items.unit_price,
--                                                 order_items.product_name
--   BR-006 flat shipping fee 5.00 per order     → orders.shipping_fee
--   BR-007 order status lifecycle               → order_status enum
--                                                 (transitions: see
--                                                 state-transitions.md, B3)
--
-- App-layer-only rules (cannot live in DDL, defined in validation-rules.json):
--   BR-002 password policy (only the bcrypt hash reaches the DB; NFR-002:
--          bcrypt cost 12)
--   BR-003 quantity may also not exceed products.stock_quantity — checked in
--          the service inside the same transaction that touches cart_items.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- users  (REQ-001 register, REQ-002 login)
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    id            UUID         NOT NULL DEFAULT gen_random_uuid(),
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,             -- bcrypt, never plaintext
    full_name     VARCHAR(100) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT users_pkey             PRIMARY KEY (id),
    CONSTRAINT users_email_unique     UNIQUE (email),                 -- BR-001
    CONSTRAINT users_email_format
        CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT users_full_name_length
        CHECK (char_length(btrim(full_name)) BETWEEN 2 AND 100)
);

-- ----------------------------------------------------------------------------
-- products  (REQ-003 browse list, REQ-004 details)
-- Catalogue is seeded/managed out of band — no admin endpoints in scope.
-- ----------------------------------------------------------------------------
CREATE TABLE products (
    id             UUID          NOT NULL DEFAULT gen_random_uuid(),
    name           VARCHAR(150)  NOT NULL,
    description    TEXT          NOT NULL DEFAULT '',
    price          NUMERIC(10,2) NOT NULL,
    stock_quantity INTEGER       NOT NULL DEFAULT 0,
    image_url      VARCHAR(500),          -- convention: /assets/products/<slug>.png
    category       VARCHAR(50)   NOT NULL,
    is_active      BOOLEAN       NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT products_pkey              PRIMARY KEY (id),
    CONSTRAINT products_name_length
        CHECK (char_length(btrim(name)) BETWEEN 1 AND 150),
    CONSTRAINT products_price_positive    CHECK (price >= 0.01),
    CONSTRAINT products_stock_nonnegative CHECK (stock_quantity >= 0)
);

CREATE INDEX idx_products_category ON products (category);
CREATE INDEX idx_products_active   ON products (created_at DESC) WHERE is_active;

-- ----------------------------------------------------------------------------
-- carts / cart_items  (REQ-005 add, REQ-006 view, REQ-007 update, REQ-008 remove)
-- Exactly one open cart per user (carts_user_unique); the cart is emptied —
-- not deleted — when an order is placed.
-- ----------------------------------------------------------------------------
CREATE TABLE carts (
    id         UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id    UUID        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT carts_pkey         PRIMARY KEY (id),
    CONSTRAINT carts_user_unique  UNIQUE (user_id),
    CONSTRAINT carts_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE cart_items (
    id         UUID        NOT NULL DEFAULT gen_random_uuid(),
    cart_id    UUID        NOT NULL,
    product_id UUID        NOT NULL,
    quantity   INTEGER     NOT NULL,
    added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT cart_items_pkey                PRIMARY KEY (id),
    CONSTRAINT cart_items_cart_product_unique UNIQUE (cart_id, product_id),
    CONSTRAINT cart_items_quantity_range      CHECK (quantity BETWEEN 1 AND 99), -- BR-003
    CONSTRAINT cart_items_cart_id_fkey    FOREIGN KEY (cart_id)
        REFERENCES carts (id) ON DELETE CASCADE,
    CONSTRAINT cart_items_product_id_fkey FOREIGN KEY (product_id)
        REFERENCES products (id) ON DELETE RESTRICT
);

CREATE INDEX idx_cart_items_cart_id ON cart_items (cart_id);

-- ----------------------------------------------------------------------------
-- orders / order_items  (REQ-009 place, REQ-010 list, REQ-011 details)
-- Lifecycle: PENDING → PAID → SHIPPED → DELIVERED; CANCELLED allowed only
-- before SHIPPED. Full transition table: state-transitions.md (B3). BR-007
-- ----------------------------------------------------------------------------
CREATE TYPE order_status AS ENUM
    ('PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED');

CREATE TABLE orders (
    id                   UUID          NOT NULL DEFAULT gen_random_uuid(),
    user_id              UUID          NOT NULL,
    order_number         VARCHAR(20)   NOT NULL,   -- human-facing, e.g. ORD-000042
    status               order_status  NOT NULL DEFAULT 'PENDING',
    subtotal             NUMERIC(10,2) NOT NULL,
    shipping_fee         NUMERIC(10,2) NOT NULL DEFAULT 5.00,       -- BR-006
    total                NUMERIC(10,2) NOT NULL,
    shipping_name        VARCHAR(100)  NOT NULL,
    shipping_line1       VARCHAR(255)  NOT NULL,
    shipping_line2       VARCHAR(255),
    shipping_city        VARCHAR(100)  NOT NULL,
    shipping_postal_code VARCHAR(20)   NOT NULL,
    shipping_country     CHAR(2)       NOT NULL,   -- ISO 3166-1 alpha-2
    placed_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT orders_pkey                     PRIMARY KEY (id),
    CONSTRAINT orders_order_number_unique      UNIQUE (order_number),
    CONSTRAINT orders_order_number_format      CHECK (order_number ~ '^ORD-[0-9]{6}$'),
    CONSTRAINT orders_subtotal_positive        CHECK (subtotal > 0),          -- BR-004
    CONSTRAINT orders_shipping_fee_nonnegative CHECK (shipping_fee >= 0),
    CONSTRAINT orders_total_consistent         CHECK (total = subtotal + shipping_fee),
    CONSTRAINT orders_shipping_name_length
        CHECK (char_length(btrim(shipping_name)) BETWEEN 2 AND 100),
    CONSTRAINT orders_shipping_postal_format
        CHECK (shipping_postal_code ~ '^[A-Za-z0-9 -]{3,20}$'),
    CONSTRAINT orders_shipping_country_format
        CHECK (shipping_country ~ '^[A-Z]{2}$'),
    CONSTRAINT orders_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX idx_orders_user_id ON orders (user_id, placed_at DESC);

CREATE TABLE order_items (
    id           UUID          NOT NULL DEFAULT gen_random_uuid(),
    order_id     UUID          NOT NULL,
    product_id   UUID          NOT NULL,
    product_name VARCHAR(150)  NOT NULL,           -- snapshot at placement, BR-005
    unit_price   NUMERIC(10,2) NOT NULL,           -- snapshot at placement, BR-005
    quantity     INTEGER       NOT NULL,

    CONSTRAINT order_items_pkey                 PRIMARY KEY (id),
    CONSTRAINT order_items_order_product_unique UNIQUE (order_id, product_id),
    CONSTRAINT order_items_quantity_min         CHECK (quantity >= 1),
    CONSTRAINT order_items_unit_price_positive  CHECK (unit_price >= 0.01),
    CONSTRAINT order_items_order_id_fkey   FOREIGN KEY (order_id)
        REFERENCES orders (id) ON DELETE CASCADE,
    CONSTRAINT order_items_product_id_fkey FOREIGN KEY (product_id)
        REFERENCES products (id) ON DELETE RESTRICT
);

CREATE INDEX idx_order_items_order_id ON order_items (order_id);

-- ----------------------------------------------------------------------------
-- updated_at maintenance
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_carts_updated_at    BEFORE UPDATE ON carts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_orders_updated_at   BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ----------------------------------------------------------------------------
-- Seed catalogue — fixed UUIDs, reused verbatim in sample-payloads.json (D5)
-- so request/response examples resolve against a freshly-seeded database.
-- ----------------------------------------------------------------------------
INSERT INTO products (id, name, description, price, stock_quantity, image_url, category, created_at) VALUES
  ('20000000-0000-4000-8000-000000000001', 'Aurora Desk Lamp',
   'Dimmable LED desk lamp with three colour temperatures and a USB charging port.',
   49.99, 120, '/assets/products/aurora-desk-lamp.png',        'Lighting',    '2026-06-15T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000002', 'Nimbus Wireless Mouse',
   'Silent-click ergonomic wireless mouse, 2.4 GHz USB receiver, 18-month battery life.',
   24.50, 200, '/assets/products/nimbus-wireless-mouse.png',   'Electronics', '2026-06-15T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000003', 'Atlas Laptop Stand',
   'Aluminium laptop stand, six height settings, folds flat for travel.',
   39.00,  75, '/assets/products/atlas-laptop-stand.png',      'Accessories', '2026-06-15T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000004', 'Terra Ceramic Mug',
   'Hand-glazed 350 ml stoneware mug, dishwasher and microwave safe.',
   14.25, 300, '/assets/products/terra-ceramic-mug.png',       'Kitchen',     '2026-06-15T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000005', 'Zephyr Mechanical Keyboard',
   'Compact 75% mechanical keyboard, hot-swappable switches, white backlight.',
   89.99,  60, '/assets/products/zephyr-mechanical-keyboard.png', 'Electronics', '2026-06-15T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000006', 'Luna Notebook Set',
   'Set of three A5 dotted notebooks, 120 gsm paper, lay-flat binding.',
   12.75, 500, '/assets/products/luna-notebook-set.png',       'Stationery',  '2026-06-15T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000007', 'Orion USB-C Hub',
   '7-in-1 USB-C hub: HDMI 4K, three USB-A ports, SD/microSD, 100 W pass-through.',
   34.99,  90, '/assets/products/orion-usb-c-hub.png',         'Electronics', '2026-06-15T09:00:00Z'),
  ('20000000-0000-4000-8000-000000000008', 'Sol Water Bottle',
   'Insulated 750 ml stainless-steel bottle, keeps drinks cold 24 h / hot 12 h.',
   19.99, 150, '/assets/products/sol-water-bottle.png',        'Kitchen',     '2026-06-15T09:00:00Z');

COMMIT;
