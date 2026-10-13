from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import PortfolioItem, PortfolioProfile
from app.schemas import (
    PortfolioItemCreate,
    PortfolioItemRead,
    PortfolioItemUpdate,
    PortfolioProfileRead,
    PortfolioProfileUpdate,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_or_create_profile(db: AsyncSession) -> PortfolioProfile:
    profile = await db.get(PortfolioProfile, 1)
    if profile is None:
        profile = PortfolioProfile(id=1)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("/profile", response_model=PortfolioProfileRead)
async def read_profile(db: DbSession) -> PortfolioProfile:
    return await get_or_create_profile(db)


@router.put("/profile", response_model=PortfolioProfileRead)
async def update_profile(
    payload: PortfolioProfileUpdate, db: DbSession
) -> PortfolioProfile:
    profile = await get_or_create_profile(db)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/items", response_model=list[PortfolioItemRead])
async def list_items(db: DbSession) -> list[PortfolioItem]:
    return list((await db.scalars(select(PortfolioItem).order_by(PortfolioItem.title))).all())


@router.post("/items", response_model=PortfolioItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: PortfolioItemCreate, db: DbSession) -> PortfolioItem:
    item = PortfolioItem(**payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=PortfolioItemRead)
async def update_item(
    item_id: int, payload: PortfolioItemUpdate, db: DbSession
) -> PortfolioItem:
    item = await db.get(PortfolioItem, item_id)
    if not item:
        raise HTTPException(404, "Portfolio item not found")
    values = payload.model_dump(exclude_unset=True)
    for key in ("services", "skills"):
        if values.get(key) is not None:
            values[key] = list(
                dict.fromkeys(value.strip() for value in values[key] if value.strip())
            )
    for key, value in values.items():
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, db: DbSession) -> None:
    item = await db.get(PortfolioItem, item_id)
    if not item:
        raise HTTPException(404, "Portfolio item not found")
    await db.delete(item)
    await db.commit()
