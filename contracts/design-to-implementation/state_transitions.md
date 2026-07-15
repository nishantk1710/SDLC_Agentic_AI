# Customer Application Pages

Registration Page:
- Loading → Not applicable (static form); submit button shows inline spinner and disabled state while POST /auth/register is in-flight
- Empty  → Not applicable (form is always pre-rendered with blank fields)
- Error  → Inline field-level messages in color-error beneath each invalid field (e.g. "Email already in use", "Password too short"); account-locked banner shown in color-error at form top if five consecutive failures have been triggered; generic API failure shown as a non-dismissible inline alert above the submit button
- Success → User is redirected to a "Check your email / SMS" confirmation screen showing the verified contact and a resend link; no further form is shown

Email / Phone Verification Page:
- Loading → Full-width centered spinner with "Verifying your account…" caption while the token is validated against the backend on page mount
- Empty  → Not applicable (token is always present in the URL or the user is prompted to request a new one)
- Error  → Centered error card in color-error stating "This link is invalid or has expired" with a prominent "Resend verification" CTA in color-primary
- Success → Centered success illustration with color-success checkmark, "Account verified!" heading, and "Start ordering" CTA routing to the Home / Restaurant List page

Login Page:
- Loading → Not applicable (static form); submit button shows inline spinner and disabled state while credentials are posted
- Empty  → Not applicable (form always renders with blank fields)
- Error  → Inline error beneath the password field for wrong credentials; distinct locked-account alert banner ("Account locked until HH:MM – try again later") using color-warning; rate-limit error ("Too many attempts, please wait") in color-error
- Success → Session token stored; user is redirected to the page they originally requested or to the Home page

Forgot Password Page:
- Loading → Submit button shows inline spinner while the reset request is posted
- Empty  → Not applicable (single-field form always renders)
- Error  → Inline error in color-error if the email / phone is not found or the request is rate-limited
- Success → Confirmation message "A reset link has been sent to [contact]" replaces the form; resend option is offered after a countdown

Reset Password Page:
- Loading → Spinner on page mount while the token is validated
- Empty  → Not applicable
- Error  → If token is invalid or expired, error card with "This link has expired" and link back to Forgot Password; inline field errors for mismatched or too-weak passwords
- Success → "Password updated!" confirmation with a "Log in" CTA

Home / Restaurant List Page:
- Loading → Top skeleton loaders: address selector shimmer, then a grid of 6–8 restaurant card skeletons (image placeholder rectangle + text-line shimmer strips) in color-canvas with animated pulse
- Empty  → Illustration of an empty street with caption "No restaurants deliver to this address right now" and a suggestion to try a different address; address-change CTA in color-primary
- Error  → Full-page inline error banner "Couldn't load restaurants" with a "Retry" button in color-primary; partial data already rendered is preserved if a filter/sort refetch fails—only the list area shows the error banner
- Success → Responsive grid of restaurant cards each showing hero image, name, cuisine tags, average rating (star + number), estimated delivery time, delivery fee, and minimum order badge; filter/sort bar pinned below the top nav; "Closed" or "Outside delivery area" overlay on ineligible cards (REQ-8, REQ-11, REQ-12)

Search Results Page:
- Loading → Search input shows a spinner adornment; results area shows shimmer card skeletons matching the expected result count (capped at 8 placeholders)
- Empty  → "No results for '[query]'" illustration with suggestions to broaden the search term or clear active filters; filters remain visible and adjustable
- Error  → Inline error banner beneath the search bar: "Search failed – please try again" with a Retry CTA; search bar remains interactive
- Success → Mixed list of matching restaurant cards and matching menu-item cards (with their parent restaurant name); active filter chips displayed above results; sort controls visible; unavailable items marked with a muted "Unavailable" pill (REQ-12)

Restaurant Detail / Menu Page:
- Loading → Hero banner shimmer at full width, restaurant-info row skeleton (logo circle, name lines, rating/ETA/fee strips), then category tab skeletons followed by 4–6 menu item card skeletons
- Empty  → If a category has no available items, that category tab is hidden; if all categories are empty, "Menu coming soon" placeholder replaces the item list
- Error  → Inline error card in the menu body area "Couldn't load the menu – Retry"; restaurant header (name, rating, hours) is still shown if cached
- Success → Full-bleed banner image, restaurant name, cuisine chips, average rating, estimated delivery time, delivery fee, minimum order value, open/closed badge; sticky category tab bar; scrollable item list grouped by category; each item shows image, name, description, allergen/dietary tags (NFR-5), price, and an "Add" button (disabled + muted label for unavailable items, REQ-12); floating cart summary bar at the bottom when cart has items

