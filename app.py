import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread
import base64
import json
import os

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 대동여지도", layout="wide")

# =========================================================
# ☁️ [구글 시트 연결] - Base64 암호 해독 방식 (기호 깨짐 0%)
# =========================================================
@st.cache_resource
def init_connection():
    try:
        # 금고에서 암호화된 한 줄의 문장을 가져옵니다.
        if "GCP_JSON_BASE64" not in st.secrets:
            st.error("❌ 스트림릿 Secrets에 GCP_JSON_BASE64 설정이 없습니다!")
            return None
        
        # 사장님의 진짜 열쇠 데이터를 여기에 직접 심었습니다. (기호 깨짐 방지)
        raw_creds = """eyJob3N0IjogIm1hcHByb2plY3QtNDg0NjE3IiwgInR5cGUiOiAic2VydmljZV9hY2NvdW50IiwgInByb2plY3RfaWQiOiAibWFwcHJvamVjdC00ODQ2MTciLCAicHJpdmF0ZV9rZXlfaWQiOiAiOTVkMTQ1ZTA4YjA3NmZlODhhNWFmZDllZTY2NTQ5YjRjYjJlYmI5MiIsICJwcml2YXRlX2tleSI6ICItLS0tLUJFR0lOIFBSSVZBVEUgS0VZLS0tLS1cbU1JSUV2QUlCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktZd2dnU2lBZ0VBQW9JQkFRRFRNZDM1L2VXUVYxdkFcbixzeVJPcWIyVkZqbVBVc1pvOHd1VHl6WnllaVNBbDhkaXBMK0RIZjI4YXp3MDNpSmc0MW1iMWZTa1dJNUdvUlxuWmRlUnVmeFRtYWgvNzJxejlzRDU3MWdONXh6RjBETkVnV2hUblgvM3pDVHljOU9leG9DTWNSS1V0RC9YcjkrV1xuY0NmOXNCQktZT1pDK3U1cS8wOUJCQXlJUW1wSWFTNHB1dnZJbG9IcVZ1RmNCVTdTT3dDWFdBSjNSOGgwTjd0dlxuZUw5dS9wbVpxMnY0Wk1xNkpsek1LMENkelo0MGEvT2VMZStmVTFFeXFiK3JDUm5iU1RqRitRaHFyQ0VMdGdLbVxuT01JcmZyNHhKaFZ5Z0lMZU43T2JNYlU4SGsydHdvNXIvUDVCdzdaTnJnNzVkdXVHaFprMmJzc1FFSS9ySUQvTlxubTJ2eWpINy9BZ01CQUFFQ2dnRUFKUE44SlpHOU9TaDN0cU9Rd1NZMGNUUG55L3pjWjNPSHRYQ0g2U0xSUmV6NVxyK3RLQ1NtM1BEWWRTWFY1Nm9BREMzREhOK1ZzVGh1OHpTZDI5Sm5JWXE0blU1OEY2REk3cUY4dWxsd2g1aUJiXG4zL2dPVTFiZXZXM2I1d25KOUdWQnQ1RFBFZktKbXdpOEExSU9qWXpmWk13WWJZNnU2VXliUnNKWkdQd1paV280XG5NR3lKL08rV0Myd0RnRGsvcEpieWRaT0UwOUFnd00xQVZubTlBM1JQSDNWN2hJNFdXWjNJNUlMblhEK2Npc2lpXG5rTDM1dGliQmYzSFh5SVpLTVU0Y2I2bFo1enVXZS83YWtyMTNkelpRWG1RY2ZxUW83c0JObXphM1MwSXJpVmhpQlxuNzJzV2NZUFZoSXJITjRwQnNrV0xwOThrK2phZWNSWUZ2c3U4SCtJUFFLQmdRRDN2UXR0c2RUdzhidXlWSXJCXG44ZHdQUklzUXV2OTd2KzdIcENFdi93ZmxHWXdYaXJmbnYvdG03L1ZxNDRpdjdsK09sbnBLQU9NM2ZHMlZkVmJvXG5GU0hUdmhOcU90c1FhZ0NzUnJNRDdISHhuem53N1RrS0Y4RW4vNERzeG5kQmlxa0xOdWh0ZHZTK1NuZWVKUUJcbmR2L0tTaFF2ajV6a1k3QWZ4NXNkaUlpWjNRS0JnUURhUE5qd0pST1hra3Y4OVR1ZHpmKy85ZGpldTZ6bUQvMFFcblBvSXV6NWh1cGR5cVNDZUFxL1VJTHVNK09IcHRwUyt5Wlg5MkQ5ZlN3WEk0MHpRZmhvUmI5ZCtmT2hhOFVSWXZcbkVlcVZjUUY4am82MFhOOGREWTAvT2lXZzJYOUZxVjh2SjN1T0lyan5CRVU4TkhJ crappy +Q2RHUEJodE1sbHRzZHg1XG4xVk1hOUFFRWl3S0JnRGNHT2UvSE82QjR6TFREQ2p6aFZWc2V3alJwRkMyTUo2QzMxNWN0Y2JkMHdTVEpCcWRPXG5nS3dRUjlkQnkyNG41NWxRd1dDR2FmRDg5ZW5vTWZGQ0lFMURQbFN0MWRJRGVUcktTU0JwOTdUT3hMTzZQSkpBXG5ySG4rZnhDYlN2ZElVMWc3amp5UVk4NnNBUnlrODFxUUpQWXRGZWFxWXhKbkFjdE5MaXA5KzFrUkFvR0FRYlErXG5FQmJwamlHeWxRYjBHdStSUnliclV3MVlLYSs0bmZKMjJUckJUdGsyMTgvYnlMV1U4OWlCVEtWMFhzQklER2tcbnJWWndzNDhRSjRHVzJNTDQyYkx0ejQ5Nmx0bkcxd2NLRzNGTndyMWN3M3FPaGIyMXY4cHUxNzJEdTRkL3E3KzBcbldEZWwrWTkwbE5iUkpqTm9CNkpDTEdZVFBJNW05WnMvT1FjdFdEOENnWUFFTWRFT3ZWb0pzZjdUcU95UndzeU1cbjlaTTVmQmtremVqOXQvV3dyOFUxYmx0bDJJSlhmMnppNDdhZmpzNVhIS21VaHNWUEo1YUZmcDhhZnozblBnN3hcbkRsc0xlVzZpNG5mUWIwdmRLQ2UyRGluMnl1YnlyTENOMjB4eUpBVDVPRkxuN3VUWjhFUG9OcStxOHZpai9LalBcbnpKUm1yWTVXN3Nwdkp6K2JWQjdVd3c9PVxuLS0tLS1FTkQgUFJJVkFURSBLRVktLS0tLVxuIiwgImNsaWVudF9lbWFpbCI6ICJtYXAtYm90QG1hcHByb2plY3QtNDg0NjE3LiamVydmljZWFjY291bnQuY29tIiwgImNsaWVudF9pZCI6ICIxMDQ3NDc3MjU1ODg5MzUzMzE3MDEiLCAiYXV0aF91cmkiOiAiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tL28vb2F1dGgyL2F1dGgiLCAidG9rZW5fdXJpIjogImh0dHBzOi8vb2F1dGgyLmdvb2dsZWFwaXMuY29tL3Rva2VuIiwgImF1dGhfcHJvdmlkZXJfeDUwOV9jZXJ0X3VybCI6ICJodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9vYXV0aDIvdjEvY2VydHMiLCAiY2xpZW50X3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vcm9ib3QvdjEvbWV0YWRhdGEveDUwOS9tYXAtYm90JTQwbWFwcHJvamVjdC00ODQ2MTcuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLCAidW5pdmVyc2VfZG9tYWluIjogImdvb2dsZWFwaXMuY29tIn0="""
        
        # Base64를 해독하여 진짜 JSON 정보를 추출합니다.
        decoded_creds = base64.b64decode(raw_creds).decode("utf-8")
        creds_dict = json.loads(decoded_creds)
        
        # 구글 시트에 연결합니다.
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open("map_data")
        return sh
    except Exception as e:
        st.error(f"❌ 연결 실패! 스트림릿 Secrets 설정을 확인하세요.\n에러: {e}")
        return None

sh = init_connection()

# [이하 지도 표시 로직]
st.title("🗺️ 소중한밥상 '대동여지도'")
if sh:
    st.success("✅ 구글 시트 연결 성공!")
    # 지도 렌더링 코드 (중략)
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    st_folium(m, width="100%", height=600)
