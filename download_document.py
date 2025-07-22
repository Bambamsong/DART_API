import os
import requests
from dotenv import load_dotenv

import zipfile
import io

load_dotenv()
API_KEY = os.getenv("DART_API")
url = "https://opendart.fss.or.kr/api/document.xml"

params = {
    'crtfc_key': API_KEY,
    'rcept_no': '20250317000701'  # 공시서류 접수번호
}

res = requests.get(url, params=params)

# 2. 응답을 메모리 상의 zip 파일로 처리
zip_bytes = io.BytesIO(res.content)

# 3. zipfile 모듈로 압축 해제
with zipfile.ZipFile(zip_bytes, 'r') as zip_ref:
    # ZIP 안에 있는 파일 목록 확인
    print("압축 파일 내 목록:", zip_ref.namelist())

    with zip_ref.open('20250317000701.xml') as xml_file:
        xml_content = xml_file.read().decode('utf-8') # 문자열로 변환


from bs4 import BeautifulSoup

# 1. XML 열기
soup = BeautifulSoup(xml_content, 'xml')

# 2. TITLE 태그 찾기
all_titles = soup.find_all("TITLE")
start_idx = end_idx = None

for idx, title in enumerate(all_titles):
    text = title.get_text(strip=True)
    if "경영진단 및 분석의견" in text:
        start_idx = idx
    elif "회계감사인의 감사의견 등" in text and start_idx is not None:
        end_idx = idx
        break

# 3. 해당 섹션만 추출
if start_idx is not None and end_idx is not None:
    content = []
    # 해당 섹션 사이의 TITLE 포함 전체 내용 파싱
    start_title = all_titles[start_idx]
    end_title = all_titles[end_idx]

    collecting = False
    for tag in soup.find_all(True):  # soup의 모든 태그 순회
        if tag == start_title:
            collecting = True
        elif tag == end_title:
            break
        elif collecting:
            # 텍스트만 추출 (SPAN, P 등 상관없이)
            if tag.name in ['SPAN', 'P', 'TITLE']:
                text = tag.get_text(strip=True)
                if text:
                    content.append(text)

    # 4. 저장
    with open("LG유플러스_경영진단_섹션.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(content))

    print("✅ 저장 완료: 경영진단_섹션.txt")

else:
    print("❌ 해당 섹션을 찾을 수 없습니다.")