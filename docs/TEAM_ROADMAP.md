# Horizon-NTM — план командной разработки

**Статус:** предложение для GitHub Issues, *не* результат реального импорта. Дата: 2026-11-08.

**Назначение:** 1.7.10 native Rust engine на базе Horizon; затем модовая система и нативные реализации HBM’s NTM, MCHeli, OpenComputers. Существующие Java/Forge `.jar` не исполняются автоматически.

**Проверенные источники архитектуры:**
- https://github.com/horizon-rust/horizon/blob/main/AGENTS.md
- https://github.com/horizon-rust/horizon/blob/main/docs/architecture.md
- https://github.com/horizon-rust/horizon/blob/main/Cargo.toml

**Ограничение:** исходный `main` меняется; зафиксировать SHA через `A02`. Полная актуальная структура `zenoaugmentis/horizon-NTM` в этом исследовании не проверена. Указанные paths — предполагаемые точки входа, а не гарантия наличия каждого файла в целевом репозитории. Первые задачи обязаны устранить это ограничение.

## 1. Milestones — результаты, а не последовательность ожидания

| Milestone | Проверяемый результат | Issues |
|---|---|---:|
| M0: Базовая инфраструктура | Воспроизводимая сборка, история upstream, CI и правила совместной разработки | 9 |
| M1: Спецификации Minecraft 1.7.10 | Фикстуры, интерфейсы данных и критерии ванильной совместимости | 11 |
| M2: Legacy world core | Блоки, чанки, NBT, сохранение, тики и генерация | 13 |
| M3: Ресурсы и графика | Загрузка ассетов 1.7.10 и рендер старых блоков, UI | 9 |
| M4: Локальная играбельная 1.7.10 | Игровая механика, предметы, мобы и локальные тесты | 11 |
| M5: Сеть и сервер 1.7.10 | Подключение к серверу протокола 5 и headless-сервер | 9 |
| M6: Native Mod API | Расширяемые блоки, TileEntity, транспорт и модовые пакеты | 10 |
| M7: HBM’s NTM: вертикальный срез | Минимальная работающая производственная цепочка NTM | 9 |
| M8: MCHeli: прототип | Одна работающая управляемая машина с корректной сетевой моделью | 5 |
| M9: OpenComputers: прототип | Один программируемый компьютер и базовая периферия | 5 |

**Итого: 91 атомарных Issues** в 10 milestones. Все задачи имеют стабильный ID, предполагаемые пути, приоритет, тип, зависимости и критерии приёмки. Полный набор: [`planning/backlog.json`](../planning/backlog.json); табличная версия: [`planning/backlog.csv`](../planning/backlog.csv).

## 2. Как вести проект

**Иерархия:** 10 родительских EPIC Issues (по milestone) → самостоятельные дочерние Issues. В Project — одна доска по всем задачам.

**Labels (два независимых измерения):**
- `area:infra`, `area:reference`, `area:world`, `area:render`, `area:gameplay`, `area:network`, `area:modapi`, `area:ntm`, `area:mcheli`, `area:oc`;
- `kind:research`, `kind:contract`, `kind:implementation`, `kind:integration`;
- `priority:P0`, `priority:P1`, `priority:P2`;
- `size:S`, `size:M`;
- `blocked` — назначать только когда есть внешнее препятствие, а не вместо реальных dependency relationships.

**Project fields:** Status = `Backlog`, `Ready`, `In Progress`, `In Review`, `Blocked`, `Done`; Owner (Assignee); Milestone; Priority; Size. Не нужны отдельные статусные Labels — Project уже содержит Status.

**Правила:** одна задача = один ответственный; reviewers могут быть несколькими. Нельзя одновременно открывать два PR, меняющих один и тот же публичный интерфейс без согласования. Кодовая задача начинается только после определения контракта; исследовательские задачи не обязаны ждать сборки. Размер `S` = небольшая локальная правка, `M` = несколько согласованных правок, больше → разделить задачу. Каждый PR — один логический результат и тесты.

**Приоритет P0** означает критичность *внутри своего milestone*, а не приказ начать немедленно. Для текущей работы фильтруйте одновременно по Milestone и `Status=Ready`.

