# simple-telegram-post-suggest
Простой бот для предложки картинок с текстом в каналы Telegram
# Настройка
Создаете бота через @botfather, токен вставляете в переменную `token`, добавляете бота в администраторы канала<br>
Настройка бота происходит через команду `/init <id-канала>;<id-админа>`<br>
Где `<id-канала>` - идентификатор канала в который будут делаться посты, например: `@durov` или `-1001111111`(для приватных каналов), команда работает только один раз, после изначальной настройки блокируется.<br>
Пример команды: `/init -1001179634177;123321123`<br><br>
Для удаления всех данных бота достаточно удалить файл `database.db`, он в формате SQLite, если что.

