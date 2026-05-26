from config import Config
from publisher import NaverBlogDraftPublisher

# =============================================
# 포스팅 세팅 구역 (여기만 수정하면 됩니다)
# =============================================

# --- 이미지 생성 프롬프트 설정 ---
# use_ai_image : True 이면 image_generator.py로 AI 이미지를 생성합니다.
#                False 이면 local_image_paths의 파일을 사용합니다.
# image_prompt : 나노바나나 AI에 전달할 영어 프롬프트
# content_topic: 로그 출력용 키워드 (실제 본문 생성 AI 연동 시 활용 예정)
TARGET_PROMPT_SETTING = {
    "use_ai_image": True,
    "image_prompt": "A modern workspace interior, photorealistic daylight, sleek technology, 4k",
    "content_topic": "자동화 프로그램의 가치",
}

# --- 로컬 이미지 경로 (use_ai_image=False 시 사용) ---
# 예: LOCAL_IMAGES = ["C:\\Users\\user\\Desktop\\image1.jpg"]
LOCAL_IMAGES = []

# --- 블로그 포스팅 원고 ---
POST_TITLE = "파이썬 웹 자동화가 가져다주는 업무 생산성의 대전환"

POST_BODY = (
    "단순하고 반복적인 웹 데이터 입력과 업로드 작업은 인간의 집중력을 저하시킵니다.\n\n"
    "셀레니움과 파이썬을 조합한 자동화 스크립트를 현업에 적용하면, 클릭 몇 번만으로 "
    "정확하고 일관된 데이터를 타겟 플랫폼에 즉시 바인딩할 수 있습니다. "
    "이를 통해 확보한 시간은 온전히 고부가가치 기획 업무에 투자할 수 있게 됩니다."
)


# =============================================
# 메인 실행 엔트리포인트
# =============================================

def main():
    print("=======================================================")
    print("  네이버 블로그 자동화 로봇: 프롬프트 세팅 및 임시저장 가동")
    print("=======================================================\n")

    # 1. 환경 변수 검증: .env 누락 시 즉시 종료
    Config.validate_or_exit()

    # 2. 세팅값 확인 로그
    print(f"[세팅] 콘텐츠 키워드  : {TARGET_PROMPT_SETTING['content_topic']}")
    print(f"[세팅] AI 이미지 사용  : {TARGET_PROMPT_SETTING['use_ai_image']}")
    print(f"[세팅] 이미지 프롬프트 : {TARGET_PROMPT_SETTING['image_prompt']}\n")

    # 3. 이미지 준비
    # TODO: TARGET_PROMPT_SETTING["use_ai_image"]=True 시 아래 주석을 활성화하세요.
    # from image_generator import NanoBananaHandler
    # images = NanoBananaHandler().generate_image_if_missing(LOCAL_IMAGES, TARGET_PROMPT_SETTING["image_prompt"])

    # 4. 자동화 봇 인스턴스화 및 실행
    bot = NaverBlogDraftPublisher()
    try:
        bot.init_driver()
        bot.naver_login()

        success = bot.write_and_save_draft(
            title=POST_TITLE,
            text_content=POST_BODY,
        )

        # 5. 최종 결과 출력
        if success:
            print("\n[완료] 임시저장 성공! 네이버 블로그 임시저장 글 목록에서 확인하세요.")
        else:
            print("\n[주의] 저장 완료 신호를 감지하지 못했습니다. 블로그에서 직접 확인하세요.")

        print("[알림] 모든 뼈대 기능(로그인 → 본문 작성 → 임시저장)이 정상 종료되었습니다.")

    except Exception as runtime_error:
        print(f"\n[치명적 예외] 메인 컨트롤러 가동 실패: {runtime_error}")

    finally:
        # 성공/실패/예외 여부와 관계없이 브라우저는 반드시 종료
        bot.quit_driver()


if __name__ == "__main__":
    main()
