import sys

import os

import traceback

import base64

import glob

import json

import logging

import multiprocessing

import random

import re

import subprocess

import threading

import time

import unicodedata

from concurrent.futures import ThreadPoolExecutor, as_completed

import uuid



import hashlib

import hmac

import requests



import pyperclip

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from google import genai

from google.genai import types

from selenium import webdriver

from selenium.webdriver.chrome.options import Options

from selenium.webdriver.chrome.service import Service

from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.common.by import By

from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.support.ui import WebDriverWait

from webdriver_manager.chrome import ChromeDriverManager



# ── 경로 설정 (일반 실행 / PyInstaller exe 양쪽 대응) ─────────────────

if getattr(sys, "frozen", False):

    BASE_DIR    = os.path.dirname(sys.executable)

    _BUNDLE_DIR = sys._MEIPASS

else:

    BASE_DIR    = os.path.dirname(os.path.abspath(__file__))

    _BUNDLE_DIR = BASE_DIR



try:

    from dotenv import load_dotenv

except ImportError:

    load_dotenv = None



_DOTENV_PATH = os.path.join(BASE_DIR, ".env")



def refresh_env_credentials() -> None:

    """.env 를 os.environ 에 다시 반영하고 모듈 전역 자격 증명을 갱신합니다."""

    global ENV_NAVER_ID, ENV_NAVER_PW, ENV_CLINIC_NAME

    if load_dotenv is not None:

        try:

            load_dotenv(_DOTENV_PATH, override=True)

        except Exception:

            pass

    ENV_NAVER_ID = (os.environ.get("NAVER_ID") or "").strip()

    ENV_NAVER_PW = (os.environ.get("NAVER_PW") or "").strip()

    ENV_CLINIC_NAME = (

        (os.environ.get("CLINIC_NAME") or os.environ.get("BLOG_CLINIC_NAME") or "").strip()

    )



refresh_env_credentials()



def _account_settings_payload() -> dict:

    """.env 파일에서 읽은 계정 UI용 값(로컬 전용: 비밀번호 평문 포함)."""

    try:

        from dotenv import dotenv_values

        vals = dotenv_values(_DOTENV_PATH) or {}

    except Exception:

        vals = {}

    if not isinstance(vals, dict):

        vals = {}

    naver_id = (vals.get("NAVER_ID") or "").strip()

    clinic = (vals.get("CLINIC_NAME") or vals.get("BLOG_CLINIC_NAME") or "").strip()

    pw = (vals.get("NAVER_PW") or "").strip()

    return {

        "naver_id": naver_id,

        "clinic_name": clinic,

        "naver_pw": pw,

        "naver_pw_configured": bool(pw),

        "has_naver_creds": bool(naver_id and pw),

        "default_clinic_name": clinic,

    }



app = Flask(

    __name__,

    template_folder=os.path.join(_BUNDLE_DIR, "templates"),

    static_folder=os.path.join(_BUNDLE_DIR, "static"),

)



SRC_DIR = os.path.join(BASE_DIR, "src")

TMP_DIR = os.path.join(BASE_DIR, "tmp")



class _NoStatusLog(logging.Filter):

    def filter(self, record):

        return "GET /status" not in record.getMessage()



logging.getLogger("werkzeug").addFilter(_NoStatusLog())



# Gemini — 소스에 키를 넣지 마세요. .env 의 GEMINI_API_KEY(또는 GOOGLE_API_KEY)만 사용합니다.

API_KEY = (

    os.environ.get("GEMINI_API_KEY", "").strip()

    or os.environ.get("GOOGLE_API_KEY", "").strip()

    or os.environ.get("GENAI_API_KEY", "").strip()

)

if not API_KEY:

    raise RuntimeError(

        "Gemini API 키가 설정되지 않았습니다. 프로젝트 루트 .env 파일에 GEMINI_API_KEY=발급받은키 를 넣고 서버를 다시 실행하세요."

    )



MODEL = "gemini-2.5-flash-lite"

MULTIMODAL_MODEL = "gemini-2.5-flash"

MULTIMODAL_FALLBACK = "gemini-2.5-flash-lite"

client = genai.Client(api_key=API_KEY)



IMG_MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg",

            "png": "image/png", "gif": "image/gif", "webp": "image/webp"}



# ?? 카드?스 모드 ?스??지???????????????????????????????????????

COMMON_INSTRUCTION = """실제 원장님이 환자에게 설명하듯 친근하게 대화하는 구어체로 블로그 컨텐츠를 제작해줘

친근한 구어체 예시 -> ~요, ~죠, ~거든요, ~해요, ~꼭 기억해 주세요. 등

이때 모든 문단은 예시와 같은 스타일이 적용되어야 하고, 구조는 아래와 같이 진행되어야 해

제목 : (치과명 포함 SEO 최적화 제목)

0. 도입부 -> 환자 질문 X
1. 소제목 -> 괄호 숫자 형태 불릿 사용 필수
2. 소제목 -> 괄호 숫자 형태 불릿 사용 필수
3. 소제목 -> 괄호 숫자 형태 불릿 사용 필수
4. 소제목 -> 괄호 숫자 형태 불릿 사용 필수
5. 의료진의 현실적인 조언

[강조사항]
- 아래 예시 스타일 그대로 작성

--

[예시]

제목 : 답십리동치과 잇몸 출혈 방치하면 어떤 문제가?

양치를 하다가 피가 나는 경험, 한 번쯤은 있으셨을 겁니다.

많은 분들이 이럴 때 "칫솔이 세게 닿았나 보다" 정도로 생각하고 대수롭지 않게 넘기곤 하시는데요.

하지만 잇몸에서 반복적으로 피가 나는 경우라면 단순한 문제가 아닐 수 있습니다.

잇몸 출혈은 생각보다 흔하게 나타나는 증상이지만, 사실은 치주질환의 초기 신호일 가능성도 있기 때문입니다.

그래서 오늘은 답십리동치과에서 잇몸 출혈을 방치하면 어떤 문제가 생길 수 있는지 차근차근 설명해 드리려고 합니다.

평소 양치할 때 피가 나는 경험이 있다면 오늘 내용 끝까지 참고해 보시면 좋겠습니다.

1. 잇몸에서 피가 난다면 어떤 신호일까요?

먼저 잇몸 출혈이 왜 생기는지부터 이야기해 볼게요.

양치할 때 피가 난다면 대부분 잇몸에 염증이 시작됐다는 신호일 가능성이 있습니다.

치아 표면에 세균과 음식물 찌꺼기가 쌓이면 치태라는 것이 형성되고, 이 치태가 잇몸을 자극하면서 염증을 일으킬 수 있습니다.

이 염증이 바로 치주질환의 시작 단계라고 보시면 이해가 쉬운데요.

잇몸 출혈이 나타나는 대표적인 상황을 정리해 보면 다음과 같습니다.

(1) 양치할 때 잇몸에서 피가 나는 경우

(2) 잇몸이 붓거나 붉게 변하는 경우

(3) 칫솔질을 하면 잇몸이 쉽게 자극되는 경우

이런 증상이 반복된다면 단순한 잇몸 자극이 아니라 잇몸 염증이 진행되고 있다는 신호일 수 있습니다.

2. 치주질환은 통증 없이 진행되는 경우가 많습니다

치주질환의 특징 중 하나는 초기에는 통증이 거의 없다는 점입니다.

그래서 많은 분들이 "아프지 않으니까 괜찮겠지"라고 생각하고 그냥 지나치는 경우가 많습니다.

하지만 치주질환은 조용히 진행되면서 잇몸과 뼈를 조금씩 손상시키는 질환입니다.

겉으로는 큰 변화가 없어 보여도 내부에서는 염증이 서서히 진행되고 있을 수 있습니다.

치주질환이 발견이 늦어지는 이유를 정리해 보면 다음과 같습니다.

(1) 초기에는 통증이 거의 없는 경우가 많음

(2) 잇몸 출혈 정도로만 나타나는 경우가 많음

(3) 증상이 나타났을 때 이미 진행된 경우도 있음

그러다 보니 증상이 악화되었을 때 답십리동치과를 찾는 분들도 계세요.

따라서 혹시라도 잇몸 출혈이 반복적으로 나타나고 있는 상황이라면?

단순한 증상으로 넘기기보다 초기 신호로 인식하는 것이 중요합니다.

3. 잇몸 질환이 진행되면 어떤 일이 생길까요?

치주질환이 진행되면 잇몸에만 문제가 생기는 것이 아닙니다.

잇몸 아래에 있는 치아를 지탱하는 뼈까지 영향을 받을 수 있어요.

처음에는 잇몸 염증으로 시작하지만 치료하지 않고 방치하게 되면,

점점 잇몸뼈가 약해지고 치아의 지지력이 떨어지게 됩니다.

이 과정이 계속 진행되면 치아가 흔들리거나 결국 발치로 이어질 수도 있어요.

치주질환이 진행될 때 나타날 수 있는 변화를 정리해 보면 다음과 같습니다.

(1) 잇몸이 붓고 쉽게 피가 남

(2) 잇몸뼈가 점차 약해짐

(3) 치아가 흔들리거나 빠질 수 있음

그래서 흔히 "풍치 때문에 이를 뽑았다"는 이야기가 생기는 것입니다.

충치가 없어도 치아를 잃게 되는 이유가 바로 여기에 있습니다.

4. 스케일링이 중요한 이유

잇몸 질환을 예방하는 가장 기본적인 방법 중 하나가 바로 정기적인 스케일링입니다.

치아 표면에 쌓인 치태는 시간이 지나면서 단단하게 굳어 치석이 되는데요.

치석은 칫솔질만으로는 제거하기 어렵기 때문에 답십리동치과와 같은 의료 기관을 통해 제거해야 합니다.

이때 스케일링이 중요한 이유를 정리해 보면 다음과 같습니다.

(1) 치석은 칫솔질만으로 제거하기 어려움

(2) 치석이 잇몸 염증의 원인이 될 수 있음

(3) 정기적인 스케일링이 치주질환 예방에 도움

그래서 잇몸 건강을 위해서는 정기적으로 스케일링을 받는 습관이 중요하다는 사실을 꼭 기억해 주세요.

잇몸 출혈을 방치하면 다른 문제로 이어질 수 있습니다!

양치할 때 피가 나는 증상은 생각보다 많은 분들이 경험합니다.

그래서 가볍게 넘기는 경우도 많지만, 반복적으로 나타난다면 잇몸 건강 상태를 확인해 보는 것이 좋아요.

특히 잇몸 질환은 초기에는 통증이 거의 없기 때문에 스스로 판단하기 어려운 경우가 많습니다.

그래서 정기적인 검진과 스케일링을 통해 잇몸 상태를 확인하는 것이 도움이 될 수 있습니다.

만약 양치할 때 잇몸 출혈이 계속된다면?

오늘 정리한 내용 참고하셔서 치과를 통해 잇몸 건강을 한 번 점검해 보시길 바랍니다.

지금까지 긴 글 읽어주셔서 감사합니다.

--

⚠️ 위 예시는 스타일 참고용입니다. 키워드/카드뉴스에 맞게 소제목과 본문을 새로 채워주세요.
⚠️ #, ##, ###, **, __, *, `, --- 등 마크다운 기호는 절대 사용하지 마세요. 순수 텍스트로만 작성하세요.
"""


# 카드뉴스 모드: 공통 지시 + 카드뉴스 전용 추가
CARDNEWS_SYSTEM_INSTRUCTION = COMMON_INSTRUCTION + """
[카드뉴스 구성 추가 지시]
- 소제목 1~4는 첨부된 카드뉴스 이미지 내용을 분석해서 뽑아줘
- 도입부(첫 소제목 "1."이 시작되기 전 문단) 끝에는 이미지 파일명 목록의 첫 번째 파일을 반드시 한 줄 [이미지: 파일명]으로 넣을 것
- 아래 사용자 메시지에 적힌 모든 파일명을 본문에서 빠짐없이 각각 한 번씩 [이미지: 파일명] 형식으로 사용할 것"""

