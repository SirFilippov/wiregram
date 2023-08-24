from sqlalchemy import (
    create_engine,
    String,
    Integer,
    Date,
    Boolean,
    select,
    cast,
    Column,
    delete
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from datetime import date, datetime, timedelta
from config import DB_PATH
import os

from sqlalchemy.sql.expression import false, true


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
    subscribe_duration: Mapped[int] = mapped_column(Integer, default=None, nullable=True)
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

    @staticmethod
    def select_expired_subscribes():
        expired_subscribes = []
        today_date = date.today()
        with Session(engine) as session:
            stmt = select(Client).where(Client.subscribe_status == false())
            for client in session.execute(stmt):
                activated_date = client[0].activated_date
                subscribe_duration = timedelta(days=int(client[0].subscribe_duration))
                expired_subscribe_date = activated_date + subscribe_duration
                if expired_subscribe_date < today_date:
                    expired_subscribes.append(client)
            return expired_subscribes


if not os.path.exists(DB_PATH):
    print('Создали бд')
    Base.metadata.create_all(engine)


print(Client.select_expired_subscribes())
