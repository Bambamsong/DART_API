import xml.etree.ElementTree as ET
import pandas as pd

xml_path = "/Users/park/Desktop/use/DART/CORPCODE.xml"

# XML 파싱
tree = ET.parse(xml_path)
root = tree.getroot()

# <list> tag를 순회하며 필요한 항목 추출
data = []
for item in root.findall("list"):
    data.append({
        "corp_code" : item.findtext("corp_code"),
        "corp_name" : item.findtext("corp_name"),
        "corp_eng_name" : item.findtext("corp_eng_name"),
        "stock_code" : item.findtext("stock_code"),
        "modify_date" : item.findtext("modify")
        })
df = pd.DataFrame(data)
df.reset_index(inplace=True)
df.to_csv("corp_list.csv", index=False)