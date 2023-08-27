import os
from time import sleep
import subprocess
import logging

import qrcode

from settings import (
    EASY_WG_QUICK_DIR,
    CLIENTS_DIR,
    BASE_DIR,
    DEV,
    LOAD_TIME,
    WG_ETC_PATH,
)


def apply_changes():
    os.chdir(EASY_WG_QUICK_DIR)
    subprocess.call(['cp', f'wghub.conf', WG_ETC_PATH], cwd=EASY_WG_QUICK_DIR)
    sleep(LOAD_TIME)

    if not DEV:
        subprocess.call(['systemctl', 'enable', 'wg-quick@wghub'])
        subprocess.call(['systemctl', 'restart', 'wg-quick@wghub'])
        sleep(LOAD_TIME)
    os.chdir(BASE_DIR)


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
        f'wgclient_{peer_name}.uci.txt',
        f'wgclient_{peer_name}.qrcode.txt'
    ]

    for file in files_to_delete:
        os.remove(file)
    os.chdir(BASE_DIR)


def wghub_editing(peer_id, mode='delete'):
    if mode not in ['delete', 'suspend', 'renew']:
        raise ValueError("Возможные аргументы для mode: 'delete', 'suspend', 'renew'")

    os.chdir(EASY_WG_QUICK_DIR)
    str_num = None

    with open(f'wghub.conf', 'r+', encoding='utf-8') as text:
        str_list = text.readlines()

        # Находим нужного пира по peer_id
        for line in str_list:
            if f'# {peer_id}:' in line:
                str_num = str_list.index(line)
                break
        if str_num is None:
            raise ValueError("Peer_id в wghub не найден")

        # Проводим нужные операции со строками
        if mode == 'delete':
            for i in range(6):
                str_list.pop(str_num - 1)
            logging.info("Удалили пользователя")
        elif mode == 'suspend':
            for i in range(4):
                str_list[str_num + i + 1] = '# ' + str_list[str_num + i + 1]
            logging.info("Приостановили пользователя")
        elif mode == 'renew':
            for i in range(4):
                str_list[str_num + i + 1] = str_list[str_num + i + 1][2:]
            logging.info("Возобновили подписку у пользователя")

        # Перезаписываем файл
        text.seek(0)
        text.truncate()
        text.writelines(str_list)

    os.chdir(BASE_DIR)


if __name__ == '__main__':
    wghub_editing(57)

