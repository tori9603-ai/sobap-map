import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pandas as pd
import os
import gspread
import json
import time
import ast

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 대동여지도", layout="wide")

# =========================================================
# ☁️ [구글 시트 연결] - 금고(Secrets)에서 직접 연결
# =========================================================
@st.cache_resource
def init_connection():
    try:
        # 금고에서 정보를 읽어옵니다.
        if "gcp_service_account" not in st.secrets:
            st.error("❌ 스트림릿 Secrets 설정이 누락되었습니다.")
            return None
            
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # ⚠️ 기호 깨짐 강제 수정: 줄바꿈 기호(\n)를 정상화합니다.
        raw_key = creds_dict["private_key"]
        creds_dict["private_key"] = raw_key.replace("\\n", "\n").strip()
            
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open("map_data")
        return sh
    except Exception as e:
        st.error(f"❌ 연결 실패! 에러: {e}")
        return None

sh = init_connection()

# [이하 데이터 로직 및 화면 구성은 생략하지 않고 모두 포함하여 업로드하세요]
# (이전에 드린 app.py 전체 코드를 사용하시되, 위 init_connection 부분만 이 버전으로 확실히 맞추시면 됩니다.)