# 키워드 입력 모드: 공통 지시 + 키워드 전용 추가
KEYWORD_SYSTEM_INSTRUCTION = COMMON_INSTRUCTION + """
[키워드 구성 추가 지시]
- 소제목 1~4는 아래 입력된 키워드를 주제로 구성해줘"""





# ?? 치과 ?스 ?일 ?퍼 ??????????????????????????????????????????



def read_reference_texts(clinic_name: str) -> str:

    """src/{clinic_name}/text/ ?서 ?덤 txt ?일 최? 5개? ?어 반환"""

    text_dir = os.path.join(SRC_DIR, clinic_name, "text")

    if not os.path.isdir(text_dir):

        return ""

    txt_files = glob.glob(os.path.join(text_dir, "*.txt"))

    if not txt_files:

        return ""

    selected = random.sample(txt_files, min(5, len(txt_files)))

    parts = []

    for fpath in selected:

        try:

            with open(fpath, "r", encoding="utf-8") as f:

                content = f.read().strip()[:1200]  # ?일??최? 1200??

            if content:

                parts.append(f"[참고글: {os.path.basename(fpath)}]\n{content}")

        except Exception:

            pass

    return "\n\n".join(parts)





def get_clinic_images(clinic_name: str) -> list:

    """src/{clinic_name}/img/ ????지 ?일?목록 반환"""

    img_dir = os.path.join(SRC_DIR, clinic_name, "img")

    if not os.path.isdir(img_dir):

        return []

    exts = ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp",

            "*.JPG", "*.JPEG", "*.PNG", "*.GIF", "*.WEBP"]

    files = []

    for ext in exts:

        files.extend(glob.glob(os.path.join(img_dir, ext)))

    return [os.path.basename(f) for f in files]





# ?? Gemini 본문 ?성 ??????????????????????????????????????????????



def _load_image_part(img_path: str, filename: str) -> list:

    """??지 ?일??멀?모??Part 리스?로 변??(??지 바이??+ ?일??스??"""

    ext = filename.lower().rsplit(".", 1)[-1]

    mime_type = IMG_MIME.get(ext, "image/jpeg")

    with open(img_path, "rb") as f:

        img_bytes = f.read()

    return [

        types.Part.from_bytes(data=img_bytes, mime_type=mime_type),

        types.Part.from_text(text=f"(????지???일? {filename})"),

    ]





def _parse_target_char_count(raw) -> int | None:

    """요청 JSON에서 목표 본문 글자 수. 없음/비유효 시 None, 아니면 안전 범위로 클램프."""

    if raw is None:

        return None

    try:

        n = int(raw)

    except (TypeError, ValueError):

        return None

    if n <= 0:

        return None

    return max(300, min(n, 12000))



def _blog_body_metric_chars(body: str) -> int:

    """프론트 표시와 동일: [이미지: …] 단독 줄 제외 후 공백 제외 글자 수."""

    if not (body or "").strip():

        return 0

    lines = (body or "").replace("\r\n", "\n").split("\n")

    kept = []

    for ln in lines:

        if re.match(r"^\s*\[이미지:\s*[^\]]+\]\s*$", ln):

            continue

        kept.append(ln)

    core = "\n".join(kept)

    return len(re.sub(r"\s+", "", core))



def _expand_blog_body_for_length(

    title: str,

    body: str,

    target: int,

    metric_before: int,

    system_instr: str,

    use_model: str,

    image_prefix_parts: list | None,

) -> tuple[str, str]:

    """1차 본문이 목표 대비 지나치게 짧을 때 한 번 더 생성해 분량을 맞춤."""

    shortage = max(0, target - metric_before)

    user_txt = (

        "[분량 보강]\n"

        "아래는 방금 작성한 블로그 초안(제목·본문)입니다.\n"

        f"'제목:' 줄과 [이미지: 파일명] 형태의 줄은 수정·삭제하지 말고 그대로 유지하세요.\n"

        f"공백을 제외한 본문 글자 수(이미지 전용 줄 제외)가 현재 약 {metric_before}자이고, 목표는 약 {target}자입니다.\n"

        f"부족한 약 {shortage}자 이상을 각 소제목 아래 설명을 구체화하거나 Q&A·주의사항으로 자연스럽게 채워,"

        f" 목표에 가깝게(가능하면 {int(target * 0.93)}자 이상) 맞춰 주세요. 허위 진료 사례·허위 수치는 쓰지 마세요.\n"

        "응답은 반드시 첫 줄에 '제목: …' 한 줄을 두고, 한 줄 띄운 뒤 전체 본문을 이어서 출력하세요.\n\n"

        f"제목: {title}\n\n{body}"

    )

    sis = (

        system_instr

        + "\n\n지금은 '분량 보강' 단계입니다. 위 지시를 최우선으로 하고, 지정한 이미지 줄은 절대 바꾸지 마세요."

    )

    has_img_prefix = bool(image_prefix_parts)

    parts = (image_prefix_parts or []) + [types.Part.from_text(text=user_txt)]

    contents = parts if has_img_prefix else user_txt

    response = None

    cur = use_model

    for attempt in range(1, 4):

        try:

            response = client.models.generate_content(

                model=cur,

                contents=contents,

                config=types.GenerateContentConfig(system_instruction=sis),

            )

            break

        except Exception as e:

            if ("503" in str(e) or "UNAVAILABLE" in str(e)) and attempt < 3:

                if attempt >= 2:

                    cur = MULTIMODAL_FALLBACK if cur == MULTIMODAL_MODEL else MODEL

                time.sleep(2**attempt)

            else:

                raise

    if response is None or not (response.text or "").strip():

        return title, body

    raw = response.text

    new_title = title

    new_body = raw

    for line in raw.splitlines():

        stripped = re.sub(r"^제목\s*:\s*", "", line)

        if stripped != line:

            new_title = stripped.strip()

            new_body = raw[raw.index(line) + len(line) :].strip()

            break

    if not new_body.strip():

        return title, body

    return new_title, new_body



def generate_blog_content(

    keywords: list,

    clinic_name: str = "",

    max_retries: int = 5,

    target_char_count: int | None = None,

) -> dict:

    """keywords: 하나 이상의 키워드 리스트. 여러 개면 하나의 글에 모두 녹여쓰기."""

    ref_texts = ""

    selected_images: list = []



    if clinic_name:

        clinic_src_dir = os.path.join(SRC_DIR, clinic_name)

        has_clinic_folder = os.path.isdir(clinic_src_dir)



        if has_clinic_folder:

            # src/{clinic_name}/ ?더 ?음 ??참고글 + ?당 ?더 ??지

            ref_texts = read_reference_texts(clinic_name)

            all_images = get_clinic_images(clinic_name)

        else:

            # src/{clinic_name}/ ?더 ?음 ??참고글 ?음, src/img/ 공용 ??지 ?백

            ref_texts = ""

            fallback_img_dir = os.path.join(SRC_DIR, "img")

            if os.path.isdir(fallback_img_dir):

                all_images = [

                    f for f in os.listdir(fallback_img_dir)

                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))

                ]

            else:

                all_images = []



        if all_images:

            selected_images = random.sample(all_images, min(4, len(all_images)))



    # ── 이미지 파트 & 멀티모달 결정 ──────────────────────────────────

    # selected_images : UI 썸네일/미리보기용 (파일 존재 여부 무관하게 반환)

    # image_parts     : AI 멀티모달 전달용 (실제 로딩 성공한 것만)

    image_parts = []

    ai_images = []   # AI???제??달????지 ?일?

    if selected_images and clinic_name:

        clinic_src_dir = os.path.join(SRC_DIR, clinic_name)

        has_clinic_folder = os.path.isdir(clinic_src_dir)

        for fname in selected_images:

            # ?더 ?으?clinic/img/, ?으?src/img/ ?백

            if has_clinic_folder:

                img_path = os.path.join(SRC_DIR, clinic_name, "img", fname)

            else:

                img_path = os.path.join(SRC_DIR, "img", fname)

            if os.path.isfile(img_path):

                try:

                    image_parts.extend(_load_image_part(img_path, fname))

                    ai_images.append(fname)

                except Exception:

                    pass



    use_multimodal = bool(image_parts)



    # ?? ?스??지?????????????????????????????????????????????????

    system_instr = KEYWORD_SYSTEM_INSTRUCTION

    if clinic_name:

        system_instr += f"\n\n작성하는 블로그 글은 '{clinic_name}' 치과의 공식 블로그 글입니다. 치과명을 본문에서 자연스럽게 언급해주세요."

    if use_multimodal:

        fname_list = "\n".join(f"- {f}" for f in ai_images)

        system_instr += (

            f"\n\n위에 첨부된 이미지들을 직접 보고 내용을 파악하세요."
            f" 아래 이미지 파일 {len(ai_images)}장을 모두 본문에 골고루 배치해야 합니다."
            f" 각 이미지가 어울리는 섹션 바로 아래에 [이미지: 파일명] 형식으로 별도 줄에 놓으세요."
            f" ⚠️ 아래 파일명을 모두 빠짐없이 사용하고, 파일명만 단독으로 쓰지 말고 반드시 [이미지: 파일명] 형식을 유지하세요:\n{fname_list}"

        )

    elif selected_images:

        fname_list = "\n".join(f"- {f}" for f in selected_images)

        system_instr += (

            f"\n\n본문의 각 섹션에 [이미지: 파일명] 형식으로 이미지를 배치하세요."
            f" 아래 파일명 {len(selected_images)}개를 모두 빠짐없이 사용해야 합니다(파일명만 단독으로 쓰지 마세요):\n{fname_list}"

        )

    else:

        system_instr += (

            "\n\n이미지 파일이 없으므로 [이미지: ...] 자리에는 해당 섹션 이미지 설명을 넣어주세요."

        )



    # ?? ?롬?트 ?스?????????????????????????????????????????????

    primary_keyword = keywords[0] if keywords else ""

    kw_str = ", ".join(keywords)

    clinic_label = f"{clinic_name} 치과" if clinic_name else "치과"

    prompt_text = (

        f"다음 치과 키워드로 블로그 글을 작성해줘.\n"

        f"치과명은 {clinic_label}\n"

        f"키워드: {kw_str}\n\n"

        f"소제목 1~4는 이 키워드를 주제로 자연스럽게 구성하고,"

        f" 글 전체에서 치과명 '{clinic_label}'을 자연스럽게 언급해줘."

    )

    if ref_texts:

        prompt_text += (

            f"\n\n아래는 {clinic_name} 치과에서 실제 작성된 블로그 글 예시입니다."
            f" 이 글들의 문체·톤·구조를 최대한 참고해서 비슷한 느낌으로 작성해주세요"
            f" (내용은 키워드에 맞게 새로 작성):\n\n{ref_texts}"

        )



    if target_char_count:

        n = target_char_count

        floor_n = int(n * 0.9)

        prompt_text += (

            f"\n\n[분량 제약 — 필수]\n"

            f"본문만 기준으로, 줄바꿈·스페이스·탭 등 공백을 제외한 글자 수가 **약 {n}자**가 되게 작성하세요.\n"

            f"같은 기준으로 **최소 {floor_n}자 이상**이 되어야 합니다. 이보다 짧으면 요구를 충족하지 못한 것입니다.\n"

            f"'[이미지: 파일명]' 형태의 **한 줄**은 글자 수 계산에서 제외합니다(해당 줄은 그대로 두세요).\n"

            "소제목별로 설명·예시·주의사항을 충분히 넣어 분량을 채우세요."

        )



    # ── contents 구성: 멀티모달(이미지+텍스트) or 텍스트만 ──────────────

    if use_multimodal:

        # 이미지 파트 먼저, 그 다음 지시 텍스트

        contents = image_parts + [types.Part.from_text(text=prompt_text)]

        use_model = MULTIMODAL_MODEL

    else:

        contents = prompt_text

        use_model = MODEL



    for attempt in range(1, max_retries + 1):

        try:

            response = client.models.generate_content(

                model=use_model,

                contents=contents,

                config=types.GenerateContentConfig(system_instruction=system_instr),

            )

            break

        except Exception as e:

            if ("503" in str(e) or "UNAVAILABLE" in str(e)) and attempt < max_retries:

                # 마???도 ?엔 lite 모델??백

                if attempt == max_retries - 1 and use_model == MULTIMODAL_MODEL:

                    use_model = MULTIMODAL_FALLBACK

                time.sleep(2 ** attempt)

            elif ("503" in str(e) or "UNAVAILABLE" in str(e)):

                # ?시???진 ??lite 모델?1?????도

                fallback = MULTIMODAL_FALLBACK if use_model != MULTIMODAL_FALLBACK else MODEL

                response = client.models.generate_content(

                    model=fallback,

                    contents=contents,

                    config=types.GenerateContentConfig(system_instruction=system_instr),

                )

                break

            else:

                raise



    raw = response.text

    title = ", ".join(keywords)   # AI ?목???으??워???열??기본값으?

    body = raw



    for line in raw.splitlines():

        stripped = re.sub(r'^제목\s*:\s*', '', line)

        if stripped != line:   # "제목:" 또는 "제목 :" 매칭

            title = stripped.strip()

            body = raw[raw.index(line) + len(line):].strip()

            break



    # 마크?운·?션 ?이??거

    body = strip_markdown(body)



    # AI가 ?목 줄을 ???었??????본문 ?문장???목?로 ?용

    if title == ", ".join(keywords):

        for line in body.splitlines():

            line = line.strip()

            if line and not line.startswith("[이미지"):

                title = line[:50]  # 최? 50??

                break

    # AI가 [??지: xxx] ?퍼 ?이 ?일명만 출력??경우 복원

    if selected_images:

        body = normalize_image_markers(body, selected_images)



    # ?동 ?정 ?스 (치과??일, ??, 말투 ????

        if clinic_name:

            title, body = _apply_fixes(title, body, clinic_name)

            if selected_images:

                body = normalize_image_markers(body, selected_images)



    if target_char_count:

        m0 = _blog_body_metric_chars(body)

        if m0 < int(target_char_count * 0.88):

            title, body = _expand_blog_body_for_length(

                title,

                body,

                target_char_count,

                m0,

                system_instr,

                use_model,

                image_parts if use_multimodal else None,

            )

            body = strip_markdown(body)

            if selected_images:

                body = normalize_image_markers(body, selected_images)

            if clinic_name:

                title, body = _apply_fixes(title, body, clinic_name)

                if selected_images:

                    body = normalize_image_markers(body, selected_images)



    # ?네???서?본문 ?장 ?서??맞게 ?렬

    ordered_images = _order_images_by_body(body, selected_images)



    return {

        "title": title,

        "body": body,

        "keywords": keywords,

        "images": ordered_images,

        "clinic_name": clinic_name,

        "multimodal": use_multimodal,

    }







