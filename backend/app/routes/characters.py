"""캐릭터 관리 API 라우트."""

import secrets
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Character, CharacterShareCode, User
from app.services.character_state import consume_inventory_item, normalize_inventory_items, normalize_statuses

router = APIRouter(prefix="/api/characters", tags=["characters"])
SHARE_CODE_EXPIRE_MINUTES = 3


def _normalize_legacy_weaknesses(weaknesses: list[str] | None) -> list[dict[str, Any]]:
    if not weaknesses:
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in weaknesses:
        name = str(raw or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "name": name,
                "category": "mental",
                "type": "debuff",
                "modifier": -1,
                "source": "legacy_weakness",
            }
        )
    return normalized


def _build_character_data(
    *,
    age: int,
    race: str,
    concept: str,
    strength: int,
    dexterity: int,
    constitution: int,
    intelligence: int,
    wisdom: int,
    charisma: int,
    skills: list[dict[str, Any]],
    statuses: list[dict[str, Any] | str] | None,
    weaknesses: list[str] | None,
    inventory: list[dict[str, Any] | str] | None,
    status_effects: list[Any] | None,
    sync_status_effects: bool,
) -> dict[str, Any]:
    raw_inventory = inventory or []
    normalized_inventory = normalize_inventory_items(raw_inventory)
    seeded_statuses = statuses or []
    if not seeded_statuses and weaknesses:
        seeded_statuses = _normalize_legacy_weaknesses(weaknesses)

    data = {
        "age": age,
        "race": race,
        "concept": concept,
        "strength": strength,
        "dexterity": dexterity,
        "constitution": constitution,
        "intelligence": intelligence,
        "wisdom": wisdom,
        "charisma": charisma,
        "skills": skills,
        "weaknesses": weaknesses or [],
        "inventory": raw_inventory,
        "statuses": seeded_statuses,
        "status_effects": status_effects or [],
    }

    status_seed_data = dict(data)
    status_seed_data["inventory"] = normalized_inventory
    normalized_statuses = normalize_statuses(status_seed_data, include_legacy_status_effects=True)
    data["statuses"] = normalized_statuses
    if sync_status_effects:
        data["status_effects"] = normalized_statuses
    return data


def _normalize_character_data_for_response(data: dict[str, Any] | None) -> dict[str, Any]:
    payload = deepcopy(data or {})
    raw_inventory = payload.get("inventory", [])
    payload["inventory"] = raw_inventory if isinstance(raw_inventory, list) else []
    status_seed_data = dict(payload)
    status_seed_data["inventory"] = normalize_inventory_items(payload["inventory"])
    payload["statuses"] = normalize_statuses(status_seed_data)

    if not isinstance(payload.get("weaknesses"), list):
        payload["weaknesses"] = []

    return payload


class CharacterCreate(BaseModel):
    """Request model for creating a new character."""

    user_id: int = Field(..., description="ID of the user creating the character")
    name: str = Field(..., min_length=1, description="Character name")
    age: int = Field(default=25, ge=1, description="Character age")
    race: str = Field(default="인간", description="Character race")
    concept: str = Field(default="", description="Character concept/background")

    # D20 Ability Scores
    strength: int = Field(default=10, ge=1, le=30, description="근력 (STR)")
    dexterity: int = Field(default=10, ge=1, le=30, description="민첩 (DEX)")
    constitution: int = Field(default=10, ge=1, le=30, description="건강 (CON)")
    intelligence: int = Field(default=10, ge=1, le=30, description="지능 (INT)")
    wisdom: int = Field(default=10, ge=1, le=30, description="지혜 (WIS)")
    charisma: int = Field(default=10, ge=1, le=30, description="매력 (CHA)")

    # Skills with detailed information
    skills: list[dict] = Field(default_factory=list, description="스킬 목록")
    weaknesses: list[str] | None = Field(default=None, description="레거시 약점 필드")
    statuses: list[dict[str, Any] | str] | None = Field(default=None, description="상태")
    inventory: list[dict[str, Any] | str] | None = Field(default=None, description="인벤토리")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "name": "엘프 궁수",
                "age": 120,
                "race": "엘프",
                "concept": "숲의 수호자",
                "strength": 12,
                "dexterity": 16,
                "constitution": 10,
                "intelligence": 14,
                "wisdom": 13,
                "charisma": 11,
                "skills": [
                    {"type": "passive", "name": "예리한 시야", "description": "어둠 속에서도 멀리 볼 수 있다"},
                    {"type": "active", "name": "정밀 사격", "description": "집중하여 급소를 노린다"},
                ],
                "statuses": [{"name": "집중", "type": "buff", "modifier": 2}],
                "inventory": [
                    {"name": "치유 물약", "type": "consumable", "quantity": 2},
                    {"name": "강철 검", "type": "equipment", "equipped": True, "modifier": 1},
                ],
            }
        }


