"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Query


def get_card_key(
    x_card_key: Annotated[Optional[str], Header(alias="X-Card-Key")] = None,
    card_key: Annotated[Optional[str], Query()] = None,
) -> str:
    value = (x_card_key or card_key or "").strip()
    if not value:
        raise HTTPException(status_code=401, detail="Missing card key")
    return value


UserCardKey = Annotated[str, Depends(get_card_key)]