**Issue готово к взятию**, если завершены все `depends_on`, задокументированы ввод/вывод API, нет другого владельца, указан минимальный тест. **Done**, когда тесты проходят, принят review, обновлены документы и PR смержен. Закрывать issue только после merge. **Blocked** отражает реальную внешнюю зависимость в GitHub и не маскирует пробелы в документации.

**Безопасность / лицензии:** не коммитить `.jar` Minecraft, assets, декомпилированные исходники, токены, реальные миры, приватные данные или пиратские ресурсы. Подготовка ассетов должна брать оригинальную копию игры у пользователя. Проверить MIT Horizon, GPLv3 целевого проекта и права на каждый мод отдельно.

## 3. Параллельные дорожки

| Дорожка | Ответственность | Начинать с | Контракт с соседями |
|---|---|---|---|
| DevOps/QA | repo, baseline, CI, smoke tests | A01, A04, A06, S11 | фиксированный SHA + matrix версий |
| World/Data | block IDs, storage, generation | S02, S03, S06 → W01 | `LegacyBlock`, `Chunk`, TileEntity |
| Rendering/Assets | import pack v1, textures, mesh, GUI | S05 → R01, R02 | world/meshing state converter |
| Networking | protocol 5, status/login, packets | S04, S07 → N01 | packet schema + block codec |
| Gameplay | player, crafting, inventory, entities | S08, S09 → G01 | ItemStack + physics API |
| Mods | native API + mod inventory | S10 → X01 | mod lifecycle, events, registry |
| Content | NTM, MCHeli, OpenComputers | H01, V01, O01 | prototype scope and legal review |

*Независимыми являются не все задачи внутри дорожек.* Например, `R02` может идти отдельно от `W04`, а `R05` требует результатов обоих. Зависимости являются ориентиром, который уточняется после просмотра закреплённого SHA.

## 4. Критический путь до первой играбельной демонстрации

```
A01 → A02 → A03 → A04
                     ├─ S02 → W01 → W02 → R04 ─┐
S01 → S03 → S06 → W04 ───────────────────────────┼→ R05 → R09 ─┐
S01 → S05 → R01 → R02 ───────────────────────────┘             ├→ G11
S01 → S08 → G01 → G02, G05, G06 ────────────────────────────────┘
S01 → S09 → G03 ────────────────────────────────────────────────┘
```

Это **схема ключевых зависимостей**, не исчерпывающий DAG. Полный DAG — в `backlog.json`. Для многопользовательской 1.7.10 отдельный путь: `S04/S07 → N01 → N02 → N03/N04 → N05 → N09`.

**Главный риск:** глобальная замена модели блока, сохранений или networking способна затронуть десятки crates. Запрещать параллельную работу не надо — нужно заморозить минимальные контракты и изолировать адаптеры.

## 5. Первый спринт: не 100 задач сразу

Выпустить в Project только следующие базовые Issues:

- **A01** Проверить состав horizon-NTM и стратегию импорта upstream — research, P0; зависимости: нет.
- **A02** Зафиксировать upstream SHA и создать воспроизводимую базовую ветку — implementation, P0; зависимости: A01.
- **A03** Проверить локальную сборку исходного Horizon — integration, P0; зависимости: A02.
- **A04** Настроить базовый CI для Rust, Python и форматирования — implementation, P0; зависимости: A02.
- **A05** Ввести GitHub Projects, Issues, labels и защиту основной ветки — implementation, P0; зависимости: A01.
- **A06** Зафиксировать лицензионную политику, атрибуцию и границы ассетов — research, P0; зависимости: нет.
- **A08** Сохранить регрессионный smoke-test 26.3 до изменений — integration, P0; зависимости: A03.
- **A09** Определить правила PR, ownership областей и ревью — contract, P0; зависимости: A01.
- **S01** Зафиксировать ванильный эталон и версии 1.7.10 (client/server/Forge) — research, P0; зависимости: нет.
- **S02** Спроектировать LegacyBlockId/metadata и динамические modded registries — contract, P0; зависимости: S01.
- **S03** Специфицировать чанки 1.7.10 и структуру секций — contract, P0; зависимости: S01.
- **S04** Специфицировать протокол 1.7.10 (protocol 5) — contract, P0; зависимости: S01.
- **S05** Специфицировать загрузку ассетов, модели и pack_format=1 — contract, P0; зависимости: S01.
- **S08** Специфицировать ItemStack, инвентари и legacy NBT — contract, P0; зависимости: S01, S02.
- **S10** Спроектировать совместимый Mod API и политику Java/Forge модов — contract, P0; зависимости: S02, S08.

