# S01 — эталон Minecraft 1.7.10: версии, источники, локальная установка

**Issue:** #14 (`S01`) · **Проверено:** 2026-11-08 · Связано: [`../LEGAL.md`](../LEGAL.md) (A06)

Этот документ — точка отсчёта для всех задач M1–M9: с чем сравнивать поведение и как получить
эталон законно, ничего не публикуя.

## 1. Эталонные версии

| Компонент | Версия | Идентификатор / источник |
|---|---|---|
| Minecraft Java Edition | **1.7.10** (релиз 2014-06-26) | Протокол **5**, resource pack format **1**, минимальная Java — SE 6 (Minecraft Wiki, «Java Edition 1.7.10») |
| Клиент | `client.jar` | SHA-1 `e80d9b3bf5085002218d4be59e668bac718abbc6` (имя объекта в URL Mojang `piston-data.mojang.com/v1/objects/<sha1>/client.jar`) |
| Описание версии | `1.7.10.json` | SHA-1 `2e818dc89e364c7efcfa54bec7e873c5f00b3840` (`piston-meta.mojang.com/v1/packages/<sha1>/1.7.10.json`) |
| Сервер | `minecraft_server.1.7.10.jar` | SHA-1 берётся из `downloads.server.sha1` в `1.7.10.json` у пользователя (скрипт ниже печатает его) |
| Forge | **10.13.4.1614** (последняя сборка для 1.7.10) | Файл `forge-1.7.10-10.13.4.1614-1.7.10-universal.jar`. Рекомендуемая на сайте Forge — 10.13.4.1558; на ней часть модов падает с требованием «minimum 1566», поэтому эталон — 1614 |
| Java для эталона | **Java 8** | Forge 1.7.10 не работает на Java 9+. Официальный лаунчер ставит свою Java для старых версий |

Pre-release 1.7.10-pre1…pre4 эталоном **не** являются: у pre4 тот же протокол 5, но тесты сравниваются
только с релизом.

### Версии модов

Конкретные релизы модов фиксируются в первых задачах их milestone, не здесь:
NTM — H01, MCHeli — V01, OpenComputers — O01. В каждой задаче записывается: репозиторий, тег или
коммит, SHA-1 собранного `.jar`, лицензия на этом коммите (по правилам `LEGAL.md`). Предварительно:

- **HBM's NTM:** `HbmMods/Hbm-s-Nuclear-Tech-GIT`, ветка `master` (1.7.10), LGPL-3.0.
- **OpenComputers:** `MightyPirates/OpenComputers`, ветка `master-MC1.7.10`, MIT.
- **MCHeli:** 0.10.8 для 1.7.10 (последний выпуск на CurseForge, 2015-11-03). Используется **только как
  наблюдаемое поведение** в отдельной установке; код и ассеты не трогаются.

## 2. Как получить эталон законно

Нужен аккаунт Microsoft, на котором куплена Minecraft: Java Edition. Ничего из этого не коммитится.

1. **Клиент.** Официальный лаунчер → «Установки» → «Новая» → версия «release 1.7.10» → запустить один раз.
   Лаунчер скачает `versions/1.7.10/1.7.10.jar` и `1.7.10.json` в `.minecraft`.
   Prism Launcher / MultiMC тоже подходят; там jar лежит в `libraries/com/mojang/minecraft/1.7.10/`.
2. **Сервер.** Ссылка на `server.jar` — в поле `downloads.server.url` файла `1.7.10.json`. Положить в
   `.local/reference/1.7.10/server.jar` внутри клона (каталог `.local/` в `.gitignore`).
3. **Forge.** Отдельная установка (в официальном лаунчере — отдельный «Игровой каталог», в Prism — отдельный
   инстанс) с Forge **10.13.4.1614** с files.minecraftforge.net. Ванильный эталон и Forge-эталон не смешиваются:
   ванильные тесты гоняются без Forge.
4. **Log4Shell.** 1.7.10 уязвима к CVE-2021-44228 (Log4j). Официальный лаунчер патчит клиент сам. Для
   **сервера** (в том числе локального эталонного) по инструкции Mojang: положить рядом с jar файл
   `log4j2_17-111.xml` (SHA-1 `dd2b723346a8dcd48e7f4d245f6bf09e98db9696`, `launcher.mojang.com/v1/objects/<sha1>/log4j2_17-111.xml`)
   и запускать с `-Dlog4j.configurationFile=log4j2_17-111.xml`. Эталонный сервер не выставлять в интернет.

Пример запуска эталонного сервера:

```bash
cd .local/reference/1.7.10
java -Xmx2G -Dlog4j.configurationFile=log4j2_17-111.xml -jar server.jar nogui
```

## 3. Локальная проверка

```bash
python tools/verify_vanilla_1710.py --server-jar .local/reference/1.7.10/server.jar \
                                    --report .local/reference/1.7.10/report.json
```

Скрипт читает установку пользователя, считает SHA-1 и пишет **только хэши и номера версий**:

- `client jar` — сравнивается с `e80d9b3b…`; несовпадение = FAIL (модифицированный или чужой jar);
- `server jar` — сравнивается с `downloads.server.sha1` из `1.7.10.json`;
- `forge` — находит установленные сборки Forge 1.7.10 и их SHA-1; 1614 = OK, другая = WARN;
- `version json` — WARN при несовпадении (лаунчер может переписать файл).

Код выхода 0 — эталон совпадает. Хэш Forge и сервера, полученные у одного участника, вставляются в этот
документ, чтобы остальные сверялись с ними (таблица в разделе 4).

Тесты скрипта не требуют игры:

```bash
python -m unittest tests.test_verify_vanilla_1710 -v     # 8 тестов на поддельной установке
```

## 4. Подтверждённые хэши

Заполняется первым участником, прогнавшим скрипт на настоящей установке (PR с изменением только этой таблицы).

| Файл | SHA-1 | Кем проверено, дата |
|---|---|---|
| client.jar 1.7.10 | `e80d9b3bf5085002218d4be59e668bac718abbc6` | значение Mojang, см. раздел 1 |
| minecraft_server.1.7.10.jar | — | — |
| forge-1.7.10-10.13.4.1614-1.7.10 (universal) | — | — |

## 5. Что не делается в S01

- Эталонные миры и чанки — S06; сетевые сценарии — S07; таблица parity — S11.
- Исходный код и mappings Minecraft/Forge не скачиваются и не используются.

## Источники

- Minecraft Wiki, «Java Edition 1.7.10»: дата релиза, протокол 5, pack format 1, Java SE 6, ссылки на client.jar и 1.7.10.json.
- Форумы Forge: 10.13.4.1614 — последняя сборка, 10.13.4.1558 — рекомендуемая; отчёты о требовании «1566» у модов.
- Mojang, «Important Message: Security vulnerability in Java Edition» (2021-12-10): https://www.minecraft.net/en-us/article/important-message--security-vulnerability-java-edition
- CurseForge, MCHeli: файл `MC1.7.10_mcheli_0.10.8.zip` от 2015-11-03.
