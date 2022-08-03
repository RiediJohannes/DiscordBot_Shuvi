import traceback as tb
import os
import inspect    # my_stack = inspect.stack()

from logging import Logger
from src.exceptions.errors import *
from src.wrapper.msg_container import MsgContainer
from src.localization.quote_server import QuoteServer as Quotes


class ErrorHandler:

    def __init__(self, bot_name: str, logger: Logger, debug_channel):
        self.bot_name = bot_name
        self.log = logger
        self.debug = debug_channel


    async def handle(self, exp: Exception, user_msg: MsgContainer = None):
        # log error message and stacktrace
        traceback = list(tb.extract_tb(exp.__traceback__, limit=4))
        # summary: '↪ func_name, line ### -------> method call in traceback record'
        summary = "".join(["\t{ind}↪ {0.name}, line {num:-<{width}}> {0.line}\n"   # string template
                          .format(trace, ind='  '*i, num=str(trace.lineno) + ' ', width=30-len(trace.name)-2*i)  # string format
                           for i, trace in enumerate(traceback)])     # list comprehension
        # output: 'exception_class: exception_msg \n full summary'
        error_log = f'{type(exp).__name__}: {str(exp)}\n{summary}'
        self.log.error(error_log)

        # log traceback to debug channel on discord
        username: str = user_msg.user.display_name if user_msg else "Unbekannt"
        if isinstance(exp, BotBaseException):
            debug_message = f"Bekannte Exception verursacht durch {username}:"
        else:
            debug_message = f"<@!{os.environ.get('LUIGI_FAN_ID', None)}> Unbekannte Exception verursacht durch {username}:"
        debug_message += "```yaml\n" + error_log + "```"
        await self.debug.send(debug_message)

        # send feedback message to the channel of the message that caused the error
        if user_msg:
            feedback = self.__react(exp)
            await user_msg.post(feedback)


    def __react(self, exp: Exception) -> str:
        # default message if an unknown error occurred
        feedback = Quotes.get_quote('exceptions/default').format(exp)

        if not isinstance(exp, BotBaseException):
            return feedback

        exp.bot = self.bot_name

        match exp:
            case UnknownCommandException(goal=Goal.HELP) as exp:
                feedback = Quotes.get_quote('exceptions/unknownCommand/help').format(exp)
            case UnknownCommandException():
                feedback = Quotes.get_quote('exceptions/unknownCommand/default').format(exp)

            case QuoteServerException(cause=Cause.INVALID_JSON_PATH):
                feedback = Quotes.get_quote('exceptions/quoteServer/invalidJSONPath').format(exp)
            case QuoteServerException(cause=Cause.NOT_AN_ENDPOINT):
                feedback = Quotes.get_quote('exceptions/quoteServer/notAnEndpoint').format(exp)

            case AuthorizationException() as exp:
                feedback = Quotes.get_quote('exceptions/authorization').format(exp)

            case ReminderNotFoundException(cause=Cause.EMPTY_DB):
                feedback = Quotes.get_quote('exceptions/reminderNotFound').format(exp)

            case IndexOutOfBoundsException() as exp:
                feedback = Quotes.get_quote('exceptions/indexOutOfBounds').format(exp, index=exp.index + 1)

            case InvalidArgumentsException(cause=Cause.NOT_A_NUMBER, goal=Goal.REMINDER_DEL):
                feedback = Quotes.get_quote('exceptions/invalidArguments/NaN/remDel').format(exp)
            case InvalidArgumentsException(cause=Cause.NOT_A_NUMBER, goal=Goal.SPAM):
                feedback = Quotes.get_quote('exceptions/invalidArguments/NaN/spam').format(exp)
            case InvalidArgumentsException(cause=Cause.NOT_A_NUMBER):
                feedback = Quotes.get_quote('exceptions/invalidArguments/NaN/default').format(exp)

            case InvalidArgumentsException(cause=Cause.DATE_NOT_FOUND, goal=Goal.REMINDER_SET):
                feedback = Quotes.get_quote('exceptions/invalidArguments/dateNotFound/remSet').format(exp)
            case InvalidArgumentsException(cause=Cause.TIME_NOT_FOUND, goal=Goal.REMINDER_SET):
                feedback = Quotes.get_quote('exceptions/invalidArguments/timeNotFound/remSet').format(exp)
            case InvalidArgumentsException(cause=Cause.INCORRECT_DATETIME, goal=Goal.REMINDER_SET):
                feedback = Quotes.get_quote('exceptions/invalidArguments/incorrectDatetime/remSet').format(exp)
            case InvalidArgumentsException(cause=Cause.TIMESTAMP_IN_THE_PAST, goal=Goal.REMINDER_SET):
                feedback = Quotes.get_quote('exceptions/invalidArguments/timestampInThePast/remSet').format(exp)

        return feedback
