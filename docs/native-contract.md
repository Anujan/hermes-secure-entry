# Native callback compatibility and remaining limits

## Findings (no core edits made)

Examined the installed/canonical Hermes 0.21.5 native vault code and read-only upstream `7bf3766f3db72d4643d1a78d18e51c1d9ddf1d6d`. The public plugin guide guarantees `PluginContext.register_tool`, hooks, and execution middleware, but does **not** document a secure-prompt provider registration contract.

Version 0.2.0 implements a scoped bridge using public native `get/set_code_prompt_callback` and `get/set_unlock_prompt_callback` functions in `agent/vault_backends/unlock.py`, installed around one existing native execution through registered `tool_execution` middleware. Original callbacks are restored in `finally`; captured callbacks cannot collect after the scope ends. A genuine separate masked manager-unlock form returns the master password to the native backend, not an approval Boolean. No dummy unlock callback, `can_prompt_here` bypass, monkeypatch or custom browser injector is used.

Only `in_process` plugin isolation supports native thread-local callbacks. Native `tools.thread_context.propagate_context_to_thread` carries callbacks and ContextVars to workers and clears them afterwards. Catalog validation's static `host_ready` verdict does not prove an isolated host can set parent TLS; host isolation is refused at runtime. The bridge scopes native list (metadata unchanged), unlock, and code tools. It requires post-auth Photon DM task-local bindings, matching home/profile, sender/chat/session and middleware session correlation; legacy environment values alone, cron, single-query, API/headless, delegated and group contexts are refused. The callback rechecks its owner on thread handoff. No pre-auth inbound hook establishes authority.

### 1. Save versus transient sign-in

`tools/browser_vault_tool.py:browser_vault_save_login` invokes a callback `(origin, host) -> {identifier,password}`. It unconditionally calls `get_vault_store().add_item`, then `browser_vault_fill`. There is no save/one-shot result discriminator. A plugin cannot truthfully offer a "do not save" checkbox through that callback. Returning an ephemeral vault handle would invent a new secret-injection backend and violate the requirement to retain the native injection path.

### 2. Browser binding

Save-login callbacks receive no immutable target, frame, field identity, navigation generation, cancellation token, or native commit capability. `browser_vault_fill` may focus/reselect a matching-origin tab after the user answers. Origin equality is not exact target equality.

The native code tool inspects controls before prompting, stamps them with a nonce, normalizes/redacts input, and fills with origin + slot checks via supervisor WS, never argv. It re-admits Bot Desktop control at the write after the human-length wait. These paths remain intact because the middleware calls the existing registered native handler, not a copied injector. No OTP collector exists until the native callback supplies its inspected site; the request tool's verification-code operation returns only an instruction to use native code entry.

**Native tab-selection ambiguity is unresolved**, not repaired by this bridge. Origin equality and inspection stamps are not proof of immutable target/frame/navigation generation; hostile same-origin scripts may copy a stamp. Inspect the intended page first. The tested installed snapshot lacks the newer canonical OTP handle-origin precheck, so every nonempty OTP handle is refused before native resolution (`unsupported_handle_binding`). Manual code entry without a handle is the enabled preview; saved-seed automatic TOTP through a handle is not enabled. Passkey/hardware-key/app approvals with no code field arm no collector and must be completed through the actual device mechanism.

Manifest compatibility range is `>=0.21.5,<0.22.0`. Synthetic tests exercise the selected PM snapshot `5ca37dcfbb1d4e14b914978392b028f5`, not every version in that range. Re-run tests/doctor/validate after upgrades. Callback setters are version-specific surface APIs, not a new universal PluginContext prompt-provider contract. The integration test executes the real registered native code/unlock handlers with synthetic supervisor/manager boundaries, real redaction, real HTTP-to-callback transport, native thread propagation and native send scheduling on a synthetic gateway loop. It does not prove real CDP/Photon/manager/HTTPS integration, physical Safari/VoiceOver accessibility or website authentication.

