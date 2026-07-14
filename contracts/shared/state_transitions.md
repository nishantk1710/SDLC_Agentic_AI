Registration Page:
- Loading → Full-page spinner overlay on the form while the registration request is in flight; submit button disabled and shows a loading indicator; no fields are editable during submission.
- Empty → Blank registration form with fields for email address or mobile number and password; inline placeholder text in each field; primary "Create Account" button in color-primary (disabled until required fields are non-empty); no error or success messaging visible.
- Error → Inline color-error messages appear directly beneath the offending field (e.g., "Email already in use," "Password too short," "Invalid mobile number format"); form remains editable so the user can correct and resubmit; if the server is unreachable, a non-blocking banner at the top of the form reads "Something went wrong — please try again."
- Success → Form replaced by a confirmation notice informing the user that a verification email or SMS has been sent; prompt to check their inbox or messages; a resend link is shown in a muted style; no navigation away until the user acts.

Email / Mobile Verification Page:
- Loading → Spinner shown while the system validates the submitted verification code or token; input and confirm button are disabled.
- Empty → Single-field form (OTP input or indication that the link was clicked) with instructional copy explaining the user should enter the code sent to their email or mobile; "Verify" button in color-primary (disabled until the field is non-empty).
- Error → Inline color-error message beneath the input: "Invalid or expired code — please try again" or "This link has expired"; option to request a new code shown as an active resend link; if the account is already verified, an informational notice with a link to log in.
- Success → Success icon in color-success with message "Your account has been verified"; automatic redirect to the home or login page after a brief pause (with a manual "Continue" button as fallback).

Login Page:
- Loading → Submit button replaced by a spinner; all inputs disabled while credentials are being checked.
- Empty → Form with email-or-mobile and password fields, both showing placeholder text; "Sign In" button in color-primary (disabled until both fields are non-empty); links to registration and password reset visible but not intrusive.
- Error → Inline color-error message beneath the relevant field or beneath the form for general failures ("Incorrect email or password"); after five consecutive failures, a color-warning banner replaces the form explaining the account is locked and stating the lockout duration; rate-limit errors surfaced as a banner ("Too many attempts — please wait before trying again").
- Success → Loading state transitions immediately to a redirect; no persistent success message shown on this page.

Forgot Password Page:
- Loading → Submit button shows a spinner and is disabled while the reset request is being sent.
- Empty → Single input for email or mobile number with placeholder; "Send Reset Link" button in color-primary (disabled until the field is non-empty).
- Error → Inline color-error beneath the input for invalid format; if the email or number is not found, a neutral message is shown (to avoid account enumeration): "If that address is registered, a reset link has been sent"; server errors produce a top-of-form banner with a retry prompt.
- Success → Form replaced by a confirmation message: "A password reset link has been sent — it expires in [configured duration]"; resend option visible; link to return to login.

Reset Password Page:
- Loading → Submit button disabled with spinner while the new password is being saved.
- Empty → Two fields: new password and confirm password, both blank with placeholder; "Set New Password" button in color-primary (disabled until both fields are non-empty); if the reset token is not yet validated, a brief inline spinner shows while the token is checked.
- Error → Expired or invalid token: the entire form is replaced by a color-error notice with a link to request a new reset; password mismatch or insufficient strength: inline color-error beneath the relevant field; server error: banner at the top of the form.
- Success → Form replaced by a success notice: "Your password has been updated"; button to go to the Login page.

Home / Restaurant Listing Page:
- Loading → Top navigation bar and address selector render immediately; below them, a grid or list of skeleton-card placeholders (rounded rectangles matching card dimensions) animate in color-muted while restaurant data fetches; filter and sort controls visible but disabled.
- Empty → Address selector and search bar are visible and functional; content area shows an illustrated empty state with copy "No restaurants are currently delivering to your location" or "No results match your filters"; a suggestion to broaden filters or change the delivery address; filter/sort controls remain active so the user can adjust without a full reload.
- Error → Skeleton placeholders replaced by a full-width error panel with a color-error icon, message "We couldn't load restaurants right now," and a "Try Again" button in color-primary; navigation bar and address selector remain functional so the user is not completely blocked.
- Success → Grid or list of restaurant cards, each showing the restaurant photo as the hero image, name (font-h3), cuisine tag, average rating with star icon in color-secondary, estimated delivery time, delivery fee, and minimum order value (REQ-11); "Closed" or "Unavailable" badge in color-muted overlaid on cards for non-deliverable restaurants (REQ-12); filter chips (cuisine, price range, minimum rating, delivery time) and sort control above the list; search bar pre-populated if a search was performed; cards are scrollable; no pagination controls interrupt the flow.