Исследование `S01`–`S05`, `S08`, `S10` допускается независимо от готовности игрового билда, но требуется соблюдать зависимости между спецификациями (например, `S02` начинается после `S01`). Первые 4 роли для команды из 4 человек: (1) DevOps/baseline, (2) world/data, (3) assets/render, (4) protocol/reference. Для команды из двух — один берёт DevOps+world/contracts, другой assets+protocol; ревью cross-contract изменений обязательно. Это не назначение людей по именам.

## 6. Контракты, которые надо принять до массовых PR

1. `LegacyBlockId` и `LegacyMeta`: диапазоны ванильных/modded ID, правила unknown/missing mappings и registry namespaces. **Не** считать ID+meta универсальной внутренней моделью современного Horizon.
2. `LegacyItemStack`: id, damage, count, NBT; стабильность форматов и операции stack split/merge.
3. `LegacyChunk`: 16x16x256, секции, metadata, lighting, biome IDs, versioned codecs.
4. `TileEntity`: тип, сериализация, server tick, синхронизация, world unload.
5. `Protocol5`: handshake/login/play, пакетные ID, framing, offline/online mode, packet fixtures.
6. `ModBridge`: регистрация на старте, lifecycle, события, сохранение, UI и packets без правок центрального `game.rs` под каждую машину.

Не заменять общий `horizon-protocol` жестко на протокол 5 без тестов: сначала версия и обособленный codec/adapter. Аналогично не уничтожать modern format в storage и asset subsystem, пока старый путь не проходит тесты.

## 7. Как использовать GitHub Projects

Представления проекта:
- **Board by Status:** текущая работа и блокировки.
- **Table by Milestone:** все Issue сгруппированы по milestone.
- **Table by Area + Owner:** зоны ответственности и перегрузка разработчиков.
- **Roadmap / Dependency:** реализация критического пути.

Правила управления потоком: не более одной активной `kind:implementation` задачи на исполнителя, допускается одна параллельная research issue; в `Ready` находятся только задачи без незакрытых dependencies. Родительский EPIC не закрывать, пока не приняты все его дочерние задачи.

## 8. Примеры веток и PR

- Ветка: `feat/W01-legacy-block-id`, `research/S04-protocol5`.
- Заголовок PR: `[W01] Implement legacy block ID mapping`.
- Тело PR: `Closes #<номер>`, список тестов, неизвестное/риски, изменённые публичные интерфейсы.
- Для изменений API (W01/S02/S08/S10) два reviewers: ответственный за подсистему + один потребитель интерфейса.

## 9. Ввод задач в GitHub

Файл `scripts/seed_github_issues.py` по умолчанию только показывает план. С `--apply` создаёт milestones/labels, родительские EPIC и Issue, затем задаёт отношения blocked-by. Повторные запуски ищут заголовки по стабильным ID; не закрывают, не удаляют и не перезаписывают существующие Issue. Можно начать с `--milestones M0 M1` и только позже импортировать остальные. Скрипт требует установленный `gh`, авторизацию и права на запись в `zenoaugmentis/horizon-NTM`.

```
python scripts/seed_github_issues.py                     # только локальная проверка
python scripts/seed_github_issues.py --milestones M0 M1  # проверить первый пакет
python scripts/seed_github_issues.py --apply --milestones M0 M1
python scripts/seed_github_issues.py --apply --all       # полный backlog, сознательное решение
```

**Не выполнять `--apply` до проверки репозитория:** если там уже открыты существующие Issues с другим заголовком, смысловые дубликаты невозможно автоматически определить только по ID.
