import streamlit as st
import pandas as pd
import googleapiclient.discovery
from datetime import datetime, timezone, timedelta
import isodate

# ---------------- API 관리 ----------------
def get_youtube_service(api_key):
    return googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

# ---------------- 데이터 수집 ----------------
def format_duration(iso_duration):
    duration = isodate.parse_duration(iso_duration)
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}시간 {minutes}분 {seconds}초"
    elif minutes > 0:
        return f"{minutes}분 {seconds}초"
    else:
        return f"{seconds}초"

def get_channel_videos(channel_id, api_key):
    youtube = get_youtube_service(api_key)
    channel_res = youtube.channels().list(
        part="snippet,statistics,contentDetails", id=channel_id
    ).execute()
    channel_info = channel_res["items"][0]
    channel_title = channel_info["snippet"]["title"]
    subscribers = int(channel_info["statistics"].get("subscriberCount", 0))
    uploads_playlist = channel_info["contentDetails"]["relatedPlaylists"]["uploads"]

    ten_days_ago = datetime.now(timezone.utc) - timedelta(days=10)

    video_ids = []
    next_page_token = None
    while True:
        playlist_res = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist,
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        for item in playlist_res["items"]:
            video_id = item["snippet"]["resourceId"]["videoId"]
            published_at = datetime.fromisoformat(
                item["snippet"]["publishedAt"].replace("Z", "+00:00")
            )
            if published_at >= ten_days_ago:
                video_ids.append((
                    video_id,
                    published_at,
                    item["snippet"]["title"],
                    item["snippet"]["thumbnails"]["medium"]["url"]
                ))
        next_page_token = playlist_res.get("nextPageToken")
        if not next_page_token:
            break

    if not video_ids:
        return pd.DataFrame(), channel_title

    video_data = []
    for video_id, published_at, title, thumb_url in video_ids:
        videos_res = youtube.videos().list(
            part="statistics,contentDetails",
            id=video_id
        ).execute()
        item = videos_res["items"][0]
        stats = item["statistics"]
        content = item["contentDetails"]

        views = int(stats.get("viewCount", 0))
        hours_since = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600
        views_per_hour = round(views / hours_since) if hours_since > 0 else views
        ratio = round((views / subscribers) * 100) if subscribers > 0 else 0
        duration_str = format_duration(content["duration"])

        video_data.append({
            "채널명": channel_title,
            "썸네일": f"<img src='{thumb_url}' width='240'>",
            "제목": title,
            "조회수": views,
            "시간당 조회수": views_per_hour,
            "구독자 대비 조회수": ratio,
            "영상길이": duration_str,
            "업로드일": published_at.strftime("%Y-%m-%d"),
            "영상 바로가기": f"<a href='https://youtu.be/{video_id}' target='_blank'>📺 링크</a>",
            "썸네일 다운로드": f"<a href='{thumb_url}' target='_blank'>📥 다운로드</a>"
        })

    return pd.DataFrame(video_data), channel_title

# ---------------- Streamlit UI ----------------
st.set_page_config(layout="wide")

st.title("📊 유튜브 실버 사연 채널 인기 영상 분석기 (최근10일간/여성향)")

# ✅ API 키 입력
if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

st.session_state["api_key"] = st.text_input(
    "🔑 YouTube Data API 키를 입력하세요",
    value=st.session_state["api_key"],
    type="password",
    placeholder="여기에 API 키 입력"
)

if not st.session_state["api_key"]:
    st.warning("👉 계속하려면 API 키를 입력하세요.")
    st.stop()

