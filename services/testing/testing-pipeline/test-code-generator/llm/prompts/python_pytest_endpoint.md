# Python / pytest — endpoint-kind test cases

An "endpoint" case is one whose `input` is a dict containing `"method"` and `"path"`
keys (e.g. `{"method": "POST", "path": "/register", "body": {...}}`). Generate one
pytest test function per case:

- Use FastAPI's `TestClient` (`from fastapi.testclient import TestClient`) against an
  `app` object imported as `from app import app` (the code under test's entrypoint —
  assume this import path). `target_symbols` (e.g.
  `"quickbite/backend/app/main.py::register"`) names the route handler for context;
  you still call it through HTTP via `TestClient`, not by importing it directly.
- `input.method` + `input.path` build the request; `input.body` (if present) is the
  JSON request body; `input.query` (if present) is query params.
- **`input.setup`** (if present) is a short descriptive string naming a precondition to
  arrange before the real call — e.g. `"mark_token_as_used"`, `"seed_menu_item_known-item-id-1"`,
  `"cart_subtotal_9_minimum_order_10"`. Translate this into realistic setup code (prior
  API calls, fixtures, monkeypatched state) using your best judgement about what the
  string implies — it is not a literal function name to call verbatim, it's a
  description of state that must exist before the assertion-bearing request.
- **`input.repeat`** (if present) is an integer meaning "make this exact same call N
  times before the one that matters" — e.g. `repeat: 4` for testing a failed-login
  lockout boundary at the 4th attempt. Loop the request that many times, then make the
  final call whose response you actually assert on.
- **`expected.status_code`** → `response.status_code`.
- **`expected.json`** (if present) is a dict of expected response-body fields, checked
  one level into `response.json()` — e.g. `expected.json.user_id` → assert
  `response.json()["user_id"]` per the value's rule below.
- For each field in `expected.json` (or a bare `expected` dict without a nested
  `json`), the value is either:
  - **A literal** (string/number/bool) → assert equality.
  - **A placeholder token** (`"__any_string__"`, `"__any_bool__"`, `"__any_int__"`, or
    similar `"__any_X__"`) → assert the field is present and of that type, not equal to
    the literal token string.
  - **A one-of token** (`"__any_of_a_or_b__"`) → assert the field's value is one of the
    listed alternatives.
- One test function per test case; name it `test_<case_id_with_underscores>`.
