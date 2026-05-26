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

import uuid



import pyperclip

from flask import Flask, jsonify, render_template, request, send_from_directory

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





app = Flask(__name__, template_folder=os.path.join(_BUNDLE_DIR, "templates"))



SRC_DIR = os.path.join(BASE_DIR, "src")

TMP_DIR = os.path.join(BASE_DIR, "tmp")



class _NoStatusLog(logging.Filter):

    def filter(self, record):

        return "GET /status" not in record.getMessage()



logging.getLogger("werkzeug").addFilter(_NoStatusLog())



API_KEY = "AIzaSyB-CcTKke6r_OwqCRcSI8Pi7TUkGmTeId0"

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





def generate_blog_content(keywords: list, clinic_name: str = "", max_retries: int = 5) -> dict:

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

    "items": [],           # [{title, state, message}, ...]

}





# ?? 치과 ?로??관??????????????????????????????????????????????



PROFILES_DIR  = os.path.join(BASE_DIR, "clinic_profiles")

PROFILES_FILE = os.path.join(BASE_DIR, "profiles.json")

os.makedirs(PROFILES_DIR, exist_ok=True)





def load_profiles() -> dict:

    if not os.path.isfile(PROFILES_FILE):

        return {}

    try:

        with open(PROFILES_FILE, encoding="utf-8") as f:

            raw = json.load(f)

    except Exception:

        return {}

    if not isinstance(raw, dict):

        return {}

    out: dict = {}

    changed = False

    for name, p in raw.items():

        if not isinstance(p, dict):

            out[name] = p

            continue

        p2 = dict(p)

        if "connected" in p2:

            changed = True

        p2.pop("connected", None)

        pd = (p2.get("profile_dir") or "").strip()

        if pd:

            pd_orig = pd

            if not os.path.isabs(pd):

                pd = os.path.normpath(os.path.join(BASE_DIR, pd))

            else:

                pd = os.path.normpath(os.path.abspath(pd))

            if pd != (p.get("profile_dir") or "").strip():

                changed = True

            p2["profile_dir"] = pd

        out[name] = p2

    if changed:

        try:

            save_profiles(out)

        except Exception:

            pass

    return out





def save_profiles(profiles: dict):

    """profiles.json 저장. connected 는 메모리 전용이므로 파일에 쓰지 않음(예전 true 캐시 방지)."""

    to_save: dict = {}

    for k, v in profiles.items():

        if isinstance(v, dict):

            d = dict(v)

            d.pop("connected", None)

            to_save[k] = d

        else:

            to_save[k] = v

    with open(PROFILES_FILE, "w", encoding="utf-8") as f:

        json.dump(to_save, f, ensure_ascii=False, indent=2)





# ?? Selenium ?????????????????????????????????????????????????????



CHROME_PROFILE_DIR = os.path.join(BASE_DIR, "chrome_profile")

_driver = None

_profile_drivers: dict = {}

_profile_processes: dict = {}




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





def _assign_debug_port(profiles: dict, name: str) -> int:

    """?로?에 ?격 ?버??트 ?당 (?? ?으?그??반환)"""

    if "debug_port" in profiles.get(name, {}):

        return profiles[name]["debug_port"]

    used = {p.get("debug_port") for p in profiles.values() if "debug_port" in p}

    port = 9223

    while port in used:

        port += 1

    profiles[name]["debug_port"] = port

    save_profiles(profiles)

    return port





def _launch_chrome_subprocess(name: str, profile_dir: str, port: int, start_url: str = "") -> None:

    """?반 Chrome???격 ?버??트??행 (?동??감? ?음 ??쿠키 ?상 ???"""

    chrome_exe = find_chrome_executable()

    if not chrome_exe:

        raise RuntimeError("Chrome ?행 ?일??찾을 ???습?다.")



    # 기존 ?로?스 종료 (?으?

    if name in _profile_processes:

        try:

            _profile_processes[name].terminate()

        except Exception:

            pass

        del _profile_processes[name]



    # lock ?일??리 (로그???션/쿠키???? 건드리? ?음)

    _clean_profile_for_selenium(profile_dir, preserve_login=True)

    time.sleep(1)



    cmd = [

        chrome_exe,

        f"--remote-debugging-port={port}",

        f"--user-data-dir={profile_dir}",

        "--profile-directory=Default",

        "--no-first-run",

        "--no-default-browser-check",

        "--disable-session-crashed-bubble",

        "--disable-infobars",

        "--disable-blink-features=AutomationControlled",

        "--lang=ko-KR",

        "--window-size=1366,900",

    ]

    if start_url:

        cmd.append(start_url)



    proc = subprocess.Popen(

        cmd,

        # Flask ?시??종료 ?에??Chrome???아?도??립 ?로?스??행

        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,

        close_fds=True,

    )

    _profile_processes[name] = proc





