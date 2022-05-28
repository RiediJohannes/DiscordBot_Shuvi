from enum import Enum

class Cause(Enum):
    UNKNOWN = 0
    MISSING_ARGUMENT = 1
    NOT_A_NUMBER = 2
    ILLEGAL_REMINDER_DELETION = 3
    EMPTY_DB = 4


class BotBaseException(Exception):

    def __init__(self, error_msg: str, args, kwargs, cause=Cause(0)):
        self.err = error_msg
        self.cause = cause
        self.arglist = args
        self.kwarglist = kwargs


class AuthorizationException(BotBaseException):

    def __init__(self, err_message: str, cause: Cause, *args, accessor=None, owner=None, resource=None, **kwargs):
        super().__init__(err_message, args, kwargs, cause=cause)
        self.accessor = accessor
        self.owner = owner
        self.resource = resource


class InvalidArgumentsException(BotBaseException):

    def __init__(self, err_message: str, cause: Cause, *args, arguments=None, **kwargs):
        super().__init__(err_message, args, kwargs, cause=cause)
        self.arguments = arguments


class ReminderNotFoundException(BotBaseException):

    def __init__(self, err_message: str, cause: Cause, *args, **kwargs):
        super().__init__(err_message, args, kwargs, cause=cause)


class IndexOutOfBoundsException(BotBaseException):

    def __init__(self, err_message: str, *args, index, length, start=0, collection, **kwargs):
        super().__init__(err_message, args, kwargs)
        self.index = index
        self.max = length
        self.min = start
        self.object = collection
