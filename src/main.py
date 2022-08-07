import asyncio
import datetime
import asyncpg
import random
import discord as d
import logging
import os
import pytz

from typing import List, Tuple
from logger import CustomFormatter
from fuzzywuzzy import fuzz, process
from wrapper.msg_container import MsgContainer
from wrapper.database_wrapper import DatabaseWrapper, Reminder
from localization.quote_server import QuoteServer as Quotes
from utils.time_handler import TimeHandler
from utils.user_interaction_handler import UserInteractionHandler
from exceptions.errors import *
from exceptions.error_handler import ErrorHandler


async def __startup():

    # setup connection to heroku postgres database
    database_connection = await asyncpg.create_pool(os.environ.get("DATABASE_URL", None), max_size=5, min_size=3)
    database = DatabaseWrapper(database_connection)

    intents = d.Intents.default()
    intents.members = True
    # instantiate a discord bot of custom class MyBot
    bot = MyBot(name="Shuvi", db=database, prefix='.', intents=intents)

    try:
        # run bot via its private API token
        main_task = asyncio.create_task(bot.start(os.environ['DISCORD_TOKEN']), name='main_task')
        asyncio.create_task(bot.watch_reminders(), name='reminder_watchdog')
        await main_task

    finally:
        await database_connection.close()
        await bot.close()


def __init_logs():
    handler = logging.StreamHandler()
    handler.setFormatter(CustomFormatter())

    logs = logging.getLogger('discord')
    logs.addHandler(handler)
    logs.setLevel(logging.INFO)
    return logs