Cart Page:
- Loading → Cart item rows show shimmer skeletons; price summary panel shows skeleton lines while totals are recalculated after a quantity change
- Empty  → Centered empty-cart illustration with caption "Your cart is empty" and a "Browse restaurants" CTA in color-primary
- Error  → Inline error banner at the top of the cart "Couldn't update your cart – Retry"; if an item has become unavailable since it was added, it is highlighted with a color-error border and an inline message "This item is no longer available – please remove it"; checkout CTA is disabled
- Success → List of cart items with quantity stepper (− / +) and remove icon per row; subtotal, taxes, delivery fee, service fee, and total in a summary panel; fulfillment toggle (Delivery / Pickup); saved-address selector for delivery (REQ-17); minimum-order shortfall warning in color-warning if subtotal is below threshold (REQ-16); "Proceed to Checkout" CTA in color-primary disabled until all validations pass

Checkout / Payment Page:
- Loading → Page skeleton while saved addresses and payment methods load; "Placing order…" full-screen overlay with spinner after the customer confirms (covers the form to prevent double-submit)
- Empty  → If no saved address exists and Delivery is selected, an inline prompt "Add a delivery address to continue" with an "Add Address" CTA is shown; the Checkout CTA remains disabled
- Error  → Payment gateway failure: inline error card "Payment unsuccessful – [gateway message]" with "Try a different method" and "Retry" CTAs; order is not confirmed; form remains editable; validation errors for missing fields shown inline in color-error near each field
- Success → Order confirmation screen replaces the checkout form: order number, itemized summary, total paid, estimated delivery time, and a "Track your order" CTA routing to the Order Tracking page (REQ-18)

Order Tracking Page:
- Loading → Map area shows a grey placeholder tile with a centered spinner; order status stepper shows skeleton lines; ETA strip shows shimmer
- Empty  → Not applicable (page is only reachable for an existing order)
- Error  → If the WebSocket connection drops, a banner "Live tracking unavailable – reconnecting…" in color-warning is shown; last known status and ETA are still displayed from cached data; map falls back to a static pin if the mapping API is unavailable (NFR-17)
- Success → Live map with agent location pin and route polyline updated within 5 s (NFR-4); horizontal status stepper showing the sequence Accepted → Preparing → Ready → Out for Delivery → Delivered with the current step highlighted in color-primary; agent name and ETA displayed; "Cancel order" CTA visible and active only while status is pendingRestaurantAcceptance (REQ-19); proof-of-delivery thumbnail shown once delivered

Order History Page:
- Loading → List of order-history card skeletons (order number shimmer, status badge shimmer, total shimmer)
- Empty  → "You haven't placed any orders yet" illustration with a "Start ordering" CTA
- Error  → Inline error banner "Couldn't load your order history – Retry"
- Success → Reverse-chronological list of order cards showing order number, restaurant name, date, status badge (color-coded by status), and total; tapping a card navigates to Order Detail; "Reorder" shortcut on each card; "Rate this order" CTA badge on delivered orders without a review (REQ-31)

Order Detail Page:
- Loading → Skeleton for the order header, item list, and payment summary while the order document is fetched
- Empty  → Not applicable (page is only reachable via a valid order ID)
- Error  → Inline error card "Couldn't load order details – Retry"
- Success → Order number, status badge, restaurant name, itemized list with unit prices and line totals, subtotal/tax/fee/total breakdown, fulfillment type and delivery address, payment method and reference, status history timeline; "Rate this order" section if delivered and not yet reviewed (REQ-31); "Cancel order" CTA if still in pendingRestaurantAcceptance (REQ-19)

Submit Review Page:
- Loading → Star rating widget and text area render immediately (no async load needed); submit button shows spinner while the review is posted
- Empty  → Not applicable (form always renders; text area is optional per REQ-31)
- Error  → Inline error in color-error below the star widget if no rating is selected on submit; API error displayed as an inline banner "Couldn't submit your review – Retry"; if a review already exists for this order the page shows "You've already reviewed this order" and disables the form (BR-6)
- Success → "Thank you for your review!" confirmation replaces the form with the submitted rating displayed; link back to Order History

