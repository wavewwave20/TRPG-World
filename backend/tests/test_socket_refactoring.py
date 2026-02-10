"""소켓 서버 리팩토링 테스트 모듈.

리팩토링된 소켓 서버 모듈의 정확성을 검증합니다.
"""

import ast
import importlib
import inspect
import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ============================================================================
# Property 2: 한글 Docstring 포함 테스트
# 검증 대상: 요구사항 2.3, 3.3, 4.4, 5.4, 6.3, 7.3, 8.3, 9.4, 10.3, 11.3, 13.1, 13.2, 13.4
# ============================================================================


def contains_korean(text: str) -> bool:
    """텍스트에 한글이 포함되어 있는지 확인합니다."""
    if not text:
        return False
    # 한글 유니코드 범위: 가-힣 (완성형), ㄱ-ㅎ, ㅏ-ㅣ (자모)
    korean_pattern = re.compile(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]")
    return bool(korean_pattern.search(text))


def get_module_docstring(module_path: Path) -> str | None:
    """모듈 파일에서 docstring을 추출합니다."""
    try:
        with open(module_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        return ast.get_docstring(tree)
    except Exception:
        return None


def get_function_docstrings(module_path: Path) -> dict[str, str | None]:
    """모듈 파일에서 모든 함수의 docstring을 추출합니다."""
    docstrings = {}
    try:
        with open(module_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstrings[node.name] = ast.get_docstring(node)
    except Exception:
        pass
    return docstrings


# 테스트할 소켓 모듈 파일들
SOCKET_MODULE_FILES = [
    "app/socket/__init__.py",
    "app/socket/server.py",
    "app/socket/managers/__init__.py",
    "app/socket/managers/participant_manager.py",
    "app/socket/managers/session_manager.py",
    "app/socket/managers/action_queue_manager.py",
    "app/socket/managers/presence_manager.py",
    "app/socket/handlers/__init__.py",
    "app/socket/handlers/connection_handlers.py",
    "app/socket/handlers/session_handlers.py",
    "app/socket/handlers/action_handlers.py",
    "app/socket/handlers/ai_gm_handlers.py",
    "app/socket/handlers/heartbeat_handlers.py",
    "app/socket/utils/__init__.py",
    "app/socket/utils/validators.py",
]


class TestKoreanDocstrings:
    """한글 docstring 검사 테스트 클래스.

    Feature: socket-server-refactoring, Property 2: 한글 Docstring 포함
    """

    @pytest.fixture
    def backend_path(self) -> Path:
        """backend 디렉토리 경로를 반환합니다."""
        return Path(__file__).parent.parent

    @pytest.mark.parametrize("module_file", SOCKET_MODULE_FILES)
    def test_module_has_korean_docstring(self, backend_path: Path, module_file: str):
        """모든 모듈이 한글 docstring을 가지고 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 2: 한글 Docstring 포함
        검증 대상: 요구사항 13.1
        """
        module_path = backend_path / module_file
        assert module_path.exists(), f"모듈 파일이 존재하지 않습니다: {module_file}"

        docstring = get_module_docstring(module_path)
        assert docstring is not None, f"모듈에 docstring이 없습니다: {module_file}"
        assert contains_korean(docstring), f"모듈 docstring에 한글이 없습니다: {module_file}"

    @pytest.mark.parametrize("module_file", SOCKET_MODULE_FILES)
    def test_functions_have_korean_docstrings(self, backend_path: Path, module_file: str):
        """모든 함수가 한글 docstring을 가지고 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 2: 한글 Docstring 포함
        검증 대상: 요구사항 13.2
        """
        module_path = backend_path / module_file
        if not module_path.exists():
            pytest.skip(f"모듈 파일이 존재하지 않습니다: {module_file}")

        docstrings = get_function_docstrings(module_path)

        # __init__.py는 함수가 없을 수 있음
        if not docstrings:
            return

        for func_name, docstring in docstrings.items():
            # 프라이빗 함수(_로 시작하지만 __로 시작하지 않는)도 검사
            if func_name.startswith("__") and func_name.endswith("__"):
                continue  # 매직 메서드는 건너뜀

            assert docstring is not None, (
                f"함수에 docstring이 없습니다: {module_file}::{func_name}"
            )
            assert contains_korean(docstring), (
                f"함수 docstring에 한글이 없습니다: {module_file}::{func_name}"
            )


# ============================================================================
# Property 4: 액션 큐 상태 일관성 테스트
# 검증 대상: 요구사항 4.1, 4.3
# ============================================================================


class TestActionQueueConsistency:
    """액션 큐 상태 일관성 테스트 클래스.

    Feature: socket-server-refactoring, Property 4: 액션 큐 상태 일관성
    """

    @pytest.fixture(autouse=True)
    def reset_queue(self):
        """각 테스트 전에 액션 큐를 초기화합니다."""
        from app.socket.managers import action_queue_manager

        action_queue_manager.action_queues.clear()
        action_queue_manager.action_counter = 0
        yield
        action_queue_manager.action_queues.clear()
        action_queue_manager.action_counter = 0

    @given(
        session_id=st.integers(min_value=1, max_value=1000),
        num_actions=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100)
    def test_order_field_is_consecutive_after_add(self, session_id: int, num_actions: int):
        """액션 추가 후 order 필드가 0부터 연속적인 정수인지 확인합니다.

        Feature: socket-server-refactoring, Property 4: 액션 큐 상태 일관성
        검증 대상: 요구사항 4.1, 4.3
        """
        from app.socket.managers.action_queue_manager import add_action, get_queue

        # 액션 추가
        for i in range(num_actions):
            add_action(session_id, i + 1, f"캐릭터{i}", f"행동{i}")

        # 큐 조회
        queue = get_queue(session_id)

        # order 필드가 0부터 연속적인 정수인지 확인
        orders = [action["order"] for action in queue]
        expected_orders = list(range(len(queue)))
        assert orders == expected_orders, f"order 필드가 연속적이지 않습니다: {orders}"

    @given(
        session_id=st.integers(min_value=1, max_value=1000),
        num_actions=st.integers(min_value=1, max_value=10),
        delete_index=st.integers(min_value=0, max_value=9),
    )
    @settings(max_examples=100)
    def test_order_field_is_consecutive_after_delete(
        self, session_id: int, num_actions: int, delete_index: int
    ):
        """액션 삭제 후 order 필드가 0부터 연속적인 정수인지 확인합니다.

        Feature: socket-server-refactoring, Property 4: 액션 큐 상태 일관성
        검증 대상: 요구사항 4.1, 4.3
        """
        from app.socket.managers.action_queue_manager import (
            add_action,
            delete_action,
            get_queue,
        )

        # 액션 추가
        action_ids = []
        for i in range(num_actions):
            action = add_action(session_id, i + 1, f"캐릭터{i}", f"행동{i}")
            action_ids.append(action["id"])

        # 유효한 인덱스로 조정
        if delete_index >= len(action_ids):
            delete_index = len(action_ids) - 1

        # 액션 삭제
        delete_action(session_id, action_ids[delete_index])

        # 큐 조회
        queue = get_queue(session_id)

        # order 필드가 0부터 연속적인 정수인지 확인
        orders = [action["order"] for action in queue]
        expected_orders = list(range(len(queue)))
        assert orders == expected_orders, f"order 필드가 연속적이지 않습니다: {orders}"

    @given(
        session_id=st.integers(min_value=1, max_value=1000),
        num_actions=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=100)
    def test_order_field_is_consecutive_after_reorder(
        self, session_id: int, num_actions: int
    ):
        """액션 재정렬 후 order 필드가 0부터 연속적인 정수인지 확인합니다.

        Feature: socket-server-refactoring, Property 4: 액션 큐 상태 일관성
        검증 대상: 요구사항 4.1, 4.3
        """
        import random

        from app.socket.managers.action_queue_manager import (
            add_action,
            get_queue,
            reorder_actions,
        )

        # 액션 추가
        action_ids = []
        for i in range(num_actions):
            action = add_action(session_id, i + 1, f"캐릭터{i}", f"행동{i}")
            action_ids.append(action["id"])

        # 랜덤하게 재정렬
        shuffled_ids = action_ids.copy()
        random.shuffle(shuffled_ids)
        reorder_actions(session_id, shuffled_ids)

        # 큐 조회
        queue = get_queue(session_id)

        # order 필드가 0부터 연속적인 정수인지 확인
        orders = [action["order"] for action in queue]
        expected_orders = list(range(len(queue)))
        assert orders == expected_orders, f"order 필드가 연속적이지 않습니다: {orders}"


# ============================================================================
# Property 5: Presence 상태 일관성 테스트
# 검증 대상: 요구사항 5.1, 5.3
# ============================================================================


class TestPresenceConsistency:
    """Presence 상태 일관성 테스트 클래스.

    Feature: socket-server-refactoring, Property 5: Presence 상태 일관성
    """

    @pytest.fixture(autouse=True)
    def reset_presence(self):
        """각 테스트 전에 presence를 초기화합니다."""
        from app.socket.managers import presence_manager

        presence_manager.session_presence.clear()
        yield
        presence_manager.session_presence.clear()

    @given(
        sid=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        session_id=st.integers(min_value=1, max_value=1000),
        user_id=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=100)
    def test_presence_has_all_required_fields(
        self, sid: str, session_id: int, user_id: int
    ):
        """presence 업데이트 후 모든 필수 필드가 존재하는지 확인합니다.

        Feature: socket-server-refactoring, Property 5: Presence 상태 일관성
        검증 대상: 요구사항 5.1, 5.3
        """
        from app.socket.managers.presence_manager import (
            get_presence,
            session_presence,
            update_presence,
        )

        # presence 업데이트
        update_presence(sid, session_id, user_id)

        # presence 조회
        presence = get_presence(sid)

        # 필수 필드 확인
        assert presence is not None, "presence가 None입니다"
        assert "session_id" in presence, "session_id 필드가 없습니다"
        assert "user_id" in presence, "user_id 필드가 없습니다"
        assert "last_ts" in presence, "last_ts 필드가 없습니다"

        # 값 확인
        assert presence["session_id"] == session_id
        assert presence["user_id"] == user_id
        assert isinstance(presence["last_ts"], (int, float))

    @given(
        entries=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),  # sid
                st.integers(min_value=1, max_value=100),  # session_id
                st.integers(min_value=1, max_value=100),  # user_id
            ),
            min_size=0,
            max_size=20,
            unique_by=lambda x: x[0],  # sid는 고유해야 함
        ),
    )
    @settings(max_examples=100)
    def test_all_presences_have_required_fields(self, entries: list):
        """모든 presence 항목이 필수 필드를 가지고 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 5: Presence 상태 일관성
        검증 대상: 요구사항 5.1, 5.3
        """
        from app.socket.managers.presence_manager import (
            session_presence,
            update_presence,
        )

        # presence 업데이트
        for sid, session_id, user_id in entries:
            update_presence(sid, session_id, user_id)

        # 모든 presence 확인
        for sid, info in session_presence.items():
            assert "session_id" in info, f"session_id 필드가 없습니다: {sid}"
            assert "user_id" in info, f"user_id 필드가 없습니다: {sid}"
            assert "last_ts" in info, f"last_ts 필드가 없습니다: {sid}"

            # session_id와 user_id가 있으면 last_ts도 있어야 함
            if info.get("session_id") and info.get("user_id"):
                assert info.get("last_ts") is not None, (
                    f"session_id와 user_id가 있지만 last_ts가 없습니다: {sid}"
                )



