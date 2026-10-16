# 0.5.1: native saved-card billing compatibility

## Reproduced cause (not a live-site claim)

An actual disposable Chrome OOPIF fixture reproducing the observed formless widget (required number and combined expiry, matching prefilled name/postal, country/state SELECTs with USA/NewYork values, prefilled street/city/phone, optional blank line2, absent CVC) returned exactly `success=false,status=write_unknown,stage=write,payment_diagnostic_version=0.5.0` before this fix.

The saved native card adapter supplies only name/postal billing metadata. The writer required a source string for every widget field; absent country/street/city/state failed its pre-write validation, even though those controls were already filled. This explains empty number and expiry without hypothesizing navigation, carousels, or a mask failure.

The adapter now explicitly enables preservation of unsupplied billing fields. Only already-valid billing controls are preserved; optional blank fields stay blank. Supplied name/postal must still match. No address is invented, no prefilled identity is overwritten, and Link's issued-billing requirements remain unchanged. The private-file Link consumer allowlists its card payload and does not accept this adapter-only policy from producer JSON.

A separate RED/GREEN Chrome regression demonstrates ordinary expiry masking from `12/35` to `12 / 35`: only spaces surrounding the slash are accepted with identical two-digit month/year. Other month/year values, extra characters, missing slash, and four-digit-year changes are refused. Both input/change events remain required. This is a proven interoperability case, not evidence that the live widget uses that mask.

## Why not always use core browser_vault?

Prefer `browser_vault(action=fill,handle=...)` for supported normal current-document card forms. The core does support native payment handles; listing one is not evidence of iframe support. The plugin does not need a stronger fence merely to justify duplicating an already-supported operation.

The selected 0.22.1 runtime's `tools/browser_vault_tool.py:426` does payment consent, exact saved-origin matching and current-page inspection. Its schema accepts handle, not a parent/frame/origin pair. `_eval_js` and `_eval_js_secret` evaluate on the supervisor page session. `agent/vault_login_classifier.py:339` inspects `document.querySelectorAll('input, select')`, not descendant frame documents. Hidden parent controls are excluded. Navigating directly to the provider origin is not equivalent: the saved item is merchant-bound and that would fail origin matching, while losing the original checkout context.

`test_core_native_fill_cannot_reach_cross_origin_widget` exercises the actual native `browser_vault_fill` handler, genuine native consent, real supervisor/tab selection and actual Chrome evaluation on a synthetic merchant page with a provider OOPIF and hidden cardnumber/depDate mirrors. Only backend discovery is substituted with a disposable native vault. It returns `No payment form fields were found on the current page.` without resolving the synthetic secret. Thus delegating this particular cross-origin widget to the existing native handler is not sufficient. No core changes, origin rebinding, provider top-level navigation, or generic browser secret injection are proposed.

## Validation and limits

Final local validation against the PM-selected 0.22.1 workspace: **199 tests, OK** (116.664 seconds); targeted Ruff and `git diff --check` pass. Clean-payload native doctor passes (secure-entry 0.5.1, six tools, three hooks); catalog validator returns `ok=true` with the existing version-specific native-import warning. The disposable test interpreter was not the live runtime.

- RED then GREEN: observed-shape saved-card/native-consent fixture; whitespace expiry masking; executing-module version bump.
- Regression negatives: missing required unsupplied billing, mismatched supplied name/postal, Link missing issued address, malformed or altered expiry.
- Existing authority/capture/owner/lineage/lifecycle/takeover tests remain in force.
- A full-suite run exposed a test-output issue: random target IDs can contain synthetic registered secret substrings and be redacted by the harness. The non-primary selection assertion now compares exact IDs inside the harness and returns a fixed boolean marker, without relaxing the target check.
- All tests use an isolated HERMES_HOME, separate test interpreter, disposable vault and disposable Chrome. No installed plugin/core changes, live card/browser/vault access, activation, submission, purchase or cleanup of the user's saved card.

Final test counts, doctor/catalog results, pushed revision and CI status are reported with publication. Historical 0.5.0 evidence remains in real-card-validation.md.
