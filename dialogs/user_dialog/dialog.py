from aiogram.types import ContentType
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import SwitchTo, Column, Row, Button, Group, Select, Start, Url, Back
from aiogram_dialog.widgets.text import Format, Const
from aiogram_dialog.widgets.input import TextInput, MessageInput
from aiogram_dialog.widgets.media import DynamicMedia

from dialogs.user_dialog import getters

from states.state_groups import startSG, adminSG

user_dialog = Dialog(
    Window(
        Const('Приветственный текст'),
        Column(
            Button(Const('✉️Запустить рассылку'), id='mail_account_choose', on_click=getters.choose_account_switcher),
            Button(Const('🗂Собрать базу'), id='base_account_choose', on_click=getters.choose_account_switcher),

            SwitchTo(Const('👥Управление аккаунтами'), id='accounts_switcher', state=startSG.accounts),
            Start(Const('Админ панель'), id='admin', state=adminSG.start, when='admin')
        ),
        getter=getters.start_getter,
        state=startSG.start
    ),
    Window(
        Const('Выберите аккаунт с которого будет воспроизводиться рассылка'),
        Group(
            Select(
                Format("{item[0]}"),
                id='choose_account_builder',
                item_id_getter=lambda x: x[1],
                items='items',
                on_click=getters.choose_account_selector
            ),
            width=1
        ),
        SwitchTo(Const('⬅️Назад'), id='back', state=startSG.start),
        getter=getters.choose_account_getter,
        state=startSG.choose_account
    ),
    Window(
        DynamicMedia('document', when='document'),
        Const('Введите юзернеймы, которым надо будет рассылать сообщение по инструкции приложенной ниже⬇️\n\n'
              '<b>❗️В базе должно быть не больше 50 человек</b>'),
        TextInput(
            id='get_usernames',
            on_success=getters.get_usernames
        ),
        MessageInput(
            func=getters.get_table_usernames,
            content_types=ContentType.DOCUMENT
        ),
        SwitchTo(Const('✅База собранна'), id='get_message_switcher', state=startSG.get_message),
        Url(Const('📋Инструкция'), id='manual_url',
            url=Const('https://telegra.ph/Instrukciya-po-ispolzovaniyu-bota-08-09')),
        SwitchTo(Const('⬅️Назад'), id='back_choose_account', state=startSG.choose_account),
        getter=getters.get_usernames_getter,
        state=startSG.get_usernames
    ),
    Window(
        Const('Отправьте сообщение, которое надо будет разослать по базе'),
        MessageInput(
            func=getters.get_message,
            content_types=ContentType.ANY
        ),
        SwitchTo(Const('⬅️Назад'), id='back_get_usernames', state=startSG.get_usernames),
        state=startSG.get_message
    ),
    Window(
        Const('Вы подтверждаете, рассылку сообщения по собранной базе пользователей'),
        Row(
            Button(Const('Запуск'), id='start_malling', on_click=getters.start_malling),
            Button(Const('Отмена'), id='cancel_malling', on_click=getters.cancel_malling),
        ),
        SwitchTo(Const('⬅️Назад'), id='back_get_message', state=startSG.get_message),
        state=startSG.confirm_malling
    ),
    Window(
        Format('🗂<b>Кол-во человек в базе:</b> {users}'),
        Const('Введите ссылку на канал с которого надо будет собрать базу пользователей'
              '\n<em>❗️Если же канал является закрытым, то перешлите любое сообщение из данного канала, чтобы'
              ' бот смог вручную достать необходимые данные</em>'),
        TextInput(
            id='get_channel_link',
            on_success=getters.get_channel
        ),
        MessageInput(
            func=getters.get_forward_message,
            content_types=ContentType.ANY
        ),
        Column(
            Button(Const('⤵️Выгрузить базу'), id='get_type_switcher', on_click=getters.get_type_switcher),
            SwitchTo(Const('💬Мои каналы|чаты'), id='my_channels_switcher', state=startSG.my_channels),
        ),
        SwitchTo(Const('⬅️Назад'), id='back', state=startSG.start),
        getter=getters.collect_base_getter,
        state=startSG.collect_base
    ),
    Window(
        Const('Выберите способ выгрузки контактов'),
        Column(
            Button(Const('📝Текстом'), id='text_type_choose', on_click=getters.type_choose),
            Button(Const('📓Таблицей'), id='table_type_choose', on_click=getters.type_choose),
        ),
        SwitchTo(Const('⬅️Назад'), id='back_collect_base', state=startSG.collect_base),
        state=startSG.choose_get_type
    ),
    Window(
        Const('Выберите канал | чат для сбора базы'),
        Group(
            Select(
                Format('{item[0]}'),
                id='my_chats_builder',
                item_id_getter=lambda x: x[1],
                items='items',
                on_click=getters.my_chat_selector
            ),
            width=1
        ),
        Row(
            Button(Const('◀️'), id='back_my_chat_pager', on_click=getters.my_channels_pager, when='not_first'),
            Button(Format('{open_page}/{last_page}'), id='pager'),
            Button(Const('▶️'), id='next_my_chat_pager', on_click=getters.my_channels_pager, when='not_last'),
        ),
        SwitchTo(Const('⬅️Назад'), id='back_collect_base', state=startSG.collect_base),
        getter=getters.my_channels_getter,
        state=startSG.my_channels
    ),
    Window(
        Format('<b>Меню привязки аккаунтов</b>\n\n{text}'),
        Column(
            SwitchTo(Const('➕Добавить аккаунт'), id='add_account', state=startSG.get_name),
            SwitchTo(Const('🗑Удалить аккаунт'), id='del_account_switcher', state=startSG.del_account)
        ),
        SwitchTo(Const('⬅️Назад'), id='back', state=startSG.start),
        getter=getters.accounts_getter,
        state=startSG.accounts
    ),
    Window(
        Const('Нажмите на аккаунт, вы хотели бы удалить👇'),
        Group(
            Select(
                Format("{item[0]}"),
                id='del_account_builder',
                item_id_getter=lambda x: x[1],
                items='items',
                on_click=getters.del_account_selector
            ),
            width=1
        ),
        Back(Const('⬅️Назад'), id='back_accounts'),
        getter=getters.del_account_getter,
        state=startSG.del_account
    ),
    Window(
        Format('Вы подтверждаете удаление аккаунта <em>"{name}"</em>?'),
        Column(
            Button(Const('🗑Удалить'), id='confirm_account_del', on_click=getters.del_account),
            SwitchTo(Const('❌Отмена'), id='back_accounts', state=startSG.accounts),
        ),
        getter=getters.del_account_confirm_getter,
        state=startSG.del_account_confirm
    ),
    Window(
        Const('Введите название для аккаунта'),
        TextInput(
            id='get_name',
            on_success=getters.get_name
        ),
        SwitchTo(Const('⬅️Назад'), id='back_accounts', state=startSG.accounts),
        state=startSG.get_name
    ),
    Window(
        Const('Отправьте номер телефона'),
        SwitchTo(Const('Отмена'), id='back', state=startSG.start),
        TextInput(
            id='get_phone',
            on_success=getters.phone_get,
        ),
        Back(Const('⬅️Назад'), id='back_get_name'),
        state=startSG.add_account
    ),
    Window(
        Const('Введи код который пришел на твой аккаунт в телеграмм в формате: 1-2-3-5-6'),
        TextInput(
            id='get_kod',
            on_success=getters.get_kod,
        ),
        state=startSG.kod_send
    ),
    Window(
        Const('Пароль от аккаунта телеграмм'),
        TextInput(
            id='get_password',
            on_success=getters.get_password,
        ),
        state=startSG.get_password
    )
)