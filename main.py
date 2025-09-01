import os
import json
import re
from dateutil import parser as date_parser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import google.generativeai as genai
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# --- 1. setting environment ---
load_dotenv()
app = FastAPI()

try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except TypeError:
    print("ERROR: GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    exit()

# --- 2. DTO (Data Transfer Object) ---

class AnalyzeUrlRequest(BaseModel):
    url: str

class JobPostingData(BaseModel):
    companyName: str | None = Field(None, description="회사명")
    applyPosition: str | None = Field(None, description="직무/포지션")
    deadline: str | None = Field(None, description="마감일")
    location: str | None = Field(None, description="근무지")
    employmentType: str | None = Field(None, description="고용형태")
    careerRequirement: int | None = Field(None, description="경력 연차")

class ApiResponse(BaseModel):
    code: str
    message: str
    data: JobPostingData | None = None



# --- 3. selenium crawling ---
def crawl_with_selenium(url: str) -> str:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ko-KR")
    chrome_options.add_argument("--window-size=1280,2000")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.set_page_load_timeout(40)

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)

        if "saramin.co.kr" in url:
            iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#iframe_content_0")))
            driver.switch_to.frame(iframe)  
            try:
                body_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.user_content")))
            except:
                body_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.view_tab_content")))

            text = body_el.text.strip()
            if not text:
                text = (body_el.get_attribute("textContent") or "").strip()
            text = "\n".join([ln for ln in (text.splitlines()) if ln.strip()])

            if not text:
                raise ValueError("본문을 찾을 수 없습니다.-> (iframe전환 후에도 비었다는 의미임)")

            return text  
        else:
            raise ValueError("본문을 찾을 수 없습니다.")

    finally:
        driver.quit()




# --- 4. general crawling ---
def crawl_and_clean_page(url: str) -> str:
    if "saramin.co.kr" in url:
        print(" 사람인 URL이므로, Selenium으로 크롤링을 진행합니다.")
        return crawl_with_selenium(url)

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        main_content = soup.find('main') or soup.find('article') or soup.body
        if main_content:
            for tag in main_content(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            text = "\n".join(line for line in main_content.get_text(separator='\n', strip=True).splitlines() if line.strip())
            return text
        else:
            raise ValueError("본문을 찾을 수 없습니다.")
    except Exception as e:
        print(f" 크롤링 실패, Selenium fallback: {e}")
        return crawl_with_selenium(url)



# --- 5. GEMINI analysis ---

def extract_info_with_gemini(text_content: str) -> dict:
    """Gemini를 사용하여 텍스트에서 채용 정보를 추출하고 JSON으로 반환합니다."""
    
    
    prompt = f"""
    당신은 채용 공고 텍스트에서 'Key: Value' 형식의 구조를 파악하여, 지정된 JSON 형식으로 핵심 정보만 추출하고 요약하는 매우 뛰어난 HR 분석가입니다.

    아래의 규칙에 따라 정보를 추출해주세요.

    1.  **"companyName"**: 회사 이름을 추출합니다.
    
    2.  **"applyPosition"**:
        - 텍스트에서 '모집직무', '채용분야', '직무' 같은 키워드를 찾으세요.
        - 그 키워드 바로 뒤에 나오는 직무 목록 (예: '연구개발/설계, IT/인터넷...')을 추출하여 **하나의 문자열로 요약**해주세요.
        - 절대로 '신입사원'이나 공고 전체 제목을 직무로 사용하지 마세요.
    
    3. "deadline": '마감일' 키워드 뒤 날짜와 시/분까지 추출
    4.  **"location"**: '근무지역' 키워드를 찾아 지역을 추출합니다.
    
    5.  **"employmentType"**:
    - '채용형태' 키워드나 '신입', '경력', '인턴' 키워드를 찾습니다.
    - 복수형태가 있을 경우, 모든 고용형태를 **한 문자열로 '/' 또는 ','로 구분**하여 출력합니다.
    - 예: "신입/인턴", "경력 3년차/인턴"

    6.  "careerRequirement": 경력 요건은 **정확히 경력 연차만 숫자로 추출**. 예: '경력 3년차/인턴' → 3

    
    JSON 형식 외의 다른 설명이나 마크다운은 절대 추가하지 마세요.


    ---분석할 채용 공고 텍스트---
    {text_content[:10000]}
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )
        response = model.generate_content(prompt, generation_config=generation_config)
        return json.loads(response.text)
    except Exception as e:
        raise ValueError(f"Gemini 정보 추출에 실패했습니다: {e}")


# --- 6. convert type ---
def format_extracted_info(raw_info: dict) -> dict:
    info = raw_info.copy()

    # careerRequirement → Integer
    career_str = str(info.get("careerRequirement", "0"))
    match = re.search(r'(\d+)', career_str)
    info["careerRequirement"] = int(match.group(1)) if match else 0



    deadline_str = info.get("deadline")
    if deadline_str:
        try:
            dt = date_parser.parse(deadline_str, fuzzy=True)
            info["deadline"] = dt.isoformat()
        except Exception:
            info["deadline"] = None
    else:
        info["deadline"] = None

    return info



# --- 7. API endpoint ---
@app.post("/api/ai/analyze-url", response_model=ApiResponse, summary="채용 공고 URL 분석")
async def analyze_job_posting_url(request: AnalyzeUrlRequest):
    try:
        cleaned_text = crawl_and_clean_page(request.url)
        if not cleaned_text:
            raise ValueError("URL에서 유효한 콘텐츠를 찾을 수 없습니다.")

        extracted_info = extract_info_with_gemini(cleaned_text)
        formatted_info = format_extracted_info(extracted_info)
        job_data = JobPostingData(**formatted_info)
        return ApiResponse(code="200", message="채용 공고 분석에 성공했습니다.", data=job_data)

    except ValueError as e:
        return JSONResponse(status_code=400, content=ApiResponse(code="400", message=str(e), data=None).model_dump())
    except Exception as e:
        return JSONResponse(status_code=500, content=ApiResponse(code="500", message=f"서버 내부 오류: {e}", data=None).model_dump())