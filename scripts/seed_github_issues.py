#!/usr/bin/env python3
"""Seed a proposed GitHub issue roadmap from planning/backlog.json.

Default mode is OFFLINE / DRY RUN. Remote mutations require --apply and an
explicit milestone selection or --all. Requires GitHub CLI (gh) in apply mode.
Stable [A01]/[EPIC M0] prefixes allow safe repeat runs; no existing issues
are modified except adding missing issue-dependency relationships.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'planning' / 'backlog.json'
ID_RE = re.compile(r'^\[([A-Z]\d{2})\]')
EPIC_RE = re.compile(r'^\[EPIC (M\d+)\]')
COLOR = {
    'area':'6F42C1', 'kind':'1D76DB', 'priority':'D93F0B', 'size':'D4C5F9'
}


def gh(*args, want_json=False):
    cmd = ['gh', *map(str,args)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if proc.returncode:
        raise RuntimeError(f"{' '.join(cmd)}\n{proc.stderr.strip()}\n{proc.stdout.strip()}")
    if want_json:
        return json.loads(proc.stdout or 'null')
    return proc.stdout.strip()


def issue_body(t, repo):
    deps=', '.join(f'`{d}`' for d in t['depends_on']) or 'Нет'
    paths='\n'.join(f'- `{p}`' for p in t['paths']) or '- Согласовать с исполнителем'
    note=(f'\n## Дополнительно\n{t["notes"]}\n' if t.get('notes') else '')
    return f'''<!-- horizon-ntm-plan:{t['id']} -->
## Цель
{t['title']}

## Категория
- Milestone: `{t['milestone']}`
- Подсистема: `{t['area']}`
- Тип: `{t['kind']}`
- Приоритет: `{t['priority']}`; размер: `{t['size']}`

## Предполагаемые точки входа
{paths}

> Путь должен быть проверен после фиксации upstream SHA. Не считать его единственно возможной точкой изменения.

## Зависимости (стабильные ID)
{deps}

## Условия приёмки (Definition of Done)
- [ ] {t['acceptance']}
- [ ] Приложены команды/результаты тестирования, либо обоснована невозможность их запуска.
- [ ] PR проходит CI и code review; документация обновлена при изменении интерфейса.
- [ ] Не добавлены Mojang assets, JAR, токены, приватные данные, декомпилированные исходники.
{note}
## Связи
Полный план: [`planning/backlog.json`](https://github.com/{repo}/blob/main/planning/backlog.json).
'''


def epic_body(k, m, ts):
    body=f'''<!-- horizon-ntm-epic:{k} -->
# {k}: {m['title']}

{m['description']}

Задачи (все стабильные ID, номера Issue появятся после импорта):
'''
    for t in ts:
        body+=f"- `{t['id']}` — {t['title']}\n"
    return body+'\nЗакрыть EPIC только после завершения всех дочерних задач.\n'


def with_body(body, callback):
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.md', delete=False) as f:
        f.write(body)
        tmp=f.name
    try:
        return callback(tmp)
    finally:
        Path(tmp).unlink(missing_ok=True)


def import_plan(data, wanted, repo):
    if not shutil.which('gh'):
        raise RuntimeError('GitHub CLI gh не найден: https://cli.github.com/')
    gh('auth','status')
    gh('repo','view',repo,'--json','nameWithOwner',want_json=True)
    # Read repository state, then only fill missing entries.
    old_issues=gh('issue','list','-R',repo,'--state','all','--limit','2000','--json','number,title',want_json=True)
    found={}; epics={}
    for i in old_issues:
        t=i['title']; mt=ID_RE.match(t); me=EPIC_RE.match(t)
        if mt:
            key=mt.group(1)
            if key in found: raise RuntimeError(f'Дублирующийся номер задачи {key}: {found[key]} и {i["number"]}')
            found[key]=i['number']
        if me:
            key=me.group(1)
            if key in epics: raise RuntimeError(f'Дублирующийся EPIC {key}')
            epics[key]=i['number']
    ms_existing=gh('api',f'repos/{repo}/milestones?state=all&per_page=100',want_json=True)
    ms_names={x['title'] for x in ms_existing}
    labels=gh('label','list','-R',repo,'--limit','1000','--json','name',want_json=True)
    label_names={x['name'] for x in labels}
    selected=[x for x in data['tasks'] if x['milestone'] in wanted]
    needed_labels={'kind:epic'}
    for t in selected:
        for key in ('area','kind','priority','size'):
            needed_labels.add(f'{key}:{t[key]}')
    for x in sorted(needed_labels-label_names):
        group=x.split(':',1)[0]
        print('LABEL +',x)
        gh('label','create',x,'-R',repo,'--color',COLOR.get(group,'CFD3D7'),'--description','Horizon-NTM roadmap category')
    for k in wanted:
        m=data['milestones'][k]
        if m['title'] not in ms_names:
            print('MILESTONE +',k,m['title'])
            gh('api',f'repos/{repo}/milestones','-f',f'title={m["title"]}','-f',f'description={m["description"]}')
    for k in wanted:
        if k in epics: continue
        ts=[t for t in selected if t['milestone']==k]
        m=data['milestones'][k]
        print('EPIC +',k)
        output=with_body(epic_body(k,m,ts),lambda tmp: gh('issue','create','-R',repo,'--title',f'[EPIC {k}] {m["title"]}', '--body-file',tmp, '--label','kind:epic','--milestone',m['title']))
        number=int(output.rstrip('/').split('/')[-1]);epics[k]=number
    # Always preserve JSON task order; task relations can be created after all tasks are present.
    for t in selected:
        id=t['id'];
        if id in found:
            print('SKIP existing', id, '#'+str(found[id]));continue
        args=['issue','create','-R',repo,'--title',f'[{id}] {t["title"]}', '--label',f'area:{t["area"]}', '--label',f'kind:{t["kind"]}', '--label',f'priority:{t["priority"]}', '--label',f'size:{t["size"]}', '--milestone',data['milestones'][t['milestone']]['title'], '--parent',str(epics[t['milestone']])]
        print('ISSUE +',id)
        output=with_body(issue_body(t,repo),lambda tmp: gh(*args,'--body-file',tmp))
        found[id]=int(output.rstrip('/').split('/')[-1])
    print('Dependencies: existing cross-milestone prerequisites are linked; future tasks remain references in body.')
    for t in selected:
        available=[found[d] for d in t['depends_on'] if d in found]
        missing=[d for d in t['depends_on'] if d not in found]
        if missing: print('PENDING',t['id'],'waits for tasks not yet created:',','.join(missing))
        if not available:continue
        # GitHub CLI supports blockedBy in JSON in recent releases. Use it to avoid duplicate relationships.
        existing=[]
        try:
            raw=gh('issue','view',str(found[t['id']]),'-R',repo,'--json','blockedBy',want_json=True)
            relation=raw.get('blockedBy') or {}
            nodes=relation.get('nodes',[]) if isinstance(relation,dict) else relation
            existing=[int(x['number']) for x in nodes if isinstance(x,dict) and x.get('number') is not None]
        except Exception:
            print('WARN cannot read existing dependencies for',t['id'],'; not adding them automatically. Add manually in GitHub.')
            continue
        pending=[n for n in available if n not in existing]
        if pending:
            print('DEPENDENCY +',t['id'],'<-',pending)
            gh('issue','edit',str(found[t['id']]),'-R',repo,'--add-blocked-by',','.join(map(str,pending)))
    print('SUCCESS: issue import completed. Issues created/reused:',len(selected))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Create missing labels, milestones, epics, issues, dependencies remotely')
    parser.add_argument('--milestones',nargs='+',help='Example: --milestones M0 M1')
    parser.add_argument('--all',action='store_true',help='Explicitly select all milestones (especially with --apply)')
    parser.add_argument('--repo',default=None,help='Explicit OWNER/REPO; default from backlog.json')
    args=parser.parse_args()
    data=json.loads(DATA.read_text(encoding='utf-8'))
    repo=args.repo or data['repo']
    if args.milestones and args.all: parser.error('Use --milestones OR --all')
    if args.milestones:
        invalid=set(args.milestones)-set(data['milestones'])
        if invalid:parser.error(f'Unknown milestones: {sorted(invalid)}')
    if args.apply and not (args.milestones or args.all):
        parser.error('Safety guard: remote import requires --milestones M0 M1 or explicit --all')
    wanted=list(dict.fromkeys(args.milestones or list(data['milestones'])))
    selected=[x for x in data['tasks'] if x['milestone'] in wanted]
    counts={k:sum(x['milestone']==k for x in selected) for k in wanted}
    print('Repo:',repo,'| Mode:', 'APPLY (remote writes)' if args.apply else 'DRY RUN (offline)')
    print('Milestones:',', '.join(f'{k}:{v}' for k,v in counts.items()))
    print('Tasks:',len(selected),'| EPICs:',len(wanted))
    for t in selected:
        print(f" {t['id']:>3} [{t['priority']}/{t['kind']}] {t['title']}  <- {','.join(t['depends_on']) or '-'}")
    if not args.apply:
        print('\nNothing was changed. Use --apply --milestones M0 M1 after reviewing targets and logging into gh.')
        return
    import_plan(data,wanted,repo)

if __name__=='__main__':
    try: main()
    except (RuntimeError,subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);sys.exit(1)
