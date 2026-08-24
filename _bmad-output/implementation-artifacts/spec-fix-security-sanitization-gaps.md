---
title: 'Fix security-sanitization gaps (sanitize-then-unescape XSS bypass, reverse-tabnabbing)'
type: 'bugfix'
created: '2026-08-24'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 'e69735084b85a5b02f4afcef901a12409f555778'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Two independent XSS/injection gaps from the codebase review's "security-sanitization" group. (1) `sanitize_text_input()` strips `<tag>` patterns, event handlers, and dangerous protocols *before* calling `html.unescape()` at the very end — so an entity-encoded payload like `&lt;script&gt;alert(1)&lt;/script&gt;` contains no raw `<` characters when the strip regexes run, passes every filter untouched, and is only decoded back into live `<script>alert(1)</script>` markup by the trailing unescape call. Any medical text field using this sanitizer is vulnerable to stored/reflected XSS via double-encoded payloads. (2) `sanitize_html()`'s `ALLOWED_ATTRIBUTES['a']` permits `target` and `rel`, but nothing forces `rel="noopener noreferrer"` on a `target="_blank"` anchor — `bleach.clean()` only keeps or drops attributes an author supplies, it can't synthesize new ones, so a `<a target="_blank">` link (with no `rel`, or an incomplete one) passes through as-is. A page opened this way can use `window.opener` to redirect the original tab to a phishing page (reverse tabnabbing). (Note: the codebase review's third item in this group, the virus-scan stub, was investigated and deliberately deferred — see `deferred-work.md` — since a correct fix requires real antivirus integration, not a narrow code change, and would otherwise block all attachment downloads app-wide.)

