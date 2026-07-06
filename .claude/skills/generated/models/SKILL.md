---
name: models
description: "Skill for the Models area of Goulong-Zhaodan. 14 symbols across 4 files."
---

# Models

14 symbols | 4 files | Cohesion: 100%

## When to Use

- Working with code in `backend/`
- Understanding how ApiKey, AgentJob, SubscriptionContract work
- Modifying models-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/models/knowledge.py` | Base, EngineeringSubcategory, KnowledgeDocument, DocumentVersion, IndexNode (+4) |
| `backend/app/models/api_keys.py` | ApiKey, AgentJob |
| `backend/app/models/delegated_deduction.py` | SubscriptionContract, DeductionOrder |
| `backend/app/models/payment.py` | PaymentOrder |

## Entry Points

Start here when exploring this area:

- **`ApiKey`** (Class) — `backend/app/models/api_keys.py:12`
- **`AgentJob`** (Class) — `backend/app/models/api_keys.py:37`
- **`SubscriptionContract`** (Class) — `backend/app/models/delegated_deduction.py:10`
- **`DeductionOrder`** (Class) — `backend/app/models/delegated_deduction.py:36`
- **`Base`** (Class) — `backend/app/models/knowledge.py:14`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ApiKey` | Class | `backend/app/models/api_keys.py` | 12 |
| `AgentJob` | Class | `backend/app/models/api_keys.py` | 37 |
| `SubscriptionContract` | Class | `backend/app/models/delegated_deduction.py` | 10 |
| `DeductionOrder` | Class | `backend/app/models/delegated_deduction.py` | 36 |
| `Base` | Class | `backend/app/models/knowledge.py` | 14 |
| `EngineeringSubcategory` | Class | `backend/app/models/knowledge.py` | 29 |
| `KnowledgeDocument` | Class | `backend/app/models/knowledge.py` | 46 |
| `DocumentVersion` | Class | `backend/app/models/knowledge.py` | 73 |
| `IndexNode` | Class | `backend/app/models/knowledge.py` | 96 |
| `ZhaodanUserProfile` | Class | `backend/app/models/knowledge.py` | 120 |
| `TabooWord` | Class | `backend/app/models/knowledge.py` | 134 |
| `KnowledgeDocumentSetting` | Class | `backend/app/models/knowledge.py` | 152 |
| `InspectionRecord` | Class | `backend/app/models/knowledge.py` | 168 |
| `PaymentOrder` | Class | `backend/app/models/payment.py` | 10 |

## How to Explore

1. `gitnexus_context({name: "ApiKey"})` — see callers and callees
2. `gitnexus_query({query: "models"})` — find related execution flows
3. Read key files listed above for implementation details
