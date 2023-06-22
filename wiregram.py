import json
import logging
from datetime import date
from time import sleep
import qrcode
import os
import subprocess
import re
from dotenv import load_dotenv
from pathlib import Path
from transliterate import translit
import requests

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from sqlalchemy import create_engine, String, Integer, Date, Boolean, select, cast, Column, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Todo: сделать систему для истечения срока подписки после итечения срока
#  желательно по телеграму или васапу отправлять сообщение о том что подписка
#  заканчивается, возможно это можно реализовать в APScheduler
#
# Todo: функция запуска wg в первый раз
# Todo: сделать скип возможно ненужных настроек
# Todo: повесить на все это докер
# Todo: wg show с именами пиров а не кодами
# Todo: сделать бота васап и телеги для клиентов
# Todo: функция добавления id админов в env


BASE_DIR = Path(__file__).resolve().parent  # Путь к python скрипту
ENV = os.path.join(BASE_DIR, '.env')  # Путь к env на сервере
CLIENTS_DIR = os.path.join(BASE_DIR, 'clients')  # Путь к папке с клиентами
EASY_WG_QUICK_DIR = os.path.join(BASE_DIR, 'easy-wg-quick')  # Путь к папке скрипта easy-wg-quick
EASY_WG_QUICK_SCR = os.path.join(EASY_WG_QUICK_DIR, 'easy-wg-quick')  # Путь к исполняющему скрипту easy-wg-quick
DB_PATH = os.path.join(BASE_DIR, 'vpnmanager.db')  # Путь к БД
WG_ETC_PATH = '/etc/wireguard/wghub.conf'  # Путь text файлу wireguard

load_dotenv(ENV)
ALLOWED_USERS = [int(i) for i in os.getenv('ALLOWED_USERS').split(',')]  # Телеграм id пользователей имеющих доступ
TELE_TOKEN = os.getenv('TELE_TOKEN')  # Токен бота


class Base(DeclarativeBase):
    pass


engine = create_engine(f"sqlite:///{DB_PATH}", echo=True)


class Client(Base):
    __tablename__ = 'clients'
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    phone_number: Mapped[str] = mapped_column(String)
    activated_date: Mapped[date] = mapped_column(Date)
    subscribe_duration: Mapped[int] = mapped_column(Integer, default=None)
    subscribe_status = Column(Boolean)
    peer_id: Mapped[str] = mapped_column(Integer)
    device: Mapped[str] = mapped_column(String)
    peer_name: Mapped[str] = mapped_column(String)

    def __repr__(self) -> str:
        return f'user_id: {self.user_id!r}\n' \
               f'first_name: {self.first_name!r}\n' \
               f'last_name: {self.last_name!r}\n' \
               f'phone_number: {self.phone_number!r}\n' \
               f'activated_date: {self.activated_date.strftime("%d-%m-%Y")!r}\n' \
               f'subscrabe_duration: {self.subscribe_duration!r}\n' \
               f'subscrabe_status: {self.subscribe_status!r}\n' \
               f'peer_id: {self.peer_id!r}\n' \
               f'device: {self.device!r}\n' \
               f'peer_name: {self.peer_name!r}\n'

    @staticmethod
    def add(first_name, last_name, phone_number, subscrabe_status, subscribe_duration, peer_id, device,
            peer_name):
        with Session(engine) as session:
            new_client = Client(first_name=first_name,
                                last_name=last_name,
                                phone_number=phone_number,
                                activated_date=date.today(),
                                subscribe_duration=subscribe_duration,
                                subscribe_status=subscrabe_status,
                                peer_id=peer_id,
                                device=device,
                                peer_name=peer_name)

            session.add(new_client)
            session.commit()
            new_client_id = new_client.user_id
        return new_client_id

    @staticmethod
    def delete_client(client_id):
        with Session(engine) as session:
            stmt = select(Client.peer_name).where(Client.user_id == client_id)
            for row in session.execute(stmt):
                wghub_peer_name = row[0] + '_id' + client_id

            stmt = delete(Client).where(Client.user_id == int(client_id))
            session.execute(stmt)

            session.commit()
        return wghub_peer_name

    @staticmethod
    def show_all():
        with Session(engine) as session:
            stmt = select(cast(Client.subscribe_status, String) + ' '
                          + cast(Client.user_id, String) + ' '
                          + Client.first_name + ' '
                          + Client.last_name + ' '
                          + Client.device)

            all_users = []
            for row in session.execute(stmt):
                if row[0][0] == '1':
                    all_users.append(f'⚪ {row[0][2:]}')
                else:
                    all_users.append(f'⚫ {row[0][2:]}')
            return all_users

    @staticmethod
    def select_client(user_id):
        with Session(engine) as session:
            stmt = select(Client).where(Client.user_id == user_id)
            for client in session.execute(stmt):
                return client[0]