def _attach_selenium(port: int, wait_sec: int = 8):

    """?행 중인 Chrome???격 ?버??트??Selenium ?결"""

    import socket

    deadline = time.time() + wait_sec

    while time.time() < deadline:

        try:

            s = socket.socket()

            s.settimeout(1)

            s.connect(("127.0.0.1", port))

            s.close()

            break

        except Exception:

            time.sleep(0.5)



    opts = Options()

    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    # navigator.webdriver ?거 (Naver 감? 방?)

    try:

        driver.execute_cdp_cmd(

            "Page.addScriptToEvaluateOnNewDocument",

            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},

        )

    except Exception:

        pass

    return driver





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





def _quit_profile_driver(name: str) -> None:

    """프로필용 Chrome을 종료할 때 about:blank 후 quit — 쿠키/LocalStorage 디스크 반영 여지."""

    driver = _profile_drivers.pop(name, None)

    if driver is None:

        return

    try:

        driver.get("about:blank")

    except Exception:

        pass

    time.sleep(0.45)

    try:

        driver.quit()

    except Exception:

        pass





def _create_profile_driver(profile_dir: str):

    """?로???더?Selenium Chrome ?행 ??쿠키 보존, ?동??감? 방?"""

    _clean_profile_for_selenium(profile_dir, preserve_login=True)

    time.sleep(0.5)

    opts = Options()

    opts.add_argument(f"--user-data-dir={profile_dir}")

    opts.add_argument("--profile-directory=Default")

    _add_chrome_stealth_options(opts)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    driver.execute_cdp_cmd(

        "Page.addScriptToEvaluateOnNewDocument",

        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},

    )

    return driver





def get_driver(profile_dir: str = ""):

    """profile_dir 지정 시 해당 Chrome 프로필 사용, 없으면 기본 프로필"""

    global _driver

    target_dir = profile_dir or CHROME_PROFILE_DIR

    try:

        if _driver is not None:

            _ = _driver.current_url

            if not profile_dir:

                return _driver

            try:

                _driver.quit()

            except Exception:

                pass

            _driver = None

    except Exception:

        _driver = None



    # ?로??지????lock ?일??리 (로그???션 ??)

    if profile_dir:

        _clean_profile_for_selenium(profile_dir, preserve_login=True)

        time.sleep(1)



    opts = Options()

    opts.add_argument(f"--user-data-dir={target_dir}")

    opts.add_argument("--profile-directory=Default")

    opts.add_argument("--disable-extensions")

    _add_chrome_stealth_options(opts)



    _driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    _driver.execute_cdp_cmd(

        "Page.addScriptToEvaluateOnNewDocument",

        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},

    )

    return _driver





def _is_on_login_page(driver) -> bool:

    try:

        url = driver.current_url

        return "nidlogin" in url or "nid.naver.com" in url

    except Exception:

        return True





