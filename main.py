import asyncio
import asyncpg
import random

import discord as d
import sched
import logging
import os

from TimeHandler import TimeHandler
from MsgContainer import MsgContainer


logging.basicConfig(level=logging.INFO)

async def startup():

    database_connection = await asyncpg.create_pool(os.environ.get("DATABASE_URL", None), max_size=5, min_size=3)
    bot = MyBot(name="Shuvi", db=database_connection, prefix='.')

    try:
        # run bot via its private token
        await bot.start(os.environ['DISCORD_TOKEN'])

    except KeyboardInterrupt:
        await database_connection.close()
        await bot.logout()


class MyBot(d.Client):

    def __init__(self, name="Bot", db=None, prefix='.'):
        self.name = name
        self.db = db
        self.prefix = prefix
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

        # prevent response to own messages or messages from any other bots
        if message.author.bot:
            return

        # create a custom message object from the real message object
        msg = MsgContainer(message)

        # check for command at message begin
        if msg.prefix == self.prefix:
            print(f'Command: {msg.cmd} by {msg.user.name}')
            # call the respective function belonging to cmd; if cmd is invalid, return function for dict-key 'not_found'
            await self.execute_command.get(msg.cmd, self.execute_command['not_found'])(self, msg)

        # check for own name in message
        if self.name.casefold() in msg.lower_text:
            # generate appropriate response
            response = await self.react_to_name(msg)
            await msg.post(response)
            # reply to message directly
            # await message.reply(response, mention_author=True)


    # defines reaction to when a user message includes the bot's name (content of self.name)
    async def react_to_name(self, msg: MsgContainer) -> str:
        # check if there is a greeting inside the message
        for word in self.greetings:
            if word.casefold() in msg.lower_text:
                return f'{random.choice(self.greetings)} {msg.user.display_name}!'

        # add another possible reaction at runtime: the name of the sender
        reactions = self.when_approached.copy()
        reactions.append(f'{msg.user.display_name}')
        return random.choice(reactions)


    # separate function (to greet or react on approach) to be called on .wake command.
    async def approaches(self, msg: MsgContainer):
        response = await self.react_to_name(msg)
        await msg.post(response)


    # spams the channel with messages counting up to the number given as a parameter
    async def spam(self, msg: MsgContainer):
        number = int(next(filter(lambda word: word.isnumeric(), msg.words), 0))
        if not number:
            return await msg.post("Eine Zahl wäre schön")
        for i in range(number):
            await msg.post(i + 1)
            # after every five messages, run the typing animation, as the bot has to wait until the HTTP-POST rate limit bucket has refilled
            if (i+1) % 5 == 0:
                async with msg.chat.typing():
                    pass
        # end the spam with an assertive message
        await msg.post(random.choice(self.spam_done), ttl=5.0)


    # deletes a requested number of messages in the same channel (starting from the most recent message)
    async def delete(self, msg: MsgContainer):
        # author's note: Falls wir später die options abfragen wollen, empfiehlt sich ein check "if options:", um zu schauen, ob die Liste leer ist

        # inner function to handle user response (confirm/abort deletion)
        async def execute_deletion():
            number = int(next(filter(lambda word: word.isnumeric(), msg.words), 0))  # search for first number within the text 'words'
            number += 3  # we also want the messages of the .delete call to disappear at the end
            remaining = number

            try:
                await msg.post(f'{self.name} würde nun {number-3} Nachrichten löschen. Fortsetzen? (y/n)')
                answer = await self.wait_for("message", check=lambda ans: ans.author == msg.user and ans.channel == msg.chat, timeout=30.0)
            except asyncio.TimeoutError:
                await msg.post(f'Hm, da kommt ja doch nichts mehr... _[Löschen abgebrochen]_')
            else:
                if answer.content.casefold() in ['yes', 'y', 'ja', 'jo', 'j', 'hai']:
                    while remaining > 0:
                        deletion_stack = remaining if remaining <= 100 else 100  # 100 is the upper deletion limit set by discord's API
                        trashcan = await msg.chat.history(limit=deletion_stack).flatten()
                        await msg.chat.delete_messages(trashcan)
                        remaining -= deletion_stack
                    await msg.post(f'{number-3} Nachrichten gelöscht', ttl=5.0)
                elif answer.content.casefold() in ['no', 'n', 'nein', 'na', 'nö', 'nope', 'stop', 'cancel', 'iie']:
                    await msg.post(f'Ist gut, {self.name} löscht nichts')
                else:
                    await msg.post(f'Das beantwortet nicht {self.name}\'s Frage')
                    await execute_deletion()    # ask again
        await execute_deletion()


    async def set_reminder(self, msg: MsgContainer):
        reminder_filter = TimeHandler()
        timestamp = reminder_filter.get_timestamp(msg)
        memo = reminder_filter.get_memo(msg)

        date = timestamp.date().strftime('%d.%m.%Y')    # get the date in standardized format (dd.mm.yyyy)
        time = timestamp.time().isoformat(timespec='minutes')   # get the time in standardized format (hh:mm)

        user = msg.user
        # create an entry for the sender in the users() relation if there isn't one already
        await self.db.execute(f"""
            INSERT INTO users(user_id, username, discriminator)
            SELECT \'{user.id}\', \'{user.name}\', \'{user.discriminator}\'
            WHERE NOT EXISTS (SELECT user_id FROM users WHERE user_id = \'{user.id}\');
        """)

        await msg.post(f'Reminder für <@!{user.id}> am **{date}** um **{time}** mit dem Text:\n_{memo}_')

        await self.db.execute(f"""
            INSERT INTO reminder(id, user_id, date_time_zone, memo)
            VALUES(gen_random_uuid(), '{user.id}', '{timestamp}', '{memo}');
        """)

        # name = await db.fetchrow("SELECT data FROM kolleg WHERE id = 0")
        # print(name)


        # TO DOs:
        # - show all currently pending reminders
        # - delete a reminder



    @staticmethod  # this is only static so that the compiler shuts up at the execute_command()-call above
    async def not_found(self, msg: MsgContainer):
        await msg.post(f'Dieses Kommando kennt {self.name} leider nicht :/')


    # dictionary to map respective function to command
    execute_command = {
        'delete': delete,
        'wake': approaches,
        'spam': spam,
        'remindme': set_reminder,
        'not_found': not_found,
        # every function with entry in this dict must have 'self' parameter to work in execute_command call
    }


loop = asyncio.get_event_loop()
loop.run_until_complete(startup())
