import time
import pyperclip
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from config import Config


class NaverBlogDraftPublisher:
    """
    Windows Chrome 환경에서 네이버 로그인 우회, 스마트에디터 ONE 본문 작성,
    '임시저장'까지의 전 과정을 자동화하는 클래스입니다.

    실행 흐름:
        1. init_driver()        → undetected-chromedriver로 크롬 실행
        2. naver_login()        → 클립보드 우회 방식으로 봇 탐지 회피 로그인
        3. write_and_save_draft() → 에디터 진입 → 제목/본문 입력 → 임시저장
        4. quit_driver()        → 브라우저 안전 종료 (main.py의 finally에서 호출)
    """

    # =============================================
    # 스마트에디터 ONE CSS / XPath 셀렉터 상수
    # =============================================
    # [주의] 네이버 에디터 업데이트 시 셀렉터가 변경될 수 있습니다.
    # 실제 페이지 소스를 F12(DevTools)로 확인하여 아래 값을 교체하세요.

    # 제목 입력 플레이스홀더 (클릭하면 contenteditable 활성화)
    # F12 실측 확인값: .se-documentTitle .se-placeholder
    SELECTOR_TITLE = ".se-documentTitle .se-placeholder"

    # 본문 첫 번째 텍스트 블록 플레이스홀더
    # F12 실측 확인값: .se-component .se-placeholder 중 두 번째([1]) 요소가 본문
    # ※ 제목 입력 후 제목 placeholder가 사라지면 [0]이 본문이 되므로 두 전략을 모두 시도합니다.
    SELECTOR_BODY = ".se-component .se-placeholder"

    # 임시저장 팝업 취소 버튼 (이전 원고 불러오기 팝업)
    SELECTOR_POPUP_CANCEL = "//button[contains(@class, 'se-popup-button-cancel') or (contains(@class, 'cancel') and ancestor::*[contains(@class,'se-popup')])]"

    # 저장 버튼: F12 실측 확인값 — 클래스명 save_btn__bzc5B
    # '저장' 텍스트를 포함한 span의 부모 버튼을 타겟팅 (클래스명은 빌드마다 해시 변경 가능)
    SELECTOR_SAVE_BTN = "//span[normalize-space(text())='저장']/parent::button"

    # 저장 완료 토스트 알림 (저장 성공 시 화면에 잠시 나타나는 메시지 레이어)
    SELECTOR_SAVE_TOAST = (
        "//*[contains(@class,'se-save-result') or "
        "contains(text(),'임시저장') or "
        "contains(@class,'toast') and contains(.,'저장')]"
    )

    def __init__(self):
        self.naver_id = Config.NAVER_ID
        self.naver_pw = Config.NAVER_PW
        self.driver = None
        # Windows에서 Ctrl 조합키
        self._mod = Keys.CONTROL

    # --------------------------------------------------
    # 드라이버 생명주기
    # --------------------------------------------------

    def init_driver(self):
        """
        undetected-chromedriver로 봇 탐지를 우회하는 크롬 인스턴스를 초기화합니다.
        undetected-chromedriver는 Selenium의 WebDriver 시그니처를 난독화하여
        네이버의 자동화 탐지 로직을 통과합니다.
        """
        print("[엔진] Windows 크롬 자동화 브라우저를 구동합니다...")
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")       # 창 최대화
        options.add_argument("--disable-popup-blocking")  # 팝업 차단 해제

        self.driver = uc.Chrome(options=options)
        # implicitly_wait: 요소를 찾을 때 최대 5초 대기 (명시적 wait와 병행 사용)
        self.driver.implicitly_wait(5)
        print("[엔진] 드라이버 초기화 완료.")

    def quit_driver(self):
        """
        브라우저 세션을 안전하게 종료합니다.
        main.py의 finally 블록에서 호출하여 오류 발생 시에도 반드시 닫히도록 합니다.
        """
        if self.driver:
            self.driver.quit()
            self.driver = None
            print("[엔진] 크롬 브라우저를 안전하게 종료했습니다.")

    # --------------------------------------------------
    # 로그인
    # --------------------------------------------------

    def naver_login(self):
        """
        클립보드(Ctrl+V) 방식으로 ID/PW를 주입하여 봇 탐지를 우회합니다.
        send_keys()로 직접 타이핑하면 키 입력 패턴이 탐지될 수 있으므로
        pyperclip으로 값을 클립보드에 올린 뒤 붙여넣기합니다.
        """
        if not self.driver:
            raise RuntimeError("드라이버가 초기화되지 않았습니다. init_driver()를 먼저 호출하세요.")

        print("[인증] 네이버 로그인 페이지로 이동합니다.")
        self.driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(2)

        # 아이디 필드
        print("[인증] 아이디 입력 중...")
        id_input = self.driver.find_element(By.ID, "id")
        self._paste(self.naver_id, id_input)
        time.sleep(1)

        # 비밀번호 필드
        print("[인증] 비밀번호 입력 중...")
        pw_input = self.driver.find_element(By.ID, "pw")
        self._paste(self.naver_pw, pw_input)
        time.sleep(1)

        # 로그인 버튼 클릭
        self.driver.find_element(By.ID, "log.login").click()
        time.sleep(3)
        print("[인증] 로그인 완료.")

    # --------------------------------------------------
    # 에디터 진입 및 글 작성
    # --------------------------------------------------

    def write_and_save_draft(self, title: str, text_content: str) -> bool:
        """
        스마트에디터 ONE에 제목과 본문을 입력하고 임시저장을 실행합니다.

        매개변수:
            title (str)        : 블로그 포스팅 제목
            text_content (str) : 블로그 포스팅 본문 텍스트

        반환값:
            bool : 임시저장 성공 여부
        """
        print(f"[에디터] 글쓰기 페이지로 이동합니다.")
        self.driver.get(f"https://blog.naver.com/{self.naver_id}/postwrite")
        time.sleep(5)  # 스마트에디터 초기 로딩 대기

        # 스마트에디터가 iframe 내부에 렌더링되는 경우 iframe으로 전환
        self._switch_to_editor_frame()

        # 이전 임시 원고 불러오기 팝업 처리
        self._dismiss_draft_popup()

        try:
            # ---- 1. 제목 입력 ----
            print("[에디터] 제목 입력 중...")
            title_placeholder = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.SELECTOR_TITLE))
            )
            title_placeholder.click()
            time.sleep(0.8)
            # 클릭 후 포커스된 contenteditable 영역에 붙여넣기
            self._paste_to_active(title)
            time.sleep(1.5)

            # ---- 2. 본문 입력 ----
            print("[에디터] 본문 입력 중...")
            # 제목 입력 완료 후 제목 placeholder는 사라집니다.
            # 남은 .se-component .se-placeholder 중 첫 번째가 본문 블록입니다.
            body_placeholders = self.driver.find_elements(By.CSS_SELECTOR, self.SELECTOR_BODY)
            if not body_placeholders:
                raise NoSuchElementException(f"본문 셀렉터를 찾지 못했습니다: {self.SELECTOR_BODY}")
            # 제목 placeholder가 아직 남아 있으면 [1](두 번째)이 본문, 이미 사라졌으면 [0]이 본문
            body_target = body_placeholders[1] if len(body_placeholders) > 1 else body_placeholders[0]
            body_target.click()
            time.sleep(0.8)
            self._paste_to_active(text_content)
            time.sleep(2)

            # ---- 3. 임시저장 버튼 클릭 ----
            print("[에디터] 임시저장 버튼을 클릭합니다...")
            save_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, self.SELECTOR_SAVE_BTN))
            )
            # JavaScript 클릭: 버튼 위에 다른 요소(se-help-title 등)가 겹쳐 있어도
            # DOM 이벤트를 직접 발생시키므로 ElementClickInterceptedException을 우회합니다.
            self.driver.execute_script("arguments[0].click();", save_button)
            print("[에디터] 저장 버튼 클릭 완료.")

            # ---- 4. 저장 완료 토스트 알림 대기 및 확인 ----
            success = self._wait_for_save_toast()
            return success

        except Exception as error:
            print(f"[오류] 에디터 제어 또는 임시저장 중 예외 발생: {error}")
            return False

    # --------------------------------------------------
    # 내부 헬퍼 메서드
    # --------------------------------------------------

    def _switch_to_editor_frame(self):
        """
        스마트에디터 ONE이 iframe 내부에 로드된 경우 iframe으로 컨텍스트를 전환합니다.
        iframe이 없으면 그대로 진행합니다.

        [참고] 네이버 에디터 버전에 따라 iframe 여부가 다를 수 있습니다.
               테스트 시 F12 → Elements 탭에서 <iframe> 존재 여부를 직접 확인하세요.
        """
        try:
            # id가 'mainFrame'인 iframe을 먼저 탐색
            frame = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "mainFrame"))
            )
            self.driver.switch_to.frame(frame)
            print("[에디터] iframe(mainFrame) 컨텍스트로 전환했습니다.")
        except TimeoutException:
            # iframe이 없는 최신 에디터 구조이면 그냥 진행
            print("[에디터] iframe 없음. 직접 DOM 조작 모드로 진행합니다.")

    def _dismiss_draft_popup(self):
        """
        글쓰기 페이지 진입 시 나타나는 '이전 임시 원고 불러오기' 팝업을
        [취소] 버튼으로 닫아 빈 문서 상태를 확보합니다.
        팝업이 없으면 조용히 넘어갑니다.
        """
        try:
            cancel_btn = WebDriverWait(self.driver, 4).until(
                EC.element_to_be_clickable((By.XPATH, self.SELECTOR_POPUP_CANCEL))
            )
            cancel_btn.click()
            time.sleep(1.5)
            print("[에디터] 이전 임시 원고 팝업을 [취소]로 닫았습니다.")
        except TimeoutException:
            print("[에디터] 이전 임시 원고 팝업 없음. 바로 진행합니다.")

    def _paste(self, text: str, element=None):
        """
        pyperclip + Ctrl+V. element가 있으면 그 요소에 클릭·포커스 후 붙여넣기(로그인 id/pw).
        없으면 현재 active 요소(에디터 등).
        """
        pyperclip.copy(text)
        if element is not None:
            element.click()
            time.sleep(0.2)
            target = element
        else:
            target = self.driver.switch_to.active_element
        target.send_keys(self._mod, "v")

    def _paste_to_active(self, text: str):
        """
        pyperclip으로 텍스트를 클립보드에 올린 뒤, 현재 포커스된
        contenteditable 영역에 Ctrl+V로 붙여넣습니다. (에디터 제목/본문용)

        에디터 영역은 일반 input이 아닌 contenteditable div이므로
        .clear()나 .send_keys()로 직접 타이핑하면 한글 깨짐이 발생합니다.
        클립보드 우회 방식이 가장 안정적입니다.
        """
        pyperclip.copy(text)
        active_el = self.driver.switch_to.active_element
        active_el.send_keys(self._mod, "v")

    def _wait_for_save_toast(self) -> bool:
        """
        임시저장 버튼 클릭 후 '저장 완료' 토스트 알림이 화면에 나타나는지 확인합니다.
        최대 5초 대기하며, 토스트 감지 성공 시 True / 타임아웃 시 False를 반환합니다.

        [사용자 정의 방식]
        토스트 대신 저장 카운트가 증가하는 방식이라면 아래 SELECTOR_SAVE_TOAST를
        저장 카운트 셀렉터(예: .se-help-panel-link-save-count)로 교체하세요.
        """
        print("[에디터] 저장 완료 토스트 알림 대기 중... (최대 5초)")
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, self.SELECTOR_SAVE_TOAST))
            )
            print("[성공] 임시저장이 정상적으로 완료되었습니다.")
            time.sleep(2)  # 토스트 알림이 사라질 때까지 여유 시간
            return True
        except TimeoutException:
            # 토스트를 감지하지 못해도, 저장 자체는 완료됐을 가능성이 있습니다.
            # 셀렉터가 맞지 않을 경우 SELECTOR_SAVE_TOAST를 F12로 직접 확인하세요.
            print("[경고] 저장 완료 토스트를 감지하지 못했습니다. (셀렉터 검토 필요)")
            print("       저장 자체는 성공했을 수 있으나, 블로그에서 직접 확인하세요.")
            time.sleep(4)  # 원래 설계대로 4초 안전 대기 유지
            return False