# 기본 채널
DEFAULT_CHANNELS = {
    "1 썰이빛나는밤에": "UCOZnrJilN9FsL8pGd0by6xg",
    "2 소리로 읽는 세상": "UCepniAEbQ3T75M2OuInzIOw",
    "3 사연튜브 사연라디오": "UCrW6eDWbbdmxr-XfOkvQKwQ",
    "4 금빛이야기": "UC8XIOLMm8kpoaEzjovaoesw",
    "5 인생사연": "UCT2S9OFvyF4rMZZQeNcIu3Q",
    "6 풀빛사연": "UCko5Mjg45-Kz8P2mq_2FFsg",
    "7 랄라하의 사연드라마": "UCrRBSlHTvHGOd6hyF3DLPPw",
    "8 인생은 그저 소풍": "UCC1QkO6jfYQoP7gpaUsaDUg",
    "9 세대공감 사연드라마": "UCXMqVMRVQWc5WFR7FvWxGQA",
    "10 사연나무": "UCkNQT75PDjH7xYAAU3TL6fw",
    "11 인생마당": "UCl1JOZvMCD9WaC5odFMXQYw",
    "12 사연사랑방": "UCMcVorIMLMWPOCGludbeU4g",
    "13 황혼튜브": "UCo36q9bPCCqUqlTokse6OTw",
    "14 수채화속 인생사연": "UCLgOsa-4EBchF90tuzfRInw",
    "15 구름 같은 이야기": "UCVE2CnAhq2k2w9Tzey2Bqcw",
}

# ✅ 선택 상태 session_state로 관리
if "selected_channels" not in st.session_state:
    st.session_state["selected_channels"] = []

col1, col2 = st.columns(2)
if col1.button("✅ 전체 선택"):
    st.session_state["selected_channels"] = list(DEFAULT_CHANNELS.values())
if col2.button("❌ 전체 해제"):
    st.session_state["selected_channels"] = []

with st.expander("📌 기본 채널 선택하기"):
    for name, cid in DEFAULT_CHANNELS.items():
        checked = cid in st.session_state["selected_channels"]
        if st.checkbox(f"{name} ({cid})", value=checked, key=cid):
            if cid not in st.session_state["selected_channels"]:
                st.session_state["selected_channels"].append(cid)
        else:
            if cid in st.session_state["selected_channels"]:
                st.session_state["selected_channels"].remove(cid)

extra_input = st.text_area(
    "➕ 추가할 채널 URL 또는 채널 ID (한 줄에 하나씩)",
    height=150,
    placeholder="예시:\nUCxxxxxxxxxx\nhttps://www.youtube.com/@life4yeon"
)
extra_channels = [line.strip() for line in extra_input.splitlines() if line.strip()]
all_channels = list(set(st.session_state["selected_channels"] + extra_channels))

# 실행
if st.button("분석 시작"):
    if not all_channels:
        st.warning("👉 분석할 채널을 선택하세요.")
        st.stop()

    all_results = pd.DataFrame()
    progress = st.progress(0)   # 진행 표시
    status_text = st.empty()

    for i, cid in enumerate(all_channels, start=1):
        try:
            status_text.text(f"🔎 {i}/{len(all_channels)} 채널 분석 중...")
            df, ch_name = get_channel_videos(cid, st.session_state["api_key"])
            if not df.empty:
                all_results = pd.concat([all_results, df], ignore_index=True)
        except Exception as e:
            st.error(f"⚠️ {cid} 분석 실패: {e}")

        progress.progress(i / len(all_channels))  # 진행 업데이트

    status_text.text("✅ 분석 완료!")

    if not all_results.empty:
        # 🔎 필터링 조건 적용
        filtered = all_results[
            (all_results["시간당 조회수"] >= 500) &
            (all_results["구독자 대비 조회수"] >= 5)
        ].copy()

        # ✅ 시간당 조회수 기준 내림차순 정렬
        filtered = filtered.sort_values(by="시간당 조회수", ascending=False)

        # 보기 좋게 다시 문자열 포맷팅
        filtered["조회수"] = filtered["조회수"].map(lambda x: f"{x:,}")
        filtered["시간당 조회수"] = filtered["시간당 조회수"].map(lambda x: f"{x:,} 회")
        filtered["구독자 대비 조회수"] = filtered["구독자 대비 조회수"].map(lambda x: f"{x} %")

        # 가운데 정렬 CSS 적용
        styled_html = (
            filtered.style
            .set_table_styles(
                [{"selector": "th", "props": [("text-align", "center")]},
                 {"selector": "td", "props": [("text-align", "center")]}]
            )
            .hide(axis="index")
            .to_html(escape=False)
        )

        st.subheader("📌 필터링된 결과 (시간당 조회수 내림차순)")
        st.markdown(styled_html, unsafe_allow_html=True)