# ?? ?스?????태 ????????????????????????????????????????????????



queue_status = {

    "state": "idle",       # idle | running | done | error

    "message": "",

    "current": 0,          # ?재 처리 중인 ?덱??(1-based)

    "total": 0,

    "items": [],           # [{title, state, message, idx?}, ...]

}





# ?? 치과 ?로??관??????????????????????????????????????????????



# ?? Selenium ?????????????????????????????????????????????????????



CHROME_PROFILE_DIR = os.path.join(BASE_DIR, "chrome_profile")

CHROME_ACCOUNTS_ROOT = os.path.join(BASE_DIR, "chrome_accounts")

ACCOUNTS_FILE = os.path.join(BASE_DIR, "blog_accounts.json")

os.makedirs(CHROME_ACCOUNTS_ROOT, exist_ok=True)

_account_drivers: dict = {}

_remote_attached_driver = None



MSG_CHROME_PROFILE_IN_USE = (

    "자동화용 Chrome이 이 프로필로 이미 실행 중입니다. "

    "해당 Chrome 창을 모두 닫은 뒤 이 페이지를 새로고침(F5)하거나 다시 시도해 주세요."

)





class ChromeProfileInUseError(Exception):

    """동일 user-data-dir으로 Chrome을 두 번 띄울 수 없을 때."""

    def __init__(self, profile_dir: str):

        self.profile_dir = profile_dir

        super().__init__(MSG_CHROME_PROFILE_IN_USE)





def _chrome_singleton_lock_present(profile_dir: str) -> bool:

    """Chrome이 프로필을 점유 중이면 SingletonLock 등이 남습니다(_clean 후에도 삭제 실패 시)."""

    root = os.path.abspath(os.path.normpath((profile_dir or "").strip()))

    if not root or not os.path.isdir(root):

        return False

    candidates = [

        os.path.join(root, "SingletonLock"),

        os.path.join(root, "SingletonSocket"),

        os.path.join(root, "SingletonCookie"),

        os.path.join(root, "Default", "SingletonLock"),

        os.path.join(root, "Default", "SingletonSocket"),

    ]

    for p in candidates:

        try:

            if os.path.exists(p):

                return True

        except OSError:

            continue

    return False





def _chrome_remote_debugging_addr() -> str:

    """예: 127.0.0.1:9222 — 설정 시 새 Chrome을 띄우지 않고 기존 인스턴스에만 연결."""

    return (os.environ.get("CHROME_REMOTE_DEBUGGING") or "").strip()





def _attach_chrome_via_remote_debugging(addr: str):

    """이미 --remote-debugging-port 로 떠 있는 Chrome에 Selenium 연결."""

    opts = Options()

    opts.add_experimental_option("debuggerAddress", addr)

    drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    try:

        drv.implicitly_wait(5)

    except Exception:

        pass

    return drv





def _installed_chrome_major_version():

    """undetected_chromedriver용 Chrome 메이저. UC_VERSION_MAIN(.env) 우선, Windows는 레지스트리."""

    ev = (os.environ.get("UC_VERSION_MAIN") or "").strip()

    if ev:

        try:

            n = int(ev)

            if 80 <= n <= 250:

                return n

        except ValueError:

            pass

    if sys.platform != "win32":

        return None

    try:

        import winreg

        reg_paths = [

            (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon"),

            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Google\Chrome\BLBeacon"),

            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Google\Chrome\BLBeacon"),

        ]

        for hive, path in reg_paths:

            try:

                key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)

                ver, _ = winreg.QueryValueEx(key, "version")

                winreg.CloseKey(key)

                m = re.match(r"^(\d+)\.", str(ver).strip())

                if m:

                    n = int(m.group(1))

                    if 80 <= n <= 250:

                        return n

            except OSError:

                continue

    except Exception:

        pass

    return None





def _add_chrome_stealth_options(opts: Options) -> None:

    """user-data-dir과 함께 쓰는 공통 Chrome 옵션 (쿠키·세션 유지 + 자동화 탐지 완화)."""

    opts.add_argument("--disable-blink-features=AutomationControlled")

    opts.add_argument("--no-first-run")

    opts.add_argument("--no-default-browser-check")

    opts.add_argument("--disable-session-crashed-bubble")

    opts.add_argument("--disable-infobars")

    opts.add_argument("--lang=ko-KR")

    opts.add_argument("--window-size=1366,900")

    opts.add_argument("--disable-background-networking")

    opts.add_argument("--disable-backgrounding-occluded-windows")

    opts.add_argument("--disable-renderer-backgrounding")

    opts.add_experimental_option("excludeSwitches", ["enable-automation"])

    opts.add_experimental_option("useAutomationExtension", False)





def _naver_logged_in_from_page_source(src: str) -> bool:

    """페이지 소스로 네이버 로그인 여부 추정. '로그아웃 상태입니다' 등으로 인한 오탐 방지."""

    if not src:

        return False

    # 비로그인 안내 문구에 '로그아웃' 부분 문자열이 포함되어 naive in 검사가 깨짐

    if "로그아웃 상태입니다" in src:

        return False

    # 로그인된 상단 메뉴에 실제 로그아웃(세션 종료) URL이 붙는 경우가 많음

    if "nid.naver.com/nidlogin.logout" in src or "nidlogin.logout" in src:

        return True

    return False





def _naver_session_cookies_present(driver) -> bool:

    """네이버 로그인 세션용 쿠키가 있는지 (HTML보다 먼저 잡히는 경우가 많음)."""

    try:

        for c in driver.get_cookies():

            dom = (c.get("domain") or "")

            nm = (c.get("name") or "")

            if "naver.com" not in dom:

                continue

            if nm.startswith("NID_AUT") or nm in ("NID_SES", "NID_JKL"):

                return True

    except Exception:

        pass

    return False





def is_naver_logged_in(driver) -> bool:

    """Naver 로그인 상태 확인 (naver.com 메인 기준)."""

    try:

        driver.get("https://www.naver.com")

        time.sleep(2)

        src = driver.page_source

        return _naver_logged_in_from_page_source(src) or _naver_session_cookies_present(driver)

    except Exception:

        return False





def _clean_profile_for_selenium(profile_dir: str, preserve_login: bool = True):

    """Chrome ?행 ???금 ?일 ?리.

    preserve_login=True(기본): lock ?일??거, ?션/쿠키 ??.

    preserve_login=False: ?션 ?일???거 (?전 초기?? 최초 ?치 ?만 ?용).

    """

    # Chrome 멀티프로세스 lock 만 제거 (SingletonCookie/Socket 삭제는 쿠키 DB와 충돌 보고가 있어 Lock만 처리)

    for fname in ["SingletonLock"]:

        try:

            os.remove(os.path.join(profile_dir, fname))

        except Exception:

            pass



    if not preserve_login:

        # 로그???션 관???일 ??로그???태??리므?최초 ?정 ?에??용

        default_dir = os.path.join(profile_dir, "Default")

        for fname in ["Last Session", "Last Tabs", "Current Session", "Current Tabs"]:

            try:

                os.remove(os.path.join(default_dir, fname))

            except Exception:

                pass





def acquire_chrome_driver(cache_key: str, profile_dir: str):

    """cache_key별 Chrome user-data-dir (세션 분리). undetected-chromedriver 우선."""

    global _account_drivers, _remote_attached_driver

    remote = _chrome_remote_debugging_addr()

    if remote:

        if _remote_attached_driver is not None:

            try:

                _ = _remote_attached_driver.current_url

                return _remote_attached_driver

            except Exception:

                try:

                    _remote_attached_driver.quit()

                except Exception:

                    pass

                _remote_attached_driver = None

        _remote_attached_driver = _attach_chrome_via_remote_debugging(remote)

        return _remote_attached_driver

    target_dir = os.path.abspath(os.path.normpath((profile_dir or CHROME_PROFILE_DIR).strip() or CHROME_PROFILE_DIR))

    existing = _account_drivers.get(cache_key)

    if existing is not None:

        try:

            _ = existing.current_url

            return existing

        except Exception:

            try:

                existing.quit()

            except Exception:

                pass

            _account_drivers.pop(cache_key, None)



    _clean_profile_for_selenium(target_dir, preserve_login=True)

    time.sleep(1)

    if _chrome_singleton_lock_present(target_dir):

        raise ChromeProfileInUseError(target_dir)



    drv = None

    try:

        import undetected_chromedriver as uc

        opts = uc.ChromeOptions()

        opts.add_argument(f"--user-data-dir={target_dir}")

        opts.add_argument("--profile-directory=Default")

        opts.add_argument("--disable-popup-blocking")

        opts.add_argument("--start-maximized")

        opts.add_argument("--lang=ko-KR")

        opts.add_argument("--disable-extensions")

        vm = _installed_chrome_major_version()

        uc_kw = {"options": opts, "use_subprocess": True}

        if vm is not None:

            uc_kw["version_main"] = vm

            logging.info("undetected_chromedriver: Chrome 메이저 %s에 맞춰 드라이버를 받습니다.", vm)

        drv = uc.Chrome(**uc_kw)

        try:

            drv.implicitly_wait(5)

        except Exception:

            pass

    except ImportError:

        logging.warning("undetected_chromedriver 미설치 — pip install undetected-chromedriver 권장. 일반 Chrome으로 폴백합니다.")

    except Exception as e:

        logging.warning("undetected_chromedriver 시작 실패, Selenium 폴백: %s", e)

        drv = None



    if drv is None:

        opts = Options()

        opts.add_argument(f"--user-data-dir={target_dir}")

        opts.add_argument("--profile-directory=Default")

        opts.add_argument("--disable-extensions")

        _add_chrome_stealth_options(opts)

        drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

        drv.execute_cdp_cmd(

            "Page.addScriptToEvaluateOnNewDocument",

            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},

        )



    _account_drivers[cache_key] = drv

    return drv





