graph TD
    A[BDI Agent Start] --> B[__init__]
    B --> C[_initialize_string_desires]
    
    D[bdi_cycle] --> E{Active desires exist<br/>and no intentions?}
    E -->|Yes| F[generate_intentions_from_desires]
    E -->|No| G{Intentions exist?}
    
    F --> F1[Stage 1: Generate high-level intentions]
    F1 --> F2[Stage 2: Generate detailed steps]
    F2 --> F3[Update agent with intentions]
    F3 --> G
    
    G -->|Yes| H[execute_intentions]
    G -->|No| I[Skip execution]
    
    H --> H1{Intention complete?}
    H1 -->|Yes| H2[Mark desire achieved<br/>Remove intention]
    H1 -->|No| H3[Execute current step]
    
    H3 --> H4{Tool call or<br/>descriptive step?}
    H4 -->|Tool call| H5[Execute via self.run with tool prompt]
    H4 -->|Descriptive| H6[Execute via self.run with description]
    
    H5 --> H7[_analyze_step_outcome_and_update_beliefs]
    H6 --> H7
    
    H7 --> H8{Step successful?}
    H8 -->|Yes| H9[Increment step counter]
    H8 -->|No| H10{HITL enabled?}
    
    H9 --> H11{Final step?}
    H11 -->|Yes| H12[Mark desire achieved<br/>Remove intention]
    H11 -->|No| H13[Continue to next step]
    
    H10 -->|Yes| H14[_human_in_the_loop_intervention]
    H10 -->|No| H15[Step failed, no intervention]
    
    H14 --> H16[_build_failure_context]
    H16 --> H17[_present_context_to_user]
    H17 --> H18[Get user input]
    H18 --> H19{User wants to quit?}
    H19 -->|Yes| H20[Exit HITL]
    H19 -->|No| H21[_interpret_user_nl_guidance]
    
    H21 --> H22[_summarize_directive_for_user]
    H22 --> H23[Get user confirmation]
    H23 --> H24{User confirms?}
    H24 -->|No| H18
    H24 -->|Edit| H18
    H24 -->|Yes| H25[_apply_user_guided_action]
    
    H25 --> H26{Action type?}
    H26 -->|RETRY_CURRENT_AS_IS| H27[No changes needed]
    H26 -->|MODIFY_CURRENT_AND_RETRY| H28[Modify current step]
    H26 -->|REPLACE_CURRENT_STEP_WITH_NEW| H29[Replace step with new ones]
    H26 -->|INSERT_NEW_STEPS_BEFORE_CURRENT| H30[Insert steps before current]
    H26 -->|INSERT_NEW_STEPS_AFTER_CURRENT| H31[Insert steps after current]
    H26 -->|REPLACE_REMAINDER_OF_PLAN| H32[Replace remaining plan]
    H26 -->|SKIP_CURRENT_STEP| H33[Skip to next step]
    H26 -->|ABORT_INTENTION| H34[_handle_user_abort_request]
    H26 -->|UPDATE_BELIEFS_AND_RETRY| H35[Update beliefs]
    H26 -->|COMMENT_NO_ACTION| H36[No action taken]
    
    H34 --> H37[Remove intention<br/>Set desire to PENDING]
    
    H2 --> J
    H12 --> J
    H13 --> J
    H15 --> J
    H20 --> J
    H27 --> J
    H28 --> J
    H29 --> J
    H30 --> J
    H31 --> J
    H32 --> J
    H33 --> J
    H37 --> J
    H35 --> J
    H36 --> J
    I --> J
    
    J{Intentions still exist?}
    J -->|Yes| K[_reconsider_current_intention]
    J -->|No| L[End BDI cycle]
    
    K --> K1[Format beliefs and remaining steps]
    K1 --> K2[Ask LLM to assess plan validity]
    K2 --> K3{Plan still valid?}
    K3 -->|Yes| L
    K3 -->|No| K4[Remove invalid intention<br/>Set desire to PENDING]
    K4 --> L
    
    L --> M[log_states]
    M --> N[BDI Cycle Complete]
    
    style A fill:#e1f5fe
    style D fill:#f3e5f5
    style F fill:#e8f5e8
    style H fill:#fff3e0
    style H14 fill:#ffebee
    style K fill:#f1f8e9