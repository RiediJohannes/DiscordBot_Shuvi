from MsgContainer import MsgContainer
import asyncio

class ConfirmationPrompt:

    affirmations = ['yes', 'y', 'ja', 'jo', 'j', 'hai']
    rejections = ['no', 'n', 'nein', 'na', 'nö', 'nope', 'stop', 'cancel', 'iie']

    def __init__(self, bot, msg: MsgContainer):
        self.bot = bot
        self.msg = msg
        self.default_retry_msg = f'Das beantwortet nicht {bot.name}\'s Frage'
        self.default_timeout_msg = f'Hm, da kommt ja doch nichts mehr... _[Vorgang abgebrochen]_'
        # we also want to count the messages needed for the confirmation process in order to e.g. delete them afterwards
        self.task_messages = 1


    async def get_confirmation(self, question, abort_msg, timeout_msg=None, retry_msg=None):
        if retry_msg is None:
            retry_msg = self.default_retry_msg
        if timeout_msg is None:
            timeout_msg = self.default_timeout_msg

        try:  # ask the user for confirmation with a predetermined question
            await self.msg.post(question)
            self.task_messages += 1
            answer = await self.bot.wait_for("message", check=lambda ans: ans.author == self.msg.user and ans.channel == self.msg.chat, timeout=30.0)

        # if you don't receive an answer until timeout, give up
        except asyncio.TimeoutError:
            await self.msg.post(timeout_msg)
            return False, 0

        else:
            # if the user agreed
            if answer.content.casefold() in self.affirmations:
                self.task_messages += 1
                return True, self.task_messages

            # if the user rejected
            elif answer.content.casefold() in self.rejections:
                await self.msg.post(abort_msg)
                self.task_messages += 2     # the abort_msg and the user's previous reply -> 2 messages
                return False, self.task_messages

            # if the user responded with something weird
            else:
                await self.msg.post(retry_msg)
                self.task_messages += 2    # the retry_msg and the user's previous reply -> 2 messages
                # call this function recursively until a proper answer is given
                return await self.get_confirmation(question=question, abort_msg=abort_msg, timeout_msg=timeout_msg, retry_msg=retry_msg), self.task_messages
