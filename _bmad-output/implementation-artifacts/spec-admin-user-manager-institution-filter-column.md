---
title: 'Add institution filter and column to super-admin user manager'
type: 'feature'
created: '2026-09-03'
status: 'done'
review_loop_iteration: 0
context: []
route: 'one-shot'
---

# Add institution filter and column to super-admin user manager

## Intent

**Problem:** `admin_user_list` (the super-admin user manager) lets a superuser see users across every institution but gave no way to filter that list down to one institution, and the table never showed which institution a row belonged to — a superuser had to open each user individually to find out.

**Approach:** Added a superuser-only `institution` field to `UserSearchForm`, applied it as an additional queryset filter in `admin_user_list`, and added a superuser-only "Institution" column to the user table template. Non-superuser admins are already institution-scoped to their own institution's users (pre-existing behavior), so the field is popped from the form entirely for them rather than just hidden, keeping the enforcement structural.

## Suggested Review Order

**View/query logic**

- Entry point: form built, then institution field structurally removed for non-superusers.
  [`views.py:605-607`](../../users/views.py#L605-L607)
- Institution filter applied only when a superuser explicitly selects one.
  [`views.py:645-648`](../../users/views.py#L645-L648)
- `select_related('institution')` scoped to superuser only — avoids an unused join for staff-only admins.
  [`views.py:650-651`](../../users/views.py#L650-L651)

**Form field**

- New `ModelChoiceField` restricted to active institutions, matching the convention used elsewhere in the codebase (`referral/forms.py`, `institution/views.py`).
  [`forms.py:529-534`](../../users/forms.py#L529-L534)

**Template — filter UI**

- Institution `<select>` only rendered for superusers; search column width adjusted conditionally so the non-superuser filter row still sums to a clean 12-column grid.
  [`user_list.html:24`](../../templates/users/admin/user_list.html#L24)
  [`user_list.html:36-40`](../../templates/users/admin/user_list.html#L36-L40)
- Institution query param carried through pagination links alongside the existing filter params.
  [`user_list.html:181`](../../templates/users/admin/user_list.html#L181)

**Template — table column**

- "Institution" header and cell, both superuser-gated; falls back to an em-dash for a user with no institution assigned.
  [`user_list.html:66-68`](../../templates/users/admin/user_list.html#L66-L68)
  [`user_list.html:94-102`](../../templates/users/admin/user_list.html#L94-L102)

**Tests**

- Filtering, cross-institution visibility, and non-superuser field/param exclusion.
  [`test_crud.py:209`](../../users/tests/test_crud.py#L209)
