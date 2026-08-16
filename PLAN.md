# Little Lemon Capstone — Implementation Plan

**All phases are complete.** This document is kept as the build record: what was
done for each capstone requirement and why the design choices were made.

## Requirement coverage

| # | Requirement | Status | Phase |
| --- | --- | --- | --- |
| 1 | Git repository + push to GitHub | ✅ done | — |
| 1 | Clean Django project structure | ✅ done | 0 |
| 1 | Static content / HTML routes | ✅ done | 4 |
| 2 | MySQL connection | ✅ done — MySQL 8.4, verified | 1 |
| 2 | Database models | ✅ `Menu` + `Booking` | 0, 2 |
| 3 | Menu API (DRF) | ✅ done | 0 |
| 3 | Table booking API (DRF) | ✅ done | 3 |
| 4 | Registration / login / logout | ✅ token API + HTML flow | 5 |
| 4 | Booking API secured | ✅ `IsAuthenticated` + per-user scoping | 3 |
| 5 | Unit tests | ✅ 25 tests, all passing on MySQL | 6 |
| 5 | Insomnia REST client testing | ✅ collection committed | 7 |

## Verification performed

- `python manage.py test` — 25 tests pass against MySQL.
- `python manage.py check` — no issues; no pending migrations.
- Live HTTP run of every route: all HTML pages, static assets, and API endpoints
  return the expected status codes.
- End-to-end auth flow: register → token → book → list → logout → revoked token
  rejected with 401.
- Booking isolation confirmed: a second user's forged `user` field was ignored,
  cross-user reads returned 404, and each caller saw only their own reservations.

## Known follow-ups

- MySQL runs from a user-owned data directory rather than a Windows service, so it
  must be started manually after a reboot (see the README). Running **MySQL
  Configurator** as Administrator would register it as a service.
- `DJANGO_SECRET_KEY` still falls back to the insecure development default; set a
  real one in `.env` before any deployment.

---

## Phase 0 — Cleanup (complete)

Removed the Course 6 scope that the capstone brief does not ask for — `Cart`,
`Order`, `OrderItem`, `Category`, the Manager / Delivery-crew role system
(`permissions.py`), the `seed_demo` command, the old 391-line test suite, and
`guide.md`. Reshaped `MenuItem` into the capstone's `Menu` (title, price,
inventory) and regenerated a single clean initial migration.

The old build is preserved at the git tag `course6-api-final`.

What remains is a working baseline: `Menu` model + menu API + Djoser token auth
+ Django admin, all verified green.

---

## Phase 1 — MySQL

**Requirement:** *Connect the Django backend to a MySQL database.*

MySQL is not currently installed on this machine (only PostgreSQL 18 is), and the
venv has no MySQL driver. `settings.py` already contains an env-driven `mysql`
branch, so no settings rewrite is needed — only installation and wiring.

### 1a. Install the server

Pick one:

```powershell
# Option A - native Windows install (matches the course walkthrough)
winget install Oracle.MySQL
# or download the MySQL Community Installer and choose "Server only"
```

```powershell
# Option B - Docker (fastest to tear down and redo)
docker run --name littlelemon-mysql -e MYSQL_ROOT_PASSWORD=changeme -e MYSQL_DATABASE=LittleLemon -p 3306:3306 -d mysql:8
```

Django 6.1 requires MySQL 8.0.11 or newer.

### 1b. Install the driver

```powershell
.venv\Scripts\pip install mysqlclient
```

If the `mysqlclient` build fails on Windows (it needs MySQL client headers), fall
back to the pure-Python driver instead:

```powershell
.venv\Scripts\pip install PyMySQL
```

…and add to `LittleLemon/__init__.py`:

```python
import pymysql
pymysql.install_as_MySQLdb()
```

### 1c. Create the database

```sql
CREATE DATABASE LittleLemon CHARACTER SET utf8mb4;
CREATE USER lemonuser@localhost IDENTIFIED BY 'changeme';
GRANT ALL PRIVILEGES ON LittleLemon.* TO lemonuser@localhost;
FLUSH PRIVILEGES;
```

