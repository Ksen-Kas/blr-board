# OPS-LAB Sync Agent — сбор + сортировка + push

Единый агент. Заменяет старые collector + sorter.

**Cowork SKILL.md:** `/Users/sizovaka/Documents/Claude/Scheduled/blr-board-collector/SKILL.md`

## Что делает (один проход)

1. Читает data.json
2. Разбирает inbox (если есть) → fire / tasks / backlog
3. Собирает новые сообщения из TG чатов (min_id)
4. Оценивает срочность из контекста → кладёт СРАЗУ в нужную секцию
5. Пишет в log
6. git push

## Расписание

4 раза в день: 9:00, 13:00, 17:00, 21:00 (через Cowork Scheduled Tasks)

## Источники

| Чат | TG ID | Что искать |
|-----|-------|-----------|
| BLR канал | -1003478224837 | анонсы, контент |
| BLR чат | -1003590719886 | вопросы, wins, churn |
| Юля (личка) | @jmatsako | задачи, дедлайны |
| публичный канал | @brainloveandrobots | публикации |
| ksenia :: inbox | личный канал | всё = задача |
