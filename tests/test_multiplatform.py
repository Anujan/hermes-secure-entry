"""The full callback/lifecycle contract runs for each explicitly supported DM.

Native send integration uses a BasePlatformAdapter on a synthetic gateway loop;
no transport authorization, target resolver, or egress function is bypassed.
"""
import test_bridge as bridge_tests


class BotRelayChecks:
    def test_relay_egress_decline_revokes_link_without_transport_send(self):
        self.check_relay_egress_decline_revokes_link_without_transport_send()


class DiscordDMTests(BotRelayChecks, bridge_tests.BridgeTests):
    platform = 'discord'
    user_id = '223456789012345678'
    chat_id = '123456789012345678'


class TelegramDMTests(BotRelayChecks, bridge_tests.BridgeTests):
    platform = 'telegram'
    user_id = '123456789'
    chat_id = '123456789'
