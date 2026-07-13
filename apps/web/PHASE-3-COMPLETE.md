# Phase 3: API Integration & State Management ✅

## Completed

### API Client
- ✅ **api/client.ts** — Fetch wrapper with:
  - JWT token auto-injection from localStorage
  - Error handling (ApiError interface with code/message/details)
  - Methods: GET, POST, PATCH, DELETE
  - Token management (set/clear)

### API Types
- ✅ **types/api.ts** — Full TypeScript interfaces for:
  - Auth (User, AuthResponse, RegisterRequest, LoginRequest)
  - Products (Product, ProductListResponse)
  - Cart (Cart, CartItem, AddCartItemRequest, UpdateCartItemRequest)
  - Orders (Order, OrderItem, OrderListResponse, PlaceOrderRequest, ShippingAddress)

### API Service Functions
- ✅ **api/auth.ts** — register(), login(), logout()
- ✅ **api/products.ts** — listProducts(), getProduct()
- ✅ **api/cart.ts** — getCart(), addCartItem(), updateCartItem(), removeCartItem()
- ✅ **api/orders.ts** — placeOrder(), listOrders(), getOrder()

### React Query Hooks
- ✅ **hooks/useAuthMutations.ts** — useRegister(), useLogin(), useLogout()
- ✅ **hooks/useProducts.ts** — useProducts(), useProduct()
- ✅ **hooks/useCart.ts** — useCart() + mutations (add, update, remove) with auto cache updates
- ✅ **hooks/useOrders.ts** — useOrders(), useOrder(), usePlaceOrder() with invalidation

### Auth Integration
- ✅ **AuthContext.tsx** — Updated to use API hooks
  - login(email, password) → calls API, stores token, sets user
  - register(fullName, email, password) → calls API, stores token, sets user
  - logout() → clears token & user
  - error state for feedback

## Architecture
```
Pages → Hooks (useCart, useProducts, etc.)
                ↓
       React Query (caching, refetching)
                ↓
       API Service functions (cart.ts, products.ts, etc.)
                ↓
       API Client (fetch wrapper, auth, error handling)
                ↓
       Backend (/api/v1)
```

## State Flow
1. **Authentication:**
   - User submits form → useRegister/useLogin hook
   - Hook calls API service function
   - API client injects JWT token
   - Response sets user in AuthContext
   - ProtectedRoute checks user context

2. **Cart:**
   - useCart() query loads cart state
   - useAddCartItem() / useUpdateCartItem() mutations update cart
   - Mutations auto-invalidate React Query cache
   - UI re-renders with new cart state

3. **Orders:**
   - usePlaceOrder() mutation sends checkout request
   - On success: invalidates cart + orders queries
   - useOrder() fetches individual order details
   - useOrders() lists all orders with pagination

## Query Cache Keys
- `['products', params]` — product list (invalidates on new params)
- `['product', id]` — single product
- `['cart']` — user's cart (auto-updated on all cart mutations)
- `['orders', params]` — orders list
- `['order', id]` — single order

## Error Handling
- API client parses error envelope (code + message + field details)
- Mutations throw with ApiError interface
- AuthContext catches and stores error state
- Ready for Toast integration in pages

## Ready for Phase 4: Form Integration & Toast Notifications
Next phase will:
- Wire login/register forms to useLogin/useRegister hooks
- Connect all forms to API calls with loading states
- Add Toast notifications for success/error feedback
- Handle 401 auth errors with redirect to login
- Complete end-to-end flows

---

**Ready for Phase 4?** ✅ (Awaiting human approval)
