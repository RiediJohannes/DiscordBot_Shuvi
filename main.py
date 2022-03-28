import asyncio
import random

import discord as d
import logging
import os

logging.basicConfig(level=logging.INFO)


class MyBot(d.Client):

    def __init__(self, name="Bot"):
        self.name = name
        self.greetings = ['Hallo', 'Hey', 'Hi', 'Hoi', 'Servus', 'Moin', 'Zeawas', 'Seawas', 'Heile', 'Grüezi',
                          'Ohayou', 'Yahallo']
        self.when_approached = ['Ja, was ist?', 'Ja?', 'Hm?', 'Was los', 'Zu Diensten!', 'Jo?', 'Hier', 'Was\'n?',
                                'Schon da', 'Ich hör dir zu', 'So heiß ich']
        super().__init__()  # superclass discord.Client needs to be properly initialized as well


    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))


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


    async def react_to_name(self, msg: d.message) -> str:
        # check if there is a greeting inside the message
        for word in self.greetings:
            if word.casefold() in msg.content.casefold():
                return f'{random.choice(self.greetings)} {msg.author.display_name}!'

        reactions = self.when_approached.copy()
        reactions.append(f'{msg.author.display_name}')
        return random.choice(reactions)


    async def delete(self, msg: d.message):
        # split message text into each word and only take everything after the command
        words = msg.content.split()[1:]
        # text = ' '.join(words)
        number = int(next(filter(lambda word: word.isnumeric(), words), 0))
        number += 3     # we also want the messages of the .delete call to disappear
        if number > 100: number = 100   # 100 is the upper deletion limit set by discord's API

        # inner function to handle user response
        async def execute_deletion():
            try:
                await msg.channel.send(f'{self.name} würde nun {number-3} Nachrichten löschen. Fortsetzen? (y/n)')
                answer = await self.wait_for("message", check=lambda ans: ans.author == msg.author and ans.channel == msg.channel, timeout=30.0)
            except asyncio.TimeoutError:
                await msg.channel.send(f'Hm, da kommt ja doch nichts mehr... _[Löschen abgebrochen]_')
            else:
                if answer.content.casefold() in ['yes', 'y', 'ja', 'jo', 'j']:
                    trashcan = await msg.channel.history(limit=number).flatten()
                    await msg.channel.delete_messages(trashcan)
                    await msg.channel.send(f'{number-3} Nachrichten gelöscht', delete_after=5.0)
                elif answer.content.casefold() in ['no', 'n', 'nein', 'na', 'nö', 'nope', 'stop', 'cancel']:
                    await msg.channel.send(f'Ist gut, {self.name} löscht nichts')
                else:
                    await msg.channel.send(f'Das beantwortet nicht {self.name}\'s Frage')
                    await execute_deletion()
        await execute_deletion()


    async def approaches(self, msg: d.message):
        await msg.channel.send(self.when_approached)

    @staticmethod  # this is only static so that the compiler shuts up at the execute_command call above
    async def not_found(self, msg: d.message):
        await msg.channel.send(f'Dieses Kommando kennt {self.name} leider nicht :/')

    execute_command = {
        '.delete': delete,
        '.ap': approaches,
        'not_found': not_found,
        # every function with entry in this dict must have 'self' parameter to work in execute_command call
    }


bot = MyBot("Shuvi")
print('Mein Token: ' + os.environ['DISCORD_TOKEN'])

# private token for my bot
bot.run(os.environ['DISCORD_TOKEN'])
