from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from selenium.common.exceptions import TimeoutException

from bots.google_meet_bot_adapter.google_meet_ui_methods import GoogleMeetUIMethods


class EnableCaptionsViaKeyboardShortcutTestCase(SimpleTestCase):
    """The 'Captions and translation' variant: 'c' is a toggle, so it must be pressed at most once."""

    def setUp(self):
        self.ui = GoogleMeetUIMethods.__new__(GoogleMeetUIMethods)
        self.ui.driver = MagicMock()

    def _button(self, pressed):
        button = MagicMock()
        button.get_attribute.return_value = pressed
        return button

    def test_already_enabled_does_not_press_c(self):
        with patch("bots.google_meet_bot_adapter.google_meet_ui_methods.ActionChains") as mock_chains:
            self.ui.enable_captions_via_keyboard_shortcut(self._button("true"))
        mock_chains.assert_not_called()

    def test_unconfirmed_enable_returns_instead_of_raising(self):
        # A raised TimeoutException would send click_captions_button round its loop to press 'c' again.
        with patch("bots.google_meet_bot_adapter.google_meet_ui_methods.ActionChains") as mock_chains, patch("bots.google_meet_bot_adapter.google_meet_ui_methods.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.side_effect = TimeoutException()
            self.ui.enable_captions_via_keyboard_shortcut(self._button("false"))
        mock_chains.return_value.send_keys.assert_called_once_with("c")