def _close_chrome_drivers_for_queue_keys(cache_keys: list) -> None:

    """포스팅 큐가 모두 성공한 뒤, 이 큐에서 사용한 Chrome을 종료합니다.

    CHROME_REMOTE_DEBUGGING으로 기존 Chrome에 붙은 경우에는 사용자 브라우저를 닫지 않습니다.

    QUEUE_CLOSE_BROWSER_ON_DONE=0 (또는 false/off/no)이면 건너뜁니다.

    """

    flag = os.environ.get("QUEUE_CLOSE_BROWSER_ON_DONE", "1")

    if str(flag).strip().lower() in ("0", "false", "no", "off"):

        return

    if _chrome_remote_debugging_addr():

        logging.info("CHROME_REMOTE_DEBUGGING: 큐 완료 후 브라우저 자동 종료를 하지 않습니다.")

        return

    global _account_drivers

    if not cache_keys:

        return

    for cache_key in cache_keys:

        drv = _account_drivers.pop(cache_key, None)

        if drv is None:

            continue

        try:

            drv.quit()

        except Exception as ex:

            logging.warning("포스팅 큐 완료 후 Chrome 종료 실패 (%s): %s", cache_key, ex)





def get_driver(profile_dir: str = ""):

    """기본(.env) 계정 — chrome_profile."""

    td = profile_dir or CHROME_PROFILE_DIR

    return acquire_chrome_driver("__env__", os.path.abspath(os.path.normpath(td)))





def _default_accounts_data() -> dict:

    return {"version": 1, "accounts": [], "active_account_id": ""}





def load_accounts_json() -> dict:

    if not os.path.isfile(ACCOUNTS_FILE):

        return _default_accounts_data()

    try:

        with open(ACCOUNTS_FILE, encoding="utf-8") as f:

            d = json.load(f)

        if not isinstance(d, dict) or not isinstance(d.get("accounts"), list):

            return _default_accounts_data()

        return d

    except Exception:

        return _default_accounts_data()





def save_accounts_json(data: dict) -> None:

    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:

        json.dump(data, f, ensure_ascii=False, indent=2)





def _normalize_accounts_rows(rows: list) -> list:

    out: list = []

    seen: set = set()

    for r in rows[:40]:

        if not isinstance(r, dict):

            continue

        aid = str(r.get("id") or "").strip()

        if not aid:

            aid = uuid.uuid4().hex[:10]

        while aid in seen:

            aid = uuid.uuid4().hex[:10]

        seen.add(aid)

        label = (str(r.get("label") or "").strip() or aid)

        nid = str(r.get("naver_id") or "").strip()

        pw = str(r.get("naver_pw") if r.get("naver_pw") is not None else "")

        cn = str(r.get("clinic_name") or "").strip()

        out.append({"id": aid, "label": label, "naver_id": nid, "naver_pw": pw, "clinic_name": cn})

        try:

            os.makedirs(os.path.join(CHROME_ACCOUNTS_ROOT, aid), exist_ok=True)

        except OSError:

            pass

    return out





def _find_account_by_id(aid: str) -> dict | None:

    for a in load_accounts_json().get("accounts") or []:

        if isinstance(a, dict) and a.get("id") == aid:

            return a

    return None





def _resolve_item_account(item: dict) -> tuple[str | None, str, str, str]:

    """(cache_key, profile_dir_abs, naver_id, naver_pw). cache_key None 이면 알 수 없는 account_id."""

    raw = (item.get("account_id") or item.get("accountId") or "").strip()

    if not raw or raw == "__env__":

        return "__env__", os.path.abspath(CHROME_PROFILE_DIR), ENV_NAVER_ID, ENV_NAVER_PW

    acc = _find_account_by_id(raw)

    if acc is None:

        return None, "", "", ""

    prof = os.path.abspath(os.path.join(CHROME_ACCOUNTS_ROOT, raw))

    return raw, prof, (acc.get("naver_id") or "").strip(), str(acc.get("naver_pw") or "")





def _is_on_login_page(driver) -> bool:

    try:

        url = driver.current_url

        return "nidlogin" in url or "nid.naver.com" in url

    except Exception:

        return True





def auto_login(driver, naver_id: str, naver_pw: str) -> bool:

    """네이버 로그인: 클립보드 붙여넣기 + #log.login 클릭 (undetected-chromedriver 조합 권장)."""

    try:

        # ??커???보 (백그?운???행 ??Ctrl+V가 ?른 창으?가??문제 방?)

        driver.maximize_window()

        driver.switch_to.window(driver.window_handles[0])

        time.sleep(0.3)



        # 로그???이지??동

        if not _is_on_login_page(driver):

            driver.get("https://nid.naver.com/nidlogin.login")

            time.sleep(2)



        pyperclip.copy("")



        # 클립보드 붙여넣기: 반드시 해당 input 요소에 send_keys (active_element는 포커스가 빗나가면 ID만 비게 됨)

        def _paste_into_field(el, text: str) -> None:

            pyperclip.copy(text if text is not None else "")

            el.click()

            time.sleep(0.22)

            try:

                el.send_keys(Keys.CONTROL, "a")

                time.sleep(0.06)

            except Exception:

                pass

            el.send_keys(Keys.CONTROL, "v")

            time.sleep(0.4)



        nid = (naver_id or "").strip()

        npw = "" if naver_pw is None else str(naver_pw)



        id_input = WebDriverWait(driver, 10).until(

            EC.element_to_be_clickable((By.ID, "id"))

        )

        for _ in range(4):

            _paste_into_field(id_input, nid)

            if (id_input.get_attribute("value") or "").strip():

                break

            time.sleep(0.35)

        else:

            if nid:

                try:

                    driver.execute_script(

                        "var el=arguments[0],v=arguments[1];el.focus();el.value=v;"

                        "['input','change'].forEach(function(t){el.dispatchEvent(new Event(t,{bubbles:true}));});",

                        id_input,

                        nid,

                    )

                except Exception:

                    pass

                time.sleep(0.25)



        pyperclip.copy("")



        pw_input = driver.find_element(By.ID, "pw")

        for _ in range(3):

            _paste_into_field(pw_input, npw)

            if len(pw_input.get_attribute("value") or "") > 0:

                break

            time.sleep(0.35)



        login_btn = WebDriverWait(driver, 10).until(

            EC.element_to_be_clickable((By.ID, "log.login"))

        )

        login_btn.click()

        time.sleep(3)



        # ?공 ?인

        if not _is_on_login_page(driver):

            return True



        # 캡챠·2?계 ?증 ?????동 개입 ??(최? 2?

        queue_status["message"] = "⚠️ 보안 인증이 필요합니다. 브라우저에서 로그인을 완료해주세요. (최대 2분)"

        start = time.time()

        while time.time() - start < 120:

            if not _is_on_login_page(driver):

                return True

            time.sleep(1)

        return False

    except Exception as e:

        logging.warning(f"auto_login ?패: {e}")

        return False





def ensure_logged_in(driver, naver_id: str = "", naver_pw: str = "") -> bool:

    """로그???태 ?인 ???? 로그?이?즉시 True.

    ?션 만료 ?? auto_login 보조 ?도 ?????면 ?동 ??"""



    if is_naver_logged_in(driver):

        return True



    # auto_login? 보조 ?단 ???? ?공?진 ?음 (Naver ?책)

    if naver_id and naver_pw:

        queue_status["message"] = "자동 로그인 시도 중..."

        if auto_login(driver, naver_id, naver_pw):

            if is_naver_logged_in(driver):

                queue_status["message"] = "자동 로그인 완료!"

                driver.get("https://blog.naver.com/GoBlogWrite.naver")

                time.sleep(2)

                return True



    # ?동 로그????(캡챠·2?계 ?증 ??

    queue_status.update({"state": "running", "message": "⚠️ 로그인이 필요합니다. 브라우저에서 네이버 로그인을 해주세요. (최대 3분)"})

    driver.get("https://nid.naver.com/nidlogin.login")

    time.sleep(1)

    start = time.time()

    while time.time() - start < 180:

        if is_naver_logged_in(driver):

            queue_status["message"] = "로그인 완료!"

            driver.get("https://blog.naver.com/GoBlogWrite.naver")

            time.sleep(2)

            return True

        time.sleep(2)

    queue_status.update({"state": "error", "message": "로그인 대기 시간 초과(3분). 브라우저에서 로그인 후 다시 시도해 주세요."})

    return False





# [??지: ?일? ?턴

IMAGE_RE = re.compile(r'\[이미지:\s*([^\]]+)\]')





def _apply_fixes(title: str, body: str, clinic_name: str) -> tuple[str, str]:

    """작성된 본문을 Gemini로 자동 교정 (치과명 일치, 오타, 말투 확인)"""

    prompt = f"""아래 블로그 글을 다음 기준으로 조용히 교정해줘. 설명 없이 교정된 결과만 출력해.



교정 기준:

1. 치과명은 반드시 "{clinic_name}"으로만 쓰기 (다른 이름 사용 금지)

2. 오타, 어색한 문장 자연스럽게 교정

3. 말투는 끝까지 통일되게 유지 (존댓말 기준)

4. 제목-본문-소제목 구조는 그대로 유지

5. [이미지: 파일명] 형태의 태그는 절대 삭제하거나 수정하지 말고 원래 위치에 그대로 유지



출력 형식 (반드시 지켜):

제목: [교정된 제목]

[교정된 본문]



--- 원본 ---

제목: {title}

{body}"""



    try:

        response = client.models.generate_content(model=MODEL, contents=prompt)

        raw = response.text.strip()

        new_title = title

        new_body = raw

        for line in raw.splitlines():

            stripped = re.sub(r'^제목\s*:\s*', '', line)

            if stripped != line:

                new_title = stripped.strip()

                new_body = raw[raw.index(line) + len(line):].strip()

                break

        new_body = strip_markdown(new_body)

        return new_title, new_body

    except Exception:

        return title, body   # ?패 ???본 ??





def strip_markdown(text: str) -> str:

    """AI가 출력한 마크다운 기호 및 구조 태그 제거"""

    # 제목: / 제목 : 제거 (제목은 별도 파싱, 본문에는 불필요)

    text = re.sub(r'^제목\s*:.*$', '', text, flags=re.MULTILINE)

    # [서론] [본론1] [본론2] [본론3] [결론] 등 섹션 태그 제거

    text = re.sub(r'^\[(?:서론|본론\s*\d*|결론)\]\s*$', '', text, flags=re.MULTILINE)

    # ## ?목 기호 ?거

    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # **굵게** / __굵게__ (?일??더?코?? ?동 방?: __ ?만 ?거)

    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)

    text = re.sub(r'__(.+?)__', r'\1', text)

    # *기울?? (?더?코??_italic_ ? ?일??손 ?험 ???거?? ?음)

    text = re.sub(r'\*(.+?)\*', r'\1', text)

    # `코드`

    text = re.sub(r'`(.+?)`', r'\1', text)

    # --- 구분??

    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)

    # 3??상 ?속 ????2줄로 ?리

    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()





