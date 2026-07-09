# Contributing

This repo is built by four phase teams working in parallel against shared
**contracts**. These rules keep everyone's work in sync and consistent.

## Ground rules

1. **Work only in your folder.** Each team owns one `services/*` folder and the
   matching `apps/web/src/modules/*` module. See [`CODEOWNERS`](CODEOWNERS).
2. **Contracts are the product.** Anything under `contracts/` is a cross-team
   interface. Changing it requires approval from **all** teams (CODEOWNERS
   enforces this) and a version bump — never a silent edit.
3. **Never break a downstream consumer.** Your output must always satisfy the
   contract the next phase reads.

## Branching model

- `main` — always releasable. No direct pushes; PRs only.
- Feature branches, named `<phase>/<short-description>`:
  - `requirements/…`, `design/…`, `implementation/…`, `testing/…`
  - platform/infra work: `platform/…`
- Contract changes: `contract/<from>-to-<to>-<change>`
  (e.g. `contract/design-to-implementation-add-field`).

Keep branches short-lived. Rebase on `main` before opening a PR.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <summary>

feat(implementation): generate A3 module skeleton from design pack
fix(testing): correct FAIL verdict when coverage is null
docs(contracts): clarify mandatory fields in design-to-implementation
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.
Scope = the folder/phase you touched.

## Pull requests

- Open against `main`. Fill in what changed and why.
- Every PR needs **at least one approval from the owning team** (CODEOWNERS).
  Contract PRs need approval from **all** teams.
- CI must be green (lint, type-check, tests) before merge.
- If you change a contract, also regenerate the types in `packages/schemas`
  and update every affected consumer in the **same** PR.
- Squash-merge to keep `main` history linear.

## Branch protection & code-owner review

Each phase team works on its `phase/*` branch and opens PRs **into `main`**.
Because CODEOWNERS scopes ownership to each phase's folders, the matching owner
is auto-required as reviewer and the PR can't merge without them:

| Branch                 | Required approver             |
| ---------------------- | ----------------------------- |
| `phase/requirements`   | nishant.khalkar@zensar.com    |
| `phase/design`         | abhishek.pandit@zensar.com    |
| `phase/implementation` | khushi.patil@zensar.com       |
| `phase/testing`        | piyush.nashikkar@zensar.com   |
| any `contracts/**` change | all four                   |

This enforcement requires a one-time branch-protection setup on `main` by a repo
admin — see [`docs/branch-protection.md`](docs/branch-protection.md).

## Local setup

```bash
cp .env.example .env
docker compose up -d      # PostgreSQL + pgvector + Redis
```

## Definition of done

- [ ] Code lives in the correct team folder.
- [ ] Input/output still conforms to the relevant contract.
- [ ] Tests added/updated and passing.
- [ ] CODEOWNERS review obtained.
- [ ] No secrets committed (`.env` is git-ignored; use `.env.example`).
