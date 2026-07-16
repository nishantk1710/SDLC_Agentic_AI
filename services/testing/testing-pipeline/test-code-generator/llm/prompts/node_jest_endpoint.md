# Node/Express / Jest — endpoint-kind test cases

An "endpoint" case is one whose `input` is a dict containing `"method"` and `"path"`
keys (e.g. `{"method": "POST", "path": "/register", "body": {...}}`). Generate one
Jest test per case, using Supertest against the app's Express instance:

- Use Supertest (`const request = require("supertest");`) against an `app`
  object imported as `const app = require("../app");` (the code under
  test's entrypoint — assume this import path). `target_symbols` names the
  route handler for context; you still call it through HTTP via Supertest,
  not by importing it directly.
- `input.method` + `input.path` build the request; `input.body` (if present) is the
  JSON request body; `input.query` (if present) is query params.
- **`input.setup`** (if present) is a short descriptive string naming a precondition to
  arrange before the real call (e.g. `"mark_token_as_used"`) — translate it into
  realistic setup code using your best judgement; it's a description of required
  state, not a literal function name.
- **`input.repeat`** (if present) is an integer meaning "make this exact same call N
  times before the one that matters" (e.g. testing a lockout boundary). Loop the
  request that many times, then make the final call whose response you assert on.
- **`expected.status_code`** → `response.status`.
- **`expected.json`** (if present) is a dict of expected response-body fields, checked
  one level into the response body — e.g. `expected.json.user_id` → assert the `user_id`
  field of the parsed body.
- For each field in `expected.json` (or a bare `expected` dict without a nested
  `json`), the value is either a **literal** (assert equality), a **placeholder token**
  like `"__any_string__"`/`"__any_bool__"` (assert presence + type, not equality to the
  literal token), or a **one-of token** like `"__any_of_a_or_b__"` (assert membership).
- Use plain JavaScript, CommonJS `require`, no JSX — this file must be
  syntax-checkable as plain JS.
- One test per test case, inside a `describe`/`test` block; name each
  `test` by `case_id_with_underscores`.
