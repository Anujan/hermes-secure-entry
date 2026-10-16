"""Real isolated Chrome + real native CapturedCDP. Synthetic route fixtures only."""

import json
import unittest
from playwright.sync_api import sync_playwright
from secure_entry import payment_browser
from tools.browser_supervisor import SUPERVISOR_REGISTRY


class PaymentBrowserTests(unittest.TestCase):
    def setUp(self):
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--enable-automation",
                "--remote-debugging-port=0",
                "--site-per-process",
            ],
        )
        self.addCleanup(self.cleanup)
        self.context = self.browser.new_context()
        self.context.route(
            "https://merchant.test/**",
            lambda r: r.fulfill(
                content_type="text/html",
                body='<iframe src="https://provider.test/pay"></iframe>',
            ),
        )
        self.context.route(
            "https://provider.test/**",
            lambda r: r.fulfill(
                content_type="text/html",
                body='<form><input autocomplete="cc-number"><input autocomplete="cc-exp-month"><input autocomplete="cc-exp-year"><input autocomplete="cc-csc"></form>',
            ),
        )
        self.page = self.context.new_page()
        self.page.goto("https://merchant.test/")
        # Playwright's browser websocket is a pipe. Obtain its CDP endpoint from
        # the isolated browser's command line profile, never a user profile.
        session = self.context.new_cdp_session(self.page)
        argv = self.browser.new_browser_cdp_session().send(
            "Browser.getBrowserCommandLine"
        )["arguments"]
        from pathlib import Path
        import urllib.request

        profile = next(
            a.split("=", 1)[1] for a in argv if a.startswith("--user-data-dir=")
        )
        port = (Path(profile) / "DevToolsActivePort").read_text().splitlines()[0]
        with urllib.request.urlopen("http://127.0.0.1:" + port + "/json/version") as r:
            endpoint = json.load(r)["webSocketDebuggerUrl"]
        SUPERVISOR_REGISTRY.get_or_start("synthetic-payment", endpoint)
        self.capture = SUPERVISOR_REGISTRY.capture("synthetic-payment")
        self.parent = session.send("Target.getTargetInfo")["targetInfo"]["targetId"]
        # OOPIF owner identity, not a frame URL/name chosen by the model.
        root = session.send("DOM.getDocument")["root"]["nodeId"]
        node = session.send(
            "DOM.querySelector", {"nodeId": root, "selector": "iframe"}
        )["nodeId"]
        self.frame = session.send("DOM.describeNode", {"nodeId": node})["node"][
            "frameId"
        ]

    def cleanup(self):
        SUPERVISOR_REGISTRY.stop("synthetic-payment")
        self.browser.close()
        self.pw.stop()

    def _run_facility(
        self, choice="once", before_answer=None, issued_card=None, expected_prompts=1
    ):
        from secure_entry.payment import LocalPayment
        from secure_entry.service import Service
        from gateway.session_context import set_session_vars, clear_session_vars
        from hermes_constants import get_hermes_home, profile_name_for_home
        from tools import approval, browser_tool
        from unittest.mock import patch

        tokens = set_session_vars(
            platform="photon",
            chat_type="dm",
            chat_id="synthetic-chat",
            user_id="synthetic-owner",
            session_key="synthetic-key",
            session_id="synthetic-session",
            profile=profile_name_for_home(get_hermes_home()) or "",
            cron_session="",
        )
        self.addCleanup(clear_session_vars, tokens)
        service = Service("https://example.invalid", str(get_hermes_home()), port=0)
        self.addCleanup(service.close)
        prompts = []

        def notify(data):
            prompts.append(data)
            if before_answer:
                before_answer()
            approval.resolve_gateway_approval(
                "synthetic-key", choice, request_id=data["request_id"]
            )

        approval.register_gateway_notify("synthetic-key", notify)
        self.addCleanup(approval.unregister_gateway_notify, "synthetic-key")
        import sys
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as root:
            script = Path(root) / "synthetic_link.py"
            payload = {
                "spend_request_id": "lsrq_synthetic",
                "merchant_url": "https://merchant.test/pay",
                "card": {
                    "number": "4242424242424242",
                    "cvc": "123",
                    "exp_month": 12,
                    "exp_year": 2030,
                },
            }
            if issued_card is not None:
                payload["card"] = issued_card
            script.write_text(
                "import json,sys,pathlib\na=sys.argv[1:]\npathlib.Path(a[6]).write_text("
                + repr(json.dumps(payload))
                + ')\nprint(json.dumps({"id":"lsrq_synthetic","status":"approved"}))\n'
            )
            facility = LocalPayment(service, [sys.executable, str(script)])
            service.payment = facility
            # Deliberately no legacy session metadata: BrowserUse dispatch does
            # not populate the native task-key cache for every route.
            with patch.dict(browser_tool._active_sessions, {}, clear=True):
                result = json.loads(
                    service.payment_fill(
                        {
                            "parent": self.parent,
                            "frame": self.frame,
                            "merchant_origin": "https://merchant.test",
                            "frame_origin": "https://provider.test",
                            "spend_request_id": "lsrq_synthetic",
                        },
                        task_id="synthetic-payment",
                    )
                )
        self.assertEqual(len(prompts), expected_prompts)
        return result, prompts

    def target_for_html(self, html):
        self.page.frames[1].evaluate("html => document.body.innerHTML=html", html)
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        self.assertTrue(target.attached)
        return target

    def test_binding_refusal_categories_are_safe(self):
        parent, frame = self.parent, self.frame
        for category in ("selected_parent", "frame_lineage", "form_layout"):
            self.parent, self.frame = parent, frame
            if category == "selected_parent":
                self.parent = "missing-private-target"
            elif category == "frame_lineage":
                self.frame = "missing-private-frame"
            else:
                self.page.frames[1].evaluate(
                    'document.body.innerHTML="<div>unsupported</div>"'
                )
            result, _ = self._run_facility(expected_prompts=0)
            self.assertEqual(
                result,
                dict(
                    success=False,
                    status="refused",
                    stage="target_binding",
                    refusal=category,
                    payment_diagnostic_version="0.4.3",
                ),
            )

    def test_formless_cohesive_payment_widget(self):
        target = self.target_for_html(
            '<div><section><input autocomplete="cc-number"></section>'
            '<section><input autocomplete="cc-exp"></section></div>'
        )
        self.assertEqual(
            target.fill(dict(number="4242424242424242", exp_month=12, exp_year=2030))[
                "filled_fields"
            ],
            2,
        )

    def test_formless_unrelated_groups_refused(self):
        for html in [
            '<div><input autocomplete="cc-number"></div><div><input autocomplete="cc-exp"></div>',
            '<div><input autocomplete="cc-number"><input autocomplete="cc-exp"></div><div><input autocomplete="billing postal-code"></div>',
            '<div><input autocomplete="cc-number"><input autocomplete="cc-exp"></div>'
            * 2,
        ]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                self.target_for_html(html)

    def test_formless_retained_container_replacement_refused(self):
        target = self.target_for_html(
            '<div><input autocomplete="cc-number"><input autocomplete="cc-exp"></div>'
        )
        self.page.frames[1].evaluate(
            'document.querySelector("div").outerHTML=document.querySelector("div").outerHTML'
        )
        with self.assertRaises(ValueError):
            target.check()

    def test_combined_expiry_without_merchant_cvc(self):
        target = self.target_for_html(
            '<form><input autocomplete="cc-number"><input autocomplete="cc-exp"></form>'
        )
        result = target.fill(
            dict(number="4242424242424242", exp_month=12, exp_year=2030, cvc="123")
        )
        self.assertEqual(result, dict(success=True, status="filled", filled_fields=2))
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-exp]").input_value(), "12/30"
        )

    def test_formless_billing_selects_react_tracker(self):
        self.test_billing_selects_prefilled_and_react_property_tracker(formless=True)

    def test_billing_selects_prefilled_and_react_property_tracker(self, formless=False):
        html = """<form><input autocomplete="cc-number"><input autocomplete="cc-exp">
        <input autocomplete="cc-name"><select autocomplete="billing country"><option value="US" selected>United States</option></select>
        <input autocomplete="billing address-line1"><input autocomplete="billing address-line2">
        <input autocomplete="billing address-level2"><select autocomplete="billing address-level1"><option value="NY" selected>New York</option></select>
        <input autocomplete="billing postal-code"><input autocomplete="billing tel" value="2125550100"></form>"""
        if formless:
            html = html.replace("<form>", "<div>").replace("</form>", "</div>")
        self.page.frames[1].evaluate("html => document.body.innerHTML=html", html)
        self.page.frames[
            1
        ].evaluate("""() => {window.updates=0; for(const e of document.querySelectorAll('input')) {
          let tracked=e.value; Object.defineProperty(e,'value',{get(){return Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').get.call(this)},set(v){tracked=v;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(this,v)}});
          e.addEventListener('input',()=>{if(e.value!==tracked){window.updates++;tracked=e.value}});
        }}""")
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        result = target.fill(
            dict(
                number="4242424242424242",
                exp_month=12,
                exp_year=2030,
                billing_address=dict(
                    name="Synthetic Person",
                    country="US",
                    line1="1 Test St",
                    line2="",
                    city="Test City",
                    state="NY",
                    postal_code="10001",
                ),
            )
        )
        self.assertEqual(result, dict(success=True, status="filled", filled_fields=6))
        self.assertEqual(self.page.frames[1].evaluate("window.updates"), 6)
        self.assertNotIn("Synthetic", json.dumps(result))

    def test_benign_validation_attributes_and_pan_grouping(self):
        self.page.frames[
            1
        ].evaluate("""() => document.querySelector('input').addEventListener('input',e=>{
          e.target.setAttribute('aria-invalid','false');
          e.target.value=e.target.value.replace(/(.{4})(?=.)/g,'$1 ');
        })""")
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        self.assertEqual(
            target.fill(
                dict(number="4242424242424242", exp_month=12, exp_year=2030, cvc="123")
            )["filled_fields"],
            4,
        )

    def test_ambiguous_and_unrelated_controls_refused(self):
        base = '<input autocomplete="cc-number"><input autocomplete="cc-exp">'
        for extra in [
            '<input autocomplete="cc-number">',
            '<input autocomplete="cc-exp-month">',
            '<input autocomplete="email">',
            '<select autocomplete="shipping country"></select>',
            '<input autocomplete="billing postal-code"><input autocomplete="billing postal-code">',
        ]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.target_for_html("<form>" + base + extra + "</form>")

    def test_mismatching_prefilled_billing_refuses_before_any_write(self):
        target = self.target_for_html(
            '<form><input autocomplete="cc-number"><input autocomplete="cc-exp"><input autocomplete="billing postal-code" value="99999"></form>'
        )
        with self.assertRaises(ValueError):
            target.fill(
                dict(
                    number="4242424242424242",
                    exp_month=12,
                    exp_year=2030,
                    billing_address=dict(postal_code="10001"),
                )
            )
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(), ""
        )

    def test_value_only_event_tampering_of_later_target_refused(self):
        self.page.frames[1].evaluate(
            """() => document.querySelector('input').addEventListener('input',()=>document.querySelector('[autocomplete=cc-exp-year]').value='attacker')"""
        )
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        with self.assertRaises(ValueError):
            target.fill(
                dict(number="4242424242424242", exp_month=12, exp_year=2030, cvc="123")
            )
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-exp-month]").input_value(), ""
        )

    def test_parent_mutation_at_dispatch_is_unknown_not_atomic_no_write(self):
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        real = target.invoke

        def invoke(sid, obj, function, args=()):
            if "this.write" in function:
                self.page.evaluate("document.querySelector('iframe').title='changed'")
            return real(sid, obj, function, args)

        target.invoke = invoke
        with self.assertRaises(ValueError):
            target.fill(
                dict(number="4242424242424242", exp_month=12, exp_year=2030, cvc="123")
            )
        self.assertTrue(target.started)
        # CDP cannot atomically check parent JS and write another OOPIF process.
        # This explicitly records the limitation, not a no-disclosure guarantee.
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(),
            "4242424242424242",
        )

    def test_last_event_tampering_of_prior_target_refused(self):
        self.page.frames[1].evaluate(
            """() => document.querySelector('[autocomplete=cc-csc]').addEventListener('change',()=>document.querySelector('[autocomplete=cc-number]').value='9999')"""
        )
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        with self.assertRaises(ValueError):
            target.fill(
                dict(number="4242424242424242", exp_month=12, exp_year=2030, cvc="123")
            )

    def test_native_issued_billing_redacted_individually_before_fill(self):
        from agent.redact import redact_registered_vault_values

        self.page.frames[1].evaluate(
            """() => document.body.innerHTML='<form><input autocomplete="cc-number"><input autocomplete="cc-exp"><input autocomplete="cc-name"><input autocomplete="billing address-line1"></form>' """
        )
        card = dict(
            number="4242424242424242",
            exp_month=12,
            exp_year=2030,
            billing_address=dict(
                name="Unique Synthetic Cardholder",
                line1="1 Private Synthetic Street",
                country="US",
            ),
        )
        result, _ = self._run_facility(issued_card=card)
        self.assertEqual(
            result,
            dict(
                success=True,
                status="filled",
                filled_fields=4,
                payment_diagnostic_version="0.4.3",
            ),
        )
        self.assertNotIn(
            "Unique Synthetic Cardholder",
            redact_registered_vault_values("Unique Synthetic Cardholder"),
        )
        self.assertNotIn(
            "1 Private Synthetic Street",
            redact_registered_vault_values("1 Private Synthetic Street"),
        )
        self.assertNotIn("12/30", redact_registered_vault_values("12/30"))

    def test_matching_prefilled_cardholder_is_preserved(self):
        target = self.target_for_html(
            '<form><input autocomplete="cc-number"><input autocomplete="cc-exp"><input autocomplete="cc-name" value="Synthetic Person"></form>'
        )
        self.assertEqual(
            target.fill(
                dict(
                    number="4242424242424242",
                    exp_month=12,
                    exp_year=2030,
                    billing_address=dict(name="Synthetic Person"),
                )
            )["filled_fields"],
            2,
        )

    def test_empty_billing_selects_use_native_change_events(self):
        target = self.target_for_html(
            '<form><input autocomplete="cc-number"><input autocomplete="cc-exp"><select autocomplete="billing country"><option value=""></option><option value="US">United States</option></select><select autocomplete="billing address-level1"><option value=""></option><option value="NY">New York</option></select></form>'
        )
        self.page.frames[1].evaluate(
            "window.changes=0;document.querySelectorAll('select').forEach(e=>e.addEventListener('change',()=>window.changes++))"
        )
        result = target.fill(
            dict(
                number="4242424242424242",
                exp_month=12,
                exp_year=2030,
                billing_address=dict(country="US", state="NY"),
            )
        )
        self.assertEqual(result["filled_fields"], 4)
        self.assertEqual(self.page.frames[1].evaluate("window.changes"), 2)

    def test_invalid_pan_mask_content_refused(self):
        self.page.frames[1].evaluate(
            "document.querySelector('input').addEventListener('input',e=>e.target.value+='x')"
        )
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        with self.assertRaises(ValueError):
            target.fill(
                dict(number="4242424242424242", exp_month=12, exp_year=2030, cvc="123")
            )
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-exp-month]").input_value(), ""
        )

    def _dispatched_browseruse_fill(self, session="", hybrid=False, nonprimary=False):
        """Real harness process + native attach/capture; only browser provisioning
        is replaced with this test's already-launched disposable Chrome endpoint.
        No generated receipt, plugin authority, live browser or live IPC runtime.
        """
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from tools import browser_use_cli as bu

        endpoint = self.capture.cdp_url
        SUPERVISOR_REGISTRY.stop("synthetic-payment")
        self.assertFalse(self.capture.is_valid())
        with tempfile.TemporaryDirectory() as directory:
            base = bu._base_subprocess_env()
            for key in list(base):
                if key.startswith(("BU_", "BH_", "BROWSER_")):
                    del base[key]
            base.update(
                BH_HOME=str(Path(directory) / "home"),
                BH_RUNTIME_DIR=str(Path(directory) / "runtime"),
                BH_RUNTIME_DIR_SHARED="1",
                BU_AUTOSPAWN="0",
            )

            def provision(env, task_id, session_name="", sidecar=False):
                self.assertEqual(sidecar, hybrid)
                bu._set_cdp_env(env, endpoint)
                env[bu._PRIVATE_BROWSER_SENTINEL] = "1"
                env[bu._BOT_DESKTOP_BROWSER_SENTINEL] = "1"
                return None

            with (
                patch.object(bu, "_base_subprocess_env", return_value=base.copy()),
                patch.object(bu, "_real_profile_consented", return_value=False),
                patch.object(bu, "_resolve_local_engine_cdp", side_effect=provision),
                patch("tools.browser_tool_cdp._get_cdp_override", return_value=""),
                patch("tools.browser_tool_cdp._get_cdp_override_raw", return_value=""),
                patch(
                    "tools.browser_tool_cloud._get_cloud_provider",
                    return_value=object() if hybrid else None,
                ),
                patch(
                    "tools.browser_tool_cloud._auto_local_for_private_urls",
                    return_value=True,
                ),
                patch.object(bu, "_read_browser_cfg", return_value={}),
            ):
                try:
                    # A private URL literal selects the genuine hybrid predicate;
                    # the code reads fixture metadata only, never field values.
                    code = '# http://127.0.0.1/fixture\nprint("fixture-dispatched", cdp("Browser.getVersion")["product"])'
                    result = bu.browser_exec(
                        code, session=session, task_id="synthetic-payment", timeout_s=45
                    )
                    if isinstance(result, str):
                        result = json.loads(result)
                    self.assertTrue(result.get("success"), result)
                    self.assertIn("fixture-dispatched", result["output"])
                    self.assertEqual(
                        bu._exec_route_is_sidecar[
                            bu._backend_cache_key("synthetic-payment", session)
                        ],
                        hybrid,
                    )
                    capture = SUPERVISOR_REGISTRY.capture("synthetic-payment")
                    self.assertTrue(capture.is_valid())
                    self.assertEqual(capture.cdp_url, endpoint)
                    self.capture = capture
                    if nonprimary:
                        original = self.page
                        self.page = self.context.new_page()
                        self.page.goto("https://merchant.test/second")
                        page_session = self.context.new_cdp_session(self.page)
                        self.parent = page_session.send("Target.getTargetInfo")[
                            "targetInfo"
                        ]["targetId"]
                        root = page_session.send("DOM.getDocument")["root"]["nodeId"]
                        node = page_session.send(
                            "DOM.querySelector", {"nodeId": root, "selector": "iframe"}
                        )["nodeId"]
                        self.frame = page_session.send(
                            "DOM.describeNode", {"nodeId": node}
                        )["node"]["frameId"]
                        selected = bu.browser_exec(
                            "switch_tab("
                            + repr(self.parent)
                            + ')\nprint(current_tab()["targetId"])',
                            session=session,
                            task_id="synthetic-payment",
                            timeout_s=45,
                        )
                        if isinstance(selected, str):
                            selected = json.loads(selected)
                        self.assertTrue(selected.get("success"), selected)
                        self.assertIn(self.parent, selected["output"])
                        default = capture.call(
                            "Target.getTargetInfo", session_id=capture.page_session_id
                        )["result"]["targetInfo"]["targetId"]
                        self.assertNotEqual(default, self.parent)
                    filled, _ = self._run_facility()
                    self.assertTrue(filled["success"], filled)
                    if nonprimary:
                        self.assertEqual(
                            original.frames[1]
                            .locator("[autocomplete=cc-number]")
                            .input_value(),
                            "",
                        )
                        self.assertEqual(
                            self.page.frames[1]
                            .locator("[autocomplete=cc-number]")
                            .input_value(),
                            "4242424242424242",
                        )
                finally:
                    import time

                    # Native best-effort cleanup can return before Windows closes
                    # the daemon log handle. Exercise reload directly and wait
                    # for the exact disposable runtime to release its files.
                    name = (
                        bu._sidecar_daemon_name(session)
                        if hybrid
                        else (session or "default")
                    )
                    import psutil

                    # Keep an identity-checked handle to this test's daemon.
                    # Harness reload has a Windows port-file deletion race;
                    # cleanup must not leave a disposable process/log handle.
                    pidfile = Path(directory) / "runtime" / f"bu-{name}.pid"
                    daemon = None
                    if pidfile.exists():
                        record = json.loads(pidfile.read_text())
                        daemon = psutil.Process(
                            int(record["pid"] if isinstance(record, dict) else record)
                        )
                        self.assertEqual(
                            daemon.cmdline()[1:3], ["-m", "browser_harness.daemon"]
                        )
                    bu._run_cli_killing_process_group(
                        [*bu._find_cli(), "--reload"], "", {**base, "BU_NAME": name}, 20
                    )
                    if daemon is not None:
                        try:
                            daemon.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            daemon.terminate()
                            daemon.wait(timeout=10)
                    for _ in range(100):
                        try:
                            for logfile in (Path(directory) / "home" / "tmp").glob(
                                "*.log"
                            ):
                                logfile.unlink()
                            break
                        except PermissionError:
                            time.sleep(0.1)
                    bu._driven_daemons.discard(name)

    def test_nonprimary_attachment_cleanup_and_wrong_frame_lineage(self):
        other = self.context.new_page()
        other.goto("https://merchant.test/other")
        session = self.context.new_cdp_session(other)
        parent = session.send("Target.getTargetInfo")["targetInfo"]["targetId"]
        with self.assertRaises(payment_browser.BindingRefused) as caught:
            payment_browser.Target(
                self.capture,
                parent,
                self.frame,
                "https://merchant.test",
                "https://provider.test",
                lambda: None,
            )
        self.assertEqual(caught.exception.category, "frame_lineage")
        root = session.send("DOM.getDocument")["root"]["nodeId"]
        node = session.send(
            "DOM.querySelector", {"nodeId": root, "selector": "iframe"}
        )["nodeId"]
        frame = session.send("DOM.describeNode", {"nodeId": node})["node"]["frameId"]
        target = payment_browser.Target(
            self.capture,
            parent,
            frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.assertTrue(target.parent_attached)
        sessions = (target.psid, target.csid)
        target.close()
        for sid in sessions:
            with self.assertRaises(RuntimeError):
                self.capture.call("Target.getTargetInfo", session_id=sid)
        self.assertEqual(
            self.capture.call(
                "Target.getTargetInfo", session_id=self.capture.page_session_id
            )["result"]["targetInfo"]["targetId"],
            self.parent,
        )

    def test_nonprimary_browseruse_selected_exact_parent(self):
        self._dispatched_browseruse_fill(session="synthetic-multitab", nonprimary=True)

    def test_default_browseruse_dispatch_to_existing_public_capture_fill(self):
        self._dispatched_browseruse_fill()

    def test_named_browseruse_dispatch_to_existing_public_capture_fill(self):
        self._dispatched_browseruse_fill(session="synthetic-checkout")

    def test_hybrid_browseruse_dispatch_to_existing_public_capture_fill(self):
        self._dispatched_browseruse_fill(session="synthetic-hybrid", hybrid=True)

    def test_registered_facility_native_consent_private_file_to_real_iframe(self):
        from agent.redact import redact_registered_vault_values

        result, prompts = self._run_facility()
        self.assertEqual(
            result,
            {
                "success": True,
                "status": "filled",
                "filled_fields": 4,
                "payment_diagnostic_version": "0.4.3",
            },
        )
        self.assertIn("https://merchant.test", prompts[0]["command"])
        self.assertIn("https://provider.test", prompts[0]["command"])
        self.assertNotIn(
            "4242424242424242", redact_registered_vault_values("4242424242424242")
        )
        self.assertNotIn("123", redact_registered_vault_values("123"))
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(),
            "4242424242424242",
        )

    def test_takeover_after_write_reports_unknown_not_nothing_written(self):
        from unittest.mock import patch
        from tools.bot_desktop import lease

        original = payment_browser.Target.fill

        def takeover(target, card):
            result = original(target, card)
            lease.acquire("synthetic-viewer")
            return result

        self.addCleanup(lease.release, "synthetic-viewer")
        with patch.object(payment_browser.Target, "fill", takeover):
            result, _ = self._run_facility()
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "write_unknown")

    def test_supervisor_replacement_during_consent_refuses_before_retrieval(self):
        endpoint = self.capture.cdp_url

        def replace():
            SUPERVISOR_REGISTRY.stop("synthetic-payment")
            SUPERVISOR_REGISTRY.get_or_start("synthetic-payment", endpoint)

        result, _ = self._run_facility(before_answer=replace)
        self.assertFalse(result["success"])
        self.assertEqual(result["stage"], "native_consent")
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(), ""
        )

    def test_native_takeover_during_consent_refuses_before_retrieval(self):
        from tools.bot_desktop import lease

        self.addCleanup(lease.release, "synthetic-viewer")
        result, _ = self._run_facility(
            before_answer=lambda: lease.acquire("synthetic-viewer")
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["stage"], "native_consent")
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(), ""
        )

    def test_supervisor_replacement_after_write_reports_unknown(self):
        from unittest.mock import patch

        original = payment_browser.Target.fill
        endpoint = self.capture.cdp_url

        def replace(target, card):
            result = original(target, card)
            SUPERVISOR_REGISTRY.stop("synthetic-payment")
            SUPERVISOR_REGISTRY.get_or_start("synthetic-payment", endpoint)
            return result

        with patch.object(payment_browser.Target, "fill", replace):
            result, _ = self._run_facility()
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "write_unknown")
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(),
            "4242424242424242",
        )

    def test_native_decline_keeps_card_fields_empty(self):
        result, _ = self._run_facility("deny")
        self.assertEqual(
            result,
            {
                "success": False,
                "status": "payment_declined",
                "payment_diagnostic_version": "0.4.3",
            },
        )
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(), ""
        )

    def test_navigation_while_native_consent_waits_refuses_before_retrieval(self):
        result, _ = self._run_facility(
            before_answer=lambda: self.page.frames[1].goto(
                "https://provider.test/reload"
            )
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["stage"], "native_consent")
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(), ""
        )

    def test_same_origin_reload_never_retargets_new_document(self):
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        self.page.frames[1].goto("https://provider.test/reloaded")
        with self.assertRaises(Exception):
            target.fill(
                {
                    "number": "4242424242424242",
                    "cvc": "123",
                    "exp_month": 12,
                    "exp_year": 2030,
                }
            )
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(), ""
        )

    def test_reverted_parent_mutation_is_sticky_refusal(self):
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        self.page.evaluate(
            "document.querySelector('iframe').setAttribute('title','changed');document.querySelector('iframe').removeAttribute('title')"
        )
        with self.assertRaises(ValueError):
            target.check()
        self.assertFalse(target.started)

    def test_child_input_event_replacement_stops_remaining_writes(self):
        self.page.frames[1].evaluate(
            "document.querySelector('input').addEventListener('input',()=>document.querySelector('[autocomplete=cc-csc]').replaceWith(document.createElement('input')))"
        )
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        with self.assertRaises(ValueError):
            target.fill(
                {
                    "number": "4242424242424242",
                    "cvc": "123",
                    "exp_month": 12,
                    "exp_year": 2030,
                }
            )
        self.assertTrue(target.started)
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-exp-month]").input_value(), ""
        )

    def test_parent_navigation_after_last_preflight_before_secret_send(self):
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        real = target.invoke

        def invoke(sid, obj, function, args=()):
            if "this.write" in function:
                self.page.goto("https://merchant.test/reloaded")
            return real(sid, obj, function, args)

        target.invoke = invoke
        with self.assertRaises(Exception):
            target.fill(
                {
                    "number": "4242424242424242",
                    "cvc": "123",
                    "exp_month": 12,
                    "exp_year": 2030,
                }
            )
        self.assertEqual(
            self.page.frames[1].locator("[autocomplete=cc-number]").input_value(), ""
        )

    def test_reconnect_invalidates_original_transport(self):
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        self.addCleanup(target.close)
        endpoint = self.capture.cdp_url
        SUPERVISOR_REGISTRY.stop("synthetic-payment")
        SUPERVISOR_REGISTRY.get_or_start("synthetic-payment", endpoint)
        with self.assertRaises(ValueError):
            target.check()
        self.assertFalse(target.started)

    def test_wrong_parent_or_provider_refused(self):
        for parent, provider in (
            ("unrelated-target", "https://provider.test"),
            (self.parent, "https://wrong.test"),
        ):
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                payment_browser.Target(
                    self.capture,
                    parent,
                    self.frame,
                    "https://merchant.test",
                    provider,
                    lambda: None,
                )

    def test_cleanup_releases_untracked_remote_objects_after_lost_reply(self):
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        sid, obj = target.psid, target.pg
        target.objects.clear()  # simulate successful creation with a lost reply
        target.close()
        with self.assertRaises(RuntimeError):
            self.capture.call(
                "Runtime.callFunctionOn",
                {
                    "objectId": obj,
                    "functionDeclaration": "function(){return true;}",
                    "returnByValue": True,
                },
                session_id=sid,
            )

    def test_actual_cross_origin_fill_and_metadata_only(self):
        target = payment_browser.Target(
            self.capture,
            self.parent,
            self.frame,
            "https://merchant.test",
            "https://provider.test",
            lambda: None,
        )
        try:
            self.assertTrue(
                target.attached,
                "fixture must exercise real cross-process iframe attachment",
            )
            result = target.fill(
                {
                    "number": "4242424242424242",
                    "cvc": "123",
                    "exp_month": 12,
                    "exp_year": 2030,
                }
            )
            self.assertEqual(
                result, {"success": True, "status": "filled", "filled_fields": 4}
            )
            self.assertEqual(
                self.page.frames[1].locator("[autocomplete=cc-number]").input_value(),
                "4242424242424242",
            )
            self.assertNotIn("424242", json.dumps(result))
        finally:
            target.close()


if __name__ == "__main__":
    unittest.main()