Saved Addresses Page:
- Loading → List of address card skeletons while the user's savedAddresses array is fetched
- Empty  → "No saved addresses yet" with an "Add address" CTA in color-primary
- Error  → Inline error banner "Couldn't load your addresses – Retry"; add/edit form errors shown inline next to each field in color-error
- Success → List of address cards showing label, full address, and default badge; Edit and Delete actions on each card; "Set as default" toggle; "Add new address" button; delete confirmation dialog before removal (REQ-6)

Account / Profile Page:
- Loading → Avatar circle and name/email fields show shimmer skeletons while user data loads
- Empty  → Not applicable (authenticated user always has profile data)
- Error  → Inline error banner if the profile update POST fails; field-level inline errors in color-error for validation failures (e.g. invalid phone format)
- Success → Editable fields for first name, last name, email, phone, and avatar upload; notification preferences toggles (push, SMS, email); "Save changes" CTA in color-primary; success toast "Profile updated" on save; "Change password" link routing to a dedicated change-password form

---

# Restaurant Partner Portal Pages

Restaurant Portal Login Page:
- Loading → Submit button spinner while credentials are posted
- Empty  → Not applicable (static form)
- Error  → Inline error for wrong credentials; account-locked or suspended-account banner in color-error
- Success → Redirect to the Restaurant Dashboard

