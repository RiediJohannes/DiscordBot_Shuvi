import asyncio
import asyncpg
import random
import discord as d
import logging
import os

from time_handler import TimeHandler
from msg_container import MsgContainer
from confirmation_prompt import ConfirmationPrompt
from reminder import Reminder
from database_wrapper import DatabaseWrapper


logging.basicConfig(level=logging.INFO)


async def startup():

    # setup connection to heroku postgres database
    database_connection = await asyncpg.create_pool(os.environ.get("DATABASE_URL", None), max_size=5, min_size=3)
    database = DatabaseWrapper(database_connection)

    # instantiate a discord bot of custom class MyBot
    bot = MyBot(name="Shuvi", db=database, prefix='.')

    try:
        # run bot via its private API token
        main_task = asyncio.create_task(bot.start(os.environ['DISCORD_TOKEN']), name='main_task')
        asyncio.create_task(bot.watch_reminders(), name='reminder_watchdog')
        await main_task

    except KeyboardInterrupt:
        await database_connection.close()
        await bot.logout()


class MyBot(d.Client):

    def __init__(self, name="Bot", db=None, prefix='.'):
        self.name = name
        self.db = db
        self.prefix = prefix

        self.greetings = ['Hallo', 'Hey', 'Hi', 'Hoi', 'Servus', 'Moin', 'Zeawas', 'Seawas', 'Heile', 'Grüezi', 'Ohayou', 'Yahallo']
        self.when_approached = ['Ja, was ist?', 'Ja?', 'Hm?', 'Was los', 'Zu Diensten!', 'Jo?', 'Hier', 'Was\'n?', 'Schon da',
                                'Ich hör dir zu', 'So heiß ich']
        self.spam_done = ['So, genug gespammt!', 'Genug jetzt!', 'Das reicht jetzt aber wieder mal.', 'Und Schluss', 'Owari desu', 'Habe fertig']
        super().__init__()  # superclass discord.Client needs to be properly initialized as well


    # executes when bot setup is finished
    async def on_ready(self):
        logging.info('Logged on as {0}!'.format(self.user))

        # confirm successful bot startup with a message into to 'bot' channel on my private server
        chat = self.get_channel(955511857156857949)
        await chat.send('Shuvi ist nun hochgefahren!')


    async def watch_reminders(self):
        # wait until the bot is ready
        await self.wait_until_ready()

        while True:
            # check the time remaining until the next reminder is due
            due_date, time_remaining = await self.db.check_next_reminder()

            logging.info(f'Next reminder is due at: {due_date}')
            logging.info(f'Time left: {time_remaining} seconds')

            # if the time remaining is less than a minute, initiate the reminding process
            if time_remaining < 60:
                logging.info(f'Upcoming reminder in {time_remaining} seconds...')

                # create a new task to sleep one last time until the reminder is due
                countdown = asyncio.create_task(asyncio.sleep(time_remaining))

                # retrieve the upcoming reminder as a reminder object
                reminder = await self.db.fetch_upcoming_reminder()

                # wait for countdown to finish, then post reminder memo into the specified channel
                await countdown
                chat = self.get_channel(reminder.channel_id)
                await chat.send(f'Reminder an <@!{reminder.user_id}>:\n{reminder.memo}')

                # delete reminder in database afterwards
                await self.db.delete_reminder(reminder)

            else:
                # sleep for a while (80% of the time remaining to be exact, for one hour at max)
                # then check again if the reminder is still valid
                sleep_time = time_remaining / 1.25 if time_remaining < 1.25*3600 else 3600
                logging.info(f'ReminderWatchdog is now sleeping for {sleep_time} seconds')
                await asyncio.sleep(sleep_time)


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
        # takes the first number in the message
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

        # author's note: Falls wir später die options abfragen wollen, empfiehlt sich hier ein check "if options:", um zu schauen, ob die Liste leer ist

        # search for first number within the list of words from the message
        number = int(next(filter(lambda word: word.isnumeric(), msg.words), 0))

        # get a confirmation from the user first before deleting
        delete_confirmation = ConfirmationPrompt(self, msg)
        question = f'{self.name} würde nun {number} Nachrichten löschen. Fortsetzen? (y/n)'
        abort_msg = f'Ist gut, {self.name} löscht nichts'
        confirmed, extra_messages = await delete_confirmation.get_confirmation(question=question, abort_msg=abort_msg)

        # we also want the messages needed for the confirmation process to disappear
        remaining = number + extra_messages

        if confirmed:
            while remaining > 0:
                deletion_stack = remaining if remaining <= 100 else 100  # 100 is the upper deletion limit set by discord's API
                trashcan = await msg.chat.history(limit=deletion_stack).flatten()
                await msg.chat.delete_messages(trashcan)
                remaining -= deletion_stack
            await msg.post(f'{number} Nachrichten gelöscht', ttl=5.0)


    async def set_reminder(self, msg: MsgContainer):
        reminder_filter = TimeHandler()
        timestamp = reminder_filter.get_timestamp(msg)
        memo = reminder_filter.get_memo(msg)

        date = timestamp.date().strftime('%d.%m.%Y')    # get the date in standardized format (dd.mm.yyyy)
        time = timestamp.time().isoformat(timespec='minutes')   # get the time in standardized format (hh:mm)

        user = msg.user

        # get a confirmation from the user first before deleting
        reminder_confirmation = ConfirmationPrompt(self, msg)
        question = f'Reminder für <@!{user.id}> am **{date}** um **{time}** mit dem Text:\n_{memo}_\nPasst das so? (y/n)'
        abort_msg = f'Na dann, lassen wir das'
        confirmed, num = await reminder_confirmation.get_confirmation(question=question, abort_msg=abort_msg)

        if confirmed:
            # create an entry for the sender in the users() relation if there isn't one already
            await self.db.create_user_entry(user)

            # write the new reminder to the database
            await self.db.push_reminder(msg, timestamp, memo)

            await msg.post(f'Reminder erfolgreich gesetzt! {self.name} wird dich wie gewünscht erinnern UwU')

            # the newly created reminder might be due earlier than the current next task, so we need to restart the watchdog
            for task in asyncio.all_tasks():
                if task.get_name() == 'reminder_watchdog':
                    # stop the current watchdog task which is most likely sleeping
                    task.cancel()
            # create a new watchdog task which starts by scanning again for the next due date
            asyncio.create_task(self.watch_reminders(), name='reminder_watchdog')


        # ToDo: show all currently pending reminders
        # ToDo: manually delete a reminder

        # ToDo: Bugfix - what if there is no reminder in the database?
        # ToDo: Bugfix - Ensure that reminders also happen when they are missed by like up to 120 seconds
        # ToDo: Bugfix - occasionally go through database and clear old reminders



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


asyncio.run(startup())
