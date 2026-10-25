import time
from unittest.mock import MagicMock, patch

from django.test import TestCase

from accounts.models import Organization
from attendee.celery import app as celery_app
from bots.bot_controller.bot_controller import BotController
from bots.models import Bot, BotStates, Project
from bots.tasks.run_bot_task import run_bot


class RunBotTaskGuardTestCase(TestCase):
    """Issue #587: a redelivered run_bot task must not run a bot that already finished."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Test Org")
        self.project = Project.objects.create(organization=self.organization, name="Test Project")
        self.bot = Bot.objects.create(project=self.project, name="Test Bot", meeting_url="https://meet.google.com/abc-defg-hij", state=BotStates.READY)

    def _run_task(self):
        with patch("bots.tasks.run_bot_task.BotController") as mock_controller:
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


class RunBotTaskTimeLimitTestCase(TestCase):
    """Oct 22-24 2026: run_bot tasks that never returned held every worker slot for two days."""

    def test_the_task_has_a_hard_time_limit(self):
        self.assertIsNotNone(run_bot.time_limit)

    def test_the_soft_limit_comes_before_the_hard_limit(self):
        self.assertLess(run_bot.soft_time_limit, run_bot.time_limit)

    def test_the_hard_limit_ends_the_task_before_the_broker_would_redeliver_it(self):
        self.assertLess(run_bot.time_limit, celery_app.conf.broker_transport_options["visibility_timeout"])


class BotControllerEndedElsewhereTestCase(TestCase):
    """A run_bot loop must shut down once its bot has finished, whichever run finished it."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Test Org")
        self.project = Project.objects.create(organization=self.organization, name="Test Project")
        self.bot = Bot.objects.create(project=self.project, name="Test Bot", meeting_url="https://meet.google.com/abc-defg-hij", state=BotStates.JOINED_RECORDING)

    def _controller(self):
        # Only the attributes the checks touch; a real BotController would launch a browser.
        controller = MagicMock()
        controller.bot_in_db = Bot.objects.get(pk=self.bot.pk)
        controller.cleanup_called = False
        controller.first_timeout_call = False
        controller.last_ended_in_another_run_check_at = time.time() - 61
        return controller

    def test_a_bot_that_ended_in_another_run_is_detected(self):
        controller = self._controller()
        Bot.objects.filter(pk=self.bot.pk).update(state=BotStates.ENDED)

        self.assertTrue(BotController.bot_ended_in_another_run(controller))

    def test_a_bot_still_in_its_meeting_is_not_detected(self):
        self.assertFalse(BotController.bot_ended_in_another_run(self._controller()))

    def test_the_database_is_checked_at_most_once_a_minute(self):
        controller = self._controller()
        controller.last_ended_in_another_run_check_at = time.time()
        Bot.objects.filter(pk=self.bot.pk).update(state=BotStates.ENDED)

        self.assertFalse(BotController.bot_ended_in_another_run(controller))

    def test_the_loop_cleans_up_and_stops_when_the_bot_ended_elsewhere(self):
        controller = self._controller()
        controller.bot_ended_in_another_run.return_value = True

        self.assertFalse(BotController.on_main_loop_timeout(controller))
        controller.cleanup.assert_called_once()

    def test_the_loop_keeps_going_while_the_bot_is_in_its_meeting(self):
        controller = self._controller()
        controller.bot_ended_in_another_run.return_value = False

        self.assertTrue(BotController.on_main_loop_timeout(controller))
        controller.cleanup.assert_not_called()

    def test_a_callback_left_behind_by_a_finished_run_removes_itself(self):
        controller = self._controller()
        controller.cleanup_called = True

        self.assertFalse(BotController.on_main_loop_timeout(controller))
        controller.set_bot_heartbeat.assert_not_called()
