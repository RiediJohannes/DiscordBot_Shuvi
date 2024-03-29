import logging


class CustomFormatter(logging.Formatter):
    grey = "\x1b[00;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    err_format = "%(levelname)s: %(asctime)s - %(message)-90s"
    format = err_format + " \t[%(name)s] (in: %(filename)s, line %(lineno)d)"
    date_format = "%Y-%m-%d %H:%M:%S"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + err_format + reset,
        logging.CRITICAL: bold_red + err_format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt=self.date_format)
        return formatter.format(record)
