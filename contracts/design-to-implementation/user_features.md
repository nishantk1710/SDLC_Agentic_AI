# User Features

## Roles
- **Customer** — End users who browse restaurants and place orders. Highest-volume class; assume broad range of technical skill and primarily mobile usage. Most important class to satisfy.
- **Restaurant Manager** — Staff of partner restaurants who manage menus, toggle availability, and accept/fulfil orders. Moderate technical skill; frequent daily use during business hours.
- **Delivery Agent** — Contract couriers who accept delivery jobs and complete drop-offs. Mobile-only; need simple, low-friction workflows and offline-tolerant behaviour.
- **Platform Administrator** — Internal staff who onboard partners, resolve disputes, and configure platform parameters. Small population; high privilege; technically proficient.

## Entities
User, Customer, Restaurant Manager, Delivery Agent, Restaurant, Menu Category, Menu Item, Cart, Order, Order Item, Payment, Delivery, Address, Review

## Features

### 4.1 User Registration and Authentication  ·  Priority: High
_Allows users of all four classes to create accounts, authenticate, and manage their profiles and saved addresses_
- **Story (derived):** As a user, I want to create accounts, authenticate, and manage my profiles and saved addresses.
- **Flow:**
    1. User submits registration details → system validates, creates account, and sends a verification message.
    2. User submits credentials → system authenticates and issues a session token, or returns an error after repeated failures.
    3. User requests password reset → system sends a time-limited reset link.
- **Requirements:** REQ-1, REQ-2, REQ-3, REQ-4, REQ-5, REQ-6, REQ-7

### 4.2 Restaurant and Menu Browsing  ·  Priority: High
_Lets customers discover restaurants and menu items relevant to their location and preferences_
- **Story (derived):** As a customer, I want to discover restaurants and menu items relevant to my location and preferences.
- **Flow:**
    1. Customer opens the app → system lists open restaurants that deliver to the customer's location.
    2. Customer enters a search term or applies filters → system returns matching restaurants and items.
    3. Customer selects a restaurant → system displays its menu, hours, rating, and delivery estimate.
- **Requirements:** REQ-8, REQ-9, REQ-10, REQ-11, REQ-12

### 4.3 Cart and Order Placement  ·  Priority: High
_Lets customers assemble an order and submit it for fulfilment_
- **Story (derived):** As a customer, I want to assemble an order and submit it for fulfilment.
- **Flow:**
    1. Customer adds items to the cart → system updates the cart total and enforces per-restaurant rules.
    2. Customer proceeds to checkout → system validates minimum order, delivery address, and item availability.
    3. Customer confirms the order → system creates the order, initiates payment, and notifies the restaurant.
- **Requirements:** REQ-13, REQ-14, REQ-15, REQ-16, REQ-17, REQ-18, REQ-19

### 4.4 Payment Processing  ·  Priority: High
_Handles secure collection of payment and issuance of refunds_
- **Story (derived):** As a customer, I want payment processing.
- **Flow:**
    1. Customer selects a payment method and confirms → system requests authorization from the gateway.
    2. Gateway returns success → system marks the order paid and proceeds; on failure the system keeps the order unpaid and prompts the customer to retry.
    3. An eligible cancellation or dispute is resolved in the customer's favour → system issues a refund through the gateway.
- **Requirements:** REQ-20, REQ-21, REQ-22, REQ-23, REQ-24

### 4.5 Order Tracking and Delivery Management  ·  Priority: High
_Coordinates assignment of a delivery agent and provides real-time tracking to the customer_
- **Story (derived):** As a delivery agent, I want order tracking and delivery management.
- **Flow:**
    1. Restaurant marks an order ready → system assigns an available nearby delivery agent.
    2. Delivery agent accepts the job → system shares pickup and drop-off details and begins tracking.
    3. Delivery agent updates status / location → system relays live progress and ETA to the customer.
- **Requirements:** REQ-25, REQ-26, REQ-27, REQ-28, REQ-29, REQ-30

### 4.6 Ratings and Reviews  ·  Priority: Medium
_Lets customers provide feedback on completed orders_
- **Story (derived):** As a customer, I want to provide feedback on completed orders.
- **Flow:**
    1. Order is delivered → system invites the customer to rate and review.
    2. Customer submits a rating and optional text → system records it and updates the restaurant's average rating.
- **Requirements:** REQ-31, REQ-32, REQ-33

### 4.7 Restaurant Partner Menu Management  ·  Priority: High
_Lets restaurant managers maintain their menu, pricing, and availability, and manage incoming orders_
- **Story (derived):** As a restaurant manager, I want to maintain my menu, pricing, and availability, and manage incoming orders.
- **Flow:**
    1. Manager edits the menu → system validates and publishes changes to customers.
    2. New order arrives → system alerts the manager, who accepts or rejects it and later marks it ready.
- **Requirements:** REQ-34, REQ-35, REQ-36, REQ-37, REQ-38

### 4.8 Administration and Platform Management  ·  Priority: Medium
_Gives administrators control over partners, users, disputes, and platform configuration_
- **Story (derived):** As a platform administrator, I want control over partners, users, disputes, and platform configuration.
- **Flow:**
    1. Administrator onboards a restaurant → system creates the partner account and portal access.
    2. Administrator reviews a dispute → system applies the resolution, including any refund.
- **Requirements:** REQ-39, REQ-40, REQ-41, REQ-42