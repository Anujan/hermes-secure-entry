# 0.5.2: value-free writer diagnostics

Diagnostics-only release. The activated 0.5.1 native fill still reported `write_unknown` at `stage=write`; the live cause is not yet measured. The 0.5.1 synthetic billing fixture did not establish the live cause.

Both saved-card and Link retained writers now return fixed refusal categories through the existing native result boundary:

- `source_missing`: a required source string is unavailable after existing billing preservation.
- `initial_mismatch`: a nonempty initial page value differs from the supplied source.
- `field_changed`: a retained control value changed unexpectedly.
- `invalidated`: the retained child/document/layout guard failed.
- `select_mismatch`: no unique enabled matching SELECT option.
- `already_used`: a second write on a consumed writer.
- `unchanged`: a dispatched write reverted to the initial value.
- `expiry_format`: combined expiry readback does not preserve the supported exact expiry format/value.
- `write_mismatch`: another field readback differs from the supplied value.
- `write_failed`: unclassified transport, pre/postflight, malformed result or exception. No raw exception is returned.

`field`, when present, is only an allowlisted canonical autocomplete token (for example `cc-name` or `billing postal-code`), never a DOM label, selector or value. `written_fields`, when known, is a bounded integer count of native setter calls, not proof of accepted or still-present values. Missing counts mean unknown, not zero. Diagnostics are re-allowlisted at the service result boundary. Results identify the executing module as `payment_diagnostic_version=0.5.2`.

The existing `write_unknown` status is retained conservatively even for zero-write writer preflight failures. No supplied name/postal mismatch policy, address-preservation rule, consent, capture/owner/lineage guard, expiry acceptance, storage, cleanup or submission behavior is loosened. A writer refusal remains visible even if postflight also detects that writer's document invalidation; no failed postflight becomes success.

## Verification

Strict RED/GREEN native-consent-to-result regression reproduced missing initial-name diagnostics, then verified fixed `initial_mismatch`, `field=cc-name`, and zero writes without returning either identity. Actual disposable Chrome OOPIF tests execute generated JavaScript for all refusal categories, including postal mismatch and unchanged/altered expiry writes. A separate RED/GREEN native-path regression verifies invalidation after one write survives postflight. Unknown category/token/count data is discarded.

Full isolated regression: **203 tests, OK**. Targeted Ruff and `git diff --check` pass. Only the disposable test interpreter, isolated HERMES_HOME, synthetic card producer/vaults and disposable Chrome were used. No live vault/browser access, installation, activation, checkout submission or core edits. Parent/operator must activate the published immutable revision and measure the actual refusal before any policy repair.
