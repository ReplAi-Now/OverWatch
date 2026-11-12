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
    log_process_census(f"before bot {bot_id}")
    kill_orphaned_xvfb_processes()
    try:
        bot_controller = BotController(bot_id)
        bot_controller.run()
    finally:
        log_process_census(f"after bot {bot_id}")


def log_process_census(label):
    # Bots share one long-lived worker container, so anything a bot leaves behind piles up until Chrome cannot start
    # (Nov 8-12 2026: EAGAIN, "user data directory is already in use"). Log what is alive around every bot so the
    # next leak names itself. Reads /proc instead of running ps, because forking is exactly what fails when we are out.
    try:
        procs = zombies = threads = 0
        by_comm, zombie_comm, orphan_comm = {}, {}, {}
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/stat") as f:
                    stat = f.read()
            except OSError:
                continue
            comm = stat[stat.find("(") + 1 : stat.rfind(")")]
            fields = stat[stat.rfind(")") + 2 :].split()
            state, ppid, num_threads = fields[0], fields[1], int(fields[17])
            procs += 1
            threads += num_threads
            by_comm[comm] = by_comm.get(comm, 0) + 1
            if state == "Z":
                zombies += 1
                zombie_comm[comm] = zombie_comm.get(comm, 0) + 1
            elif ppid == "1" and pid != "1":
                orphan_comm[comm] = orphan_comm.get(comm, 0) + 1

        def top(counts):
            return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:10])

        limits = {}
        for name, path in (("pids_current", "/sys/fs/cgroup/pids.current"), ("pids_max", "/sys/fs/cgroup/pids.max"), ("threads_max", "/proc/sys/kernel/threads-max")):
            try:
                with open(path) as f:
                    limits[name] = f.read().strip()
            except OSError:
                pass
        logger.info(f"Process census {label}: processes={procs} threads={threads} zombies={zombies} limits={limits} top={top(by_comm)} zombie_top={top(zombie_comm)} orphans_top={top(orphan_comm)}")
    except Exception as e:
        logger.warning(f"Process census {label} failed: {e}")


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
