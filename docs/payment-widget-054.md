# 0.5.4: narrowly permit framework value-attribute reflection

A React-like event handler that synchronizes an INPUT's `value` attribute after the native property setter reproduced the measured first-PAN-write invalidation in disposable actual Chrome cross-origin OOPIFs. The new acceptance test failed against 0.5.3 for input/change events, both plain and exactly formatted PAN/combined expiry, then passed with this fix.

The generic child observer permits only the currently self-written retained INPUT's value-attribute reflection during its synchronous setter/input/change sequence. Both its current property and every queued attribute result must match the supplied value under the existing exact semantic rules: PAN permits spaces/hyphens only while preserving every digit; combined expiry permits spacing around the slash only while preserving two-digit month/year. Mutation oldValue reconstructs intermediate attribute results so mismatched-then-restored attributes still refuse. These private checks never return values to the model. The exception is cleared in finally, including on refusal; prewrite and postwrite value-attribute changes remain sticky invalidation.

No other attributes are newly ignored. Foreign field property/attribute changes, value removal, wrong PAN digits, wrong expiry, replacement controls, restored type/name/autocomplete mutations, and ancestor security changes refuse. Existing current-document, exact-node, grouping, usability, expected-property, origin, consent, capture and takeover checks remain unchanged. No merchant selectors, retry, retargeting, core changes or billing-policy changes were added. Partial writes retain unknown/refusal semantics.

Validation against the PM-selected Hermes source, using an explicit disposable HERMES_HOME and separate test interpreter:

- Relevant actual-Chrome browser suite: **52 tests, OK**.
- Full isolated regression suite after the version bump: **209 tests, OK**.
- Targeted Ruff and `git diff --check`: passed.

Only synthetic cards, disposable vaults/profiles and isolated Chrome were used. No installation, activation, live wallet/card/vault/browser access or merchant submission was performed. Synthetic compatibility is not live checkout acceptance.
