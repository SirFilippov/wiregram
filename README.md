# wiregram
Готовое решение "из коробки" для управления клиентами wireguard с помощью телерам-бота.

Ставится в несколько команд на только что оформленный VDS.

Скрипт написан на python мной, начинающим разработчиком, и сделан для людей, не сильно дружащих с консольным управлением ос и которые не хотят сильно заморачиваться с настройкой wireguard.

Поэтому установка максимально упрощена и сводится к нескольким командам, после которых вы сможете управлять своим VPN-сервером через телеграм
## Перед установкой
Данное решение сделано для максимально малого количества действий по установке, поэтому установка унифицирована под структуру со стандартными VDS-серверами предлагаемыми большинством популярных провайдеров и протестирована мной на системе Ubuntu 22.04.

В связи с этим для успешной установки и работы желательно использовать VDS c Ubuntu 22.04.

## Установка
Проверяем есть ли у нас на сервере git
```
git --version
```
Если гит уже установлен, то терминал выдаст что-то вроде:

> git version X.XX.X

где вместо X цифры версии

Если гит не установлен, то устанавливаем:
```
sudo apt install git
```
Далее вводим в терминал команду, которая запросит токен телеграм-бота, телеграм-id администраторов, и установит всё необходимое.
```
cd /home && git clone https://github.com/SirFilippov/wiregram.git && chmod +x /home/wiregram/setup_scr.sh && sudo /home/wiregram/setup_scr.sh
```
Бот не будет реагировать на сообщения от пользователей, которые не являются администраторами.

Где взять токен бота

Где взять id пользователя

Если во время установляется появится цветное окно, нажимайте ENTER.

После завершения всех установок можно исполльзовать бота

## Управление

Все доступные функции перечислины в кнопке "Меню" или по вызову слеша / В крадце о них:

- /add_client - Добавить клиента: запрашивает имя, фамилию, номер телефона клиента для идентификации и уведомлений.
Так же запрашивает статус подписки: VIP - бессрочная, simple - на срок, который вы задаете в следующем сообщении (удаление клиента по сроку будет реализовано в дальнейшем)
Далее выбирается устройство. Сделано для формы инструкции по добавлению туннеля на устройство клиента.
- /del_client - Удаление клиента: бот присылает id, имя, фамилию всех пользователей. В ответ нужно ввести id пользователя, которого хотите исключить.
- /show_clients - Список пользователей: бот присылает id, имя, фамилию всех пользователей
- /get_conf - Файл конфигурации клиента: бот присылает id, имя, фамилию всех пользователей. В ответ нужно ввести id пользователя, конфигурационный файл которого вы хотите получить. Дополнительно бот выдаст qr-код.
- /wg_restart - Рестарт wireguard: рестарт wireguard. Помогает в случае каких-либо проблем с соединением. В моем случае рестарт помогал, когда скорость через VPN сервер резалась до 1-2 Мб\с.
- /wg_show - Статистика wireguard: вывод внутренней команды wireguard wg_show (статистика по клиентам) в телеграм. В планах привести вывод в читабельный вид.
- /cancel - Выйти из операции/очистить память: позволяет выйти из операции на любой стадии и очистисть память в которую сохраняются ваши ответы. Использовать рекомендуется в любой непонятной ситуации.
