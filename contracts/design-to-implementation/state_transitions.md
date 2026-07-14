Registration Page:
- Loading → Full-page warm canvas (color-canvas) with top nav bar visible; form skeleton shows shimmer placeholders for email/mobile field, password field, and submit button; no interaction possible during initial config fetch (e.g. supported regions, terms URL).
- Empty → Blank registration form rendered with email/mobile input, password input, confirm-password input, and a "Create Account" primary button (color-primary); all fields show placeholder text in color-muted; no error or helper text shown; "Already have an account? Sign in" secondary link visible.
- Error → Inline validation messages rendered directly beneath the offending field(s) in color-error using font-small; specific cases: invalid email/mobile format, password too weak, passwords don't match, email/mobile already registered, rate-limit lockout banner at top of form; "Create Account" button remains enabled so the user can correct and retry; network/server failure shows a non-blocking toast or inline banner ("Something went wrong — please try again") without clearing field values.
- Success → Form replaced by a confirmation panel: icon (envelope or phone), heading ("Check your inbox / messages"), body text instructing the user to verify their email or mobile before they can place orders; a "Resend verification" link is available; no navigation away is forced so the user can switch context freely.

Email / Mobile Verification Page:
- Loading → Spinner centered on canvas while the system validates the token from the verification link; brief "Verifying your account…" label in color-muted below the spinner.
- Empty → Not applicable — page is only reached via a verification link; if no token is present in the URL, immediately transition to the Error state.
- Error → Full-page message with color-error icon and heading ("Verification link invalid or expired"); body text explains the link is single-use and time-limited; prominent "Resend verification link" button (color-primary); secondary "Go to Sign In" text link.
- Success → Confirmation panel with color-success icon, heading ("Email / mobile verified"), and message ("Your account is ready — you can now place orders"); single primary CTA button "Start Ordering" that navigates to the Restaurant Listing page.

Login Page:
- Loading → Form skeleton with shimmer placeholders for credential fields and button; shown only if session state is being checked on mount to avoid flashing the form for already-authenticated users.
- Empty → Clean form with email/mobile field, password field, "Sign In" primary button, "Forgot password?" text link, and "Create an account" secondary link; all inputs empty with color-muted placeholders; no error states shown.
- Error → Inline error beneath the relevant field for invalid format; a dismissible alert banner below the form heading for authentication failures ("Incorrect email or password"); account-locked state replaces the button with a disabled state and displays a banner in color-warning indicating the lockout duration and that the account is temporarily locked after five consecutive failures; network error shows a top-of-form banner without clearing credentials.
- Success → Login form is hidden; a brief full-screen loading indicator appears while the session token is stored and the user is redirected to their role-appropriate landing page (Customer → Restaurant Listing; Restaurant Manager → Order Queue; Delivery Agent → Job Queue; Administrator → Admin Dashboard).

Forgot Password Page:
- Loading → Shimmer placeholder for the email/mobile input field and submit button during any initial state check.
- Empty → Single-field form asking for the verified email or mobile number associated with the account; "Send Reset Link" primary button; "Back to Sign In" text link; no errors or helper text.
- Error → Inline error beneath the field for invalid format; a form-level banner for unrecognised email/mobile ("If this address is registered, you'll receive a link shortly" — deliberately ambiguous per security best practice, but rendered using color-warning rather than color-error to signal non-blocking feedback); network failure shows a retry banner without clearing the field.
- Success → Form replaced by a confirmation panel ("Reset link sent"); body text instructs the user to check their email or messages; the link is time-limited and single-use (per REQ-5); "Resend" link and "Back to Sign In" text link provided.

