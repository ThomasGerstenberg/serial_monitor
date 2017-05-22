import sys
import logging


LOG_FORMAT = "[%(asctime)s] [%(threadName)s] [%(name)s.%(funcName)s:%(lineno)s] [%(levelname)s]: %(message)s"

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
DEFAULT_LOG_LEVEL = "DEBUG"


def _get_level(level):
    if level is None:
        return DEFAULT_LOG_LEVEL
    elif isinstance(level, str) and level.upper() in LOG_LEVELS:
        return level.upper()
    else:
        return None


def create(log_name, level):
    l = logging.getLogger(log_name)
    l.propagate = True
    level = _get_level(level)
    if level is None:
        print("Unknown log level '{}', setting to default: {}".format(level, DEFAULT_LOG_LEVEL))
        level = DEFAULT_LOG_LEVEL

    l.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    l.addHandler(stream_handler)
    stream_handler.setLevel(level)

    return l

def get(log_name="serial_monitor"):
    return logging.getLogger(log_name)