def normalize_image_markers(body: str, known_images: list) -> str:

    """AI가 [??지: xxx] ?퍼 ?이 ?일명만 줄에 출력??경우 ??[??지: xxx] ?식?로 복원"""

    for fname in known_images:

        body = re.sub(

            r'^\s*' + re.escape(fname) + r'\s*$',

            f'[이미지: {fname}]',

            body,

            flags=re.MULTILINE,

        )

    return body





def _order_images_by_body(body: str, images: list) -> list:

    """본문???장?는 [??지: ?일? ?서??images 배열???정??

    본문???는 ??지???에 붙임."""

    seen = []

    for m in re.finditer(r'\[이미지:\s*([^\]]+)\]', body):

        fname = m.group(1).strip()

        if fname in images and fname not in seen:

            seen.append(fname)

    # 본문???는 ??지???래 ?서 ???며 ?에 추?

    rest = [f for f in images if f not in seen]

    return seen + rest


def ensure_cardnews_image_markers(body: str, saved_filenames: list) -> str:

    """카드뉴스 생성 시 모델이 도입부 첫 이미지를 생략하는 경우가 있어, 누락된 [이미지: 파일명] 태그를 보강한다."""

    if not saved_filenames or not (body or "").strip():

        return body

    present = set(m.group(1).strip() for m in IMAGE_RE.finditer(body))

    missing_prefix = []

    missing_suffix = []

    seen_present = False

    for fn in saved_filenames:

        if fn in present:

            seen_present = True

        elif not seen_present:

            missing_prefix.append(fn)

        else:

            missing_suffix.append(fn)

    out = body

    if missing_prefix:

        block = "\n\n" + "\n".join(f"[이미지: {fn}]" for fn in missing_prefix) + "\n\n"

        m1 = re.search(r"(?m)^\s*1\.\s", out)

        if m1:

            out = out[: m1.start()] + block + out[m1.start() :]

        else:

            out = block + out

    if missing_suffix:

        out = out.rstrip() + "\n\n" + "\n".join(f"[이미지: {fn}]" for fn in missing_suffix) + "\n"

    return out







def _env_float(key: str, default: float, lo: float, hi: float) -> float:

    try:

        v = float(os.environ.get(key, "") or default)

    except (TypeError, ValueError):

        v = default

    return max(lo, min(hi, float(v)))





def _send_keys_to_visible_file_inputs(driver, abs_path: str) -> bool:

    """DOM의 file input에 경로만 넣기 (가능하면 OS '열기' 창 없이 동작)."""

    selectors = [

        ".se-popup input[type='file']",

        ".se-popup-tab-content input[type='file']",

        ".se-layer input[type='file']",

        "input[type='file']",

    ]

    for css in selectors:

        for fi in driver.find_elements(By.CSS_SELECTOR, css):

            try:

                driver.execute_script(

                    "arguments[0].style.cssText='display:block!important;"

                    "visibility:visible!important;opacity:1!important;';",

                    fi,

                )

                fi.send_keys(abs_path)

                return True

            except Exception:

                continue

    return False





def _upload_image(driver, img_abs_path: str) -> bool:

    """스마트에디터3에 로컬 이미지 삽입. 먼저 숨은 file input에 경로를 넣고, 실패할 때만 'PC에서' 탭을 눌러 재시도."""

    try:

        abs_path = os.path.normpath(os.path.abspath(img_abs_path))

        wait_panel = _env_float("NAVER_IMG_PANEL_WAIT_SEC", 0.9, 0.2, 5.0)

        wait_tab = _env_float("NAVER_IMG_TAB_CLICK_WAIT_SEC", 0.35, 0.05, 3.0)

        wait_after_keys = _env_float("NAVER_IMG_AFTER_SENDKEYS_SEC", 1.6, 0.4, 30.0)

        wait_after_confirm = _env_float("NAVER_IMG_AFTER_CONFIRM_SEC", 1.0, 0.2, 15.0)

        wait_tail = _env_float("NAVER_IMG_TAIL_WAIT_SEC", 0.9, 0.2, 15.0)

        img_btn = WebDriverWait(driver, 10).until(

            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-name='image']"))

        )

        driver.execute_script("arguments[0].click();", img_btn)

        try:

            WebDriverWait(driver, 6).until(

                EC.presence_of_element_located(

                    (By.CSS_SELECTOR, "input[type='file'], .se-popup, .se-layer")

                )

            )

        except Exception:

            pass

        time.sleep(wait_panel)

        sent = _send_keys_to_visible_file_inputs(driver, abs_path)

        if not sent:

            for sel in [

                "button[data-name='imageUploadFromFile']",

                ".__se__upload-file",

                ".se-popup-tab-item[data-tab='upload']",

                "[data-type='fileUpload']",

            ]:

                try:

                    el = driver.find_element(By.CSS_SELECTOR, sel)

                    if el.is_displayed():

                        driver.execute_script("arguments[0].click();", el)

                        time.sleep(wait_tab)

                        break

                except Exception:

                    pass

            sent = _send_keys_to_visible_file_inputs(driver, abs_path)

        if not sent:

            ActionChains(driver).send_keys(Keys.ESCAPE).perform()

            return False

        time.sleep(wait_after_keys)

        for sel in [

            ".se-popup-button-confirm",

            "button[data-action='insert']",

            ".se-file-upload-area button[type='button']",

        ]:

            try:

                btn = WebDriverWait(driver, 3).until(

                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))

                )

                btn.click()

                time.sleep(wait_after_confirm)

                break

            except Exception:

                pass

        try:

            import ctypes

            for title in ("열기", "Open"):

                hwnd = ctypes.windll.user32.FindWindowW(None, title)

                if hwnd:

                    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)

                    time.sleep(0.2)

        except Exception:

            pass

        time.sleep(wait_tail)

        return True

    except Exception:

        return False





def _paste_text_segment(driver, text: str):

    """본문 구간을 클립보드로 붙여넣기. 한 줄이 매우 길면 잘라 넣어 에디터/클립보드 한계로 끊기는 현상을 줄임."""

    CHUNK = 2500

    lines = text.splitlines()

    for j, line in enumerate(lines):

        pos = 0

        while pos < len(line):

            chunk = line[pos : pos + CHUNK]

            pyperclip.copy(chunk)

            time.sleep(0.08)

            ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()

            time.sleep(0.28)

            pos += len(chunk)

        if j < len(lines) - 1:

            ActionChains(driver).send_keys(Keys.ENTER).perform()

            time.sleep(0.15)





def post_one(driver, title: str, body: str, clinic_name: str = "", img_dir: str = ""):

    """글쓰기 페이지에서 자동으로 제목·본문(이미지 포함) 입력 후 저장"""

    # ?전 글 ?집 ?태가 ?아?을 ???으므?먼? 기본 ?레?으?복?

    try:

        driver.switch_to.default_content()

    except Exception:

        pass

    driver.get("https://blog.naver.com/GoBlogWrite.naver")

    time.sleep(4)



    # iframe 진입

    main_frame = WebDriverWait(driver, 15).until(

        EC.presence_of_element_located((By.CSS_SELECTOR, "#mainFrame"))

    )

    driver.switch_to.frame(main_frame)

    time.sleep(1)



    # ?업 ?기

    for selector in [".se-popup-button-cancel", ".se-help-panel-close-button"]:

        try:

            el = driver.find_element(By.CSS_SELECTOR, selector)

            if el.is_displayed():

                el.click()

                time.sleep(0.5)

        except Exception:

            pass



    # ?목 ?력

    title_area = WebDriverWait(driver, 15).until(

        EC.element_to_be_clickable((By.CSS_SELECTOR, ".se-section-documentTitle"))

    )

    ActionChains(driver).click(title_area).perform()

    time.sleep(0.5)

    pyperclip.copy(title)

    ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()

    time.sleep(0.5)



    # 본문 ?역 ?커??

    body_area = WebDriverWait(driver, 15).until(

        EC.element_to_be_clickable((By.CSS_SELECTOR, ".se-section-text"))

    )

    ActionChains(driver).click(body_area).perform()

    time.sleep(0.5)



    # 마크?운 ?전 ?거 ????지 마커 기??로 분리

    # segments: [?스?? ??지?일? ?스?? ??지?일? ...]

    segments = IMAGE_RE.split(strip_markdown(body))



    for seg_idx, segment in enumerate(segments):

        if seg_idx % 2 == 0:

            # ?? ?스??구간 ??

            if segment:

                _paste_text_segment(driver, segment)

        else:

            # ?? ??지 구간 ??

            img_filename = segment.strip()

            img_inserted = False

            if re.search(r'\.(jpg|jpeg|png|gif|webp)$', img_filename, re.IGNORECASE):

                img_abs = None

                # 카드?스 ?시 ?렉?리 ?선

                if img_dir:

                    candidate = os.path.join(img_dir, img_filename)

                    if os.path.isfile(candidate):

                        img_abs = candidate

                # ?으?clinic src ?렉?리

                if img_abs is None and clinic_name:

                    candidate = os.path.join(SRC_DIR, clinic_name, "img", img_filename)

                    if os.path.isfile(candidate):

                        img_abs = candidate

                if img_abs:

                    img_inserted = _upload_image(driver, img_abs)



            # ?? 커서 ?배?(??지 ?공/?패 공통) ??????????????????

            # ESCAPE 금?: SE3?서 ??지 ?입 직후 ESC??르?

            #   ?택????지 블록??취소/?커???탈?어 ?음 ?스???치가 ?긋??

            # ?결: ARROW_DOWN?로 ??지 ?음 블록 ?동,

            #       ?패 ??마???스???션??직접 ?릭

            try:

                time.sleep(0.5)

                if img_inserted:

                    # SE3????지 ?입 ???동?로 ??지 ?음 ?스??블록???성

                    # ARROW_DOWN ???블록?로 ?동, END ????으?

                    ActionChains(driver).send_keys(Keys.ARROW_DOWN).perform()

                    time.sleep(0.2)

                    ActionChains(driver).send_keys(Keys.END).perform()

                    time.sleep(0.2)

                else:

                    # ??지 ?로???패 ??마???스???션???릭??커서 복구

                    text_sections = driver.find_elements(By.CSS_SELECTOR, ".se-section-text")

                    if text_sections:

                        ActionChains(driver).click(text_sections[-1]).perform()

                        time.sleep(0.2)

                        ActionChains(driver).send_keys(Keys.END).perform()

                        time.sleep(0.2)

            except Exception:

                pass



    # ?? ???버튼 (iframe ?? ???? ?? ??

    save_btn = None

    try:

        save_btn = driver.find_element(By.CSS_SELECTOR, ".save_btn__bzc5B")

        if not save_btn.is_displayed():

            save_btn = None

    except Exception:

        save_btn = None



    if save_btn is None:

        driver.switch_to.default_content()

        time.sleep(1)

        for selector, by in [

            (".save_btn__bzc5B", By.CSS_SELECTOR),

            ("[data-click-area='tpb.save']", By.CSS_SELECTOR),

            ("//button[.//span[contains(text(),'???)]]", By.XPATH),

        ]:

            try:

                save_btn = WebDriverWait(driver, 10).until(

                    EC.element_to_be_clickable((by, selector))

                )

                break

            except Exception:

                pass



    if save_btn:

        try:

            driver.execute_script("arguments[0].scrollIntoView(true);", save_btn)

            time.sleep(0.3)

            driver.execute_script("arguments[0].click();", save_btn)

        except Exception:

            save_btn.click()

        time.sleep(2)

        return True

    return False





