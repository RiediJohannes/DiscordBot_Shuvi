class Reminder:

    def __init__(self, user_id=178992018788188162, channel_id=955511857156857949, due_date=None, memo='Keine Nachricht spezifiziert'):
        self.user_id = user_id   # defaults to my account 'Luigi-Fan'
        self.channel_id = channel_id    # defaults to 'bot' channel on my private 'SR388' server
        self.memo = memo
        self.due_date = due_date