def auto_login(driver, naver_id: str, naver_pw: str) -> bool:

    """클립보드 붙여넣기 방식으로 아이디 자동 로그인"""

    try:

        # ??커???보 (백그?운???행 ??Ctrl+V가 ?른 창으?가??문제 방?)

        driver.maximize_window()

        driver.switch_to.window(driver.window_handles[0])

        time.sleep(0.3)



        # 로그???이지??동

        if not _is_on_login_page(driver):

            driver.get("https://nid.naver.com/nidlogin.login")

            time.sleep(2)



        pyperclip.copy("")   # ?립보드 초기??



        # ?이???력 ??JS ?릭?로 ?커???실??

        id_input = WebDriverWait(driver, 10).until(

            EC.element_to_be_clickable((By.ID, "id"))

        )

        driver.execute_script("arguments[0].click();", id_input)

        time.sleep(0.3)

        pyperclip.copy(naver_id)

        id_input.send_keys(Keys.CONTROL, "v")

        time.sleep(1)



        # 비?번호 ?력 ??JS ?릭

        pw_input = driver.find_element(By.ID, "pw")

        driver.execute_script("arguments[0].click();", pw_input)

        time.sleep(0.3)

        pyperclip.copy(naver_pw)

        pw_input.send_keys(Keys.CONTROL, "v")

        time.sleep(1)



        # ?터?로 로그??(버튼 ?릭보다 ?정??

        pw_input.send_keys(Keys.ENTER)

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

        queue_status["message"] = "? ?동 로그???도 ?.."

        if auto_login(driver, naver_id, naver_pw):

            if is_naver_logged_in(driver):

                queue_status["message"] = "???동 로그???료!"

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

            queue_status["message"] = "로그???료!"

            driver.get("https://blog.naver.com/GoBlogWrite.naver")

            time.sleep(2)

            return True

        time.sleep(2)

    queue_status.update({"state": "error", "message": "로그???간 초과 (3?. ?시 ?도?주?요."})

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







