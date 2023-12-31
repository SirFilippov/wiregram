from sqlalchemy import (
    create_engine,
    String,
    Integer,
    Date,
    select,
    cast,
    delete,
    update
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from datetime import date, timedelta
from settings import DB_PATH
import os
import logging
from file_manager import wghub_editing, apply_changes


class Base(DeclarativeBase):
    pass


engine = create_engine(f"sqlite:///{DB_PATH}")

'''
Статусы подписок:
VIP - бессрочная
simple - обычная, срок окончания в столбце subscribe_duration, дата активации в столбце activated_date
expired - отсановленная по расписанию (чек раз в день), коментится в conf-файле WG, можно возобновить
stopped - действующая, но остановленная вручную, можно возобновить
'''


class Client(Base):
    __tablename__ = 'clients'
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    phone_number: Mapped[str] = mapped_column(String)
    activated_date: Mapped[date] = mapped_column(Date)
    subscribe_duration: Mapped[int] = mapped_column(Integer, default=None, nullable=True)
    subscribe_status: Mapped[str] = mapped_column(String)
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
            stmt = select(Client).where(Client.user_id == client_id)
            for row in session.execute(stmt):
                wghub_peer_id = row[0].peer_id

            stmt = delete(Client).where(Client.user_id == int(client_id))
            session.execute(stmt)

            session.commit()
        return wghub_peer_id

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
                row = row[0].split()
                if row[0] == 'simple':
                    all_users.append(f'\U000026AA {" ".join(row[1:])}')
                elif row[0] == 'VIP':
                    all_users.append(f'\U0001F7E1 {" ".join(row[1:])}')
                elif row[0] in ('expired', 'stopped'):
                    all_users.append(f'\U0001F480 {" ".join(row[1:])}')
            return all_users

    @staticmethod
    def select_client(user_id):
        with Session(engine) as session:
            stmt = select(Client).where(Client.user_id == user_id)
            for client in session.execute(stmt):
                return client[0]

    @staticmethod
    def suspend_expired_subscribes():
        logging.info('Плановая проверка подписки...')
        today_date = date.today()
        with Session(engine) as session:
            select_stmt = select(Client).where(Client.subscribe_status == 'simple')
            for client in session.execute(select_stmt):
                activated_date = client[0].activated_date
                subscribe_duration = timedelta(days=int(client[0].subscribe_duration))
                expired_subscribe_date = activated_date + subscribe_duration
                if expired_subscribe_date < today_date:
                    logging.info(f"У пользователя {client[0].peer_name} закончился срок подписки")
                    wghub_editing(client[0].peer_id, mode='suspend')
                    update_stmt = update(Client).where(Client.peer_id == client[0].peer_id).values(subscribe_status='expired',
                                                                                                   subscribe_duration=None)
                    session.execute(update_stmt)
                    session.commit()
        apply_changes()


    @staticmethod
    def renew_client(user_id, mode, renew_duration=0):
        """
        Режимы включения:
        renew - просто включить подписку которая уже оплачена/активна и выключена была вручную
        extend - добавить количество дней в подписку
        reopen - включение подписки из статуса expired, с изменением даты активации
        """
        logging.info(f'Возобновляем/продлеваем подписку пользователя в режиме {mode}...')
        with Session(engine) as session:
            select_stmt = select(Client).where(Client.user_id == user_id)
            for client in session.execute(select_stmt):
                wghub_editing(client[0].peer_id, 'renew')

                if mode == 'renew':
                    update_stmt = update(Client).where(Client.user_id == user_id).values(
                        subscribe_status='simple')
                    expired_date = client[0].activated_date + timedelta(days=int(client[0].subscribe_duration))
                elif mode == 'extend':
                    renew_duration = int(client[0].subscribe_duration) + int(renew_duration)
                    update_stmt = update(Client).where(Client.user_id == user_id).values(
                        subscribe_duration=renew_duration)
                    expired_date = date.today() + timedelta(days=int(renew_duration))
                elif mode == 'reopen':
                    update_stmt = update(Client).where(Client.user_id == user_id).values(
                        subscribe_status='simple',
                        subscribe_duration=renew_duration,
                        activated_date=date.today())
                    expired_date = date.today() + timedelta(days=int(renew_duration))
                else:
                    raise ValueError('Не один из режимов не выбран')

                session.execute(update_stmt)
                session.commit()
                expired_date = expired_date.strftime('%d.%m.%Y')
                return expired_date

    @staticmethod
    def suspend_client(user_id):
        logging.info('Останавливаем подписку пользователя...')
        today_date = date.today()
        with Session(engine) as session:
            select_stmt = select(Client).where(Client.user_id == user_id)
            for client in session.execute(select_stmt):
                activated_date = client[0].activated_date
                subscribe_duration = timedelta(days=int(client[0].subscribe_duration))
                expired_subscribe_date = activated_date + subscribe_duration
                wghub_editing(client[0].peer_id, mode='suspend')
                update_stmt = update(Client).where(Client.peer_id == client[0].peer_id).values(
                    subscribe_status='stopped')
                session.execute(update_stmt)
                session.commit()
                expired_subscribe_date = expired_subscribe_date.strftime('%d.%m.%Y')
                return expired_subscribe_date

    @staticmethod
    def check_subscribe_status(user_id):
        with Session(engine) as session:
            select_stmt = select(Client).where(Client.user_id == user_id)
            for client in session.execute(select_stmt):
                return client[0].subscribe_status

    @staticmethod
    def check_subscribe_duration(user_id):
        with Session(engine) as session:
            select_stmt = select(Client).where(Client.user_id == user_id)
            for client in session.execute(select_stmt):
                return client[0].subscribe_duration

    @staticmethod
    def check_expired_date(user_id):
        with Session(engine) as session:
            select_stmt = select(Client).where(Client.user_id == user_id)
            for client in session.execute(select_stmt):
                expired_date = client[0].activated_date + timedelta(days=int(client[0].subscribe_duration))
                return expired_date


if not os.path.exists(DB_PATH):
    logging.info('Создали бд')
    Base.metadata.create_all(engine)

if __name__ == '__main__':
    # Client.suspend_client(48)
    # print(Client.renew_client(40, 'renew'))
    Client.suspend_expired_subscribes()
