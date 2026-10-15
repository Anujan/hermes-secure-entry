# Hermes 0.22.1 compatibility repair (plugin 0.2.1)

## Evidence and supported version

Validated against pristine upstream Hermes commit
`046094df28b712f62a5e3c728a9e59da05dcbf1e` (0.22.1), and separately against
the operator's working 0.22.1 core with its independently restored local fixes.
The compatibility manifest is deliberately narrow: `>=0.22.1,<0.22.2`.
No compatibility with earlier or future Hermes releases is newly asserted.

This was not a manifest-only repair:

- The registry now exposes **one `browser_vault` tool**, with actions `list`,
  `unlock`, `enter_code`, `fill`, and `save_login`. Separate registered tool names
  used by plugin 0.2.0 no longer exist. Without adaptation, the old middleware
  silently passes the real calls through without installing prompt callbacks.
- Service admission now maps only `list`, `unlock`, and `enter_code` to the
  existing bridge scopes. Native argument objects are unchanged. `fill`,
  `save_login`, invalid and absent actions remain untouched. Native callbacks,
  approval checks, context propagation, supervisor-only writes, origin/nonce
  fences and takeover checks are not replaced or bypassed.
- Verification-code guidance and tool descriptions now name the actual tool
  and `enter_code` action. Nonempty OTP handles remain refused before native
  execution, even though the current core includes a handle-origin precheck.
- The callback getter/setter signatures, `VaultStore.add_item/get_meta`,
  `PluginContext.register_middleware`, and native thread propagation remain
  compatible. Real encrypted add/readback and registered code/unlock handlers
  are exercised with synthetic inputs and disposable stores.
- Native `send_message_tool` is still the CLI delivery entry, not a registered
  model tool. The new relay egress guard reads the gateway reference; tests
  provide a synthetic native gateway adapter there without importing the
  launcher or bypassing the guard. No real message is sent.
- The idle stop handler now also invokes its holographic owner-turn stop hook.
  The test supplies that collaborator and still executes the actual idle
  handler: it does not emit plugin stop lifecycle cancellation in this case.
  Explicit form/tool cancellation remains required for a delivered idle link.
- Existing fixed-category diagnostic changes are retained: identity/listener
  failures never disclose exception text, credentials, tokens or owner data.

## Verification

The complete 61-test unittest suite passes against both pristine upstream and
the restored working core. The new six-test action-contract suite was run red
before the middleware change (five tests caught missing interception; the
unrelated-action passthrough control already passed); native instruction and
health-version changes were also tested red before implementation. The Windows CI pin now targets the
same upstream commit. Tests resolve their synthetic profile from the test home,
not the operator's default installation.

Hermes Plugin Doctor passes runtime discovery, import and registration with
three tools and three hooks. Catalog validation passes all checks, including
middleware declarations, security scan and no core overrides. It warns about
version-specific/private native imports. Its static `host_ready` classification
is **not** permission to use host isolation: this bridge still requires
`plugins.isolation=in_process`.

Validation intentionally omits `--install-deps`: there are no declared plugin
Python dependencies, and that flag can synchronize the selected live PM
runtime. Tests and host validation use the separate test interpreter. The
existing test dependency graph was sufficient; no live dependency installation
is needed for this plugin repair.

An upstream asyncio event-loop ResourceWarning can appear in the integration
suite; it does not fail the tests. The default-home run also reported an
unreadable unrelated temporary plugin directory and a core version-parser
DeprecationWarning. Clean test-home runs avoid that unrelated discovery.

These results do **not** prove live activation, real Photon delivery, manager
unlock, browser authentication, tailnet HTTPS, or physical Safari/VoiceOver
accessibility. Tab identity/immutable target binding and atomic record updates
remain outside this plugin's supported contract. Gateway session-ID propagation
and native classifier/tab-selection fixes are separate core work; passing
synthetic identity tests does not prove the live gateway uses those fixes.

## Coordinated activation only

Do not replace files while a gateway or another Hermes process can have this
plugin imported. Disabling it alone does not establish unload. The staged
payload is ordinary plugin source, outside the active plugin discovery tree;
it contains no secrets, live vault data, configuration or dependency environment.

After an operator has coordinated shutdown of the gateway and all plugin-using
processes, and confirmed pending forms are cancelled:

1. Verify the payload hashes and rerun doctor with the selected 0.22.1 runtime.
2. Move the old `$HERMES_HOME/plugins/secure-entry` directory to a unique backup
   **outside** `$HERMES_HOME/plugins`. Never delete or move the native vault.
3. Copy the reviewed payload directory to `$HERMES_HOME/plugins/secure-entry`.
   Keep the current plugin settings, Serve route and dependency selection.
4. Run `hermes plugins doctor secure-entry --ci`, then explicitly run
   `hermes plugins enable secure-entry --no-allow-tool-override`.
5. Start the gateway as a separate coordinated operator action. Open a fresh
   Photon conversation and verify owner binding/status/cancel with a synthetic
   request before real credentials. Expect `/health` version `0.2.1` only after
   the authorized lazy listener has started.

No installer, hotcopy, enable/config change or gateway restart is performed by
this compatibility check. Rollback requires the same shutdown discipline,
restoring only the backed-up plugin source and an appropriate compatible Hermes
version; the old 0.2.0 manifest deliberately rejects Hermes 0.22.1.
