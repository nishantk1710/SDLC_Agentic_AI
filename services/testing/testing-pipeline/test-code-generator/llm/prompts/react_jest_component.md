# React / Jest + React Testing Library — component-kind test cases

Note: no case currently routes here (see codegen/react.py's docstring) --
this prompt is kept ready for when Step B's schema gains a way to signal a
component case. `target_symbols` names a component (e.g. `"LoginForm"`,
`"SignupForm"`). Generate one Jest test per case, using React Testing
Library (RTL) with jsdom:

- Import RTL helpers: `import { render, screen, fireEvent } from "@testing-library/react";`
  and the component itself: `import LoginForm from "../LoginForm";` — use
  your best judgement on the import path from `target_symbols` alone.
- Render the component: `render(<ComponentName {...props} />)`, building
  `props` from `input`. Some `input` keys describe preconditions/state
  (e.g. a pre-filled form field, a prior validation error shown) rather
  than literal props — translate these into realistic setup (props,
  `fireEvent` interactions before the assertion) rather than passing them
  through verbatim if they clearly aren't component props.
- Assert on `expected` — e.g. `expected.renders` → the component rendered
  without throwing, `expected.text_visible` → `screen.getByText(...)` finds
  it, other free-form keys → assert the corresponding rendered
  state/behavior matches the given value.
- This file uses JSX — write valid JSX syntax; keep test bodies otherwise
  simple so the file is easy to eyeball for correctness.
- One test per test case, inside a `describe`/`test` block; name each
  `test` by `case_id_with_underscores`.
