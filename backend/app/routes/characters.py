"""캐릭터 관리 API 라우트."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Character, User

router = APIRouter(prefix="/api/characters", tags=["characters"])


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
    weaknesses: list[str] = Field(default_factory=list, description="약점")

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
                "weaknesses": ["어둠 공포증"],
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
    weaknesses: list[str] = Field(default_factory=list, description="약점")

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
                "weaknesses": ["어둠 공포증"],
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
        data=character.data,
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
            id=char.id, user_id=char.user_id, name=char.name, data=char.data, created_at=char.created_at.isoformat()
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
        # Initialize character data with D20 stats
        character_data = {
            "age": char_data.age,
            "race": char_data.race,
            "concept": char_data.concept,
            "strength": char_data.strength,
            "dexterity": char_data.dexterity,
            "constitution": char_data.constitution,
            "intelligence": char_data.intelligence,
            "wisdom": char_data.wisdom,
            "charisma": char_data.charisma,
            "skills": char_data.skills,
            "weaknesses": char_data.weaknesses,
            "status_effects": [],
            "inventory": [],
        }

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
            data=new_character.data,
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
        # Update character with D20 stats
        character.name = char_data.name.strip()
        character.data = {
            "age": char_data.age,
            "race": char_data.race,
            "concept": char_data.concept,
            "strength": char_data.strength,
            "dexterity": char_data.dexterity,
            "constitution": char_data.constitution,
            "intelligence": char_data.intelligence,
            "wisdom": char_data.wisdom,
            "charisma": char_data.charisma,
            "skills": char_data.skills,
            "weaknesses": char_data.weaknesses,
            "status_effects": character.data.get("status_effects", []),
            "inventory": character.data.get("inventory", []),
        }

        db.commit()
        db.refresh(character)

        return CharacterResponse(
            id=character.id,
            user_id=character.user_id,
            name=character.name,
            data=character.data,
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
