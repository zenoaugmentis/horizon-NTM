# Лицензии, атрибуция и границы ассетов

**Issue:** #10 (`A06`) · **Проверено:** 2026-11-08 · Это инженерная политика проекта, а не юридическая
консультация. Спорные места помечены **⚠** и требуют решения владельца репозитория.

## 1. Лицензия проекта

- horizon-NTM распространяется под **GNU GPL v3** (`LICENSE`).
- ⚠ В репозитории нет указания «only» или «or later». Предложение: **GPL-3.0-or-later** — так
  код можно будет объединять с будущими версиями GPL. Решение записать в `README.md` и в
  `license` полях `Cargo.toml` наших crates (`GPL-3.0-or-later` или `GPL-3.0-only`).
- Импортированный код Horizon остаётся под MIT своих авторов: заголовки файлов и `LICENSES/Horizon-MIT.txt`
  не удаляются и не переписываются. Проект в целом при этом распространяется под GPLv3: MIT это допускает.

## 2. Компоненты и их лицензии

| Компонент | Лицензия | Можно включать в репозиторий? | Условие |
|---|---|---|---|
| **Horizon** (код) | MIT | Да | Сохранить `LICENSES/Horizon-MIT.txt` и `THIRD_PARTY_NOTICES.md` upstream |
| Сторонние части Horizon: wgpu-hal, naga | MIT **или** Apache-2.0 | Да | Обе лицензии лежат в `third_party/*/` |
| libmimalloc-sys, mimalloc, Ponder/Catnip, Pixelarticons, Hugeicons, AMD FidelityFX, CIT Resewn, FusionExamples, BlueMap, JOML, JEI, Flywheel, Starling | MIT | Да | Уведомления из `THIRD_PARTY_NOTICES.md` |
| Шрифты Pixelify Sans, Geist, Bricolage Grotesque | SIL OFL 1.1 | Да | Файлы `OFL-*.txt` рядом со шрифтами |
| fdlibm (порт) | разрешение Sun «freely granted, provided that this notice is preserved» | Да | Уведомление Sun в заголовке файлов |
| Логотипы Fabric/Quilt/NeoForge/Forge, символ Microsoft (лаунчер Horizon) | Товарные знаки владельцев (арт Quilt — CC0, NeoForge — CC BY 4.0) | Только для указания загрузчика / входа Microsoft | ⚠ при ребрендинге лаунчера пересмотреть |
| **HBM's NTM** (HbmMods/Hbm-s-Nuclear-Tech-GIT, 1.7.10) | **LGPL-3.0** (README: «GNU Lesser General Public License version 3»; в репозитории файлы `LICENSE` = GPLv3 и `LICENSE.LESSER`) | Код — да, порт допустим | Сохранить копирайт и лицензию; порт под GPLv3 совместим. Ассеты — см. раздел 4 |
| Форки NTM (Space и др.) | разные (на Modrinth встречается GPL-3.0-only) | Проверять каждый отдельно | Брать только с конкретного коммита, лицензию фиксировать в PR |
| **OpenComputers** (MightyPirates, ветка `master-MC1.7.10`) | Код **MIT** (© 2013–2015 Florian "Sangar" Nücke); README: «All assets are public domain, unless otherwise stated» | Да | Сохранить MIT и указание авторства; проверить файлы `LICENSE-*` для встроенных сторонних частей |
| **MCHeli** (EMB4) | **All rights reserved**, закрытый и обфусцированный код; разрешено только распространение в некоммерческих модпаках | **Нет**: ни код, ни модели, ни текстуры, ни звуки, ни конфиги-паки | Только clean-room (раздел 5) |
| Форки MCHeli (Overdrive, Community Edition и др.) | Заявляют GPL-3 | **Нет** | ⚠ Это производные от закрытого кода; заявленная лицензия не гарантирует прав. Не использовать как источник |
| **Minecraft Forge 1.7.10** | LGPL-2.1 (+ отдельные условия для данных MCP) | Код не нужен | Мы не исполняем Forge. Повторяем поведение API, а не копируем код. Данные MCP (mappings) **не** распространяются без разрешения MCP |
| **Minecraft 1.7.10** (код, ассеты, звуки, языковые файлы) | Собственность Mojang/Microsoft, Minecraft EULA | **Нет** | Только у пользователя локально (раздел 3) |
| **Minecraft Wiki** (minecraft.wiki) | CC BY-NC-SA 3.0; страницы, импортированные из wiki.vg, — CC BY-SA 3.0 | Текст и таблицы **не копировать** | NC несовместима с GPL. Брать факты (номера ID, поля пакетов), писать своими словами, ссылаться на источник |

## 3. Что запрещено коммитить

Проверка `tools/check_public_tree.py` (приходит с импортом upstream, подключается в CI задачей A04)
ловит часть этого автоматически. Остальное — ответственность автора PR и ревьюера.

