# Extracted Requirements

## Functional (42)
- **REQ-1** (User Registration and Authentication): The system shall allow a customer to register using an email address or mobile number and a password.
- **REQ-2** (User Registration and Authentication): The system shall verify a new customer's email or mobile number before the account can place orders.
- **REQ-3** (User Registration and Authentication): The system shall authenticate registered users and issue a session token valid for a configurable duration.
- **REQ-4** (User Registration and Authentication): The system shall lock an account for a configurable period after five consecutive failed login attempts.
- **REQ-5** (User Registration and Authentication): The system shall allow a user to reset a forgotten password via a time-limited, single-use link sent to their verified email or mobile number.
- **REQ-6** (User Registration and Authentication): The system shall allow a customer to create, edit, and delete multiple saved delivery addresses.
- **REQ-7** (User Registration and Authentication): The system shall enforce role-based access so that each user can access only functions permitted to their user class.
- **REQ-8** (Restaurant and Menu Browsing): The system shall display restaurants that are currently open and configured to deliver to the customer's selected address.
- **REQ-9** (Restaurant and Menu Browsing): The system shall allow customers to search restaurants and menu items by name and by cuisine.
- **REQ-10** (Restaurant and Menu Browsing): The system shall allow customers to filter results by cuisine, price range, minimum rating, and estimated delivery time, and to sort by rating, delivery time, or price.
- **REQ-11** (Restaurant and Menu Browsing): The system shall display for each restaurant its average rating, estimated delivery time, delivery fee, and minimum order value.
- **REQ-12** (Restaurant and Menu Browsing): The system shall indicate when a restaurant or a specific menu item is temporarily unavailable and shall prevent unavailable items from being added to a cart.
- **REQ-13** (Cart and Order Placement): The system shall allow a customer to add, update the quantity of, and remove menu items in a cart, and shall maintain one active cart per customer per restaurant.
- **REQ-14** (Cart and Order Placement): The system shall prevent items from more than one restaurant from being combined in a single order.
- **REQ-15** (Cart and Order Placement): The system shall recalculate the order subtotal, taxes, delivery fee, and total whenever the cart changes.
- **REQ-16** (Cart and Order Placement): The system shall block checkout when the order subtotal is below the restaurant's minimum order value and shall inform the customer of the shortfall.
- **REQ-17** (Cart and Order Placement): The system shall allow the customer to choose delivery or pickup and, for delivery, to select a saved address.
- **REQ-18** (Cart and Order Placement): On order confirmation, the system shall create an order record, transition it to “Pending Restaurant Acceptance,” and notify the restaurant in real time.
- **REQ-19** (Cart and Order Placement): The system shall allow a customer to cancel an order without charge only before the restaurant accepts it (see BR-1).
- **REQ-20** (Payment Processing): The system shall support online payment by card and digital wallet through the integrated payment gateway, and shall support cash on delivery where the restaurant permits it.
- **REQ-21** (Payment Processing): The system shall never store raw card data; all card details shall be tokenized by the payment gateway.
- **REQ-22** (Payment Processing): The system shall confirm an online order for fulfilment only after the gateway authorizes payment successfully.
- **REQ-23** (Payment Processing): The system shall record the payment status, amount, method, and gateway transaction reference against each order.
- **REQ-24** (Payment Processing): The system shall issue a full or partial refund through the gateway when an order is cancelled within the eligible window or when an administrator resolves a dispute in the customer's favour.
- **REQ-25** (Order Tracking and Delivery Management): The system shall assign a delivery order to an available delivery agent based on proximity to the restaurant and current agent load.
- **REQ-26** (Order Tracking and Delivery Management): The system shall allow a delivery agent to accept or decline an offered job within a configurable time limit, reassigning declined or timed-out jobs to another agent.
- **REQ-27** (Order Tracking and Delivery Management): The system shall present the customer with a live order status through the sequence: Accepted, Preparing, Ready, Out for Delivery, Delivered.
- **REQ-28** (Order Tracking and Delivery Management): The system shall display the delivery agent's live location and an updated ETA to the customer while the order is out for delivery.
- **REQ-29** (Order Tracking and Delivery Management): The system shall allow a delivery agent to mark an order delivered and to attach an optional proof-of-delivery photograph.
- **REQ-30** (Order Tracking and Delivery Management): The system shall notify the customer by push and SMS at each major status change.
- **REQ-31** (Ratings and Reviews): The system shall allow a customer to submit a rating from 1 to 5 and an optional text review for a delivered order, once per order.
- **REQ-32** (Ratings and Reviews): The system shall recompute and display the restaurant's average rating after each new review.
- **REQ-33** (Ratings and Reviews): The system shall allow an administrator to remove a review that violates content policy.
- **REQ-34** (Restaurant Partner Menu Management): The system shall allow a restaurant manager to create, edit, and remove menu categories and menu items, including name, description, price, and availability.
- **REQ-35** (Restaurant Partner Menu Management): The system shall allow a restaurant manager to toggle the restaurant's overall open/closed status and per-item availability.
- **REQ-36** (Restaurant Partner Menu Management): The system shall alert the restaurant manager in real time when a new order is received.
- **REQ-37** (Restaurant Partner Menu Management): The system shall allow a restaurant manager to accept or reject an incoming order and, once accepted, to advance it to Preparing and Ready.
- **REQ-38** (Restaurant Partner Menu Management): The system shall require a reason when a restaurant rejects an accepted-eligible order, and shall trigger a refund for any prepaid amount (see REQ-24).
- **REQ-39** (Administration and Platform Management): The system shall allow an administrator to onboard, suspend, and reactivate restaurant partners and delivery agents.
- **REQ-40** (Administration and Platform Management): The system shall allow an administrator to view and search orders, users, and transactions across the platform.
- **REQ-41** (Administration and Platform Management): The system shall allow an administrator to review customer disputes and record a resolution, including issuing refunds where warranted.
- **REQ-42** (Administration and Platform Management): The system shall allow an administrator to configure platform parameters including commission rate, service fee, and default delivery radius.

