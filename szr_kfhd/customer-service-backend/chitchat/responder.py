# itwwy/chitchat/responder.py
from itertools import chain

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from domain.messages import UserMessage, BotMessage
from domain.state import Turn
from prompts.history_builder import HistoryBuilder
from prompts.loader import load_prompt
from infrastructure.llm import llm

class ChitChatResponder:

    async def respond(self,
                      user_message: UserMessage,
                      recent_turns: list[Turn]):

        # 格式化一下消息
        user_message = HistoryBuilder._render_user_message(user_message)
        # 把整个历史对话串起来
        history = HistoryBuilder.build(recent_turns)

        prompt_text = load_prompt("chitchat_respond")
        prompt = PromptTemplate.from_template(prompt_text, template_format="jinja2")
        chain = prompt | llm | StrOutputParser()
        response = await chain.ainvoke({
            "user_message": user_message,
            "history": history,
        })
        return [BotMessage(text=response)]

