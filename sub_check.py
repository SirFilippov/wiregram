import logging
import threading
import time
from db import Client
import schedule


def run_continuously(interval=1):
    """Continuously run, while executing pending jobs at each
    elapsed time interval.
    @return cease_continuous_run: threading. Event which can
    be set to cease continuous run. Please note that it is
    *intended behavior that run_continuously() does not run
    missed jobs*. For example, if you've registered a job that
    should run every minute and you set a continuous run
    interval of one hour then your job won't be run 60 times
    at each interval but only once.
    """
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run


def check_subscribe():
    Client.suspend_expired_subscribes()


schedule.every().day.at("10:30").do(check_subscribe)
stop_run_continuously = run_continuously()

# schedule.every(30).seconds.do(check_subscribe)
# stop_run_continuously = run_continuously()

logging.info("Ежедневная проверка запущена")