## Performance (4)
- **NFR-1**: Restaurant search and listing results shall be returned to the client within 2 seconds for 95% of requests under normal load.
- **NFR-2**: Order placement (from confirmation to acknowledgement) shall complete within 3 seconds for 95% of requests, excluding external payment-gateway latency.
- **NFR-3**: The system shall support at least 10,000 concurrent active users and 500 orders per minute at launch without violating NFR-1 or NFR-2.
- **NFR-4**: Live delivery-location updates shall reach the customer within 5 seconds of being reported by the delivery agent.

## Non-Functional (13)
- **NFR-5** [safety]: The system shall display allergen and dietary information supplied by the restaurant on the relevant menu items so customers can make informed choices.
- **NFR-6** [safety]: The system shall not present delivery-agent workflows that require manual interaction while the agent is expected to be driving; status updates shall be minimal-interaction and confirmable in a single tap.
- **NFR-7** [safety]: The system shall retain committed order and payment data durably such that no confirmed transaction is lost in the event of a single-node failure.
- **NFR-8** [security]: All data in transit shall be encrypted using TLS 1.2 or higher; sensitive data at rest shall be encrypted.
- **NFR-9** [security]: User passwords shall be stored only as salted, one-way hashes.
- **NFR-10** [security]: Payment card handling shall comply with PCI DSS v4.0, with all card data tokenized by the payment gateway and never persisted by QuickBite.
- **NFR-11** [security]: The system shall enforce role-based access control for all privileged operations and shall log all administrative actions with actor, timestamp, and affected entity.
- **NFR-12** [security]: The system shall protect authentication and payment endpoints against automated abuse through rate limiting.
- **NFR-13** [software_quality]: Availability: the platform shall maintain 99.9% monthly uptime for customer-facing ordering functions.
- **NFR-14** [software_quality]: Usability: a first-time customer shall be able to complete an order from restaurant selection to confirmation without external assistance.
- **NFR-15** [software_quality]: Maintainability: the backend shall be organized into independently deployable services so that a change to one does not require redeploying the whole platform.
- **NFR-16** [software_quality]: Portability: the customer application shall run on both Android and iOS from a shared codebase, and the web experience shall function on all supported browsers.
- **NFR-17** [software_quality]: Reliability: a failure of an external provider (payment, mapping, or messaging) shall degrade only the dependent function and shall not crash unrelated parts of the platform.

