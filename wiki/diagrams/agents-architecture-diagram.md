# Agents Architecture Diagram

```mermaid
graph LR
  subgraph CoreAgents
    CoreHub[Core Hub]
    NAVI[NAVI]
    SnapshotLayer[Snapshot Layer]
  end

  subgraph BaseAgents[Base Agents]
    CLS_Core[CLS_Core v2.0]
    Indie_Core[Indie_Operator_Core]
    VIC[VIC (Navigator v2.1)]
    Platon[Platon (Tech-Narrative)]
    MiaVoice[Mia Voice Core]
  end

  subgraph InstanceAgents[Instance Agents]
    CLS_Andrey[CLS_Andrey]
    Indie_MAU[Indie_Operator_MAU]
    Mia_Voice_Operator[Mia_Voice_Operator (Айра)]
    Alina[Алина (Strategist)]
  end

  subgraph ContextAgents[Context-bound Agents]
    MauAgent[MAU Agent]
    MiaAgent[Mia Agent]
    WeeklyOp[Weekly Cycle Operator]
    PinFunnel[Pinterest Funnel Agent]
  end

  CoreHub --> NAVI
  CoreHub --> SnapshotLayer
  CoreHub --> CLS_Core
  CoreHub --> Indie_Core
  CoreHub --> VIC
  CoreHub --> Platon
  CoreHub --> MiaVoice

  CLS_Core --> CLS_Andrey
  Indie_Core --> Indie_MAU
  MiaVoice --> Mia_Voice_Operator

  Indie_MAU --> MauAgent
  Mia_Voice_Operator --> MiaAgent
  Indie_MAU --> WeeklyOp
  WeeklyOp --> PinFunnel
```
