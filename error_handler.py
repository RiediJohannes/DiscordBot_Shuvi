import traceback as tb
import inspect
from logging import Logger
from exceptions import *
from msg_container import MsgContainer


class ErrorHandler:

    def __init__(self, logger: Logger, debug_channel):
        self.log = logger
        self.debug = debug_channel


    async def handle(self, exp: Exception, user_msg: MsgContainer):

        # log error message and stacktrace
        traceback = list(tb.extract_tb(exp.__traceback__))
        summary = "".join(["\t{ind}↪ {0.name}, line {num:-<{width}}> {0.line}\n"   # string template
                          .format(trace, ind='  '*i, num=str(trace.lineno) + ' ', width=30-len(trace.name)-2*i)  # string format
                           for i, trace in enumerate(traceback)])     # list comprehension
        error_log = f'{type(exp).__name__}: {str(exp)}\n{summary}'
        self.log.error(error_log)

        # my_stack = inspect.stack()

        if isinstance(exp, BotBaseException):
            debug_message = f"Bekannte Exception verursacht durch {user_msg.user.display_name}:" \
                            " ```yaml\n" + error_log + "```"
            await self.debug.send(debug_message)
        else:
            debug_message = f"**Unbekannte** Exception verursacht durch {user_msg.user.display_name}:" \
                            " ```yaml\n" + error_log + "```"
            await self.debug.send(debug_message)
