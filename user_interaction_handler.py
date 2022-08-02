import asyncio

from msg_container import MsgContainer
from quote_server import QuoteServer as Quotes


class UserInteractionHandler:

    def __init__(self, bot, msg: MsgContainer):
        self.bot = bot
        self.msg = msg
        self.task_messages: int = 1     # counts the messages needed for the confirmation process in order to e.g. delete them afterwards
        self.retry_counter: int = 0     # counts the retries for a given question; the caller can set a maximum of retries


    async def get_confirmation(self, question: str, abort_msg: str, timeout_msg=None, retry_msg=None, enough_msg=None, retries=5) -> [bool, int]:
        # keep all the kwargs for the recursive function call later
        arguments = vars()
        del arguments['self']

        # set the default message wherever there was no message given
        if retry_msg is None:
            retry_msg = Quotes.get_quote('userInteraction/retry').format(self.bot)
        if timeout_msg is None:
            timeout_msg = Quotes.get_quote('userInteraction/timeout').format(self.bot)
        if enough_msg is None:
            enough_msg = Quotes.get_quote('userInteraction/enough').format(self.bot)

        try:  # ask the user for confirmation with a predetermined question
            await self.msg.post(question)
            self.task_messages += 1
            answer = await self.listen(timeout=30.0)    # listen for the next user message

        # if you don't receive an answer until timeout, give up
        except asyncio.TimeoutError:
            await self.msg.post(timeout_msg)
            return False, 0

        else:
            # if the user agreed
            if answer.casefold() in Quotes.get_choices('affirmations'):
                self.task_messages += 1
                self.retry_counter = 0
                return True, self.task_messages

            # if the user rejected
            elif answer.casefold() in Quotes.get_choices('rejections'):
                await self.msg.post(abort_msg)
                self.task_messages += 2  # the abort_msg and the user's previous reply -> 2 messages
                self.retry_counter = 0
                return False, self.task_messages

            # if the user responded with something weird
            else:
                # increment the retry counter and check if we already reached the retry limit
                self.retry_counter += 1
                if self.retry_counter >= retries:
                    await self.msg.post(enough_msg)
                    self.retry_counter = 0
                    return False, self.task_messages + 2

                await self.msg.post(retry_msg)
                self.task_messages += 2  # the retry_msg and the user's previous reply -> 2 messages
                # call this function recursively until a proper answer is given
                return await self.get_confirmation(**arguments)


    async def get_response(self, question=None, timeout_msg=None, timeout=120.0, hint_msg=None, hint_on_try=3) -> str | None:
        if question:
            # post the question
            await self.msg.post(question)
        # if a hint was given, check if it's time for the hint
        if hint_msg:
            self.retry_counter += 1
            if self.retry_counter == hint_on_try:
                await self.msg.post(hint_msg)
        try:
            answer = await self.listen(timeout=timeout)    # listen for the next user message
            return answer
        # in case we run into a timeout
        except asyncio.TimeoutError:
            if timeout_msg is None:
                timeout_msg = Quotes.get_quote('userInteraction/timeout').format(self.bot)
            return await self.msg.post(timeout_msg)     # in this case None is returned!


    # just send a message in the correct channel without having to know the message's origin
    async def talk(self, message: str) -> None:
        return await self.msg.post(message)


    # listen for the next message that isn't empty; may throw an asyncio.TimeoutError(!)
    async def listen(self, timeout=None) -> str:
        # wait for the next message of the regarded user in the regarded channel
        message = await self.bot.wait_for("message", check=lambda ans: ans.author == self.msg.user and ans.channel == self.msg.chat, timeout=timeout)
        # if the message's content was none (image, gif), wait again
        if message.content is None:
            return await self.listen()
        # else return the text of the message
        return message.content
