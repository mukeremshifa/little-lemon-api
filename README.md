# Little Lemon REST API

A Django REST Framework implementation of the Little Lemon restaurant back end, covering
all 21 acceptance criteria in [guide.md](guide.md).

## Quick start

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo        # role groups + demo users, categories, menu items
python manage.py runserver
```

`seed_demo` creates four users — `admin`, `manager`, `crew`, `customer` — all with the
password `LittleLemon123!`. Use `python manage.py createsuperuser` instead if you would
rather start from an empty database (the role groups are created on first use).

Run the acceptance test suite (24 tests, one or more per criterion):

```bash
python manage.py test
```

## Authentication

Token authentication via Djoser. Obtain a token and send it on every request:

```bash
curl -X POST http://127.0.0.1:8000/api/token/login/ \
     -d "username=customer&password=LittleLemon123!"
# {"auth_token":"9cc0856350..."}

curl -H "Authorization: Token 9cc0856350..." http://127.0.0.1:8000/api/menu-items/
```

## Roles

| Role | How it is granted | Can do |
| --- | --- | --- |
| **Admin** | `is_staff` / superuser | everything, including managing the Manager group |
| **Manager** | member of the `Manager` group | item of the day, staff the delivery crew, assign & delete orders |
| **Delivery crew** | member of the `Delivery crew` group | see orders assigned to them, mark them delivered |
| **Customer** | any other authenticated user | browse, cart, place and view their own orders |

## Endpoints

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| POST | `/api/users/` | anyone | register a customer |
| GET | `/api/users/me/` | authenticated | current profile |
| POST | `/api/token/login/` | anyone | obtain an auth token |
| POST | `/api/token/logout/` | authenticated | revoke the token |
| GET | `/api/whoami/` | authenticated | caller's effective role (debug helper) |
| GET / POST | `/api/categories/` | read: all · write: admin | browse / add categories |
| GET / PUT / PATCH / DELETE | `/api/categories/<id>/` | read: all · write: admin | single category |
| GET / POST | `/api/menu-items/` | read: all · write: admin | browse / add menu items |
| GET | `/api/menu-items/<id>/` | authenticated | single item |
| PATCH | `/api/menu-items/<id>/` | manager (`featured` only) / admin | edit an item |
| PUT / DELETE | `/api/menu-items/<id>/` | admin | replace / remove an item |
| GET | `/api/menu-items/item-of-the-day/` | authenticated | current featured item |
| PUT / PATCH | `/api/menu-items/item-of-the-day/` | manager | promote `{"menuitem": <id>}` |
| GET / POST | `/api/groups/manager/users/` | admin | list / add managers |
| DELETE | `/api/groups/manager/users/<id>/` | admin | remove a manager |
| GET / POST | `/api/groups/delivery-crew/users/` | manager | list / add delivery crew |
| DELETE | `/api/groups/delivery-crew/users/<id>/` | manager | remove from the crew |
| GET / POST / DELETE | `/api/cart/menu-items/` | authenticated | the caller's own cart |
| GET | `/api/orders/` | authenticated | role-scoped order list |
| POST | `/api/orders/` | customer | check out the cart |
| GET | `/api/orders/<id>/` | owner / assigned crew / manager | one order |
| PATCH | `/api/orders/<id>/` | manager (crew + status) · crew (status only) | update an order |
| DELETE | `/api/orders/<id>/` | manager | delete an order |

Group membership accepts either `{"username": "..."}` or `{"user_id": 3}`.

## Browsing the menu

| Query | Effect |
| --- | --- |
| `?category=desserts` | filter by category id, slug, or title |
| `?ordering=price` / `?ordering=-price` | sort by price (also `title`) |
| `?page=2&perpage=5` | paginate (default 10 per page, `perpage` capped at 100) |
| `?search=lemon` | search title and category title |
| `?featured=true` | only the item of the day |
| `?price_min=5&price_max=15` | price range |

## Design notes

- **Money is never trusted from the client.** `Cart.save()` reads `unit_price` from the
  live `MenuItem` and computes `price`; `OrderItem` rows freeze those values at checkout so
  later menu price changes never rewrite order history.
- **One item of the day.** `MenuItem.save()` demotes the previous featured item inside a
  transaction, so the flag is unique by construction rather than by convention.
- **Role scoping happens in `get_queryset()`**, so a delivery crew member requesting another
  crew's order gets a 404 rather than a 403 — the API does not confirm that the order exists.
- **Checkout is atomic**: order, line items and cart deletion succeed or fail together.
- **Throttling** is on by default (30/min anonymous, 120/min authenticated) and disabled in
  the test suite.
- **MySQL** is a drop-in swap: set `DB_ENGINE=mysql` plus `DB_NAME`/`DB_USER`/`DB_PASSWORD`/
  `DB_HOST`/`DB_PORT`. `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` and `DJANGO_ALLOWED_HOSTS` are
  likewise environment-driven.

## Layout

```
LittleLemon/          project settings, root URLconf
LittleLemonAPI/
  models.py           Category, MenuItem, Cart, Order, OrderItem
  serializers.py      including role-aware order updates
  permissions.py      IsAdmin, IsManager, IsDeliveryCrew, IsCustomer, ...
  views.py            generic views + filtering / ordering / pagination
  urls.py             app routes
  admin.py            Django admin registration
  tests.py            one test per acceptance criterion
  management/commands/seed_demo.py
```
