"""유효성 검사 유틸리티 모듈.

소켓 이벤트에서 사용하는 유효성 검사 함수들을 제공합니다.
"""


def validate_chat_message(message: str) -> tuple[bool, str | None]:
    """채팅 메시지의 유효성을 검사합니다.

    메시지가 비어있거나, 공백만 있거나, 최대 길이를 초과하는 경우
    유효하지 않은 것으로 판단합니다.

    인자:
        message: 검사할 메시지 텍스트

    반환값:
        (유효 여부, 오류 메시지) 튜플
        - 유효한 경우: (True, None)
        - 유효하지 않은 경우: (False, 오류 메시지)
    """
    # 메시지가 비어있는지 확인
    if not message or not message.strip():
        return False, "메시지가 비어있습니다"

    # 공백만 있는지 확인
    if message.strip() == "":
        return False, "메시지가 공백만 포함하고 있습니다"

    # 최대 길이 확인 (500자)
    if len(message) > 500:
        return False, "메시지가 최대 길이(500자)를 초과했습니다"

    return True, None
