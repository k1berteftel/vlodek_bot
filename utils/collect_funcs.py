import logging
import asyncio
from datetime import datetime

from aiogram import Bot
from pyrogram import Client
from pyrogram.enums.chat_type import ChatType
from pyrogram.errors import FloodWait

from clientManager.session_storage import ClientManager
from config_data.config import load_config, Config


config: Config = load_config()

format = '[{asctime}] #{levelname:8} {filename}:' \
         '{lineno} - {name} - {message}'

logging.basicConfig(
    level=logging.INFO,
    format=format,
    style='{'
)

logger = logging.getLogger(__name__)


api_id = config.user_bot.api_id
api_hash = config.user_bot.api_hash


async def collect_users_base(account: str, bot: Bot, user_id: int, channel: str | int, usernames: list[str]) -> list[
                                                                                                                  str] | None:
    """Сбор базы пользователей (без детального прогресса)"""
    users = []
    try:
        app = Client(account, api_id=api_id, api_hash=api_hash)
    except Exception as err:
        print(err)
        await bot.send_message(
            chat_id=user_id,
            text='❗️Сессия вашего аккаунта слетела, пожалуйста удалите и добавьте в бота данный аккаунт повторно'
        )
        return None

    async with app:
        chat = await app.get_chat(channel)
        channel_type = chat.type
        if chat.type == ChatType.CHANNEL:
            channel = chat.linked_chat.id if chat.linked_chat else None
            channel_type = ChatType.SUPERGROUP
            print(channel)
        if not channel:
            return None

        new_users = []
        members = app.get_chat_members(channel)

        try:
            # Отправляем уведомление о начале сбора
            await bot.send_message(
                chat_id=user_id,
                text="🔄 Начинаю сбор базы пользователей с канала..."
            )

            async for user in members:
                if user.user.username and not user.user.is_bot and not user.user.is_contact and not user.user.verification_status.is_fake:
                    if user.user.username not in users and user.user.username not in usernames:
                        new_users.append(user.user.username)

            if len(new_users) > 50 and channel_type != ChatType.SUPERGROUP:
                users.extend(new_users)
            else:
                attempts = 0
                max_attempts = 5

                while attempts < max_attempts:
                    try:
                        async for message in app.get_chat_history(channel):
                            user = message.from_user
                            if user and (
                                    not user.is_bot and not user.verification_status.is_fake) and user.username and user.username not in users:
                                if user.username not in new_users and user.username not in usernames:
                                    new_users.append(user.username)
                        # Если дошли до этой точки - успешно собрали историю
                        break

                    except FloodWait as e:
                        wait_time = e.value
                        attempts += 1
                        if attempts < max_attempts:
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"⏳ Получена ошибка FloodWait. Жду {wait_time} секунд перед повторной попыткой {attempts}/{max_attempts}..."
                            )
                            await asyncio.sleep(wait_time + 1)  # +1 секунда для надежности
                        else:
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"❌ Не удалось собрать историю сообщений после {max_attempts} попыток. Продолжаю с тем, что удалось собрать."
                            )
                    except Exception as e:
                        print(f"Ошибка при сборе истории: {e}")
                        break

                users.extend(new_users)

        except Exception as err:
            print(err, err.args, err.__traceback__)

    # Уведомление о завершении сбора
    await bot.send_message(
        chat_id=user_id,
        text=f"✅ Сбор базы завершен! Найдено пользователей: {len(users)}\n"
    )

    return users if users else None


async def filter_user_base(account: str, channel: str | int, user_id: int, bot: Bot, users: list[str]):
    """Основная функция фильтрации с прогресс-отчетами"""
    base = await collect_users_base(f'accounts/{user_id}_{account.replace(" ", "_")}', bot, user_id, channel, users)
    if not base:
        return None
    return base


async def get_channels(account: str, bot: Bot, user_id: int, manager: ClientManager):
    try:
        app = Client(f'accounts/{user_id}_{account.replace(" ", "_")}', api_id=config.user_bot.api_id, api_hash=config.user_bot.api_hash)
        await manager.add_client(user_id, app)
        await app.start()
    except Exception as err:
        print(err)
        await bot.send_message(
            chat_id=user_id,
            text='❗️Сессия вашего аккаунта слетела, пожалуйста удалите и добавьте в бота данный аккаунт повторно'
        )
        return
    dialogs = []
    async for dialog in app.get_dialogs():
        if dialog.chat.type not in [ChatType.BOT, ChatType.PRIVATE]:
            dialogs.append(
                (
                    dialog.chat.title,
                    dialog.chat.id
                )
            )
    return dialogs