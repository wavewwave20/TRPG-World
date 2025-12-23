#!/usr/bin/env python3
"""
캐릭터 데이터 초기화 및 예시 캐릭터 생성 스크립트

기존 캐릭터를 모두 삭제하고 test 유저에게 올바른 데이터 구조로
예시 캐릭터들을 생성합니다.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime

from app.database import SessionLocal
from app.models import Character, User


def reset_characters():
    """기존 캐릭터를 모두 삭제하고 예시 캐릭터를 생성합니다."""
    db = SessionLocal()

    try:
        # 1. 기존 캐릭터 모두 삭제
        print("=" * 60)
        print("기존 캐릭터 삭제 중...")
        print("=" * 60)

        deleted_count = db.query(Character).delete()
        db.commit()
        print(f"✓ {deleted_count}개의 캐릭터가 삭제되었습니다.\n")

        # 2. test 유저 찾기
        print("=" * 60)
        print("test 유저 확인 중...")
        print("=" * 60)

        test_user = db.query(User).filter(User.username == "test").first()
        if not test_user:
            print("✗ test 유저를 찾을 수 없습니다.")
            print("  먼저 test 유저를 생성하세요: uv run python seed_users.py")
            return False

        print(f"✓ test 유저 발견 (ID: {test_user.id})\n")

        # 3. 예시 캐릭터 생성
        print("=" * 60)
        print("예시 캐릭터 생성 중...")
        print("=" * 60)

        example_characters = [
            {
                "name": "엘라리온",
                "data": {
                    "race": "엘프",
                    "concept": "숲의 수호자이자 명궁",
                    "inventory": [],
                    "strength": 12,
                    "dexterity": 18,
                    "constitution": 10,
                    "intelligence": 14,
                    "wisdom": 16,
                    "charisma": 11,
                    "skills": [
                        {
                            "type": "passive",
                            "name": "예리한 시야",
                            "description": "어둠 속에서도 멀리 볼 수 있으며, 숨겨진 것을 발견하기 쉽다",
                        },
                        {
                            "type": "active",
                            "name": "정밀 사격",
                            "description": "집중하여 급소를 노린다. 치명타 확률 증가",
                        },
                        {
                            "type": "passive",
                            "name": "자연과의 교감",
                            "description": "동물과 식물의 상태를 직감적으로 이해한다",
                        },
                    ],
                    "weaknesses": ["어둠 마법에 취약", "근접 전투 미숙"],
                    "status_effects": [],
                },
            },
            {
                "name": "그롬 아이언피스트",
                "data": {
                    "race": "드워프",
                    "concept": "전설적인 대장장이 전사",
                    "inventory": [],
                    "strength": 18,
                    "dexterity": 10,
                    "constitution": 16,
                    "intelligence": 12,
                    "wisdom": 13,
                    "charisma": 8,
                    "skills": [
                        {"type": "passive", "name": "강철 같은 체력", "description": "독과 질병에 대한 저항력이 높다"},
                        {"type": "active", "name": "강타", "description": "전력을 다해 내리치는 강력한 일격"},
                        {
                            "type": "passive",
                            "name": "대장장이의 눈",
                            "description": "무기와 갑옷의 품질을 한눈에 파악한다",
                        },
                    ],
                    "weaknesses": ["느린 이동 속도", "마법에 대한 이해 부족"],
                    "status_effects": [],
                },
            },
            {
                "name": "리리안 섀도우",
                "data": {
                    "race": "인간",
                    "concept": "교활한 도적이자 정보상",
                    "inventory": [],
                    "strength": 10,
                    "dexterity": 17,
                    "constitution": 12,
                    "intelligence": 15,
                    "wisdom": 11,
                    "charisma": 14,
                    "skills": [
                        {"type": "active", "name": "은신", "description": "그림자 속으로 몸을 숨긴다"},
                        {"type": "active", "name": "자물쇠 따기", "description": "복잡한 자물쇠도 순식간에 연다"},
                        {
                            "type": "passive",
                            "name": "거리의 정보망",
                            "description": "도시의 소문과 정보를 빠르게 수집한다",
                        },
                    ],
                    "weaknesses": ["정면 전투 회피", "신뢰 문제"],
                    "status_effects": [],
                },
            },
            {
                "name": "아리아 스타위버",
                "data": {
                    "race": "하프엘프",
                    "concept": "신비로운 마법사",
                    "inventory": [],
                    "strength": 8,
                    "dexterity": 12,
                    "constitution": 10,
                    "intelligence": 18,
                    "wisdom": 14,
                    "charisma": 15,
                    "skills": [
                        {"type": "active", "name": "화염구", "description": "불타는 구체를 발사한다"},
                        {"type": "active", "name": "마법 방패", "description": "마법 에너지로 보호막을 생성한다"},
                        {"type": "passive", "name": "마법 감지", "description": "주변의 마법 에너지를 감지한다"},
                        {"type": "passive", "name": "고대 지식", "description": "고대 문자와 마법 이론에 정통하다"},
                    ],
                    "weaknesses": ["낮은 체력", "마나 고갈 시 무력함"],
                    "status_effects": [],
                },
            },
            {
                "name": "세라핀 라이트브링어",
                "data": {
                    "race": "인간",
                    "concept": "정의로운 성기사",
                    "inventory": [],
                    "strength": 16,
                    "dexterity": 10,
                    "constitution": 14,
                    "intelligence": 10,
                    "wisdom": 15,
                    "charisma": 16,
                    "skills": [
                        {"type": "active", "name": "신성한 일격", "description": "신성한 힘을 담은 공격"},
                        {"type": "active", "name": "치유의 손길", "description": "아군의 상처를 치유한다"},
                        {"type": "passive", "name": "언데드 퇴치", "description": "언데드에게 추가 피해를 준다"},
                        {"type": "passive", "name": "카리스마적 리더십", "description": "아군의 사기를 북돋운다"},
                    ],
                    "weaknesses": ["명예에 얽매임", "속임수에 약함"],
                    "status_effects": [],
                },
            },
        ]

        created_characters = []
        for char_data in example_characters:
            character = Character(
                user_id=test_user.id, name=char_data["name"], data=char_data["data"], created_at=datetime.utcnow()
            )
            db.add(character)
            db.flush()  # Get the ID
            created_characters.append(character)

            print(f"\n✓ {character.name} 생성됨 (ID: {character.id})")
            print(f"  종족: {character.data['race']}")
            print(f"  컨셉: {character.data['concept']}")
            print(
                f"  능력치: STR {character.data['strength']}, "
                f"DEX {character.data['dexterity']}, "
                f"CON {character.data['constitution']}, "
                f"INT {character.data['intelligence']}, "
                f"WIS {character.data['wisdom']}, "
                f"CHA {character.data['charisma']}"
            )
            print(f"  스킬: {len(character.data['skills'])}개")

        db.commit()

        print("\n" + "=" * 60)
        print("완료!")
        print("=" * 60)
        print(f"✓ 총 {len(created_characters)}개의 캐릭터가 생성되었습니다.")
        print("\ntest 유저로 로그인하여 캐릭터를 확인하세요:")
        print("  Username: test")
        print("  Password: test123")
        print()

        return True

    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        db.rollback()
        import traceback

        traceback.print_exc()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("캐릭터 데이터 초기화 스크립트")
    print("=" * 60)
    print("이 스크립트는 다음을 수행합니다:")
    print("1. 기존 캐릭터 모두 삭제")
    print("2. test 유저에게 5개의 예시 캐릭터 생성")
    print("=" * 60)

    response = input("\n계속하시겠습니까? (y/N): ")
    if response.lower() != "y":
        print("취소되었습니다.")
        sys.exit(0)

    print()
    success = reset_characters()

    sys.exit(0 if success else 1)