Search Results Page:
- Loading → Search bar shows the current query; below it, skeleton cards animate while results are fetched; filter controls rendered but disabled.
- Empty → Search bar with current query retained; illustration and copy "No restaurants or items match '[query]'" with suggestions to check spelling or try a broader term; active filter chips shown so the user can remove them; "Clear Filters" shortcut.
- Error → Error panel with message "Search is unavailable right now" and a "Retry" button; search bar remains editable so the user can try a different query.
- Success → List of matching restaurants and/or menu items, grouped by type if both appear; each restaurant result shows the same metadata as the listing page; each menu-item result shows the item name, the restaurant it belongs to, price, and a thumbnail; unavailable items shown with a disabled style and "Unavailable" label (REQ-12); filter and sort controls at the top remain interactive for refinement.

Restaurant Detail / Menu Page:
- Loading → Restaurant hero image area renders as a color-muted skeleton; name, rating, and metadata row animate as placeholder bars; menu category tabs render as pill skeletons; below them, item-card skeletons fill the viewport.
- Empty → Shown when a restaurant has no menu items configured: hero and restaurant metadata display correctly; menu area shows an illustrated empty state with copy "This restaurant's menu is not available yet"; no "Add to Cart" affordance is presented.
- Error → If the restaurant detail call fails, the hero area shows the restaurant name (if cached) with an error panel below: "Menu could not be loaded — try again"; "Retry" button in color-primary; if the mapping/ETA service is unavailable, the delivery estimate field shows "ETA unavailable" in color-muted without blocking the rest of the page (NFR-17).
- Success → Hero food photography fills the top; restaurant name (font-h1), cuisine, average rating, estimated delivery time, delivery fee, minimum order value, and open/closed status clearly visible; if closed, a color-warning banner states "Currently closed — opens at [time]" and "Add to Cart" is disabled for all items; menu categories shown as horizontal scrollable tabs; items listed per category with name (font-h3), description, price, allergen and dietary tags (NFR-5); unavailable items shown with a grayed-out card and "Unavailable" label — Add button absent or disabled (REQ-12); available items have a prominent "Add" button in color-primary meeting the 44 × 44 px tap-target requirement; a persistent cart summary bar appears at the bottom once at least one item is in the cart.

Cart Page:
- Loading → Cart line items and totals area show skeleton placeholders while the cart is fetched or recalculated after a change; action buttons are disabled during recalculation.
- Empty → Illustrated empty state with copy "Your cart is empty" and a "Browse Restaurants" button in color-primary that navigates back to the listing page; no totals or checkout controls are shown.
- Error → If a recalculation call fails, an inline color-error banner beneath the item list states "We couldn't update your cart — please try again" with a Retry button; if an item has become unavailable since it was added, that line item is highlighted in color-warning with the message "This item is no longer available" and an option to remove it; checkout is blocked until unavailable items are resolved.
- Success → List of cart items, each showing name, customization notes (if any), quantity stepper (minus / count / plus), per-item price, and a remove icon; order subtotal, taxes, delivery fee, and total dynamically updated on any quantity change (REQ-15); if the subtotal is below the restaurant's minimum order value, the shortfall is shown in color-warning ("Add [amount] more to reach the minimum order") and the "Proceed to Checkout" button is disabled (REQ-16); delivery method selector (Delivery / Pickup) with saved-address picker for Delivery (REQ-17); single-restaurant enforcement message shown in color-warning if the user somehow arrives with mixed items; "Proceed to Checkout" button in color-primary, full-width, 44 px tall.

Checkout Page:
- Loading → Spinner overlay on the page while the order is being submitted to the backend; all inputs and the confirm button are disabled; a message reads "Placing your order…"
- Empty → Not applicable as a distinct state; the page is pre-populated from cart data and is only reachable with a non-empty cart.
- Error → Payment gateway failure: a color-error panel below the payment section states "Payment could not be processed — please check your details or try a different method" with a Retry button; the order is not created and no charge is made; delivery address outside the restaurant's radius: inline color-error beneath the address picker (BR-4); if the restaurant has closed between cart and checkout, a color-warning banner states "This restaurant is now closed — you cannot place this order"; individual field validation errors appear inline beneath each field.
- Success → Order confirmation screen replaces the checkout form: a color-success checkmark icon, "Order Confirmed!" heading (font-h1), order reference number, summary of items, total charged, estimated delivery time; a "Track My Order" button in color-primary and a "Back to Home" secondary link; push and SMS notifications have been dispatched in the background (REQ-30).