Reset Password Page:
- Loading → Spinner while the reset token in the URL is validated server-side before rendering the form.
- Empty → Not applicable — page is only reachable via a reset link; missing token transitions immediately to Error state.
- Error → Token invalid or expired: full-page error panel with color-error icon, explanatory message, and "Request a new reset link" primary button. Form-level validation errors (password too weak, passwords don't match): inline messages beneath each field in color-error; submit button remains enabled.
- Success → Form replaced by a confirmation panel with color-success icon ("Password updated"); single primary CTA "Sign In" navigating to the Login page; no automatic redirect to prevent session confusion.

Restaurant Listing / Home Page (Customer):
- Loading → Top nav bar and address selector rendered immediately; below, a grid or list of restaurant card skeletons (shimmer rectangles matching card dimensions) fills the viewport; filter/sort bar shown in a disabled shimmer state; results are returned within 2 seconds for 95% of requests (NFR-1).
- Empty → Address selector and filter/sort bar fully interactive; zero-results illustration with friendly icon, heading ("No restaurants available"), and contextual body text — either "No restaurants deliver to this address right now" (address outside all delivery radii or all restaurants closed, per BR-3/BR-4) or "No results match your filters" (when filters are active, with a "Clear filters" action link in color-primary).
- Error → Address selector remains usable; restaurant grid area shows an error panel with a retry button ("Try again") in color-primary; specific sub-states: mapping/geocoding failure shows a color-warning inline banner ("We couldn't confirm your address — results may be incomplete") without blocking the list if partial data is available (NFR-17); full API failure shows the error panel.
- Success → Fully rendered list/grid of restaurant cards each showing: food photography hero image, restaurant name (font-h3), cuisine tags (color-secondary badges), average star rating, estimated delivery time, delivery fee, and minimum order value (REQ-11); "Closed" or "Unavailable" pill overlay on cards for non-deliverable restaurants (REQ-12); filter/sort bar active with cuisine, price range, minimum rating, and estimated delivery time controls (REQ-10); search input active (REQ-9); selected delivery address displayed prominently with a change-address affordance.

Restaurant Detail / Menu Page (Customer):
- Loading → Restaurant hero image area renders as a large shimmer block; below it, restaurant meta row (rating, ETA, fee, minimum) shows shimmer placeholders; menu category tabs and item list show skeleton rows; add-to-cart button in the sticky footer is hidden until data loads.
- Empty → Only reachable if the restaurant exists but has no menu categories or items configured; shows the restaurant header fully rendered and a body message ("Menu coming soon — check back later") with no item cards; the cart footer is absent; a back-navigation affordance is present.
- Error → Restaurant header renders if cached data allows; menu area shows an error panel with a retry button; if the restaurant is marked closed or outside operating hours (BR-3), a full-width color-warning banner replaces the CTA footer: "This restaurant is currently closed — you can browse the menu but cannot add items."
- Success → Full restaurant header: hero image, name (font-h1), cuisine, open/closed badge, average rating, estimated delivery time, delivery fee, minimum order value, and operating hours (REQ-11); horizontally scrollable category tab bar anchoring to menu sections; each menu item card shows name, description, price, allergen/dietary badges (NFR-5), and an "Add" button (color-primary, 44 × 44 px min); unavailable items show a "Unavailable" label and a disabled "Add" button (REQ-12); sticky cart summary footer appears as soon as ≥1 item is in the cart showing item count and subtotal with a "View Cart" CTA.

Cart Page (Customer):
- Loading → Sticky header with restaurant name shown immediately; cart item list area shows shimmer skeleton rows for items; price summary panel (subtotal, taxes, delivery fee, total) shows shimmer placeholders; checkout button disabled.
- Empty → Illustration with icon, heading ("Your cart is empty"), body text ("Add items from a restaurant to get started"); single "Browse Restaurants" primary button; no price summary or checkout button shown.
- Error → Cart items remain displayed using last-known state; error banner at the top of the page for any sync failure ("We couldn't update your cart — please try again"); if an item has become unavailable since it was added, that item is highlighted with a color-error inline label ("No longer available — please remove to continue") and the checkout button is disabled until removed (REQ-12); cross-restaurant conflict (BR-2) shown as an inline warning if data integrity is violated.
- Success → List of cart items each showing name, customisation summary, per-item price, quantity stepper (−/+ controls, 44 × 44 px), and remove icon; price summary panel showing subtotal, taxes, delivery fee, and total recalculated live (REQ-15); delivery/pickup selector (REQ-17); saved-address selector for delivery (REQ-6/REQ-17); if subtotal is below the restaurant's minimum order value, checkout button is disabled and an inline message shows the shortfall amount in color-error ("Add [amount] more to reach the minimum order", REQ-16); "Proceed to Checkout" primary button (color-primary) enabled only when all validations pass; order cancellation note ("You can cancel free of charge before the restaurant accepts your order", BR-1).

Checkout / Payment Page (Customer):
- Loading → Page structure (address summary, payment method selector, order summary panel) renders with shimmer skeletons while payment gateway widget and saved addresses are fetched; "Place Order" button is disabled.
- Empty → Not a reachable independent empty state; if the user lands here with an empty cart they are redirected to the Cart page.
- Error → Payment gateway failure: inline color-error banner below the payment widget ("Payment could not be processed — please check your details or try another method") with the form kept intact for retry; order placement timeout: dismissible error banner at top of page; address outside delivery radius: color-error inline message next to the address selector ("This address is outside the delivery area", BR-4); all errors are non-destructive — no entered data is cleared; PCI-compliant gateway widget handles card-specific validation errors inline within the widget itself (REQ-21).
- Success → Payment authorised and order created (REQ-22): page transitions to an Order Confirmation panel showing order ID, itemised summary, estimated delivery time, and payment method/amount recorded (REQ-23); a prominent "Track My Order" CTA in color-primary; a "Continue Shopping" secondary link; no sensitive card data is displayed.

Order Confirmation Page (Customer):
- Loading → Spinner/skeleton while the newly created order record is fetched to confirm persistence (REQ-23, NFR-7); order ID shown immediately from the prior response if available.
- Empty → Not applicable — page is only rendered post-successful order placement.
- Error → If order record cannot be confirmed (e.g. network drop after placement), a color-warning banner states "Your order may have been placed — check your Order History or contact support" alongside order details captured client-side; a "View Order History" link and support contact are offered; avoids falsely implying failure since payment may have been captured.
- Success → Color-success icon and heading ("Order placed!"); order reference number; itemised order summary; selected delivery address or pickup note; payment method and amount; estimated delivery time; status chip "Pending Restaurant Acceptance" (REQ-18/REQ-27); "Track My Order" primary CTA; "Cancel Order" secondary action available (color-error text link) with a note that cancellation is free only before restaurant acceptance (BR-1/REQ-19).

Order Tracking Page (Customer):
- Loading → Map area renders as a placeholder tile while the mapping API initialises; status stepper and ETA panel show shimmer skeletons; delivery agent location indicator absent until data arrives; WebSocket connection initiated in background.
- Empty → Not applicable as a standalone state; if the order ID is invalid or does not belong to the authenticated user, transitions directly to Error.
- Error → Mapping API failure: map area replaced by a color-warning banner ("Live map unavailable — tracking may be limited", NFR-17); status stepper and ETA text remain functional from WebSocket data; full WebSocket disconnection: color-warning top banner "Reconnecting…" with automatic retry; order data shown from last known state with a "last updated" timestamp.
- Success → Status progress stepper showing the full sequence (Accepted → Preparing → Ready → Out for Delivery → Delivered, REQ-27) with current step highlighted in color-primary and completed steps in color-success; while "Out for Delivery": live map with delivery agent pin updating within 5 seconds of agent location report (REQ-28, NFR-4), updated ETA displayed prominently; order summary panel (items, restaurant name, delivery address); "Cancel Order" action visible and enabled only in "Pending Restaurant Acceptance" state (BR-1/REQ-19), shown as disabled with explanatory tooltip after acceptance; on reaching "Delivered" status: color-success banner and "Rate Your Order" CTA appearing inline (REQ-31).

Order History Page (Customer):
- Loading → List skeleton showing shimmer rows for past orders; filter/search bar rendered but inactive.
- Empty → Illustration with heading ("No orders yet") and body text ("Your completed and active orders will appear here"); "Browse Restaurants" primary CTA.
- Error → Error panel with retry button ("Couldn't load your orders — try again"); if partial data is cached, show available orders with a color-warning banner noting that the list may be incomplete.
- Success → Chronological list of past orders each showing: restaurant name and logo, order date, status chip (color-success for Delivered, color-error for Cancelled, color-warning for in-progress), item summary, and total amount; tapping/clicking an order navigates to Order Detail or Order Tracking if still active; a "Reorder" shortcut button on delivered orders; "Rate" CTA on delivered unreviewed orders (REQ-31); pagination or infinite scroll for long histories.

Order Detail Page (Customer):
- Loading → Order header (restaurant name, order ID, date) shows immediately from list data; full item breakdown, payment details, and timeline shimmer until detail fetch completes.
- Empty → Not applicable — only rendered for an existing order record.
- Error → Partial render with cached list-level data; error panel in the detail body with retry; if the order cannot be loaded at all, full-page error with "Back to Order History" link.
- Success → Full itemised breakdown with quantities and prices; delivery address or pickup label; payment status, method, and amount (REQ-23); order status timeline showing status history with timestamps; proof-of-delivery photo thumbnail if attached (REQ-29); "Rate this order" section if delivered and not yet reviewed (REQ-31); "Dispute / Contact Support" link visible for delivered or cancelled orders.

Submit Review Page (Customer):
- Loading → Restaurant name and order summary shown immediately; star-rating widget and text area shimmer briefly while confirming the order is eligible (delivered, not yet reviewed).
- Empty → Star-rating widget (1–5 stars, all unselected, REQ-31); optional text review textarea with placeholder ("Share your experience…"); "Submit Review" primary button disabled until a star rating is selected; "Skip" text link.
- Error → If the order has already been reviewed (BR-6), the form is replaced by an informational panel ("You've already reviewed this order") with a link back to Order History; network submission error shows a color-error banner beneath the form without clearing the rating or text; star rating remains interactive for correction.
- Success → Color-success confirmation panel ("Review submitted — thank you!"); note that the restaurant's rating has been updated (REQ-32); "Back to Orders" primary CTA; review text and star rating displayed read-only as confirmation.

Saved Addresses Page (Customer — within Account/Profile):
- Loading → List of address cards shimmers while fetching; "Add New Address" button rendered immediately.
- Empty → Illustration with heading ("No saved addresses"), body text ("Add an address to speed up checkout"); single "Add Address" primary CTA.
- Error → Error panel with retry for list fetch failure; inline color-error messages beneath individual address form fields for validation failures (invalid postcode, unresolvable address per mapping API); save-failure toast without closing the form.
- Success → List of saved address cards each showing formatted address, a default badge (color-secondary pill) if applicable, "Edit" and "Delete" icon buttons (44 × 44 px); "Add New Address" button at top or bottom; inline edit/add form expands within the page (or via a bottom sheet on mobile) with geocoding validation on blur; delete triggers a confirmation dialog before removal (REQ-6).

Restaurant Partner — Order Queue Page:
- Loading → Top nav bar and restaurant open/closed toggle rendered immediately; incoming order list shows shimmer skeleton cards; WebSocket connection initialising in background.
- Empty → Order list area shows a friendly illustration with heading ("No active orders") and body text ("New orders will appear here automatically"); open/closed toggle remains interactive.
- Error → WebSocket disconnection: color-warning banner "Connection lost — reconnecting…" at top of page with auto-retry; order cards last received remain visible with a "last updated" timestamp; if the restaurant's session has expired, a modal prompts re-authentication without losing order state.
- Success → Real-time list of incoming and active orders sorted by arrival time; each order card shows: order ID, customer name, items summary, total value, time received, and current status chip; new orders arrive with an audio alert and a visual highlight animation (REQ-36); each card has action buttons: "Accept" (color-success) and "Reject" (color-error) for pending orders; "Mark Preparing" and "Mark Ready" for accepted orders (REQ-37); rejecting an order opens an inline reason-entry field before confirmation (REQ-38); order cards transition status in real time via WebSocket.

Restaurant Partner — Menu Management Page:
- Loading → Category list and item grid/list show shimmer skeletons; "Add Category" and "Add Item" buttons rendered but disabled until data loads.
- Empty → No menu categories exist yet: full-page empty state with heading ("Your menu is empty") and "Add your first category" primary CTA guiding the manager through the creation flow.
- Error → Category or item save failure: inline color-error banner within the open edit form without closing it, preserving entered data; list fetch failure: error panel with retry; image upload failure: inline error beneath the image upload control ("Image could not be uploaded — try again").
- Success → Accordion or tab list of menu categories; each category shows its name, item count, and expand/collapse control; within each category, item rows showing: item photo thumbnail, name (font-h3), description (font-small, truncated), price, availability toggle (REQ-35), and edit/delete icon buttons; inline edit form opens within the page or a side panel for adding/editing categories and items including name, description, price, allergen/dietary fields (NFR-5), and availability toggle (REQ-34); restaurant-level open/closed toggle in the page header (REQ-35); unsaved changes prompt a confirmation dialog on navigation away.

Restaurant Partner — Restaurant Settings Page:
- Loading → Settings form shimmers while current configuration is fetched.
- Empty → Not applicable — settings always have persisted values for an onboarded restaurant.
- Error → Inline color-error messages for invalid field values; save-failure banner at top of form without clearing data; if the manager lacks permission for a specific field, that field is rendered as read-only with a tooltip explaining the restriction.
- Success → Editable form with restaurant name, cuisine type(s), operating hours, delivery radius (read reference to platform default, per constraint), minimum order value, COD availability toggle, and contact details; "Save Changes" primary button; changes to open/closed status and per-item availability are reflected immediately to customers upon save (REQ-35).

Delivery Agent — Job Queue / Available Jobs Page:
- Loading → Single-tap-optimised layout renders immediately; job card area shows a minimal shimmer (single card placeholder) to avoid distraction; geolocation permission is requested on mount if not already granted.
- Empty → Full-screen friendly panel ("No jobs available right now — stay close and we'll notify you of the next one"); agent availability toggle remains accessible.
- Error → Geolocation unavailable: color-warning banner "Location access required for job assignment — please enable location in your browser settings"; WebSocket disconnection: minimal top banner "Reconnecting…" (NFR-6, single-tap interactions preserved); network error: retry button displayed prominently in large tap target.
- Success → Pending job card displayed one at a time (highest priority / proximity); card shows restaurant name, pickup address, drop-off area, estimated distance, and estimated payout; two large single-tap buttons: "Accept" (color-success) and "Decline" (color-error) each ≥ 44 × 44 px (REQ-26, NFR-6); a countdown timer shows the time remaining to respond before automatic reassignment (REQ-26); agent availability toggle (online/offline) accessible in the header at all times.

Delivery Agent — Active Delivery Page:
- Loading → Map initialises as a tile placeholder; pickup and drop-off address details shown immediately from accepted job data (already in client state); status action button shimmers briefly.
- Empty → Not applicable — only rendered when an active delivery exists.
- Error → Map failure: color-warning banner "Map unavailable" with text directions fallback showing address and any available route description (NFR-17); location reporting failure: silent retry in background, no interruption to the agent workflow (NFR-6).
- Success → Full-screen or large-format map showing current agent position, restaurant pin, and customer pin; turn-by-turn or route polyline overlay from Mapping API; current job details panel (restaurant name, pickup address, customer drop-off address, order items summary) collapsible to maximise map visibility; single large-tap status progression button that advances through: "Picked Up" → "Out for Delivery" → "Mark Delivered" (REQ-29, NFR-6); "Mark Delivered" action opens a minimal confirmation sheet with an optional camera capture for proof-of-delivery photograph (REQ-29, browser camera API per tech stack); after marking delivered, page transitions to Job Queue.

Delivery Agent — Delivery History Page:
- Loading → Shimmer list skeleton while past deliveries are fetched.
- Empty → Heading ("No deliveries yet") with body text ("Completed deliveries will appear here").
- Error → Error panel with retry; partial cached data shown with color-warning banner noting the list may be incomplete.
- Success → Chronological list of completed deliveries showing: order ID, restaurant name, delivery address (area-level for privacy), completion time, and status chip ("Delivered" in color-success); total earnings summary card at top showing period totals; tapping a row opens a minimal detail view with proof-of-delivery photo if attached.

Admin — Dashboard Page:
- Loading → KPI summary cards shimmer; activity feed shows skeleton rows; all nav links remain active.
- Empty → Not applicable for a live platform; if the platform is freshly initialised with zero data, KPI cards show "0" values with an onboarding prompt to add the first restaurant partner.
- Error → Individual widget failure: each KPI card or chart renders its own inline error state with a retry icon, so a single failing data source does not blank the whole dashboard (NFR-17); session expiry: full-page re-authentication prompt.
- Success → KPI summary cards: total orders today, revenue today, active deliveries, and open disputes; trend charts (orders over time, revenue over time); live activity feed of recent orders and status changes; quick-action links to Manage Restaurants, Manage Agents, Review Disputes, and Platform Settings; all administrative actions logged automatically (NFR-11).

Admin — Manage Restaurants Page:
- Loading → Search bar and filter controls rendered immediately; restaurant table/list shows shimmer rows.
- Empty → Zero results from search/filter: inline message ("No restaurants match your search — try different criteria") with "Clear filters" link; zero restaurants on platform: empty state with "Onboard First Restaurant" primary CTA.
- Error → Table load failure: error panel with retry; individual row action failure (e.g. suspend action fails): inline color-error toast for that row without affecting the rest of the list.
- Success → Searchable, filterable table of all restaurant partners showing: name, cuisine, city, status chip (Active / Suspended), date onboarded, and action buttons "View", "Suspend", "Reactivate" (REQ-39); clicking a row opens the Restaurant Detail panel showing full profile, commission rate, operating history, and a direct link to their menu; "Onboard New Restaurant" primary CTA; all actions logged (NFR-11).

Admin — Restaurant Detail / Onboarding Page:
- Loading → Restaurant header (name, status) shown from list data; full detail sections shimmer.
- Empty → Onboarding form in blank state (all fields empty) when creating a new restaurant; form is guided with clear labels, required-field markers, and inline hints.
- Error → Inline color-error validation messages per field; save failure banner at top of form; if the geocoding API fails to validate the restaurant address, a color-warning inline note ("Address could not be verified — please check") allows saving with manual override for admin.
- Success → Full restaurant profile form: name, cuisine, address (geocoded), operating hours, delivery radius, minimum order value, commission rate override (REQ-42), COD permission, contact details, and status toggle (Active / Suspended); "Save" and "Cancel" actions; status history timeline at the bottom; all saves logged with actor and timestamp (NFR-11).

Admin — Manage Delivery Agents Page:
- Loading → Search bar rendered immediately; agent table shimmers.
- Empty → No agents match search: inline "No results" message with "Clear filters"; no agents on platform: empty state with "Onboard First Agent" CTA.
- Error → Table load failure with retry; individual action failure shown as an inline color-error toast per row.
- Success → Searchable table of all delivery agents showing: name, contact, current status chip (Online/Offline/Suspended), total deliveries, and action buttons "View", "Suspend", "Reactivate" (REQ-39); agent detail panel/page accessible from each row showing profile, delivery history, and current active job if any; "Onboard New Agent" primary CTA; all actions logged (NFR-11).

Admin — Orders & Transactions Page:
- Loading → Search and filter controls rendered immediately; orders table shimmers; date-range picker available.
- Empty → No orders match current filters: inline "No orders found" message with "Clear filters" link; no orders on platform yet: empty state illustration with explanatory copy.
- Error → Table load failure with retry button; export action failure: color-error toast without affecting the visible table.
- Success → Searchable, filterable table of all orders across the platform showing: order ID, customer name, restaurant name, agent name, status chip, payment method, amount, and timestamp (REQ-40); clicking a row expands or navigates to a full order detail view including payment reference and gateway transaction ID (REQ-23); filter controls: date range, status, payment method, restaurant; export to CSV action; refund action accessible from order detail for eligible orders (REQ-24/BR-7), requiring admin confirmation before execution.

Admin — Disputes Page:
- Loading → Dispute queue shows shimmer rows; filter controls rendered immediately.
- Empty → No open disputes: color-success banner ("All disputes resolved") with an option to view closed disputes.
- Error → Load failure: error panel with retry; resolution-save failure: color-error banner within the open dispute panel without closing it, preserving the admin's entered notes.
- Success → List of disputes showing: dispute ID, customer name, order ID, reason summary, date opened, and status chip (Open / In Review / Resolved); clicking a dispute opens a detail panel with: full order summary, customer's dispute description, payment details, and a resolution form with free-text notes, resolution type selector (refund / no action / partial refund), and "Apply Resolution" primary button (REQ-41); refund issuance triggers confirmation dialog reminding the admin that the action is irreversible and will call the gateway (REQ-24/BR-7); resolved disputes show the resolution summary read-only; all resolutions logged with actor and timestamp (NFR-11).

Admin — Platform Settings Page:
- Loading → Settings form shimmers while current configuration values are fetched.
- Empty → Not applicable — platform settings always have default values post-initialisation.
- Error → Inline color-error messages for out-of-range or invalid field values (e.g. commission rate > 100%); save failure banner at top of form without clearing data; field-level permission restriction shown as read-only with tooltip for any fields outside the admin's specific sub-role if sub-roles are configured.
- Success → Editable configuration form with: platform commission rate, service fee structure, default delivery radius, order cancellation window, session token duration, account lockout duration and threshold (REQ-4), and rate-limiting parameters; each field includes a descriptive hint and valid range note; "Save Changes" primary button triggers a confirmation dialog ("These changes will affect all active operations — confirm?") before persisting (REQ-42); change history log displayed at the bottom showing previous values, changed-by actor, and timestamp (NFR-11).

Admin — Manage Users Page:
- Loading → Search bar rendered immediately; user table shimmers.
- Empty → No users match search: inline "No results" message with "Clear filters"; not applicable as a platform-wide empty since at least the admin account exists.
- Error → Load failure with retry; individual action failure (e.g. suspend fails) shown as an inline color-error toast for that row.
- Success → Searchable table of all users (customers, managers, agents) showing: name, email/mobile, role chip, account status (Active / Locked / Suspended), and registration date (REQ-40); clicking a row opens a user detail panel showing profile data, order/review history link, and status management actions; administrators can view but not expose raw credentials (NFR-9); all status-change actions logged with actor and timestamp (NFR-11).
