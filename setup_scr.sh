#!/bin/bash

# Кома для скачивания и установки моего репо:
#cd /home && git clone https://github.com/SirFilippov/wiregram.git && chmod +x /home/wiregram/setup_scr.sh && sudo /home/wiregram/setup_scr.sh

# Пути
WIREGRAM_DIR=$"/home/wiregram"
ENV_DIR="$WIREGRAM_DIR/tele_data.env"
VENV_DIR="$WIREGRAM_DIR/venv"
WIREGRAM_SCR="$WIREGRAM_DIR/wiregram.py"
EASY_WG_QUICK_DIR="$WIREGRAM_DIR/easy-wg-quick"
EASY_WG_QUICK_SCR="$WIREGRAM_DIR/easy-wg-quick/easy-wg-quick"

# Создаем env
read -r -p "Введите токен бота: " bot_token
read -r -p "Введите телеграм-id администраторов через запятую без пробелов: " allowed_users
echo "TELE_TOKEN=$bot_token" >> "$ENV_DIR"
echo "ALLOWED_USERS=$allowed_users" >> "$ENV_DIR"

# Установка нужного ПО
apt-get -y update
apt-get -y upgrade
apt install -y wireguard
apt install -y sqlite3
apt install -y python3-venv

# Установка easy-wg-quick_
mkdir -p "$EASY_WG_QUICK_DIR"
wget -P "$EASY_WG_QUICK_DIR" https://raw.githubusercontent.com/burghardt/easy-wg-quick/master/easy-wg-quick
chmod +x "$EASY_WG_QUICK_SCR"

# Манипуляции по python
chmod +x "$WIREGRAM_SCR"
python3 -m venv $VENV_DIR
source "$VENV_DIR/bin/activate"
pip install -r "$WIREGRAM_DIR/requirements.txt"
deactivate

# Создаем и запускаем сервис
echo "[Unit]
Description=wiregram

[Service]
Type=simple
User=root
ExecStart=$VENV_DIR/bin/python $WIREGRAM_SCR
Restart=always

[Install]
WantedBy=multi-user.target" > /etc/systemd/system/wiregram.service

mkdir "$WIREGRAM_DIR/clients"
systemctl enable wiregram.service
systemctl start wiregram.service



