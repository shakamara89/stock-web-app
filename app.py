import datetime
import re
import FinanceDataReader as fdr
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# Matplotlib 한글 깨짐 방지 설정
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# 페이지 기본 설정
st.set_page_config(
    page_title="주식 Raw Data & 데이터 박스 시스템", page_layout="wide"
)


# 거래소 종목 데이터 로드 (캐싱으로 속도 최적화)
@st.cache_data
def load_krx_stocks():
    df = fdr.StockListing("KRX")
    df["Name"] = df["Name"].str.strip()
    return df


krx_stocks = load_krx_stocks()

# 세션 상태 초기화 (데이터 박스 및 수식 로그 저장)
if "stock_boxes" not in st.session_state:
    st.session_state.stock_boxes = {}
if "manual_box_count" not in st.session_state:
    st.session_state.manual_box_count = 0
if "active_box_name" not in st.session_state:
    st.session_state.active_box_name = None

# 메인 타이틀
st.title("📈 주식 Raw Data & 산점도 & 데이터 박스 웹 프로그램")

# ==============================================================================
# 1. 상단 종목 검색 바
# ==============================================================================
top_col1, top_col2 = st.columns([3, 1])
with top_col1:
    search_input = st.text_input(
        "종목명 입력 (예: 삼성전자, SK하이닉스, 카카오)", key="search_keyword"
    )
with top_col2:
    st.write(" ")  # 정렬용 여백
    st.write(" ")
    btn_search = st.button("Raw Data & 차트 불러오기", type="primary")


def fetch_and_add_stock(stock_query):
    stock_match = krx_stocks[
        krx_stocks["Name"].str.contains(stock_query, case=False, na=False)
    ]
    if stock_match.empty:
        st.error(f"'{stock_query}'에 해당하는 종목을 찾을 수 없습니다.")
        return

    matched_row = stock_match.iloc[0]
    actual_name = matched_row["Name"]
    stock_code = str(matched_row["Code"]).zfill(6)

    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (
        datetime.date.today() - datetime.timedelta(days=365)
    ).strftime("%Y-%m-%d")

    try:
        df = fdr.DataReader(stock_code, start_date, end_date)
        if df.empty:
            st.warning("해당 기간에 데이터가 없습니다.")
            return

        df = df.sort_index(ascending=True)
        df.index = df.index.strftime("%Y-%m-%d")
        df.index.name = "날짜"

        df = df.rename(
            columns={
                "Open": "시가",
                "High": "고가",
                "Low": "저가",
                "Close": "종가",
                "Volume": "거래량",
            }
        )

        target_cols = ["시가", "고가", "저가", "종가", "거래량"]
        df = df[[col for col in target_cols if col in df.columns]]

        # 보관소 저장 및 선택된 박스 활성화
        st.session_state.stock_boxes[actual_name] = df
        st.session_state.active_box_name = actual_name
        st.success(f"✅ [{actual_name}] 데이터를 성공적으로 로드했습니다.")

    except Exception as e:
        st.error(f"데이터 수집 중 오류가 발생했습니다: {e}")


if btn_search and search_input:
    fetch_and_add_stock(search_input)

# ==============================================================================
# 2. 메인 화면 3열 레이아웃 구성
# ==============================================================================
col_list, col_mid, col_right = st.columns([1, 2, 2])

# ------------------------------------------------------------------------------
# [창 0: 가장 좌측] 전체 종목 리스트
# ------------------------------------------------------------------------------
with col_list:
    st.subheader("📜 전체 종목 리스트")
    filter_keyword = st.text_input(
        "리스트 검색 필터", placeholder="종목명 필터링..."
    )

    filtered_df = krx_stocks
    if filter_keyword:
        filtered_df = krx_stocks[
            krx_stocks["Name"].str.contains(
                filter_keyword, case=False, na=False
            )
        ]

    # 종목 선택 멀티 옵션 박스
    display_options = [
        f"[{row.get('Market', 'KRX')}] {row.get('Name')}"
        for _, row in filtered_df.iterrows()
    ]
    selected_item = st.selectbox(
        "종목 선택 시 바로 데이터 조회",
        options=["선택하세요..."] + display_options,
    )

    if selected_item and selected_item != "선택하세요...":
        selected_stock_name = selected_item.split("]", 1)[1].strip()
        if st.button(f"'{selected_stock_name}' 불러오기"):
            fetch_and_add_stock(selected_stock_name)

