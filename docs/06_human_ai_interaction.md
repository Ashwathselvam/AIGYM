# 06 Human–AI Interaction

> Draft v0.1 · last updated {{DATE}}

## Purpose
Define how **human teachers** and reviewers interact with the agentic system: feedback formats, UI flows, and memory integration.

## 1. Interaction Modes
| Mode | When | Channel | Stored As |
|------|------|---------|-----------|
| Task Assignment | Beginning of episode | Web UI / CLI | `episodes.task_id` & initial message |
| Feedback & Scores | After critic | Web UI form | `feedback` rows (source=human) |
| Brainstorm Chat | During task | Chat pane | `episode_messages` (role=human) |
| Curriculum Review | Periodic | Dashboard | Pagination queries |

## 2. Constructive Feedback Template
```text
**Score (0-1):** 0.65
**Reasoning:**
• Your loop breaks early on input size 1.
• Consider using list slicing for clarity.
**Next Step Suggestion:**
Rewrite using while-loop and re-run tests.
```

System enforces the headings so the Critic and Reflective Thinker can parse.

## 3. Conversation Design Guidelines
1. Start with *praise*, then *critique*, then *actionable advice* (“SBI” model).  
2. Ask open-ended questions to encourage agent explanation.  
3. Limit messages to ≤300 words; long messages dilute signal.

## 4. UI Wireframe (ASCII)
```
+--------------------------------------------------+
| Task: Implement Binary Search (G1)               |
+------------------+-------------------------------+
| Agent Console    | Human Feedback               |
| > code output    | [Score 0-1] [_____]          |
| > ...            | [Reasoning]  [textarea]      |
|                  | [Submit]                     |
+------------------+-------------------------------+
```

## 5. Memory Integration
* On submit, FE calls `POST /episodes/{id}/feedback` with JSON payload.  
* Episode page shows timeline merging **agent**, **critic**, **human** events chronologically.

## 6. Privacy & Ethics
| Concern | Mitigation |
|---------|-----------|
| Sensitive data leakage | PII scrubber before storing messages |
| Teacher bias | Multiple reviewers + calibration rubrics |
| Over-reliance on human | Progression gate: <25% episodes require human intervention |

---
Next: `07_deployment_plan.md` outlines infra & scaling. 