### 3. Atomic update

`agent/vault_store.py:VaultStore` exposes `add_item`, metadata listing/readback, `remove_item`, and server-side `resolve_secret`; it exposes no public atomic same-record update. Private `_locked/_read_all/_write_all` surgery or delete-then-add is not an acceptable substitute. This release only adds a new item and never deletes an old item.

### 4. Delivery

Add-login returns its URL for the originating conversation. Native prompts send the URL directly while the tool worker waits, using a destination built solely from the authenticated DM context. If a native `send_message` registry entry exists, delivery uses `ctx.dispatch_tool`; the selected test snapshot has **no registered send_message tool**, despite having its native implementation. In that case the adapter selects `tools.send_message_tool.send_message_tool`, the same native function used by the Hermes send CLI, before any send. It never retries another transport after a delivery failure or ambiguous result, and never accesses private gateway members. The native send path schedules onto the live gateway loop, avoiding a worker/event-loop wait deadlock. Real Photon delivery still needs operator testing.

Native send mirrors text into session history: **capability URLs may be model-visible**. This is not transcript-free delivery. Codes/master passwords remain in memory/direct callback input and never enter dispatch args/results. Delivery failure revokes the form; the total callback execution deadline is 180 seconds. Pending and received-but-not-consumed input expires. Once input is handed to native code, `commit_unknown` prevents cancellation from falsely promising no action. Verified native results become `filled` or `unlocked`, never authenticated. Native error strings are not relayed; only allowlisted error-type constants survive.

### 5. Lifecycle cancellation

The host's idle `/stop` path returns no-active-agent without emitting `agent_loop_stopped`; a normally delivered link survives. This release supports explicit form Cancel and owner-bound `secure_entry_cancel`, not reliable idle `/stop` revocation. The tests execute the actual host stop handler with an idle runner (isolating only launcher constants and background-delegation lookup), then verify the link remains pending and explicit cancel works. No pre-auth `pre_gateway_dispatch` mutation or core edit is used to work around this contract.

## Possible upstream improvements (not prerequisites for this in-process OTP bridge)

1. A documented `ctx.register_secure_prompt_provider(provider)`/scoped registration lease, installed in actual authorized tool workers and inherited through native thread-context propagation. It must preserve the existing `can_prompt_here` gates and headless/cron/delegated denial rules.
2. Host-created request descriptors with profile/session/sender binding and a bound notification callback. The model can supply only labels/metadata, not destinations, secrets, or privileged target IDs.
3. Native login request with explicit `save_policy` choices: `once`, `save`, `update(handle)`. The native tools remain the only browser-secret injectors. Values never enter tool arguments/results.
4. An immutable native browser target/frame/input set and navigation/control-generation fence, selected unambiguously before the human prompt and checked atomically with the final write. Native field identity/nonce and supervisor/takeover protections remain mandatory. A different tab, iframe, reload, navigation, replaced control, multiple candidate form, expired request, stop/reset, or profile/session rotation must refuse before writing.
5. Public atomic `VaultStore.update_item` preserving a validated existing login handle. Native store owns lock/encryption/fsync and metadata verification; failure preserves the prior record.
6. Native commit outcome callback to distinguish `received`, `saved`, `filled`, `refused`, `expired`, and `cancelled`. `filled` must never imply authenticated. A failed/partial native action cannot be blindly replayed.

Revalidate behavior, not just symbol names, after a host upgrade. A parent-side prompt-provider seam is still needed for host isolation. Immutable-target APIs and atomic updates would improve native capabilities but are not invented prerequisites to deny existing in-process OTP callbacks. Core upgrade and extension development remain separate; this plugin contains no core patch or runtime monkeypatch. Live installed-copy synchronization is not performed: hooks/middleware can hotload into current sessions while schemas are deferred, and no safe new-session-only activation gate has been established.