Restaurant Dashboard Page:
- Loading → KPI card skeletons (today's orders count, revenue, pending count), incoming-orders panel skeleton, open/closed toggle shimmer
- Empty  → KPI cards show "0" with explanatory caption; incoming-orders panel shows "No new orders" placeholder
- Error  → Inline error banner at the top of the dashboard if real-time WebSocket connection fails ("Live order alerts unavailable – reconnecting…" in color-warning); cached counts displayed if available
- Success → Open/Closed toggle prominent at the top (REQ-35); real-time incoming-orders panel with per-order Accept / Reject CTAs and an audible/visual alert for new arrivals (REQ-36, REQ-37); KPI summary cards (orders today, revenue today, pending count); quick-links to Menu Management and Order Queue

Order Queue Page (Restaurant):
- Loading → Table/list skeleton rows while active orders are fetched
- Empty  → "No active orders right now" placeholder with an icon
- Error  → Inline error banner "Couldn't load orders – Retry"; retry button in color-primary
- Success → Filterable list of active orders grouped by status (Pending Acceptance, Accepted, Preparing, Ready); each row shows order number, customer first name, items summary, total, time since placed; action buttons per row: Accept/Reject (pending), Mark Preparing (accepted), Mark Ready (preparing); reject flow opens an inline reason field (REQ-38); status changes reflected in real time via WebSocket

Order Detail Page (Restaurant):
- Loading → Skeleton for order header, items list, customer/delivery info
- Empty  → Not applicable
- Error  → Inline error card "Couldn't load order – Retry"
- Success → Full item list with quantities and prices, delivery address or pickup indicator, payment method, current status badge, action CTA appropriate to current status (Accept / Reject / Mark Preparing / Mark Ready); rejection reason textarea appears inline when Reject is chosen (REQ-38)

Menu Management Page:
- Loading → Category accordion skeletons with item-row shimmer strips inside each
- Empty  → "Your menu is empty – add a category to get started" CTA in color-primary
- Error  → Inline error banner if categories or items fail to save; field-level inline validation errors in color-error
- Success → Accordion list of menu categories each with sort order handle, availability toggle, Edit and Delete controls, and an expanded item list; each item row shows image thumbnail, name, price, availability toggle, Edit and Delete; "Add category" and "Add item" buttons; changes publish immediately to the customer-facing menu (REQ-34, REQ-35)

Add / Edit Menu Item Page:
- Loading → Form fields shimmer while existing item data loads (edit mode only)
- Empty  → Not applicable (form always renders)
- Error  → Inline field-level errors in color-error for required fields (name, price); API error banner if save fails
- Success → Form with fields for name, description, price, image upload, availability toggle, allergen/dietary tags (NFR-5), and sort order; "Save" CTA in color-primary; success toast on save; redirect back to Menu Management

Restaurant Settings Page:
- Loading → Settings form skeleton while the restaurant document is fetched
- Empty  → Not applicable (restaurant record always exists for an authenticated manager)
- Error  → Inline error banner if save fails; field-level inline errors for validation failures
- Success → Editable fields for restaurant name, description, cuisine types, delivery fee, minimum order value, estimated delivery time, delivery radius, operating hours per day, COD allowed toggle (REQ-20); "Save" CTA; changes take effect immediately

---

# Delivery Agent Pages

Agent Login Page:
- Loading → Submit button spinner during authentication
- Empty  → Not applicable
- Error  → Inline error for wrong credentials; locked-account banner in color-error
- Success → Redirect to Agent Home

Agent Home / Availability Page:
- Loading → Current assignment card and availability toggle shimmer on mount
- Empty  → "No active delivery assigned" placeholder when agent is available but has no current job
- Error  → Inline banner if availability status update fails ("Couldn't update availability – Retry") in color-warning; WebSocket disconnection indicated by a banner
- Success → Large availability toggle (single-tap per NFR-6); current delivery card if a job is active showing restaurant name, pickup address, drop-off address, and ETA; "View job details" CTA

Incoming Job Offer Page:
- Loading → Job details load immediately from the WebSocket push; no async fetch required; countdown timer starts on render
- Empty  → Not applicable (page only appears when a job is actively offered)
- Error  → If the accept/decline POST fails, an inline retry option is shown; timer continues running
- Success → Restaurant name, pickup address, customer drop-off area, estimated distance, countdown timer showing time remaining to respond (REQ-26); large "Accept" CTA in color-primary and "Decline" secondary CTA, both ≥44 × 44 px and single-tap (NFR-6)

Active Delivery Page:
- Loading → Map tile loads asynchronously; order details are pre-loaded from the accepted-job payload; spinner shown only in the map region
- Empty  → Not applicable
- Error  → Map API failure shows a static address text fallback with the route described in words (NFR-17); status update POST failure shows a dismissible inline banner "Update failed – tap to retry" in color-error
- Success → Live map showing current position and destination pin; pickup and drop-off addresses; order summary (restaurant, items count, customer name); sequential single-tap action buttons: "Picked Up" → "Out for Delivery" → "Mark Delivered" (NFR-6, REQ-29); "Mark Delivered" triggers optional camera prompt for proof-of-delivery photo (REQ-29); all CTAs ≥44 × 44 px

Delivery History Page (Agent):
- Loading → List of past delivery card skeletons
- Empty  → "No completed deliveries yet" placeholder
- Error  → Inline error banner "Couldn't load history – Retry"
- Success → Reverse-chronological list showing order number, restaurant, drop-off area, completion time, and status badge (Delivered / Failed / Cancelled)

---

# Admin Console Pages

Admin Login Page:
- Loading → Submit button spinner; rate-limit protection active
- Empty  → Not applicable
- Error  → Inline error for wrong credentials; locked or suspended account banner in color-error
- Success → Redirect to Admin Dashboard

Admin Dashboard Page:
- Loading → KPI metric card skeletons (total orders, revenue, open disputes, pending approvals)
- Empty  → KPI cards show "0" with date-range context; no list items in alert panels
- Error  → Inline error banner "Couldn't load dashboard data – Retry"; individual panels degrade independently per NFR-17
- Success → KPI cards for orders today, revenue today, open disputes count, restaurants pending approval; quick-access panels for Pending Disputes and Pending Restaurant Approvals; navigation links to all major admin sections

User Management Page:
- Loading → Table skeleton rows while the paginated user list loads
- Empty  → "No users match the current filters" with a "Clear filters" CTA
- Error  → Inline error banner above the table "Couldn't load users – Retry"
- Success → Searchable, filterable (by role, status) paginated table of users showing name, email/phone, role badge, status badge, and created date; row-level actions: View, Suspend, Reactivate (REQ-39); bulk-search by name or email (REQ-40)

User Detail Page (Admin):
- Loading → Detail panel skeleton while the user document is fetched
- Empty  → Not applicable
- Error  → Inline error card "Couldn't load user – Retry"
- Success → Full user profile read-only display (name, contact, role, status, verification status, saved addresses, registration date); status controls: Suspend / Reactivate / Unsuspend with confirmation dialog; audit trail of admin actions on this user (REQ-39); for delivery agents, shows vehicle info and availability state

Restaurant Management Page:
- Loading → Table skeleton rows while restaurant list loads
- Empty  → "No restaurants match the current filters" with "Clear filters"
- Error  → Inline error banner above the table "Couldn't load restaurants – Retry"
- Success → Searchable, filterable (by status, cuisine) paginated table showing name, status badge, cuisine, average rating, and created date; row-level actions: View, Approve, Suspend, Reactivate (REQ-39)

Restaurant Detail Page (Admin):
- Loading → Detail skeleton while restaurant document loads
- Empty  → Not applicable
- Error  → Inline error card "Couldn't load restaurant – Retry"
- Success → Restaurant profile (name, address, cuisine, delivery radius, fee, commission rate, status); status action buttons (Approve / Suspend / Reactivate) with confirmation dialogs; read-only menu preview; link to this restaurant's orders; commission rate override field with Save CTA

Order Management Page:
- Loading → Table skeleton rows with shimmer
- Empty  → "No orders match the current filters" with "Clear filters" CTA
- Error  → Inline error banner "Couldn't load orders – Retry"
- Success → Searchable, filterable (by status, date range, restaurant, customer) paginated table showing order number, restaurant name, customer name, status badge, total, payment status, and created timestamp; row-level "View" action (REQ-40)

Order Detail Page (Admin):
- Loading → Detail skeleton while the order, payment, and delivery documents are fetched
- Empty  → Not applicable
- Error  → Inline error card "Couldn't load order – Retry"
- Success → Full order breakdown (items, pricing, fees, commission snapshot); payment record (method, status, gateway reference, refund history); delivery record (agent, status, assignment attempts); order status history timeline; "Issue Refund" CTA (opens inline amount + reason form, REQ-24, BR-7); "Cancel Order" CTA with reason field; links to related dispute if one exists

Dispute Management Page:
- Loading → Table skeleton rows while dispute list loads
- Empty  → "No disputes match the current filters" placeholder
- Error  → Inline error banner "Couldn't load disputes – Retry"
- Success → Filterable (by status) paginated table of disputes showing dispute ID, order number, customer name, status badge, and created date; row-level "Review" action; disputes in "open" status highlighted with color-warning indicator (REQ-41)

Dispute Detail Page:
- Loading → Detail skeleton while dispute, order, and payment data are fetched
- Empty  → Not applicable
- Error  → Inline error card "Couldn't load dispute – Retry"
- Success → Customer description, linked order summary card, payment method and amount; status badge; resolution section with status selector (Under Review / Resolved – Refund / Resolved – No Action / Closed), resolution notes textarea, and optional refund amount input; "Submit Resolution" CTA in color-primary; if a refund is issued the gateway response status is shown inline after submission (REQ-41, REQ-24)

Review Moderation Page:
- Loading → Table skeleton rows while published reviews load
- Empty  → "No reviews to moderate" placeholder
- Error  → Inline error banner "Couldn't load reviews – Retry"
- Success → Filterable (by restaurant, status) paginated table showing review ID, restaurant name, customer name, rating stars, comment excerpt, status badge, and submitted date; "Remove" action on published reviews opens a confirmation dialog with a required reason field; removed reviews shown with "Removed by Admin" muted badge (REQ-33, BR-7)

Platform Configuration Page:
- Loading → Configuration form skeleton while the platformConfigs document is fetched
- Empty  → Not applicable (singleton config always exists after first boot)
- Error  → Inline error banner if fetch or save fails; field-level inline errors for out-of-range values in color-error
- Success → Labeled input fields for default commission rate, service fee, default delivery radius, session token TTL, account lock duration, agent offer timeout, cancellation charge percentage, and max failed login attempts (REQ-42); current values pre-populated; "Save changes" CTA in color-primary; success toast confirming save; all changes written to AdminAuditLog automatically

Admin Audit Log Page:
- Loading → Table skeleton rows while the paginated audit log loads
- Empty  → "No audit log entries for the selected filters" with "Clear filters" CTA
- Error  → Inline error banner "Couldn't load audit log – Retry"
- Success → Searchable, filterable (by actor, action type, target collection, date range) read-only paginated table showing timestamp, actor name, action, target collection, target ID, and IP address; no edit or delete controls (log is immutable); export-to-CSV button
