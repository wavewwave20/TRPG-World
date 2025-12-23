"""
프롬프트 로더 유틸리티

마크다운 파일에서 프롬프트를 로드하고 LangChain SystemMessage로 변환합니다.
"""

from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.prompts import SystemMessagePromptTemplate

# 기본 프롬프트 디렉토리
DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(filename: str) -> SystemMessage:
    """
    프롬프트 파일을 로드하여 SystemMessage로 반환합니다.

    Args:
        filename: 프롬프트 파일명 (예: "judgment_prompt.md")

    Returns:
        SystemMessage: LangChain SystemMessage 객체

    Raises:
        FileNotFoundError: 프롬프트 파일을 찾을 수 없을 때
    """
    if not filename.endswith(".md"):
        filename = f"{filename}.md"

    file_path = DEFAULT_PROMPTS_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    return SystemMessage(content=content)


class PromptLoader:
    """
    프롬프트 마크다운 파일을 로드하고 SystemMessage로 변환하는 유틸리티

    사용 예시:
        loader = PromptLoader("judgment_prompt.md")
        system_message = loader.get_system_message()

        # 또는 변수 치환이 필요한 경우
        template = loader.template
        formatted = template.format(world_context="...")
    """

    def __init__(
        self,
        prompt_filename: str,
        prompts_dir: Path | None = None,
        override_content: str | None = None,
        extend_content: str | None = None,
    ):
        """
        프롬프트 로더를 초기화합니다.

        Args:
            prompt_filename: 프롬프트 파일명 (.md 확장자 포함/제외 모두 가능)
            prompts_dir: 프롬프트 디렉토리 경로 (기본값: app/prompts)
            override_content: 파일 대신 사용할 커스텀 프롬프트
            extend_content: 파일 내용에 추가할 프롬프트
        """
        self.prompt_filename = prompt_filename if prompt_filename.endswith(".md") else f"{prompt_filename}.md"
        self.prompts_dir = prompts_dir or Path(__file__).parent.parent / "prompts"

        # 프롬프트 내용 로드
        if override_content:
            prompt_content = override_content
        else:
            prompt_content = self._load_prompt_file()

        # 추가 내용이 있으면 붙이기
        if extend_content:
            prompt_content += f"\n\n{extend_content}"

        self.prompt_content = prompt_content
        self.system_message = SystemMessage(content=prompt_content)

    def _load_prompt_file(self) -> str:
        """
        프롬프트 파일을 로드합니다.

        Returns:
            str: 프롬프트 내용

        Raises:
            FileNotFoundError: 프롬프트 파일을 찾을 수 없을 때
            RuntimeError: 파일 로드 중 오류 발생 시
        """
        try:
            file_path = self.prompts_dir / self.prompt_filename

            if not file_path.exists():
                raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {file_path}")

            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            return content

        except FileNotFoundError:
            raise
        except Exception as e:
            raise RuntimeError(f"프롬프트 파일 로드 실패 ({self.prompt_filename}): {e}") from e

    def get_system_message(self) -> SystemMessage:
        """
        SystemMessage 객체를 반환합니다.

        Returns:
            SystemMessage: LangChain SystemMessage 객체
        """
        return self.system_message

    @property
    def template(self) -> SystemMessagePromptTemplate:
        """
        변수 치환이 가능한 프롬프트 템플릿

        Returns:
            SystemMessagePromptTemplate: 변수 치환 가능한 템플릿
        """
        return SystemMessagePromptTemplate.from_template(self.prompt_content)

    @property
    def content(self) -> str:
        """
        프롬프트 원본 내용

        Returns:
            str: 프롬프트 텍스트
        """
        return self.prompt_content
