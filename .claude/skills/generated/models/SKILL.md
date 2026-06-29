---
name: models
description: "Skill for the Models area of Goulong-Zhaodan. 11 symbols across 2 files."
---

# Models

11 symbols | 2 files | Cohesion: 100%

## When to Use

- Working with code in `backend/`
- Understanding how ApiKey, AgentJob, Base work
- Modifying models-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/models/knowledge.py` | Base, EngineeringSubcategory, KnowledgeDocument, DocumentVersion, IndexNode (+4) |
| `backend/app/models/api_keys.py` | ApiKey, AgentJob |

## Entry Points

Start here when exploring this area:

- **`ApiKey`** (Class) — `backend/app/models/api_keys.py:12`
- **`AgentJob`** (Class) — `backend/app/models/api_keys.py:37`
- **`Base`** (Class) — `backend/app/models/knowledge.py:14`
- **`EngineeringSubcategory`** (Class) — `backend/app/models/knowledge.py:29`
- **`KnowledgeDocument`** (Class) — `backend/app/models/knowledge.py:46`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ApiKey` | Class | `backend/app/models/api_keys.py` | 12 |
| `AgentJob` | Class | `backend/app/models/api_keys.py` | 37 |
| `Base` | Class | `backend/app/models/knowledge.py` | 14 |
| `EngineeringSubcategory` | Class | `backend/app/models/knowledge.py` | 29 |
| `KnowledgeDocument` | Class | `backend/app/models/knowledge.py` | 46 |
| `DocumentVersion` | Class | `backend/app/models/knowledge.py` | 73 |
| `IndexNode` | Class | `backend/app/models/knowledge.py` | 96 |
| `ZhaodanUserProfile` | Class | `backend/app/models/knowledge.py` | 120 |
| `TabooWord` | Class | `backend/app/models/knowledge.py` | 134 |
| `KnowledgeDocumentSetting` | Class | `backend/app/models/knowledge.py` | 152 |
| `InspectionRecord` | Class | `backend/app/models/knowledge.py` | 168 |

## How to Explore

1. `gitnexus_context({name: "ApiKey"})` — see callers and callees
2. `gitnexus_query({query: "models"})` — find related execution flows
3. Read key files listed above for implementation details
