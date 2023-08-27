import json
import logging
from time import sleep
import os
import subprocess
import re

from transliterate import translit
import requests

from file_manager import trash_delete, make_qr, wghub_editing, apply_changes

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from settings import (
    TELE_TOKEN,
    EASY_WG_QUICK_DIR,
    CLIENTS_DIR,
    EASY_WG_QUICK_SCR,
    WG_ETC_PATH,
    ALLOWED_USERS,
    DEV,
    LOAD_TIME
)

from db import Client

if not DEV:
    import sub_check

logger = logging.getLogger(__name__)

ENTER_FIRST_NAME, \
    ENTER_LAST_NAME, \
    ENTER_PHONE_NUMBER, \
    ENTER_SUBSCRIBE_STATUS, \
    ENTER_SUBSCRIBE_DURATION, \
    ENTER_DEVICE, \
    DELETE_CLIENT, \
    GET_CONF, \
    SHOW_CLIENTS, \
    RENEW_SUB, \
    RENEW_SUB_DUR, \
    SUSPEND_SUB, \
    RENEW_APPROVE = range(13)

device_buttons = ReplyKeyboardMarkup([['pc', 'smartphone']], resize_keyboard=True)
subscrabe_status_buttons = ReplyKeyboardMarkup([['VIP', 'simple']], resize_keyboard=True)
renew_approve_buttons = ReplyKeyboardMarkup([['Да', 'Нет']], resize_keyboard=True)


def set_menu():
    bot_commands = [
        {'command': 'add_client',
         'description': 'Добавить клиента'},
        {'command': 'del_client',
         'description': 'Удалить клиента'},
        {'command': 'renew_client',
         'description': 'Возобновить/продлить подписку'},
        {'command': 'suspend_client',
         'description': 'Приостановить подписку'},
        {'command': 'show_clients',
         'description': 'Список пользователей'},
        {'command': 'get_conf',
         'description': 'Файл конфигурации клиента'},
        {'command': 'wg_restart',
         'description': 'Рестарт wireguard'},
        {'command': 'wg_show',
         'description': 'Статистика wireguard'},
        {'command': 'cancel',
         'description': 'Выйти из операции/очистить память'},
    ]
    bot_commands = json.dumps(bot_commands)
    url_tele_post = 'https://api.telegram.org/bot' + TELE_TOKEN + '/setMyCommands?commands=' + str(bot_commands)
    requests.get(url_tele_post)


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)

    mess = update.message.text

    if mess == f'/add_client':
        await update.message.reply_text('Введите имя клиента\n/cancel что бы выйти из операции',
                                        reply_markup=ReplyKeyboardRemove())
        return ENTER_FIRST_NAME

    if mess in ('/del_client', '/get_conf', '/show_clients', '/renew_client', '/suspend_client'):
        all_users = Client.show_all()
        if all_users:
            await update.message.reply_text('\n'.join(all_users))
        else:
            await update.message.reply_text('Список пуст')

        if mess == '/show_clients':
            return ConversationHandler.END

        await update.message.reply_text('Введите id клиента\n/cancel что бы выйти из операции',
                                        reply_markup=ReplyKeyboardRemove())
        if mess == '/del_client':
            return DELETE_CLIENT
        elif mess == '/get_conf':
            return GET_CONF
        elif mess == '/renew_client':
            return RENEW_SUB
        elif mess == '/suspend_client':
            return SUSPEND_SUB


async def enter_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["first_name"] = update.message.text
    await update.message.reply_text('Введите фамилию клиента\n/cancel что бы выйти из операции')
    return ENTER_LAST_NAME


async def enter_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_name'] = update.message.text
    await update.message.reply_text('Введите телефон клиента в формате +77777777777\n/cancel что бы выйти из операции')
    return ENTER_PHONE_NUMBER


async def enter_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if re.fullmatch(r'\+7\d{10}', update.message.text):
        context.user_data['phone_number'] = update.message.text
        await update.message.reply_text('Введите статус подписки\n/cancel что бы выйти из операции',
                                        reply_markup=subscrabe_status_buttons)
        return ENTER_SUBSCRIBE_STATUS
    else:
        await update.message.reply_text('Неверный формат')
        await update.message.reply_text('Введите телефон клиента в формате +77777777777'
                                        '\n/cancel что бы выйти из операции')
        return ENTER_PHONE_NUMBER


