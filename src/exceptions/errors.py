from enum import Enum


class Cause(Enum):
    UNKNOWN = 0
    MISSING_ARGUMENT = 1
    NOT_A_NUMBER = 2
    ILLEGAL_REMINDER_DELETION = 3
    EMPTY_DB = 4
    DATE_NOT_FOUND = 5
    TIME_NOT_FOUND = 6
    INCORRECT_DATE = 7
    INCORRECT_TIME = 8
    TIMESTAMP_IN_THE_PAST = 9
    INVALID_JSON_PATH = 10
    NOT_A_LIST = 11
    NOT_A_DICT = 12
    INSUFFICIENT_ARGUMENTS = 20


class Goal(Enum):
    UNKNOWN = 0
    REMINDER_DEL = 1
    REMINDER_SET = 2
    SPAM = 3
    HELP = 4


class BotBaseException(Exception):

    def __init__(self, error_msg: str, args, kwargs, *, cause=Cause(0), goal=Goal(0)):
        self.err = error_msg
        self.cause = cause
        self.goal = goal
        self.arglist = args
        self.kwarglist = kwargs


class UnknownCommandException(BotBaseException):

    def __init__(self, err_message: str, goal: Goal, *args, command: str, **kwargs):
        super().__init__(err_message, args, kwargs, goal=goal)
        self.cmd = command


class AuthorizationException(BotBaseException):

    def __init__(self, err_message: str, cause: Cause, *args, accessor=None, owner=None, resource=None, **kwargs):
        super().__init__(err_message, args, kwargs, cause=cause)
        self.accessor = accessor
        self.owner = owner
        self.resource = resource


class InvalidArgumentsException(BotBaseException):

    def __init__(self, err_message: str, cause: Cause, goal: Goal, *args, arguments=None, **kwargs):
        super().__init__(err_message, args, kwargs, cause=cause)
        self.arguments = arguments
        self.goal = goal


class ReminderNotFoundException(BotBaseException):

    def __init__(self, err_message: str, cause: Cause, *args, **kwargs):
        super().__init__(err_message, args, kwargs, cause=cause)


class FruitlessChoosingException(BotBaseException):

    def __init__(self, err_message: str, cause: Cause, *args, **kwargs):
        super().__init__(err_message, args, kwargs, cause=cause)


class IndexOutOfBoundsException(BotBaseException):

    def __init__(self, err_message: str, *args, index, length, start=0, collection, **kwargs):
        super().__init__(err_message, args, kwargs)
        self.index = index
        self.max = length
        self.min = start
        self.object = collection


class QuoteServerException(BotBaseException):

    def __init__(self, err_message: str, cause: Cause, *args, quote_path: str, error_node: str = None, **kwargs):
        super().__init__(err_message, args, kwargs, cause=cause)
        self.path = quote_path
        self.node = error_node
