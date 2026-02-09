import asyncio
import logging

from pyrogram import Client
from pyrogram.errors import (
    PeerFlood,
    UserIsBlocked,
    FloodWait,
    UsernameInvalid,
    UsernameNotOccupied,
    ChatWriteForbidden,
    RPCError,
    SessionPasswordNeeded,
    AuthKeyUnregistered
)
from typing import List
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram.enums.parse_mode import ParseMode
from utils.log_upload import account_err_log

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


async def process_malling(account: str, base: list[str], user_id: int, text: str, bot: Bot, msg_to_del: int, job_id: str, scheduler: AsyncIOScheduler, manager: ClientManager):
    try:
        client = Client(f'accounts/{user_id}_{account.replace(" ", "_")}', api_id=config.user_bot.api_id,
                        api_hash=config.user_bot.api_hash)
        await manager.add_client(user_id, client)
        await client.start()
    except Exception as err:
        print(err)
        account_err_log(f'malling start error: \n{err}\n\n')
        await bot.send_message(
            chat_id=user_id,
            text='❗️Сессия вашего аккаунта слетела, пожалуйста удалите и добавьте в бота данный аккаунт повторно'
        )
        job = scheduler.get_job(job_id)
        if job:
            job.remove()
        return
    delay = 16
    results = {
        "sent": [],
        "failed": [],
        "blocked": [],
        "not_found": [],
        "flood_wait": [],
        "invalid": [],
        "write_forbidden": []
    }
    print(base)
    print('base: ', len(base))
    users = await client.get_users(base)

    for user in users:
        # Очищаем юзернейм
        username = user.username
        clean_username = username.strip().lstrip('@')
        try:
            # Отправляем сообщение
            await client.send_message(clean_username, text, parse_mode=ParseMode.HTML)
            results["sent"].append(clean_username)
            logger.info(f"✅ Сообщение отправлено: @{clean_username}")

        except PeerFlood:
            results["not_found"].append(clean_username)
            logger.warning(f"❌ Пользователь не найден (спам): @{clean_username}")

        except UserIsBlocked:
            results["blocked"].append(clean_username)
            logger.warning(f"🚫 Пользователь заблокировал бота: @{clean_username}")

        except UsernameInvalid:
            results["invalid"].append(username)
            logger.warning(f"⚠️ Неверный формат юзернейма: {username}")

        except UsernameNotOccupied:
            results["not_found"].append(clean_username)
            logger.warning(f"❌ Юзернейм не занят: @{clean_username}")

        except ChatWriteForbidden:
            results["write_forbidden"].append(clean_username)
            logger.warning(f"⛔ Нет прав на отправку: @{clean_username}")

        except FloodWait as e:
            # Важно: нужно подождать указанное время
            wait_seconds = e.value
            logger.error(f"⏱️ FloodWait: ждём {wait_seconds} секунд...")
            await asyncio.sleep(wait_seconds + 10)
            # Можно повторить попытку, но лучше остановиться
            results["flood_wait"].append({"username": clean_username, "wait": wait_seconds})
            break  # Прерываем, чтобы не продолжать после большого wait

        except RPCError as e:
            results["failed"].append({"username": clean_username, "error": str(e)})
            logger.error(f"❌ RPC ошибка при отправке @{clean_username}: {e}")

        except (SessionPasswordNeeded, AuthKeyUnregistered):
            try:
                await client.stop()
            except Exception:
                ...
            try:
                await bot.delete_message(
                    chat_id=user_id,
                    message_id=msg_to_del
                )
            except Exception:
                ...
            text = ("📬 Рассылка завершена\n"
                    f"✅ Успешно: {len(results['sent'])}\n"
                    f"🚫 Заблокировали: {len(results['blocked'])}\n"
                    f"❌ Не найдены (спам): {len(results['not_found'])}\n"
                    f"⏸️ Отброшены в спам: {len(results['flood_wait'])}\n"
                    f"⚠️ Неверный формат юзернейма: {len(results['invalid'])}\n"
                    f"⛔ Нет прав на отправку: {len(results['write_forbidden'])}\n"
                    f"❌ Неизвестная ошибка: {len(results['failed'])}")
            await bot.send_message(
                chat_id=user_id,
                text=text
            )
            await bot.send_message(
                chat_id=user_id,
                text='❗️Telegram сбросил сессию вашего аккаунта из-за спама, '
                     'пожалуйста удалите и добавьте в бота данный аккаунт повторно'
            )
            job = scheduler.get_job(job_id)
            if job:
                job.remove()
            return

        except Exception as e:
            results["failed"].append({"username": clean_username, "error": str(e)})
            logger.error(f"❌ Неизвестная ошибка с @{clean_username}: {e}")

        # Задержка между сообщениями
        await asyncio.sleep(delay)
    await client.stop()
    print("📬 Рассылка завершена")
    print(f"✅ Успешно: {len(results['sent'])}")
    print(f"🚫 Заблокировали: {len(results['blocked'])}")
    print(f"❌ Не найдены: {len(results['not_found'])}")
    print(f"⏸️ FloodWait: {len(results['flood_wait'])}")

    text = ("📬 Рассылка завершена\n"
            f"✅ Успешно: {len(results['sent'])}\n"
            f"🚫 Заблокировали: {len(results['blocked'])}\n"
            f"❌ Не найдены (спам): {len(results['not_found'])}\n"
            f"⏸️ Отброшены в спам: {len(results['flood_wait'])}\n"
            f"⚠️ Неверный формат юзернейма: {len(results['invalid'])}\n"
            f"⛔ Нет прав на отправку: {len(results['write_forbidden'])}\n"
            f"❌ Неизвестная ошибка: {len(results['failed'])}")
    try:
        await bot.delete_message(
            chat_id=user_id,
            message_id=msg_to_del
        )
    except Exception:
        ...
    await bot.send_message(
        chat_id=user_id,
        text=text
    )
    job = scheduler.get_job(job_id)
    if job:
        job.remove()


async def test_func():
    app: Client = Client('1236300146_Leggit_Mail')
    async with app:
        user = await app.get_users('@Dyrachekk')
        print(user.full_name)
        print(user.__dict__)


#asyncio.run(test_func())
