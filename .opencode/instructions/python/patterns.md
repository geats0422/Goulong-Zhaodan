---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python 模式

> 此文件扩展自 [common/patterns.md](../common/patterns.md)，包含 Python 特定内容。

## Protocol（鸭子类型）

```python
from typing import Protocol

class Repository(Protocol):
    def find_by_id(self, id: str) -> dict | None: ...
    def save(self, entity: dict) -> dict: ...
```

## Dataclass 作为 DTO

```python
from dataclasses import dataclass

@dataclass
class CreateUserRequest:
    name: str
    email: str
    age: int | None = None
```
