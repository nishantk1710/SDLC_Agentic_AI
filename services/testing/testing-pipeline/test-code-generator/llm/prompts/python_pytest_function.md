# Python / pytest — function-kind test cases

A "function" case is any case that isn't endpoint-shaped (see the endpoint prompt) —
`input` isn't a dict with `"method"`/`"path"` keys. `target_symbols` names the callable,
e.g. `"quickbite/backend/app/main.py::_hash_password"` — import it from the module path
before `::`, calling the name after it.

- **`input` as a dict** → call the function with those as keyword arguments (or
  positional if that reads more naturally for the function's apparent signature).
  Some dict entries (e.g. `"setup"`) describe preconditions/state to arrange first
  (e.g. seed a cart, create prior ratings), not literal arguments — use judgement.
- **`input` as a list** → call the function with that list as its single positional
  argument (e.g. `assign_delivery_agent([{"agent_id": "A1", ...}, ...])`).
- **`expected` as a scalar** (bool/int/float/str) → assert the return value equals it
  directly.
- **`expected` as a flat dict of descriptively-named boolean/value checks** (e.g.
  `{"is_hex_string": true, "does_not_contain_raw_password": true}`) → each key names a
  *property to verify about the function's return value or observable behavior*, not a
  field of a returned object. Interpret the key name to decide what check it implies
  (e.g. `is_hex_string` → the return value matches a hex-string pattern;
  `does_not_contain_raw_password` → the raw input password is not a substring of the
  return value; `two_calls_produce_different_hashes` → call the function twice and
  assert the two results differ). The expected value (`true`/`false`) is what the
  check should evaluate to — never invent a more specific value (e.g. a literal hash)
  that isn't in the test case.
- One test function per test case; name it `test_<case_id_with_underscores>`.
