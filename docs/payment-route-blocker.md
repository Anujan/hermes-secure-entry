# Browser route decision: no core dependency

The earlier proposed provenance registry was not implemented. Its necessity was falsified in an isolated harness using pristine core at `046094df28b`. The plugin candidate remains uninstalled and unactivated. No live browser, wallet, payment API, user secret, configuration or gateway process was used or changed.

## Existing public native contract

- `tools.browser_supervisor.SUPERVISOR_REGISTRY.capture(task_id)` already captures an existing native supervisor. It never starts, reconnects or refocuses one.
- `tools.browser_supervisor_capture.CapturedCDP.is_valid()` binds the supervisor object, task key, exact WebSocket object and loop. Stop, registry replacement and reconnect invalidate it. `call(..., before_send=guard)` rechecks validity before dispatch on that same socket.
- BrowserUse's `_attach_vault_supervisor` already attaches the actual resolved endpoint under the native task at dispatch. Default/named/hybrid backend cache keys need not appear in the legacy `_active_sessions` task entry.
- Native vault operations allow cloud/CDP routes. A local metadata bit is neither a prerequisite for approved secret injection nor proof of an endpoint's identity. The candidate's additional local-only admission constraint was an unjustified compatibility restriction, not a native credential-safety invariant.

## Plugin-only implementation

The plugin calls only the existing public native capture API, never a backend resolver, browser creator, endpoint guess or metadata setter. Its exact parent ID must exist on that captured socket; the direct iframe, origins, documents and nodes are bound by the existing retained-document implementation. Independent Link authorization and native `request_elicitation_consent(surface='vault-payment')` remain mandatory.

Because native vault's legacy desktop metadata lookup can miss named BrowserUse routes, payment conservatively checks the native **profile-specific desktop lease for every route**, before capture, around native approval/retrieval, immediately before every target CDP dispatch, and after completion. It retains the admitted epoch, so takeover followed by handback still invalidates an in-flight operation. This does not assert that a route is local and can refuse an unrelated cloud/CDP operation while a human holds this profile's desktop. No native approval or takeover protection is bypassed.

`LocalPayment` refers to the local Link CLI/private-file source, not an assurance the captured browser runs locally. Local or cloud CDP supervisors can satisfy the contract. Direct-cloud BrowserUse without a native capture cannot. There is deliberately no plugin route-name selector, route registry or immutable 'last successful dispatch' receipt: the operation targets the explicit parent/frame on the **current task capture**, not an inferred named daemon. If another route replaces the supervisor, old captures refuse rather than retarget. If named sessions share one browser endpoint, exact parent/frame binding—not a route-name guess—selects the document.

## Executed evidence

`tests/test_payment_browser.py` exercises real `browser_use_cli.browser_exec`, actual `browser_harness.run` subprocess/IPC, native `_attach_vault_supervisor`, public capture, genuine native gateway consent enqueue/resolution, Windows private-file handling and a real OOPIF fill for **default, named and hybrid routes**. Only browser provisioning is redirected to each test's already-launched disposable Chrome. The hybrid private-URL predicate and sidecar dispatch execute natively. Harness home/runtime are isolated; no daemon or user browser is selected by the plugin. Legacy task session metadata is explicitly absent.

Additional tests cover absent-capture refusal without resolver/start calls; invalid capture; native active takeover, mid-capture takeover and handback; concurrent stop while capture waits; native supervisor replacement during consent; and post-write takeover/replacement reporting `write_unknown`. Existing owner/profile admission, target/frame mismatch, document reload/mutation, cleanup and payment-file tests remain.

The RED regression was `test_existing_public_capture_needs_no_legacy_local_metadata`: before the adaptation, native capture was never called (`Expected 'capture' to be called once. Called 0 times.`). The plugin-only change makes it pass. The full suite and exact final output are recorded in `docs/local-link-payment.md` and the parent handoff log.

## Remaining acceptance limits

No new core patch or upstream PR is needed for the exercised payment path. This is synthetic integration evidence, not real merchant compatibility, real Link authorization, physical approval UI verification or live activation. The operator-trusted Link CLI command still needs configuration at activation; there is no per-merchant setup. The existing parent/child CDP limitation remains: parent-only mutation between separate parent precheck and child write can disclose to the retained child, followed by `write_unknown`. No atomic cross-document no-disclosure fence is claimed.
