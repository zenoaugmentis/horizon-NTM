# S01 · Эталон Minecraft 1.7.10: версии, источники, legal setup

Статус: черновик контракта S01 (#14). Дата проверки источников: 2026-11-08.

Этот документ — единственный источник истины о том, **с какой именно** 1.7.10 сравнивается
Horizon-NTM. Все остальные спецификации M1 (S02–S11) ссылаются на версии отсюда, а не
повторяют их.

## 1. Эталонные версии

| Компонент | Версия | Зачем |
|---|---|---|
| Minecraft Java Edition | `1.7.10` (release, 2014-05-14) | ванильное поведение, формат мира, ассеты |
| Сетевой протокол | `5` | S04, S07, M5 |
| `pack_format` ресурс-пака | `1` | S05, M3 |
| Версия формата мира (Anvil) | `19133` (`level.dat` → `Data.version`) | S03, S06, M2 |
| Minecraft Forge | `10.13.4.1614` (recommended и latest для 1.7.10) | только для сверки поведения модов, M6–M9 |
| Java для эталонного клиента/сервера | Java 8 (`jre-legacy`, majorVersion 8) | Forge 1.7.10 не запускается на Java 9+ |

`1.7.10` — последний релиз ветки 1.7; более поздних патчей нет. Снапшоты и pre-release
(`1.7.10-pre*`) эталоном **не являются**.

## 2. Контрольные суммы

Источник: официальный манифест Mojang
`https://piston-meta.mojang.com/mc/game/version_manifest_v2.json` → запись `1.7.10` →
`https://piston-meta.mojang.com/v1/packages/ed5d8789ed29872ea2ef1c348302b0c55e3f3468/1.7.10.json`.
SHA-1 скачанного version JSON совпал с SHA-1 в манифесте.

| Файл | SHA-1 | Размер, байт |
|---|---|---|
| version JSON `1.7.10.json` (piston-meta) | `ed5d8789ed29872ea2ef1c348302b0c55e3f3468` | — |
| `client.jar` (`versions/1.7.10/1.7.10.jar`) | `e80d9b3bf5085002218d4be59e668bac718abbc6` | 5 256 245 |
| `server.jar` (`minecraft_server.1.7.10.jar`) | `952438ac4e01b4d115c5fc38f891710c4941df29` | 9 605 030 |
| `windows_server.exe` | `a79b91ef69b9b4af63d1c7007f60259106869b21` | 9 999 270 |
| asset index `indexes/1.7.10.json` | `1863782e33ce7b584fc45b037325a1964e095d3e` | 72 996 (объекты: 112 396 854) |
| client log config `client-1.7.xml` | `50c9cc4af6d853d9fc137c84bcd153e2bd3a9a82` | 966 |
| server log config `log4j2_17-111.xml` | `4bb89a97a66f350bc9f73b3ca8509632682aea2e` | — |

Forge, источник `https://maven.minecraftforge.net/net/minecraftforge/forge/1.7.10-10.13.4.1614-1.7.10/`
(файлы `.sha1` рядом с артефактами; версия подтверждена `promotions_slim.json`):

| Файл | SHA-1 |
|---|---|
| `forge-1.7.10-10.13.4.1614-1.7.10-installer.jar` | `fccafccf8ad4ce6d9f008e786b48ff53172bf9de` |
| `forge-1.7.10-10.13.4.1614-1.7.10-universal.jar` | `25fd97f72beca728112256938e03e8105b1b78cc` |

Эти же значения зашиты в `tools/verify_vanilla_1710.py`. Меняются только вместе.

### Ключевые библиотеки клиента (из version JSON)

Полезны для понимания поведения, **не** для переноса кода: LWJGL `2.9.1`, Netty `4.0.10.Final`,
authlib `1.5.21`, Log4j `2.0-beta9`, Guava `15.0`, Gson `2.2.4`, paulscode SoundSystem `20120107`.
Главный класс клиента — `net.minecraft.client.main.Main`.

## 3. Legal setup: как получить эталон

Правило проекта: **мы публикуем только хэши и инструкции, никогда — сами файлы.**
Каждый разработчик получает эталон сам, из официальных источников, на свою лицензию.

1. **Клиент.** Купленная копия Minecraft: Java Edition → официальный лаунчер → «Установки» →
   новая установка, версия `release 1.7.10` → запустить один раз. Лаунчер скачает
   `versions/1.7.10/1.7.10.jar`, `1.7.10.json`, библиотеки и ассеты в каталог `.minecraft`.
   Для изоляции укажите в установке отдельный каталог игры, например
   `%USERPROFILE%\horizon-ref\1.7.10` (Windows) или `~/horizon-ref/1.7.10` (Linux).
2. **Сервер.** `server.jar` по URL из version JSON (поле `downloads.server.url`). Запуск
   сервера означает согласие с Minecraft EULA (`eula=true` в `eula.txt`) — каждый ставит
   это сам, в репозиторий `eula.txt` не попадает.
3. **Forge.** Installer с официального `files.minecraftforge.net` (версия из раздела 1),
   «Install client» в **отдельный** каталог игры, не в основной. Forge-установка нужна только
   задачам, где сверяется поведение модов (M6–M9); ванильные задачи M1–M5 сверяются
   с чистым 1.7.10 без Forge.
4. **Java 8.** Лаунчер использует свой `jre-legacy`. Для сервера и Forge установите
   любую сборку Java 8 (например Eclipse Temurin 8) и запускайте её явным путём.

### Обязательно: защита от Log4Shell (CVE-2021-44228)

1.7.10 использует Log4j `2.0-beta9`, он уязвим. Официальный лаунчер уже подставляет
исправленный `client-1.7.xml` (раздел 2). **Сервер** запускайте только с исправленным
конфигом Mojang для версий 1.7–1.11.2:

```
java -Dlog4j.configurationFile=log4j2_17-111.xml -jar minecraft_server.1.7.10.jar nogui
```

`log4j2_17-111.xml` — по ссылке
`https://launcher.mojang.com/v1/objects/4bb89a97a66f350bc9f73b3ca8509632682aea2e/log4j2_17-111.xml`
в рабочий каталог сервера. Эталонный сервер слушает только `127.0.0.1`
(`server-ip=127.0.0.1` в `server.properties`) и не выставляется в интернет.

## 4. Локальная проверка эталона

```
python tools/verify_vanilla_1710.py --game-dir "%USERPROFILE%\horizon-ref\1.7.10" --server-jar "%USERPROFILE%\horizon-ref\server\minecraft_server.1.7.10.jar" --forge-universal "%USERPROFILE%\horizon-ref\forge\libraries\net\minecraftforge\forge\1.7.10-10.13.4.1614-1.7.10\forge-1.7.10-10.13.4.1614-1.7.10.jar"
```

Все аргументы необязательны; не переданные компоненты отмечаются `SKIPPED`. Скрипт:

- только читает файлы и считает SHA-1/размер, ничего не копирует и не распаковывает;
- печатает отчёт и с `--report путь.json` пишет его в JSON — **только** имена компонентов,
  статусы, хэши и размеры, без абсолютных путей пользователя;
- возвращает код `0`, если всё переданное совпало, `1` при несовпадении или отсутствии файла.

Отчёты кладите в `.local/` (игнорируется git). Когда эталон проверен у разработчика,
он отмечает это в таблице ниже через PR.

| Кто | ОС | client | server | Forge | Дата |
|---|---|---|---|---|---|
| Slava-Gusak (S01) | Windows 11 | не проверено | OK (файл с `launcher.mojang.com`) | не проверено | 2026-11-08 |

Тесты скрипта (поддельная установка, настоящие jar не нужны):

```
python -m unittest discover -s tests -p "test_verify_vanilla_1710.py" -v
```

## 5. Что запрещено коммитить

`.jar`, `.exe`, ассеты и `indexes/`, распакованные или декомпилированные классы, маппинги
MCP/SRG, миры и `level.dat`, `eula.txt`, `launcher_profiles.json`, токены и
`accessToken`, логи с именем аккаунта. `.gitignore` закрывает `.local/`, `*.jar`, `*.exe`.
Политика лицензий в целом — задача A06.

## 6. Где закрепляются версии модов

Версии модов здесь **не** фиксируются — у каждого своя задача с правовой проверкой:
HBM's NTM — `H01`, MCHeli — `V01`, OpenComputers — `O01`. Они обязаны ссылаться на Forge
`10.13.4.1614` из этого документа или явно обосновать другую сборку.

## 7. Источники

- Манифест версий Mojang: https://piston-meta.mojang.com/mc/game/version_manifest_v2.json
- Version JSON 1.7.10: https://piston-meta.mojang.com/v1/packages/ed5d8789ed29872ea2ef1c348302b0c55e3f3468/1.7.10.json
- Forge promotions: https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json
- Forge maven: https://maven.minecraftforge.net/net/minecraftforge/forge/1.7.10-10.13.4.1614-1.7.10/
- Mojang о Log4Shell: https://www.minecraft.net/en-us/article/important-message--security-vulnerability-java-edition
- Протокол 5 и история версий: https://minecraft.wiki/w/Java_Edition_1.7.10 (только как справка;
  тексты Minecraft Wiki под CC BY-NC-SA, в репозиторий их не копируем)
