import logging
import sys
from typing import Optional


class _ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m',
        'ERROR': '\033[31m', 'CRITICAL': '\033[35m'
    }
    BOLD = '\033[1m'
    RESET = '\033[0m'

    def format(self, record):
        raw = record.levelname
        color = self.COLORS.get(raw, self.RESET)
        record.levelname = f"{color}{self.BOLD}{raw}{self.RESET}"
        msg = super().format(record)
        record.levelname = raw
        return msg


class Logger:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, name="AI_Assistant", level="INFO", colored=True, log_file=None):
        if self._initialized:
            return
        self._initialized = True
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._logger.handlers.clear()

        fmt = '[%(asctime)s] %(levelname)s %(message)s'
        console_fmt = _ColoredFormatter(fmt, datefmt='%H:%M:%S') if colored else logging.Formatter(fmt, datefmt='%H:%M:%S')
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(console_fmt)
        self._logger.addHandler(ch)

        if log_file:
            fh = logging.FileHandler(log_file, encoding='utf-8', mode='a')
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
            self._logger.addHandler(fh)

    def debug(self, msg): self._logger.debug(msg)
    def info(self, msg): self._logger.info(msg)
    def warning(self, msg): self._logger.warning(msg)
    def error(self, msg): self._logger.error(msg)
    def critical(self, msg): self._logger.critical(msg)
    def set_level(self, level):
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))


_log = None
def get_logger(cfg=None):
    global _log
    if _log is None:
        if cfg is None:
            from config_loader import load_config
            cfg = load_config()
        lc = cfg.get("logging", {})
        _log = Logger(level=lc.get("level", "INFO"), colored=lc.get("colored", True), log_file=lc.get("log_file"))
    return _log