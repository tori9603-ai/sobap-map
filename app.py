import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정 및 성능 최적화
st.set_page_config(page_title="소중한밥상 통합 관제 시스템", layout="wide", initial_sidebar_state="expanded")

# 🔑 접속 보안 설정
ACCESS_PASSWORD = "0119" 

# 💡 [UI] 사이드바 및 🆑 클릭 버튼 디자인
st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #FFF0F0; }
        [data-testid="stSidebarCollapsedControl"] {
            background-color: #FF4B4B !important; color: white !important;
            border-radius: 0 15px 15px 0 !important;
            width: 160px !important; height: 65px !important;
            display: flex !important; align-items: center !important;
            justify-content: center !important; position: fixed !important;
            left: 0 !important; top: 20px !important;
            box-shadow: 5px 5px 15px rgba(0,0,0,0.5) !important;
            z-index: 1000000 !important;
            cursor: pointer !important;
        }
        [data-testid="stSidebarCollapsedControl"] svg { display: none !important; }
        [data-testid="stSidebarCollapsedControl"]::after {
            content: "🆑 클릭해서 메뉴열기" !important;
            font-weight: 900 !important; color: white !important;
            font-size: 17px !important; white-space: nowrap !important;
        }
    </style>
    """, unsafe_allow_html=True)

# 🔐 로그인 로직
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.title("🔐 소중한밥상 관제 센터 접속")
    if st.text_input("접속 암호", type="password") == ACCESS_PASSWORD:
        if st.button("접속하기"): st.session_state.authenticated = True; st.rerun()
    st.stop()

# ⚠️ 사장님이 방금 발급받으신 최신 URL입니다!
API_URL = "https://script.google.com/macros/s/AKfycbxzZjALlZmyzrhhuOUrN7Md51xQWbXDDP4qLiEE10rVa0SZWDirbISPjoDvyPmNeKL6/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" 

@st.cache_data(ttl=60)
def get_data_cached(api_url):
    try:
        response = requests.get(api_url, allow_redirects=True, timeout=10)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            return df[~df['owner'].isin(['0', '', 'nan'])]
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except: return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 주소 검색 후보 리스트 기능
@st.cache_data(ttl=3600)
def get_location_smart(query, api_key):
    headers = {"Authorization": f"KakaoAK {api_key}"}
    all_results = []
    try:
        res_addr = requests.get(f"https://dapi.kakao.com/v2/local/search/address.json?query={query}", headers=headers).json()
        for d in res_addr.get('documents', []):
            all_results.append({'display_name': f"[주소] {d['address_name']}", 'y': d['y'], 'x': d['x']})
        res_kw = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers).json()
        for d in res_kw.get('documents', []):
            all_results.append({'display_name': f"[{d.get('category_group_name', '장소')}] {d['place_name']}", 'y': d['y'], 'x': d['x']})
    except: pass
    return all_results

# 이하 관리 및 지도 로직 생략 (기본 기능 동일하게 포함됨)