def run_queue(items: list):

    """계정별 Chrome 프로필 + 자격 증명으로 순차 포스팅(.env 기본 + blog_accounts.json 추가 계정)."""

    queue_status.update({

        "state": "running",

        "message": "브라우저 확인 중..",

        "current": 0,

        "total": len(items),

        "items": [

            {

                "title": it.get("title", ""),

                "state": "pending",

                "message": "",

                "idx": it.get("idx"),

            }

            for it in items

        ],

    })



    for it in items:

        ak, _, nid, npw = _resolve_item_account(it)

        if ak is None:

            queue_status.update({"state": "error", "message": f"알 수 없는 계정(account_id)입니다: {(it.get('account_id') or it.get('accountId') or '').strip()}"})

            return

        if not nid or not (npw or "").strip():

            queue_status.update({"state": "error", "message": "선택한 계정에 네이버 아이디·비밀번호가 없습니다. 상단 .env 또는 추가 계정 목록을 확인하세요."})

            return



    try:

        current_key = None

        driver = None

        driver_keys_used = []



        for global_idx, item in enumerate(items):

            ak, prof, nid, npw = _resolve_item_account(item)

            title = item["title"]

            body = item["body"]

            clinic_name = item.get("clinic_name", "")

            cardnews_session = item.get("cardnews_session", "")



            if ak != current_key:

                queue_status["message"] = f"브라우저·로그인 확인 중.. ({ak})"

                try:

                    driver = acquire_chrome_driver(ak, prof)

                except ChromeProfileInUseError:

                    for j in range(global_idx, len(items)):

                        queue_status["items"][j].update(

                            {"state": "error", "message": "Chrome 프로필 사용 중"}

                        )

                    queue_status.update({"state": "error", "message": MSG_CHROME_PROFILE_IN_USE})

                    return

                if not ensure_logged_in(driver, nid, npw):

                    for j in range(global_idx, len(items)):

                        queue_status["items"][j].update({"state": "error", "message": "로그인 실패"})

                    queue_status.update({"state": "error", "message": "네이버 로그인에 실패했습니다. 해당 계정 정보·캡차를 확인해주세요."})

                    return

                current_key = ak

                if ak not in driver_keys_used:

                    driver_keys_used.append(ak)



            if cardnews_session:

                img_dir = os.path.join(TMP_DIR, cardnews_session)

            elif clinic_name:

                clinic_img = os.path.join(SRC_DIR, clinic_name, "img")

                img_dir = clinic_img if os.path.isdir(clinic_img) else os.path.join(SRC_DIR, "img")

            else:

                img_dir = ""



            queue_status["current"] = global_idx + 1

            queue_status["message"] = f"포스팅 중.. ({global_idx + 1}/{len(items)})"

            queue_status["items"][global_idx]["state"] = "running"

            queue_status["items"][global_idx]["message"] = "작성 중.."



            try:

                success = post_one(driver, title, body, clinic_name, img_dir)

                if success:

                    queue_status["items"][global_idx].update({"state": "done", "message": "포스팅 완료"})

                else:

                    queue_status["items"][global_idx].update({"state": "error", "message": "저장 버튼 못 찾음"})

            except Exception as e:

                queue_status["items"][global_idx].update({"state": "error", "message": str(e)[:80]})



            if global_idx < len(items) - 1:

                queue_status["message"] = f"다음 글 준비 중.. ({global_idx + 2}/{len(items)})"

                try:
                    gap = float(os.environ.get("QUEUE_POST_GAP_SEC", "2") or "2")
                except (TypeError, ValueError):
                    gap = 2.0
                gap = max(0.5, min(gap, 60.0))
                time.sleep(gap)



        done_count = sum(1 for it in queue_status["items"] if it["state"] == "done")

        msg_done = f"완료! {done_count}/{len(items)} 포스팅됨"

        if items and done_count == len(items):

            _close_chrome_drivers_for_queue_keys(driver_keys_used)

            msg_done += " · 브라우저 종료됨"

        queue_status.update({

            "state": "done",

            "message": msg_done,

        })



    except Exception as e:

        queue_status.update({"state": "error", "message": f"오류: {e}"})





# ── 네이버 검색광고 키워드 도구 (공식: HMAC-SHA256 서명 + GET /keywordstool) ──



NAVER_SEARCHAD_API_BASE = os.environ.get(

    "NAVER_SEARCHAD_API_BASE", "https://api.searchad.naver.com"

).rstrip("/")





# 테스트용: 아래에 값을 넣으면 환경 변수가 비어 있을 때 사용합니다.

# 운영·공유·커밋 전에는 반드시 비우거나 환경 변수만 쓰세요.

_NAVER_AD_API_KEY_DEV = "01000000008fe97e9773096e5698d8202d75a5c39da9e9f1208ce756a44c607c2f7e5614bd"

_NAVER_AD_SECRET_KEY_DEV = "AQAAAACP6X6XcwluVpjYIC11pcOdrnEJFAD7zZB1fjauRu866w=="

_NAVER_AD_CUSTOMER_ID_DEV = "841351"





def _naver_searchad_credentials():

    return {

        "api_key": (

            os.environ.get("NAVER_AD_API_KEY", "").strip()

            or _NAVER_AD_API_KEY_DEV.strip()

        ),

        "secret": (

            os.environ.get("NAVER_AD_SECRET_KEY", "").strip()

            or _NAVER_AD_SECRET_KEY_DEV.strip()

        ),

        "customer_id": (

            os.environ.get("NAVER_AD_CUSTOMER_ID", "").strip()

            or _NAVER_AD_CUSTOMER_ID_DEV.strip()

        ),

    }





def _naver_searchad_signature(secret: str, timestamp_ms: int, method: str, uri_path: str) -> str:

    """https://naver.github.io/searchad-apidoc/ — sign = ms + '.' + METHOD + '.' + path (query 제외)."""

    msg = f"{timestamp_ms}.{method.upper()}.{uri_path}"

    digest = hmac.new(

        secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256

    ).digest()

    return base64.b64encode(digest).decode("ascii")





def _naver_keywordstool_request(hint_keywords: str, show_detail: int = 1) -> tuple[int, dict]:

    cred = _naver_searchad_credentials()

    if not cred["api_key"] or not cred["secret"] or not cred["customer_id"]:

        raise RuntimeError(

            "NAVER_AD_API_KEY, NAVER_AD_SECRET_KEY, NAVER_AD_CUSTOMER_ID 를 환경 변수로 설정하거나 "

            "app.py 상단 _NAVER_AD_*_DEV 에 테스트 값을 넣어 주세요."

        )

    uri_path = "/keywordstool"

    ts = int(time.time() * 1000)

    sig = _naver_searchad_signature(cred["secret"], ts, "GET", uri_path)

    headers = {

        "X-Timestamp": str(ts),

        "X-API-KEY": cred["api_key"],

        "X-Customer": cred["customer_id"],

        "X-Signature": sig,

    }

    params = {"hintKeywords": hint_keywords, "showDetail": int(show_detail)}

    url = NAVER_SEARCHAD_API_BASE + uri_path

    r = requests.get(url, headers=headers, params=params, timeout=45)

    try:

        body = r.json()

    except Exception:

        body = {"_non_json": (r.text or "")[:800]}

    return r.status_code, body





def _naver_sanitize_hint_tokens(tokens: list[str]) -> tuple[list[str], bool]:

    """검색광고 keywordstool: hintKeywords에 공백 불가(공식 답변, GitHub #1043)."""

    out: list[str] = []

    changed = False

    for t in tokens:

        s = (t or "").strip()

        if not s:

            continue

        compact = re.sub(r"\s+", "", s)

        if compact != s:

            changed = True

        if compact:

            out.append(compact)

    return out, changed





def _naver_searchad_qc_to_num(v) -> int:

    """검색광고 monthly*QcCnt를 합산·비율용 정수로 근사."""

    if v is None:

        return 0

    if isinstance(v, bool):

        return 0

    if isinstance(v, (int, float)):

        return max(0, int(v))

    s = str(v).strip()

    if not s:

        return 0

    lt = re.match(r"^<\s*(\d+(?:[.,]\d+)?)", s)

    if lt:

        cap = float(str(lt.group(1)).replace(",", "."))

        return max(0, int(cap - 0.5))

    s2 = s.replace(",", "").replace(" ", "")

    try:

        return max(0, int(s2))

    except ValueError:

        return 0





_NAVER_BLOG_SEARCH_URL = "https://openapi.naver.com/v1/search/blog.json"





def _naver_blog_search_total(client_id: str, client_secret: str, query: str) -> tuple[int | None, str | None]:

    """블로그 검색 total 조회. 429/5xx·일시 오류는 재시도, 쿼리는 NFKC·공백 제거 변형도 시도."""

    q = (query or "").strip()

    if not q:

        return None, "empty"

    variants: list[str] = [q]

    q_nf = unicodedata.normalize("NFKC", q)

    if q_nf != q:

        variants.append(q_nf)

    q_cs = re.sub(r"\s+", "", q)

    if q_cs and q_cs not in variants:

        variants.append(q_cs)

    last_err: str | None = None

    for variant in variants:

        for attempt in range(3):

            try:

                r = requests.get(

                    _NAVER_BLOG_SEARCH_URL,

                    headers={

                        "X-Naver-Client-Id": client_id,

                        "X-Naver-Client-Secret": client_secret,

                    },

                    params={"query": variant, "display": 1, "sort": "sim"},

                    timeout=18,

                )

                try:

                    body = r.json()

                except Exception:

                    last_err = f"json_{r.status_code}"

                    if r.status_code in (429, 502, 503):

                        time.sleep(0.35 * (2**attempt))

                        continue

                    break

                if r.status_code != 200:

                    msg = str(body.get("errorMessage") or body.get("message") or body)[:180]

                    last_err = msg

                    if r.status_code in (429, 502, 503):

                        time.sleep(0.35 * (2**attempt))

                        continue

                    break

                tot = body.get("total")

                if isinstance(tot, (int, float)):

                    return int(tot), None

                if isinstance(tot, str) and tot.strip().isdigit():

                    return int(tot.strip()), None

                last_err = "no_total"

                break

            except requests.RequestException as e:

                last_err = str(e)[:120]

                time.sleep(0.35 * (2**attempt))

    return None, last_err





def _apply_blog_market_comp_fields(item: dict) -> None:

    """경쟁비율(블로그 글 수 ÷ 월간 검색 합) 기준 블로그 관점 경쟁 라벨."""

    r = item.get("competitionRatio")

    if r is None or r == "":

        item["blogMarketComp"] = None

        item["blogMarketTier"] = None

        item["blogMarketOrder"] = 99

        return

    try:

        x = float(r)

    except (TypeError, ValueError):

        item["blogMarketComp"] = None

        item["blogMarketTier"] = None

        item["blogMarketOrder"] = 99

        return

    if x < 1:

        item["blogMarketComp"] = "꿀 키워드"

        item["blogMarketTier"] = "honey"

        item["blogMarketOrder"] = 0

    elif x <= 5:

        item["blogMarketComp"] = "보통"

        item["blogMarketTier"] = "mid"

        item["blogMarketOrder"] = 1

    else:

        item["blogMarketComp"] = "높음"

        item["blogMarketTier"] = "high"

        item["blogMarketOrder"] = 2





def _blog_enrich_apply_total(item: dict, total: int | None) -> None:

    sm = int(item.get("monthlySearchSum") or 0)

    item["blogTotal"] = total

    if total is not None and sm > 0:

        item["competitionRatio"] = round(float(total) / float(sm), 4)

    else:

        item["competitionRatio"] = None





