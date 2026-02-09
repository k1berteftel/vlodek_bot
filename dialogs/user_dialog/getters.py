import os

from aiogram import Bot
from aiogram.types import CallbackQuery, User, Message, FSInputFile, ContentType
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from pyrogram.types import SentCode
from pyrogram.errors import PasswordHashInvalid

from clientManager.session_storage import ClientManager
from utils.malling_funcs import process_malling
from utils.build_ids import get_random_id
from utils.collect_funcs import filter_user_base, get_channels
from utils.usernames_utils import add_usernames
from utils.tables_parse import load_usernames, get_table
from database.action_data_class import DataInteraction
from config_data.config import load_config, Config
from states.state_groups import startSG


config: Config = load_config()


async def start_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    admin = False
    admins = [*config.bot.admin_ids]
    admins.extend([admin.user_id for admin in await session.get_admins()])
    if event_from_user.id in admins:
        admin = True
    return {'admin': admin}


async def collect_base_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    base = dialog_manager.dialog_data.get('users')
    if not base:
        base = []
        dialog_manager.dialog_data['users'] = base
    return {'users': len(base)}


async def choose_account_switcher(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    select = clb.data.split('_')[0]
    dialog_manager.dialog_data['select'] = select
    await dialog_manager.switch_to(startSG.choose_account)


async def clean_base(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data['users'] = None
    await clb.answer('База пользователей была успешно почищена')
    await dialog_manager.switch_to(startSG.collect_base)


async def get_channel(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    try:
        text = int(text)
    except Exception as err:
        print(err)
        if 't.me' not in text:
            await msg.answer('❗️Вы ввели ссылку не в том формате, пожалуйста попробуйте снова')
            return
        try:
            text = text.split('/')[-1]
        except Exception:
            await msg.answer('❗️Вы ввели ссылку не в том формате, пожалуйста попробуйте снова')
            return
    account_id = dialog_manager.dialog_data.get('account_id')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    manager: ClientManager = dialog_manager.middleware_data.get('session_manager')
    await manager.clear_client(msg.from_user.id)
    account = await session.get_account(account_id)
    message = await msg.answer('Начался процесс сбора базы')
    users = dialog_manager.dialog_data.get('users')
    users = await filter_user_base(account.account_name, text, msg.from_user.id, msg.bot, users)
    if not users:
        await msg.answer('❗️При сборе базы произошла какая-то ошибка пожалуйста попробуйте снова')
        await dialog_manager.switch_to(startSG.collect_base)
        return
    dialog_manager.dialog_data['users'] = users
    await message.delete()
    await dialog_manager.switch_to(startSG.collect_base)


async def get_forward_message(msg: Message, widget: MessageInput, dialog_manager: DialogManager):
    if msg.forward_from_chat is None:
        await msg.answer('❗️К сожалению невозможно получить данные о канале из-за правил конфиденциальности канала')
        return
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account_id = dialog_manager.dialog_data.get('account_id')
    manager: ClientManager = dialog_manager.middleware_data.get('session_manager')
    await manager.clear_client(msg.from_user.id)
    account = await session.get_account(account_id)
    users = dialog_manager.dialog_data.get('users')
    users = await filter_user_base(account.account_name, msg.forward_from_chat.id, msg.from_user.id, msg.bot, users)
    if not users:
        await msg.answer('❗️При сборе базы произошла какая-то ошибка пожалуйста попробуйте снова')
        await dialog_manager.switch_to(startSG.collect_base)
        return
    dialog_manager.dialog_data['users'] = users
    await dialog_manager.switch_to(startSG.collect_base)


async def my_channels_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    page = dialog_manager.dialog_data.get('chat_page')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account_id = dialog_manager.dialog_data.get('account_id')
    manager: ClientManager = dialog_manager.middleware_data.get('session_manager')
    await manager.clear_client(event_from_user.id)
    account = await session.get_account(account_id)
    bot: Bot = dialog_manager.middleware_data.get('bot')
    if not page:
        page = 0
        dialog_manager.dialog_data['chat_page'] = page
    dialogs = dialog_manager.dialog_data.get('chats')
    if not dialogs:
        dialogs = await get_channels(account.account_name, bot, event_from_user.id, manager)
        dialogs = [dialogs[i:i + 20] for i in range(0, len(dialogs), 20)]
        dialog_manager.dialog_data['chats'] = dialogs
    not_first = True
    not_last = True
    if page == 0:
        not_first = False
    if page == len(dialogs) - 1:
        not_last = False
    return {
        'items': dialogs[page],
        'not_first': not_first,
        'not_last': not_last,
        'open_page': str(page + 1),
        'last_page': str(len(dialogs))
    }


async def my_channels_pager(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    page = dialog_manager.dialog_data.get('chat_page')
    if clb.data.startswith('back'):
        dialog_manager.dialog_data['chat_page'] = page - 1
    else:
        dialog_manager.dialog_data['chat_page'] = page + 1
    await dialog_manager.switch_to(startSG.my_channels)


async def my_chat_selector(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str):
    await clb.answer('Начался процесс считывания базы пользователей, пожалуйста ожидайте')
    users = dialog_manager.dialog_data.get('users')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    manager: ClientManager = dialog_manager.middleware_data.get('session_manager')
    await manager.clear_client(clb.from_user.id)
    account_id = dialog_manager.dialog_data.get('account_id')
    account = await session.get_account(account_id)
    users = await filter_user_base(account.account_name, int(item_id), clb.from_user.id, clb.bot, users)
    if not users:
        await clb.message.answer('❗️При сборе базы произошла какая-то ошибка пожалуйста попробуйте снова')
        await dialog_manager.switch_to(startSG.collect_base)
        return
    dialog_manager.dialog_data['users'] = users
    await dialog_manager.switch_to(startSG.collect_base)


async def get_type_switcher(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    users = dialog_manager.dialog_data.get('users')
    if not users:
        await clb.answer('❗️Перед тем как перейти в выгрузке соберите хотя бы минимальную базу')
        return
    await dialog_manager.switch_to(startSG.choose_get_type)


async def type_choose(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    discharge = clb.data.split('_')[0]
    users = dialog_manager.dialog_data.get('users')
    if discharge == 'text':
        text = ''
        for username in users:
            if len(text) >= 4050:
                await clb.message.answer(text)
                text = ''
            text += '@' + username + '\n'
        await clb.message.answer(text)
    else:
        usernames = ['@' + username for username in users]
        table = get_table(usernames, f'База_{clb.from_user.id}')
        await clb.message.answer_document(
            document=FSInputFile(path=table)
        )
        try:
            os.remove(table)
        except Exception:
            ...
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.start, show_mode=ShowMode.DELETE_AND_SEND)


async def choose_account_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    accounts = await session.get_user_accounts(event_from_user.id)
    buttons = []
    for account in accounts:
        buttons.append(
            (account.account_name, account.id)
        )
    return {'items': buttons}


async def choose_account_selector(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str):
    select = dialog_manager.dialog_data.get('select')
    dialog_manager.dialog_data.clear()
    dialog_manager.dialog_data['account_id'] = int(item_id)
    if select == 'mail':
        await dialog_manager.switch_to(startSG.get_usernames)
    else:
        await dialog_manager.switch_to(startSG.collect_base)


async def get_usernames_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    document = None
    base = dialog_manager.dialog_data.get('base')
    if not base:
        base = []
        dialog_manager.dialog_data['base'] = base
    if base:
        document = get_table(base, f'Пользователи_{event_from_user.id}')
        document = MediaAttachment(path=document, type=ContentType.DOCUMENT)
    return {'document': document}


async def get_table_usernames(msg: Message, widget: MessageInput, dialog_manager: DialogManager):
    try:
        usernames = await load_usernames(msg.bot, msg)
    except Exception:
        await msg.answer('❗️Таблица должна быть в формате .csv или .xlsx, пожалуйста попробуйте снова')
        return
    base = dialog_manager.dialog_data.get('base')
    base = add_usernames(usernames, base)
    dialog_manager.dialog_data['base'] = base
    await dialog_manager.switch_to(startSG.get_usernames)


async def get_usernames(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    text.strip()
    usernames = text.strip().split('\n')
    new_data = []
    for username in usernames:
        if username.startswith('@'):
            new_data.append(username)
    base = dialog_manager.dialog_data.get('base')
    base = add_usernames(new_data, base)
    dialog_manager.dialog_data['base'] = base
    await dialog_manager.switch_to(startSG.get_usernames)


async def get_message(msg: Message, widget: MessageInput, dialog_manager: DialogManager):
    dialog_manager.dialog_data['text'] = msg.html_text
    await dialog_manager.switch_to(startSG.confirm_malling)


async def cancel_malling(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.start)


async def start_malling(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    scheduler: AsyncIOScheduler = dialog_manager.middleware_data.get('scheduler')
    account_id = dialog_manager.dialog_data.get('account_id')
    manager: ClientManager = dialog_manager.middleware_data.get('session_manager')
    await manager.clear_client(clb.from_user.id)
    base = dialog_manager.dialog_data.get('base')
    text = dialog_manager.dialog_data.get('text')
    account = await session.get_account(account_id)
    msg = await clb.message.answer('📤Начался процесс рассылки по базе пользователей, '
                                   'обычно он занимает от 3 до 15 минут в зависимости от собранной базы, '
                                   'пожалуйста ожидайте\nПо завершению рассылки вы получите уведомление')
    job_id = f'{clb.from_user.id}_{account_id}'
    job = scheduler.get_job(job_id)
    if job:
        await clb.answer('❗️В данный момент на этом аккаунте уже запущенна, задача, пожалуйста дождитесь ее завершения')
        return
    scheduler.add_job(
        process_malling,
        'interval',
        args=[account.account_name, base, clb.from_user.id, text, clb.bot, msg.message_id, job_id, scheduler, manager],
        id=job_id
    )
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.start)


async def accounts_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    accounts = await session.get_user_accounts(event_from_user.id)
    text = ''
    if accounts:
        text = 'Добавленные аккаунты:\n'
        count = 1
        for account in accounts:
            text += f'\t{count} - {account.account_name}'
            count += 1
    return {'text': text}


async def del_account_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    accounts = await session.get_user_accounts(event_from_user.id)
    buttons = []
    for account in accounts:
        buttons.append(
            (account.account_name, account.id)
        )
    return {'items': buttons}


async def del_account_selector(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str):
    dialog_manager.dialog_data['account_id'] = int(item_id)
    await dialog_manager.switch_to(startSG.del_account_confirm)


async def del_account_confirm_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account_id = dialog_manager.dialog_data.get('account_id')
    manager: ClientManager = dialog_manager.middleware_data.get('session_manager')
    await manager.clear_client(event_from_user.id)
    account = await session.get_account(account_id)
    return {'name': account.account_name}


async def del_account(clb: CallbackQuery, button: Button, dialog_manager: DialogManager):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account_id = dialog_manager.dialog_data.get('account_id')
    manager: ClientManager = dialog_manager.middleware_data.get('session_manager')
    await manager.clear_client(clb.from_user.id)
    account = await session.get_account(account_id)
    await session.del_account(account_id)
    try:
        os.remove(f'accounts/{clb.from_user.id}_{account.account_name.replace(" ", "_")}.session')
        os.remove(f'accounts/{clb.from_user.id}_{account.account_name.replace(" ", "_")}.session-journal')
    except Exception:
        ...
    await clb.answer('Аккаунт был успешно удален')
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.accounts)


async def get_name(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    if text in [account.account_name for account in await session.get_user_accounts(msg.from_user.id)]:
        await msg.answer('❗️У вас уже есть аккаунт с таким названием, пожалуйста придумайте другое название')
        return
    dialog_manager.dialog_data['name'] = text
    await dialog_manager.switch_to(startSG.add_account)


async def phone_get(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    print('Начало соединения')
    name = dialog_manager.dialog_data.get('name')
    manager: ClientManager = dialog_manager.middleware_data.get('session_manager')
    await manager.clear_client(msg.from_user.id)
    client = Client(f'accounts/{msg.from_user.id}_{name.replace(" ", "_")}', config.user_bot.api_id, config.user_bot.api_hash)
    await manager.add_client(msg.from_user.id, client)
    await client.connect()
    print(text, type(text))
    try:
        print('Отправка кода')
        sent_code_info: SentCode = await client.send_code(text.strip())
    except Exception as err:
        print(err)
        await msg.answer('❗️Веденный номер телефона неверен, попробуйте снова')
        return
    dialog_manager.dialog_data['client'] = client
    dialog_manager.dialog_data['phone_info'] = sent_code_info
    dialog_manager.dialog_data['phone_number'] = text
    await dialog_manager.switch_to(state=startSG.kod_send)


async def get_kod(message: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    name = dialog_manager.dialog_data.get('name')
    client: Client = dialog_manager.dialog_data.get('client')
    phone_info: SentCode = dialog_manager.dialog_data.get('phone_info')
    phone = dialog_manager.dialog_data.get('phone_number')
    code = ''
    if len(text.split('-')) != 5:
        await message.answer(text='❗️Вы отправили код в неправильном формате, попробуйте вести код снова')
        return
    for number in text.split('-'):
        code += number
    print(code)
    try:
        await client.sign_in(phone, phone_info.phone_code_hash, code)
        await client.disconnect()
        await session.add_user_account(message.from_user.id, name)
        dialog_manager.dialog_data.clear()
        await dialog_manager.switch_to(state=startSG.accounts)
    except Exception as err:
        print(err)
        await dialog_manager.switch_to(state=startSG.get_password)


async def get_password(message: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    client: Client = dialog_manager.dialog_data.get('client')
    manager: ClientManager = dialog_manager.middleware_data.get('session_manager')
    name = dialog_manager.dialog_data.get('name')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    dialog_manager.dialog_data.clear()
    try:
        await client.check_password(text)
        await client.disconnect()
        await session.add_user_account(message.from_user.id, name)
        await message.answer(text='✅Ваш аккаунт был успешно добавлен')
        await dialog_manager.switch_to(state=startSG.accounts)
        await manager.clear_client(message.from_user.id)
    except PasswordHashInvalid as err:
        print(err)
        await message.answer(text='❗️Введенные данные были неверны, пожалуйста попробуйте авторизоваться снова')
        await dialog_manager.switch_to(state=startSG.get_name)

