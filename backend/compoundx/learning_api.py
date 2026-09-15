from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from .auth import decode_token
from .config import CONFIG
from .db import connection, is_configured
from .learning import pre_trade_check, record_trade_lesson, fingerprint, review_similar_lessons

router = APIRouter(prefix="/api/learning", tags=["learning"])


class PreTradeRequest(BaseModel):
    context: dict = Field(default_factory=dict)
    base_score: int = Field(ge=0, le=9)


class LessonRequest(BaseModel):
    trade_id: str
    context: dict = Field(default_factory=dict)
    outcome: dict = Field(default_factory=dict)


def user_token(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        return decode_token(authorization[7:].strip())
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


@router.get("/status")
def learning_status():
    return {"enabled": is_configured(), "mode": "ADVISORY", "max_adjustment": 2, "minimum_score": CONFIG.strategy.minimum_signal_score}


@router.post("/pre-trade")
def learning_pre_trade(request: PreTradeRequest, claims: dict = Depends(user_token)):
    if not is_configured():
        raise HTTPException(status_code=503, detail="Database is not configured")
    context = dict(request.context)
    result = pre_trade_check(context, request.base_score, CONFIG.strategy.minimum_signal_score)
    with connection() as conn:
        conn.execute(
            "INSERT INTO learning_reviews(trade_id,fingerprint,base_score,adjusted_score,adjustment,blocked,matched_lessons,rationale) VALUES(NULL,%s,%s,%s,%s,%s,%s,%s)",
            (fingerprint(context), result["base_score"], result["adjusted_score"], result["learning"]["adjustment"], result["blocked"], result["learning"]["similar_trades"], result["reason"]),
        )
    return result


@router.post("/lessons")
def learning_lesson(request: LessonRequest, claims: dict = Depends(user_token)):
    if not is_configured():
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        uuid.UUID(request.trade_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid trade_id")
    with connection() as conn:
        result = record_trade_lesson(conn, trade_id=request.trade_id, context=request.context, outcome=request.outcome)
    return {"ok": True, **result}


@router.post("/review")
def learning_review(request: PreTradeRequest, claims: dict = Depends(user_token)):
    if not is_configured():
        raise HTTPException(status_code=503, detail="Database is not configured")
    with connection() as conn:
        return review_similar_lessons(conn, request.context)
