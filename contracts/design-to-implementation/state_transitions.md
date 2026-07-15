# Customer Application Pages

Registration Page:
- Loading → Full-page spinner overlaid on the form while the registration request is in flight; submit button disabled and shows "Creating account…" label
- Empty   → N/A (form always renders with blank fields; no pre-existing data required)
- Error   → Inline validation messages in color-error beneath each offending field (e.g. "Email already in use," "Password too short"); a top-of-form banner in color-error if the server returns a non-field-specific error (e.g. rate limit hit); submit button re-enabled
- Success → Form replaced by a confirmation panel: icon + "Check your email / phone" heading, brief instruction to click the verification link, and a resend link

Email / Phone Verification Page:
- Loading → Spinner while the token is being validated on mount (token read from URL query param and sent to API automatically)
- Empty   → N/A (token is always present in URL or the page shows the Error state)
- Error   → Centered card with color-error icon; message distinguishes "Link expired" from "Link already used" from "Invalid link"; primary CTA button "Resend verification" triggers a new token
- Success → Centered card with color-success checkmark; "Your account is verified" heading; auto-redirect to Login after 3 seconds with a manual link as fallback

Login Page:
- Loading → Submit button disabled and labeled "Signing in…"; form fields read-only; inline spinner beside button
- Empty   → N/A (form always renders empty; no data fetch required)
- Error   → Inline color-error message below the password field for bad credentials; distinct locked-account banner (color-warning) showing "Account locked — try again in X minutes" when `lockedUntil` is active; rate-limit error shown as top-of-form banner
- Success → Session token stored; user redirected to their role-appropriate home page (Restaurant Listing for customers)

Forgot Password Page:
- Loading → Submit button disabled and labeled "Sending…" while the reset-link request is in flight
- Empty   → N/A (single input form, always rendered)
- Error   → Inline color-error message below the email/phone field (e.g. "No account found for this address"); top-of-form banner for rate-limit errors
- Success → Input replaced by confirmation panel: "Reset link sent" heading, instruction to check email/SMS, note that the link expires in N minutes

Reset Password Page:
- Loading → Spinner while token validity is checked on mount
- Empty   → N/A
- Error   → Full-panel color-error message if token is invalid or expired, with a "Request new link" CTA; inline field-level errors (e.g. "Passwords do not match") during form submission
- Success → "Password updated" confirmation card with color-success icon; auto-redirect to Login after 3 seconds

Restaurant Listing / Home Page:
- Loading → Address bar and search bar rendered; below them a grid of skeleton cards (logo placeholder, shimmer lines for name, rating, delivery time) matching the expected result density
- Empty   → Illustrated empty-state graphic; heading "No restaurants available"; body copy "We couldn't find any open restaurants delivering to your address right now — try a different address or check back later"; address-edit CTA
- Error   → Error card with color-error icon; "Couldn't load restaurants" heading; short message (network issue, service unavailable); "Try again" retry button; if the Mapping API failed specifically, a banner "Location services unavailable — delivery radius may not apply"
- Success → Search bar, active filter chips (cuisine, price range, min rating, delivery time), sort controls; responsive grid of restaurant cards each showing logo/banner thumbnail, name, cuisine tags, avg rating (star + number), estimated delivery time, delivery fee, minimum order value, and an "Unavailable" overlay badge when `isOpen` is false or outside operating hours

Restaurant Detail / Menu Page:
- Loading → Hero banner skeleton; restaurant meta row skeleton (name, rating, delivery fee, ETA chips); below, category tab bar skeleton and a list of item card skeletons with shimmer
- Empty   → Restaurant header renders normally; below it an empty-state message "This restaurant hasn't added any menu items yet" (only plausible during onboarding edge case)
- Error   → Restaurant header area shows a color-error banner "Couldn't load menu — please try again"; retry button; rest of page blank
- Success → Sticky hero banner with restaurant photo; meta row showing avg rating, delivery fee, estimated delivery minutes, minimum order value, cuisine types, open/closed status badge; sticky horizontal category tab bar auto-generated from `menuCategories`; each category section lists item cards with photo, name, description, price, allergen/dietary tags (from `allergens` and `tags` fields), and an "Unavailable" chip + disabled add-button when `isAvailable` is false; floating cart summary bar at bottom when cart has items

