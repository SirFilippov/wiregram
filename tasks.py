from celery import Celery
from celery.schedules import crontab
from db import Client

from config import BROKER_URL

app = Celery('tasks', broker=BROKER_URL)

app.conf.beat_schedule = {
    'check_subscribe_date': {
        'task': 'tasks.check_subscribe_date',
        # 'schedule': crontab(minute='0', hour='0'),
        'schedule': 10,
    },
}
app.conf.timezone = 'UTC'


@app.task
def check_subscribe_date():
    expired_subscribes = Client.select_expired_subscribes()

# Сделать авто отключение при истечении подписки
# Сделать функцию продления подписки - бот спрашивает сколько дней
# Сделать функцию чека если подписка не продлевается более 10 дней - удаляется аккаунт
# Сделать статус подписки не true false а VIP simple expired
