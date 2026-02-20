"""액션 큐 관리 모듈.

플레이어 행동 큐의 추가, 수정, 삭제, 재정렬을 담당합니다.
인메모리 저장소를 사용하며, 서버 재시작 시 데이터가 초기화됩니다.
"""

# 인메모리 액션 큐
# 구조: {session_id: [actions]}
# 각 action은 딕셔너리: {id, player_id, character_name, action_text, order}
action_queues: dict[int, list[dict]] = {}

# 액션 ID 카운터 (고유 ID 생성용)
action_counter: int = 0


def add_action(
    session_id: int,
    player_id: int,
    character_name: str,
    action_text: str,
    action_mode: str = "normal",
    skill_name: str | None = None,
    skill_ability: str | None = None,
) -> dict:
    """액션을 큐에 추가합니다.

    새로운 액션을 생성하고 세션의 큐에 추가합니다.
    액션 ID는 자동으로 증가하며, order는 현재 큐 길이로 설정됩니다.

    인자:
        session_id: 게임 세션 ID
        player_id: 플레이어(사용자) ID
        character_name: 캐릭터 이름
        action_text: 행동 텍스트

    반환값:
        dict: 생성된 액션 정보
            - id: 액션 ID
            - player_id: 플레이어 ID
            - character_name: 캐릭터 이름
            - action_text: 행동 텍스트
            - order: 큐 내 순서
    """
    global action_counter

    # 세션 큐 초기화
    if session_id not in action_queues:
        action_queues[session_id] = []

    # 액션 ID 증가
    action_counter += 1

    # 액션 생성
    action = {
        "id": action_counter,
        "player_id": player_id,
        "character_name": character_name,
        "action_text": action_text,
        "action_mode": action_mode,
        "skill_name": skill_name,
        "skill_ability": skill_ability,
        "order": len(action_queues[session_id]),
    }

    # 큐에 추가
    action_queues[session_id].append(action)

    return action


def edit_action(session_id: int, action_id: int, new_text: str) -> bool:
    """액션 텍스트를 수정합니다.

    인자:
        session_id: 게임 세션 ID
        action_id: 수정할 액션 ID
        new_text: 새로운 행동 텍스트

    반환값:
        bool: 수정 성공 여부
    """
    if session_id not in action_queues:
        return False

    for action in action_queues[session_id]:
        if action["id"] == action_id:
            action["action_text"] = new_text
            return True

    return False


def delete_action(session_id: int, action_id: int) -> bool:
    """액션을 큐에서 삭제합니다.

    삭제 후 남은 액션들의 order 필드를 재정렬합니다.

    인자:
        session_id: 게임 세션 ID
        action_id: 삭제할 액션 ID

    반환값:
        bool: 삭제 성공 여부
    """
    if session_id not in action_queues:
        return False

    original_length = len(action_queues[session_id])

    # 해당 ID의 액션 제거
    action_queues[session_id] = [action for action in action_queues[session_id] if action["id"] != action_id]

    # 삭제되었는지 확인
    if len(action_queues[session_id]) == original_length:
        return False

    # order 필드 재정렬
    for idx, action in enumerate(action_queues[session_id]):
        action["order"] = idx

    return True


def reorder_actions(session_id: int, action_ids: list[int]) -> bool:
    """액션 순서를 재정렬합니다.

    주어진 액션 ID 순서대로 큐를 재구성합니다.

    인자:
        session_id: 게임 세션 ID
        action_ids: 새로운 순서의 액션 ID 목록

    반환값:
        bool: 재정렬 성공 여부
    """
    if session_id not in action_queues:
        return False

    # ID -> 액션 매핑 생성
    action_map = {action["id"]: action for action in action_queues[session_id]}

    # 새 순서로 큐 재구성
    reordered = []
    for idx, action_id in enumerate(action_ids):
        if action_id in action_map:
            action = action_map[action_id]
            action["order"] = idx
            reordered.append(action)

    action_queues[session_id] = reordered
    return True


def get_queue(session_id: int) -> list[dict]:
    """세션의 액션 큐를 반환합니다.

    세션에 큐가 없으면 빈 리스트를 반환합니다.

    인자:
        session_id: 게임 세션 ID

    반환값:
        list[dict]: 액션 목록
    """
    if session_id not in action_queues:
        action_queues[session_id] = []

    return action_queues[session_id]


def clear_queue(session_id: int) -> list[dict]:
    """세션의 액션 큐를 비우고 기존 액션을 반환합니다.

    인자:
        session_id: 게임 세션 ID

    반환값:
        list[dict]: 비우기 전의 액션 목록 (order 기준 정렬됨)
    """
    if session_id not in action_queues:
        return []

    # 기존 액션을 order 기준으로 정렬하여 저장
    actions = sorted(action_queues[session_id], key=lambda a: a["order"])

    # 큐 비우기
    action_queues[session_id] = []

    return actions


def get_queue_count(session_id: int) -> int:
    """세션의 액션 큐 길이를 반환합니다.

    인자:
        session_id: 게임 세션 ID

    반환값:
        int: 큐에 있는 액션 수
    """
    if session_id not in action_queues:
        return 0

    return len(action_queues[session_id])