Cart Page:
- Loading → Skeleton rows for each cart item plus skeleton totals block while the cart document is fetched; checkout button disabled
- Empty   → Centered illustration of an empty bowl; "Your cart is empty" heading; "Browse restaurants" CTA button routing back to Restaurant Listing
- Error   → Top-of-page color-error banner "Couldn't load your cart"; retry button; if a specific item has become unavailable since it was added, an inline color-warning chip on that item row reading "No longer available — remove to continue"
- Success → Restaurant name header with a "Clear cart" link; scrollable list of item rows (thumbnail, name, unit price, quantity stepper, line total, remove icon, optional special instructions); totals block showing subtotal, delivery fee, tax, and total recalculated live on every quantity change; minimum-order shortfall banner in color-warning when subtotal < `minimumOrderValue`; fulfillment toggle (Delivery / Pickup); saved-address selector dropdown when Delivery is chosen; disabled "Proceed to Checkout" button with tooltip when minimum order not met, enabled otherwise

Checkout Page:
- Loading → Skeleton for delivery address confirmation, order summary, and payment method selector while saved addresses and cart snapshot are fetched; place-order button disabled
- Empty   → If no saved address exists and fulfillment is Delivery, inline prompt card "Add a delivery address to continue" with an "Add address" inline form or modal
- Error   → Payment gateway failure renders a color-error banner "Payment failed — [gateway reason]" with a "Try a different method" CTA and keeps the order in unpaid state; address-out-of-radius error shows inline color-error below address selector; general API error shows top-of-page banner with retry
- Success → Two-column layout (mobile: stacked): left — confirmed delivery address with edit link, fulfillment type, special instructions field; right — order summary (item list, subtotal, delivery fee, tax, total); payment method selector (card via gateway iframe/hosted fields, digital wallet, COD if `allowsCashOnDelivery`); primary "Place Order" button (color-primary, 44 × 44 px minimum); processing spinner on button after tap

Order Confirmation Page:
- Loading → Spinner with "Confirming your order…" while the order-creation and payment-authorization round trip completes (target ≤ 3 s per NFR-2)
- Empty   → N/A (page is always navigated to with a freshly created order)
- Error   → Full-page error state with order reference if partially created: color-error icon, "Something went wrong" heading, explanation ("Payment could not be confirmed"), suggested action ("Check your order history or contact support"), order number if available
- Success → color-success checkmark animation; "Order placed!" heading; order number prominently displayed; estimated delivery time; summary of items and total; "Track Order" primary CTA; "Continue Browsing" secondary link

Order Tracking Page:
- Loading → Status stepper skeleton; map area skeleton (grey rectangle); ETA chip skeleton; order summary skeleton below
- Empty   → N/A (page always opened from a specific order reference)
- Error   → If order fetch fails: color-error banner "Couldn't load order details" with retry; if Mapping API unavailable: map area replaced by color-warning banner "Live map unavailable — status updates will still appear"; order status stepper still renders from order document
- Success → Horizontal or vertical status stepper showing the sequence Accepted → Preparing → Ready → Out for Delivery → Delivered with current step highlighted in color-primary and completed steps in color-success; live map panel with agent location pin and route polyline while status is "Out for Delivery" (updated ≤ 5 s per NFR-4); ETA chip updated in real time; order items summary; agent name and vehicle info when assigned; "Cancel Order" button visible and enabled only while status is "pendingRestaurantAcceptance" (per BR-1); cancellation-charge warning modal shown if cancellation attempted after acceptance

Order History Page:
- Loading → List of skeleton order-summary cards with shimmer (order number, date, restaurant name, total, status chip)
- Empty   → Centered illustration; "No orders yet" heading; "Start browsing" CTA button
- Error   → color-error banner "Couldn't load your orders"; retry button
- Success → Chronologically sorted list of order cards each showing order number, restaurant name snapshot, date, item count, total, and a color-coded status chip; "Reorder" quick-action button; "Leave a Review" CTA on delivered orders without a review; tapping a card navigates to Order Detail

