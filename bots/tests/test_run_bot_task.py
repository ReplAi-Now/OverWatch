import signal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from accounts.models import Organization
from bots.models import Bot, BotStates, Project
from bots.tasks.run_bot_task import kill_orphaned_xvfb_processes, run_bot


class RunBotTaskGuardTestCase(TestCase):
    """Issue #587: a redelivered run_bot task must not run a bot that already finished."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Test Org")
        self.project = Project.objects.create(organization=self.organization, name="Test Project")
        self.bot = Bot.objects.create(project=self.project, name="Test Bot", meeting_url="https://meet.google.com/abc-defg-hij", state=BotStates.READY)

    def _run_task(self):
        with patch("bots.tasks.run_bot_task.BotController") as mock_controller, patch("bots.tasks.run_bot_task.kill_orphaned_xvfb_processes"):
            run_bot.apply(args=[self.bot.id])
        return mock_controller

    def test_skips_bot_in_post_meeting_state(self):
        for state in BotStates.post_meeting_states():
            Bot.objects.filter(pk=self.bot.pk).update(state=state)
            mock_controller = self._run_task()
            mock_controller.assert_not_called()

    def test_runs_bot_not_in_post_meeting_state(self):
        Bot.objects.filter(pk=self.bot.pk).update(state=BotStates.READY)
        mock_controller = self._run_task()
        mock_controller.assert_called_once_with(self.bot.id)
        mock_controller.return_value.run.assert_called_once()


class KillOrphanedXvfbTestCase(TestCase):
    """Nov 2026: Xvfb from finished bots outlived their celery child and exhausted the worker."""

    PS_OUTPUT = "    1     0 tini\n  200     1 Xvfb\n  300   250 Xvfb\n  400     1 chrome_crashpad\n  500     1 Xvfb\n"

    def test_kills_only_xvfb_reparented_to_pid_1(self):
        with patch("bots.tasks.run_bot_task.subprocess.run", return_value=MagicMock(stdout=self.PS_OUTPUT)), patch("bots.tasks.run_bot_task.os.kill") as mock_kill:
            kill_orphaned_xvfb_processes()
        self.assertEqual(sorted(call.args for call in mock_kill.call_args_list), [(200, signal.SIGKILL), (500, signal.SIGKILL)])

    def test_ps_failure_does_not_raise(self):
        with patch("bots.tasks.run_bot_task.subprocess.run", side_effect=FileNotFoundError("ps")), patch("bots.tasks.run_bot_task.os.kill") as mock_kill:
            kill_orphaned_xvfb_processes()
        mock_kill.assert_not_called()