### 1d. Point Django at it

Set the environment variables the existing settings branch already reads:

| Variable | Value |
| --- | --- |
| `DB_ENGINE` | `mysql` |
| `DB_NAME` | `LittleLemon` |
| `DB_USER` | `lemonuser` |
| `DB_PASSWORD` | `changeme` |
| `DB_HOST` | `127.0.0.1` |
| `DB_PORT` | `3306` |

For convenience, add `python-dotenv` and a gitignored `.env` file rather than
setting these by hand each session. Add `mysqlclient` to `requirements.txt`.

**Verify:** `python manage.py migrate` succeeds, then `python manage.py dbshell`
and `SHOW TABLES;` lists the `LittleLemonAPI_menu` table. Take a screenshot — the
rubric asks for evidence of the MySQL connection.

---

## Phase 2 — Booking model

**Requirement:** *Create and configure the required data models.*

Add to `LittleLemonAPI/models.py`:

```python
class Booking(models.Model):
    """A reserved table."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        null=True, blank=True,
    )
    name = models.CharField(max_length=255)
    no_of_guests = models.SmallIntegerField(validators=[MinValueValidator(1)])
    booking_date = models.DateTimeField()

    class Meta:
        ordering = ["booking_date"]

    def __str__(self) -> str:
        return f"{self.name} - {self.no_of_guests} guests on {self.booking_date}"
```

The `user` foreign key goes beyond the literal brief (the canonical model is just
name / no_of_guests / booking_date) but it is what makes "secure the booking API"
mean something — it lets each customer see only their own reservations instead of
every booking in the restaurant. It is nullable so admin-created bookings still work.

Register it in `admin.py` alongside `Menu`, then:

```powershell
python manage.py makemigrations
python manage.py migrate
```

**Verify:** create a booking through `/admin/` and confirm the row lands in MySQL.

---

## Phase 3 — Booking API (secured)

**Requirements:** *Build the table booking API with DRF* and *secure it with
proper authentication controls.*

### Serializer — `LittleLemonAPI/serializers.py`

```python
class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ["id", "user", "name", "no_of_guests", "booking_date"]
        read_only_fields = ["user"]          # set from the request, never the client
```

### ViewSet — `LittleLemonAPI/views.py`

Use a `ModelViewSet` here rather than the generic views the menu uses — the
booking resource needs the full CRUD set and a router gives it for free:

```python
class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]        # the security requirement

    def get_queryset(self):
        # Customers see only their own reservations; staff see all.
        qs = Booking.objects.all()
        return qs if self.request.user.is_staff else qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
```

### Routing — `LittleLemonAPI/urls.py`

```python
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"tables", views.BookingViewSet, basename="booking")

urlpatterns = [
    path("menu/", views.MenuItemsView.as_view(), name="menu-items"),
    path("menu/<int:pk>/", views.SingleMenuItemView.as_view(), name="menu-item-detail"),
    path("booking/", include(router.urls)),      # -> /api/booking/tables/
]
```

Scoping in `get_queryset()` (rather than with a permission check) means one
customer requesting another's booking gets a 404, not a 403 — the API never
confirms that someone else's reservation exists.

**Verify:** `GET /api/booking/tables/` with no token returns 401; with a token it
returns only that user's bookings.

---

## Phase 4 — Static content & HTML routes

**Requirement:** *Configure and serve static content/HTML routes using Django.*

Nothing HTML-facing exists yet — `TEMPLATES["DIRS"]` is empty and there is no
static directory.

### Structure

Because this app is named `LittleLemonAPI`, put the presentation layer at project
level rather than burying templates inside an API app:

```
templates/
  base.html
  index.html          home / about
  book.html           booking form
  menu.html           menu listing
static/
  css/style.css
  img/restaurant.jpg
```

### Settings

```python
TEMPLATES = [{ ..., "DIRS": [BASE_DIR / "templates"], ... }]

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]     # add
STATIC_ROOT = BASE_DIR / "staticfiles"       # already present
```

