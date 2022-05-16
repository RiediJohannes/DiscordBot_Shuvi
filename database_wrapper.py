from reminder import Reminder
from msg_container import MsgContainer
from datetime import datetime


class DatabaseWrapper:

    def __init__(self, database_connection):
        self.database_connection = database_connection


    async def check_next_reminder(self) -> [datetime, int]:
        due_date, timeleft_epoch = await self.database_connection.fetchrow("""
            SELECT MIN(rem.date_time_zone), EXTRACT(EPOCH FROM ( MIN(rem.date_time_zone) - current_timestamp) )
            FROM reminder rem
            WHERE rem.date_time_zone > current_timestamp;
        """)
        # we add one to the time remaining because the reminders were always a fraction of a second to early
        return [due_date, int(timeleft_epoch) + 1]


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


    async def fetch_reminders(self) -> list[Reminder]:
        reminder_args = await self.database_connection.fetch("""
            SELECT id, user_id, channel_id, date_time_zone, memo
            FROM reminder rem
            WHERE rem.date_time_zone >= current_timestamp
            ORDER BY date_time_zone ASC;
        """)
        # create a list of Reminder objects from the data
        reminder_list = []
        for record in reminder_args:
            new_reminder = Reminder(*record)
            reminder_list.append(new_reminder)
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


    async def create_user_entry(self, user) -> None:
        # create an entry for the sender in the users() relation if there isn't one already
        await self.database_connection.execute(f"""
            INSERT INTO users(user_id, username, discriminator)
            SELECT {user.id}, '{user.name}', '{user.discriminator}'
            WHERE NOT EXISTS (SELECT user_id FROM users WHERE user_id = {user.id});
        """)


    async def push_reminder(self, msg: MsgContainer, timestamp: datetime, memo: str) -> None:
        # write the new reminder to the database
        await self.database_connection.execute(f"""
            INSERT INTO reminder(id, user_id, channel_id, date_time_zone, memo)
            VALUES(gen_random_uuid(), {msg.user.id}, {msg.chat.id}, '{timestamp}', '{memo}');
        """)