## Business Rules (7)
- **BR-1**: A customer may cancel an order free of charge only until the restaurant accepts it; after acceptance, cancellation is subject to a charge determined by platform policy.
- **BR-2**: An order may be placed only from a single restaurant.
- **BR-3**: A restaurant may receive orders only while it is marked open and within its configured operating hours.
- **BR-4**: A delivery order may be placed only when the delivery address falls within the restaurant's configured delivery radius.
- **BR-5**: The platform shall deduct a configurable commission from each completed order's value before settlement to the restaurant.
- **BR-6**: A customer may submit at most one review per delivered order.
- **BR-7**: Only administrators may issue refunds or remove published reviews.

## Constraints
- All payment card handling shall comply with PCI DSS v4.0; card data shall never be stored on QuickBite servers and shall be tokenized by the payment gateway.
- All network communication shall use TLS 1.2 or higher.
- The system shall be built as a set of services behind a single API gateway to allow independent scaling of high-traffic components (search, ordering).
- The launch is restricted to a single metropolitan area; delivery radius logic must be configurable per restaurant.
- Personal data handling shall comply with applicable data-protection regulation for the launch region.

## External Interfaces
- **Payment Gateway**: Outbound HTTPS/REST. Sends tokenized payment authorization and capture requests; receives transaction status, refunds, and webhook settlement events. No raw card data crosses QuickBite servers.
- **Mapping / Geocoding API**: Outbound HTTPS/REST. Sends addresses and coordinate pairs; receives geocoded locations, distance/ETA estimates, and route polylines used for delivery tracking.
- **Messaging Provider**: Outbound HTTPS/REST. Sends templated SMS, push, and email notification requests (order confirmation, status updates); receives delivery/failure receipts.
- **Relational Database**: Internal. Stores users, restaurants, menus, carts, orders, payments, deliveries, and reviews. Shared across backend services through a data-access layer.

## UI Token Source (feeds Design Tokens)
- ****: Every client application shall follow the QuickBite design system defined below for theme, colour, typography, spacing, and component usage. The design tokens specified in this section are normative: they are the single source of truth for the visual language and shall be implemented as named tokens (not hard-coded values) so that the four applications remain visually consistent and the theme can be adjusted centrally.
- **3.1.1 Overall Visual Theme**: QuickBite's visual identity is warm, appetizing, and energetic while remaining clean and trustworthy. The theme is content-forward: food photography is the hero of each screen, framed by generous whitespace and a warm off-white canvas so that dishes stand out. The brand colour is an appetite-stimulating tomato-coral used for primary actions and key highlights; a warm amber acts as a secondary accent. Surfaces are light with soft, rounded corners and subtle shadows to create a friendly, approachable feel rather than a hard, corporate one. Interactions favour large, thumb-friendly tap targets and single-tap primary actions, reflecting the mobile-first, on-the-go nature of the product. The delivery-agent app inverts to a higher-contrast, minimal-interaction variant of the same tokens for glanceability while moving. Across all four applications the underlying tokens are shared; only density and emphasis differ by context.
- **3.1.3 Typography Tokens**: Headings use a friendly geometric sans (Poppins); body text uses a highly legible neutral sans (Inter). The type scale below shall be applied consistently; line height is 1.25 for headings and 1.5 for body and smaller sizes.
- **3.1.4 Spacing, Radius, and Elevation Tokens**: Spacing follows a 4 px base scale; all margins, padding, and gaps shall use these steps. Corner radii are rounded to reinforce the friendly theme, and elevation is kept soft and subtle.
- **3.1.5 Layout and Interaction Standards**: Beyond the tokens above, all client applications shall meet the following interface standards. Detailed screen designs are maintained in a separate UI specification and shall not contradict the tokens defined here.
- **3.1.5 Layout and Interaction Standards**: Every screen shall provide a consistent top navigation bar giving access to help and account.
- **3.1.5 Layout and Interaction Standards**: Validation and error messages shall be displayed inline, near the relevant field, using color-error.
- **3.1.5 Layout and Interaction Standards**: Interfaces shall remain usable on screen widths from 360 px (mobile) upward and shall reflow responsively to desktop widths for the web, restaurant, and admin experiences.
- **3.1.5 Layout and Interaction Standards**: Primary actions shall use color-primary, be reachable without horizontal scrolling on mobile, and present tap targets of at least 44 × 44 px.
- **3.1.5 Layout and Interaction Standards**: The customer ordering flow shall be completable in no more than five screens from restaurant selection to order confirmation.
- **3.1.5 Layout and Interaction Standards**: The interface shall meet WCAG 2.1 AA contrast for text and essential controls, and shall not rely on colour alone to convey status.

