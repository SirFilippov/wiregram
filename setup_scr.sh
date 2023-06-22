#!/bin/bash

# Кома для скачивания и установки моего репо:
#git clone https://github.com/SirFilippov/wiregram.git /home/wiregram && chmod +x /home/wiregram/setup_scr.sh && /home/wiregram/setup_scr.sh
# -y поставить на обновах



# Пути
VPNMANAGER_DIR=$"/home/wiregram"
ENV_DIR="$VPNMANAGER_DIR/tele_data.env"
VENV_DIR="$VPNMANAGER_DIR/venv"
VPNMANAGER_SCR="$VPNMANAGER_DIR/vpnmanager.py"
EASY_WG_QUICK_DIR="$VPNMANAGER_DIR/easy-wg-quick"
EASY_WG_QUICK_SCR="$VPNMANAGER_DIR/easy-wg-quick/easy-wg-quick"

# Создаем env
read -r -p "Введите токен бота: " bot_token
read -r -p "Введите телеграм-id администраторов через запятую без пробелов: " allowed_users
echo "TELE_TOKEN=$bot_token" > "$ENV_DIR"
echo "TELE_ADMIN_ID=$allowed_users" > "$ENV_DIR"

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
chmod +x "$VPNMANAGER_SCR"
python3 -m venv $VENV_DIR
source "$VENV_DIR/bin/activate"
pip install -r "$VPNMANAGER_DIR/requirements.txt"
deactivate

# Создаем и запускаем сервис
echo "[Unit]
Description=VPNManager

[Service]
Type=simple
User=root
ExecStart=$VENV_DIR/bin/python $VPNMANAGER_SCR
Restart=always

[Install]
WantedBy=multi-user.target" > /etc/systemd/system/vpnmanager.service

systemctl enable vpnmanager.service
systemctl start vpnmanager.service