def _enrich_blog_totals_parallel(

    items: list[dict],

    client_id: str,

    client_secret: str,

    max_workers: int,

) -> None:

    """월간합을 채우고 relKeyword 가 있는 행만 블로그 검색 total 을 병렬로 조회."""

    pairs: list[tuple[dict, str]] = []

    for item in items:

        rk = str(item.get("relKeyword", "")).strip()

        pc = _naver_searchad_qc_to_num(item.get("monthlyPcQcCnt"))

        mo = _naver_searchad_qc_to_num(item.get("monthlyMobileQcCnt"))

        sm = pc + mo

        item["monthlySearchSum"] = sm

        if rk:

            pairs.append((item, rk))

        else:

            _blog_enrich_apply_total(item, None)

    mw = max(2, min(int(max_workers), 24))

    if not pairs:

        return

    with ThreadPoolExecutor(max_workers=mw) as ex:

        futures = {

            ex.submit(_naver_blog_search_total, client_id, client_secret, rk): it

            for it, rk in pairs

        }

        for fut in as_completed(futures):

            it = futures[fut]

            tot, _err = fut.result()

            _blog_enrich_apply_total(it, tot)





def _retry_blog_misses_parallel(

    miss_items: list[dict],

    client_id: str,

    client_secret: str,

    max_workers: int,

) -> None:

    """1차에서 blogTotal 이 비었던 키워드만 짧게 쉰 뒤 재시도(429 등 일시 실패 보완)."""

    pairs = [

        (it, str(it.get("relKeyword", "")).strip())

        for it in miss_items

        if str(it.get("relKeyword", "")).strip()

    ]

    if not pairs:

        return

    mw = max(2, min(int(max_workers), 16))

    time.sleep(0.35)

    with ThreadPoolExecutor(max_workers=mw) as ex:

        futures = {

            ex.submit(_naver_blog_search_total, client_id, client_secret, rk): it

            for it, rk in pairs

        }

        for fut in as_completed(futures):

            it = futures[fut]

            tot, _err = fut.result()

            if tot is not None:

                _blog_enrich_apply_total(it, tot)





def _enrich_keyword_rows_blog_supply(

    rows: list[dict],

    client_id: str,

    client_secret: str,

    delay_s: float,

    limit: int,

    warnings: list[str],

    blog_workers: int = 12,

) -> None:

    if not client_id or not client_secret:

        for item in rows:

            item["blogTotal"] = None

            item["monthlySearchSum"] = _naver_searchad_qc_to_num(item.get("monthlyPcQcCnt")) + _naver_searchad_qc_to_num(

                item.get("monthlyMobileQcCnt")

            )

            item["competitionRatio"] = None

        for item in rows:

            _apply_blog_market_comp_fields(item)

        return

    head = rows[:limit]

    _enrich_blog_totals_parallel(head, client_id, client_secret, blog_workers)

    misses = [

        it

        for it in head

        if str(it.get("relKeyword", "")).strip() and it.get("blogTotal") is None

    ]

    if misses:

        _retry_blog_misses_parallel(misses, client_id, client_secret, blog_workers)

    for item in rows[limit:]:

        pc = _naver_searchad_qc_to_num(item.get("monthlyPcQcCnt"))

        mo = _naver_searchad_qc_to_num(item.get("monthlyMobileQcCnt"))

        item["monthlySearchSum"] = pc + mo

        item["blogTotal"] = None

        item["competitionRatio"] = None

    for item in rows:

        _apply_blog_market_comp_fields(item)





def _json_response(payload: dict, status: int = 200) -> Response:

    """jsonify 대신 사용 — API 응답에 비직렬화 타입이 섞여도 HTML 500 대신 JSON으로 떨어짐."""

    return Response(

        json.dumps(payload, ensure_ascii=False, default=str),

        status=status,

        mimetype="application/json; charset=utf-8",

    )





# ?? Flask ?우????????????????????????????????????????????????????



@app.route("/")

def index():

    return render_template(

        "index.html",

        startup_hints_inline=_collect_chrome_startup_hints(),

        chrome_remote_addr=_chrome_remote_debugging_addr(),

    )





@app.route("/naver_keyword_tool", methods=["POST"])

def naver_keyword_tool():

    """검색광고 키워드 도구 API — 연관 키워드·월간 검색량(showDetail=1)."""

    warnings: list[str] = []

    try:

        data = request.get_json(silent=True) or {}

        raw = data.get("hint_keywords", data.get("hintKeywords", ""))

        if isinstance(raw, list):

            hints = [str(x).strip() for x in raw if str(x).strip()]

        else:

            hints = [x.strip() for x in re.split(r"[\n,]+", str(raw)) if x.strip()]

        hints, _ = _naver_sanitize_hint_tokens(hints)

        if not hints:

            return _json_response({"error": "시드 키워드를 한 개 이상 입력해 주세요.", "rows": []}, 400)

        try:

            delay_ms = int(data.get("delay_ms", 400) or 400)

        except (TypeError, ValueError):

            delay_ms = 400

        delay_ms = max(0, min(delay_ms, 5000))

        show_detail = 1 if data.get("show_detail", data.get("showDetail", 1)) in (1, True, "1", "true") else 0

        max_hints = 25

        if len(hints) > max_hints:

            hints = hints[:max_hints]

        chunk_size = 5

        merged: dict[str, dict] = {}

        batches: list[dict] = []

        for ci in range(0, len(hints), chunk_size):

            chunk = ",".join(hints[ci : ci + chunk_size])

            if ci > 0 and delay_ms:

                time.sleep(delay_ms / 1000.0)

            status, body = _naver_keywordstool_request(chunk, show_detail=show_detail)

            if not isinstance(body, dict):

                body = {"message": "응답 본문이 객체(JSON)가 아닙니다.", "_preview": str(body)[:400]}

            batches.append({"hintKeywords": chunk, "http_status": status, "body": body})

            if status != 200:

                err_msg = body.get("message") or body.get("title") or str(body)[:400]

                return _json_response(

                    {

                        "error": f"검색광고 API 오류 (HTTP {status}): {err_msg}",

                        "rows": list(merged.values()),

                        "batches": batches,

                        "warnings": warnings,

                    },

                    502,

                )

            klist = body.get("keywordList")

            if not isinstance(klist, list):

                return _json_response(

                    {

                        "error": "응답에 keywordList가 없습니다.",

                        "rows": [],

                        "batches": batches,

                        "warnings": warnings,

                    },

                    502,

                )

            for item in klist:

                if not isinstance(item, dict):

                    continue

                rk = str(item.get("relKeyword", "")).strip()

                if rk:

                    merged[rk] = item

        rows_list = list(merged.values())



        open_cid = (os.environ.get("NAVER_OPEN_CLIENT_ID") or "").strip()

        open_sec = (os.environ.get("NAVER_OPEN_CLIENT_SECRET") or "").strip()

        try:

            blog_limit = int(data.get("blog_limit", 200) or 200)

        except (TypeError, ValueError):

            blog_limit = 200

        blog_limit = max(1, min(blog_limit, 300))

        try:

            blog_workers = int(data.get("blog_workers", 0) or 0)

        except (TypeError, ValueError):

            blog_workers = 0

        if blog_workers <= 0:

            try:

                blog_workers = int(os.environ.get("NAVER_BLOG_FETCH_WORKERS", "12") or "12")

            except (TypeError, ValueError):

                blog_workers = 12

        blog_workers = max(2, min(blog_workers, 20))

        try:

            blog_delay = float(delay_ms) / 2000.0

        except Exception:

            blog_delay = 0.12

        if open_cid and open_sec:

            _enrich_keyword_rows_blog_supply(

                rows_list, open_cid, open_sec, blog_delay, blog_limit, warnings, blog_workers

            )

        else:

            _enrich_keyword_rows_blog_supply(rows_list, "", "", 0, blog_limit, warnings, blog_workers)



        return _json_response(

            {

                "rows": rows_list,

                "batches": batches,

                "warnings": warnings,

                "blog_openapi_configured": bool(open_cid and open_sec),

            }

        )

    except RuntimeError as e:

        return _json_response({"error": str(e), "rows": [], "warnings": warnings}, 503)

    except requests.RequestException as e:

        return _json_response({"error": f"HTTP 요청 실패: {e}", "rows": [], "warnings": warnings}, 502)

    except Exception as e:

        traceback.print_exc()

        return _json_response({"error": str(e), "rows": [], "warnings": warnings}, 500)





@app.route("/generate", methods=["POST"])

def generate():

    data = request.get_json()

    clinic_name = data.get("clinic_name", "").strip()



    # keywords(list) ?는 keyword(string) 모두 ?용

    raw_kw = data.get("keywords", data.get("keyword", ""))

    if isinstance(raw_kw, list):

        keywords = [k.strip() for k in raw_kw if str(k).strip()]

    else:

        keywords = [k.strip() for k in str(raw_kw).split(",") if k.strip()]



    if not keywords:

        return jsonify({"error": "키워드를 입력해주세요."}), 400

    target_chars = _parse_target_char_count(data.get("target_char_count"))

    try:

        result = generate_blog_content(keywords, clinic_name, target_char_count=target_chars)

        return jsonify(result)

    except Exception as e:

        return jsonify({"error": str(e)}), 500





@app.route("/generate_cardnews", methods=["POST"])

def generate_cardnews():

    """카드?스 ??지 ?로????AI가 ??지 ?고 블로?본문 ?성"""

    data = request.get_json()

    clinic_name = data.get("clinic_name", "").strip()

    images_raw = data.get("images", [])  # [{filename, b64data, mime_type}]



    if not images_raw:

        return jsonify({"error": "카드뉴스 이미지를 업로드해 주세요."}), 400



    # ?션 ?렉?리????지 ???(Selenium ?로?용)

    session_id = uuid.uuid4().hex[:12]

    tmp_session_dir = os.path.join(TMP_DIR, session_id)

    os.makedirs(tmp_session_dir, exist_ok=True)



    # base64 ?코????멀?모???트 구성

    content_parts = []

    saved_filenames = []

    for idx, img in enumerate(images_raw, 1):

        try:

            img_bytes = base64.b64decode(img["b64data"])

            mime_type = img.get("mime_type", "image/jpeg")

            filename = img.get("filename") or f"image_{idx}.jpg"

            # 로컬 ???

            with open(os.path.join(tmp_session_dir, filename), "wb") as fh:

                fh.write(img_bytes)

            saved_filenames.append(filename)

            content_parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))

            content_parts.append(types.Part.from_text(text=f"(카드뉴스 {idx}번째 이미지: {filename})"))

        except Exception:

            pass



    if not content_parts:

        return jsonify({"error": "이미지 데이터를 읽을 수 없습니다."}), 400



    # ??된 ?롬?트 고정 ?용 (치과명? 별도 지?로 ?달)

    system_instr = CARDNEWS_SYSTEM_INSTRUCTION

    if clinic_name:

        system_instr += f"\n\n치과명은 {clinic_name} 입니다. 제목과 본문에 자연스럽게 포함하세요."



    image_list_str = ", ".join(saved_filenames)

    target_chars = _parse_target_char_count(data.get("target_char_count"))

    user_cn_text = (

        "위 카드뉴스 이미지들의 내용을 바탕으로 블로그 본문을 작성해주세요.\n"

        "도입부(첫 소제목 1. 전) 마지막에는 반드시 첫 번째 파일을 "

        f"[이미지: {saved_filenames[0]}] 한 줄로 넣고, "

        "그 다음 소제목 1~4 각 본문 뒤에 남은 이미지를 내용에 맞게 배치하세요.\n"

        f"아래 {len(saved_filenames)}개 파일명을 모두 빠짐없이 정확히 한 번씩 [이미지: 파일명]으로 쓰세요(순서): "

        f"{image_list_str}"

    )

    if target_chars:

        user_cn_text += (

            f"\n\n[분량 제약 — 필수] 공백 제외·이미지 전용 줄 제외 기준으로 본문이 **약 {target_chars}자**,"

            f" 같은 기준 **최소 {int(target_chars * 0.9)}자 이상**이 되게 작성하세요. 짧으면 요구 미충족입니다."

            f" '[이미지: 파일명]' 줄은 글자 수에서 제외합니다."

        )

    content_parts.append(types.Part.from_text(text=user_cn_text))



    try:

        cur_model = MULTIMODAL_MODEL

        for attempt in range(1, 6):

            try:

                response = client.models.generate_content(

                    model=cur_model,

                    contents=content_parts,

                    config=types.GenerateContentConfig(system_instruction=system_instr),

                )

                break

            except Exception as e:

                if ("503" in str(e) or "UNAVAILABLE" in str(e)) and attempt < 5:

                    if attempt >= 3:

                        cur_model = MULTIMODAL_FALLBACK

                    time.sleep(2 ** attempt)

                else:

                    raise



        raw = response.text

        title = clinic_name or "치과"

        body = raw



        for line in raw.splitlines():

            stripped = re.sub(r'^제목\s*:\s*', '', line)

            if stripped != line:

                title = stripped.strip()

                body = raw[raw.index(line) + len(line):].strip()

                break



        body = strip_markdown(body)

        body = normalize_image_markers(body, saved_filenames)



        # AI가 ?목 줄을 ???었??????본문 ?문장???목?로 ?용

        if title == (clinic_name or "치과"):

            for line in body.splitlines():

                line = line.strip()

                if line and not line.startswith("[이미지"):

                    title = line[:50]

                    break



        # ?동 ?정 ?스 (치과??일, ??, 말투 ????

        if clinic_name:

            title, body = _apply_fixes(title, body, clinic_name)

            body = normalize_image_markers(body, saved_filenames)



        body = ensure_cardnews_image_markers(body, saved_filenames)



        if target_chars:

            m_cn = _blog_body_metric_chars(body)

            if m_cn < int(target_chars * 0.88):

                prefix_parts = content_parts[:-1] if len(content_parts) > 1 else None

                title, body = _expand_blog_body_for_length(

                    title,

                    body,

                    target_chars,

                    m_cn,

                    system_instr,

                    cur_model,

                    prefix_parts,

                )

                body = strip_markdown(body)

                body = normalize_image_markers(body, saved_filenames)

                if clinic_name:

                    title, body = _apply_fixes(title, body, clinic_name)

                    body = normalize_image_markers(body, saved_filenames)

                body = ensure_cardnews_image_markers(body, saved_filenames)



        return jsonify({

            "title": title,

            "body": body,

            "images": saved_filenames,

            "cardnews_session": session_id,

            "clinic_name": clinic_name,

        })

    except Exception as e:

        traceback.print_exc()

        return jsonify({"error": str(e)}), 500





