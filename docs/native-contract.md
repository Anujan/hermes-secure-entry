# Native contract blockers and required upstream extension

## Findings (no core edits made)

Examined the installed/canonical Hermes 0.21.5 native vault code and read-only upstream `7bf3766f3db72d4643d1a78d18e51c1d9ddf1d6d`. The public plugin guide guarantees `PluginContext.register_tool`, hooks, and execution middleware, but does **not** document a secure-prompt provider registration contract.

The native functions `set_save_login_prompt_callback`, `set_code_prompt_callback`, and `set_unlock_prompt_callback` in `agent/vault_backends/unlock.py` are real native APIs: thread-local surface callbacks used by CLI/TUI. A technical bridge is possible in an authorized, prompt-capable surface using those setters and native tool paths. This is not an impossibility claim. What is missing here is a complete supported Photon provider/delivery/binding contract meeting all requirements below; this release intentionally does not install a bridge. Merely assigning a wrapper to a core function, modifying approval context, or replacing browser helpers is not a supported extension. This plugin does none of those things. It does not install an always-empty unlock callback to trick `can_prompt_here` into allowing browser prompts.

### 1. Save versus transient sign-in

`tools/browser_vault_tool.py:browser_vault_save_login` invokes a callback `(origin, host) -> {identifier,password}`. It unconditionally calls `get_vault_store().add_item`, then `browser_vault_fill`. There is no save/one-shot result discriminator. A plugin cannot truthfully offer a "do not save" checkbox through that callback. Returning an ephemeral vault handle would invent a new secret-injection backend and violate the requirement to retain the native injection path.

### 2. Browser binding

Save-login callbacks receive no immutable target, frame, field identity, navigation generation, cancellation token, or native commit capability. `browser_vault_fill` may focus/reselect a matching-origin tab after the user answers. Origin equality is not exact target equality.

Canonical native code entry is stronger: the tool inspects controls before prompting, stamps them with a nonce, and fills with origin + slot checks via supervisor WS. It also re-admits Bot Desktop control at the write. The installed runtime snapshot has weaker OTP binding than the canonical checkout; do not assume these protections are present in every 0.21.5 installation. These native protections must stay intact. However, `(site,hint)` callbacks expose no public exact-target/frame/generation binding or unambiguous-tab-selection contract. An external provider cannot independently prove every required strict binding or atomically guarantee it at native commit. A pre/post JavaScript check or a lock private to the plugin cannot close that race.

Therefore this release does not collect an OTP for real browser use. A synthetic code-form transport test is not represented as native OTP success. Passkey/hardware-key/app approvals are not codes and must be completed through their real device mechanism.

### 3. Atomic update

`agent/vault_store.py:VaultStore` exposes `add_item`, metadata listing/readback, `remove_item`, and server-side `resolve_secret`; it exposes no public atomic same-record update. Private `_locked/_read_all/_write_all` surgery or delete-then-add is not an acceptable substitute. This release only adds a new item and never deletes an old item.

### 4. Delivery

Requests are created only in bound Photon DMs using native session context, never from user/model-supplied destinations. The supported add-login tool returns a metadata URL for the originating conversation; no background delivery is attempted. A blocking native browser prompt would require a host-owned delivery capability bound to the authenticated originating sender/chat/session. Capturing a gateway object in `pre_gateway_dispatch` (which fires BEFORE pairing/auth) does not itself prove recipient authorization. Arbitrary `send_message` targets are not used as a substitute.

### 5. Lifecycle cancellation

The host's idle `/stop` path returns no-active-agent without emitting `agent_loop_stopped`; a normally delivered link survives. This release supports explicit form Cancel and owner-bound `secure_entry_cancel`, not reliable idle `/stop` revocation. The tests execute the actual host stop handler with an idle runner (isolating only launcher constants and background-delegation lookup), then verify the link remains pending and explicit cancel works. No pre-auth `pre_gateway_dispatch` mutation or core edit is used to work around this contract.

## Minimal upstream API proposal (separate change, NOT implemented here)

1. A documented `ctx.register_secure_prompt_provider(provider)`/scoped registration lease, installed in actual authorized tool workers and inherited through native thread-context propagation. It must preserve the existing `can_prompt_here` gates and headless/cron/delegated denial rules.
2. Host-created request descriptors with profile/session/sender binding and a bound notification callback. The model can supply only labels/metadata, not destinations, secrets, or privileged target IDs.
3. Native login request with explicit `save_policy` choices: `once`, `save`, `update(handle)`. The native tools remain the only browser-secret injectors. Values never enter tool arguments/results.
4. An immutable native browser target/frame/input set and navigation/control-generation fence, selected unambiguously before the human prompt and checked atomically with the final write. Native field identity/nonce and supervisor/takeover protections remain mandatory. A different tab, iframe, reload, navigation, replaced control, multiple candidate form, expired request, stop/reset, or profile/session rotation must refuse before writing.
5. Public atomic `VaultStore.update_item` preserving a validated existing login handle. Native store owns lock/encryption/fsync and metadata verification; failure preserves the prior record.
6. Native commit outcome callback to distinguish `received`, `saved`, `filled`, `refused`, `expired`, and `cancelled`. `filled` must never imply authenticated. A failed/partial native action cannot be blindly replayed.

Do not enable browser collection merely because a future host version has similarly named symbols. Require the documented behavior contract, implement an adapter under tests, and review it independently. Core upgrade and extension development must be coordinated separately; this plugin contains no core patch or runtime monkeypatch.
