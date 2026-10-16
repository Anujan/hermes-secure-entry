"""Native local Link CLI payment source; no vault persistence or purchase submit.

The only exported handler is registered with PluginContext, not a generic secret
script executor. Authenticated owner admission, native vault-payment consent,
retained CapturedCDP, native takeover fences, private inbox and redaction compose
one synchronous operation. Real Link authorization remains independently required.
"""

import json
import re
import time
from pathlib import Path
from .native import owner, validate_origin
from .payment_file import PrivateCard
from .payment_browser import Target


def retrieve_card(command, request_id, output):
    """Trusted operator-configured CLI prefix; no shell, spend creation or approval.

    Link itself must have approved this exact request. Its full private artifact
    is never stdout, model args, logs or vault storage. The metadata stdout is
    parsed privately, validated and discarded, never forwarded on any failure.
    """
    import subprocess

    try:
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(p, str) and p for p in command)
            or not Path(command[0]).is_absolute()
            or Path(command[0]).suffix.lower() in (".bat", ".cmd")
        ):
            raise ValueError("link_retrieval_refused")
        result = subprocess.run(
            [
                *command,
                "spend-request",
                "retrieve",
                request_id,
                "--include",
                "card",
                "--output-file",
                str(output),
                "--format",
                "json",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=40,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode or len(result.stdout) > 65536:
            raise ValueError("link_retrieval_refused")
        metadata = json.loads(result.stdout)
        # Link CLI 0.27.4 streams retrieve results as a JSON array. Require
        # exactly one result; never select an approved row from ambiguous output.
        if isinstance(metadata, list):
            if len(metadata) != 1:
                raise ValueError("link_retrieval_refused")
            metadata = metadata[0]
        if (
            not isinstance(metadata, dict)
            or metadata.get("id") != request_id
            or metadata.get("status") != "approved"
        ):
            raise ValueError("link_retrieval_refused")
    except Exception:
        raise ValueError("link_retrieval_refused") from None


class LocalPayment:
    def __init__(self, service, command, *, retrieve=None):
        self.service, self.command, self.retrieve = (
            service,
            command,
            retrieve or retrieve_card,
        )

    def fill(self, args, **kwargs):
        target, card = None, None
        stage = "admission"
        try:
            from hermes_cli.plugin_isolation import isolation_mode
            from tools.browser_supervisor import SUPERVISOR_REGISTRY
            from tools.bot_desktop import lease
            from tools.interrupt import is_interrupted
            from tools.approval_prompt import request_elicitation_consent
            from agent.redact import register_vault_redaction_value

            if (
                isolation_mode() != "in_process"
                or not self.command
                or self.retrieve is None
            ):
                raise ValueError("facility_unavailable")
            with self.service.lock:
                if self.service.closed:
                    raise ValueError("operation_cancelled")
                generation = self.service.generation
            bound = owner(self.service.home)
            merchant = validate_origin(args["merchant_origin"])
            provider = validate_origin(args["frame_origin"])
            rid = args["spend_request_id"]
            if not isinstance(rid, str) or not re.fullmatch(
                r"lsrq_[A-Za-z0-9_]{1,100}", rid
            ):
                raise ValueError("invalid_request")
            task = kwargs.get("task_id")
            if not isinstance(task, str) or not task:
                raise ValueError("missing_task")
            deadline = time.monotonic() + 180
            # Route metadata is not secret authority. Public native capture below
            # pins the task's existing socket; Target binds the exact documents.
            # Fence ALL routes conservatively, including unknown/named/cloud CDP,
            # rather than infer desktop provenance from a legacy session cache.
            admitted = lease.assert_agent_may_act(str(self.service.home))
            capture = None

            # Synchronous native lease/lifecycle checks on the supervisor loop
            # immediately before dispatch. No capture, owner lookup or CDP here.
            def guard():
                if (
                    self.service.closed
                    or self.service.generation != generation
                    or time.monotonic() >= deadline
                    or is_interrupted()
                ):
                    raise ValueError("operation_cancelled")
                if (
                    lease.assert_agent_may_act(str(self.service.home)).epoch
                    != admitted.epoch
                ):
                    raise ValueError("takeover_refused")
                if capture is not None and not capture.is_valid():
                    raise ValueError("browser_capture_invalid")

            def current():
                guard()
                if owner(self.service.home) != bound:
                    raise ValueError("owner_changed")

            def operation():
                nonlocal target, card, stage, capture
                current()
                capture = SUPERVISOR_REGISTRY.capture(task)
                current()
                stage = "target_binding"
                target = Target(
                    capture, args["parent"], args["frame"], merchant, provider, guard
                )
                stage = "native_consent"
                # Genuine existing native surface; no approval callbacks installed
                # or forged. Photon/gateway notification belongs to the host.
                verdict = request_elicitation_consent(
                    f"Fill Link payment on merchant {merchant}; payment frame {provider}; request {rid}",
                    "Enter the approved one-time Link card into this exact checkout document. "
                    "This does not submit or purchase. No card is saved in the vault.",
                    surface="vault-payment",
                    title="Confirm local Link card fill?",
                )
                if verdict != "accept":
                    return {"success": False, "status": "payment_declined"}
                current()
                target.check()
                stage = "link_retrieval"
                root = Path(self.service.home) / "cache"
                root.mkdir(parents=True, exist_ok=True)
                with PrivateCard(root) as inbox:
                    self.retrieve(self.command, rid, inbox.path)
                    current()
                    target.check()
                    stage = "private_file"
                    card = inbox.consume(rid, merchant)
                    for value in [
                        *card.values(),
                        *card.get("billing_address", {}).values(),
                        f"{card['exp_month']:02d}/{card['exp_year'] % 100:02d}",
                    ]:
                        if isinstance(value, (str, int)) and str(value):
                            register_vault_redaction_value(str(value))
                    # Cover common formatting if a subsequent browser read echoes
                    # a number with spaces/dashes, not just its original digits.
                    number = card["number"]
                    for sep in (" ", "-"):
                        register_vault_redaction_value(
                            sep.join(
                                number[i : i + 4] for i in range(0, len(number), 4)
                            )
                        )
                    current()
                    stage = "write"
                    return target.fill(card)

            result = operation()
            current()
            return json.dumps(result)
        except Exception:
            return json.dumps(
                {
                    "success": False,
                    "status": "write_unknown"
                    if target and target.started
                    else "refused",
                    "stage": stage,
                }
            )
        finally:
            if card is not None:
                card.clear()
            if target is not None:
                target.close()
