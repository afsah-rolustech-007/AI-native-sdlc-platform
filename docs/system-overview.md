# Runtime architecture

A **Task** runs through eight phases in **LangGraph**. Shared services sit beside the graph, not inside it.

**Red = LLM.** **Blue = wait for a human.** **Orange = run workers in parallel, series, or mixed.** Everything else is code.

```mermaid
flowchart TB
  REQ[User request] --> G

  subgraph G["LangGraph  ·  save progress in Postgres"]
    direction TB

    subgraph IN["1  Intake  ·  built"]
      PM["LLM  Planning Manager<br/>What kind of work? How risky?"]
    end

    subgraph RQ["2  Requirements  ·  next to wire into the graph"]
      EX["LLM  Read the request once"]
      ENG["Code + repo search<br/>Fill in what we already know"]
      Q{Need to ask the user?}
      HITL1["HUMAN  Ask one question"]
      IT["LLM  Did their answer change scope?"]
      SPEC[Write requirements spec]
      VR["LLM  Check the spec"]
      CS[Score confidence  ·  math]
      AGS["HUMAN  Approve scope"]
    end

    subgraph DS["3  Design  ·  Phase 06"]
      DM["LLM  Design the change"]
      SAX["LLM  Security review if needed"]
      VD["LLM  Check the design"]
      AGD["HUMAN  Approve design"]
    end

    subgraph IMP["4  Implementation  ·  Phase 06"]
      IMM["LLM  Split into subtasks"]
      TS["Code  Topology Selector<br/>Look at the dependency graph"]
      TOP{How should workers run?}
      PAR[In parallel]
      SEQ[One after another]
      HYB[Mix of both]
      WS[Start coding workers]
      CG["LLM  Write code"]
      FI[Merge results  ·  code]
      IV["LLM  Check the combined diff"]
    end

    subgraph TAIL["5–8  Later"]
      QA[QA]
      REV[Review]
      REL["HUMAN  Approve release"]
      MON[Monitor  ·  new incident = new Task]
    end
  end

  subgraph SVC["Always available"]
    RI[Repo Intelligence  ·  search the codebase]
    MR[Model Router  ·  pick which LLM]
    MASC[MASC  ·  reject bad agent output]
    HL[(Human-question log)]
    TBX[(Task + checkpoints)]
  end

  IN --> RQ --> DS --> IMP --> TAIL
  EX --> ENG --> Q
  Q -->|no| SPEC
  Q -->|yes| HITL1 --> IT --> ENG
  SPEC --> VR --> CS --> AGS
  IMM --> TS --> TOP
  TOP --> PAR --> WS
  TOP --> SEQ --> WS
  TOP --> HYB --> WS
  WS --> CG --> FI
  FI -->|more work| WS
  FI -->|done| IV
  G -.-> RI
  G -.-> MR
  G -.-> MASC
  HITL1 -.-> HL
  AGS -.-> HL
  AGD -.-> HL
  REL -.-> HL
  G -.-> TBX

  classDef llm fill:#c92a2a,stroke:#862e2e,color:#fff,stroke-width:2px
  classDef hitl fill:#1c7ed6,stroke:#1864ab,color:#fff,stroke-width:2px
  classDef topo fill:#e8590c,stroke:#d9480f,color:#fff,stroke-width:2px
  class PM,EX,IT,VR,DM,SAX,IMM,CG,IV,VD llm
  class HITL1,AGS,AGD,REL hitl
  class TS,TOP,PAR,SEQ,HYB topo
```

**Ask the user for requirements** = blue box in phase 2, not intake.  
**Parallel vs series** = orange boxes in phase 4, not requirements.

| Now | After Phase 05 | After Phase 06 |
|-----|----------------|----------------|
| 1 LLM (intake only) | 3 LLMs if the request is already clear | + coding LLMs; topology is still code, not an LLM |
