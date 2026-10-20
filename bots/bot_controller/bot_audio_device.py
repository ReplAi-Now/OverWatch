import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)


class BotAudioDevice:
    """
    A PulseAudio null sink of this bot's own, so bots sharing one worker container
    never hear or record each other. Chrome plays into the sink and ffmpeg records
    its monitor, both through the PULSE_SINK / PULSE_SOURCE defaults set here, which
    every child process (chromedriver, Chrome, ffmpeg) inherits.

    Each celery prefork child runs one bot at a time, so the process environment
    belongs to this bot for as long as it runs.
    """

    def __init__(self, bot_object_id):
        self.sink_name = "bot_" + re.sub(r"[^A-Za-z0-9_]", "_", str(bot_object_id))
        self.module_index = None

    @property
    def source_name(self):
        return f"{self.sink_name}.monitor"

    def create(self):
        try:
            result = subprocess.run(
                ["pactl", "load-module", "module-null-sink", f"sink_name={self.sink_name}", f"sink_properties=device.description={self.sink_name}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as e:
            # Falling back to the shared default sink still records the call; it only risks bleed from a parallel bot.
            logger.error(f"Could not create audio sink {self.sink_name}, using the shared default: {e}")
            return False

        self.module_index = result.stdout.strip()
        os.environ["PULSE_SINK"] = self.sink_name
        os.environ["PULSE_SOURCE"] = self.source_name
        logger.info(f"Created audio sink {self.sink_name} (module {self.module_index})")
        return True

    def remove(self):
        os.environ.pop("PULSE_SINK", None)
        os.environ.pop("PULSE_SOURCE", None)
        if not self.module_index:
            return
        try:
            subprocess.run(["pactl", "unload-module", self.module_index], check=True, capture_output=True, timeout=10)
            logger.info(f"Removed audio sink {self.sink_name}")
        except Exception as e:
            logger.error(f"Could not remove audio sink {self.sink_name}: {e}")
        self.module_index = None


def current_sink():
    """The sink this process plays into: the bot's own when one was created, else the shared default."""
    return os.environ.get("PULSE_SINK") or "@DEFAULT_SINK@"
