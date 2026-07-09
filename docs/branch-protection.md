# Runbook: Branch protection & code-owner review

**Goal:** every phase's PRs can only be merged after that phase's code owner
approves. Requires repo **admin** rights. One-time setup.

## Who owns what

See [`/CODEOWNERS`](../CODEOWNERS). Summary:

| Phase          | Branch                 | Owner (must approve)          |
| -------------- | ---------------------- | ----------------------------- |
| Requirements   | `phase/requirements`   | nishant.khalkar@zensar.com    |
| Design         | `phase/design`         | abhishek.pandit@zensar.com    |
| Implementation | `phase/implementation` | khushi.patil@zensar.com       |
| Testing        | `phase/testing`        | piyush.nashikkar@zensar.com   |
| Contracts      | any                    | all four                      |

## How it actually works (read this first)

`CODEOWNERS` matches **file paths, not branch names**, and GitHub reads it from
the branch a PR **targets** (the base branch). So the workflow is:

```
work on phase/design  ──PR──▶  main
        │                        │
        │   PR only changes      │  CODEOWNERS on main sees the
        │   services/design/**   │  changed paths → auto-requires
        └────────────────────────┘  abhishek's review before merge
```

Because each phase branch only edits its own folder (see
[`CONTRIBUTING.md`](../CONTRIBUTING.md)), the "branch owner" you want falls out
of path ownership automatically. **You need only ONE ruleset — on `main`.**

## Setup (GitHub web UI)

1. Go to **Settings → Branches → Add branch ruleset** (or classic **Add rule**).
2. **Target:** branch name `main`.
3. Enable:
   - ✅ **Require a pull request before merging**
   - ✅ **Require approvals** → set to **1**
   - ✅ **Require review from Code Owners**   ← ties merges to `CODEOWNERS`
   - ✅ **Require status checks to pass** (add CI checks once they exist)
   - ✅ **Do not allow bypassing the above settings** (so admins follow it too)
4. Save.

Result: a `phase/design` → `main` PR cannot merge until abhishek approves; a
`contracts/**` change needs all four. Same for every other phase.

## Setup (gh CLI alternative)

Run with an admin token. Repo: `nishantk1710/SDLC_Agentic_AI`.

```bash
gh api -X PUT repos/nishantk1710/SDLC_Agentic_AI/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f "required_pull_request_reviews[require_code_owner_reviews]=true" \
  -F "required_pull_request_reviews[required_approving_review_count]=1" \
  -F "enforce_admins=true" \
  -F "restrictions=null" \
  -F "required_status_checks=null"
```

(Set `required_status_checks` once CI workflows exist.)

## Prerequisites for CODEOWNERS to take effect

- Each owner is a **collaborator with write access** to the repo.
- The Zensar **email in CODEOWNERS is added to that person's GitHub account**
  (Settings → Emails). If it isn't linked, GitHub silently ignores the rule.

## Optional: also protect the phase branches themselves

Only needed if you want the `phase/*` branches to be shared integration lines
that teammates also PR into (not just personal working branches). Add a second
ruleset targeting `phase/*` with *Require a pull request before merging*. For
most teams the single `main` ruleset above is enough.
