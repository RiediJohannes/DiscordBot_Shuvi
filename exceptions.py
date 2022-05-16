
class AuthorizationException(Exception):

    def __init__(self, message: str, *args, **kwargs):
        self.msg: str = message
        self.accessor = kwargs['accessor']
        self.owner = kwargs['owner']
        self.resource = kwargs['resource']