class MyBot(d.Client):

    def __init__(self, name="Bot", db=None, prefix='.', intents=None):
        super().__init__(intents=intents)  # superclass discord.Client needs to be properly initialized as well
        self.name = name
        self.db = db
        self.prefix = prefix

        self.method_dict = {
            'help': "Erhalte eine Übersicht über alle Kommandos.\n"
                    "Auch als Option -h oder -help für jedes Kommando verfügbar",
            'wake': f"Stubse {self.name} kurz an, um zu sehen, ob sie noch da ist",
            'delete <anzahl>': "Lösche eine bestimmte _Anzahl_ von zuletzt gesendeten Nachrichten im aktuellen Chat. Auch jegliche Spuren des Löschvorgangs werden anschließend beseitigt.\n",
            'spam <anzahl>': f"Lass {self.name} den aktuellen Chat mit einer bestimmten _Anzahl von Nachrichten_ vollspammen.",
            'remindme <datum> <uhrzeit> "<nachricht>"': f"Setze einen Reminder mit einer bestimmten _Nachricht_. {self.name} wird dich dann am gewählten _Datum_ zur gewünschten _Zeit_ erinnern.\n"
                                                        f"Verwende für das Datum die europäische Reihenfolge (dd.mm.yyyy), für die Uhrzeit die 24h-Uhr und setze deine Nachricht an Anführungszeichen.\n"
                                                        f"Die Reihenfolge der Argumente ist jedoch egal.",
            'remindme -s | -show': "Erhalte eine Übersicht über alle anstehenden Reminder auf dem aktuellen Server.",
            'remindme -d | -delete <nummer>': f"Lösche den anstehenden Reminder mit einer bestimmten Nummer. Um die Nummer deines gesuchten Reminders zu erfahren, probier mal das"
                                              f"{self.prefix}remindme -show Kommando aus. Du kannst aber logischerweise nur deinen eigenen Reminder löschen.",
            'timezone': "Lass dir deine derzeit gewählte Zeitzone anzeigen und ändere sie bei Bedarf.",
        }
        self.error_handler = None


    # executes when bot setup is finished
    async def on_ready(self):
        logger.info('Logged on as {0}!'.format(self.user))

        # setup ErrorHandler to process errors during runtime
        debug_channel = self.get_channel(int(os.environ.get("DEBUG_CHANNEL", None)))
        self.error_handler = ErrorHandler(self.name, logger, debug_channel)

        try:
            # confirm successful bot startup with a message into to 'bot' channel on my private server
            chat = self.get_channel(int(os.environ.get("TEST_CHANNEL", None)))
            await chat.send(Quotes.get_quote('startup').format(self))

        except Exception as exp:
            # forward any exception to the ErrorHandler
            await self.error_handler.handle(exp)

        # remove long expired reminders from database
        await self.db.clean_up_reminders()


    async def watch_reminders(self):
        # wait until the bot is ready
        await self.wait_until_ready()

        try:
            while True:
                # check the time remaining until the next reminder is due
                due_date, time_remaining = await self.db.check_next_reminder()

                if not due_date or not time_remaining:
                    logger.info(f'Currently no reminders in the DB. ReminderWatchdog is placed on hold until further notice')
                    break   # escape while loop

                # localize the due date to CET
                due_date = due_date.astimezone(pytz.timezone('Europe/Berlin'))

                logger.info(f'Next reminder is due at: {due_date}')
                logger.info(f'Time left: {time_remaining} seconds')

                # if the time remaining is less than a minute, initiate the reminding process
                if time_remaining > 60:
                    # sleep for a while (80% of the time remaining to be exact, for one hour at max)
                    # then check again if the reminder is still valid
                    sleep_time = time_remaining / 1.25 if time_remaining < 1.25 * 3600 else 3600
                    logger.info(f'ReminderWatchdog is now sleeping for {sleep_time} seconds')
                    await asyncio.sleep(sleep_time)

                else:
                    logger.info(f'Upcoming reminder in {time_remaining} seconds...')

                    # create a new task to sleep one last time until the reminder is due
                    countdown = asyncio.create_task(asyncio.sleep(time_remaining))

                    # retrieve the upcoming reminder as a reminder object
                    reminder = await self.db.fetch_next_reminder()
                    # get the chat for which the reminder is destined
                    chat = await self.__get_channel_by_id(reminder.channel_id, reminder.user_id)

                    # wait for countdown to finish, then post reminder memo into the specified channel
                    await countdown
                    await chat.send(Quotes.get_quote('reminder/due').format(self, reminder=reminder))

                    # delete reminder in database afterwards
                    await self.db.delete_reminder(reminder)

        except Exception as exp:
            # forward any exception to the ErrorHandler
            await self.error_handler.handle(exp)


    # returns a channel object corresponding to a given channel_id
    async def __get_channel_by_id(self, channel_id: int, user_id: int) -> d.abc.Messageable | None:
        # try to get a channel object through the channel id - this method only works for server channels
        chat = self.get_channel(channel_id)
        if chat:
            return chat

        # if chat is none, the channel_id was most likely a private channel (dm)
        # search through all existing private channels the bot has
        for dm in self.private_channels:
            if channel_id == dm.id:
                return dm

        # in case we don't have a dm chat with that user yet, we need to create one
        user = self.get_user(user_id)
        return await user.create_dm()


    # executes when a new message is detected in any channel
    async def on_message(self, message):
        logger.debug('Message from {0.author}: {0.content}'.format(message))

        # prevent response to own messages or messages from any other bots
        if message.author.bot:
            return

        # create a custom message object from the real message object
        msg = MsgContainer(message, self.db)

        try:
            # check for command at message begin
            if msg.prefix == self.prefix:

                # don't react on prefixes that are not followed by an alphabetic character
                # this is most likely a smiley, not a command
                if not msg.text[1].isalpha():
                    return

                logger.info(f"Command '{msg.cmd}' by {msg.user.name}")

                # only show the help info for a given command
                if '-h' in msg.words or '-help' in msg.words:
                    return await self.__get_command_info(msg)

                # call the respective function belonging to given cmd with arguments (self, msg);
                # if cmd is invalid, return function for dict-key 'not_found'
                return await self.execute_command.get(msg.cmd, self.execute_command['not_found'])(self, msg)

            # check for own name in message
            if self.name.casefold() in msg.text:
                # generate appropriate response
                response = await self.__react_to_name(msg)
                await msg.post(response)

            # check for selam in message
            if 'selam' in msg.text:
                # generate appropriate response
                await msg.post('Aleyküm selam')

        except Exception as exp:
            # forward any exception during the execution of a command to the ErrorHandler
            await self.error_handler.handle(exp, msg)


    # defines reaction to when a user message includes the bot's name (content of self.name)
    @staticmethod
    async def __react_to_name(msg: MsgContainer) -> str:
        # check if there is a greeting inside the message
        for word in Quotes.get_choices("greetings"):
            if word.casefold() in msg.text:
                return f'{Quotes.get_quote("greetings")} {msg.user.display_name}!'

        # add another possible reaction at runtime: the name of the sender
        reactions = Quotes.get_choices("reactions")
        reactions.append(f'{msg.user.display_name}')
        return random.choice(reactions)


    # separate function (to greet or react on approach) to be called on .wake command.
    async def approached(self, msg: MsgContainer):
        response = await self.__react_to_name(msg)
        await msg.post(response)


    async def info(self, msg: MsgContainer):
        help_embed = d.Embed(title=Quotes.get_quote('help/title').format(self), color=0x008800)

        for name, description in self.method_dict.items():
            help_embed.add_field(name=self.prefix + name, value=description, inline=False)

        help_embed.set_footer(text=Quotes.get_quote('help/hint').format(self))
        return await msg.post(embed=help_embed)


    async def __get_command_info(self, msg: MsgContainer):
        # get a list of every signature for the given command
        cmd_info = [(signature, description) for signature, description in self.method_dict.items() if msg.cmd + ' ' in signature.lower()]

        # check if cmd_info is empty -> there is no command with the given name
        if not cmd_info:
            raise UnknownCommandException(f"Couldn't find a command with the name {msg.cmd}", command=msg.cmd, goal=Goal.HELP)

        cmd_embed = d.Embed(title=f'{msg.cmd.capitalize()} command:', color=0x008800)
        # add a field for every usage (every signature) of the given command
        for signature, description in cmd_info:
            cmd_embed.add_field(name=self.prefix + signature, value=description, inline=False)

        return await msg.post(embed=cmd_embed)


    # spams the channel with messages counting up to the number given as a parameter
    @staticmethod
    async def spam(msg: MsgContainer) -> None:
        # takes the first number in the message
        number = int(next(filter(lambda word: word.isnumeric(), msg.words), 0))
        if not number:
            raise InvalidArgumentsException('No number of messages to spam was given', cause=Cause.NOT_A_NUMBER, goal=Goal.SPAM, arguments=msg.words)
        for i in range(number):
            await msg.post(i + 1)
            # after every five messages, run the typing animation, as the bot has to wait until the HTTP-POST rate limit bucket has refilled
            if (i+1) % 5 == 0:
                async with msg.chat.typing():
                    pass
        # end the spam with an assertive message
        await msg.post(Quotes.get_quote('spam_end'), ttl=5.0)


    # deletes a requested number of messages in the same channel (starting from the most recent message)
    async def delete(self, msg: MsgContainer):

        # author's note: Falls wir später die options abfragen wollen, empfiehlt sich hier ein check "if options:", um zu schauen, ob die Liste leer ist

        # search for first number within the list of words from the message
        number = int(next(filter(lambda word: word.isnumeric(), msg.words), 0))

        # get a confirmation from the user first before deleting
        delete_confirmation = UserInteractionHandler(self, msg)
        question = Quotes.get_quote('deletion/question').format(self, number=number)
        abort_msg = Quotes.get_quote('deletion/abort').format(self)
        confirmed, extra_messages = await delete_confirmation.get_confirmation(question=question, abort_msg=abort_msg)

        # we also want the messages needed for the confirmation process to disappear
        remaining = number + extra_messages

        if confirmed is False:
            return
        # delete the requested count of messages
        while remaining > 0:
            deletion_stack = remaining if remaining <= 100 else 100  # 100 is the upper deletion limit set by discord's API
            trashcan = await msg.chat.history(limit=deletion_stack).flatten()
            await msg.chat.delete_messages(trashcan)
            remaining -= deletion_stack
        await msg.post(Quotes.get_quote('deletion/done').format(self, number=number), ttl=5.0)


    async def set_reminder(self, msg: MsgContainer) -> None | ReminderNotFoundException | InvalidArgumentsException:
        # option 1: the user just wanted to see the upcoming reminders
        if '-s' in msg.options or '-show' in msg.options:
            embed = await self.show_reminders(msg)
            return await msg.post(embed=embed)

        # option 2: the user wants to delete a reminder
        if '-d' in msg.options or '-delete' in msg.options:
            return await self.delete_reminder(msg)

        # parse memo and timestamp from user message
        reminder_parser = TimeHandler()
        timestamp: datetime.datetime = await reminder_parser.get_timestamp(msg)
        memo: str = reminder_parser.get_memo(msg)

        user = msg.user
        epoch = round(timestamp.timestamp())  # convert timestamp to UNIX epoch in order to display them as discord timestamp

        # fetch user data from the database
        user_data = await msg.db_user
        if not user_data.tz:
            # if the user hasn't defined a timezone yet, add one
            user_data.tz = await self.__add_timezone(msg)

        user_tz = pytz.timezone(user_data.tz)

        # check if the reminder datetime has already passed (with regard to the user's timezone ofc)
        now = datetime.datetime.now(user_tz)
        if timestamp < now:
            raise InvalidArgumentsException('Cannot set reminder for datetime in the past', cause=Cause.TIMESTAMP_IN_THE_PAST,
                                            goal=Goal.REMINDER_SET, arguments=timestamp)

        # write the new reminder to the database
        await self.db.push_reminder(msg, timestamp, memo)
        await msg.post(Quotes.get_quote('reminder/setDone').format(self, uid=user.id, unix=epoch, memo=memo))

        # the newly created reminder might be due earlier than the current next task, so we need to restart the watchdog
        for task in asyncio.all_tasks():
            if task.get_name() == 'reminder_watchdog':
                # stop the current watchdog task which is most likely sleeping
                task.cancel()
        # create a new watchdog task which starts by scanning again for the next due date
        asyncio.create_task(self.watch_reminders(), name='reminder_watchdog')


    async def __add_timezone(self, msg: MsgContainer) -> str:
        default_tz = Quotes.get_quote('timezone/default')
        timezone_interrogation = UserInteractionHandler(self, msg)
        want_default = Quotes.get_quote('timezone/firstTime').format(self, default_tz=default_tz)
        start_selection = Quotes.get_quote('timezone/selection/start').format(self)
        confirmed, _ = await timezone_interrogation.get_confirmation(question=want_default, abort_msg=start_selection)
        if confirmed:
            await self.db.update_timezone(msg.user, default_tz)
            await msg.post(Quotes.get_quote('timezone/selection/done').format(self, new_tz=default_tz))
            return default_tz

        # choose a different timezone
        timezone_guess = await timezone_interrogation.listen()
        timezone: str = await self.__choose_timezone(timezone_interrogation, timezone_guess)
        if not timezone:
            raise FruitlessChoosingException(f"Failed to select a timezone for the user {msg.user.display_name}, most likely due to a timeout", cause=Cause(0))
        await self.db.update_timezone(msg.user, timezone)
        await msg.post(Quotes.get_quote('timezone/selection/done').format(self, new_tz=timezone))
        return timezone


    async def __choose_timezone(self, interaction: UserInteractionHandler, tz_guess: str) -> str | None:
        result_limit = 20
        # evaluates a "similarity score" between 0 and 100 for every timezone
        # then sorts them descending by their score and returns the [result_limit] best matching tuples
        scores: List[Tuple[str, int]] = process.extract(tz_guess, pytz.common_timezones, scorer=fuzz.partial_ratio, limit=result_limit)

        # if the match is very clear, ask the user if that's the correct timezone
        if (scores[0][1] == 100 and scores[1][1] < 100) or 0.8 * scores[0][1] > scores[1][1]:
            question = Quotes.get_quote('timezone/selection/didYouMean').format(self, best_match=scores[0][0])
            abort_msg = Quotes.get_quote('timezone/selection/otherResults').format(self)
            confirmed, _ = await interaction.get_confirmation(question=question, abort_msg=abort_msg)
            if confirmed:
                return scores[0][0]     # return the timezone that matched with the highest score
            # if the user rejected our offer, continue with the usual timezone choosing procedure below

        # let the user choose either one of those highest ranking timezones or search again with another string
        tz_selection: str = Quotes.get_quote('timezone/selection/mostSimilar').format(self) + \
                            "\n".join([str(i + 1) + ') ' + match[0]    # '1) Europe/Berlin' (example)
                                      for i, match in enumerate(scores)  # iterate through every element in the list
                                      if i < 5 or match[1] == scores[0][1]])  # take the first 5, potentially more if they have the same score as the 1st element

        if len(scores) == result_limit:
            tz_selection += Quotes.get_quote('timezone/selection/andMore').format(self)
        await interaction.talk(tz_selection)

        choose_one: str = Quotes.get_quote('timezone/selection/chooseOne').format(self)
        hint: str = Quotes.get_quote('timezone/selection/hint').format(self)
        response: str = await interaction.get_response(question=choose_one, hint_msg=hint, hint_on_try=3)

        if not response:
            return None     # something went wrong, perhaps a TimeOut
        index = response[0]
        # the user responded with a numbers (index of timezone)
        if index.isnumeric():
            return scores[int(index) - 1][0]    # return the corresponding timezone
        # the user responded with another search term
        return await self.__choose_timezone(interaction, response)  # search again for string matches


    async def change_timezone(self, msg: MsgContainer) -> None:
        # fetch data about the user from the database
        user_data = await msg.db_user

        # if the user hasn't defined a timezone yet, add one
        if not user_data.tz:
            user_data.tz = await self.__add_timezone(msg)
            return

        # if we already have an entry for this user, and he chose a timezone before, they can change it
        change_tz_interaction = UserInteractionHandler(self, msg)
        question = Quotes.get_quote('timezone/info').format(tz=user_data.tz)
        abort_msg = Quotes.get_quote('abort/happy')
        confirmed, _ = await change_tz_interaction.get_confirmation(question=question, abort_msg=abort_msg)

        if not confirmed:
            return  # apparently the user didn't want to change his timezone
        # let the user choose a new timezone
        question = Quotes.get_quote('timezone/selection/start').format(self)
        timezone_guess = await change_tz_interaction.get_response(question=question)
        timezone: str = await self.__choose_timezone(change_tz_interaction, timezone_guess)

        if not timezone:
            return await msg.post(Quotes.get_quote('timezone/selection/error').format(self))

        await self.db.update_timezone(msg.user, timezone)
        return await msg.post(Quotes.get_quote('timezone/selection/done').format(self, new_tz=timezone))


    # returns an embed, listing all reminders that are currently in the database
    async def show_reminders(self, msg: MsgContainer) -> d.Embed | ReminderNotFoundException:
        # check if command was sent in a server
        if not msg.server:
            # command was invoked in a private chat -> fetch all reminders for that user
            next_reminders: List[Reminder] = await self.db.fetch_reminders(user=msg.user)
        else:
            # get a list of channel_ids for all channels on the message's server
            channel_list = [str(channel.id) for channel in msg.server.text_channels]
            # fetch a list of upcoming reminders on this server from the database
            next_reminders: List[Reminder] = await self.db.fetch_reminders(channels=channel_list)

        if not next_reminders:  # empty list -> no reminders found in the database
            raise ReminderNotFoundException('There are no upcoming reminders at the moment', cause=Cause.EMPTY_DB)

        # create an embed to neatly display the upcoming reminders
        reminder_embed = d.Embed(title=Quotes.get_quote('reminder/show/title').format(self), color=0x660000)
        for i, rem in enumerate(next_reminders):
            user = self.get_user(rem.user_id)
            epoch = round(rem.due_date.timestamp())
            reminder_entry: str = Quotes.get_quote('reminder/show/entry').format(self, index=i+1, epoch=epoch, user=user)
            reminder_embed.add_field(name=reminder_entry, value=rem.memo, inline=False)
        reminder_embed.set_footer(text=Quotes.get_quote('reminder/show/hint').format(self))
        return reminder_embed


    # deletes the reminder with the given index (ordinal number, ordered by due_date) from the database
    # checkout .remindme -show to find the index of your target reminder
    async def delete_reminder(self, msg: MsgContainer) -> None | AuthorizationException | InvalidArgumentsException | IndexOutOfBoundsException:
        reminder_nr = self.__find_first_number(msg.words)
        if reminder_nr is None:
            raise InvalidArgumentsException("Couldn't find a number in the command arguments", arguments=msg.words, cause=Cause.NOT_A_NUMBER, goal=Goal.REMINDER_DEL)

        # fetch all upcoming reminders from the database and choose the one at the given index
        upcoming_reminders: List[Reminder] = await self.db.fetch_reminders()
        if not upcoming_reminders:
            raise ReminderNotFoundException("There are no upcoming reminders at the moment", cause=Cause.EMPTY_DB)
        if reminder_nr > len(upcoming_reminders):
            raise IndexOutOfBoundsException(f"Index {reminder_nr-1} not in scope of available reminders (length: {len(upcoming_reminders)})",
                                            index=reminder_nr-1, length=len(upcoming_reminders), collection=upcoming_reminders)
        del_rem = upcoming_reminders[reminder_nr - 1]

        # check if the reminder belongs to the user that wants to delete it
        if del_rem.user_id != msg.user.id:
            raise AuthorizationException(f"User {msg.user.display_name} (id: {msg.user.id}) tried to delete a reminder of user {del_rem.user_id}!",
                                         accessor=msg.user, owner=del_rem.user_id, resource=del_rem, cause=Cause.ILLEGAL_REMINDER_DELETION)

        date = del_rem.due_date.date().strftime('%d.%m.%Y')  # get the date in standardized format (dd.mm.yyyy)
        time = del_rem.due_date.time().isoformat(timespec='minutes')

        # get a confirmation from the user first before deleting
        reminder_confirmation = UserInteractionHandler(self, msg)
        deletion_summary = Quotes.get_quote('reminder/deletion/summary').format(self, rem=del_rem, date=date, time=time)
        abort_msg = Quotes.get_quote('reminder/deletion/abort').format(self)
        confirmed, num_of_messages = await reminder_confirmation.get_confirmation(question=deletion_summary, abort_msg=abort_msg)
        if not confirmed:
            return  # deletion aborted
        await self.db.delete_reminder(del_rem)
        return await msg.post(Quotes.get_quote('reminder/deletion/done').format(self))


    @staticmethod
    def __find_first_number(words: list[str]) -> int | None:
        for word in words:
            if word.isdigit():
                return int(word)
        return None


    # reminders
    # TODO: enable the use of relative time intervals (1 day, 2 hours, etc.) when setting a reminder

    # general improvements
    # TODO: make greeting dependant on current time?

    # delete command
    # TODO: check user rights when deleting messages
    # TODO: add option to only delete messages of the calling user
    # TODO: prevent deleting in private channels, as it is not possible

    # bugs
    # ToDo: Bugfix - Ensure that reminders also happen when they are missed by like up to 120 seconds
    # TODO: Bugfix - multiple reminders at the exact same time (atm only one of them is sent)


    @staticmethod  # this is only static so that the compiler shuts up at the execute_command()-call above
    async def not_found(self, msg: MsgContainer):
        raise UnknownCommandException(f"Couldn't find command with the name {msg.cmd}", command=msg.cmd, goal=Goal(0))


    # dictionary to map respective function to command
    execute_command = {
        'help': info,
        'delete': delete,
        'wake': approached,
        'spam': spam,
        'remindme': set_reminder,
        'timezone': change_timezone,
        'not_found': not_found,
        # every function with entry in this dict must have 'self' parameter to work in execute_command call
    }


# start the program
if __name__ == '__main__':
    logger = __init_logs()
    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(__startup())
