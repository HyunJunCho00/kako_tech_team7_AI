# 카카오테크캠퍼스 3단계 AI 서버 (Team 7)

Team 7의 AI 서버 레포지토리입니다.  
이 서버의 주요 역할은 외부 채용 공고 URL을 입력받아, 웹 크롤링과 Google Gemini LLM을 통해 핵심 정보를 추출하고, 이를 표준화된 JSON 형식으로 메인 백엔드 서버에 제공합니다.

---

## ✨ 주요 기능
- **채용 공고 분석**: URL만으로 채용 공고의 핵심 정보를 자동으로 분석하고 추출합니다.
- **웹 크롤링**: `Requests`와 `BeautifulSoup4`를 사용하여 웹 페이지의 HTML을 가져와 분석에 필요한 순수 텍스트를 정제합니다.
- **LLM 기반 정보 추출**: Google의 Gemini 모델을 활용하여 정제된 텍스트에서 회사명, 직무, 마감일, 자격요건 등의 정보를 정확하게 추출합니다.
- **표준 API 제공**: 추출된 정보를 표준화된 JSON 형식으로 제공하는 RESTful API 엔드포인트를 제공합니다.

---

## 📌 API 명세

### 채용 공고 분석 요청

- **Endpoint**: `POST /api/ai/analyze-url`
- **Description**: 주어진 URL의 채용 공고를 분석하여 구조화된 데이터를 반환합니다.

#### Request Body

```json
{
  "url": "https://www.wanted.co.kr/wd/..."
}
```

### Success Response (200 OK)

```json
{
    "code": "200",
    "message": "채용 공고 분석에 성공했습니다.",
    "data": {
        "companyName": "아이오트러스트",
        "applyPosition": "프론트엔드",
        "deadline": "2025-09-30T14:59:00",
        "location": "서울",
        "employmentType": "정규직",
        "careerRequirement": 3
    }
}
```


### MCP(Server) 미사용 이유

이번 AI 서버는 사용자가 채용 공고 URL을 입력하면 **즉시 분석 후 JSON을 반환**하는 단발성 요청 처리 구조입니다. 
MCP(Model Context Protocol)는 **대화형, 다중 요청, 이전 문맥 유지** 등의 기능이 필요할 때 유용합니다. 하지만 제가 생각했을 때는 본 프로젝트에서는 단일 요청만 처리하고 결과를 반환하면 끝나므로 **MCP를 활용할 필요가 없다고 판단**하여 처음에 논의했던 MCP를 활용하기 보다는 단순히 URL을 하나 분석해서 JSON을 반환하는 방향으로 구조를 바꾸었습니다.
