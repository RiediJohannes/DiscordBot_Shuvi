import re
from datetime import datetime

import pytz

from msg_container import MsgContainer


class TimeHandler:

    date_pattern = '(?:0?[1-9]|[12][0-9]|3[01])[-/.](?:0?[1-9]|1[012])[-/.](?:(?:20)?[0-9]{2})'
    time_pattern = '(?:0?[0-9]|1[0-9]|2[0-3])[:](?:[0-5][0-9])'
    memo_pattern = '(?<=\").*(?=\")'

    def __init__(self):
        pass

    def get_timestamp(self, msg: MsgContainer) -> datetime:

        # read date and time in message
        date_str = re.search(self.date_pattern, msg.text).group()
        time_str = re.search(self.time_pattern, msg.text).group()

        # if the user used '/' or '-' as a date delimiter, replace it with '.'
        date_str = date_str.replace('/', '.')
        date_str = date_str.replace('-', '.')

        # special case if year was given as two digits instead of four
        if len(date_str.split('.')[2]) == 2:
            timestamp = datetime.strptime(date_str + ' ' + time_str, '%d.%m.%y %H:%M')
        else:
            timestamp = datetime.strptime(date_str + ' ' + time_str, '%d.%m.%Y %H:%M')

        return timestamp


    # finds the message in quotes inside the message and returns it
    def get_memo(self, msg: MsgContainer):
        return re.search(self.memo_pattern, msg.text).group()
