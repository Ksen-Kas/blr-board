# TKACH_v1.0 — Core Specification

## Console Block (for direct use)
```
!tkach.init
!tkach.load <PROFILE_NAME>
!tkach.refresh
!tkach.export
```

## Purpose
TKACH (Voice Weaver) — инструмент для:
- сборки голоса по рассеянным данным,
- консолидации живого профиля,
- обновления профиля при появлении нового материала.

## Core Logic
1. **Input ingestion** — принимает текст, заметки, посты, биографию, переписки.
2. **Clustering** — группирует по смысловым полям.
3. **Voice-pattern extraction** — вычленяет тон, ритм, лексические особенности.
4. **Context synthesis** — собирает единый живой профиль.
5. **Export** — выдаёт обновлённую версию для Github/архива.
6. **Refresh-loop ready** — умеет принимать новые данные и обновлять профиль.

## Output Types
- `<name>_profile_vX.md` — текстовый живой контекст.
- `<name>_voice_map.json` — карта паттернов речи.
- `<name>_summary.txt` — краткое описание для агентов.

## Usage Protocol
1. Создать ветку обучения.
2. Запустить:
```
!tkach.init
!tkach.load <PROFILE_NAME>
```
3. Кидать материалы с пометкой “обучение”.
4. Периодически:
```
!tkach.refresh
!tkach.export
```
5. Загружать итоговый файл в Github.
```