async def enter_subscribe_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'VIP':
        context.user_data['subscribe_status'] = 'VIP'
        context.user_data['subscribe_duration'] = None
        await update.message.reply_text('Введите девайс клиента\n/cancel что бы выйти из операции',
                                        reply_markup=device_buttons)
        return ENTER_DEVICE

    elif update.message.text == 'simple':
        context.user_data['subscribe_status'] = 'simple'
        await update.message.reply_text('Введите длительность подписки (в днях)\n/cancel что бы выйти из операции',
                                        reply_markup=ReplyKeyboardRemove())
        return ENTER_SUBSCRIBE_DURATION

    else:
        await update.message.reply_text('Выберите один из предложенных вариантов\n/cancel что бы выйти из операции')
        return ENTER_SUBSCRIBE_STATUS


async def enter_subscribe_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if re.fullmatch(r'\d+', update.message.text):
        context.user_data['subscribe_duration'] = update.message.text
        await update.message.reply_text('Введите девайс клиента\n/cancel что бы выйти из операции',
                                        reply_markup=device_buttons)
        return ENTER_DEVICE
    else:
        await update.message.reply_text('Некорректный ввод, нужно число\n/cancel что бы выйти из операции')
        return ENTER_SUBSCRIBE_DURATION


async def enter_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)

    if update.message.text == 'pc':
        context.user_data['device'] = 'pc'
    elif update.message.text == 'smartphone':
        context.user_data['device'] = 'smartphone'
    else:
        await update.message.reply_text('Выберите один из предложенных вариантов\n/cancel что бы выйти из операции')
        return ENTER_SUBSCRIBE_STATUS

    await update.message.reply_text('Данные приняты, создаем клиента...',
                                    reply_markup=ReplyKeyboardRemove())
    sleep(LOAD_TIME)

    peer_name = f'{context.user_data["first_name"]}_{context.user_data["last_name"]}'
    peer_name = translit(peer_name, reversed=True)

    if os.path.exists(os.path.join(EASY_WG_QUICK_DIR, 'seqno.txt')):
        with open(os.path.join(EASY_WG_QUICK_DIR, 'seqno.txt'), 'r') as file:
            peer_id = int(file.readline())
    else:
        peer_id = 10

    new_client_id = str(Client.add(context.user_data['first_name'],
                                   context.user_data['last_name'],
                                   context.user_data['phone_number'],
                                   context.user_data['subscribe_status'],
                                   context.user_data['subscribe_duration'],
                                   peer_id,
                                   context.user_data['device'],
                                   peer_name))

    mess = await update.message.reply_text(text='Записали пользователя в БД')
    sleep(LOAD_TIME)

    peer_name = f'{peer_name}_id{new_client_id}'

    new_client_dir = os.path.join(CLIENTS_DIR, new_client_id)
    subprocess.call(['mkdir', new_client_id], cwd=CLIENTS_DIR)
    await mess.edit_text('Создали папку пользователя')
    sleep(LOAD_TIME)

    subprocess.call([EASY_WG_QUICK_SCR, peer_name], cwd=EASY_WG_QUICK_DIR)
    await mess.edit_text("Записали конфиг в wghub.conf")
    sleep(LOAD_TIME)

    subprocess.call(['mv', f'wgclient_{peer_name}.conf', f'{CLIENTS_DIR}/{new_client_id}'], cwd=EASY_WG_QUICK_DIR)
    await mess.edit_text(f'Переместили wgclient_{peer_name}.conf')
    sleep(LOAD_TIME)

    trash_delete(peer_name)
    await mess.edit_text('Удилили треш')
    sleep(LOAD_TIME)

    subprocess.call(['cp', f'wghub.conf', WG_ETC_PATH], cwd=EASY_WG_QUICK_DIR)
    await mess.edit_text(text='Скопировали wghub.conf')
    sleep(LOAD_TIME)

    apply_changes()
    await mess.edit_text(text='Применяем изменения, перезапускаем wireguard')

    qr_jpeg = make_qr(new_client_dir)
    await mess.edit_text(text=f'Клиент добавлен\n{Client.select_client(new_client_id)}')
    await update.message.reply_photo(qr_jpeg)

    final_message_phone = f'''Ваш id в системе: {new_client_id}
Для активации vpn скачайте приложение wireguard, в нем выполните следующие действия: 
1. Нажмите ➕ (Android) или кнопку \"Добавить туннель\" (iOS)
2. Выберите "Сканировать QR" и отсканируйте полученный qr-код
3. Введите любое имя английскими буквами и нажмите "Создать туннель"
4. Активируйте переключатель
Приятного использования!'''

    await update.message.reply_text(final_message_phone)

    return ConversationHandler.END