@app.route("/clinics")

def list_clinics():

    if not os.path.isdir(SRC_DIR):

        return jsonify({"clinics": []})

    clinics = sorted(

        d for d in os.listdir(SRC_DIR)

        if os.path.isdir(os.path.join(SRC_DIR, d))

    )

    return jsonify({"clinics": clinics})





@app.route("/src_image/<clinic_name>/<filename>")

def serve_src_image(clinic_name, filename):

    # 1?위: src/{clinic_name}/img/

    clinic_img_dir = os.path.join(SRC_DIR, clinic_name, "img")

    if os.path.isfile(os.path.join(clinic_img_dir, filename)):

        return send_from_directory(clinic_img_dir, filename)

    # 2?위: src/img/ 공용 ?더 ?백

    fallback_dir = os.path.join(SRC_DIR, "img")

    if os.path.isfile(os.path.join(fallback_dir, filename)):

        return send_from_directory(fallback_dir, filename)

    # ?으?404

    return "", 404





@app.route("/tmp_image/<session_id>/<filename>")

def serve_tmp_image(session_id, filename):

    img_dir = os.path.join(TMP_DIR, session_id)

    return send_from_directory(img_dir, filename)





@app.route("/account_settings", methods=["GET"])

def account_settings_get():

    resp = jsonify(_account_settings_payload())

    resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"

    return resp





@app.route("/account_settings", methods=["POST"])

def account_settings_post():

    try:

        from dotenv import set_key

    except ImportError:

        return jsonify({"error": "python-dotenv가 필요합니다."}), 500



    data = request.get_json(silent=True) or {}

    naver_id = str(data.get("naver_id") or "").strip()

    clinic_name = str(data.get("clinic_name") or "").strip()

    naver_pw_raw = data.get("naver_pw")

    naver_pw = "" if naver_pw_raw is None else str(naver_pw_raw)



    if not naver_id:

        return jsonify({"error": "네이버 아이디를 입력해주세요."}), 400



    if not os.path.isfile(_DOTENV_PATH):

        try:

            with open(_DOTENV_PATH, "w", encoding="utf-8") as f:

                f.write("")

        except OSError as e:

            return jsonify({"error": f".env 파일을 만들 수 없습니다: {e}"}), 500



    try:

        set_key(_DOTENV_PATH, "NAVER_ID", naver_id, quote_mode="always", encoding="utf-8")

        set_key(_DOTENV_PATH, "CLINIC_NAME", clinic_name, quote_mode="always", encoding="utf-8")

        set_key(_DOTENV_PATH, "NAVER_PW", naver_pw.strip(), quote_mode="always", encoding="utf-8")

    except OSError as e:

        return jsonify({"error": str(e)}), 500



    refresh_env_credentials()

    return jsonify({"ok": True, "message": ".env에 저장했습니다."})





@app.route("/accounts", methods=["GET"])

def accounts_list():

    d = load_accounts_json()

    active_id = str(d.get("active_account_id") or "").strip()

    resp = jsonify({"accounts": d.get("accounts") or [], "active_account_id": active_id})

    resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"

    return resp





@app.route("/accounts", methods=["PUT"])

def accounts_put():

    data = request.get_json(silent=True) or {}

    rows = data.get("accounts")

    if not isinstance(rows, list):

        return jsonify({"error": "accounts 배열이 필요합니다."}), 400

    accounts = _normalize_accounts_rows(rows)

    active_raw = data.get("active_account_id")

    active_id = str(active_raw).strip() if active_raw is not None else ""

    if active_id:

        valid_ids = {a["id"] for a in accounts}

        if active_id not in valid_ids:

            active_id = ""

    payload = {"version": 1, "accounts": accounts, "active_account_id": active_id}

    save_accounts_json(payload)

    return jsonify({"ok": True, "accounts": accounts, "active_account_id": active_id})





def _collect_chrome_startup_hints() -> list[dict]:

    """Chrome 프로필 잠금(SingletonLock) 시 메시지 목록(메인 페이지 SSR + /startup_hints 공용)."""

    if _chrome_remote_debugging_addr():

        return []

    hints: list[dict] = []

    try:

        if _chrome_singleton_lock_present(CHROME_PROFILE_DIR):

            hints.append(

                {

                    "code": "chrome_profile_default",

                    "message": "[기본 계정] " + MSG_CHROME_PROFILE_IN_USE,

                }

            )

    except Exception:

        pass

    try:

        for acc in load_accounts_json().get("accounts") or []:

            if not isinstance(acc, dict):

                continue

            aid = str(acc.get("id") or "").strip()

            if not aid:

                continue

            pd = os.path.abspath(os.path.join(CHROME_ACCOUNTS_ROOT, aid))

            if not os.path.isdir(pd):

                continue

            if not _chrome_singleton_lock_present(pd):

                continue

            label = (str(acc.get("clinic_name") or "").strip() or str(acc.get("label") or "").strip() or aid)

            hints.append(

                {

                    "code": "chrome_profile_account",

                    "account_id": aid,

                    "message": f"[계정: {label}] " + MSG_CHROME_PROFILE_IN_USE,

                }

            )

    except Exception:

        pass

    return hints





@app.route("/ui_config")

def ui_config():

    """프론트 초기화용(하위 호환): 치과명·자격 증명 존재 여부."""

    p = _account_settings_payload()

    return jsonify(

        {

            "default_clinic_name": p["default_clinic_name"],

            "has_naver_creds": p["has_naver_creds"],

        }

    )





@app.route("/startup_hints")

def startup_hints():

    """Chrome 프로필 잠금(SingletonLock) 시 화면 상단 안내용."""

    return jsonify({"hints": _collect_chrome_startup_hints()})





@app.route("/post_queue", methods=["POST"])

def post_queue():

    if queue_status["state"] == "running":

        return jsonify({"error": "이미 포스팅이 진행 중입니다."}), 400



    data = request.get_json()

    items = data.get("items", [])



    if not items:

        return jsonify({"error": "포스팅할 항목이 없습니다."}), 400



    for it in items:

        ak, _, nid, npw = _resolve_item_account(it)

        if ak is None:

            return jsonify({"error": f"알 수 없는 계정(account_id): {(it.get('account_id') or it.get('accountId') or '').strip()}"}), 400

        if not nid or not (npw or "").strip():

            return jsonify({"error": "선택한 계정에 네이버 아이디·비밀번호가 없습니다. .env 또는 추가 계정을 확인하세요."}), 400



    thread = threading.Thread(target=run_queue, args=(items,), daemon=True)

    thread.start()

    return jsonify({"message": "포스팅 작업 시작됨"})





@app.route("/status")

def status():

    return jsonify(queue_status)





@app.route("/review", methods=["POST"])

def review_content():

    """작성된 블로그 본문 자동 검수 (치과명 일치, 구조, 말투)"""

    data = request.get_json()

    title = data.get("title", "")

    body = data.get("body", "")

    clinic_name = data.get("clinic_name", "")



    prompt = f"""아래 블로그 글을 꼼꼼하게 검수해줘. 치과명은 "{clinic_name}"이어야 해.



검수 항목:

1. 치과명이 본문에서 올바르게 들어갔는지 (다른 치과명이 섞여 있으면 지적)

2. 오타 및 어색한 문장

3. 제목-본문-소제목 구조가 갖춰졌는지

4. 말투가 통일됐는지 (반말/존댓말 혼용 여부)



--- 제목 ---

{title}



--- 본문 ---

{body}



발견된 문제를 항목별로 간단하게 한국어로 나열해줘. 문제가 없으면 "이상없음"이라고만 해줘. 설명 없이 결과만"""



    try:

        response = client.models.generate_content(

            model=MODEL,

            contents=prompt,

        )

        raw = response.text.strip()

        if "?상?음" in raw:

            return jsonify({"ok": True, "issues": []})

        issues = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()]

        return jsonify({"ok": False, "issues": issues})

    except Exception as e:

        return jsonify({"ok": None, "issues": [], "error": str(e)})





if __name__ == "__main__":

    multiprocessing.freeze_support()



    try:




        # 새 프로세스에서 드라이버 맵이 비어 있도록 보장 (exe/스크립트 공통)
        try:

            if _remote_attached_driver is not None:

                try:

                    _remote_attached_driver.quit()

                except Exception:

                    pass

                _remote_attached_driver = None

            for _drv in list(_account_drivers.values()):

                try:

                    _drv.quit()

                except Exception:

                    pass

            _account_drivers.clear()

        except Exception:

            pass



        def _open_browser():

            time.sleep(2)

            import webbrowser

            webbrowser.open("http://127.0.0.1:5000")



        threading.Thread(target=_open_browser, daemon=True).start()



        print("=" * 45)

        print("  Blog Tool Server starting...")

        print("  URL : http://127.0.0.1:5000")

        if (os.environ.get("CHROME_REMOTE_DEBUGGING") or "").strip():

            print("  Chrome : 원격 연결(CHROME_REMOTE_DEBUGGING) — 새 창을 띄우지 않고 기존 Chrome에 붙습니다.")

        print("  (Close this window to stop the server)")

        print("=" * 45)



        app.run(debug=False, use_reloader=False, port=5000, threaded=True)



    except Exception as e:

        _err = traceback.format_exc()

        print("\n[ERROR]", _err)

        input("\nPress Enter to exit...")



