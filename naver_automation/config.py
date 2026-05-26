import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# =============================================
# .env 파일 로드
# =============================================
# Path(__file__).parent : 이 파일(config.py)이 있는 디렉토리를 기준으로 .env 경로를 잡습니다.
# → main.py, publisher.py 등 어느 파일에서 import해도 항상 올바른 .env를 찾습니다.
# override=True : 시스템 환경 변수보다 .env 파일의 값을 우선 적용합니다.
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)


class Config:
    """
    애플리케이션 전역에서 사용할 설정 값을 관리하는 클래스입니다.
    .env 파일의 환경 변수를 읽어 클래스 속성으로 바인딩합니다.

    사용 예:
        from config import Config
        Config.validate()           # 시작 시 필수 값 검증
        naver_id = Config.NAVER_ID  # 어디서든 값 참조
    """

    # --- 네이버 로그인 정보 ---
    NAVER_ID: str = os.getenv("NAVER_ID")
    NAVER_PW: str = os.getenv("NAVER_PW")

    # --- Google AI Studio ---
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")

    @classmethod
    def validate(cls) -> bool:
        """
        프로그램 실행 전, 필수 인증 정보가 모두 로드되었는지 검증합니다.

        반환값:
            True  - 모든 필수 변수가 존재할 때
            False - 하나라도 누락되었을 때 (오류 메시지 출력 후 반환)
        """
        missing_vars = []

        if not cls.NAVER_ID:
            missing_vars.append("NAVER_ID")
        if not cls.NAVER_PW:
            missing_vars.append("NAVER_PW")
        if not cls.GOOGLE_API_KEY:
            missing_vars.append("GOOGLE_API_KEY")

        if missing_vars:
            print(f"[검증 오류] .env 파일에 다음 필수 변수가 누락되었습니다: {', '.join(missing_vars)}")
            print(f"[검증 오류] .env 파일 위치: {_ENV_PATH}")
            print("프로그램을 종료합니다. .env 파일을 다시 확인해 주세요.")
            return False

        print("[검증 성공] 모든 환경 변수가 정상적으로 로드되었습니다.")
        return True

    @classmethod
    def validate_or_exit(cls) -> None:
        """
        검증 실패 시 프로그램을 즉시 종료합니다.
        main.py 시작 시점에 호출하면 잘못된 설정으로 실행되는 상황을 방지합니다.
        """
        if not cls.validate():
            sys.exit(1)

    @classmethod
    def display(cls) -> None:
        """
        현재 로드된 설정 값을 안전하게 출력합니다.
        비밀번호와 API 키는 앞 4자리만 보이고 나머지는 마스킹(*) 처리합니다.

        사용 목적: 디버깅 시 설정이 올바르게 로드되었는지 육안으로 확인
        """
        def mask(value: str, visible: int = 4) -> str:
            """앞 visible 자리만 보이고 나머지는 * 처리"""
            if not value:
                return "(없음)"
            return value[:visible] + "*" * (len(value) - visible)

        print("=" * 45)
        print("  현재 로드된 Config 값 (마스킹 처리)")
        print("=" * 45)
        print(f"  NAVER_ID       : {cls.NAVER_ID or '(없음)'}")
        print(f"  NAVER_PW       : {mask(cls.NAVER_PW)}")
        print(f"  GOOGLE_API_KEY : {mask(cls.GOOGLE_API_KEY)}")
        print(f"  .env 경로      : {_ENV_PATH}")
        print("=" * 45)


# =============================================
# 모듈 독립 실행 테스트
# python config.py 로 직접 실행 시 동작
# =============================================
if __name__ == "__main__":
    print("Config 모듈 검증 테스트를 시작합니다...\n")
    Config.display()
    print()
    Config.validate()