class CharacterUpdate(BaseModel):
    """Request model for updating a character."""

    name: str = Field(..., min_length=1, description="Character name")
    age: int = Field(..., ge=1, description="Character age")
    race: str = Field(..., description="Character race")
    concept: str = Field(default="", description="Character concept/background")

    # D20 Ability Scores
    strength: int = Field(..., ge=1, le=30, description="근력 (STR)")
    dexterity: int = Field(..., ge=1, le=30, description="민첩 (DEX)")
    constitution: int = Field(..., ge=1, le=30, description="건강 (CON)")
    intelligence: int = Field(..., ge=1, le=30, description="지능 (INT)")
    wisdom: int = Field(..., ge=1, le=30, description="지혜 (WIS)")
    charisma: int = Field(..., ge=1, le=30, description="매력 (CHA)")

    # Skills with detailed information
    skills: list[dict] = Field(default_factory=list, description="스킬 목록")
    weaknesses: list[str] | None = Field(default=None, description="레거시 약점 필드")
    statuses: list[dict[str, Any] | str] | None = Field(default=None, description="상태")
    inventory: list[dict[str, Any] | str] | None = Field(default=None, description="인벤토리")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "엘프 궁수",
                "age": 120,
                "race": "엘프",
                "concept": "숲의 수호자",
                "strength": 12,
                "dexterity": 16,
                "constitution": 10,
                "intelligence": 14,
                "wisdom": 13,
                "charisma": 11,
                "skills": [
                    {"type": "passive", "name": "예리한 시야", "description": "어둠 속에서도 멀리 볼 수 있다"},
                    {"type": "active", "name": "정밀 사격", "description": "집중하여 급소를 노린다"},
                ],
                "statuses": [{"name": "집중", "type": "buff", "modifier": 2}],
                "inventory": [
                    {"name": "치유 물약", "type": "consumable", "quantity": 2},
                    {"name": "강철 검", "type": "equipment", "equipped": True, "modifier": 1},
                ],
            }
        }


class CharacterResponse(BaseModel):
    """Response model for character."""

    id: int
    user_id: int
    name: str
    data: dict[str, Any]
    created_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": 1,
                "name": "엘프 궁수",
                "data": {"HP": 100, "MP": 50, "inventory": []},
                "created_at": "2025-12-15T10:30:00",
            }
        }


class CharacterShareCodeCreateRequest(BaseModel):
    """Request model for creating a character share code."""

    user_id: int = Field(..., description="ID of the user who owns the character")


class CharacterShareCodeCreateResponse(BaseModel):
    """Response model for character share code creation."""

    share_code: str
    character_id: int
    character_name: str
    created_at: str


class CharacterShareCodeRedeemRequest(BaseModel):
    """Request model for redeeming a character share code."""

    user_id: int = Field(..., description="ID of the user receiving the shared character")
    share_code: str = Field(..., description="9-digit numeric share code")


class CharacterShareCodeRedeemResponse(BaseModel):
    """Response model for successful share code redemption."""

    message: str
    character: CharacterResponse


class InventoryConsumeRequest(BaseModel):
    item_name: str = Field(..., min_length=1, description="소모할 아이템 이름")


def _generate_unique_share_code(db: Session) -> str:
    """Generate a unique 9-digit numeric share code."""
    for _ in range(30):
        code = f"{secrets.randbelow(900_000_000) + 100_000_000:09d}"
        existing = db.query(CharacterShareCode).filter(CharacterShareCode.code == code).first()
        if not existing:
            return code
    raise HTTPException(status_code=500, detail="Failed to generate unique share code")