**Approach:** (1) Move the `html.unescape()` call to the very start of `sanitize_text_input()`, before any of the strip regexes, so entity-encoded payloads are decoded first and then actually get caught by the tag/event-handler/protocol strips — matching the function's own documented intent ("Unescape HTML entities to prevent double-encoding"), just at the correct point in the pipeline. (2) Add a small post-process step in `sanitize_html()`, applied after `bleach.clean()`/`bleach.linkify()`, that scans the already-sanitized, well-formed `<a ...>` tags for `target="_blank"` and merges in `noopener`/`noreferrer` rel tokens (preserving any existing `rel` value like `nofollow` rather than clobbering it). This runs on bleach's own safe output, not raw input, so a regex is an accepted, standard pattern here (bleach's attribute allowlist mechanism can only keep/drop existing attributes — it has no way to inject a new one).

## Boundaries & Constraints

**Always:** Preserve the documented behavior of both functions for all non-adversarial input — plain text, medical notation (`< 5 mg/dl`, `> 38°C`), and already-safe HTML must sanitize identically to before. Preserve idempotency: running `sanitize_html()` twice on already-fixed output must not double up `rel` tokens.

**Ask First:** Nothing expected — both fixes are narrow, isolated, and the third finding in this group (virus-scan stub) was already explicitly deferred by the user rather than attempted here.

**Never:** Do not touch the virus-scan stub (`patients/models.py` `_schedule_virus_scan`) — explicitly deferred, tracked in `deferred-work.md`. Do not change `ALLOWED_TAGS`/`ALLOWED_ATTRIBUTES`/`ALLOWED_PROTOCOLS` themselves. Do not attempt to fix the separately-flagged `(javascript|data|vbscript):` whitespace-bypass regex in `validators.py:52` — out of scope for this spec (not part of the deferred "security-sanitization" group's three named items).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Double-encoded script tag | `sanitize_text_input("&lt;script&gt;alert(1)&lt;/script&gt;")` | Script tag and its content are stripped, not decoded into live markup | N/A |
| Medical notation preserved | `sanitize_text_input("BP < 120/80 mmHg")` | Unchanged (`<` followed by digit isn't a tag) | N/A |
| Entity-encoded medical notation | `sanitize_text_input("Temp &lt;5")` | Decodes to `Temp <5`, still preserved (not stripped) | N/A |
| target=_blank, no rel | `sanitize_html('<a href="..." target="_blank">x</a>')` | `rel="noopener noreferrer"` added | N/A |
| target=_blank, existing rel | `sanitize_html('<a href="..." target="_blank" rel="nofollow">x</a>')` | `rel="nofollow noopener noreferrer"` (merged, not replaced) | N/A |
| target=_blank, already has both tokens | `sanitize_html('<a ... target="_blank" rel="noopener noreferrer">x</a>')` | Unchanged (idempotent) | N/A |
| No target=_blank | `sanitize_html('<a href="...">x</a>')` | Unchanged | N/A |

</frozen-after-approval>

## Code Map

- `ndas/custom_codes/validators.py:12-71` (`sanitize_text_input`) -- move the `html.unescape()` call (currently line 61) to immediately after `text = str(value)`
- `ndas/custom_codes/sanitization.py:37-79` (`sanitize_html`) -- add a new `_enforce_noopener_noreferrer()` helper and call it after `bleach.linkify()`
- `ndas/custom_codes/sanitization.py:23-32` (`ALLOWED_ATTRIBUTES`) -- READ-ONLY reference: confirms `'a': [..., 'target', 'rel']` are both already-allowed attributes bleach passes through verbatim, which is why a post-process (not an attribute-allowlist change) is needed

## Tasks & Acceptance

**Execution:**
- [x] `ndas/custom_codes/validators.py` -- in `sanitize_text_input`, move `text = html.unescape(text)` to run immediately after `text = str(value)` (before the script/style/event-handler/protocol/tag strips), removing the old call at the end of the pipeline -- closes the double-encoded XSS bypass
- [x] `ndas/custom_codes/sanitization.py` -- add `_enforce_noopener_noreferrer(html_content)`: a regex-based post-process over `<a ...>` tags that, when `target="_blank"` is present (case-insensitive), adds `rel="noopener noreferrer"` if no `rel` attribute exists, or merges in the missing `noopener`/`noreferrer` tokens if one does -- closes the reverse-tabnabbing gap
- [x] `ndas/custom_codes/sanitization.py` -- call `_enforce_noopener_noreferrer()` on `cleaned` at the end of `sanitize_html()`, after the `bleach.linkify()` step -- ensures both author-supplied and (if ever configured) auto-linkified `target="_blank"` anchors are covered
- [x] new test file `ndas/tests/test_validators_sanitization.py` -- add tests for `sanitize_text_input`: a double-encoded `<script>` payload is neutralized (not decoded into live markup); medical notation (`< 5 mg/dl`) and entity-encoded medical notation both still pass through correctly
- [x] new test file `ndas/tests/test_sanitization.py` -- add tests for `sanitize_html`: `target="_blank"` with no `rel` gets `noopener noreferrer` added; `target="_blank"` with `rel="nofollow"` gets both tokens merged in (not replaced); a link without `target="_blank"` is untouched; running the function twice is idempotent

**Acceptance Criteria:**
- Given `sanitize_text_input("&lt;script&gt;alert(1)&lt;/script&gt;")`, when sanitized, then the output contains no executable `<script>` tag
- Given `sanitize_text_input("BP < 120/80 mmHg")`, when sanitized, then the medical notation is preserved unchanged
- Given HTML containing `<a href="..." target="_blank">`, when passed through `sanitize_html()`, then the output's anchor tag includes both `noopener` and `noreferrer` in its `rel` attribute
- Given HTML containing `<a href="..." target="_blank" rel="nofollow">`, when passed through `sanitize_html()`, then the output's `rel` attribute contains `nofollow`, `noopener`, and `noreferrer` — none dropped

## Verification

**Commands:**
- `python manage.py test ndas.tests.test_validators_sanitization ndas.tests.test_sanitization` -- expected: all pass

## Suggested Review Order

**Sanitize-then-unescape XSS bypass**

- Core fix: unescape moved to the front of the pipeline, now looped to a bounded fixed point so multiply-encoded payloads (not just single-encoded) are fully decoded before the strips run.
  [`validators.py:51`](../../ndas/custom_codes/validators.py#L51)

- Single- and triple-encoded payload regression coverage, plus medical notation preserved through the new decode-first ordering.
  [`test_validators_sanitization.py:25`](../../ndas/tests/test_validators_sanitization.py#L25)
  [`test_validators_sanitization.py:53`](../../ndas/tests/test_validators_sanitization.py#L53)
  [`test_validators_sanitization.py:70`](../../ndas/tests/test_validators_sanitization.py#L70)

**Reverse-tabnabbing (missing rel=noopener/noreferrer)**

- Core fix: a post-process over bleach's own sanitized `<a>` output, wired in after `bleach.linkify()`.
  [`sanitization.py:46`](../../ndas/custom_codes/sanitization.py#L46)
  [`sanitization.py:133`](../../ndas/custom_codes/sanitization.py#L133)

- Add/merge coverage, plus a real bug the review cycle caught: browsers trim whitespace around the target value per the HTML5 spec, so an exact-match regex missed `target=" _blank"` — now fixed and tested.
  [`test_sanitization.py:25`](../../ndas/tests/test_sanitization.py#L25)
  [`test_sanitization.py:31`](../../ndas/tests/test_sanitization.py#L31)
  [`test_sanitization.py:71`](../../ndas/tests/test_sanitization.py#L71)

- Adversarial-input regression tests added during review — verified empirically (not just by inspection) that bleach's own attribute-allowlisting and value-escaping guarantees make attribute-collision and `&gt;`-truncation attacks unreachable in practice; tests lock that in rather than leaving it as an unverified assumption.
