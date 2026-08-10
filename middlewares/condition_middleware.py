import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, User
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.action_data_class import DataInteraction
from states.state_groups import AuthorizeSG
from config_data.config import load_config, Config

config: Config = load_config()
logger = logging.getLogger(__name__)


class RemindMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get('event_from_user')
        bot: Bot = data.get('bot')
        print(data)
        context: FSMContext = data.get('state')
        db: DataInteraction = data.get('session')

        if user is None:
            return await handler(event, data)

        session: DataInteraction = data.get('session')
        await session.set_activity(user_id=user.id)

        result = await handler(event, data)
        db_user = await db.get_user(user.id)
        if not db_user.authorized:
            await bot.send_message(
                chat_id=user.id,
                text='Чтобы продолжить пользоваться ботом введите пароль:'
            )
            await context.set_state(AuthorizeSG.get_password)
            return
        return result
