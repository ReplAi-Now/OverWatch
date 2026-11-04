import logging
import os
import signal
import subprocess

from celery import shared_task
from celery.signals import worker_shutting_down

from bots.bot_controller import BotController
from bots.models import Bot, BotStates

logger = logging.getLogger(__name__)


@shared_task(bind=True, soft_time_limit=3600)
def run_bot(self, bot_id):
    bot = Bot.objects.get(id=bot_id)
    # Guard against broker redelivery: re-running a finished bot risks clobbering its recording (issue #587).
    if bot.state in BotStates.post_meeting_states():
        logger.warning(f"Bot {bot_id} is already in post-meeting state {BotStates.state_to_api_code(bot.state)}, skipping run_bot")
        return
    logger.info(f"Running bot {bot_id}")
    kill_orphaned_xvfb_processes()
    bot_controller = BotController(bot_id)
    bot_controller.run()


def kill_orphaned_xvfb_processes():
    # Each bot starts its own Xvfb from a celery child that exits after the task. When a run dies before its cleanup
    # (hard time limit, crash), the Xvfb is reparented to PID 1 and lives on. A running bot's Xvfb always has its
    # celery child as parent, so a PID 1 parent means the bot that started it is gone.
    try:
        out = subprocess.run(["ps", "-eo", "pid=,ppid=,comm="], capture_output=True, text=True, timeout=5).stdout
    except Exception as e:
        logger.warning(f"Could not list processes to find orphaned Xvfb: {e}")
        return
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) != 3 or parts[2] != "Xvfb" or parts[1] != "1":
            continue
        try:
            os.kill(int(parts[0]), signal.SIGKILL)
            logger.warning(f"Killed orphaned Xvfb process {parts[0]}")
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.warning(f"Could not kill orphaned Xvfb process {parts[0]}: {e}")


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