Order Detail Page:
- Loading → Skeleton for order meta header, item list, totals, payment info, and status history timeline
- Empty   → N/A
- Error   → color-error banner with retry
- Success → Order number, placed-at timestamp, restaurant name; item list with quantities and line totals; pricing breakdown (subtotal, delivery fee, tax, total); payment method and status; fulfillment type and delivery address; status history timeline; refund details if applicable; "Rate this Order" CTA when status is "delivered" and `reviewId` is null

Leave a Review Page:
- Loading → Skeleton star-rating row and text area while order eligibility is verified
- Empty   → N/A
- Error   → If order is not eligible (not delivered, or review already submitted): full-panel informational message "Review not available" with explanation; if submission fails: inline color-error banner with retry
- Success → Restaurant name and order reference shown as context; 1–5 star tap-to-select rating widget (color-secondary for filled stars); optional text area for comment; character count indicator; "Submit Review" primary button; confirmation toast "Review submitted" on success; CTA to return to Order History

Customer Profile / Account Page:
- Loading → Skeleton avatar circle, skeleton name line, skeleton for each section (saved addresses, notification preferences)
- Empty   → Saved addresses sub-section shows "No saved addresses" with an "Add address" CTA when `savedAddresses` array is empty
- Error   → color-error banner "Couldn't load your profile" with retry
- Success → Avatar (or initials fallback), full name, email/phone; editable full-name and avatar-upload fields; Saved Addresses section listing each address with label, full address string, default badge, edit and delete controls, and "Add new address" button; Change Password section; notification preferences toggles; Logout button

Saved Address Add / Edit Modal (within Profile Page):
- Loading → Modal opens with a spinner while geocoding API resolves coordinates for a pasted address on save
- Empty   → Blank form fields when adding a new address
- Error   → Inline color-error messages for required fields; color-warning banner if geocoding fails ("Address could not be verified — please check and retry")
- Success → Modal closes; updated address list reflects the change immediately; success toast "Address saved"

---

# Restaurant Partner Portal Pages

Restaurant Manager Login Page:
- Loading → Submit button disabled, labeled "Signing in…"
- Empty   → Blank credential form
- Error   → Inline color-error for bad credentials; locked-account banner in color-warning
- Success → Redirect to Restaurant Dashboard

