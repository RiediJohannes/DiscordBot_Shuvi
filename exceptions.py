default_message = "Keine Fehlermeldung spezifiziert"


class AuthorizationException(Exception):

    def __init__(self, message: str = default_message, *args, accessor=None, owner=None, resource=None, **kwargs):
        self.msg: str = message
        self.accessor = accessor
        self.owner = owner
        self.resource = resource
        self.arglist = args
        self.kwarglist = kwargs


class InvalidArgumentsException(Exception):

    def __init__(self, message: str = default_message, *args, arguments=None, **kwargs):
        self.msg: str = message
        self.arguments = arguments
        self.arglist = args
        self.kwarglist = kwargs


class ReminderNotFoundException(Exception):

    def __init__(self, message: str = default_message, *args, **kwargs):
        self.msg: str = message
        self.kwarglist = kwargs


class IndexOutOfBoundsException(Exception):

    def __init__(self, message: str = default_message, *args, index, length, start=0, collection, **kwargs):
        self.msg: str = message
        self.index = index
        self.max = length
        self.min = start
        self.object = collection
        self.arglist = args
        self.kwarglist = kwargs
