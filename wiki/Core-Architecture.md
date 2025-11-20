# Core Architecture

## Core Hub
Центральное ядро системы:
- маршрутизация запросов,
- управление режимами,
- поддержка контекстов,
- применение Model Set Context,
- управление Snapshot Layer.
Всегда активен.

## NAVI
Фронтовой агент входа.
Определяет контекст запроса и направляет его в нужный режим или агент.

## Snapshot Layer
Слой снапшотов, хранящий восстановимые состояния ядра и агентов.
Текущий зафиксированный снапшот:
**CORE_SNAPSHOT_2025-11-05 (“Jarvis-ready”)**.

## Mode Layer
Поддерживаемые режимы:
- CORE_BACKUP_LAB
- LAB v3
- PVC v1.1
- CLS mode
- Tech-Narrative mode
- Navigator mode
- MAU Weekly Cycle mode
- Indie Operator mode