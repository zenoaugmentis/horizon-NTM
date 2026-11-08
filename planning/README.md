# Управление задачами Horizon-NTM

Все решения о задачах и зависимостях согласуются в `docs/TEAM_ROADMAP.md`.

- `backlog.json` — источник истины (стабильные ID, dependencies, acceptance, области).
- `backlog.csv` — выгрузка для анализа в табличном виде; обновлять **из JSON**, не редактировать обе версии независимо.
- `scripts/seed_github_issues.py` — опциональный импорт в GitHub Issues; по умолчанию ничего не изменяет.

## Запуск из корня репозитория

```bash
python scripts/seed_github_issues.py --milestones M0 M1
# после проверки задач и `gh auth login`:
python scripts/seed_github_issues.py --apply --milestones M0 M1
# сознательная массовая публикация:
python scripts/seed_github_issues.py --apply --all
```

Импорт создаёт до 10 EPIC Issues, 91 дочернее Issue, labels и milestones. Связи `blocked by` создаются, если требуемые Issues уже существуют. Скрипт **не удаляет и не перезаписывает** Issue, но может добавлять недостающие зависимости. Дубли в ID определяются по префиксу `[W01]` и т. п.; смысловые дубли с другим заголовком нужно проверить вручную.

Если `--apply` выдаёт ошибку, повторный запуск пытается пропустить успешно созданные Issues. Перед повтором всё равно проверьте список Issues на сервере.
