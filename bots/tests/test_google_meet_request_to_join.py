from unittest.mock import MagicMock

from django.test import SimpleTestCase
from selenium.common.exceptions import NoSuchElementException

from bots.google_meet_bot_adapter.google_meet_ui_methods import GoogleMeetUIMethods
from bots.web_bot_adapter.ui_methods import UiRequestToJoinDeniedException

NO_ONE_RESPONDED = "No one responded to your request to join the call"
DENIED = "Someone in the call denied your request to join"


class RequestToJoinTestCase(SimpleTestCase):
    """Nov 2026: Meet expires an unanswered knock after a few minutes, and the bot gave up for good instead of asking again."""

    def setUp(self):
        self.ui = GoogleMeetUIMethods.__new__(GoogleMeetUIMethods)
        self.ui.driver = MagicMock()
        self.ask_to_join = MagicMock()

    def _screen(self, message, ask_to_join_button=True):
        notice = MagicMock(text=message)

        def find_element(_by, selector):
            if "your request to join" in selector:
                return notice
            if "Ask to join" in selector and ask_to_join_button:
                return self.ask_to_join
            raise NoSuchElementException()

        self.ui.driver.find_element.side_effect = find_element

    def test_unanswered_knock_asks_again(self):
        self._screen(NO_ONE_RESPONDED)
        self.ui.look_for_denied_your_request_element("click_captions_button")
        self.ask_to_join.click.assert_called_once()

    def test_unanswered_knock_with_no_button_gives_up(self):
        self._screen(NO_ONE_RESPONDED, ask_to_join_button=False)
        with self.assertRaises(UiRequestToJoinDeniedException):
            self.ui.look_for_denied_your_request_element("click_captions_button")

    def test_a_refusal_is_never_retried(self):
        self._screen(DENIED)
        with self.assertRaises(UiRequestToJoinDeniedException):
            self.ui.look_for_denied_your_request_element("click_captions_button")
        self.ask_to_join.click.assert_not_called()