### Views and routes

Plain function views in `LittleLemonAPI/views.py` (or a small `pages.py` if you
prefer to keep API and HTML views apart):

```python
def index(request):
    return render(request, "index.html")

def menu(request):
    return render(request, "menu.html", {"menu": Menu.objects.all()})
```

Wire `path("", views.index, name="index")` into `LittleLemon/urls.py`.

Templates load assets with `{% load static %}` and `{% static 'css/style.css' %}`.

**Verify:** `runserver`, hit `http://127.0.0.1:8000/`, confirm the page renders
with CSS and images applied.

---

## Phase 5 — User registration, login, logout

**Requirement:** *Implement user registration, login, and logout functionality.*

The API half already works via Djoser (`/api/users/`, `/api/token/login/`,
`/api/token/logout/`). What is missing is the browser-facing half.

Add to `LittleLemon/urls.py`:

```python
path("accounts/", include("django.contrib.auth.urls")),   # login, logout, password reset
path("accounts/register/", views.RegisterView.as_view(), name="register"),
```

`RegisterView` is a thin `CreateView` over Django's `UserCreationForm`:

```python
class RegisterView(CreateView):
    form_class = UserCreationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("login")
```

Templates go in `templates/registration/` — `login.html`, `logged_out.html`,
`register.html`. Set `LOGIN_REDIRECT_URL = "index"` and `LOGOUT_REDIRECT_URL = "index"`.

Note that Django 5+ requires logout to be a POST — the logout control must be a
small form, not an `<a href>`.

**Verify:** register a user in the browser, log in, see the nav change, log out.

---

## Phase 6 — Unit tests

**Requirement:** *Write and include unit tests for application code.*

Replace the deleted single `tests.py` with a test package, which is the layout the
rubric expects:

```
LittleLemonAPI/tests/
  __init__.py
  test_models.py
  test_views.py
```

**`test_models.py`** — model behaviour:

- `Menu.__str__` renders `"Title : Price"`.
- `Booking.__str__` renders as expected.
- `no_of_guests` below 1 fails `full_clean()`.

**`test_views.py`** — API behaviour:

- `GET /api/menu/` returns all seeded items (the canonical `test_getall`).
- `POST /api/menu/` without a token returns 401.
- `GET /api/booking/tables/` without a token returns 401.
- An authenticated user sees only their own bookings, not another user's.
- `POST /api/booking/tables/` assigns `user` from the token, ignoring any
  client-supplied `user` field.

Run with `python manage.py test`. Note that the test runner will try to create a
`test_LittleLemon` MySQL database, so the configured MySQL user needs `CREATE`
privileges.

---

## Phase 7 — Insomnia collection

**Requirement:** *Verify and test API endpoints using the Insomnia REST client.*

Build a collection covering every endpoint and commit the export so the work is
reviewable:

```
insomnia/LittleLemon_Insomnia.json
```

Suggested structure — an environment holding `base_url` (`http://127.0.0.1:8000`)
and `token`, then folders:

- **Auth** — register, obtain token, logout
- **Menu** — list, create, retrieve, update, delete
- **Booking** — list, create, retrieve, update, delete, plus a deliberate
  no-token request showing the 401

Set the collection auth header once as `Authorization: Token {{ token }}` so it
inherits down. Export via *Application → Preferences → Data → Export*.

Capture screenshots of the key responses — submissions are usually graded on
visual evidence that the endpoints were exercised.

---

## Phase 8 — Repo hygiene and submission

- Confirm `.gitignore` covers `.venv/`, `db.sqlite3`, `__pycache__/`,
  `staticfiles/`, `.env` — it already does.
- Make sure no MySQL password is committed; keep credentials in `.env`.
- Freeze final dependencies into `requirements.txt`.
- Update `README.md` with the full endpoint table, MySQL setup steps, and how to
  run the tests.
- Push to GitHub, and consider renaming the repo from `little-lemon-api` to
  something capstone-appropriate.
