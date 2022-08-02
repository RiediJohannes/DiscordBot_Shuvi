import uuid
from dataclasses import dataclass

from msg_container import MsgContainer
from datetime import datetime
from typing import Tuple


@dataclass(frozen=True)
class DBUser:
    id: int     # user id on discord
    name: str   # username
    hash: str   # user identifier (digits after hashtag in name)
    tz: str     # default timezone

    def __str__(self):
        return f'User {self.name}#{self.hash} (id = {self.id})'


@dataclass(frozen=True)
class Reminder:
    rem_id: uuid.UUID
    user_id: int = 178992018788188162       # defaults to my account 'Luigi-Fan'
    channel_id: int = 955511857156857949    # defaults to 'bot' channel on my private 'SR388' server
    due_date: datetime = None
    memo: str = 'Keine Nachricht spezifiziert'

    def __str__(self):
        return f'Reminder for user {self.user_id} at {self.due_date} (id = {self.rem_id})'


class DatabaseWrapper:

    def __init__(self, database_connection):
        self.database_connection = database_connection


    async def check_next_reminder(self) -> Tuple[datetime, int] | Tuple[None, None]:
        next_time_data: Tuple[datetime, str] = await self.database_connection.fetchrow("""
            SELECT MIN(rem.date_time_zone), EXTRACT(EPOCH FROM ( MIN(rem.date_time_zone) - current_timestamp) )
            FROM reminder rem
            WHERE rem.date_time_zone > current_timestamp;
        """)

        # apparently there are no upcoming reminders in the database atm
        if not next_time_data:
            return None, None

        due_date, timeleft_epoch = next_time_data
        # we add one to the time remaining because the reminders were always a fraction of a second too early
        return due_date, int(timeleft_epoch) + 1


    async def fetch_next_reminder(self) -> Reminder:
        reminder_args = await self.database_connection.fetchrow("""
            SELECT id, user_id, channel_id, date_time_zone, memo
            FROM reminder
            WHERE date_time_zone = (
                SELECT MIN(rem.date_time_zone)
                FROM reminder rem
                WHERE rem.date_time_zone > current_timestamp
            );
        """)
        # create a reminder object from the data retrieved from the database
        return Reminder(*reminder_args)


    async def fetch_reminders(self, channels=None, user=None) -> list[Reminder]:
        # if a list of channels was given, only fetch reminders which are bound to one of those channels
        channel_filter = ''
        if channels:
            server: str = ", ".join(channels)
            channel_filter = f'AND rem.channel_id IN ({server})'

        # if a specific user was given, only fetch reminders for that user
        user_filter = ''
        if user:
            user_filter = f'AND rem.user_id = {user.id}'

        reminder_args = await self.database_connection.fetch(f"""
            SELECT id, user_id, channel_id, date_time_zone, memo
            FROM reminder rem
            WHERE rem.date_time_zone >= current_timestamp {channel_filter} {user_filter}
            ORDER BY date_time_zone ASC;
        """)
        # create a list of Reminder objects from the data
        reminder_list = [Reminder(*record) for record in reminder_args]
        return reminder_list


    async def delete_reminder(self, reminder) -> None:
        # delete reminder in database afterwards
        await self.delete_reminder_by_id(reminder.rem_id)


    async def delete_reminder_by_id(self, reminder_id) -> None:
        # delete reminder in database afterwards
        await self.database_connection.execute(f"DELETE FROM reminder WHERE id = '{reminder_id}';")


    # remove long expired reminders from database
    async def clean_up_reminders(self) -> None:
        # lösche alte Reminder, die seit mehr als zwei Tagen abgelaufen sind
        await self.database_connection.execute("DELETE FROM reminder WHERE date_time_zone < current_timestamp - INTERVAL '2 day';")


    async def fetch_user_entry(self, user) -> DBUser | None:
        user_entry = await self.database_connection.fetchrow(f"""
            SELECT user_id, username, discriminator, time_zone
            FROM users
            WHERE user_id = {user.id};
        """)
        # if no user was found
        if not user_entry:
            return None
        return DBUser(*user_entry)


    async def create_user_entry(self, user) -> None:
        # create an entry for the sender in the users() relation if there isn't one already
        await self.database_connection.execute(f"""
            INSERT INTO users(user_id, username, discriminator)
            SELECT {user.id}, '{user.name}', '{user.discriminator}'
            WHERE NOT EXISTS (SELECT user_id FROM users WHERE user_id = {user.id});
        """)


    async def push_reminder(self, msg: MsgContainer, timestamp: datetime, memo: str) -> None:
        # escape potential single quotes in the message (works in SQL by doubling up the single quotes)
        memo = memo.replace("'", "''")
        # write the new reminder to the database
        await self.database_connection.execute(f"""
            INSERT INTO reminder(id, user_id, channel_id, date_time_zone, memo)
            VALUES(gen_random_uuid(), {msg.user.id}, {msg.chat.id}, '{timestamp}', '{memo}');
        """)


    async def update_timezone(self, user, timezone: str) -> None:
        await self.database_connection.execute(f"""
            UPDATE users
            SET time_zone = '{timezone}'
            WHERE user_id = {user.id};
        """)