def _upload_image(driver, img_abs_path: str) -> bool:

    """SE3 ?디?에 로컬 ??지 ?입 (iframe ?? 컨텍?트?서 ?출)"""

    try:

        # ??지 ?바 버튼 ?릭

        img_btn = WebDriverWait(driver, 10).until(

            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-name='image']"))

        )

        driver.execute_script("arguments[0].click();", img_btn)

        time.sleep(1.5)



        # ?업 ?이?에??"?일 ?리? ??버튼 ?릭 (?으?

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

                    time.sleep(0.8)

                    break

            except Exception:

                pass



        # ?겨?input[type=file]????경로 직접 ?송

        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")

        sent = False

        for fi in file_inputs:

            try:

                driver.execute_script(

                    "arguments[0].style.cssText='display:block!important;"

                    "visibility:visible!important;opacity:1!important;';",

                    fi,

                )

                fi.send_keys(img_abs_path)

                sent = True

                time.sleep(4)  # ?로???료 ??

                break

            except Exception:

                pass



        if not sent:

            ActionChains(driver).send_keys(Keys.ESCAPE).perform()

            return False



        # "?인" / "?입" 버튼???으??릭

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

                time.sleep(2)

                break

            except Exception:

                pass



        # ?시 ?린 OS ?일 ?기 ?이?로??기 (?목??"?기"??창만)

        try:

            import ctypes

            hwnd = ctypes.windll.user32.FindWindowW(None, "열기")

            if hwnd:

                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE

                time.sleep(0.3)

        except Exception:

            pass



        time.sleep(2)  # ??지 ?더???

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

    """선택된 카드들을 프로필별로 그룹화하여 순차 포스팅"""

    queue_status.update({

        "state": "running",

        "message": "브라?? ?인 ?..",

        "current": 0,

        "total": len(items),

        "items": [{"title": it["title"], "state": "pending", "message": ""} for it in items],

    })



    try:

        profiles = load_profiles()

        global _profile_drivers



        # ?로?별 그룹??(profile_name ?는 ??? "default" 그룹)

        groups: dict[str, list] = {}

        for it in items:

            key = it.get("profile_name") or "default"

            groups.setdefault(key, []).append(it)



        # ?? ?스???? ?결??계정 ?라?버 ?인 ??????????????????????

        missing_browsers = []

        for gk in list(groups.keys()):

            if gk == "default":

                continue

            existing = _profile_drivers.get(gk)

            if existing:

                try:

                    _ = existing.current_url

                    continue   # ?아?음 ??OK

                except Exception:

                    _profile_drivers.pop(gk, None)

            missing_browsers.append(gk)



        if missing_browsers:

            names = ", ".join(missing_browsers)

            queue_status.update({

                "state": "error",

                "message": f"⚠️ [{names}] 브라우저가 연결되지 않았습니다.\n치과 계정 관리에서 '연결하기' 후 로그인하고 '연결 확인'을 먼저 해주세요.",

            })

            return

        # ????????????????????????????????????????????????????????????



        global_idx = 0

        for group_key, group_items in groups.items():

            # ?로??Chrome ?렉?리 결정

            profile_dir = ""

            if group_key != "default" and group_key in profiles:

                profile_dir = profiles[group_key]["profile_dir"]

                queue_status["message"] = f"[{group_key}] 브라우저 확인 중.."

            else:

                queue_status["message"] = "브라우저 확인 중.."



            try:

                # ?결???로?? 로그?????려???라?버 ?사???도

                driver = None

                need_login_check = True



                if group_key != "default" and group_key in _profile_drivers:

                    existing = _profile_drivers[group_key]

                    try:

                        _ = existing.current_url   # ?아?는지 ?인

                        driver = existing

                        need_login_check = False   # ?아?는 ?라?버 ??로그???뢰

                        queue_status["message"] = f"[{group_key}] 브라우저 재사용 중.."

                    except Exception:

                        _profile_drivers.pop(group_key, None)

                        driver = None



                if driver is None:

                    driver = get_driver(profile_dir)

                    need_login_check = True



            except Exception as e:

                for it in group_items:

                    queue_status["items"][global_idx].update({"state": "error", "message": f"브라우저 오류: {str(e)[:60]}"})

                    global_idx += 1

                continue



            # ???라?버?로그???인 (쿠키 ?효?면 즉시 ?과, ?이??비번 ?으??동로그??

            if need_login_check:

                nid = profiles.get(group_key, {}).get("naver_id", "")

                npw = profiles.get(group_key, {}).get("naver_pw", "")

                if not ensure_logged_in(driver, nid, npw):

                    for it in group_items:

                        queue_status["items"][global_idx].update({"state": "error", "message": "로그???패"})

                        global_idx += 1

                    continue

                if group_key != "default":

                    _profile_drivers[group_key] = driver



            for item in group_items:

                title = item["title"]

                body = item["body"]

                clinic_name = item.get("clinic_name", "")

                cardnews_session = item.get("cardnews_session", "")

                if cardnews_session:

                    # 카드?스: ?시 ?더

                    img_dir = os.path.join(TMP_DIR, cardnews_session)

                elif clinic_name:

                    # ?워???성: src/{clinic_name}/img/ ?선, ?으?src/img/ ?백

                    clinic_img = os.path.join(SRC_DIR, clinic_name, "img")

                    img_dir = clinic_img if os.path.isdir(clinic_img) else os.path.join(SRC_DIR, "img")

                else:

                    img_dir = ""



                queue_status["current"] = global_idx + 1

                queue_status["message"] = f"[{group_key}] 포스팅 중.. ({global_idx + 1}/{len(items)})"

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

                    time.sleep(8)



                global_idx += 1



        done_count = sum(1 for it in queue_status["items"] if it["state"] == "done")

        queue_status.update({

            "state": "done",

            "message": f"완료! {done_count}/{len(items)} 포스팅됨",

        })



    except Exception as e:

        queue_status.update({"state": "error", "message": f"오류: {e}"})





# ?? Flask ?우????????????????????????????????????????????????????



@app.route("/")

def index():

    return render_template("index.html")





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

    try:

        result = generate_blog_content(keywords, clinic_name)

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

        return jsonify({"error": "카드?스 ??지??로?해주세??"}), 400



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

            content_parts.append(types.Part.from_text(text=f"(카드?스 {idx}번째 ??지: {filename})"))

        except Exception:

            pass



    if not content_parts:

        return jsonify({"error": "??지??을 ???습?다."}), 400



    # ??된 ?롬?트 고정 ?용 (치과명? 별도 지?로 ?달)

    system_instr = CARDNEWS_SYSTEM_INSTRUCTION

    if clinic_name:

        system_instr += f"\n\n치과명은 {clinic_name} 입니다. 제목과 본문에 자연스럽게 포함하세요."



    image_list_str = ", ".join(saved_filenames)

    content_parts.append(types.Part.from_text(

        text=(

            "위 카드뉴스 이미지들의 내용을 바탕으로 블로그 본문을 작성해주세요.\n"

            "도입부(첫 소제목 1. 전) 마지막에는 반드시 첫 번째 파일을 "

            f"[이미지: {saved_filenames[0]}] 한 줄로 넣고, "

            "그 다음 소제목 1~4 각 본문 뒤에 남은 이미지를 내용에 맞게 배치하세요.\n"

            f"아래 {len(saved_filenames)}개 파일명을 모두 빠짐없이 정확히 한 번씩 [이미지: 파일명]으로 쓰세요(순서): "

            f"{image_list_str}"

        )

    ))



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





