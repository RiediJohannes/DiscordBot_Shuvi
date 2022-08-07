import re
import pytz
from datetime import datetime
from dateutil.relativedelta import relativedelta

from src.exceptions.errors import *
from src.wrapper.msg_container import MsgContainer
from src.localization.quote_server import QuoteServer as Quotes


class TimeHandler:

    def __init__(self):
        self.time_set = False
        self.date_set = False


    async def get_timestamp(self, msg: MsgContainer) -> datetime:
        self.time_set = False
        self.date_set = False

        # reduce the text to search through to everything except the memo text
        memo: str = self.get_memo(msg)
        relevant_text: str = msg.text.replace(memo.casefold(), "")

        # get the timezone of the user to calculate their local time
        user_data = await msg.db_user
        user_timezone = pytz.timezone(user_data.tz)

        # look for absolute date and time values (e.g. '18.06.22' or '14:25')
        timestamp = self.__get_absolute_datetime(datetime.now(user_timezone), relevant_text)

        # if either date or time was not set by an absolute value, search for relative time statements
        if not (self.date_set and self.time_set):
            timestamp = self.__get_relative_datetime(timestamp, relevant_text)

        # check if reminder date and time have been made clear
        if not self.date_set:
            raise InvalidArgumentsException(f"Could not parse reminder date from {msg.text}", cause=Cause.DATE_NOT_FOUND, goal=Goal.REMINDER_SET,
                                            arguments=msg.text)
        if not self.time_set:
            raise InvalidArgumentsException(f"Could not parse reminder time from {msg.text}", cause=Cause.TIME_NOT_FOUND, goal=Goal.REMINDER_SET,
                                            arguments=msg.text)

        # at last, add timezone information to the timestamp
        timestamp_localized = user_timezone.localize(timestamp)
        return timestamp_localized


    # finds the message in quotes inside the message and returns it
    @staticmethod
    def get_memo(msg: MsgContainer):
        memo = re.search(Quotes.get_quote('timestamp/patterns/memo'), msg.original_text)
        if memo:
            return memo.group()
        return Quotes.get_quote('reminder/noMemo')


    def __get_absolute_datetime(self, start_timestamp: datetime, text: str) -> datetime.time:
        date = start_timestamp.date()
        time = start_timestamp.time()

        # read date and time in message
        date_match = re.search(Quotes.get_quote('timestamp/patterns/date'), text)
        time_match = re.search(Quotes.get_quote('timestamp/patterns/time'), text)

        if date_match:
            date = self.__parse_date(date_match.group())
            self.date_set = True

        if time_match:
            time = self.__parse_time(time_match.group())
            self.time_set = True

        return datetime.combine(date, time)


    def __get_relative_datetime(self, start_timestamp: datetime, text: str) -> datetime:
        time_units = ["seconds", "minutes", "hours"]
        date_units = ["days", "weeks", "months", "years"]
        units: dict[str, int] = {"seconds": 0, "minutes": 0, "hours": 0, "days": 0, "weeks": 0, "months": 0, "years": 0}

        for unit in units:
            # check for various patterns to describe the given unit
            for day_pattern in Quotes.get_choices(f'timestamp/{unit}/patterns'):
                match = re.search(day_pattern, text)
                if match:
                    units[unit] = int(match.group())

            # check for other special keywords to describe a shift in the given unit
            for keyword, value in Quotes.get_dict(f'timestamp/{unit}/keywords').items():
                match = re.search(keyword, text)
                if match:
                    units[unit] = value

        # check for date keywords which explicitly take the current date
        for modifier in Quotes.get_choices(f'timestamp/futileKeywords/date'):
            if modifier in text:
                self.date_set = True

        # check for time keywords which explicitly take the current time
        for modifier in Quotes.get_choices(f'timestamp/futileKeywords/time'):
            if modifier in text:
                self.time_set = True

        # confirm the existence of a date/time unit
        units_set = {unit: count for unit, count in units.items() if count != 0}
        if any(unit in time_units for unit in units_set):   # checks for any common element in time_units and units_set
            self.time_set = True
            self.date_set = True    # if a time was set, then a date is not required
        if any(unit in date_units for unit in units_set):   # checks for any common element in date_units and units_set
            self.date_set = True

        # offset the start timestamp by the values of all the units which were set
        return start_timestamp + relativedelta(**units)


    @staticmethod
    def __parse_date(date_str: str) -> datetime.date:
        # if the user used '/' or '-' as a date delimiter, replace it with '.'
        date_str = date_str.replace('/', '.')
        date_str = date_str.replace('-', '.')

        try:
            # special case if year was given as two digits instead of four
            if len(date_str.split('.')[2]) == 2:
                return datetime.strptime(date_str, '%d.%m.%y').date()

            return datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError as exp:
            raise InvalidArgumentsException(str(exp), cause=Cause.INCORRECT_DATE, goal=Goal.REMINDER_SET, arguments=date_str)

    @staticmethod
    def __parse_time(time_str: str) -> datetime.time:
        try:
            return datetime.strptime(time_str, '%H:%M').time()
        except ValueError as exp:
            raise InvalidArgumentsException(str(exp), cause=Cause.INCORRECT_TIME, goal=Goal.REMINDER_SET, arguments=time_str)
