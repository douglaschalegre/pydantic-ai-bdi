graph TD
    A[BDI Agent Start] --> B[Initialize with Desires]
    
    B --> C[BDI Cycle]
    
    C --> D{Have Intentions?}
    D -->|No| E[Generate Intentions<br/>from Desires]
    D -->|Yes| F[Execute Current Step]
    
    E --> F
    
    F --> G{Step Successful?}
    G -->|Yes| H{More Steps?}
    G -->|No| I{Human Intervention<br/>Enabled?}
    
    H -->|Yes| J[Next Step]
    H -->|No| K[Mark Desire Achieved]
    
    I -->|Yes| L[Human Guidance]
    I -->|No| M[Step Failed]
    
    L --> N[Apply Guidance]
    N --> F
    
    J --> F
    K --> O[Plan Reconsideration]
    M --> O
    
    O --> P{Plan Still Valid?}
    P -->|Yes| Q[Continue]
    P -->|No| R[Remove Invalid Plan]
    
    Q --> S{More Cycles Needed?}
    R --> T[Mark Desire Pending]
    T --> S
    
    S -->|Yes| C
    S -->|No| U[End]
    
    style A fill:#e1f5fe
    style C fill:#f3e5f5
    style E fill:#e8f5e8
    style F fill:#fff3e0
    style L fill:#ffebee
    style O fill:#f1f8e9