## UI Tokens (structured, from 3.1 tables)

### Colour (12)
- token: color-primary · hex: #E8502E · usage: Primary brand colour; primary buttons, active states, key highlights
- token: color-primary-dark · hex: #C43E20 · usage: Hover / pressed state of primary actions
- token: color-secondary · hex: #F5A623 · usage: Secondary accent; badges, promotions, secondary emphasis
- token: color-success · hex: #2E9E5B · usage: Positive status (e.g. Delivered), confirmations
- token: color-warning · hex: #E8952E · usage: Warnings and attention states
- token: color-error · hex: #D64545 · usage: Errors, destructive actions, validation failures
- token: color-ink · hex: #1F2422 · usage: Primary text and headings
- token: color-body · hex: #4A524E · usage: Body and secondary text
- token: color-muted · hex: #8A928E · usage: Placeholder, disabled, and tertiary text
- token: color-surface · hex: #FFFFFF · usage: Cards and primary surfaces
- token: color-canvas · hex: #FAF7F2 · usage: Warm off-white app background
- token: color-border · hex: #E5E1DA · usage: Dividers, input borders, card outlines

### Typography (7)
- token: font-display · size: 32 px · weight: Bold (700) · usage: Screen titles, hero headings (Poppins)
- token: font-h1 · size: 28 px · weight: SemiBold (600) · usage: Section headings (Poppins)
- token: font-h2 · size: 22 px · weight: SemiBold (600) · usage: Sub-section headings (Poppins)
- token: font-h3 · size: 18 px · weight: Medium (500) · usage: Card titles, list group headers (Poppins)
- token: font-body · size: 16 px · weight: Regular (400) · usage: Default body text (Inter)
- token: font-small · size: 14 px · weight: Regular (400) · usage: Secondary text, metadata (Inter)
- token: font-caption · size: 12 px · weight: Medium (500) · usage: Labels, captions, badges (Inter)

### Spacing Radius And Elevation (7)
- token: space-1 … space-8 · value: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 px · usage: 4 px-based spacing scale for padding, margins, and gaps
- token: radius-sm · value: 8 px · usage: Inputs, chips, small controls
- token: radius-md · value: 12 px · usage: Buttons and cards
- token: radius-lg · value: 16 px · usage: Sheets, modals, image containers
- token: radius-pill · value: 999 px · usage: Pills, tags, avatar and status badges
- token: elevation-1 · value: 0 1px 2px rgba(0,0,0,0.06) · usage: Resting cards and list items
- token: elevation-2 · value: 0 4px 12px rgba(0,0,0,0.10) · usage: Raised elements: menus, popovers, active cards

## Tech Stack
Not fixed by the SRS (requirements-level document). Stack is decided in Design; see constraints + external_interfaces for imposed technical constraints (API-gateway/services, relational DB, TLS 1.2+, PCI-DSS tokenization).