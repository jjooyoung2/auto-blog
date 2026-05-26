import time
from pathlib import Path
from google import genai
from google.genai import types
from config import Config

# =============================================
# 이미지 저장 디렉토리 설정
# =============================================
# Path(__file__).parent : 이 파일이 있는 디렉토리 기준으로 경로를 잡습니다.
# → main.py 등 어느 파일에서 import해도 항상 올바른 폴더를 찾습니다.
_OUTPUT_DIR = Path(__file__).parent / "generated_images"

# =============================================
# 사용 가능한 이미지 생성 모델 (Google AI Studio)
# =============================================
# 아래 모델들은 모두 유료 플랜(Pay-as-you-go) 필요합니다.
# Google AI Studio → 결제 수단 등록 후 사용 가능합니다.
# https://aistudio.google.com/plan_information
#
# 모델명                             호출 방식            특징
# ----------------------------       ----------------     ------------------
# nano-banana-pro-preview            generate_content     나노바나나 (고품질)
# gemini-3-pro-image-preview         generate_content     Gemini 3 Pro 이미지
# gemini-3.1-flash-image-preview     generate_content     빠른 생성, 경량
# gemini-2.5-flash-image             generate_content     저비용 옵션
# imagen-4.0-generate-001            generate_images      Imagen 4 표준
# imagen-4.0-ultra-generate-001      generate_images      Imagen 4 최고품질
# imagen-4.0-fast-generate-001       generate_images      Imagen 4 고속
_DEFAULT_MODEL = "nano-banana-pro-preview"


class NanoBananaHandler:
    """
    구글 AI 스튜디오의 나노바나나(nano-banana-pro-preview) 모델을 사용하여
    블로그 포스팅용 고품질 이미지를 자동 생성하고 관리하는 클래스입니다.

    [중요] 나노바나나는 generate_content + response_modalities=["IMAGE"] 방식으로 호출합니다.
           generate_images() 방식은 Imagen 계열 전용이므로 혼동하지 마세요.

    동작 흐름:
        1. generate_image_if_missing() 호출
        2. 로컬 이미지 리스트가 비어 있거나 실제 파일이 없으면 _generate() 호출
        3. 생성된 이미지를 generated_images/ 폴더에 저장 후 절대 경로 리스트 반환

    [사전 조건] Google AI Studio 유료 플랜(Pay-as-you-go) 등록 필요
               https://aistudio.google.com/plan_information
    """

    def __init__(self, model: str = _DEFAULT_MODEL):
        """
        매개변수:
            model (str): 사용할 이미지 생성 모델명. 기본값은 나노바나나입니다.
                         파일 상단 모델 목록 참고.
        """
        # config.py에서 검증 완료된 구글 API 키로 GenAI 클라이언트를 초기화합니다.
        self.client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        self.model = model

        # 이미지 저장 폴더가 없으면 자동 생성합니다. (exist_ok=True → 이미 있어도 오류 없음)
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[초기화] 모델: {self.model}")
        print(f"[초기화] 이미지 저장 디렉토리 확인 완료 -> {_OUTPUT_DIR}")

    def generate_image_if_missing(self, local_image_paths: list, prompt: str) -> list:
        """
        로컬 이미지 리스트를 우선 검사하고, 사용 불가능한 경우 AI로 이미지를 생성합니다.

        매개변수:
            local_image_paths (list): 사용자가 준비한 로컬 이미지 경로 리스트
            prompt (str): AI 이미지 생성 시 전달할 영어 프롬프트

        반환값:
            list: 최종적으로 사용 가능한 이미지들의 절대 경로 리스트
                  로컬 이미지가 유효하면 그대로 반환, 없으면 AI 생성 경로 반환
        """
        # 1. 로컬 이미지 유효성 검사
        # 경로가 리스트에 있어도 실제 파일이 디스크에 없으면 사용할 수 없으므로 걸러냅니다.
        if local_image_paths:
            valid_paths = [p for p in local_image_paths if Path(p).is_file()]

            if valid_paths:
                print(f"[이미지 프로세서] 유효한 로컬 이미지 {len(valid_paths)}개 확인됨. AI 생성을 생략합니다.")
                return [str(Path(p).resolve()) for p in valid_paths]

            skipped = len(local_image_paths) - len(valid_paths)
            print(f"[이미지 프로세서] 경고: 리스트에 {skipped}개 경로가 있었으나 실제 파일이 존재하지 않습니다.")

        print("[이미지 프로세서] 활용 가능한 이미지 소스가 없습니다.")
        print("[이미지 프로세서] 나노바나나 엔진 원격 호출을 시작합니다.")

        # 2. AI 이미지 생성으로 전환
        return self._generate(prompt)

    def _generate(self, prompt: str) -> list:
        """
        나노바나나(generate_content) API를 호출하여 이미지를 생성하고 로컬에 저장합니다.

        [나노바나나 호출 방식 설명]
        나노바나나는 Gemini 계열 멀티모달 모델입니다.
        response_modalities=["IMAGE"] 를 설정하면 텍스트 프롬프트에서 이미지를 생성합니다.
        응답은 response.candidates[0].content.parts 배열에서 꺼내야 합니다.
        part.inline_data.data 가 이미지 바이트 데이터입니다.

        매개변수:
            prompt (str): 이미지 생성에 전달할 영어 프롬프트

        반환값:
            list: 저장된 이미지 파일들의 절대 경로 리스트 (실패 시 빈 리스트)
        """
        print(f"[매개 프롬프트] {prompt}")

        try:
            # 나노바나나(Gemini 계열 이미지 모델) 호출
            # response_modalities=["IMAGE"] : 이미지 출력 모드 활성화
            # "TEXT"를 함께 넣으면 이미지와 함께 설명 텍스트도 응답됩니다.
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"]
                ),
            )

            generated_paths = []

            # 응답 파트를 순회하며 이미지 데이터만 추출하여 저장합니다.
            for i, part in enumerate(response.candidates[0].content.parts):
                # inline_data가 None이면 텍스트 파트이므로 건너뜁니다.
                if part.inline_data is None:
                    continue

                # MIME 타입으로 확장자를 결정합니다. (image/jpeg → jpg, image/png → png)
                ext = part.inline_data.mime_type.split("/")[-1]
                file_name = f"nanobanana_{int(time.time())}_{i}.{ext}"
                full_path = _OUTPUT_DIR / file_name

                # 바이트 데이터를 바이너리 모드로 저장
                with open(full_path, "wb") as file_stream:
                    file_stream.write(part.inline_data.data)

                print(f"[성공] AI 이미지 저장 완료 -> {full_path}")
                generated_paths.append(str(full_path.resolve()))

            if not generated_paths:
                print("[경고] 응답에서 이미지 데이터를 찾지 못했습니다.")

            return generated_paths

        except Exception as error:
            print(f"[오류] 나노바나나 API 통신 또는 파일 입출력 중 예외 발생: {error}")
            return []


# =============================================
# 모듈 독립 실행 테스트
# python image_generator.py 로 직접 실행 시 동작
# =============================================
if __name__ == "__main__":
    print("=== [모듈 테스트] image_generator.py 단독 검증 ===\n")

    if Config.validate():
        handler = NanoBananaHandler()
        print()

        sample_prompt = (
            "A premium tech product shot of a mechanical keyboard on a wooden table, "
            "volumetric lighting, macro photography, 4k resolution"
        )

        test_result = handler.generate_image_if_missing([], sample_prompt)

        print()
        print(f"[테스트 완료] 최종 반환 경로 리스트 ({len(test_result)}개):")
        for path in test_result:
            print(f"  - {path}")
