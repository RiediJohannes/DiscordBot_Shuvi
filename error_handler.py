import traceback as tb
import inspect    # my_stack = inspect.stack()
from logging import Logger
from errors import *
from msg_container import MsgContainer


class ErrorHandler:

    def __init__(self, bot, logger: Logger, debug_channel):
        self.bot = bot
        self.log = logger
        self.debug = debug_channel


    async def handle(self, exp: Exception, user_msg: MsgContainer):
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
        if isinstance(exp, BotBaseException):
            debug_message = f"Bekannte Exception verursacht durch {user_msg.user.display_name}:"
        else:
            debug_message = f"<@!178992018788188162> Unbekannte Exception verursacht durch {user_msg.user.display_name}:"
        debug_message += "```yaml\n" + error_log + "```"
        await self.debug.send(debug_message)

        # react to exception
        await self.__react(exp, user_msg)


    async def __react(self, exp: Exception, msg: MsgContainer):
        # default message if an unknown error occurred
        feedback = 'Ups, hier hat irgendwas nicht ganz geklappt .-.'

        if isinstance(exp, UnknownCommandException):
            if exp.goal == Goal.HELP:
                feedback = f"Es gibt kein Kommando '{exp.cmd}' du kek"
            else:
                feedback = f'Dieses Kommando kennt {self.bot.name} leider nicht :/'

        if isinstance(exp, AuthorizationException):
            feedback = 'Du kannst nicht einfach den Reminder von jemand anderem löschen, wtf?\n' \
                       '-- _{0} hat versucht den Reminder "{1}" von <@{2}> zu löschen._ --' \
                       .format(exp.accessor.display_name, exp.resource.memo, exp.owner)


        elif isinstance(exp, ReminderNotFoundException):
            if exp.cause == Cause.EMPTY_DB:
                feedback = f'Aktuell scheint es gar keine anstehenden Reminder zu geben. Niemand nutzt {self.bot.name}s Hilfe :('


        elif isinstance(exp, IndexOutOfBoundsException):
            feedback = '{0}? Sorry aber so viele Reminder kennt {1} aktuell gar nicht'.format(exp.index + 1, self.bot.name)


        elif isinstance(exp, InvalidArgumentsException):
            if exp.cause == Cause.NOT_A_NUMBER:
                if exp.goal == Goal.REMINDER_DEL:
                    feedback = f'Welchen Reminder möchtest du denn löschen? {self.bot.name} benötigt eine Nummer von dir'
                elif exp.goal == Goal.SPAM:
                    feedback = f'Eine Zahl wäre schön, meinst du nicht?'
                else:
                    feedback = f'{self.bot.name} konnte in deiner Nachricht keine Nummer finden :|'

            elif exp.cause == Cause.DATE_NOT_FOUND:
                if exp.goal == Goal.REMINDER_SET:
                    feedback = f'Irgendwie kann {self.bot.name} da kein korrektes Datum sehen. Bitte verwende die Notation **dd.mm.yyyy** (oder kurz **d.m.yy**, geht auch)'

            elif exp.cause == Cause.TIME_NOT_FOUND:
                if exp.goal == Goal.REMINDER_SET:
                    feedback = f'Zu welcher Zeit soll {self.bot.name} dich denn erinnern? Bitte verwende die Notation **mm:hh**'

            elif exp.cause == Cause.INCORRECT_DATETIME:
                feedback = f'Bei deinem Datum oder deiner Uhrzeit scheint irgendwas nicht ganz zu passen'

        # send feedback message to the channel of the message that caused the error
        await msg.post(feedback)
