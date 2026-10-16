# 0.5.0 validation record

## Scope

Plugin-only extension on `feat/local-link-payment`; no core modifications and no live installation/activation. Link remains supported. New tools: `secure_entry_card_fill`, `secure_entry_card_remove`; `secure_entry_request` adds `operation=add_card`. Existing status/cancel apply unchanged.

## Executed RED/GREEN evidence

Each production feature slice followed a real failing test run before implementation:

- Private HTTP add: `invalid_operation != pending`, then actual native encrypted payment add/list/reopen passed.
- Cleanup: missing metadata-only cleanup tool, then explicit native remove/readback passed.
- Saved-card fill: missing retained native vault-card fill, then real captured cross-origin iframe/native consent passed.
- Registration: the two new tools missing from actual registrations, then all six registered.
- Cleanup malformed handle: `absent != refused`, then format rejection with no echoed input passed.
- Cardholder mapping: real browser `write_unknown` when `cc-name` was absent from the source's billing map, then all six native writes passed.
- Diagnostic version: `0.4.6 != 0.5.0`, then payment/admission/browser assertions passed with the new marker.

No secret-bearing user input was collected. Synthetic secrets occur only in disposable fixtures and native test-memory checks. Native approval enqueue/resolution, captured browser transport and generated payment JavaScript were exercised, not replaced by a pretend fill.

## Reproduction

Use a separate Hermes-compatible test interpreter with unittest, ruff, Playwright/Chrome and Windows native support already prepared. Never pip-modify the selected live runtime. In a clean copy of this revision:

```bash
# Values are operator-selected absolute native Windows paths.
HERMES_HOME="$SCRATCH/secure-entry-card-test-home" \
PYTHONPATH="$SELECTED_HERMES_WORKSPACE" \
"$TEST_PY" -m unittest discover -s tests -v

"$TEST_PY" -m ruff check secure_entry/cards.py secure_entry/native.py \
  secure_entry/service.py secure_entry/payment.py secure_entry/broker.py \
  tests/test_cards.py tests/test_registration.py __init__.py

git diff --check

HERMES_HOME="$SCRATCH/secure-entry-card-doctor-home" \
"$TEST_PY" -m hermes_cli.main plugins doctor "$CLEAN_PLUGIN_PAYLOAD" --ci

HERMES_HOME="$SCRATCH/secure-entry-card-doctor-home" \
"$TEST_PY" -m hermes_cli.main plugins validate "$CLEAN_PLUGIN_PAYLOAD" --json
```

Results:

- Full suite against canonical Hermes source: **194 tests, OK**.
- Full suite against PM-selected Hermes workspace: **194 tests, OK**.
- Clean tracked-payload full suite against PM-selected workspace: **194 tests, OK** (111.001 seconds in the recorded clean-payload run before final documentation/test-dispatch refinements; the final rerun is reported with the published SHA).
- New real-card tests: **8 tests, OK**, including native registered `PluginContext.dispatch_tool` -> captured browser -> six fields and explicit cleanup.
- Ruff targeted check and `git diff --check`: passed.
- Doctor: `secure-entry 0.5.0`, runtime discovery/import/registration passed; **6 tools, 3 hooks**.
- Catalog validator: **ok=true**, tool/hook/middleware declarations match, security scan safe, no core overrides or built-in collisions. It still warns about version-specific native imports (vault/session/consent/capture/takeover integration); this is not an assertion of reviewed catalog acceptance or documented `ctx.*` vault facades.

An initial nonisolated run inherited installed middleware from the active profile and failed OTP bridge status assertions. Untouched 0.4.6 baseline reproduced the same failure family. All assertions passed once `HERMES_HOME` was isolated; no production fence or test expectation was weakened to hide those failures. The baseline also had one timing-sensitive non-primary-tab test failure in a full run; isolated candidate full runs passed it. A canonical host `DeprecationWarning` about positional `re.split(maxsplit)` is pre-existing and not patched here; selected-workspace runs were clean.

An initial published Windows CI run failed because the existing test environment did not install Playwright (`ModuleNotFoundError`), so browser tests could not import. The workflow now installs Playwright only into the isolated test environment and provisions Chrome explicitly; it does not skip browser tests or modify a live runtime. Final exact-head CI status is included in the publication report.

## Native requirements and limits

See [real-card-payment.md](real-card-payment.md) for the exact public native APIs, CVC persistence contract and blocker for a CVC-less variant. Both routes require in-process native integrations, genuine human DM owner/session/profile, native explicit payment consent, `SUPERVISOR_REGISTRY.capture`/`CapturedCDP`, takeover lease, and the existing standard-autocomplete direct-iframe writer contract. Manifest stays bounded to Hermes `>=0.22.1,<0.22.2`.

No hotel, Passkey checkout, live user browser, physical screen reader, actual card, charge, reservation, or live activation was tested. The parent/operator must inspect the official intended checkout origin, independently verify this artifact, coordinate activation and only then issue the actual private link. Cleanup is never automatic and never claimed successful after an uncertain native outcome.
