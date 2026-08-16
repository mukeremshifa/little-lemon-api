# Little Lemon — Django Capstone

Django + Django REST Framework back end for the Little Lemon restaurant: server-rendered
pages with static assets, a MySQL data layer, a public menu API, and a table booking API
locked behind token authentication.

> The earlier Course 6 build of this repo (categories, cart, orders, delivery-crew roles)
> is preserved at the git tag [`course6-api-final`](../../tree/course6-api-final).

## Requirements covered

| Requirement | Where |
| --- | --- |
| Git repository pushed to GitHub | this repo |
| Clean Django project structure | `LittleLemon/` + `LittleLemonAPI/` |
| Static content & HTML routes | `templates/`, `static/`, routes in `LittleLemon/urls.py` |
| MySQL connection | `LittleLemon/settings.py` + `.env` |
| Database models | `LittleLemonAPI/models.py` — `Menu`, `Booking` |
| Menu API (DRF) | `MenuItemsView`, `SingleMenuItemView` |
| Table booking API (DRF) | `BookingViewSet` |
| Registration / login / logout | Djoser (API) + `django.contrib.auth` (HTML) |
| Booking API secured | `permission_classes = [IsAuthenticated]` + per-user queryset |
| Unit tests | `LittleLemonAPI/tests/` — 25 tests |
| Insomnia REST client testing | `insomnia/LittleLemon_Insomnia.json` |

## Quick start

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cp .env.example .env              # then edit the DB_* values
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

## Database

The project runs on **MySQL 8.4**. Credentials come from a gitignored `.env`
(see `.env.example`); real environment variables override it. Set `DB_ENGINE=sqlite`
to fall back to a local file if you need to run without a database server.

```sql
CREATE DATABASE littlelemon CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Starting the local MySQL server

This machine's MySQL 8.4 is installed but not registered as a Windows service, so it
runs from its own data directory:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" `
    --datadir="C:\Users\mukee\AppData\Local\LittleLemonMySQL\data" `
    --port=3306 `
    --log-error="C:\Users\mukee\AppData\Local\LittleLemonMySQL\error.log"
```

To make it start automatically on boot instead, run **MySQL Configurator** as
Administrator and let it register the Windows service.

## Pages

| Path | Purpose |
| --- | --- |
| `/` | home page |
| `/menu/` | menu, rendered from the `Menu` table |
| `/book/` | booking form (posts to the booking API) |
| `/accounts/register/` | create an account |
| `/accounts/login/` · `/accounts/logout/` | session login / logout |
| `/admin/` | Django admin |

## API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/menu/` | open | list menu items |
| POST | `/api/menu/` | token | add a menu item |
| GET | `/api/menu/<id>/` | open | retrieve one item |
| PUT / PATCH / DELETE | `/api/menu/<id>/` | token | update / remove an item |
| GET | `/api/booking/tables/` | **token** | list *your* reservations |
| POST | `/api/booking/tables/` | **token** | reserve a table |
| GET | `/api/booking/tables/<id>/` | **token** | retrieve one reservation |
| PUT / PATCH / DELETE | `/api/booking/tables/<id>/` | **token** | update / cancel |
| POST | `/api/users/` | open | register |
| GET | `/api/users/me/` | token | current profile |
| POST | `/api/token/login/` | open | obtain an auth token |
| POST | `/api/token/logout/` | token | revoke the token |

```bash
curl -X POST http://127.0.0.1:8000/api/token/login/ -d "username=you&password=yourpass"
# {"auth_token":"9cc0856350..."}
curl -H "Authorization: Token 9cc0856350..." http://127.0.0.1:8000/api/booking/tables/
```

### Booking security

Every booking action requires a token. Beyond that, `BookingViewSet.get_queryset()`
filters reservations to the caller, so one customer requesting another's booking gets a
**404 rather than a 403** — the API never confirms that someone else's reservation
exists. `user` is read-only on the serializer and stamped from the token in
`perform_create()`, so a client cannot book on someone else's behalf. Staff users see
every booking.

## Tests

```bash
python manage.py test
```

25 tests across `LittleLemonAPI/tests/test_models.py` (string representations, field
validation, ordering) and `test_views.py` (menu CRUD, booking authentication, per-user
scoping, forged-owner rejection, HTML routes). The runner creates a
`test_littlelemon` MySQL database, so the configured user needs `CREATE` privileges.

## Insomnia

Import `insomnia/LittleLemon_Insomnia.json` (*Application → Preferences → Data → Import*).
Set the environment's `base_url` and paste the value from **Obtain auth token** into
`token`; every authenticated request reads it via `{{ _.token }}`. The collection includes
deliberate no-token requests that demonstrate the 401 responses.

## Layout

```
LittleLemon/          settings, root URLconf
LittleLemonAPI/
  models.py           Menu, Booking
  serializers.py      MenuSerializer, BookingSerializer, UserSerializer
  views.py            HTML pages + menu API + booking viewset
  urls.py             API routes (DefaultRouter for bookings)
  admin.py            admin registration
  migrations/
  tests/              test_models.py, test_views.py
templates/            base, index, menu, book, registration/
static/               css/, img/
insomnia/             REST client collection
.env.example          environment template
```