Order Tracking Page:
- Loading → Status timeline bar and map area show skeleton placeholders; ETA text shows "Calculating…" in color-muted; order summary section renders from cached data immediately if available.
- Empty → Not applicable; the page is only reachable for an existing order.
- Error → If the real-time tracking connection drops, a color-warning banner states "Live updates paused — reconnecting…" with a manual Refresh button; the last known status is still displayed; if the mapping service is unavailable, the map is replaced by a static placeholder with "Map unavailable" and only the status timeline is shown, ensuring the rest of the page remains functional (NFR-17); if the order is not found, a full-page error panel with a "Go to My Orders" link.
- Success → Live status timeline showing the sequence Accepted → Preparing → Ready → Out for Delivery → Delivered, with the current step highlighted in color-primary and completed steps in color-success (REQ-27); while Out for Delivery: embedded map with the delivery agent's live pin updating within 5 seconds (NFR-4) and a live ETA countdown (REQ-28); order summary panel (restaurant name, items, total) collapsed by default and expandable; "Cancel Order" button shown in color-error (disabled after restaurant acceptance per BR-1, with tooltip "Cancellation is no longer available"); agent contact affordance visible once assigned; once Delivered: status shows color-success "Delivered", map hides, and a "Rate Your Order" prompt appears (REQ-31).

Order History Page:
- Loading → List area shows skeleton card placeholders while past orders are fetched; navigation and tab filters remain visible and interactive.
- Empty → Illustrated empty state with copy "You haven't placed any orders yet" and a "Start Ordering" button in color-primary.
- Error → Error panel with message "We couldn't load your order history" and a "Try Again" button; navigation remains functional.
- Success → Chronological list of past orders, each card showing restaurant name and logo, date and time, order total, item count, and current or final status badge (color-success for Delivered, color-error for Cancelled, etc.); tapping a card navigates to the Order Detail page; delivered orders with no review yet display a "Leave a Review" chip in color-secondary; pagination or infinite scroll for long histories.

Order Detail Page:
- Loading → Skeleton placeholders for item list, status, and payment section while the order record loads.
- Empty → Not applicable; page only reachable for a specific order ID.
- Error → Full-page error panel with "Order details could not be loaded" and a "Retry" button; back navigation to Order History remains available.
- Success → Full order breakdown: order ID, placed timestamp, restaurant name, list of items with quantities and prices, subtotal, taxes, delivery fee, total, payment method and status, delivery address, agent name (if applicable); status badge in appropriate semantic color; if order is still active, a "Track Order" button in color-primary; if Delivered and no review submitted, a "Rate This Order" button in color-secondary (one-time, REQ-31); if cancellable (pre-acceptance), a "Cancel Order" button in color-error with confirmation dialog.

Submit Review Page:
- Loading → Submit button shows a spinner and is disabled while the review is being saved.
- Empty → Star-rating selector (1–5 stars, none selected by default) and an optional text area for a written review; restaurant name and order reference shown for context; "Submit Review" button in color-primary (disabled until at least one star is selected).
- Error → If submission fails, a color-error banner beneath the form states "Review could not be submitted — please try again"; if the customer has already reviewed this order (BR-6), the page is replaced by a notice "You have already reviewed this order" with a back link.
- Success → Form replaced by a color-success confirmation: "Thank you for your review!"; updated average rating for the restaurant displayed beneath the message (REQ-32); "Back to Orders" button.

Saved Addresses Page:
- Loading → List area shows skeleton row placeholders while addresses are fetched; "Add Address" button is visible but inactive.
- Empty → Illustrated empty state with copy "No saved addresses yet"; a prominent "Add New Address" button in color-primary.
- Error → Error panel with "Addresses could not be loaded" and a "Try Again" button.
- Success → List of saved addresses, each row showing the full address string, an edit icon, and a delete icon; tapping edit opens an inline or modal form to update the address; tapping delete shows a confirmation prompt before removing (REQ-6); "Add New Address" button always visible at the top or bottom of the list; address validation errors surface inline when saving a new or edited address.

Add / Edit Address Page:
- Loading → Save button disabled with spinner while the address is being geocoded or saved.
- Empty → Form fields for address line 1, address line 2, city, postcode, and a label (e.g., Home, Work) all blank with placeholder text; "Save Address" button in color-primary (disabled until required fields are non-empty).
- Error → If geocoding fails or the address falls outside the supported area, an inline color-error message beneath the address field: "This address could not be verified — please check and try again"; field-level validation messages for missing required fields; server error shown as a top-of-form banner.
- Success → Address saved; user returned to the Saved Addresses page with the new or updated entry visible; a brief color-success toast confirms "Address saved."