def _build_shared_character_name(db: Session, target_user_id: int, source_name: str) -> str:
    """Build a non-conflicting character name for shared character import."""
    base_name = source_name.strip()
    same_name_exists = (
        db.query(Character).filter(Character.user_id == target_user_id, Character.name == base_name).first() is not None
    )
    if not same_name_exists:
        return base_name

    shared_name = f"{base_name} (공유본)"
    suffix = 2
    while (
        db.query(Character).filter(Character.user_id == target_user_id, Character.name == shared_name).first()
        is not None
    ):
        shared_name = f"{base_name} (공유본 {suffix})"
        suffix += 1
    return shared_name


def _is_share_code_expired(share_entry: CharacterShareCode) -> bool:
    """Return True when share code is older than configured TTL."""
    return datetime.utcnow() > share_entry.created_at + timedelta(minutes=SHARE_CODE_EXPIRE_MINUTES)


@router.get("/{character_id}", response_model=CharacterResponse)
def get_character(character_id: int, db: Session = Depends(get_db)):
    """
    Get a character by ID.

    Args:
        character_id: Character ID
        db: Database session

    Returns:
        Character details

    Raises:
        HTTPException 404: If character not found
    """
    character = db.query(Character).filter(Character.id == character_id).first()

    if not character:
        raise HTTPException(status_code=404, detail=f"Character with id {character_id} not found")

    return CharacterResponse(
        id=character.id,
        user_id=character.user_id,
        name=character.name,
        data=_normalize_character_data_for_response(character.data),
        created_at=character.created_at.isoformat(),
    )


@router.get("/user/{user_id}", response_model=list[CharacterResponse])
def get_user_characters(user_id: int, db: Session = Depends(get_db)):
    """
    Get all characters for a user.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        List of characters
    """
    characters = db.query(Character).filter(Character.user_id == user_id).all()

    return [
        CharacterResponse(
            id=char.id,
            user_id=char.user_id,
            name=char.name,
            data=_normalize_character_data_for_response(char.data),
            created_at=char.created_at.isoformat(),
        )
        for char in characters
    ]


