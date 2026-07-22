---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python 测试

> 此文件扩展自 [common/testing.md](../common/testing.md)，包含 Python 特定内容。

## 框架

使用 **pytest** 作为测试框架。

## 覆盖率

```bash
pytest --cov=src --cov-report=term-missing
```

## 测试组织

使用 `pytest.mark` 进行测试分类：

```python
import pytest

@pytest.mark.unit
def test_calculate_total():
    ...
```