# ------------------------------------------------------------------------------
# [중간 영역] 차트 및 Raw Data 테이블
# ------------------------------------------------------------------------------
with col_mid:
    active_name = st.session_state.active_box_name
    active_df = (
        st.session_state.stock_boxes.get(active_name) if active_name else None
    )

    # [창 1] Multi-Axis Scatter Chart
    st.subheader("📈 주가 산점도 차트")
    if active_df is not None:
        fig, ax1 = plt.subplots(figsize=(6, 3.5))
        dates = pd.to_datetime(active_df.index)
        num_cols = active_df.select_dtypes(include=["number"]).columns.tolist()

        has_volume = "거래량" in num_cols
        price_cols = [c for c in num_cols if c != "거래량"]

        handles, labels = [], []
        colors = plt.cm.tab10.colors

        for i, col in enumerate(price_cols):
            color = colors[i % len(colors)]
            sc = ax1.scatter(
                dates,
                active_df[col],
                label=col,
                color=color,
                s=18,
                alpha=0.7,
            )
            handles.append(sc)
            labels.append(col)

        ax1.set_xlabel("날짜", fontsize=9)
        ax1.set_ylabel("가격 / 값", fontsize=9, color="#1f77b4")
        ax1.grid(True, linestyle="--", alpha=0.4)

        if has_volume:
            ax2 = ax1.twinx()
            sc_vol = ax2.scatter(
                dates,
                active_df["거래량"],
                label="거래량",
                color="#FF9800",
                s=14,
                alpha=0.5,
                marker="s",
            )
            ax2.set_ylabel("거래량", fontsize=9, color="#E65100")
            handles.append(sc_vol)
            labels.append("거래량")

        ax1.set_title(f"[{active_name}] 데이터 분포", fontsize=11)
        if handles:
            ax1.legend(handles, labels, loc="upper left", fontsize=8)

        fig.autofmt_xdate()
        fig.tight_layout()
        st.pyplot(fig)
    else:
        st.info("선택된 데이터 박스가 없습니다.")

    # [창 2] Raw Data 테이블
    st.subheader("📋 Raw Data 테이블")
    if active_df is not None:
        st.dataframe(active_df, use_container_width=True, height=250)
    else:
        st.text("표시할 데이터가 없습니다.")

# ------------------------------------------------------------------------------
# [우측 영역] Data Box Storage 및 조합 창
# ------------------------------------------------------------------------------
with col_right:
    # [창 3] Data Box Storage (스크롤 보관소)
    st.subheader("📦 데이터 함수 보관소")

    if st.session_state.stock_boxes:
        box_cols = st.columns(3)
        for idx, box_k in enumerate(st.session_state.stock_boxes.keys()):
            col_target = box_cols[idx % 3]
            if col_target.button(
                f"f(x) {box_k}", key=f"btn_box_{box_k}", use_container_width=True
            ):
                st.session_state.active_box_name = box_k
                st.rerun()

        # 가이드 & 구조 요약
        if active_df is not None:
            num_cols = active_df.select_dtypes(
                include=["number"]
            ).columns.tolist()
            cols_str = " / ".join(num_cols)
            st.caption(
                f"📊 변수 접근 표현식: `{active_name}(x).{num_cols[0] if num_cols else ''}`"
            )
            with st.expander("데이터 구조 요약 (최근 5일)", expanded=False):
                st.text(active_df.tail(5).to_string())
    else:
        st.caption("보관된 데이터 박스가 없습니다.")

    # [창 4] 데이터 박스 조합 창
    st.subheader("⚙️ 데이터 박스 조합 창")
    st.caption("💡 예시: `삼성전자(x).종가 + 삼성전자(x-2).시가` | (x-n)은 과거 n일 시프트")

    formula_input = st.text_input(
        "수식 입력", placeholder="삼성전자(x).종가 - SK하이닉스(x).종가"
    )

    if st.button("조합 실행", type="primary"):
        if not formula_input:
            st.warning("수식을 입력하세요.")
        else:
            try:
                pattern = re.compile(
                    r"([가-힣a-zA-Z0-9_]+)\(x(?:-(\d+))?\)\.([가-힣a-zA-Z0-9_]+)"
                )
                matches = pattern.findall(formula_input)

                if not matches:
                    st.error("올바른 수식 형식이 아닙니다.")
                else:
                    eval_formula = formula_input
                    series_dict = {}

                    for idx_m, (stock, shift_val, col) in enumerate(matches):
                        if stock not in st.session_state.stock_boxes:
                            raise KeyError(
                                f"'{stock}' 박스를 찾을 수 없습니다."
                            )

                        df_target = st.session_state.stock_boxes[stock]
                        if col not in df_target.columns:
                            raise KeyError(
                                f"'{stock}' 박스에 '{col}' 컬럼이 없습니다."
                            )

                        s = df_target[col].copy()
                        if shift_val:
                            s = s.shift(int(shift_val))

                        var_name = f"__var_{idx_m}__"
                        series_dict[var_name] = s

                        target_token = (
                            f"{stock}(x-{shift_val}).{col}"
                            if shift_val
                            else f"{stock}(x).{col}"
                        )
                        eval_formula = eval_formula.replace(
                            target_token, var_name
                        )

                    result_series = eval(
                        eval_formula, {"__builtins__": None}, series_dict
                    )

                    st.session_state.manual_box_count += 1
                    new_box_name = (
                        f"ManualBox{st.session_state.manual_box_count}"
                    )

                    result_df = pd.DataFrame({formula_input: result_series})
                    result_df.index.name = "날짜"

                    st.session_state.stock_boxes[new_box_name] = result_df
                    st.session_state.active_box_name = new_box_name
                    st.success(f"✅ [{new_box_name}] 생성 완료!")
                    st.rerun()

            except Exception as e:
                st.error(f"조합 계산 오류: {e}")