@router.post("/", response_model=CharacterResponse, status_code=201)
def create_character(char_data: CharacterCreate, db: Session = Depends(get_db)):
    """
    Create a new character.

    Args:
        char_data: Character creation data
        db: Database session

    Returns:
        Created character

    Raises:
        HTTPException 400: If name is empty
        HTTPException 404: If user does not exist
    """
    # Validation: Check for empty name
    if not char_data.name or not char_data.name.strip():
        raise HTTPException(status_code=400, detail="Name is required and cannot be empty")

    # Validation: Verify user exists
    user = db.query(User).filter(User.id == char_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {char_data.user_id} not found")

    try:
        character_data = _build_character_data(
            age=char_data.age,
            race=char_data.race,
            concept=char_data.concept,
            strength=char_data.strength,
            dexterity=char_data.dexterity,
            constitution=char_data.constitution,
            intelligence=char_data.intelligence,
            wisdom=char_data.wisdom,
            charisma=char_data.charisma,
            skills=char_data.skills,
            statuses=char_data.statuses,
            weaknesses=char_data.weaknesses,
            inventory=char_data.inventory,
            status_effects=[],
            sync_status_effects=False,
        )

        # Create new character
        new_character = Character(
            user_id=char_data.user_id, name=char_data.name.strip(), data=character_data, created_at=datetime.utcnow()
        )

        db.add(new_character)
        db.commit()
        db.refresh(new_character)

        return CharacterResponse(
            id=new_character.id,
            user_id=new_character.user_id,
            name=new_character.name,
            data=_normalize_character_data_for_response(new_character.data),
            created_at=new_character.created_at.isoformat(),
        )

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create character: {e!s}")


@router.put("/{character_id}", response_model=CharacterResponse)
def update_character(character_id: int, char_data: CharacterUpdate, db: Session = Depends(get_db)):
    """
    Update a character.

    Args:
        character_id: Character ID
        char_data: Updated character data
        db: Database session

    Returns:
        Updated character

    Raises:
        HTTPException 404: If character not found
    """
    character = db.query(Character).filter(Character.id == character_id).first()

    if not character:
        raise HTTPException(status_code=404, detail=f"Character with id {character_id} not found")

    # Validation: Check for empty name
    if not char_data.name or not char_data.name.strip():
        raise HTTPException(status_code=400, detail="Name is required and cannot be empty")

    try:
        existing_data = character.data if isinstance(character.data, dict) else {}
        character.name = char_data.name.strip()
        should_sync_status_effects = (
            char_data.statuses is not None or char_data.weaknesses is not None or char_data.inventory is not None
        )
        character.data = _build_character_data(
            age=char_data.age,
            race=char_data.race,
            concept=char_data.concept,
            strength=char_data.strength,
            dexterity=char_data.dexterity,
            constitution=char_data.constitution,
            intelligence=char_data.intelligence,
            wisdom=char_data.wisdom,
            charisma=char_data.charisma,
            skills=char_data.skills,
            statuses=char_data.statuses if char_data.statuses is not None else existing_data.get("statuses", []),
            weaknesses=char_data.weaknesses
            if char_data.weaknesses is not None
            else existing_data.get("weaknesses", []),
            inventory=char_data.inventory if char_data.inventory is not None else existing_data.get("inventory", []),
            status_effects=existing_data.get("status_effects", []),
            sync_status_effects=should_sync_status_effects,
        )

        db.commit()
        db.refresh(character)

        return CharacterResponse(
            id=character.id,
            user_id=character.user_id,
            name=character.name,
            data=_normalize_character_data_for_response(character.data),
            created_at=character.created_at.isoformat(),
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update character: {e!s}")


@router.delete("/{character_id}", status_code=204)
def delete_character(character_id: int, db: Session = Depends(get_db)):
    """
    Delete a character.

    Args:
        character_id: Character ID
        db: Database session

    Raises:
        HTTPException 404: If character not found
    """
    character = db.query(Character).filter(Character.id == character_id).first()

    if not character:
        raise HTTPException(status_code=404, detail=f"Character with id {character_id} not found")

    try:
        db.delete(character)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete character: {e!s}")


@router.post("/{character_id}/inventory/consume", response_model=CharacterResponse)
def consume_character_inventory_item(
    character_id: int,
    payload: InventoryConsumeRequest,
    db: Session = Depends(get_db),
):
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Character with id {character_id} not found")

    try:
        data = deepcopy(character.data or {})
        original_inventory = normalize_inventory_items(data.get("inventory", []))
        updated_inventory = consume_inventory_item(original_inventory, payload.item_name)

        if updated_inventory == original_inventory:
            raise HTTPException(status_code=400, detail="Consumable item not found")

        data["inventory"] = updated_inventory
        status_seed_data = dict(data)
        status_seed_data["inventory"] = updated_inventory
        data["statuses"] = normalize_statuses(status_seed_data, include_legacy_status_effects=True)

        character.data = data
        db.commit()
        db.refresh(character)

        return CharacterResponse(
            id=character.id,
            user_id=character.user_id,
            name=character.name,
            data=_normalize_character_data_for_response(character.data),
            created_at=character.created_at.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to consume inventory item: {e!s}")


@router.post("/{character_id}/share-code", response_model=CharacterShareCodeCreateResponse, status_code=201)
def create_character_share_code(
    character_id: int,
    payload: CharacterShareCodeCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Create a one-time share code for a character.

    Args:
        character_id: Character ID to share
        payload: Request payload with owner user_id
        db: Database session

    Returns:
        9-digit share code

    Raises:
        HTTPException 404: If character not found
        HTTPException 403: If user does not own the character
    """
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Character with id {character_id} not found")

    if character.user_id != payload.user_id:
        raise HTTPException(status_code=403, detail="You can only share your own character")

    try:
        share_code = _generate_unique_share_code(db)
        now = datetime.utcnow()
        share_entry = CharacterShareCode(
            code=share_code,
            source_character_id=character.id,
            source_user_id=character.user_id,
            created_at=now,
        )

        db.add(share_entry)
        db.commit()
        db.refresh(share_entry)

        return CharacterShareCodeCreateResponse(
            share_code=share_entry.code,
            character_id=character.id,
            character_name=character.name,
            created_at=share_entry.created_at.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create share code: {e!s}")


@router.post("/share/redeem", response_model=CharacterShareCodeRedeemResponse, status_code=201)
def redeem_character_share_code(payload: CharacterShareCodeRedeemRequest, db: Session = Depends(get_db)):
    """
    Redeem a character share code and clone the character to the recipient.

    Args:
        payload: recipient user_id and 9-digit share code
        db: Database session

    Returns:
        Newly created shared character for recipient

    Raises:
        HTTPException 400: Invalid/used share code or self-redemption
        HTTPException 404: User/share code/source character not found
    """
    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User with id {payload.user_id} not found")

    share_code = payload.share_code.strip()
    if not share_code.isdigit() or len(share_code) != 9:
        raise HTTPException(status_code=400, detail="Share code must be a 9-digit number")

    share_entry = db.query(CharacterShareCode).filter(CharacterShareCode.code == share_code).first()
    if not share_entry:
        raise HTTPException(status_code=404, detail="Share code not found")

    if share_entry.redeemed_at is not None:
        raise HTTPException(status_code=400, detail="Share code has already been used")

    if _is_share_code_expired(share_entry):
        raise HTTPException(
            status_code=400, detail=f"Share code has expired (valid for {SHARE_CODE_EXPIRE_MINUTES} minutes)"
        )

    if share_entry.source_user_id == payload.user_id:
        raise HTTPException(status_code=400, detail="You cannot redeem your own share code")

    source_character = db.query(Character).filter(Character.id == share_entry.source_character_id).first()
    if not source_character:
        raise HTTPException(status_code=404, detail="Source character not found")

    try:
        cloned_name = _build_shared_character_name(db, payload.user_id, source_character.name)
        new_character = Character(
            user_id=payload.user_id,
            name=cloned_name,
            data=deepcopy(source_character.data or {}),
            created_at=datetime.utcnow(),
        )
        db.add(new_character)

        share_entry.redeemed_by_user_id = payload.user_id
        share_entry.redeemed_at = datetime.utcnow()

        db.commit()
        db.refresh(new_character)

        character_response = CharacterResponse(
            id=new_character.id,
            user_id=new_character.user_id,
            name=new_character.name,
            data=_normalize_character_data_for_response(new_character.data),
            created_at=new_character.created_at.isoformat(),
        )

        return CharacterShareCodeRedeemResponse(
            message="Character shared successfully",
            character=character_response,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to redeem share code: {e!s}")


@router.post("/{character_id}/duplicate", response_model=CharacterResponse, status_code=201)
def duplicate_character(character_id: int, db: Session = Depends(get_db)):
    """
    Duplicate a character with all profile data.

    Args:
        character_id: Source character ID
        db: Database session

    Returns:
        Newly duplicated character

    Raises:
        HTTPException 404: If source character not found
    """
    source_character = db.query(Character).filter(Character.id == character_id).first()

    if not source_character:
        raise HTTPException(status_code=404, detail=f"Character with id {character_id} not found")

    try:
        base_name = source_character.name.strip()
        duplicated_name = f"{base_name} (복제본)"
        suffix = 2

        while (
            db.query(Character)
            .filter(Character.user_id == source_character.user_id, Character.name == duplicated_name)
            .first()
            is not None
        ):
            duplicated_name = f"{base_name} (복제본 {suffix})"
            suffix += 1

        new_character = Character(
            user_id=source_character.user_id,
            name=duplicated_name,
            data=deepcopy(source_character.data or {}),
            created_at=datetime.utcnow(),
        )

        db.add(new_character)
        db.commit()
        db.refresh(new_character)

        return CharacterResponse(
            id=new_character.id,
            user_id=new_character.user_id,
            name=new_character.name,
            data=_normalize_character_data_for_response(new_character.data),
            created_at=new_character.created_at.isoformat(),
        )

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to duplicate character: {e!s}")
