# Project Implementation Specification: Little Lemon REST API

Act as a Principal Django Back-End Engineer. Implement a full production-ready Django REST Framework (DRF) project that strictly fulfills all 21 acceptance criteria below.

## Acceptance Criteria Checklist

1. The admin can assign users to the manager group
2. You can access the manager group with an admin token
3. The admin can add menu items
4. The admin can add categories
5. Managers can log in
6. Managers can update the item of the day
7. Managers can assign users to the delivery crew
8. Managers can assign orders to the delivery crew
9. The delivery crew can access orders assigned to them
10. The delivery crew can update an order as delivered
11. Customers can register
12. Customers can log in using their username and password and get access tokens
13. Customers can browse all categories
14. Customers can browse all the menu items at once
15. Customers can browse menu items by category
16. Customers can paginate menu items
17. Customers can sort menu items by price
18. Customers can add menu items to the cart
19. Customers can access previously added items in the cart
20. Customers can place orders
21. Customers can browse their own orders

## Requirements & Design Specifications

### 1. Technology Stack

- **Framework:** Django & Django REST Framework (DRF)
- **Authentication:** Djoser / DRF Token Authentication (or SimpleJWT)
- **Database:** SQLite (default for development) or MySQL

### 2. User Roles & Permissions

- **Admin (Superuser):** Full access to create categories, menu items, assign users to Manager/Delivery Crew groups.
- **Manager:** Can update item of the day, assign users to delivery crew, assign orders to delivery crew.
- **Delivery Crew:** Can view assigned orders and update delivery status (`status=1` or `delivered=True`).
- **Customer:** Can view categories, menu items (with filtering, ordering, pagination), manage their personal cart, create orders, and view their orders.

### 3. Core Models Required

- `Category` (slug, title)
- `MenuItem` (title, price, featured/item_of_the_day, category)
- `Cart` (user, menuitem, quantity, unit_price, price)
- `Order` (user, delivery_crew, status, total, date)
- `OrderItem` (order, menuitem, quantity, unit_price, price)

### 4. Code Structure Required

Provide clean, commented, and executable code for:

- `models.py`
- `serializers.py`
- `permissions.py` (Custom permissions: `IsManager`, `IsDeliveryCrew`, `IsAdmin`)
- `views.py` (Class-Based Views / Generic Views / ViewSets with filtering, ordering, and pagination enabled)
- `urls.py`
- `settings.py` (REST_FRAMEWORK configuration, Djoser/Token auth setup)

Generate a clean, fully-formed solution meeting every criterion.