# ============================================================================
# Property 1: Import 호환성 테스트
# 검증 대상: 요구사항 1.4, 12.1, 12.2
# ============================================================================


class TestImportCompatibility:
    """Import 호환성 테스트 클래스.

    Feature: socket-server-refactoring, Property 1: Import 호환성
    """

    def test_import_sio_from_socket_server(self):
        """기존 경로에서 sio를 import할 수 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 1: Import 호환성
        검증 대상: 요구사항 12.1
        """
        from app.socket_server import sio

        assert sio is not None
        assert hasattr(sio, "emit")
        assert hasattr(sio, "on")

    def test_import_sio_from_socket_package(self):
        """새 경로에서 sio를 import할 수 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 1: Import 호환성
        검증 대상: 요구사항 1.4
        """
        from app.socket import sio

        assert sio is not None
        assert hasattr(sio, "emit")
        assert hasattr(sio, "on")

    def test_both_imports_return_same_instance(self):
        """두 경로에서 import한 sio가 동일한 인스턴스인지 확인합니다.

        Feature: socket-server-refactoring, Property 1: Import 호환성
        검증 대상: 요구사항 1.4, 12.1
        """
        from app.socket import sio as sio_new
        from app.socket_server import sio as sio_old

        assert sio_old is sio_new

    def test_import_logger_from_socket_server(self):
        """기존 경로에서 logger를 import할 수 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 1: Import 호환성
        검증 대상: 요구사항 12.2
        """
        from app.socket_server import logger

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_import_participant_functions_from_socket_server(self):
        """기존 경로에서 참가자 관리 함수를 import할 수 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 1: Import 호환성
        검증 대상: 요구사항 12.2
        """
        from app.socket_server import (
            add_participant,
            get_participant_count,
            get_participants,
            remove_participant,
        )

        assert callable(add_participant)
        assert callable(remove_participant)
        assert callable(get_participant_count)
        assert callable(get_participants)

    def test_import_session_functions_from_socket_server(self):
        """기존 경로에서 세션 관리 함수를 import할 수 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 1: Import 호환성
        검증 대상: 요구사항 12.2
        """
        from app.socket_server import (
            check_and_deactivate_session,
            maybe_end_session_if_host,
            verify_host_authorization,
        )

        assert callable(check_and_deactivate_session)
        assert callable(verify_host_authorization)
        assert callable(maybe_end_session_if_host)

    def test_import_session_presence_from_socket_server(self):
        """기존 경로에서 session_presence를 import할 수 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 1: Import 호환성
        검증 대상: 요구사항 12.2
        """
        from app.socket_server import session_presence

        assert isinstance(session_presence, dict)

    def test_import_action_queues_from_socket_server(self):
        """기존 경로에서 action_queues를 import할 수 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 1: Import 호환성
        검증 대상: 요구사항 12.2
        """
        from app.socket_server import action_queues

        assert isinstance(action_queues, dict)


