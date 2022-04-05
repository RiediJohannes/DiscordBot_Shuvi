import asyncio
import asyncpg
import random

import discord as d
import logging
import os

logging.basicConfig(level=logging.INFO)

async def startup():

    database_connection = await asyncpg.create_pool(os.environ.get("DATABASE_URL", None))
    bot = MyBot("Shuvi", database_connection)

    try:
        # Example create table code, you'll probably change it to suit you
        # await db.execute("CREATE TABLE IF NOT EXISTS users(id bigint PRIMARY KEY, data text);")
        # await db.execute("INSERT INTO users VALUES(1, 'Manuel')")

        # name = await db.fetchrow("SELECT data FROM kolleg WHERE id = 0")
        # print(name)

        # run bot via its private token
        await bot.start(os.environ['DISCORD_TOKEN'])

    except KeyboardInterrupt:
        await database_connection.close()
        await bot.logout()


class MyBot(d.Client):

    def __init__(self, name="Bot", db=None):
        self.name = name
        self.db = db
        self.greetings = ['Hallo', 'Hey', 'Hi', 'Hoi', 'Servus', 'Moin', 'Zeawas', 'Seawas', 'Heile', 'Grüezi',
                          'Ohayou', 'Yahallo']
        self.when_approached = ['Ja, was ist?', 'Ja?', 'Hm?', 'Was los', 'Zu Diensten!', 'Jo?', 'Hier', 'Was\'n?',
                                'Schon da', 'Ich hör dir zu', 'So heiß ich']
        self.spam_done = ['So, genug gespammt!', 'Genug jetzt!', 'Das reicht jetzt aber wieder mal.', 'Und Schluss', 'Owari desu', 'Habe fertig']
        super().__init__()  # superclass discord.Client needs to be properly initialized as well

    # executes when bot setup is finished
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    # executes when a new message is detected in any channel
    async def on_message(self, message):
        print('Message from {0.author}: {0.content}'.format(message))

        # prevent response to own messages
        if message.author == self.user:
            return

        # check for command at message begin
        if message.content.startswith('.'):
            cmd = message.content.split()[0].casefold()
            print(f'Command: {cmd} by {message.author.name}')
            # call the respective function belonging to cmd; if cmd is invalid, return function for dict-key 'not_found'
            await self.execute_command.get(cmd, self.execute_command['not_found'])(self, message)

        # check for own name in message
        if self.name.casefold() in message.content.casefold():
            # generate appropriate response
            response = await self.react_to_name(message)
            await message.channel.send(response)

    # defines reaction to when a user message includes the bot's name (content of self.name)
    async def react_to_name(self, msg: d.message) -> str:
        # check if there is a greeting inside the message
        for word in self.greetings:
            if word.casefold() in msg.content.casefold():
                return f'{random.choice(self.greetings)} {msg.author.display_name}!'

        reactions = self.when_approached.copy()
        reactions.append(f'{msg.author.display_name}')
        return random.choice(reactions)


    # separate function (to greet or react on approach) to be called on .wake command.
    async def approaches(self, msg: d.message):
        response = await self.react_to_name(msg)
        await msg.channel.send(response)


    # spams the channel with messages counting up to the number given as a parameter
    async def spam(self, msg: d.message):
        words = msg.content.split()[1:]
        number = int(next(filter(lambda word: word.isnumeric(), words), 0))
        if not number:
            return await msg.channel.send("Eine Zahl wäre schön")
        for i in range(number):
            await msg.channel.send(i + 1)
            # after every five messages, run the typing animation, as the bot has to wait until the HTTP-POST rate limit bucket has refilled
            if (i+1) % 5 == 0:
                async with msg.channel.typing():
                    pass
        # end the spam with an assertive message
        await msg.channel.send(random.choice(self.spam_done), delete_after=5.0)


    # deletes a requested number of messages in the same channel (starting from the most recent message)
    async def delete(self, msg: d.message):
        # split message text into each word (deliminator: ' ') and only take everything after the command
        words = msg.content.split()[1:]
        # text = ' '.join(words)

        # check for option flags
        flags = list(filter(lambda word: word.startswith('-'), words))
        # author's note: Falls wir später die flags abfragen wollen, empfiehlt sich ein check "if flags:", um zu schauen, ob die Liste leer ist

        # inner function to handle user response (confirm/abort deletion)
        async def execute_deletion():
            number = int(next(filter(lambda word: word.isnumeric(), words), 0))  # search for first number within the text 'words'
            number += 3  # we also want the messages of the .delete call to disappear at the end
            remaining = number

            try:
                await msg.channel.send(f'{self.name} würde nun {number-3} Nachrichten löschen. Fortsetzen? (y/n)')
                answer = await self.wait_for("message", check=lambda ans: ans.author == msg.author and ans.channel == msg.channel, timeout=30.0)
            except asyncio.TimeoutError:
                await msg.channel.send(f'Hm, da kommt ja doch nichts mehr... _[Löschen abgebrochen]_')
            else:
                if answer.content.casefold() in ['yes', 'y', 'ja', 'jo', 'j', 'hai']:
                    while remaining > 0:
                        deletion_stack = remaining if remaining <= 100 else 100  # 100 is the upper deletion limit set by discord's API
                        trashcan = await msg.channel.history(limit=deletion_stack).flatten()
                        await msg.channel.delete_messages(trashcan)
                        remaining -= deletion_stack
                    await msg.channel.send(f'{number-3} Nachrichten gelöscht', delete_after=5.0)
                elif answer.content.casefold() in ['no', 'n', 'nein', 'na', 'nö', 'nope', 'stop', 'cancel', 'iie']:
                    await msg.channel.send(f'Ist gut, {self.name} löscht nichts')
                else:
                    await msg.channel.send(f'Das beantwortet nicht {self.name}\'s Frage')
                    await execute_deletion()
        await execute_deletion()


    @staticmethod  # this is only static so that the compiler shuts up at the execute_command()-call above
    async def not_found(self, msg: d.message):
        await msg.channel.send(f'Dieses Kommando kennt {self.name} leider nicht :/')


    # dictionary to map respective function to command
    execute_command = {
        '.delete': delete,
        '.wake': approaches,
        '.spam': spam,
        'not_found': not_found,
        # every function with entry in this dict must have 'self' parameter to work in execute_command call
    }


loop = asyncio.get_event_loop()
loop.run_until_complete(startup())