async def del_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)

    user_id = update.message.text
    wghub_peer_id = Client.delete_client(user_id)
    mess = await update.message.reply_text('Удалили из бд')
    sleep(LOAD_TIME)

    wghub_editing(wghub_peer_id)
    await mess.edit_text('Удалили из wghub.conf')
    sleep(LOAD_TIME)

    client_dir = os.path.join(CLIENTS_DIR, user_id)
    subprocess.call(['rm', '-rf', client_dir])
    await mess.edit_text('Удалили папку')
    sleep(LOAD_TIME)

    await mess.edit_text(text='Применяем изменения, перезапускаем wireguard')
    apply_changes()

    await mess.edit_text(f'Удалили клиента {user_id}')

    return ConversationHandler.END


async def get_conf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)

    jpeg_file, text_file = None, None
    need_id = update.message.text
    id_folder = os.path.join(CLIENTS_DIR, need_id)

    if os.path.exists(id_folder):
        for filename in os.listdir(id_folder):
            file_path = os.path.join(id_folder, filename)
            if filename.endswith('.jpeg'):
                jpeg_file = file_path
            elif filename.endswith('.conf'):
                text_file = file_path
    else:
        await update.message.reply_text('Папка с клиентом отсутствует')

    if text_file:
        await update.message.reply_document(text_file)
        if jpeg_file:
            await update.message.reply_photo(jpeg_file)
        else:
            client_qr = make_qr(id_folder)
            await update.message.reply_photo(client_qr)
    else:
        await update.message.reply_text('Файл конфигурации отсутствует')

    return ConversationHandler.END


async def wg_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subprocess.call(['systemctl', 'restart', 'wg-quick@wghub'])
    await update.message.reply_text("Wireguard перезапущен")


async def wg_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    process = subprocess.Popen(['sudo', 'wg', 'show'], stdout=subprocess.PIPE)
    output = process.stdout.read().decode("utf-8")
    await update.message.reply_text(output)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)
    context.user_data.clear()
    await update.message.reply_text("Вышли из операции", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def renew_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)
    context.user_data['user_id'] = update.message.text
    subscribe_duration = Client.check_subscribe_duration(context.user_data['user_id'])
    subscribe_status = Client.check_subscribe_status(context.user_data['user_id'])
    
    if subscribe_status == 'VIP':
        await update.message.reply_text('Операция отменена\n'
                                        'Пользователь VIP, подписка бесконечна')
        return ConversationHandler.END
    elif subscribe_status == 'simple':
        expired_date = Client.check_expired_date(context.user_data['user_id'])
        await update.message.reply_text(f'Подписка пользователя всё еще активна до {expired_date}\n'
                                        f'Продлить подписку?\n'
                                        '/cancel что бы выйти из операции',
                                        reply_markup=renew_approve_buttons)
        return RENEW_APPROVE
    elif subscribe_status == 'stopped':
        expired_date = Client.renew_client(context.user_data['user_id'], 'renew')
        await update.message.reply_text('Пользователь возобновлен\n'
                                        f'Подписка пользователя всё еще активна до {expired_date}\n'
                                        'Продлить подписку?\n'
                                        '/cancel что бы выйти из операции',
                                        reply_markup=renew_approve_buttons)
        return RENEW_APPROVE
    elif subscribe_status == 'expired':
        await update.message.reply_text('Введите длительность подписки (в днях)\n'
                                        '/cancel что бы выйти из операции')
        return RENEW_SUB_DUR


async def renew_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)
    if update.message.text == 'Да':
        await update.message.reply_text(f'На сколько продлить? (в днях)\n'
                                        '/cancel что бы выйти из операции',
                                        reply_markup=ReplyKeyboardRemove())
        return RENEW_SUB_DUR
    else:
        return ConversationHandler.END