Account / Profile Page:
- Loading → Profile fields render as skeleton placeholders while user data is fetched; save controls are hidden until data loads.
- Empty → Not applicable; profile is always pre-populated for an authenticated user.
- Error → If profile data cannot be fetched, an error panel with "Profile could not be loaded" and a Retry button; if saving changes fails, an inline color-error banner beneath the form with a retry prompt.
- Success → Editable fields for display name, email address, and mobile number (with re-verification flow triggered if either contact field changes); current verification status shown as a badge (Verified in color-success, Unverified in color-warning); "Save Changes" button in color-primary; link to "Saved Addresses" and "Change Password" as secondary actions; account deletion option available in a destructive style at the bottom.

Restaurant Manager — Menu Management Page:
- Loading → Category list and item grid show skeleton placeholders while menu data loads; add/edit controls are inactive.
- Empty → No categories exist yet: an illustrated empty state with copy "Your menu is empty — add a category to get started" and an "Add Category" button in color-primary.
- Error → Error panel with "Menu could not be loaded" and a Retry button; if an individual save operation fails (adding or editing a category or item), an inline color-error toast or banner near the relevant control.
- Success → Left-hand (or top-tab) category list with each category name and an edit and delete icon; selecting a category shows its items in a main panel, each item displaying name, description, price, availability toggle, and edit/delete controls; "Add Item" button within each category; "Add Category" button at the top of the category list; availability toggles update in real time with a brief spinner on the toggle itself (REQ-34, REQ-35); allergen and dietary fields visible on the item edit form (NFR-5); unsaved changes prompt a confirmation before navigating away.

Restaurant Manager — Incoming Orders Page:
- Loading → Order queue shows skeleton card placeholders; the real-time connection indicator shows "Connecting…" in color-muted.
- Empty → No pending orders: illustrated empty state with copy "No new orders" and a connection status indicator confirming real-time alerts are active.
- Error → If the real-time connection drops, a color-warning banner at the top states "Live order alerts paused — reconnecting…" with a manual Refresh button; last-fetched orders remain visible; if accepting or rejecting an order fails, an inline color-error message on that order card with a retry option.
- Success → Live queue of incoming orders, each card showing order ID, items summary, customer note, order total, and time received; two primary actions per card: "Accept" (color-primary) and "Reject" (color-error); accepted orders move to an "Active Orders" section showing status (Accepted → Preparing → Ready) with "Mark Preparing" and "Mark Ready" advancement buttons (REQ-37); rejected orders require a reason via a modal text field before confirmation (REQ-38); restaurant open/closed toggle prominently placed at the top of the page (REQ-35); an audio or visual alert fires when a new order card appears (REQ-36).

Restaurant Manager — Order Detail Page:
- Loading → Skeleton placeholders for order items, customer info, and delivery details.
- Empty → Not applicable.
- Error → Inline color-error banner if status advancement fails, with a retry button; order data still visible.
- Success → Full order breakdown: order ID, timestamp, item list with quantities, subtotal, delivery vs pickup flag, customer delivery address, payment method, and current status; action buttons to advance status (Preparing → Ready) in color-primary; if order is in Pending state, Accept and Reject buttons; rejection requires a reason string (REQ-38) submitted via a modal; refund trigger is confirmed as dispatched automatically for prepaid rejected orders.

Delivery Agent — Job Queue Page:
- Loading → Job cards show skeleton placeholders; connection status shows "Connecting…"
- Empty → No available jobs: minimal illustration with copy "No deliveries assigned right now"; agent availability toggle visible.
- Error → If the connection to the dispatch system drops, a color-warning banner states "Connection lost — trying to reconnect"; last-known job state displayed; if accepting or declining fails, an inline error on the job card.
- Success → One or more job offer cards, each showing pickup restaurant name and address, drop-off address, estimated distance, and payout; a single large "Accept" button and a "Decline" button, both meeting the 44 × 44 px tap target (NFR-6); a countdown timer shows the time remaining to respond before the job is auto-reassigned (REQ-26); one active job shown prominently if already accepted, with navigation to the Active Delivery page.

Delivery Agent — Active Delivery Page:
- Loading → Map and order details show skeleton placeholders while job data loads.
- Empty → Not applicable; page only reachable when an active delivery exists.
- Error → If the mapping service is unavailable, the map is replaced by a text-only address display; a color-warning banner states "Map unavailable — follow address instructions"; all status-update actions remain functional; if a status update fails, a color-error banner with a single-tap retry.
- Success → Full-screen or large map showing the current route and destination pin; order summary panel (restaurant name, pickup address, customer drop-off address) collapsible to maximize map space; current status shown; single large "Confirm Pickup" or "Mark as Delivered" action button (one tap, minimal interaction per NFR-6); "Delivered" action reveals an optional photo upload field for proof of delivery (REQ-29) before final confirmation; once delivered, page shows a color-success confirmation and returns to the Job Queue.

