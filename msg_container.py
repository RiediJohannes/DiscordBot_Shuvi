import discord as d

class MsgContainer(d.Message):

    def __init__(self, msg: d.Message, option_prefix='-'):
        # straight-up copied attributes
        self._state = msg._state
        self.id = msg.id
        self.webhook_id = msg.webhook_id
        self.reactions = msg.reactions
        self.attachments = msg.attachments
        self.embeds = msg.embeds
        self.application = msg.application
        self.activity = msg.activity
        self.call = None
        self._edited_timestamp = msg._edited_timestamp
        self.type = msg.type
        self.pinned = msg.pinned
        self.flags = msg.flags
        self.mention_everyone = msg.mention_everyone
        self.tts = msg.tts
        self.nonce = msg.nonce
        self.stickers = msg.stickers
        self.reference = msg.reference

        # renamed attributes
        self.user = msg.author
        self.text = msg.content
        self.lower_text = msg.content.casefold()
        self.chat = msg.channel

        # new custom attributes
        self.prefix = msg.content[0]  # the first character of the message

        if not self.prefix.isalpha() and not self.prefix.isnumeric():
            self.cmd = msg.content.casefold().split()[0][1:]  # takes in the command (first word in the message) but leaves out the prefix!
            self.words = msg.content.casefold().split()[1:]  # splits the rest of the message into an array of distinct words (splits at each whitespace)
        else:
            self.cmd = None     # there was no command given
            self.words = msg.content.split()    # splits the message into an array of distinct words (splits at each whitespace)

        self.options = list(filter(lambda word: word.startswith(option_prefix), self.words))    # filters out all the words that are marked as a command option


    async def post(self, text, ttl=None, embed=None, file=None):
        await self.chat.send(text, embed=embed, file=file, delete_after=ttl)
