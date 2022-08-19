import discord as d
from src.wrapper.database_wrapper import DatabaseWrapper, DBUser

class MsgContainer:

    def __init__(self, msg: d.Message, database: DatabaseWrapper, option_prefix='-'):
        # straight-up copied attributes
        # self.state = msg._state
        self.id: int = msg.id
        self.webhook_id = msg.webhook_id
        self.reactions = msg.reactions
        self.attachments = msg.attachments
        self.embeds = msg.embeds
        self.application = msg.application
        self.activity = msg.activity
        self.call = None
        # self.edited_timestamp = msg._edited_timestamp
        self.type = msg.type
        self.pinned = msg.pinned
        self.flags = msg.flags
        self.mention_everyone = msg.mention_everyone
        self.tts = msg.tts
        self.nonce = msg.nonce
        self.stickers = msg.stickers
        self.reference = msg.reference
        self.interaction = msg.interaction


        # renamed attributes
        self.user = msg.author
        self.original_text = msg.content
        self.text = msg.content.casefold()
        self.chat = msg.channel
        self.server = msg.guild

        # new custom attributes
        self.prefix = msg.content[0]  # the first character of the message

        if not self.prefix.isalpha() and not self.prefix.isnumeric():
            # takes in the command (first word in the message) but leaves out the prefix!
            self.cmd: str = msg.content.casefold().split()[0][1:]
            # splits the rest of the message into an array of distinct words (splits at each whitespace)
            self.words: list[str] = msg.content.casefold().split()[1:]
        else:
            self.cmd: None = None     # there was no command given
            self.words: list[str] = msg.content.casefold().split()    # splits the message into an array of distinct words (splits at each whitespace)

        # filters out all the words that are marked as a command option
        self.options: list[str] = list(filter(lambda word: word.startswith(option_prefix), self.words))

        self.db = database
        self._db_user = None


    @property
    async def db_user(self) -> DBUser:
        # lazy loading of the database entry for the message's author
        if not self._db_user:
            self._db_user = await self.db.fetch_user_entry(self.user)

            # create an entry for the sender in the database if there wasn't one before
            if not self._db_user:
                self._db_user = await self.db.create_user_entry(self.user)

        return self._db_user


    # simple wrapper around the normal msg.send method
    async def post(self, text=None, ttl=None, embed=None, file=None):
        await self.chat.send(text, embed=embed, file=file, delete_after=ttl)
