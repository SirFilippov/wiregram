from dotenv import load_dotenv
from pathlib import Path
import os
import logging

DEV = True
BASE_DIR = Path(__file__).resolve().parent  # Путь к python скрипту
ENV = os.path.join(BASE_DIR, 'tele_data.env')  # Путь к env на сервере
CLIENTS_DIR = os.path.join(BASE_DIR, 'clients')  # Путь к папке с клиентами
EASY_WG_QUICK_DIR = os.path.join(BASE_DIR, 'easy-wg-quick')  # Путь к папке скрипта easy-wg-quick
EASY_WG_QUICK_SCR = os.path.join(EASY_WG_QUICK_DIR, 'easy-wg-quick')  # Путь к исполняющему скрипту easy-wg-quick
DB_PATH = os.path.join(BASE_DIR, 'vpnmanager.db')  # Путь к БД
WG_ETC_PATH = '/etc/wireguard/wghub.conf'  # Путь text файлу wireguard


load_dotenv(ENV)
ALLOWED_USERS = [int(i) for i in os.getenv('ALLOWED_USERS').split(',')]  # Телеграм id пользователей имеющих доступ
TELE_TOKEN = os.getenv('TELE_TOKEN')  # Токен бота

BROKER_URL = 'redis://localhost:6379/0'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
