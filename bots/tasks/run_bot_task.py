import logging
import os
import signal

from celery import shared_task
from celery.signals import worker_shutting_down

from bots.bot_controller import BotController
from bots.models import Bot, BotStates

logger = logging.getLogger(__name__)

# Backstop for a run that never ends. Celery's parent process kills the task at the hard limit even if the bot's
# main loop ignores everything else, which frees the worker slot. It must stay under the broker visibility_timeout
# (21600s by default, see attendee/celery.py) or the killed task would be redelivered. The soft limit comes first so
# the bot gets a chance to leave and upload what it recorded before the kill.
RUN_BOT_TIME_LIMIT_SECONDS = int(os.getenv("RUN_BOT_TIME_LIMIT_SECONDS", 18000))
RUN_BOT_SOFT_TIME_LIMIT_SECONDS = RUN_BOT_TIME_LIMIT_SECONDS - 600


@shared_task(bind=True, soft_time_limit=RUN_BOT_SOFT_TIME_LIMIT_SECONDS, time_limit=RUN_BOT_TIME_LIMIT_SECONDS)
def run_bot(self, bot_id):
    bot = Bot.objects.get(id=bot_id)
    # Guard against broker redelivery: re-running a finished bot risks clobbering its recording (issue #587).
    if bot.state in BotStates.post_meeting_states():
        logger.warning(f"Bot {bot_id} is already in post-meeting state {BotStates.state_to_api_code(bot.state)}, skipping run_bot")
        return
    logger.info(f"Running bot {bot_id}")
    bot_controller = BotController(bot_id)
    bot_controller.run()


def kill_child_processes():
    # Get the process group ID (PGID) of the current process
    pgid = os.getpgid(os.getpid())

    try:
        # Send SIGTERM to all processes in the process group
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # Process group may no longer exist


@worker_shutting_down.connect
def shutting_down_handler(sig, how, exitcode, **kwargs):
    # Just adding this code so we can see how to shut down all the tasks
    # when the main process is terminated.
    # It's likely overkill.
    logger.info("Celery worker shutting down, sending SIGTERM to all child processes")
    kill_child_processes()
