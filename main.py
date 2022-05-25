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
from exceptions import *
from reminder import Reminder
from time_handler import TimeHandler
from msg_container import MsgContainer
from user_interaction_handler import UserInteractionHandler
from database_wrapper import DatabaseWrapper


handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())

logger = logging.getLogger('discord')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


async def startup():

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


class MyBot(d.Client):

    def __init__(self, name="Bot", db=None, prefix='.', intents=None):
        self.name = name
        self.db = db
        self.prefix = prefix

        self.greetings = ['Hallo', 'Hey', 'Hi', 'Hoi', 'Servus', 'Moin', 'Zeawas', 'Seawas', 'Heile', 'Grüezi', 'Ohayou', 'Yahallo']
        self.when_approached = ['Ja, was ist?', 'Ja?', 'Hm?', 'Was los', 'Zu Diensten!', 'Jo?', 'Hier', 'Was\'n?', 'Schon da',
                                'Ich hör dir zu', 'So heiß ich']
        self.spam_done = ['So, genug gespammt!', 'Genug jetzt!', 'Das reicht jetzt aber wieder mal.', 'Und Schluss', 'Owari desu', 'Habe fertig']
        super().__init__(intents=intents)  # superclass discord.Client needs to be properly initialized as well


    # executes when bot setup is finished
    async def on_ready(self):
        logger.info('Logged on as {0}!'.format(self.user))

        # confirm successful bot startup with a message into to 'bot' channel on my private server
        chat = self.get_channel(955511857156857949)
        await chat.send(self.name + ' ist nun hochgefahren!')

        # remove long expired reminders from database
        await self.db.clean_up_reminders()


    async def watch_reminders(self):
        # wait until the bot is ready
        await self.wait_until_ready()

        # tz_guess = "Erope Berlin"
        # scores: List[Tuple[str, int]] = process.extract(tz_guess, pytz.common_timezones, scorer=fuzz.partial_ratio, limit=20)
        # infos = f"Folgende Zeitzonen sind deiner Anfrage am ähnlichsten:\n" + "\n".join([str(i + 1) + ') ' + match[0] + ', ' + str(match[1])
        #                                                                                      for i, match in enumerate(scores)
        #                                                                                     if i < 5 or match[1] == scores[0][1]])
        # logger.info(infos)
        # if len(infos) == 20:
        #     print(f"\n...und weitere - bitte verwende einen genaueren Suchbegriff!")
        # if (scores[0][1] == 100 and scores[1][1] < 100) or 0.8 * scores[0][1] > scores[1][1]:
        #     print("Hurra!")


        while True:
            # check the time remaining until the next reminder is due
            due_date, time_remaining = await self.db.check_next_reminder()
            # localize the due date to CET
            due_date = due_date.astimezone(pytz.timezone('Europe/Berlin'))

            logger.info(f'Next reminder is due at: {due_date}')
            logger.info(f'Time left: {time_remaining} seconds')

            # if the time remaining is less than a minute, initiate the reminding process
            if time_remaining < 60:
                logger.info(f'Upcoming reminder in {time_remaining} seconds...')

                # create a new task to sleep one last time until the reminder is due
                countdown = asyncio.create_task(asyncio.sleep(time_remaining))

                # retrieve the upcoming reminder as a reminder object
                reminder = await self.db.fetch_next_reminder()

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
                logger.info(f'ReminderWatchdog is now sleeping for {sleep_time} seconds')
                await asyncio.sleep(sleep_time)


    # executes when a new message is detected in any channel
    async def on_message(self, message):
        logger.debug('Message from {0.author}: {0.content}'.format(message))

        # prevent response to own messages or messages from any other bots
        if message.author.bot:
            return

        # create a custom message object from the real message object
        msg = MsgContainer(message)

        # check for command at message begin
        if msg.prefix == self.prefix:
            logger.info(f"Command '{msg.cmd}' by {msg.user.name}")
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
        delete_confirmation = UserInteractionHandler(self, msg)
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
        # option 1: the user just wanted to see the upcoming reminders
        if '-s' in msg.options or '-show' in msg.options:
            report_msg, embed = await self.show_reminders(msg)
            return await msg.post(report_msg, embed=embed)

        # option 2: the user wants to delete a reminder
        if '-d' in msg.options or '-delete' in msg.options:
            try:
                await self.delete_reminder(msg)
            except AuthorizationException as exp:
                await msg.post('Du kannst nicht einfach den Reminder von jemand anderem löschen, wtf?\n'
                               '-- _{0} hat versucht den Reminder "{1}" von <@{2}> zu löschen._ --'.format(exp.accessor.display_name, exp.resource.memo, exp.owner))
            except ReminderNotFoundException:
                await msg.post(f'Aktuell scheint es gar keine anstehenden Reminder zu geben. Niemand nutzt {self.name}s Hilfe :(')
            except IndexOutOfBoundsException as exp:
                await msg.post('{0}? Sorry aber so viele Reminder kennt {1} aktuell gar nicht'.format(exp.index + 1, self.name))
            except InvalidArgumentsException:
                await msg.post('Welchen Reminder möchtest du denn löschen? Mir fehlt da eine Nummer')
                # TODO: maybe move this up to execute_command in the future
            return

        reminder_filter = TimeHandler()
        timestamp: datetime.datetime = reminder_filter.get_timestamp(msg)
        memo: str = reminder_filter.get_memo(msg)

        date = timestamp.date().strftime('%d.%m.%Y')    # get the date in standardized format (dd.mm.yyyy)
        time = timestamp.time().isoformat(timespec='minutes')   # get the time in standardized format (hh:mm)
        user = msg.user

        # get a confirmation from the user first before deleting
        reminder_confirmation = UserInteractionHandler(self, msg)
        question = f'Reminder für <@!{user.id}> am **{date}** um **{time}** mit dem Text:\n_{memo}_\nPasst das so? (y/n)'
        abort_msg = f'Na dann, lassen wir das'
        confirmed, num = await reminder_confirmation.get_confirmation(question=question, abort_msg=abort_msg)

        # if the user wants to abort the task, stop execution
        if not confirmed:
            return

        # fetch user data from the database
        user_data = await self.db.fetch_user_entry(user)
        if not user_data:
            # create an entry for the sender in the users() relation if there isn't one already
            await self.db.create_user_entry(user)
            user_data.tz = await self.__add_timezone(msg)
        elif not user_data.tz:
            # if the user hasn't defined a timezone yet, add one
            user_data.tz = await self.__add_timezone(msg)

        user_tz = pytz.timezone(user_data.tz)
        timestamp_localized = user_tz.localize(timestamp)   # add timezone information to the timestamp

        # write the new reminder to the database
        await self.db.push_reminder(msg, timestamp_localized, memo)
        await msg.post(f'Reminder erfolgreich gesetzt! {self.name} wird dich wie gewünscht erinnern UwU')

        # the newly created reminder might be due earlier than the current next task, so we need to restart the watchdog
        for task in asyncio.all_tasks():
            if task.get_name() == 'reminder_watchdog':
                # stop the current watchdog task which is most likely sleeping
                task.cancel()
        # create a new watchdog task which starts by scanning again for the next due date
        asyncio.create_task(self.watch_reminders(), name='reminder_watchdog')


    async def __add_timezone(self, msg: MsgContainer) -> str:
        default_tz = 'Europe/Berlin'
        timezone_interrogation = UserInteractionHandler(self, msg)
        question = f'Du hast noch nie deine Zeitzone angegeben.\n' \
                   f'Möchtest du die Standardzeitzone {default_tz} wählen? (y/n)'
        abort_msg = f'Na dann, welche Zeitzone soll es denn sein?\n' \
                    f'Schreibe den ungefähren Namen der Zeitzone (Beispiel: **Europe/Berlin**)'
        confirmed, _ = await timezone_interrogation.get_confirmation(question=question, abort_msg=abort_msg)
        if confirmed:
            await self.db.update_timezone(msg.user, default_tz)
            await msg.post(f'Alright, deine Zeitzone ist jetzt auf {default_tz} gesetzt!')
            return default_tz

        # choose a different timezone
        timezone_guess = await timezone_interrogation.listen()
        timezone: str = await self.__choose_timezone(timezone_interrogation, timezone_guess)
        if not timezone:
            return default_tz   # TODO do something, maybe throw an error
        await self.db.update_timezone(msg.user, timezone)
        await msg.post(f'Alright, deine Zeitzone ist jetzt auf {timezone} gesetzt!')
        return timezone


    async def __choose_timezone(self, interaction: UserInteractionHandler, tz_guess: str) -> str | None:
        # evaluates a "similarity score" between 0 and 100 for every timezone
        # then sorts them descending by their score and returns the 20 best matching tuples
        scores: List[Tuple[str, int]] = process.extract(tz_guess, pytz.common_timezones, scorer=fuzz.partial_ratio, limit=20)

        # if the match is very clear, ask the user if that's the correct timezone
        if (scores[0][1] == 100 and scores[1][1] < 100) or 0.8 * scores[0][1] > scores[1][1]:
            question = f'Meintest du {scores[0][0]}? (y/n)'
            abort_msg = f'Hm, dann lass mal schauen, was {self.name} sonst so findet...'
            confirmed, _ = await interaction.get_confirmation(question=question, abort_msg=abort_msg)
            if confirmed:
                return scores[0][0]     # return the timezone that matched with the highest score
            # if the user rejected our offer, continue with the usual timezone choosing procedure below

        # let the user choose either one of those highest ranking timezones or search again with another string
        tz_selection = f"Folgende Zeitzonen sind deiner Anfrage am ähnlichsten:\n" + \
                       "\n".join([str(i + 1) + ') ' + match[0]    # '1) Europe/Berlin' (example)
                                 for i, match in enumerate(scores)  # iterate through every element in the list
                                 if i < 5 or match[1] == scores[0][1]])  # take the first 5, potentially more if they have the same score as the 1st element

        if len(tz_selection) == 20:
            tz_selection += "\n...und eventuell weitere - bitte verwende einen genaueren Suchbegriff!"
        await interaction.talk(tz_selection)

        choose_one: str = f"Wähle eine dieser Zeitzonen, indem du mit der **entsprechenden Zahl** antwortest, oder gib {self.name} einen **neuen Suchbegriff**"
        hint: str = "...\n**Ok warte**, schau mal, hier findest du eine Liste aller Zeitzonen:\nhttps://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        response: str = await interaction.get_response(question=choose_one, hint_msg=hint, hint_on_try=3)

        if not response:
            return None     # something went wrong
        index = response[0]
        # the user responded with a numbers (index of timezone)
        if index.isnumeric():
            return scores[int(index) - 1][0]    # return the corresponding timezone
        # the user responded with another search term
        return await self.__choose_timezone(interaction, response)  # search again for string matches


    # returns an embed, listing all reminders that are currently in the database
    async def show_reminders(self, msg: MsgContainer) -> [str, d.Embed]:
        # get a list of channel_ids for all channels on the message's server
        channel_list = [str(channel.id) for channel in msg.server.text_channels]

        # fetch a list of upcoming reminders on this server from the database
        next_reminders: List[Reminder] = await self.db.fetch_reminders(channels=channel_list)
        if not next_reminders:  # empty list -> no reminders found in the database
            return 'Aktuell steht kein Reminder in der Zukunft an', None    # no embed (2nd return value)

        # create an embed to neatly display the upcoming reminders
        reminder_embed = d.Embed(title="Die nächsten Reminder sind...", color=0x660000)
        for i, rem in enumerate(next_reminders):
            user = self.get_user(rem.user_id)
            reminder_embed.add_field(name=f'({i+1})  {rem.due_date.strftime("%d.%m.%Y, %H:%M")} an {user.display_name}:', value=rem.memo, inline=False)
        reminder_embed.set_footer(text='Tipp: Verwende ".remindme -d <Nummer>", um den\nReminder mit gegebener Nummer zu löschen')
        return None, reminder_embed  # no string message (1st return value)


    # deletes the reminder with the given index (ordinal number, ordered by due_date) from the database
    # checkout .remindme -show to find the index of your target reminder
    async def delete_reminder(self, msg: MsgContainer) -> None | AuthorizationException | InvalidArgumentsException | IndexOutOfBoundsException:
        reminder_nr = self.__find_first_number(msg.words)
        if reminder_nr is None:
            raise InvalidArgumentsException("Couldn't find a number in the command arguments", arguments=msg.words)

        # fetch all upcoming reminders from the database and choose the one at the given index
        upcoming_reminders: List[Reminder] = await self.db.fetch_reminders()
        if not upcoming_reminders:
            raise ReminderNotFoundException("There are no upcoming reminders at the moment")
        if reminder_nr > len(upcoming_reminders):
            raise IndexOutOfBoundsException(f"Index {reminder_nr-1} not in scope of available reminders (length: {len(upcoming_reminders)})",
                                            index=reminder_nr-1, length=len(upcoming_reminders), collection=upcoming_reminders)
        del_rem = upcoming_reminders[reminder_nr - 1]

        # check if the reminder belongs to the user that wants to delete it
        if del_rem.user_id != msg.user.id:
            raise AuthorizationException(f"User {msg.user.display_name} (id: {msg.user.id}) tried to delete a reminder of user {del_rem.user_id}!", accessor=msg.user, owner=del_rem.user_id, resource=del_rem)

        date = del_rem.due_date.date().strftime('%d.%m.%Y')  # get the date in standardized format (dd.mm.yyyy)
        time = del_rem.due_date.time().isoformat(timespec='minutes')

        # get a confirmation from the user first before deleting
        reminder_confirmation = UserInteractionHandler(self, msg)
        question = f'Reminder für <@!{del_rem.user_id}> am **{date}** um **{time}** mit dem Text:\n_{del_rem.memo}_\nwird nun **gelöscht**.' \
                   f'\nFortsetzen? (y/n)'
        abort_msg = f'Alles klar, der Reminder bleibt'
        confirmed, num_of_messages = await reminder_confirmation.get_confirmation(question=question, abort_msg=abort_msg)
        if not confirmed:
            return  # deletion aborted
        await self.db.delete_reminder(del_rem)
        return await msg.post("Reminder erfolgreich gelöscht!")


    @staticmethod
    def __find_first_number(words: list[str]) -> int | None:
        for word in words:
            if word.isdigit():
                return int(word)
        return None


    # ToDo: let a user change their default time zone afterwards

    # TODO: use discord timestamps for the reminder confirmation message
    # TODO: enable relative time intervals (1 day, 2 hours, etc.)

    # ToDo: add a help command which explains every available command

    # ToDo: Bugfix - what if there is no reminder in the database?
    # ToDo: Bugfix - Ensure that reminders also happen when they are missed by like up to 120 seconds
    # TODO: Bugfix - Incorrect reminder input
    # TODO: Bugfix - multiple reminders at the exact same time (atm only one of them is being sent)


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

# start the program
asyncio.run(startup())
