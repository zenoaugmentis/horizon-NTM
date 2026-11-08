# horizon-NTM — правила для Claude Code

Перенос Minecraft 1.7.10 на Rust на базе движка Horizon (https://github.com/horizon-rust/horizon),
затем нативные порты HBM's NTM, MCHeli и OpenComputers. План и правила команды —
`docs/TEAM_ROADMAP.md`, задачи — `planning/backlog.json` и GitHub Issues.

## Доска задач

Доска: GitHub Project «Horizon-NTM Development» (владелец `zenoaugmentis`, номер `1`).
Статус меняется только через `scripts/board.py` (нужен `gh auth refresh -s project`):

```bash
python scripts/board.py list                     # все задачи и статусы
python scripts/board.py status 5 "In Progress"    # 5 = номер issue
python scripts/board.py status 5 Done
python scripts/board.py options                  # какие статусы есть сейчас
```

Сейчас у поля Status три значения: `Todo`, `In Progress`, `Done`. Если в проекте добавят
`In Review` и `Blocked`, используй их; пока их нет — правила ниже говорят, что делать вместо.

### Жизненный цикл задачи

1. **Перед началом** проверь, что все `depends_on` задачи (`planning/backlog.json`) закрыты.
   Если нет — не начинай, выбери другую задачу.
2. **Взял задачу:** `board.py status <N> "In Progress"` и `gh issue edit <N> --add-assignee @me`.
   Одновременно не больше одной `kind:implementation` задачи в работе.
3. **Ветка:** `feat/<ID>-<кратко>` для кода, `research/<ID>-<кратко>` для исследований/спецификаций
   (`<ID>` — стабильный ID вроде `A01`, `S04`).
4. **PR:** заголовок `[<ID>] ...`, тело по `.github/PULL_REQUEST_TEMPLATE.md`, строка `Closes #<N>`.
   Если есть `In Review` — переведи туда; иначе оставь `In Progress`.
5. **Заблокировано:** комментарий в issue с причиной; статус `Blocked`, если он есть,
   иначе метка `blocked` (`gh issue edit <N> --add-label blocked`).
6. **Done** ставится только после merge PR (issue закрывается через `Closes #N`).
   EPIC не закрывать, пока открыта хоть одна дочерняя задача.

Не меняй статус задач, которые ты не трогал.

## Жёсткие запреты

- Не коммитить файлы Mojang: `.jar`, ассеты, декомпилированный код, `.local/`, миры, токены.
  Эталонные данные 1.7.10 получаются у пользователя локально (см. `docs/specs/versions.md`).
- Не переносить код из MCHeli: он закрыт («All rights reserved»). Только clean-room по поведению.
- Не менять `PROTOCOL_VERSION`, `VERSION_ID` и `horizon-prepare` до появления тестов 1.7.10.
- Upstream Horizon импортируется снимком закреплённого коммита без истории (`docs/UPSTREAM.md`).

## Окружение

Основная машина — Windows (PowerShell). В примерах для терминала не используй `<...>` как
заполнитель: PowerShell считает `<` оператором. Пиши реальные значения.