@app.route("/profiles", methods=["GET"])

def get_profiles():

    profiles = load_profiles()

    # connected 는 이 프로세스의 _profile_drivers 로만 판단 (JSON 의 connected 무시)
    rows = []

    for name_key, p in profiles.items():

        if not isinstance(p, dict):

            continue

        row = dict(p)

        display_name = (row.get("name") or name_key or "").strip() or name_key

        if not row.get("name"):

            row["name"] = display_name

        row["connected"] = bool(

            name_key in _profile_drivers or display_name in _profile_drivers

        )

        rows.append(row)

    resp = jsonify({"profiles": rows})

    resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"

    resp.headers["Pragma"] = "no-cache"

    resp.headers["X-Profile-Drivers-Count"] = str(len(_profile_drivers))

    return resp





@app.route("/profiles", methods=["POST"])

def add_profile():

    data = request.get_json()

    name = data.get("name", "").strip()

    if not name:

        return jsonify({"error": "치과명을 ?력?주?요."}), 400

    profiles = load_profiles()

    if name in profiles:

        return jsonify({"error": "?? ?록??치과명입?다."}), 400

    folder_id = "clinic_" + uuid.uuid4().hex[:8]

    profile_dir = os.path.normpath(os.path.abspath(os.path.join(PROFILES_DIR, folder_id)))

    os.makedirs(profile_dir, exist_ok=True)

    profiles[name] = {

        "name": name,

        "profile_dir": profile_dir,

    }

    save_profiles(profiles)

    prof = dict(profiles[name])

    prof["connected"] = bool(name in _profile_drivers)

    return jsonify({"ok": True, "profile": prof})





@app.route("/profiles/<name>", methods=["DELETE"])

def delete_profile(name):

    import shutil

    profiles = load_profiles()

    if name not in profiles:

        return jsonify({"error": "?로?을 찾을 ???습?다."}), 404



    # ?아?는 ?라?버 종료 (Chrome ?로?스??subprocess가 관?

    if name in _profile_drivers:

        _quit_profile_driver(name)



    # Chrome subprocess 종료

    if name in _profile_processes:

        try:

            _profile_processes[name].terminate()

        except Exception:

            pass

        del _profile_processes[name]



    # ?로???더 ??

    profile_dir = profiles[name].get("profile_dir", "")

    if profile_dir and os.path.isdir(profile_dir):

        try:

            shutil.rmtree(profile_dir, ignore_errors=True)

        except Exception:

            pass



    del profiles[name]

    save_profiles(profiles)

    return jsonify({"ok": True})





def find_chrome_executable():

    candidates = [

        r"C:\Program Files\Google\Chrome\Application\chrome.exe",

        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",

        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),

    ]

    return next((p for p in candidates if os.path.isfile(p)), None)





@app.route("/profiles/<name>/connect", methods=["POST"])

