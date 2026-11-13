# S04 · Начальные состояния протокола Minecraft 1.7.10

Задача: [#17](https://github.com/zenoaugmentis/horizon-NTM/issues/17).
Подготовлено по ручным проверкам Zeno, предоставленному выводу зондов
и закреплённым открытым исходникам независимой реализации.
Дата оформления: 2026-11-14. Статус: техническая часть подготовлена к PR и review.

## 1. Область и доказательства

Целевая версия — vanilla Minecraft Java Edition 1.7.10, protocol 5.
Документ определяет framing, handshake/status/login и вход в play.
Полный каталог play-пакетов, Forge/FML handshake, чанки и gameplay
не входят в выполненные измерения. Реализация кодека Horizon — N01;
расширенные эталонные сетевые сценарии — S07.

Обозначения: C→S — клиент серверу, S→C — сервер клиенту.
«Измерено» означает результат ручного запуска пользователя; «схема» —
описание независимой реализации, не подтверждённое этим опытом.

Источники:

1. [Ручной отчёт](../reports/S04-manual-2026-11-14.md), три начальных обмена и два отказа на несовместимую версию.
2. [PrismarineJS minecraft-data, protocol.json](https://github.com/PrismarineJS/minecraft-data/blob/9b995542ab4a17837dee785439954e43d031b33e/data/pc/1.7/protocol.json),
   commit `9b995542ab4a17837dee785439954e43d031b33e`,
   blob `a835f549be5cbf6ff7e9803da395e7367c939c20`.
   Схема прочитана непосредственно; исходный код не переносился.
3. [S01: версии и происхождение стенда](versions.md).
   Хеш JAR из S01 в этой сессии повторно не измерялся.
4. [Контракт шифрования и session-проверки](protocol-5-encryption.md)
   со ссылками на закреплённые исходники и границами локальных тестов.

Upstream Horizon в рамках S04 не проверялся. Известная из начала сессии
база fork — `8322f0fac91f56e6bed31a8dc9677cc90b2bce62`;
это не upstream SHA и не гарантия актуального HEAD. Пути crates/API
не закрепляются без отдельной проверки дерева репозитория.

## 2. Framing и типы

TCP — поток: один read не обязан возвращать целый пакет; один TCP-сегмент
может содержать несколько пакетов. Чтение выполняется до требуемой длины.

Обычный пакет: `Length: VarInt | Packet ID: VarInt | Payload`.
Length считает ID и payload, но не собственные байты длины.
Значение ID определяется состоянием и направлением, а не только числом.
В схеме login 1.7 отсутствует Set Compression; современную оболочку
`Data Length + compressed packet` к этим пакетам применять нельзя.
Сжатие данных внутри отдельных play-пакетов — другой механизм.

| Тип | Представление |
|---|---|
| VarInt | 32-битное число, группы по 7 бит младшими вперёд, старший бит — продолжение; до 5 байт; не ZigZag |
| Byte / Unsigned Byte | 1 байт, соответственно signed / unsigned |
| Short / Unsigned Short | 2 байта, big-endian, соответственно signed / unsigned |
| Int | 4 байта, signed, big-endian |
| Long | 8 байт, signed, big-endian |
| String | VarInt длины UTF-8 в байтах, затем UTF-8; это не NBT modified UTF-8 |
| Short-prefixed byte array | Short длины, затем байты; для массивов login длина должна быть неотрицательной |

Наблюдения подтверждают использованные положительные VarInt, ASCII-строки,
порт и Long ping; отрицательные VarInt, Unicode и пределы сервера не проверены.
Лимит тела в комплектном зонде — 1 MiB, технический предел инструмента,
а не установленный лимит протокола. Зонд отклоняет отрицательные длины,
обрывы, VarInt длиннее 5 байт и ненулевой остаток payload.

## 3. Состояния

| Текущее состояние | Событие | Следующее состояние |
|---|---|---|
| Handshaking | C→S Handshake, nextState=1 | Status |
| Handshaking | C→S Handshake, nextState=2 | Login |
| Status | Request / Response / Ping / Pong | Status; затем закрытие соединения |
| Login, online | Login Start → Encryption Request | Login, ожидание Encryption Response |
| Login, online, по схеме | Encryption Response и успешная авторизация | Login Success, затем Play |
| Login, offline | Login Start → Login Success | Play |
| Login | Disconnect | Закрытие |
| Play | Join Game | Play |

Получение Login Success меняет таблицу ID: следующий пакет уже разбирается
как Play. В протоколе 5 нет отдельного Configuration-состояния.
В offline-опыте первым полученным play-пакетом был Join Game.
Это наблюдение vanilla-стенда, не утверждение о любой модификации сервера.

## 4. Handshaking

C→S `0x00`, поля строго в порядке:

| Поле | Тип | Использованное значение |
|---|---|---|
| Protocol Version | VarInt | 5 |
| Server Address | String | `127.0.0.1` |
| Server Port | Unsigned Short | 25565 (`63 dd`) |
| Next State | VarInt | 1 status / 2 login |

Измерены обе ветки и отказы на protocol=4/6 при nextState=2.
Сервер ответил Login Disconnect сразу после Handshake, до Login Start:
для 4 — `Outdated client! Please use 1.7.10` (38 байт тела),
для 6 — `Outdated server! I'm still on 1.7.10` (45 байт тела).
Неверный state и legacy ping `FE` не проверялись. Legacy ping не следует обрабатывать как обычный framed ID `0xFE`.

Вектор status, включая длину:
`0f 00 05 09 31 32 37 2e 30 2e 30 2e 31 63 dd 01`.
Вектор login отличается последним байтом `02`.

## 5. Status

| Направление | ID | Пакет | Payload |
|---|---|---|---|
| C→S | 0x00 | Status Request | Пустой |
| S→C | 0x00 | Status Response | String с JSON |
| C→S | 0x01 | Ping | Long |
| S→C | 0x01 | Pong | Long, копия ping |

Все четыре пакета измерены. Сервер сообщил `version.name="1.7.10"`,
`version.protocol=5`, `players.max=20`, `players.online=0`,
`description="A Minecraft Server"` (строка).
Нельзя требовать конкретный порядок JSON-полей или считать длину 111
константой. Состав необязательных полей и другие формы description
этим опытом не проверены.

Request frame: `01 00`.
Ping frame: `09 01 01 02 03 04 05 06 07 08`.
Pong вернул Long `0x0102030405060708` без изменения.

## 6. Login

| Направление | ID | Пакет | Payload в порядке следования | Основание |
|---|---|---|---|---|
| C→S | 0x00 | Login Start | Username: String | Измерено |
| S→C | 0x00 | Disconnect | Reason: String с JSON | Измерено для protocol 4/6 |
| S→C | 0x01 | Encryption Request | Server ID: String; Public Key: Short-prefixed bytes; Verify Token: Short-prefixed bytes | Измерено |
| C→S | 0x01 | Encryption Response | Shared Secret: Short-prefixed bytes; Verify Token: Short-prefixed bytes | Схема |
| S→C | 0x02 | Login Success | UUID: String; Username: String | Измерено offline |

Login Start с именем S04Probe:
`0a 00 08 53 30 34 50 72 6f 62 65`.
Ограничение длины имени и невалидные имена не измерялись.

Online-опыт: Server ID пуст, ключ 162 байта, verify token 4 байта,
тело 172 байта: `1 ID + 1 пустая String + 2 + 162 + 2 + 4`.
Эти длины — наблюдение стенда; длину публичного ключа нельзя фиксировать
константой в универсальном декодере. Ключ и token не выводились.

Offline-опыт: Login Success имеет тело 47 байт. UUID разобран как String
и принят Python uuid.UUID; точное текстовое представление в выводе отсутствует.
Значение UUID, его длина и соответствие offline-алгоритму не зафиксированы.
Имя совпало с S04Probe. Проверка синтаксиса UUID не является авторизацией.

Полный контракт online-обмена, включая RSA padding, AES и session hash,
описан в [дополнении](protocol-5-encryption.md). Encryption Response в
реальный сервер не отправлялся. Успешный online-login не проверен из-за
отсутствия авторизованного клиента; это обоснованное ограничение стенда.
Криптографические API и границы потока проверены отдельно на синтетике.

## 7. Первый пакет Play

S→C `0x01`, Join Game:

| Поле | Тип | Измерено |
|---|---|---|
| Entity ID | Int | 290 |
| Game Mode | Unsigned Byte | 0 |
| Dimension | Byte | 0 |
| Difficulty | Unsigned Byte | 1 |
| Max Players | Unsigned Byte | 20 |
| Level Type | String | `default` |

Длина тела: `1 + 4 + 1 + 1 + 1 + 1 + 1 + 7 = 17` байт.
Entity ID — результат конкретного запуска, не эталонная константа.
Пакет не содержит современной отдельной simulation distance или registry codec.
Нельзя добавлять поля из форматов более новых версий.

У Handshaking нет отдельного S→C ответа об успехе: сервер использует
выбранное состояние. Для Play нет универсального обязательного первого
C→S пакета или подтверждения Login Success: последовательность определяется
клиентом и событиями. Первый фактический C→S Play в этих опытах не снимался.
Keep Alive, позиция, чанки, инвентарь и сообщения не исследовались. Схема источника покрывает их, но документ не выдаёт их
за проверенные сценарии. Следующий практический этап — S07.

## 8. Воспроизведение и приёмка

Команды и результаты — в ручном отчёте. Единый `tools/probe_s04.py`
содержит режимы status, online, offline и reject. Он не меняет конфигурацию сервера.
В режиме offline вход S04Probe может создать данные игрока в мире.
Новый зонд появился после исторических запусков: на реальном сервере
в этой сессии он не запускался, проверен только локально синтетически.

| Критерий S04 | Статус |
|---|---|
| Состояния и начальные ID/payload/переходы | Описаны; три успешных начальных ветки и два отказа измерены; границы явно помечены |
| Команды и результаты | Приложены |
| CI и code review | Не выполнены этим комплектом; требуются в PR |
| Нет JAR/assets/миров/токенов/декомпиляции | В комплект входят только собственные тексты и Python |

Это контракт начального обмена, а не готовый сетевой стек и не доказательство
полной совместимости клиента/сервера. Закрывать issue следует после review
согласованной области документа и прохождения CI.
