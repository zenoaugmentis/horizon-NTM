# S04 · Online-login: шифрование и проверка сессии

Дополнение к [protocol-5.md](protocol-5.md). Цель — контракт protocol 5,
а не реализация аутентификации для конечного пользователя.

## Основание и границы

Ниже приведён разбор открытой независимой реализации. На сервере пользователя
измерен только Encryption Request. Успешный online-login не проверен:
имеющийся клиент запускается без лицензионной сессии, авторизованный клиент
на стенде недоступен. Это ограничение испытаний, не основание пропустить
описание online-ветки. Не требуется выдавать offline-вход за online-вход.

Источники закреплены по commit:

- node-minecraft-protocol `dacf62ef40cc559429537a303ac246ee9cede175`:
  [клиентский обмен](https://github.com/PrismarineJS/node-minecraft-protocol/blob/dacf62ef40cc559429537a303ac246ee9cede175/src/client/encrypt.js),
  [серверный login](https://github.com/PrismarineJS/node-minecraft-protocol/blob/dacf62ef40cc559429537a303ac246ee9cede175/src/server/login.js),
  [AES-потоки](https://github.com/PrismarineJS/node-minecraft-protocol/blob/dacf62ef40cc559429537a303ac246ee9cede175/src/transforms/encryption.js),
  [расположение шифрования относительно framing](https://github.com/PrismarineJS/node-minecraft-protocol/blob/dacf62ef40cc559429537a303ac246ee9cede175/src/client.js).
- node-yggdrasil `ca6b1e61adece31e5cab049f652874c6deee85e0`:
  [join/hasJoined](https://github.com/PrismarineJS/node-yggdrasil/blob/ca6b1e61adece31e5cab049f652874c6deee85e0/src/Server.js),
  [signed hex digest](https://github.com/PrismarineJS/node-yggdrasil/blob/ca6b1e61adece31e5cab049f652874c6deee85e0/src/utils.js).

Это многоверсионная реализация: ветки profile signatures, signed chat,
Configuration и поля современных версий не переносятся в protocol 5.
Пакетные поля фильтруются схемой 1.7 из основного документа.
Пример различия реализации и vanilla: PrismarineJS генерирует непустой
serverId, а измеренный vanilla-сервер прислал пустую строку. Декодер должен
использовать переданное значение, а не требовать один из этих вариантов.

## Порядок обмена

1. C→S Handshake с protocol=5, nextState=2, затем Login Start.
2. S→C Encryption Request (login 0x01), пока без шифрования.
   Public Key — DER SubjectPublicKeyInfo RSA; Verify Token — случайные байты.
3. Клиент генерирует случайный общий секрет ровно 16 байт.
   Для online-авторизации клиент выполняет session join, связывающий профиль
   с hash данного соединения. Нельзя заменять это проверкой имени/UUID.
4. C→S Encryption Response (login 0x01), ещё в открытом framed-потоке:
   Shared Secret и исходный Verify Token независимо зашифрованы публичным
   RSA-ключом сервера с PKCS#1 v1.5 encryption padding (не OAEP).
   Оба результата передаются как Short-prefixed byte arrays.
5. После отправки всего Encryption Response клиент включает AES-потоки.
   Сервер читает полный незашифрованный ответ, расшифровывает оба массива,
   проверяет token на совпадение и использует полученный 16-байтный секрет.
   Несовпавший token или невалидное RSA-сообщение не допускают входа.
6. Сервер проверяет session hasJoined для имени и hash соединения.
   Только успешная проверка профиля позволяет отправить Login Success.
   Ошибка проверки приводит к отказу; точный JSON причины зависит от сервера
   и не зафиксирован измерением. После включения AES такой ответ зашифрован.
7. S→C Login Success разбирается в login, затем обе стороны используют
   таблицу Play. Для protocol 5 нет Login Acknowledged и Configuration.
   На vanilla offline-стенде первым S→C Play был Join Game 0x01.

Тайм-ауты, тексты отказов и поведение при недоступном session service в этой
сессии не измерялись. Нельзя переносить 30-секундный тайм-аут PrismarineJS
как установленную константу vanilla.

## AES и граница framing

Алгоритм: AES-128-CFB8, без padding. Ключ = 16 байт shared secret;
начальный IV = те же 16 байт. Для направлений C→S и S→C создаются отдельные
контексты с одинаковыми исходными key/IV. Каждый контекст непрерывен на
всём направлении соединения: он не сбрасывается ни на границе пакета,
ни на границе TCP read/write.

Шифруется весь framed-поток, включая VarInt Length и Packet ID.
Порядок отправки: payload → ID/framing → AES → TCP.
Порядок чтения: TCP → AES → framing → разбор пакета.
Пакетная оболочка и ID после расшифрования остаются прежними.
Нельзя сначала искать длину в зашифрованных байтах.

Нельзя смешивать AES-CFB128 и CFB8, сбрасывать IV на каждом пакете,
включать шифрование до Encryption Response или оставлять Length открытым.
Длины RSA ciphertext зависят от размера RSA-ключа, а не от длины секрета.

## Session hash и HTTP-обмен

Вход SHA-1: последовательная конкатенация `serverId ASCII bytes`,
`sharedSecret bytes`, `publicKey DER bytes`. Для измеренного пустого serverId
первый фрагмент имеет нулевую длину. Результат представляется как signed
big-endian 160-битное целое в шестнадцатеричном виде: без ведущих нулей,
с минусом для отрицательных значений. Это не обычный unsigned hexdigest.

Клиентский запрос в разобранной реализации:
`POST https://sessionserver.mojang.com/session/minecraft/join`,
JSON с accessToken, selectedProfile и serverId (вычисленный hash).
Серверный запрос:
`GET https://sessionserver.mojang.com/session/minecraft/hasJoined?username=...&serverId=...`.
Параметры URL кодируются. Ответ содержит идентичность подтверждённого профиля.

Эти endpoints описаны по исходникам; их текущая доступность и успешный
ответ в этой сессии не проверялись. Получение Microsoft/Minecraft-токенов
не входит в пакетный протокол 5. Реальные credentials в тесты, журналы
или репозиторий не включаются.

## Что проверено локально

`tests/test_s04_crypto.py` использует только искусственные ключи и сообщения:
RSA PKCS#1 v1.5, SPKI round-trip, зашифрованные secret/token с Short-длинами,
непрерывный CFB8 на нескольких framed-пакетах и фрагментах, отделение
Encryption Response от последующих зашифрованных байтов и signed hash.

Это проверка воспроизводимой модели и выбранных криптографических API,
а не соединение с Mojang, не проверка исходников Mojang и не доказательство
работоспособности online-входа на игровом стенде. Реальные сетевые результаты
и восстановление настроек — в ручном отчёте.
