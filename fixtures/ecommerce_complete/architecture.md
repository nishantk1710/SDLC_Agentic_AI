# architecture.md — design-pack artifact E3 (owner: M4 — Standards & Assembly)

System architecture for the e-commerce shop. Stack is fixed (E1): React 18 +
TypeScript + Vite + Tailwind · Node 20 + NestJS REST · PostgreSQL 16 · JWT.

---

## 1 · System context

```mermaid
flowchart LR
    U[Shopper's browser] -->|HTTPS| FE["React SPA<br/>(Vite build, static hosting)<br/>:5173 dev"]
    FE -->|"REST JSON · /api/v1<br/>Authorization: Bearer JWT"| BE["NestJS API<br/>Node 20 · :3000"]
    BE -->|SQL · TypeORM| DB[("PostgreSQL 16<br/>ecommerce db<br/>:5432")]
    FE -.->|"/assets/*.svg (static)"| FE
```

- The SPA is fully static after build; all data flows through the REST API
  described in openapi.yaml (D2).
- The API is stateless (NFR-001 JWTs carry the session); horizontal scaling
  needs no session store.
- Assets (logo/icons/product images) are served statically by the frontend
  host from `public/assets/` (see assets-manifest.md).

## 2 · Module view

```mermaid
flowchart TB
    subgraph SPA [React SPA — frontend-structure.json]
        pages[pages/ 9 routes] --> features[features/]
        features --> ui[components/ui]
        pages --> api[api/ fetch layer]
        api --> authctx[auth/ JWT context]
    end
    subgraph API [NestJS — backend-structure.json]
        authm[auth module] --> usersm[users module]
        cartm[cart module] --> productsm[products module]
        ordersm[orders module] --> cartm
        ordersm --> productsm
        common[common: exception filter,<br/>validation pipe, jwt guard]
    end
    api -->|/auth /products /cart /orders| API
    API --> DBT[(6 tables — schema.sql)]
```

## 3 · Key sequence — checkout (REQ-009; BR-003/004/005/006)

```mermaid
sequenceDiagram
    participant B as Browser (CheckoutPage)
    participant A as NestJS OrdersService
    participant P as PostgreSQL

    B->>A: POST /api/v1/orders {shippingAddress} + JWT
    A->>A: validate DTO (validation-rules.json checkout)
    A->>P: BEGIN
    A->>P: SELECT cart items FOR UPDATE
    alt cart empty (BR-004)
        A-->>B: 409 {error: CART_EMPTY}
    else stock insufficient (BR-003)
        A-->>B: 409 {error: INSUFFICIENT_STOCK}
    else ok
        A->>P: UPDATE products SET stock_quantity = stock_quantity - qty
        A->>P: INSERT orders (subtotal, shipping_fee 5.00, total) -- BR-006
        A->>P: INSERT order_items (name & price snapshots) -- BR-005
        A->>P: DELETE FROM cart_items -- empty the cart
        A->>P: COMMIT
        A-->>B: 201 Order (status PENDING)
        B->>B: navigate /orders/:orderId + toast "Order placed."
    end
```

## 4 · Auth flow (REQ-001/002/012, NFR-001/002)

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as NestJS AuthController
    participant P as PostgreSQL

    B->>A: POST /auth/register {fullName, email, password}
    A->>P: INSERT users (bcrypt cost 12) + INSERT carts
    A-->>B: 201 {accessToken (exp 3600s), user}
    Note over B: JWT stored; sent as Authorization: Bearer on every protected call
    B->>A: GET /cart (Bearer)
    A-->>B: 200 Cart
    Note over B: expiry/invalid token → 401 UNAUTHORIZED → client discards JWT,<br/>redirects /login?next=… (state-transitions.md §3)
```

## 5 · Data model (schema.sql is authoritative)

```mermaid
erDiagram
    users ||--o| carts : "owns (1:1)"
    users ||--o{ orders : places
    carts ||--o{ cart_items : contains
    products ||--o{ cart_items : "referenced by"
    products ||--o{ order_items : "referenced by"
    orders ||--o{ order_items : contains

    users { uuid id PK; varchar email UK; varchar password_hash; varchar full_name }
    products { uuid id PK; varchar name; numeric price; int stock_quantity; varchar category; bool is_active }
    carts { uuid id PK; uuid user_id FK }
    cart_items { uuid id PK; uuid cart_id FK; uuid product_id FK; int quantity }
    orders { uuid id PK; uuid user_id FK; varchar order_number UK; order_status status; numeric subtotal; numeric shipping_fee; numeric total }
    order_items { uuid id PK; uuid order_id FK; uuid product_id FK; varchar product_name; numeric unit_price; int quantity }
```

## 6 · Deployment (local/dev reference)

```mermaid
flowchart LR
    subgraph docker-compose
        db[(postgres:16<br/>volume pgdata)]
    end
    dev1[Vite dev server :5173] -->|proxy /api/v1| dev2[nest start --watch :3000]
    dev2 --> db
```

- `docker compose up -d` starts PostgreSQL 16; `schema.sql` initialises it
  (mounted as an init script or run via migration 0001).
- Configuration comes exclusively from `.env` (contract: `.env.example`, E2).
- Production shape: static SPA behind any web server/CDN; API as a single
  container; managed PostgreSQL. Nothing else is required (no cache, no queue).

## 7 · Cross-cutting decisions

| Concern | Decision | Where |
|---------|----------|-------|
| Error shape | Single `{error:{code,message,details[]}}` envelope | openapi.yaml, GlobalExceptionFilter |
| Message text | Defined once, reused verbatim (NFR-007) | validation-rules.json |
| Money | NUMERIC(10,2) USD end-to-end; render with 2dp | schema.sql, SKILL.md §4 |
| IDs | UUIDv4 server-generated | schema.sql |
| Pagination | page/limit + items/total/totalPages envelope, limit ≤ 100 (NFR-004) | openapi.yaml |
| Traceability | REQ/BR/NFR IDs in code comments at implementation sites | SKILL.md §7 |