Admin — User Management Page:
- Loading → Table shows skeleton rows while user data fetches; search and filter controls are visible but inactive.
- Empty → No users match the current search or filter: empty state within the table body with copy "No users found"; "Clear Filters" link.
- Error → Error panel replacing the table body with "Users could not be loaded" and a Retry button; search and filter inputs remain active.
- Success → Paginated, searchable table of users (customers, managers, agents) with columns for name, email/mobile, role, status (Active, Suspended), and registered date; row actions: view detail, suspend, or reactivate (REQ-39); status changes apply immediately with a brief spinner on the row and a color-success or color-warning toast confirmation; search input filters the table in real time or on submit.

Admin — Restaurant Management Page:
- Loading → Table shows skeleton rows; action buttons inactive.
- Empty → No restaurants match the search: empty table state with "No restaurants found" and a "Clear Filters" link.
- Error → Error panel with "Restaurants could not be loaded" and Retry; search remains active.
- Success → Paginated, searchable table of restaurant partners with columns for name, cuisine, status (Active, Suspended), commission rate, delivery radius, and date onboarded; row actions: view detail, edit configuration, suspend, or reactivate (REQ-39); "Onboard New Restaurant" button in color-primary at the top; clicking a row opens the Restaurant Detail / Config panel.

Admin — Restaurant Detail / Configuration Page:
- Loading → Skeleton placeholders for restaurant info fields and parameter inputs.
- Empty → Not applicable.
- Error → Inline color-error banner if a save operation fails, with field-level messages where applicable.
- Success → Restaurant profile fields (name, address, cuisine, operating hours, delivery radius); commission rate and service fee fields (REQ-42); open/closed status toggle; "Save Changes" button in color-primary; section showing recent orders for this restaurant with a link to the full order search.

Admin — Order Search and Detail Page:
- Loading → Search results table shows skeleton rows while the query runs.
- Empty → No orders match the search criteria: empty state in the table body with "No orders found" and a "Clear Search" link.
- Error → Error panel with "Orders could not be loaded" and a Retry button.
- Success → Searchable, filterable table of orders across the platform with columns for order ID, customer, restaurant, status, payment status, total, and timestamp (REQ-40); clicking a row shows a full order detail panel with all financial data, status history, and a link to the related dispute if one exists; "Issue Refund" action available on eligible orders (REQ-24), protected by a confirmation modal; all administrative actions logged automatically (NFR-11).

Admin — Disputes Page:
- Loading → Dispute queue shows skeleton cards or table rows while data loads.
- Empty → No open disputes: illustrated empty state with copy "No disputes to review."
- Error → Error panel with "Disputes could not be loaded" and a Retry button.
- Success → List of open and resolved disputes, each showing order ID, customer name, reason summary, date opened, and current status; clicking a dispute opens a detail view with the full order record, customer message, and a resolution form; resolution options include "Resolve — Issue Refund" (triggers REQ-24 via the gateway) and "Resolve — No Refund," both requiring a recorded resolution note (REQ-41); resolved disputes show the resolution outcome in color-success or color-muted; only administrators can issue refunds or remove reviews (BR-7).

Admin — Reviews Moderation Page:
- Loading → Review list shows skeleton rows while data loads.
- Empty → No reviews flagged or no reviews exist: empty state with "No reviews to moderate."
- Error → Error panel with "Reviews could not be loaded" and a Retry button.
- Success → List of published reviews with reviewer name, restaurant, rating, review text, date submitted, and a "Remove" action button in color-error (REQ-33); removing a review triggers a confirmation modal with a policy-violation reason selector; removed reviews disappear from the list immediately with a color-success toast; remaining reviews show updated restaurant average rating where applicable (REQ-32).

Admin — Platform Configuration Page:
- Loading → Form fields show skeleton placeholders while current configuration values are fetched.
- Empty → Not applicable; configuration always has current values.
- Error → If configuration cannot be fetched, a full-page error panel with a Retry button; if saving fails, an inline color-error banner at the top of the form with field-level messages where applicable.
- Success → Editable fields for platform-wide commission rate, default service fee, default delivery radius, session token duration, account lockout duration, and lockout threshold (REQ-42); current values pre-populated; "Save Configuration" button in color-primary; a read-only audit log section below listing recent configuration changes with actor, timestamp, and old/new value (NFR-11); confirmation modal required before saving changes to prevent accidental overwrites.
