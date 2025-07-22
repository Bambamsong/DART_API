# 공시검색(공시 유형별, 회사별 등 여러가지 조건으로 공시보고서 검색기능 제공) API
# 공시 원문을 다운로드 받기 위해서는 공시문서의 고유번호를 알아야함
import os
import requests
from dotenv import load_dotenv

###
load_dotenv()
API_KEY = os.getenv("DART_API")
###

###
url_list = "https://opendart.fss.or.kr/api/list.json" # 공시검색 URL
###

###
params= {
    'crtfc_key' : API_KEY, # API 인증키
    'corp_code' : '00231363', # 고유번호
    'bgn_de' : '20180101', # 검색 시작일
    # 'end_de' : '20250101', # 검색 종료일
    'last_reprt_at' : 'Y', # 최종 보고서만 채택여부
    # 'pblntf_ty' : 'A', # 공시유형(A:정기공시)
    'pblntf_detail_ty' : 'A001', # A001:사업보고서 
    'sort' : 'date',
    'page_count' : '100'
}
###
res = requests.get(url_list, params=params)

data = res.json()

for report in data.get('list', []):
    print(report['corp_code'], report['report_nm'], report['rcept_no'])