# Recovery and verification

## Expired, cancelled, failed, or unavailable link

Do not reuse or replay the submission. `commit_unknown` means the save may have completed: inspect native metadata using `browser_vault_list`/`hermes vault list`, including any returned handle, before considering another add. Never blindly request a new link after this outcome. Expired/cancelled/unavailable requests with no attempted save can be replaced in the same authorized Photon DM. Never remove an old item before confirming a replacement.

Add-login forms expire after ten minutes; native code/unlock prompts share a total 180-second execution deadline. Refresh shows current state. `saved` means native vault storage verified by metadata readback. `filled` means the native handler reported a code fill; `unlocked` means the manager reported unlock. None means website authentication. For a code/unlock `commit_unknown`, inspect the browser/manager before retrying, not just the vault. A native tool may still be completing after the value was handed off.

## Cancellation contract

Idle `/stop` does not reliably revoke a delivered link. After normal completion, the host no-active-agent path does not emit `agent_loop_stopped`. Use the form **Cancel** button or `secure_entry_cancel(request_id)` from the originating session; verify `cancelled`. Normal turn-end preserves the link for delivery. Delivered stop/reset/abnormal-end events and unload invalidate pending requests, but cannot undo a committed save. No pre-authentication gateway hook is used to mutate requests.

## Listener or route unavailable

Run `python -m secure_entry.cli diagnose`. An inactive listener before the first valid request is normal. Test loopback with the explicit synthetic demo and `python -m secure_entry.cli health`. If loopback works but the phone cannot reach HTTPS, inspect Tailscale Serve status/ACLs on the operator side. Preserve every unrelated Serve route. The plugin never changes Tailscale configuration.

Port occupied: stop only the known disposable demo or coordinate gateway shutdown; do not kill unrelated processes. A second demo/gateway instance must not share port 8769. The gateway plugin refuses to create a request if binding fails.

## Disable or upgrade

`hermes plugins disable secure-entry` changes future loading; it does not prove a running gateway has unloaded its copy. Coordinate a normal gateway restart or explicit host unload after cancelling pending requests. Never assume disabling a config key stops an existing listener. Plugin unload closes its own listener and cancels pending requests. Do not stop/restart Hermes as part of unattended installation.

To replace a staged local version, disable and coordinate unload first, move the existing plugin directory to an operator-chosen backup **outside the plugin discovery directory**, then rerun the installer. It refuses destructive overwrite. Review source, run tests/doctor/validate, then explicitly enable. No automatic updater exists. Native vault data is owned by Hermes under the active home and must not be moved/deleted by plugin recovery.

Removing the dedicated Tailscale Serve route is an operator action; remove only the route created for this plugin, not other ports. No route-removal command is automated here.

## Before publication or real credentials

1. Independent source/security review, including the explicit partial-feature disclosure.
2. Run unit/integration tests with the PM-created test interpreter and native vault implementation; run `hermes plugins doctor PATH --ci` and `hermes plugins validate PATH --install-deps`.
3. Start the synthetic demo at loopback8769. Verify `/health`, then have the operator create the dedicated tailnet-only HTTPS route. Test the one-use link on Safari/VoiceOver using only its printed synthetic values.
4. Verify heading/labels/password masking/autocomplete/tab order/Continue/Cancel/status, expiry, link preview, replay refusal, and same-session status access. Screen-reader device testing is not replaced by HTML assertions.
5. Stop the demo. Coordinate plugin enable/new gateway process and a new Photon conversation. Verify real Photon context binds `chat_type=dm`, chat/user/session key/session ID before expecting a request to succeed. Missing/unsupported context fails closed, not by falling back to a home channel.
6. Test the OTP/unlock preview with synthetic values and a controlled page first. Verify native list/unlock, actual-site form arming, direct DM delivery while the worker waits, expiry/cancel/duplicate POST, code redaction, callback cleanup, supervisor/takeover refusal and unknown-outcome handling. Use no OTP handle on this snapshot. Do not mistake a synthetic supervisor result for real browser integration. Transient sign-in remains dropped. Real external-manager/Photon/browser/HTTPS testing is not claimed by the automated suite.
7. Do not copy upgraded middleware over an active installed plugin. Hooks/middleware may hotload into current sessions even when schemas are deferred; no safe live new-session-only activation gate is claimed. Coordinate unload/new process and a fresh conversation first. Native capability URLs may appear in mirrored session history; never post them publicly.
