"""
세션 데이터 초기화 스크립트

이 스크립트는 다음을 수행합니다:
1. 모든 SessionParticipant 레코드 삭제
2. 모든 ActionJudgment 레코드 삭제
3. 모든 StoryLog 레코드 삭제
4. 모든 GameSession 레코드 삭제

주의: 사용자(User)와 캐릭터(Character) 데이터는 유지됩니다.
"""

from app.database import SessionLocal
from app.models import ActionJudgment, GameSession, SessionParticipant, StoryLog


def reset_all_sessions():
    """모든 세션 관련 데이터를 초기화합니다."""
    db = SessionLocal()

    try:
        # 1. SessionParticipant 삭제
        participant_count = db.query(SessionParticipant).count()
        db.query(SessionParticipant).delete()
        print(f"✓ {participant_count}개의 SessionParticipant 레코드 삭제됨")

        # 2. ActionJudgment 삭제
        judgment_count = db.query(ActionJudgment).count()
        db.query(ActionJudgment).delete()
        print(f"✓ {judgment_count}개의 ActionJudgment 레코드 삭제됨")

        # 3. StoryLog 삭제
        story_count = db.query(StoryLog).count()
        db.query(StoryLog).delete()
        print(f"✓ {story_count}개의 StoryLog 레코드 삭제됨")

        # 4. GameSession 삭제
        session_count = db.query(GameSession).count()
        db.query(GameSession).delete()
        print(f"✓ {session_count}개의 GameSession 레코드 삭제됨")

        # 커밋
        db.commit()
        print("\n✅ 모든 세션 데이터가 성공적으로 초기화되었습니다!")
        print("   (사용자 및 캐릭터 데이터는 유지됨)")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 오류 발생: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("세션 데이터 초기화")
    print("=" * 60)
    print("\n경고: 이 작업은 모든 게임 세션, 스토리 로그, 참가자 정보를 삭제합니다.")
    print("사용자 계정과 캐릭터 데이터는 유지됩니다.\n")

    confirm = input("계속하시겠습니까? (yes/no): ")

    if confirm.lower() in ["yes", "y"]:
        reset_all_sessions()
    else:
        print("\n취소되었습니다.")