async def get_renew_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)
    context.user_data['renew_duration'] = update.message.text
    if Client.check_subscribe_status(context.user_data['user_id']) == 'simple':
        expired_date = Client.renew_client(context.user_data['user_id'],
                                           'extend',
                                           context.user_data['renew_duration'])

        await update.message.reply_text(text=f'Подписка продлена до {expired_date}')

    elif Client.check_subscribe_status(context.user_data['user_id']) == 'expired':
        expired_date = Client.renew_client(context.user_data['user_id'],
                                           'reopen',
                                           context.user_data['renew_duration'])

        mess = await update.message.reply_text('Применяем изменения, перезапускаем wireguard')
        apply_changes()
        await mess.edit_text(text='Клиент возобновлен\n'
                                  f'Подписка активна до {expired_date}')
    else:
        await update.message.reply_text('Ошибка статуса подписки')
    return ConversationHandler.END


async def suspend_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)
    user_id = update.message.text
    subscribe_status = Client.check_subscribe_status(user_id)
    if subscribe_status == 'VIP':
        await update.message.reply_text('Операция отменена\n'
                                        'Пользователь VIP')
    elif subscribe_status in ('stopped', 'expired'):
        await update.message.reply_text('Вы пытаетесь остановить уже неработающую/остановленную подписку\n'
                                        'Операция отменена')
    else:
        expired_subscribe_date = Client.suspend_client(user_id)
        mess = await update.message.reply_text('Применяем изменения, перезапускаем wireguard')
        apply_changes()
        await mess.edit_text(text='Подписка приостановлен\n'
                                  f'Остановленная подписка активна до {expired_subscribe_date}')
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(TELE_TOKEN).build()
    restrict_filter = filters.User(user_id=ALLOWED_USERS)
    set_menu()

    # Добавление новых клиентов
    add_client_handler = ConversationHandler(
        fallbacks=[CommandHandler("cancel", cancel)],
        entry_points=[CommandHandler("add_client", ask_name, filters=restrict_filter)],
        states={
            ENTER_FIRST_NAME: [MessageHandler(filters.TEXT & (~ filters.COMMAND), enter_first_name)],
            ENTER_LAST_NAME: [MessageHandler(filters.TEXT & (~ filters.COMMAND), enter_last_name)],
            ENTER_PHONE_NUMBER: [MessageHandler(filters.TEXT & (~ filters.COMMAND), enter_phone_number)],
            ENTER_SUBSCRIBE_STATUS: [MessageHandler(filters.TEXT & (~ filters.COMMAND), enter_subscribe_status)],
            ENTER_SUBSCRIBE_DURATION: [MessageHandler(filters.TEXT & (~ filters.COMMAND), enter_subscribe_duration)],
            ENTER_DEVICE: [MessageHandler(filters.TEXT & (~ filters.COMMAND), enter_device)]
        },
        allow_reentry=False
    )

    # Операции с существующими клиентами
    client_interaction_handler = ConversationHandler(
        fallbacks=[CommandHandler("cancel", cancel)],
        entry_points=[CommandHandler(['del_client',
                                      'show_clients',
                                      'get_conf',
                                      'renew_client',
                                      'suspend_client',
                                      'extend_subscription'], ask_name,
                                     filters=restrict_filter)],
        states={
            DELETE_CLIENT: [MessageHandler(filters.TEXT & (~ filters.COMMAND), del_client)],
            GET_CONF: [MessageHandler(filters.TEXT & (~ filters.COMMAND), get_conf)],
            RENEW_SUB: [MessageHandler(filters.TEXT & (~ filters.COMMAND), renew_client)],
            RENEW_SUB_DUR: [MessageHandler(filters.TEXT & (~ filters.COMMAND), get_renew_duration)],
            SUSPEND_SUB: [MessageHandler(filters.TEXT & (~ filters.COMMAND), suspend_client)],
            RENEW_APPROVE: [MessageHandler(filters.TEXT & (~ filters.COMMAND), renew_approve)]
        },
        allow_reentry=False
    )

    wg_restart_handler = (CommandHandler('wg_restart', wg_restart, filters=restrict_filter))
    wg_show_handler = (CommandHandler('wg_show', wg_show, filters=restrict_filter))
    cancel_handler = (CommandHandler('cancel', cancel, filters=restrict_filter))

    application.add_handler(add_client_handler)
    application.add_handler(client_interaction_handler)
    application.add_handler(wg_restart_handler)
    application.add_handler(wg_show_handler)
    application.add_handler(cancel_handler)

    application.run_polling()


if __name__ == '__main__':
    main()
