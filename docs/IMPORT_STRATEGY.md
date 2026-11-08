# A01 — состав horizon-NTM и стратегия импорта upstream

**Issue:** #5 (`A01`) · **Дата проверки:** 2026-11-08 · **Решение:** снимок закреплённого коммита без истории

## 1. Состав целевого репозитория до импорта

`zenoaugmentis/horizon-NTM`, ветка `main`, коммит `2f80e7b6aebef90806c9a705e24a2876c2ad5923`
(получено `git clone --depth 1` и `find . -path ./.git -prune -o -print`):

```text
.
├── .github/
│   ├── ISSUE_TEMPLATE/port_task.md
│   └── PULL_REQUEST_TEMPLATE.md
├── .gitignore            # шаблон GitHub для Rust (target, *.pdb, debug, …)
├── LICENSE               # GNU GPL v3
├── README.md             # 1 абзац: цель проекта
├── docs/TEAM_ROADMAP.md
├── planning/{README.md, backlog.csv, backlog.json}
└── scripts/seed_github_issues.py
```

Кода движка нет: `Cargo.toml`, `crates/` и прочее отсутствуют. Это подтверждает вывод аудита
(`Cargo.toml` → 404). Issues #1–#2 закрыты (license, roadmap), #3–#24 открыты (EPIC M0/M1, A01–A09, S01–S11).

## 2. Upstream

