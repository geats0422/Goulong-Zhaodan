# 官方默认合同规则包

本目录说明照胆「合同初审」智能体的系统默认知识库来源与维护方式。

## 设计目标

照胆只做合同初审，不再提供招投标场景。首期所有工程类别（房建施工、市政道路、装饰装修、机电安装、钢结构、通用工程）共享一个「通用工程合同规则包」，标识为 `general-engineering-contract-rules:v1`。

当用户没有匹配的已启用知识库文档时，检索服务（`knowledge_retrieval.retrieve_regulation_base`）会回退到该系统默认规则包。

## 法规来源 manifest

官方法规来源维护在 `backend/scripts/default_contract_rules_manifest.json`，包含：

- `rule_package_key`：规则包标识，格式 `name:version`。
- `application_scenario`：固定为 `contract`。
- `engineering_type_key` / `contract_type_key`：通用绑定，首期为 `general-engineering` / `other`。
- `official_domain_allowlist`：官方域名白名单，所有来源 URL 必须命中。
- `sources`：来源列表，每条记录官方 URL、发布日期、施行日期、版本、抓取日期、`content_hash`（`sha256:` + 64 位 16 进制）和本地文件名。

首期收录：

1. 《中华人民共和国民法典》第三编 合同
2. 《中华人民共和国建筑法》
3. 《建设工程质量管理条例》
4. 《建设工程安全生产管理条例》
5. 《中华人民共和国安全生产法》
6. 《保障农民工工资支付条例》
7. 建设工程施工合同纠纷相关司法解释（一）
8. 官方建设工程施工合同示范文本中与合同条款相关的部分

## 法规文件不入 Git

法规二进制/文本文件不直接提交版本库，避免合规与体积风险。管理员按以下流程维护：

1. 从官方域名白名单中的来源人工抓取法规正文，整理为 `knowledge-base/system/legal-regulations/<filename>`。
2. 计算文件 SHA-256，填入 manifest 的 `content_hash`（`sha256:` + 64 位 16 进制）。manifest 默认的 `0000…` 占位符仅用于占位，实际导入前必须替换为真实哈希。
3. 人工审核内容、发布日期、施行日期、版本号与抓取日期。
4. 运行 dry-run 预览计划，确认无误后再正式导入。

## 导入脚本

入口：`backend/scripts/import_default_knowledge.py`

```bash
# 预览计划（只校验 manifest，不写数据库、不读法规文件）
cd backend && uv run python scripts/import_default_knowledge.py --dry-run

# 正式导入（需要 reference_dir 下存在 manifest 中声明的文件）
cd backend && uv run python scripts/import_default_knowledge.py --reference-dir <path>
```

### 行为契约

- **管理员幂等导入**：相同 `rule_package_key + filename` 只导入一次，重复执行标记为 `skipped`。
- **合同规则包固定写入**：所有导入文档 `owner_type=system`、`application_scenario=contract`、`rule_package_key=general-engineering-contract-rules:v1`、`engineering_type_key=general-engineering`、`contract_type_key=other`、`is_active=True`。
- **content_hash 校验**：导入时校验本地文件 SHA-256 与 manifest 一致，不匹配则拒绝导入。
- **版本切换**：当 manifest 的 `rule_package_key` 变更（如 `:v1 → :v2`），导入新版本时会停用同包名、不同版本的系统合同文档（`is_active=False`），但**不删除**历史文档、版本、索引节点或历史报告快照。历史 `InspectionRecord.rule_package_keys_snapshot` 保持不变。
- **官方域名白名单**：manifest 校验阶段拒绝 URL 域名不在白名单的来源。
- **兜底分类**：`classify_filename` 无法识别文件时已从 `bidding` 改为 `contract`（合同规则包导入）。

## 检索回退

检索服务读取该规则包的契约见 `backend/app/services/knowledge_retrieval.py`：系统回退只匹配 `owner_type=system`、`application_scenario=contract`、`rule_package_key=general-engineering-contract-rules:v1`、`is_active=True` 且版本 `completed` 的文档。规则的检索/匹配逻辑由任务 7 实现，本规则包只负责入库与版本维护。
