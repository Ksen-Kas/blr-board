# Context Layers Diagram

```mermaid
graph TD
  CoreHub[Core Hub] --> CtxMau[Mau Context]
  CoreHub --> CtxMia[Mia Context]
  CoreHub --> CtxAndrey[Andrey Context]
  CoreHub --> CtxSvetlana[Svetlana Context]

  CtxMau --> Indie_MAU[Indie_Operator_MAU]
  CtxMau --> MauAgent[MAU Agent]
  CtxMau --> Alina[Алина (Strategist)]

  CtxMia --> MiaVoice[Mia Voice Core]
  MiaVoice --> Mia_Voice_Operator[Mia_Voice_Operator (Айра)]

  CtxAndrey --> CLS_Core[CLS_Core v2.0]
  CLS_Core --> CLS_Andrey[CLS_Andrey]

  CtxSvetlana --> CLS_Core
```
