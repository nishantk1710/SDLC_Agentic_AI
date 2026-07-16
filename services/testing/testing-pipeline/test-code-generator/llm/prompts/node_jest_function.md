# Node/Express / Jest — function-kind test cases

A "function" case is any case that isn't endpoint-shaped (see the endpoint prompt) —
`input` isn't a dict with `"method"`/`"path"` keys. `target_symbols` names the callable,
e.g. `"quickbite/backend/app/main.js::_hashPassword"` — import it from the module path
before `::`, calling the name after it, e.g. `const { _hashPassword } = require("../main");`.

- **`input` as a dict** → call the function with those as named/positional arguments,
  whichever reads more naturally for the function's apparent signature. Some dict
  entries (e.g. `"setup"`) describe preconditions/state to arrange first, not literal
  arguments — use judgement.
- **`input` as a list/array** → call the function with that array as its single
  argument (e.g. `assignDeliveryAgent([{agentId: "A1", ...}, ...])`).
- **`expected` as a scalar** (bool/number/string) → assert the return value equals it
  directly.
- **`expected` as a flat object of descriptively-named checks** (e.g.
  `{"isHexString": true, "doesNotContainRawPassword": true}`) → each key names a
  *property to verify about the return value or observable behavior*, not a field of a
  returned object. Interpret the key name to decide what check it implies. The
  expected value (`true`/`false`) is what the check should evaluate to — never invent
  a more specific value that isn't in the test case.
- Use plain JavaScript, CommonJS `require`, no JSX — this file must be
  syntax-checkable as plain JS.
- One test per test case, inside a `describe`/`test` block; name each
  `test` by `case_id_with_underscores`.
