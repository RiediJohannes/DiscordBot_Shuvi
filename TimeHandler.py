import discord as d
import re
import datetime

class TimeHandler:

    def __init__(self):
        self.date_pattern = '(?:0?[1-9]|[12][0-9]|3[01])[-/.](?:0?[1-9]|1[012])[-/.](?:(?:20)?[0-9]{2})'
        self.time_pattern = '(?:0?[0-9]|1[0-9]|2[0-3])[:](?:[0-5][0-9])'
        self.memo_pattern = '(?<=\").*(?=\")'


    def get_timestamp(self, msg: d.message):

        # read date and time in message
        date = re.search(self.date_pattern, msg.content).group()
        time = re.search(self.time_pattern, msg.content).group()
        memo = re.search(self.memo_pattern, msg.content).group()

        return date, time, memo
