"""
네이버 스마트에디터 ONE의 실제 DOM 셀렉터를 조회하는 디버그 스크립트입니다.
실행하면 브라우저가 열리고 에디터 페이지에 진입한 뒤 핵심 요소들의
실제 클래스명과 XPath를 콘솔에 출력합니다.
"""
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import Config

def debug_selectors():
    Config.validate_or_exit()

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    driver.implicitly_wait(5)

    try:
        # 1. 로그인
        import pyperclip
        from selenium.webdriver.common.keys import Keys
        driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(2)
        id_el = driver.find_element(By.ID, "id")
        id_el.click()
        pyperclip.copy(Config.NAVER_ID)
        id_el.send_keys(Keys.CONTROL, "v")
        time.sleep(0.5)
        pw_el = driver.find_element(By.ID, "pw")
        pw_el.click()
        pyperclip.copy(Config.NAVER_PW)
        pw_el.send_keys(Keys.CONTROL, "v")
        time.sleep(0.5)
        driver.find_element(By.ID, "log.login").click()
        time.sleep(3)
        print("[로그인 완료]")

        # 2. 에디터 진입
        driver.get(f"https://blog.naver.com/{Config.NAVER_ID}/postwrite")
        time.sleep(6)
        print("[에디터 진입 완료] DOM 조회 시작...\n")

        # 3. 핵심 후보 셀렉터 일괄 탐색
        candidates = {
            "제목(CSS) - se-document-title-top placeholder": ".se-document-title-top .se-placeholder",
            "제목(CSS) - se-title-input":                    ".se-title-input",
            "제목(CSS) - se-documentTitle placeholder":      ".se-documentTitle .se-placeholder",
            "제목(CSS) - [data-placeholder] in title":       ".se-documentTitle [data-placeholder]",
            "본문(CSS) - se-component-text placeholder":     ".se-content .se-component-text .se-placeholder",
            "본문(CSS) - se-main-container placeholder":     ".se-main-container .se-placeholder",
            "본문(CSS) - se-component placeholder":          ".se-component .se-placeholder",
        }

        for label, selector in candidates.items():
            els = driver.find_elements(By.CSS_SELECTOR, selector)
            status = f"✅ {len(els)}개 발견" if els else "❌ 없음"
            print(f"  [{status}] {label}")
            if els:
                print(f"           클래스: {els[0].get_attribute('class')}")
                print(f"           태그  : {els[0].tag_name}")
                print(f"           텍스트: {els[0].text[:60] if els[0].text else '(없음)'}")
            print()

        # 4. contenteditable 요소 전체 목록 출력
        print("=" * 55)
        print("[contenteditable=true 요소 전체 목록]")
        editable_els = driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
        for i, el in enumerate(editable_els):
            cls = el.get_attribute('class') or ""
            print(f"  [{i}] 클래스: {cls[:80]}")
            print(f"       id   : {el.get_attribute('id') or '(없음)'}")
            print(f"       role : {el.get_attribute('role') or '(없음)'}")

        # 5. 저장 버튼 후보 탐색
        print()
        print("=" * 55)
        print("[저장 버튼 후보 탐색]")
        save_candidates = [
            ("XPATH", "//button[contains(@class,'se-help-panel-link-save')]"),
            ("XPATH", "//span[normalize-space(text())='저장']/parent::button"),
            ("XPATH", "//button[.//span[normalize-space(text())='저장']]"),
            ("CSS",   "button.se-save"),
            ("CSS",   ".se-help-panel-link-save"),
        ]
        for by_type, sel in save_candidates:
            by = By.XPATH if by_type == "XPATH" else By.CSS_SELECTOR
            els = driver.find_elements(by, sel)
            status = f"✅ {len(els)}개 발견" if els else "❌ 없음"
            print(f"  [{status}] ({by_type}) {sel}")
            if els:
                print(f"           클래스: {els[0].get_attribute('class')}")
                print(f"           텍스트: {els[0].text[:60]}")

        print("\n[완료] 브라우저를 수동으로 F12 열어 추가 확인 후 Enter를 누르면 종료됩니다.")
        input()

    finally:
        driver.quit()

if __name__ == "__main__":
    debug_selectors()
