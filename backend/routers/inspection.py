"""体检台 API 路由"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from agents.inspector import run_inspection
from core.auth import get_current_user
from core.deps import InspectionDeps

router = APIRouter(prefix="/inspection", tags=["体检台"])


# ─── 内存中的体检记录（后续可替换为 PostgreSQL） ───
_inspection_records: list[dict[str, Any]] = []


class InspectionCreateRequest(BaseModel):
    """创建体检请求"""

    project_id: str = "default"
    taboo_words: list[str] | None = None


class InspectionReportResponse(BaseModel):
    """体检报告响应"""

    id: int
    overall_risk: str
    summary: str
    issues: list[dict[str, Any]]
    regulation_refs: list[str]
    document_name: str


class HistoryStatsSummary(BaseModel):
    total_docs: int
    hit_docs: int
    banned_rate: float
    quota_consumed: int


class HistoryStatsTrend(BaseModel):
    dates: list[str]
    total_docs: list[int]
    hit_docs: list[int]
    banned_rate: list[float]
    quota_consumed: list[int]


class HistoryStatsResponse(BaseModel):
    range: str
    timezone: str
    summary: HistoryStatsSummary
    trend: HistoryStatsTrend


def _build_last_n_dates(days: int) -> list[date]:
    today = date.today()
    return [today - timedelta(days=offset) for offset in reversed(range(days))]


def _safe_parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _calc_rate(hit_docs: int, total_docs: int) -> float:
    if total_docs == 0:
        return 0.0
    return round(hit_docs / total_docs, 4)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _aggregate_history_stats(records: list[dict[str, Any]], days: int = 7) -> HistoryStatsResponse:
    buckets = {
        d.isoformat(): {"total_docs": 0, "hit_docs": 0, "quota_consumed": 0}
        for d in _build_last_n_dates(days)
    }

    for record in records:
        created_at = _safe_parse_date(record.get("created_at"))
        if created_at is None:
            continue

        key = created_at.isoformat()
        if key not in buckets:
            continue

        buckets[key]["total_docs"] += 1
        if record.get("issues"):
            buckets[key]["hit_docs"] += 1
        buckets[key]["quota_consumed"] += _safe_int(record.get("quota_consumed", 0) or 0)

    dates = list(buckets.keys())
    total_docs_series = [buckets[d]["total_docs"] for d in dates]
    hit_docs_series = [buckets[d]["hit_docs"] for d in dates]
    quota_series = [buckets[d]["quota_consumed"] for d in dates]
    rate_series = [_calc_rate(hit, total) for hit, total in zip(hit_docs_series, total_docs_series)]

    total_docs = sum(total_docs_series)
    hit_docs = sum(hit_docs_series)
    quota_consumed = sum(quota_series)

    return HistoryStatsResponse(
        range="7d",
        timezone="Asia/Shanghai",
        summary=HistoryStatsSummary(
            total_docs=total_docs,
            hit_docs=hit_docs,
            banned_rate=_calc_rate(hit_docs, total_docs),
            quota_consumed=quota_consumed,
        ),
        trend=HistoryStatsTrend(
            dates=dates,
            total_docs=total_docs_series,
            hit_docs=hit_docs_series,
            banned_rate=rate_series,
            quota_consumed=quota_series,
        ),
    )


@router.post("/upload", response_model=InspectionReportResponse)
async def upload_and_inspect(
    file: UploadFile = File(..., description="待体检的工程文档"),
    project_id: str = Form(default="default"),
    taboo_words: str = Form(default=""),
    user: dict = Depends(get_current_user),
) -> InspectionReportResponse:
    """
    上传文档并执行智能体检。

    支持格式：txt、pdf（文本提取后处理）
    """
    # 读取文件内容
    try:
        content = await file.read()
        text = content.decode("utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法读取文件: {exc}") from exc

    if len(text) < 10:
        raise HTTPException(status_code=400, detail="文件内容过短，无法体检")

    # 解析违禁词
    taboo_list = [w.strip() for w in taboo_words.split(",") if w.strip()]

    # 构建依赖
    deps = InspectionDeps(
        project_id=project_id,
        taboo_words=taboo_list or None,
    )

    # 运行 Agent 体检
    result = await run_inspection(text, deps)

    # 保存记录
    record_id = len(_inspection_records) + 1
    record = {
        "id": record_id,
        "document_name": file.filename or "unknown",
        "project_id": project_id,
        "overall_risk": result.overall_risk,
        "summary": result.summary,
        "issues": result.issues,
        "regulation_refs": result.regulation_refs,
        "text_preview": text[:500],
        "created_at": date.today().isoformat(),
        "quota_consumed": max(1, len(text) // 500),
    }
    _inspection_records.append(record)

    return InspectionReportResponse(
        id=record_id,
        overall_risk=result.overall_risk,
        summary=result.summary,
        issues=result.issues,
        regulation_refs=result.regulation_refs,
        document_name=file.filename or "unknown",
    )


@router.get("/records")
async def list_records(
    project_id: str | None = None,
    risk_level: str | None = None,
    user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """获取体检记录列表（支持按项目和风险等级筛选）"""
    records = _inspection_records

    if project_id:
        records = [r for r in records if r["project_id"] == project_id]

    if risk_level:
        records = [r for r in records if r["overall_risk"] == risk_level]

    # 脱敏返回
    return [
        {
            "id": r["id"],
            "document_name": r["document_name"],
            "project_id": r["project_id"],
            "overall_risk": r["overall_risk"],
            "summary": r["summary"],
            "issue_count": len(r["issues"]),
        }
        for r in records
    ]


@router.get("/records/{record_id}")
async def get_record(record_id: int, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    """获取单条体检记录详情"""
    for r in _inspection_records:
        if r["id"] == record_id:
            return {
                "id": r["id"],
                "document_name": r["document_name"],
                "project_id": r["project_id"],
                "overall_risk": r["overall_risk"],
                "summary": r["summary"],
                "issues": r["issues"],
                "regulation_refs": r["regulation_refs"],
            }
    raise HTTPException(status_code=404, detail="记录不存在")


@router.get("/stats/history", response_model=HistoryStatsResponse)
async def get_history_stats(
    project_id: str = "default",
    range: str = "7d",
    user: dict = Depends(get_current_user),
) -> HistoryStatsResponse:
    """获取历史统计（MVP: 近7天，按天聚合）。"""
    if range != "7d":
        raise HTTPException(status_code=400, detail="当前仅支持 range=7d")

    scoped_records = [record for record in _inspection_records if record.get("project_id") == project_id]
    return _aggregate_history_stats(scoped_records, days=7)
