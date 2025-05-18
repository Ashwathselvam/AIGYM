# 03 Concept Extraction Prompts

> Draft v0.1 · last updated {{DATE}}

## 1. Purpose
Transform **episodic memory** (raw messages, tasks, feedback) into an **abstract knowledge representation** that feeds Semantic Memory. Extract *Concepts* (skills, tools, ideas) and *Relations* (PREREQUISITE_OF, PART_OF, CAUSES, ANALOGY, FOLLOW_UP).

## 2. Input & Output Contracts
### Input JSON
```json
{
  "episode_id": "uuid",
  "context": "<≤4 000 tokens of episode text>"
}
```
### Output JSON
```json
{
  "concepts": [
    {
      "id": "uuid",
      "name": "Bubble Sort",
      "type": "algorithm",
      "description": "A comparison sort that swaps adjacent elements.",
      "source_sentences": [12,13]
    }
  ],
  "relations": [
    {
      "source_id": "uuid",
      "target_id": "uuid",
      "relation": "PREREQUISITE_OF",
      "confidence": 0.82,
      "evidence_sentence": 14
    }
  ]
}
```
*Caller validates with `pydantic`; malformed JSON triggers a fix-json retry.*

## 3. Prompt Template
### 3.1 System Message
```
You are an expert knowledge-graph extractor helping an AI curriculum builder.
Return strictly valid JSON that follows the schema.
```
### 3.2 User Message (template)
```
Extract key concepts and relationships.
Rules:
1. Max 15 concepts.
2. Relation types: PREREQUISITE_OF, PART_OF, CAUSES, ANALOGY, FOLLOW_UP.
3. Concept names must appear verbatim in context (unless inferred=true).
4. confidence ∈ [0,1].
5. Return **only** JSON.

<SCHEMA>
```json
{…full schema…}
```
<CONTEXT>
{{context}}
```
### 3.3 Few-shot Primers
Include two example Q→A pairs before `<CONTEXT>`: one coding lesson, one soft-skill.

## 4. Extraction Pipeline
1. **Window** episode into ≤3 000-token chunks.
2. Call GPT-4o (temperature 0). 3 retries w/ exponential backoff.
3. Validate → fix-json if needed.
4. Upsert concepts to NebulaGraph; vectors to Infinity.
5. Deduplicate: Levenshtein<0.1 merges nodes.

## 5. Quality Gates
| Check | Threshold | Action |
|-------|-----------|--------|
| JSON valid | 100 % | auto-retry 2× |
| Avg confidence | ≥ 0.7 | else human review |
| Concepts count | ≤ 15 | else keep top-15 |

## 6. Future Work
* RAG-powered disambiguation using existing Semantic Memory.
* Self-critique second pass to score relation plausibility. 