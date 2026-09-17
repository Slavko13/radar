from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SearchProfile
from app.schemas import SearchProfileCreate, SearchProfileRead, SearchProfileUpdate

router = APIRouter(prefix="/search-profiles", tags=["search-profiles"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=list[SearchProfileRead])
async def list_profiles(db: DbSession) -> list[SearchProfile]:
    return list((await db.scalars(select(SearchProfile).order_by(SearchProfile.name))).all())


@router.post("", response_model=SearchProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(payload: SearchProfileCreate, db: DbSession) -> SearchProfile:
    profile = SearchProfile(**payload.model_dump())
    db.add(profile)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Search profile already exists") from exc
    await db.refresh(profile)
    return profile


@router.patch("/{profile_id}", response_model=SearchProfileRead)
async def update_profile(
    profile_id: int, payload: SearchProfileUpdate, db: DbSession
) -> SearchProfile:
    profile = await db.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Search profile not found")
    values = payload.model_dump(exclude_unset=True)
    for key in ("categories", "positive_keywords", "negative_keywords"):
        if values.get(key) is not None:
            values[key] = list(
                dict.fromkeys(value.strip() for value in values[key] if value.strip())
            )
    for key, value in values.items():
        setattr(profile, key, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Search profile already exists") from exc
    await db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: int, db: DbSession) -> None:
    profile = await db.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Search profile not found")
    await db.delete(profile)
    await db.commit()
