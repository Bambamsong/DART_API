# 공시대상회사의 고유번호(8자리) 조회 API
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("DART_API")
url = 'https://opendart.fss.or.kr/api/corpCode.xml' # 고유번호 API URL
params = {
    'crtfc_key' : API_KEY
}
response = requests.get(url, params=params)

# 상태코드 확인
if response.status_code == 200:
    with open("공시회사_고유번호.zip", "wb") as f:
        f.write(response.content)
    print("ZIP 파일이 성공적으로 저장되었습니다.")
else:
    print("요청 실패. 상태 코드: ", response.status_code)