def connect_profile(name):

    """프로필별 user-data-dir로 Chrome을 띄웁니다. 최초 1회 로그인 후에는 같은 폴더에 세션이 남습니다."""

    profiles = load_profiles()

    if name not in profiles:

        return jsonify({"error": "?로?을 찾을 ???습?다."}), 404



    profile_dir = profiles[name]["profile_dir"]



    # 기존 ?라?버 종료

    if name in _profile_drivers:

        _quit_profile_driver(name)



    try:

        driver = _create_profile_driver(profile_dir)

        # www.naver.com 에서 쿠키 적용 + DOM 지연 대기. 세션 쿠키(NID_*)가 있으면 HTML에 로그아웃 링크가
        # 아직 없어도 로그인된 것으로 본다. nidlogin 으로 바로 가면 세션이 있어도 폼이 뜨는 경우가 많음.

        driver.get("https://www.naver.com")

        session_ok = False

        for _ in range(6):

            time.sleep(1.0)

            try:

                src = driver.page_source

            except Exception:

                src = ""

            if _naver_logged_in_from_page_source(src) or _naver_session_cookies_present(driver):

                session_ok = True

                break

            try:

                cur = (driver.current_url or "")

            except Exception:

                cur = ""

            if "nid.naver.com" in cur or "nidlogin" in cur.lower():

                break

        try:

            cur = (driver.current_url or "")

        except Exception:

            cur = ""

        if (not session_ok) and ("nid.naver.com" not in cur) and ("nidlogin" not in cur.lower()):

            if not _naver_session_cookies_present(driver):

                driver.get("https://nid.naver.com/nidlogin.login")

        _profile_drivers[name] = driver

        return jsonify({

            "ok": True,

            "message": "브라우저가 열렸습니다.\n네이버 로그인 화면이 나오면 가능한 경우 「로그인 상태 유지」를 체크해 두세요.\n(저장된 세션이 있으면 네이버 메인에 머무르며, 자동으로 로그인 페이지로 넘기지 않습니다.)\n브라우저를 닫지 말고 '연결 확인'을 눌러주세요.\n\n※ 세션은 이 PC의 clinic_profiles 폴더에 저장됩니다."

        })

    except Exception as e:

        return jsonify({"error": str(e)}), 500





@app.route("/profiles/<name>/check_login", methods=["GET"])

def check_profile_login(name):

    """?려 ?는 Chrome(?격 ?버??서 로그???료 ?? ?인"""

    profiles = load_profiles()

    if name not in profiles:

        return jsonify({"error": "?로?을 찾을 ???습?다."}), 404



    driver = _profile_drivers.get(name)

    if driver is None:

        return jsonify({"logged_in": False, "message": "브라우저가 닫혔습니다. 연결하기를 다시 눌러주세요."})



    try:

        current = driver.current_url

    except Exception:

        _profile_drivers.pop(name, None)

        return jsonify({"logged_in": False, "message": "브라우저가 닫혔습니다. 연결하기를 다시 눌러주세요."})



    if "nidlogin.login" in current:

        return jsonify({"logged_in": False, "message": "아직 로그인 중입니다. 로그인 완료 후 다시 눌러주세요."})



    try:

        src = driver.page_source

    except Exception:

        src = ""

    if _naver_logged_in_from_page_source(src) or _naver_session_cookies_present(driver):

        return jsonify({"logged_in": True, "message": "연결 완료! 이제 포스팅 시 해당 계정이 사용됩니다."})



    return jsonify({"logged_in": False, "message": "네이버 로그인이 확인되지 않았습니다. 로그인 후 '연결 확인'을 다시 눌러주세요."})





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





@app.route("/post_queue", methods=["POST"])

def post_queue():

    if queue_status["state"] == "running":

        return jsonify({"error": "?? ?스?이 진행 중입?다."}), 400



    data = request.get_json()

    items = data.get("items", [])



    if not items:

        return jsonify({"error": "?스?할 ?????습?다."}), 400



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

            for _drv in list(_profile_drivers.values()):

                try:

                    _drv.quit()

                except Exception:

                    pass

        except Exception:

            pass

        _profile_drivers.clear()

        _profile_processes.clear()



        def _open_browser():

            time.sleep(2)

            import webbrowser

            webbrowser.open("http://127.0.0.1:5000")



        threading.Thread(target=_open_browser, daemon=True).start()



        print("=" * 45)

        print("  Blog Tool Server starting...")

        print("  URL : http://127.0.0.1:5000")

        print("  (Close this window to stop the server)")

        print("=" * 45)



        app.run(debug=False, use_reloader=False, port=5000)



    except Exception as e:

        _err = traceback.format_exc()

        print("\n[ERROR]", _err)

        input("\nPress Enter to exit...")