Restaurant Dashboard Page:
- Loading → Skeleton stat tiles (today's orders, revenue, avg rating); skeleton incoming-order queue
- Empty   → Stat tiles show zeroes; incoming-order queue shows "No pending orders" empty state with a waving-hand illustration
- Error   → color-error banner "Couldn't load dashboard data"; retry; WebSocket disconnection shown as a persistent color-warning top banner "Live order updates paused — reconnecting…"
- Success → Summary stat tiles (orders today, revenue today, avg rating, open/closed toggle); real-time incoming-order queue with per-order card showing order number, customer name, item count, total, and Accept / Reject action buttons; active orders section showing orders in Accepted / Preparing / Ready states with advance-status CTA per card; restaurant open/closed toggle prominent in top bar

Incoming Order Detail Modal (within Dashboard):
- Loading → Spinner while full order details are fetched after clicking an order card
- Empty   → N/A
- Error   → color-error banner inside modal with retry
- Success → Full item list with quantities and special instructions; customer delivery address; order total; Accept (color-success) and Reject (color-error) primary action buttons; rejection requires a reason text field (REQ-38) before confirming; timer countdown showing acceptance window remaining

Order Management Page (Active & Past Orders):
- Loading → Skeleton order rows in a table/list
- Empty   → "No orders found" with date-range filter hint
- Error   → color-error banner with retry
- Success → Filterable, sortable table of orders with columns: order number, placed time, customer name, items summary, total, current status chip, action button (Advance to Preparing / Ready where applicable); date-range and status filters; search by order number

Menu Management Page:
- Loading → Skeleton category accordions with skeleton item rows inside
- Empty   → "No menu categories yet" empty state with "Add category" primary CTA (shown when `menuCategories` is empty)
- Error   → color-error banner "Couldn't load menu" with retry
- Success → List of collapsible category sections each showing category name, availability toggle, sort-order handle, edit and delete controls, and a nested list of item cards; each item card shows thumbnail, name, price, availability toggle, allergen tags, edit and delete icons; "Add category" and "Add item to category" CTAs; inline edit forms expand in-place on edit action; unsaved-changes confirmation dialog on navigation away

Menu Item Add / Edit Form (inline or modal within Menu Management):
- Loading → Spinner on save while the updated restaurant document is persisted and the response returns
- Empty   → Blank fields when adding a new item
- Error   → Inline color-error for required fields (name, price); color-error banner for API save failure
- Success → Form collapses / modal closes; item appears or is updated in the category list immediately; success toast "Item saved"

Restaurant Settings Page:
- Loading → Skeleton for restaurant profile fields, operating-hours table, and delivery settings
- Empty   → N/A (settings are always pre-populated from the restaurant document)
- Error   → color-error banner "Couldn't load settings" with retry; inline save errors appear near the relevant section
- Success → Editable fields: restaurant name, description, cuisine types, logo/banner upload, delivery fee, minimum order value, estimated delivery minutes, delivery radius, cash-on-delivery toggle, operating-hours table (days × open/close times); save button per section or a global save; success toast on save

---

# Delivery Agent App Pages

Agent Login Page:
- Loading → Submit button disabled, labeled "Signing in…"
- Empty   → Blank credential form
- Error   → Inline color-error for bad credentials; locked-account banner
- Success → Redirect to Agent Home / Job Queue

Agent Home / Job Queue Page:
- Loading → Skeleton for availability toggle and offered-job card
- Empty   → Availability toggle shown; "No jobs available right now" message when `agentProfile.isAvailable` is true but no delivery has been offered
- Error   → color-error banner "Couldn't connect to dispatch"; WebSocket reconnection banner
- Success → Prominent availability toggle (Online / Offline) at top; when a job is offered: full-screen modal-style job card showing restaurant name, pickup address, drop-off address, estimated distance, time limit countdown (offer expiry per `offerExpiresAt`); single-tap Accept (color-success) and Decline (color-error) buttons (≥ 44 × 44 px, minimal interaction per NFR-6)

Active Delivery Page:
- Loading → Spinner while delivery details are fetched after accepting a job
- Empty   → N/A (only reached after accepting a job)
- Error   → color-error banner "Couldn't load delivery details" with retry; if location permission denied, color-warning banner "Location access needed to update your position — tap to enable"
- Success → Map showing agent's current position, restaurant pin (pickup), and customer pin (drop-off); order summary (items count, order number, restaurant name, customer address); large single-tap status-advance button ("Picked Up" → "Delivered") per NFR-6; camera capture button for optional proof-of-delivery photo (active only at "Delivered" step); ETA to next waypoint; all controls thumb-reachable at bottom of screen

Agent Order History Page:
- Loading → Skeleton list of past delivery cards
- Empty   → "No completed deliveries yet"
- Error   → color-error banner with retry
- Success → List of completed deliveries with order number, restaurant name, customer address, delivered-at timestamp, and earnings per trip

Agent Profile Page:
- Loading → Skeleton for profile fields
- Empty   → N/A
- Error   → color-error banner with retry
- Success → Full name, vehicle type, licence plate (editable); availability toggle; browser location-permission status indicator; change-password section; logout button

---

# Admin Console Pages

Admin Login Page:
- Loading → Submit button disabled, labeled "Signing in…"
- Empty   → Blank credential form
- Error   → Inline color-error for bad credentials; locked-account banner; rate-limit warning
- Success → Redirect to Admin Dashboard

Admin Dashboard Page:
- Loading → Skeleton KPI tiles and skeleton recent-activity feed
- Empty   → KPI tiles show zeroes on a brand-new installation; activity feed shows "No recent activity"
- Error   → color-error banner "Couldn't load dashboard"; retry
- Success → KPI tiles (total orders today, revenue today, active restaurants, active agents, open disputes); recent orders feed; quick-nav cards to each major admin section; system-health indicators for external integrations (Payment Gateway, Mapping API, Messaging Provider) showing up/degraded/down

Restaurant Management Page:
- Loading → Skeleton table rows while restaurant list is fetched
- Empty   → "No restaurants found" for the active filter set; "Onboard your first restaurant" CTA when the platform has no restaurants at all
- Error   → color-error banner with retry
- Success → Searchable, filterable table of restaurants (name, cuisine, status chip, avg rating, onboarded date, manager email); status filter (active / suspended / pending); per-row actions: View, Suspend, Reactivate; "Onboard New Restaurant" primary CTA button; bulk-action checkboxes for suspend/reactivate

Restaurant Onboarding / Edit Form Page:
- Loading → Spinner while existing restaurant data loads (edit mode) or blank (create mode)
- Empty   → All fields blank in create mode
- Error   → Inline color-error per required field; top-of-form banner for API errors (e.g. slug conflict)
- Success → Form with all restaurant fields (name, slug, address with geocoding, cuisine types, delivery fee, min order value, delivery radius, commission rate, manager account assignment); save creates/updates the restaurant document and triggers a success toast; admin redirected back to Restaurant Management list

User Management Page:
- Loading → Skeleton table rows
- Empty   → "No users found" for the active search/filter
- Error   → color-error banner with retry
- Success → Searchable table of users filterable by role and status; columns: full name, email/phone, role chip, status chip, created date; per-row actions: View, Suspend, Reactivate; row click navigates to User Detail

User Detail Page:
- Loading → Skeleton for profile header and linked-entity sections
- Empty   → N/A
- Error   → color-error banner with retry
- Success → User profile (name, email/phone, role, status, verified badge, created date); for agents: vehicle info and availability status; for managers: linked restaurant with link to Restaurant Detail; order count with link to filtered Order Management; Suspend / Reactivate / Reset Password action buttons; confirmation dialogs for destructive actions

Order Management (Admin) Page:
- Loading → Skeleton table rows
- Empty   → "No orders match the current filters"
- Error   → color-error banner with retry
- Success → Searchable, filterable (by status, date range, restaurant, customer) table of all platform orders; columns: order number, customer, restaurant, total, payment status, order status chip, placed-at timestamp; row click navigates to Admin Order Detail

Admin Order Detail Page:
- Loading → Skeleton for order data, payment block, delivery block, and dispute block
- Empty   → N/A
- Error   → color-error banner with retry
- Success → Full order data mirroring customer Order Detail plus: payment record (method, gateway ref, status, refund history); delivery record (agent name, status, proof-of-delivery photo thumbnail); status history timeline; dispute / resolution section; admin action buttons: Issue Refund (full or partial), Cancel Order, with confirmation modals and required reason text fields; all actions written to adminAuditLogs

Disputes Page:
- Loading → Skeleton dispute card list
- Empty   → "No open disputes" with a color-success checkmark illustration
- Error   → color-error banner with retry
- Success → List of orders flagged as disputed, each card showing order number, customer name, dispute description, current order/payment status, and date raised; per-card CTA "Review Dispute" navigating to Admin Order Detail; filter tabs: Open / Resolved / All

Platform Configuration Page:
- Loading → Skeleton key-value rows while `platformConfigs` collection is fetched
- Empty   → "No configuration keys found" (should not occur in a seeded installation; shown as a safeguard)
- Error   → color-error banner "Couldn't load configuration" with retry; inline save error banner if a specific key update fails
- Success → Table of editable configuration parameters (key, current value, description, last-updated-by, last-updated-at); inline edit input per row with a Save button; confirmation dialog for high-impact parameters (e.g. commission rate, delivery radius); success toast on save; all saves logged to adminAuditLogs

Audit Log Page:
- Loading → Skeleton table rows
- Empty   → "No audit log entries found" for the active filter
- Error   → color-error banner with retry
- Success → Append-only table of administrative actions; columns: timestamp, admin name, action type, entity type, entity ID (linked to relevant detail page); search by admin, entity type, date range; read-only (no edit or delete controls); export to CSV button
