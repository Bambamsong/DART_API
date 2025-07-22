# 📋 DART API를 이용한 사업보고서 수집 자동화

이 프로젝트는 [DART 공시 API](https://opendart.fss.or.kr/)를 활용하여 특정 기업의 **사업보고서(XML)** 를 자동으로 수집하는 프로세스를 구현합니다.

---
## 🧭 전체 실행 흐름
1. **기업 고유번호 (`corp_code`) 조회**
2. **사업보고서 목록 조회 → 접수번호(`rcept_no`) 획득**
3. **접수번호로 공시 문서 원문(XML) 다운로드**
4. **XML파일로부터 텍스트 추출하기**

![FCE8D322-C078-426D-A043-61BFCBAD020A_1_105_c](https://github.com/user-attachments/assets/b60bd507-83ea-42f4-90b3-d2f9711456f7)
___
## 🧩 사용 API 구성

| 번호 | API명             | 설명                                                  |
|------|------------------|-------------------------------------------------------|
| 1    | 고유번호           | 기업의 고유번호 및 기본 정보 제공                    |
| 2    | 공시정보           | 공시 유형별, 날짜별 공시보고서 목록 제공             |
| 3    | 공시서류원본파일   | 접수번호 기반의 원문(XML) 제공                       |

---

## ⚙️ 실행 환경

- Python 3.x
- `requests`, `dotenv`, `zipfile`, `io` 패키지 사용

---

## 📌 핵심 변수

| 변수명       | 설명                         |
|--------------|------------------------------|
| `corp_code`  | 기업의 고유 식별 번호         |
| `rcept_no`  | 사업보고서 접수번호           |
| `API_KEY`    | DART 인증키 (환경변수 사용)   |

---
## 단계별 요약
### ✅ 1단계: 기업 고유번호 조회 (search_corp_code.py)
응답 결과는 **ZIP FILE(binary)** 이며 아래 항목들을 포함하고 있음

|응답키|명칭|출력설명|
|-----------|----------|----------------------------|
|`corp_code`|고유번호|공시대상회사의 고유번호(8자리)|
|`corp_name`|정식명칭|정식회사명칭|
|`corp_eng_name`|영문 정식명칭|영문정식회사명칭|
|`stock_code`|종목코드|상장회사인 경우 주식의 종목코드(6자리)|
|`modify_date`|최종변경일자|기업개황정보 최종변경일자|

보다 자세한 내용은 아래 링크를 참고하여 확인

https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018
### ✅ 2단계: 기업 사업보고서 목록에서 접수번호 획득 (search_rcept_no.py)
1단계로부터 얻은 고유번호(`corp_code`)를 Parameter로 전달하여 해당기업의 사업보고서 접수번호를 얻을 수 있음

파라미터에 대한 세부 내용은 파이썬 파일에 첨부

```Python
response = requests.get(url, params=params)
data = response.json()

for report in data.get('list', []):
  print(report['corp_code'], report['report_nm'], report['rcept_no'])
```

응답 결과 **list** 항목내부에 해당기업의 보고서에 대한 정보가 존재

해당 보고서들은 접수번호에 따라 분류하며 `rcept_no`가 해당 보고서 접수번호이다

### ✅ 3단계: 공시서류 원문(XML) 다운로드 및 텍스트 추출
2단계로부터 얻은 접수번호(`rcept_no`)를 이용하여 원본파일을 ZIP FILE 형태로 받을 수 있음

해당 ZIP FILE을 압축해제하면 xml파일이 존재하는데 `이중 접수번호.xml`가 사업보고서임