if not os.path.exists(DB_PATH):
    Base.metadata.create_all(engine)



DELETE_CLIENT, GET_CONF, SHOW_CLIENTS = 0, 1, 2
# START_USER, STOP_USER = 0, 1

ENTER_FIRST_NAME, \
    ENTER_LAST_NAME, \
    ENTER_PHONE_NUMBER, \
    ENTER_SUBSCRIBE_STATUS, \
    ENTER_SUBSCRIBE_DURATION, \
    ENTER_DEVICE = range(6)


device_buttons = ReplyKeyboardMarkup([['pc', 'smartphone']], resize_keyboard=True)
subscrabe_status_buttons = ReplyKeyboardMarkup([['VIP', 'simple']], resize_keyboard=True)

load_time = 1


def set_menu():
    bot_commands = [
        {'command': 'add_client',
         'description': 'Добавить клиента'},
        {'command': 'del_client',
         'description': 'Удалить клиента'},
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
        await update.message.reply_text('Введите имя клиента\n/cancel что бы выйти из операции.',
                                        reply_markup=ReplyKeyboardRemove())
        return ENTER_FIRST_NAME

    if mess in ('/del_client', '/get_conf', '/show_clients'):
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


    # if update.message.text == f'\U00002705Возобновить клиента':
    #     await update.message.reply_text('\n'.join(show_usr_lst()),
    #                                     reply_markup=ReplyKeyboardRemove())
    #     await update.message.reply_text('Кого возобновить? /cancel что бы выйти из операции')
    #     return START_USER
    #
    # if update.message.text == f'\U0000274CОстановить клиента':
    #     await update.message.reply_text('\n'.join(show_usr_lst()),
    #                                     reply_markup=ReplyKeyboardRemove())
    #     await update.message.reply_text('Кого остановить? /cancel что бы выйти из операции')
    #     return STOP_USER


async def enter_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["first_name"] = update.message.text
    await update.message.reply_text('Введите фамилию клиента\n/cancel что бы выйти из операции.')
    return ENTER_LAST_NAME


async def enter_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_name'] = update.message.text
    await update.message.reply_text('Введите телефон клиента в формате +77777777777\n/cancel что бы выйти из операции.')
    return ENTER_PHONE_NUMBER


async def enter_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if re.fullmatch(r'\+7\d{10}', update.message.text):
        context.user_data['phone_number'] = update.message.text
        await update.message.reply_text('Введите статус подписки\n/cancel что бы выйти из операции.',
                                        reply_markup=subscrabe_status_buttons)
        return ENTER_SUBSCRIBE_STATUS
    else:
        await update.message.reply_text('Неверный формат')
        await update.message.reply_text('Введите телефон клиента в формате +77777777777'
                                        '\n/cancel что бы выйти из операции.')
        return ENTER_PHONE_NUMBER


async def enter_subscribe_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'VIP':
        context.user_data['subscribe_status'] = True
        context.user_data['subscribe_duration'] = None
        await update.message.reply_text('Введите девайс клиента\n/cancel что бы выйти из операции.',
                                        reply_markup=device_buttons)
        return ENTER_DEVICE

    elif update.message.text == 'simple':
        context.user_data['subscribe_status'] = False
        await update.message.reply_text('Введите длительность подписки (в днях)\n/cancel что бы выйти из операции.',
                                        reply_markup=ReplyKeyboardRemove())
        return ENTER_SUBSCRIBE_DURATION

    else:
        await update.message.reply_text('Выберите один из предложенных вариантов\n/cancel что бы выйти из операции.')
        return ENTER_SUBSCRIBE_STATUS


async def enter_subscribe_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if re.fullmatch(r'\d+', update.message.text):
        context.user_data['subscribe_duration'] = update.message.text
        await update.message.reply_text('Введите девайс клиента\n/cancel что бы выйти из операции.',
                                        reply_markup=device_buttons)
        return ENTER_DEVICE
    else:
        await update.message.reply_text('Некорректный ввод, нужно число\n/cancel что бы выйти из операции.')
        return ENTER_SUBSCRIBE_DURATION


async def enter_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s: %s", update.message.from_user.first_name, update.message.text)

    if update.message.text == 'pc':
        context.user_data['device'] = 'pc'
    elif update.message.text == 'smartphone':
        context.user_data['device'] = 'smartphone'
    else:
        await update.message.reply_text('Выберите один из предложенных вариантов\n/cancel что бы выйти из операции.')
        return ENTER_SUBSCRIBE_STATUS

    await update.message.reply_text('Данные приняты, создаем клиента...',
                                    reply_markup=ReplyKeyboardRemove())
    sleep(1)

    peer_name = f'{context.user_data["first_name"]}_{context.user_data["last_name"]}'
    peer_name = translit(peer_name, reversed=True)

    with open(os.path.join(EASY_WG_QUICK_DIR, 'seqno.txt'), 'r') as file:
        peer_id = int(file.readline())

    new_client_id = str(Client.add(context.user_data['first_name'],
                                   context.user_data['last_name'],
                                   context.user_data['phone_number'],
                                   context.user_data['subscribe_status'],
                                   context.user_data['subscribe_duration'],
                                   peer_id,
                                   context.user_data['device'],
                                   peer_name))

    mess = await update.message.reply_text(text='Записали пользователя в БД')
    sleep(load_time)

    peer_name = f'{peer_name}_id{new_client_id}'

    new_client_dir = os.path.join(CLIENTS_DIR, new_client_id)
    subprocess.call(['mkdir', new_client_id], cwd=CLIENTS_DIR)
    await mess.edit_text('Создали папку пользователя')
    sleep(load_time)

    subprocess.call([EASY_WG_QUICK_SCR, peer_name], cwd=EASY_WG_QUICK_DIR)
    await mess.edit_text("Записали конфиг в wghub.conf")
    sleep(load_time)

    subprocess.call(['mv', f'wgclient_{peer_name}.conf', f'{CLIENTS_DIR}/{new_client_id}'], cwd=EASY_WG_QUICK_DIR)
    await mess.edit_text(f'Переместили wgclient_{peer_name}.conf')
    sleep(load_time)

    trash_delete(peer_name)
    await mess.edit_text('Удилили треш')
    sleep(load_time)

    # todo: изменить BASE_DIR на WG_ETC_PATH
    subprocess.call(['cp', f'wghub.conf', WG_ETC_PATH], cwd=EASY_WG_QUICK_DIR)
    await mess.edit_text(text='Скопировали wghub.conf')
    sleep(load_time)

    # todo: включить рестарт
    subprocess.call(['systemctl', 'restart', 'wg-quick@wghub'])
    await mess.edit_text(text='Перезапустили wireguard')
    sleep(load_time)

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
    wghub_peer_name = Client.delete_client(user_id)
    mess = await update.message.reply_text('Удалили из бд')
    sleep(load_time)

    wghub_editing(wghub_peer_name)
    await mess.edit_text('Удалили из wghub.conf')
    sleep(load_time)

    client_dir = os.path.join(CLIENTS_DIR, user_id)
    subprocess.call(['rm', '-rf', client_dir])
    await mess.edit_text('Удалили папку')
    sleep(load_time)

    # todo: изменить BASE_DIR на WG_ETC_PATH
    subprocess.call(['cp', 'wghub.conf', WG_ETC_PATH], cwd=EASY_WG_QUICK_DIR)
    await mess.edit_text('Скопировали wghub.conf')
    sleep(load_time)

    # todo: включить рестарт
    subprocess.call(['systemctl', 'restart', 'wg-quick@wghub'])
    await mess.edit_text('Перезапустили wireguard')
    sleep(load_time)

    await mess.edit_text(f'Удалили клиента {wghub_peer_name}')

    return ConversationHandler.END


# async def stop_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     logger.info("%s: %s", update.message.from_user.first_name, update.message.text)
#
#     user_name = update.message.text
#     subscribe_edit(user_name, 0)
#     await update.message.reply_text(f"Закоментили строки пользователя...")
#
#     sleep(2)
#     subprocess.call(['cp', f'{working_path}wghub.text', '/etc/wireguard/wghub.text'])
#     await update.message.reply_text(f"Скопировали wghub.text...")
#
#     sleep(2)
#     subprocess.call(['systemctl', 'restart', 'wg-quick@wghub'])
#     await update.message.reply_text(f'Перезапустили сервер...')
#
#     await update.message.reply_text(f"Остановили подписку клиента {user_name}",
#                                     reply_markup=ReplyKeyboardMarkup(main_buttons, resize_keyboard=True))
#     return ConversationHandler.END


# async def start_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     logger.info("%s: %s", update.message.from_user.first_name, update.message.text)
#
#     user_name = update.message.text
#     subscribe_edit(user_name, 1)
#     await update.message.reply_text(f"Раскоментили строки пользователя...")
#
#     time.sleep(2)
#     subprocess.call(['cp', f'{working_path}wghub.text', '/etc/wireguard/wghub.text'])
#     await update.message.reply_text(f"Скопировали wghub.text...")
#
#     time.sleep(2)
#     subprocess.call(['systemctl', 'restart', 'wg-quick@wghub'])
#     await update.message.reply_text(f'Перезапустили сервер...')
#
#     await update.message.reply_text(f"Активировали подписку клиента {user_name}",
#                                     reply_markup=ReplyKeyboardMarkup(main_buttons, resize_keyboard=True))
#     return ConversationHandler.END


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
    subprocess.call(['systemctl', 'restart', 'wg-quick@wghub.service'])
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


def make_qr(new_client_dir):
    text_file = os.listdir(new_client_dir)[0]
    text_file = os.path.join(new_client_dir, text_file)
    qr_name = text_file[:-5] + '_qrcode.jpeg'
    qr_path = os.path.join(CLIENTS_DIR, qr_name)

    with open(text_file, 'r', encoding='utf-8') as text_file:
        file_info = text_file.read()
        img = qrcode.make(file_info)
        type(img)
        img.save(qr_path)

    return qr_path


def trash_delete(peer_name):
    os.chdir(EASY_WG_QUICK_DIR)
    files_to_delete = [
        f'wgclient_{peer_name}.psk',
        f'wgclient_{peer_name}.qrcode.txt',
        f'wgclient_{peer_name}.uci.txt'
    ]

    for file in files_to_delete:
        os.remove(file)
    os.chdir(BASE_DIR)


def wghub_editing(peer_name):
    os.chdir(EASY_WG_QUICK_DIR)
    with open(f'wghub.conf', 'r', encoding='utf-8') as text:
        str_list = text.readlines()

        # Finding need string number
        for line in str_list:
            if f'wgclient_{peer_name}.conf' in line:
                str_num = str_list.index(line) - 1

        # Deleting 6 times on this index
        for i in range(6):
            str_list.pop(str_num)

    with open(f'wghub.conf', 'w', encoding='utf-8') as text:
        for line in str_list:
            text.write(line)
    os.chdir(BASE_DIR)



# def files_edit(user_name):
#
    # with open(f'{working_path}wghub.text', 'r', encoding='utf-8') as text_file:
    #     str_list = text_file.readlines()
    #
    #     # Finding need string number
    #     for line in str_list:
    #         if f'wgclient_{user_name}.text' in line:
    #             str_num = str_list.index(line) - 1
    #
    #     # Deleting 6 times on this index
    #     for i in range(6):
    #         str_list.pop(str_num)
    #
    # with open(f'{working_path}wghub.text', 'w', encoding='utf-8') as text_file:
    #     for line in str_list:
    #         text_file.write(line)


# def subscribe_edit(user_name, mode):
#     with open(f'{working_path}wghub.text', 'r', encoding='utf-8') as text_file:
#         str_list = text_file.readlines()
#
#         # Finding need string number
#         for line in str_list:
#             if user_name in line:
#                 str_num = str_list.index(line) + 1
#
#         # Comment or uncomment 4 strings from this index
#         # Mode to rule: 0 - comment 1 - uncomment
#         for i in range(str_num, str_num + 4):
#             if mode:
#                 if '#' not in str_list[i]:
#                     break
#                 str_list[i] = str_list[i][2:]
#             else:
#                 if '#' in str_list[i]:
#                     break
#                 str_list[i] = '# ' + str_list[i]
#
#     with open(f'{working_path}wghub.text', 'w', encoding='utf-8') as text_file:
#         text_file.writelines(str_list)


def main() -> None:
    application = Application.builder().token(TELE_TOKEN).build()
    restrict_filter = filters.User(user_id=ALLOWED_USERS)
    set_menu()

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

    client_interaction_handler = ConversationHandler(
        fallbacks=[CommandHandler("cancel", cancel)],
        entry_points=[CommandHandler(['del_client', 'show_clients', 'get_conf'], ask_name,
                                     filters=restrict_filter)],
        states={
            DELETE_CLIENT: [MessageHandler(filters.TEXT & (~ filters.COMMAND), del_client)],
            GET_CONF: [MessageHandler(filters.TEXT & (~ filters.COMMAND), get_conf)],
        },
        allow_reentry=False
    )

    wg_restart_handler = (CommandHandler('wg_restart', wg_restart, filters=restrict_filter))
    wg_show_handler = (CommandHandler('wg_show', wg_show, filters=restrict_filter))
    cancel_handler = (CommandHandler('cancel', cancel, filters=restrict_filter))


    # start_stop_user_handler = ConversationHandler(
    #     entry_points=[
    #         MessageHandler(filters.Regex(f'\U00002705Возобновить клиента|\U0000274CОстановить клиента'), ask_name)],
    #     states={
    #         START_USER: [MessageHandler(filters.Regex('^\w*$'), start_user)],
    #         STOP_USER: [MessageHandler(filters.Regex('^\w*$'), stop_user)],
    #     },
    #     fallbacks=[CommandHandler("cancel", cancel)],
    #     allow_reentry=True
    # )

    # application.add_handler(CommandHandler("start", start))

    application.add_handler(add_client_handler)
    application.add_handler(client_interaction_handler)
    application.add_handler(wg_restart_handler)
    application.add_handler(wg_show_handler)
    application.add_handler(cancel_handler)
    # application.add_handler(start_stop_user_handler)
    application.run_polling()


if __name__ == '__main__':
    main()