| Параметр | Значение |
|---|---|
| Репозиторий | https://github.com/horizon-rust/horizon |
| Ветка / коммит на 2026-11-08 | `main` @ `9fc6abb08b40bf411841f7bb375ad5dfbf163927` (2026-11-08T13:01:32+01:00, merge PR #12468) |
| Лицензия | MIT, «Copyright (c) 2026 Ludovic Marie and the Horizon contributors» |
| Размер | 5 941 отслеживаемых файлов, ~142 МБ рабочего дерева |
| Workspace | 40 членов (включая `xtask` и `horizon-mod-api-gen/dispatch-tests`); вне workspace: `launcher/`, `horizon-telemetry-server`, `horizon-mod-registry`, `third_party/*` |
| Rust | `edition = "2024"`, `rust-version = "1.95"`; файла `rust-toolchain.toml` нет |

Точное закрепление коммита и команды — задача A02 (`docs/UPSTREAM.md`).

## 3. Варианты импорта

| Вариант | Плюсы | Минусы |
|---|---|---|
| **GitHub fork** | Кнопка «sync fork», общая история | horizon-NTM уже создан отдельным репозиторием и не может стать форком без пересоздания; форк наследует видимость и сеть upstream |
| **Merge истории** (`git merge --allow-unrelated-histories`) или **subtree с историей** | `git blame` по upstream-авторам, cherry-pick без конфликтов путей | Публикует **всю** историю upstream, включая код, удалённый из-за лицензии (см. ниже); десятки тысяч коммитов в репозитории под GPLv3 |
| **Снимок (copy) закреплённого коммита** | Чистая история; ровно тот код, лицензия которого проверена; размер = одно дерево | Нет upstream-`blame` внутри репозитория; синхронизация вручную |

### Почему не переносить историю

`THIRD_PARTY_NOTICES.md` upstream прямо говорит, что в **старых коммитах** Horizon лежит код,
не покрытый MIT, который потом удалили:

- шейдер-паки, написанные по исходникам Iris (LGPL-3.0), коммиты с `b22583d057`, удалены в PR #1561;
- математика `fdlibm`/`aarch64` и `round_f32`, переведённые из OpenJDK/HotSpot (GPL-2.0, частично
  с Classpath Exception), с `558d140fca` и `95db0fce9d`, заменены в PR #11944;
- `java_hash_map.rs` из OpenJDK `HashMap.java` (GPL-2.0 + Classpath Exception), с `118e93ea51`/`194db0dbb4`, заменён в PR #12043.

GPL-2.0-only несовместима с GPLv3, под которой выпускается horizon-NTM. Импорт истории
повторно опубликовал бы эти файлы в нашем репозитории. Снимок закреплённого коммита
(после всех трёх удалений) этой проблемы не имеет.

## 4. Решение

**Снимок закреплённого коммита upstream в корень репозитория, одним коммитом, без истории.**
Upstream подключается как remote `upstream` только локально — для чтения и точечных cherry-pick.

Правила:

1. Импорт выполняет скрипт из A02 (`scripts/import_upstream.py`), а не ручное копирование.
   Сообщение коммита содержит полный SHA upstream.
2. Обновление upstream — отдельный PR «sync upstream `<old>`→`<new>`»: скрипт строит
   `git diff <old> <new>` в upstream и применяет его как патч. Перед этим проверяется
   `THIRD_PARTY_NOTICES.md` нового коммита на новые разделы «Code removed for its license».
3. Код, перенесённый из NTM (LGPL-3.0), допустим в horizon-NTM, но **не может** уйти обратно
   в upstream: правила Horizon запрещают GPL/LGPL-код даже для чтения
   (CONTRIBUTING.md upstream, раздел «Only original code, or code whose license allows it»).
   Такие изменения помечаются в PR, чтобы их не предлагали в upstream.

### Конфликты с существующими файлами

| Путь | Что делать при импорте |
|---|---|
| `LICENSE` | Остаётся наш GPLv3. MIT-лицензия upstream сохраняется дословно как `LICENSES/Horizon-MIT.txt` |
| `README.md` | Остаётся наш. Upstream-README сохраняется как `docs/upstream-README.md` |
| `.gitignore` | Берётся upstream (он закрывает `.local/`, `*.jar`, `/assets/`, декомпиляцию) + строки нашего Rust-шаблона, которых там нет: `*.pdb`, `rustc-ice-*.txt`, `**/*.rs.bk`, `**/mutants.out*/`. Наше незаякоренное `debug` заменяется upstream-овским `/debug/` |
| `.github/workflows/` | **Не импортируется.** 21 workflow upstream рассчитаны на их раннеры, секреты, раннер с копией Minecraft (`parity`) и релизы. Свой CI — задача A04 |
| `.github/CODEOWNERS`, `trusted-reviewers.txt`, `release-line.txt`, `pull_request_template.md` | **Не импортируются** (люди и процессы upstream). Наш шаблон PR остаётся |
| `AGENTS.md`, `CLAUDE.md` (symlink), `.claude/` | `AGENTS.md` импортируется на своё место (карта кода upstream); symlink `CLAUDE.md` → `AGENTS.md` заменяется нашим `CLAUDE.md`. `.claude/` не импортируется |
| `docs/` | Импортируется на своё место: тесты upstream проверяют ссылки `docs/README.md` и сгенерированные `docs/*-commands.md`. Имена наших документов (`TEAM_ROADMAP`, `IMPORT_STRATEGY`, `UPSTREAM`, `LEGAL`, `specs/`) с upstream не пересекаются |

Остальное дерево (`crates/`, `tools/`, `tests/`, `third_party/`, `launcher/`, `mods/`, `xtask/`,
`Cargo.toml`, `Cargo.lock`, `THIRD_PARTY_NOTICES.md` и т. д.) импортируется без изменений.

## 5. Авторские уведомления, которые обязаны сохраниться

MIT и лицензии третьих сторон требуют сохранять тексты при любом копировании. После импорта
в репозитории должны лежать **без изменений**:

- `LICENSES/Horizon-MIT.txt` — MIT Horizon (Ludovic Marie and the Horizon contributors);
- `THIRD_PARTY_NOTICES.md` upstream целиком: Catnip/Ponder, wgpu-hal, naga, libmimalloc-sys/mimalloc,
  Pixelify Sans, Pixelarticons, Hugeicons, AMD FidelityFX SDK, логотипы загрузчиков, Sign in with Microsoft,
  CIT Resewn, FusionExamples, BlueMap, JOML, Just Enough Items, Flywheel, fdlibm, Starling;
- 14 файлов лицензий в дереве:
  - `crates/horizon-client-render/src/jei_recipes/LICENSE.txt`
  - `crates/horizon-theme/fonts/OFL-{BricolageGrotesque,Geist,PixelifySans}.txt`
  - `crates/horizon-theme/icons/glass/LICENSE-hugeicons.txt`, `icons/pixel/LICENSE-pixelarticons.txt`
  - `third_party/libmimalloc-sys/LICENSE.txt`, `third_party/libmimalloc-sys/c_src/mimalloc/v3/LICENSE`
  - `third_party/{naga,wgpu-hal}/LICENSE.{MIT,APACHE}`
  - `tools/lra-catalog/LICENSE`
- заголовки с лицензиями внутри файлов (например, `fluid_render.rs` — MIT Ponder, `fdlibm.rs` — уведомление Sun).

Скрипт A02 проверяет наличие всех перечисленных файлов после импорта.

## 6. Что ещё учесть сразу после импорта (вне A01)

- **`horizon-extras`.** Feature по умолчанию включает косметику, официальные и партнёрские сервера
  Horizon в списке, Play with Friends, Discord и анонимный heartbeat на инфраструктуру Horizon
  (`docs/forking.md` upstream). Для horizon-NTM их стоит собирать без этой feature:
  `cargo build -p horizon-client --no-default-features --features audio,controllers`.
  Upstream честно называет этот режим «best effort». Решение — в A03/A04.
- **`tools/check_public_tree.py`** из upstream уже отклоняет `.jar`, `.class`, `.local/`, `assets/` в корне,
  декомпилированные `.java`. Его стоит подключить в наш CI (A04).
- **Торговые знаки.** Логотипы загрузчиков и символ Microsoft в `launcher/` — чужие знаки; при
  ребрендинге лаунчера их использование пересматривается (A06).

## 7. Проверка

Всё ниже воспроизводится без Minecraft:

```bash
git clone --depth 1 https://github.com/zenoaugmentis/horizon-NTM && cd horizon-NTM
find . -path ./.git -prune -o -print | sort          # дерево из раздела 1

git clone --depth 1 https://github.com/horizon-rust/horizon ../horizon
git -C ../horizon rev-parse HEAD                     # на момент проверки: 9fc6abb0…
git -C ../horizon ls-files | wc -l                    # 5941
git -C ../horizon ls-files | grep -iE '(^|/)(licen[cs]e|copying|notice|ofl)[^/]*$'   # список из раздела 5
```

Сборка и тесты кода в рамках A01 не запускались: импорта ещё нет. Сборка — задача A03.
