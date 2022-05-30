import re
from datetime import datetime
from exceptions import *
from msg_container import MsgContainer


class TimeHandler:

    date_pattern = '(?:0?[1-9]|[12][0-9]|3[01])[-/.](?:0?[1-9]|1[012])[-/.](?:(?:20)?[0-9]{2})'
    time_pattern = '(?:0?[0-9]|1[0-9]|2[0-3])[:](?:[0-5][0-9])'
    memo_pattern = '(?<=\").*(?=\")'

    def __init__(self):
        pass

    def get_timestamp(self, msg: MsgContainer) -> datetime:

        # read date and time in message
        date_match = re.search(self.date_pattern, msg.text)
        time_match = re.search(self.time_pattern, msg.text)

        if not date_match:
            raise InvalidArgumentsException(f"Could not parse reminder date from {msg.text}", cause=Cause.DATE_NOT_FOUND, goal=Goal.REMINDER_SET, arguments=msg.text)
        if not time_match:
            raise InvalidArgumentsException(f"Could not parse reminder time from {msg.text}", cause=Cause.TIME_NOT_FOUND, goal=Goal.REMINDER_SET, arguments=msg.text)

        date_str = date_match.group()
        time_str = time_match.group()

        # if the user used '/' or '-' as a date delimiter, replace it with '.'
        date_str = date_str.replace('/', '.')
        date_str = date_str.replace('-', '.')

        try:
            # special case if year was given as two digits instead of four
            if len(date_str.split('.')[2]) == 2:
                timestamp = datetime.strptime(date_str + ' ' + time_str, '%d.%m.%y %H:%M')
            else:
                timestamp = datetime.strptime(date_str + ' ' + time_str, '%d.%m.%Y %H:%M')
        except ValueError as exp:
            raise InvalidArgumentsException(str(exp), cause=Cause.INCORRECT_DATETIME, goal=Goal(0), arguments=[date_str, time_str])

        return timestamp


    # finds the message in quotes inside the message and returns it
    def get_memo(self, msg: MsgContainer):
        memo = re.search(self.memo_pattern, msg.text)
        if memo:
            return memo.group()
        return 'Keine Nachricht spezifiziert'