# ============================================================================
# Property 3: 이벤트 핸들러 등록 테스트
# 검증 대상: 요구사항 12.3
# ============================================================================


class TestEventHandlerRegistration:
    """이벤트 핸들러 등록 테스트 클래스.

    Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
    """

    def test_connect_handler_registered(self):
        """connect 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        # Socket.io 서버의 이벤트 핸들러 확인
        assert "connect" in sio.handlers.get("/", {})

    def test_disconnect_handler_registered(self):
        """disconnect 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "disconnect" in sio.handlers.get("/", {})

    def test_chat_message_handler_registered(self):
        """chat_message 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "chat_message" in sio.handlers.get("/", {})

    def test_join_session_handler_registered(self):
        """join_session 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "join_session" in sio.handlers.get("/", {})

    def test_leave_session_handler_registered(self):
        """leave_session 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "leave_session" in sio.handlers.get("/", {})

    def test_submit_action_handler_registered(self):
        """submit_action 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "submit_action" in sio.handlers.get("/", {})

    def test_get_queue_handler_registered(self):
        """get_queue 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "get_queue" in sio.handlers.get("/", {})

    def test_commit_actions_handler_registered(self):
        """commit_actions 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "commit_actions" in sio.handlers.get("/", {})

    def test_submit_player_action_handler_registered(self):
        """submit_player_action 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "submit_player_action" in sio.handlers.get("/", {})

    def test_roll_dice_handler_registered(self):
        """roll_dice 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "roll_dice" in sio.handlers.get("/", {})

    def test_session_heartbeat_handler_registered(self):
        """session_heartbeat 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        assert "session_heartbeat" in sio.handlers.get("/", {})

    def test_all_expected_handlers_registered(self):
        """모든 예상 이벤트 핸들러가 등록되어 있는지 확인합니다.

        Feature: socket-server-refactoring, Property 3: 이벤트 핸들러 등록
        검증 대상: 요구사항 12.3
        """
        from app.socket import sio

        expected_handlers = [
            "connect",
            "disconnect",
            "chat_message",
            "join_session",
            "leave_session",
            "submit_action",
            "get_queue",
            "edit_action",
            "reorder_actions",
            "delete_action",
            "commit_actions",
            "submit_player_action",
            "roll_dice",
            "next_judgment",
            "request_narrative_stream",
            "trigger_story_generation",
            "session_heartbeat",
        ]

        registered_handlers = sio.handlers.get("/", {}).keys()

        for handler in expected_handlers:
            assert handler in registered_handlers, f"핸들러가 등록되지 않았습니다: {handler}"