1. `.jar` любых версий Minecraft, Forge, модов; `.class`; распакованные классы.
2. Ассеты Minecraft: текстуры, модели, звуки, музыка, `lang`-файлы, шрифты, `pack.png`.
3. Декомпилированный код Minecraft, Forge и MCHeli; патчи Forge; mappings MCP/SRG/MCPBot.
4. Подготовленные ресурсы (`.local/`, `horizon-data.bin`), кэш лаунчера.
5. Миры с чужих серверов и любые миры, где есть данные игроков (UUID, ники, координаты баз).
6. Сетевые дампы с токенами сессии, `accessToken`, файлы `launcher_profiles.json`, `.minecraft/`.
7. Любой контент MCHeli и его форков (раздел 2).
8. Ассеты NTM — до решения из раздела 4.

Эталонные данные (хэши, метаданные, ожидаемые значения) коммитить можно, если они получены
скриптом у пользователя и не воспроизводят защищённое содержимое (S01, S06).

## 4. Ассеты модов

- **OpenComputers:** ассеты в public domain, «unless otherwise stated». Перед включением конкретного файла
  проверить, нет ли рядом иной лицензии. Указать источник в `THIRD_PARTY_NOTICES.md`.
- **NTM:** README говорит о лицензии на «software» и не выделяет ассеты. ⚠ До явного решения ассеты
  **не коммитятся**. Вместо этого порт загружает их из `.jar` NTM, который есть у пользователя, — тем же
  способом, каким Horizon берёт ресурсы Minecraft из установленной игры (`horizon-port-pack`).
  Это решение пересматривается в задаче H01 после уточнения у авторов NTM.
- **MCHeli:** только собственные модели и текстуры проекта.

## 5. Как работать с закрытыми источниками (clean-room)

Для Minecraft 1.7.10 и MCHeli:

- Источник поведения — **наблюдение** (запуск игры, логи, пакеты, сохранения) и публичная документация.
- Если разработчик читал декомпилированный код Minecraft 1.7.10 для понимания поведения, это остаётся
  у него локально. В репозиторий попадает описание поведения и собственная реализация, не перевод
  кода строка в строку. ⚠ Upstream Horizon пишет порты, сверяясь с декомпилированными исходниками
  26.3 (комментарий в `Cargo.toml`, `docs/decompilation-status.md`) и держит в `datafix/` таблицы,
  «taken from vanilla's code». Это решение Horizon; для horizon-NTM лучше придерживаться
  описанной здесь более строгой схемы.
- Для MCHeli — никакого чтения декомпилированного кода вообще. Спецификацию пишет один человек по
  наблюдениям, реализацию — по спецификации.

## 6. Обмен кодом с upstream Horizon

Правила Horizon запрещают GPL, LGPL, MPL и закрытый код, даже для чтения
(upstream `CONTRIBUTING.md`, «Only original code, or code whose license allows it»). Поэтому:

- изменения движка (`crates/horizon-*`), которые мы хотим предложить в upstream, пишутся **без**
  использования кода NTM, Forge и прочего GPL/LGPL-кода;
- PR, в которых использован код NTM, помечаются меткой `upstream:no` (её нужно создать) и в upstream не отправляются.

## 7. Атрибуция в проекте

- Добавить в `README.md` отказ от связи с Mojang (сделано в этом PR).
- Порт любого фрагмента из NTM/OpenComputers указывает в PR репозиторий, коммит и путь исходного
  файла; в заголовке нового файла — копирайт и лицензия оригинала.
- Свои сторонние включения перечисляются в разделе «horizon-NTM» в конце `THIRD_PARTY_NOTICES.md`
  (файл приходит с импортом upstream; отдельный файл не заводится, чтобы не конфликтовать с импортом).

## 8. Как проверено

```bash
curl -sSL https://raw.githubusercontent.com/HbmMods/Hbm-s-Nuclear-Tech-GIT/master/README.md | grep -n -A2 '^# License'
curl -sSL -o /dev/null -w '%{http_code}\n' https://raw.githubusercontent.com/HbmMods/Hbm-s-Nuclear-Tech-GIT/master/LICENSE.LESSER   # 200
curl -sSL https://raw.githubusercontent.com/MightyPirates/OpenComputers/master-MC1.7.10/LICENSE | head -3
curl -sSL https://raw.githubusercontent.com/MightyPirates/OpenComputers/master-MC1.7.10/README.md | grep -n 'public domain'
git -C horizon ls-files | grep -iE '(^|/)(licen[cs]e|copying|notice|ofl)[^/]*$'   # клон upstream
```

Источники, которые нельзя проверить скриптом:

- MCHeli: страница мода на CurseForge (Fureniku): https://www.curseforge.com/minecraft/mc-mods/mcheli-minecraft-helicopter-mod —
  «licensed as all rights reserved», мод закрытый.
- Лицензия Minecraft Wiki: https://meta.weirdgloop.org/w/Meta:Copyrights — Minecraft Wiki под CC BY-NC-SA 3.0.
- Forge: `LICENSE.txt` в дистрибутиве Forge 1.7.10 — LGPL-2.1 и отдельный раздел «MCP Data».
- Minecraft EULA: https://www.minecraft.net/en-us/eula
