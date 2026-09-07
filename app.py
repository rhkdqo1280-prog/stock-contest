import random
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st

from database import db, one, sha
from market import STOCKS, SCENARIOS, load_prices


st.set_page_config(
    page_title="주식 타임머신",
    page_icon="📈",
    layout="wide",
)

KST = pytz.timezone("Asia/Seoul")
APP_VERSION = "2026.09.07-7"

# 교사 비밀번호 6340의 암호화 값
TEACHER_HASH = (
    "4d0394d43c5c04173e8de51f3e4fff9"
    "ba8f5a2ee5e229020ea19511f48b43c6b"
)

st.markdown(
    """
    <style>
    .stApp {
        background: #f4f7fb;
    }

    .block-container {
        max-width: 1400px;
        padding-top: 5rem !important;
    }

    .hero {
        padding: 28px;
        border-radius: 22px;
        background: linear-gradient(130deg, #10203b, #1557d5);
        color: white;
        margin-bottom: 18px;
    }

    .hero h1 {
        margin: 0;
        font-size: 2.4rem;
    }

    .hero p {
        opacity: 0.8;
        margin: 0.5rem 0 0;
    }

    .code {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 0.15em;
        color: #1557d5;
    }

    @media (max-width: 768px) {
        .block-container {
            padding: 4.5rem 0.8rem 2rem !important;
        }

        .hero {
            padding: 18px 16px;
            border-radius: 16px;
            margin-bottom: 12px;
        }

        .hero h1 {
            font-size: 1.65rem;
            line-height: 1.25;
        }

        .hero p {
            font-size: 0.9rem;
        }

        .code {
            font-size: 1.5rem;
            letter-spacing: 0.1em;
        }

        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        [data-testid="stColumn"] {
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }

        [data-testid="stMetric"] {
            padding: 0.35rem 0;
        }

        [data-testid="stDataFrame"] {
            overflow-x: auto;
        }

        .stButton button,
        .stFormSubmitButton button {
            min-height: 46px;
            font-size: 1rem;
        }

        h1 {
            font-size: 1.8rem !important;
        }

        h2 {
            font-size: 1.45rem !important;
        }

        h3 {
            font-size: 1.2rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def make_code():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    while True:
        value = "".join(random.choice(chars) for _ in range(6))

        if not one("competitions", code=value):
            return value


def current_day(comp):
    started = datetime.fromisoformat(
        comp["starts_at"].replace("Z", "+00:00")
    ).astimezone(KST).date()

    elapsed = (datetime.now(KST).date() - started).days

    return max(
        0,
        min(int(comp["duration"]) - 1, elapsed),
    )


def ranking(comp, prices):
    day = current_day(comp)

    players = (
        db()
        .table("players")
        .select("*")
        .eq("competition_id", comp["id"])
        .execute()
        .data
    )

    player_ids = [player["id"] for player in players]

    if player_ids:
        holdings = (
            db()
            .table("holdings")
            .select("*")
            .in_("player_id", player_ids)
            .gt("quantity", 0)
            .execute()
            .data
        )
    else:
        holdings = []

    rows = []

    for player in players:
        stock_value = sum(
            float(prices[holding["ticker"]].iloc[day])
            * holding["quantity"]
            for holding in holdings
            if holding["player_id"] == player["id"]
        )

        total_asset = float(player["cash"]) + stock_value
        initial_cash = float(comp["initial_cash"])

        rows.append(
            {
                "학번": player["student_id"],
                "이름": player["name"],
                "총자산": total_asset,
                "수익률": (
                    (total_asset - initial_cash)
                    / initial_cash
                    * 100
                ),
                "player_id": player["id"],
            }
        )

    return sorted(
        rows,
        key=lambda row: row["총자산"],
        reverse=True,
    )


def reveal_market(comp):
    st.success(
        f"정답 공개 · "
        f"{str(comp['scenario_start'])[:4]}년 실제 한국 주식시장"
    )

    st.caption(
        "대회 중에는 종목명과 가격을 바꿨지만, "
        "실제 일별 등락률은 그대로 사용했습니다."
    )

    reveal_rows = []

    for alias, market, real_name in STOCKS.values():
        reveal_rows.append(
            {
                "대회 종목": alias,
                "실제 종목": real_name,
                "시장": market,
            }
        )

    st.dataframe(
        pd.DataFrame(reveal_rows),
        hide_index=True,
        use_container_width=True,
    )


def delete_competition(comp):
    st.warning(
        "삭제하면 참가 학생, 보유 종목, 거래 내역도 "
        "모두 삭제되며 되돌릴 수 없습니다."
    )

    confirmation = st.text_input(
        "삭제하려면 대회 코드를 입력하세요.",
        key=f"delete_confirm_{comp['id']}",
    ).strip().upper()

    delete_disabled = confirmation != comp["code"]

    if st.button(
        "대회 영구 삭제",
        key=f"delete_{comp['id']}",
        disabled=delete_disabled,
        type="primary",
        use_container_width=True,
    ):
        (
            db()
            .table("competitions")
            .delete()
            .eq("id", comp["id"])
            .execute()
        )

        st.session_state.page = "list"
        st.session_state.pop("competition_id", None)
        st.rerun()


def advance_competition_day(comp):
    started = datetime.fromisoformat(
        comp["starts_at"].replace("Z", "+00:00")
    )

    new_started = started - timedelta(days=1)

    (
        db()
        .table("competitions")
        .update({"starts_at": new_started.isoformat()})
        .eq("id", comp["id"])
        .execute()
    )


def login():
    st.markdown(
        """
        <div class="hero">
            <h1>📈 주식 타임머신</h1>
            <p>연도를 숨긴 과거 한국 주식시장 모의투자 대회</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    student_tab, teacher_tab = st.tabs(
        ["학생 참가", "교사 관리"]
    )

    with student_tab:
        with st.form("student_login"):
            code = st.text_input(
                "대회 코드",
                max_chars=6,
            ).strip().upper()

            student_id = st.text_input("학번").strip()
            name = st.text_input("이름").strip()

            pin = st.text_input(
                "개인 비밀번호",
                type="password",
                help="다른 컴퓨터에서 다시 접속할 때 사용합니다.",
            )

            submitted = st.form_submit_button(
                "참가 또는 다시 접속",
                type="primary",
                use_container_width=True,
            )

            if submitted:
                comp = one("competitions", code=code)

                if not comp:
                    st.error("대회 코드를 확인하세요.")

                elif not student_id or not name:
                    st.error("학번과 이름을 입력하세요.")

                elif len(pin) < 4:
                    st.error(
                        "비밀번호는 4자리 이상이어야 합니다."
                    )

                else:
                    player = one(
                        "players",
                        competition_id=comp["id"],
                        student_id=student_id,
                    )

                    if (
                        player
                        and player["pin_hash"] != sha(pin)
                    ):
                        st.error(
                            "학번 또는 비밀번호가 맞지 않습니다."
                        )

                    else:
                        if not player:
                            player_data = {
                                "competition_id": comp["id"],
                                "student_id": student_id,
                                "name": name,
                                "pin_hash": sha(pin),
                                "cash": comp["initial_cash"],
                            }

                            player = (
                                db()
                                .table("players")
                                .insert(player_data)
                                .execute()
                                .data[0]
                            )

                        st.session_state.update(
                            role="student",
                            competition_id=comp["id"],
                            player_id=player["id"],
                        )

                        st.rerun()

    with teacher_tab:
        with st.form("teacher_login"):
            pin = st.text_input(
                "교사 관리 비밀번호",
                type="password",
                max_chars=4,
            )

            submitted = st.form_submit_button(
                "내 대회 보기",
                use_container_width=True,
            )

            if submitted:
                if pin != "6340":
                    st.error(
                        "패스워드 오류 · "
                        "교사 비밀번호가 맞지 않습니다."
                    )

                else:
                    st.session_state.update(
                        role="teacher",
                        page="list",
                    )

                    st.rerun()


def teacher_home():
    st.title("교사 관리")

    if st.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

    with st.expander(
        "새 대회 만들기",
        expanded=True,
    ):
        with st.form("create"):
            title = st.text_input(
                "대회 이름",
                "우리 학교 모의투자 대회",
            )

            duration = st.slider(
                "진행 기간(거래일)",
                5,
                60,
                20,
            )

            submitted = st.form_submit_button(
                "대회 만들기",
                type="primary",
            )

            if submitted:
                scenario = random.choice(SCENARIOS)

                load_prices(
                    scenario,
                    duration,
                )

                competition_data = {
                    "code": make_code(),
                    "title": title,
                    "teacher_hash": TEACHER_HASH,
                    "scenario_start": scenario,
                    "duration": duration,
                }

                (
                    db()
                    .table("competitions")
                    .insert(competition_data)
                    .execute()
                )

                st.success("대회를 만들었습니다.")
                st.rerun()

    competitions = (
        db()
        .table("competitions")
        .select("*")
        .order("created_at", desc=True)
        .execute()
        .data
    )

    if not competitions:
        st.info("아직 만들어진 대회가 없습니다.")

    for comp in competitions:
        with st.container(border=True):
            left, middle, right = st.columns([2, 1, 1])

            left.subheader(comp["title"])

            left.markdown(
                f'<div class="code">{comp["code"]}</div>',
                unsafe_allow_html=True,
            )

            middle.metric(
                "진행",
                f"{current_day(comp) + 1}/"
                f"{comp['duration']}일",
            )

            status_text = (
                "진행 중"
                if comp["status"] == "active"
                else "종료"
            )

            right.write(status_text)

            if st.button(
                "관리하기",
                key=f"manage_{comp['id']}",
                use_container_width=True,
            ):
                st.session_state.update(
                    page="manage",
                    competition_id=comp["id"],
                )

                st.rerun()

            if comp["status"] == "ended":
                with st.expander(
                    "🗑️ 종료된 대회 삭제",
                    expanded=True,
                ):
                    delete_competition(comp)


def manage(comp, prices):
    if st.button("← 대회 목록"):
        st.session_state.page = "list"
        st.rerun()

    st.title(comp["title"])

    st.caption(
        f"학생 참가 코드 · {comp['code']}"
    )

    rows = ranking(comp, prices)
    day = current_day(comp)

    metric1, metric2, metric3 = st.columns(3)

    metric1.metric(
        "참가 인원",
        f"{len(rows)}명",
    )

    metric2.metric(
        "진행",
        f"{day + 1}/{comp['duration']}일",
    )

    metric3.metric(
        "상태",
        (
            "진행 중"
            if comp["status"] == "active"
            else "종료"
        ),
    )

    st.subheader("교사 기능")

    if comp["status"] == "active":
        can_advance = (
            day < int(comp["duration"]) - 1
        )

        if st.button(
            "⏭️ 다음 날짜로 넘기기",
            type="primary",
            disabled=not can_advance,
            use_container_width=True,
        ):
            advance_competition_day(comp)
            st.rerun()

        st.caption(
            "매일 자동 진행은 그대로 유지됩니다. "
            "이 버튼을 누르면 즉시 다음 거래일로 넘어갑니다."
        )

    else:
        st.info(
            "종료된 대회입니다. "
            "날짜는 더 이상 넘길 수 없습니다."
        )

    with st.expander(
        "🔑 학생 비밀번호 초기화",
        expanded=False,
    ):
        if not rows:
            st.info("참가한 학생이 없습니다.")

        else:
            reset_labels = [
                f"{row['학번']} {row['이름']}"
                for row in rows
            ]

            reset_selected = st.selectbox(
                "학생 선택",
                reset_labels,
                key=f"reset_student_{comp['id']}",
            )

            reset_person = rows[
                reset_labels.index(reset_selected)
            ]

            new_pin = st.text_input(
                "새 비밀번호",
                type="password",
                max_chars=20,
                key=f"new_pin_{comp['id']}",
                help="4자리 이상 입력하세요.",
            )

            reset_clicked = st.button(
                "이 비밀번호로 초기화",
                key=f"reset_pin_{comp['id']}",
                use_container_width=True,
            )

            if reset_clicked:
                if len(new_pin) < 4:
                    st.error(
                        "새 비밀번호를 "
                        "4자리 이상 입력하세요."
                    )

                else:
                    (
                        db()
                        .table("players")
                        .update(
                            {"pin_hash": sha(new_pin)}
                        )
                        .eq(
                            "id",
                            reset_person["player_id"],
                        )
                        .execute()
                    )

                    st.success(
                        f"{reset_person['이름']} 학생의 "
                        "비밀번호를 초기화했습니다."
                    )

    if comp["status"] == "ended":
        with st.expander(
            "🗑️ 종료된 대회 삭제",
            expanded=True,
        ):
            delete_competition(comp)

    st.divider()

    if rows:
        table = pd.DataFrame(rows).drop(
            columns=["player_id"]
        )

        table.insert(
            0,
            "순위",
            range(1, len(table) + 1),
        )

        table["총자산"] = table["총자산"].map(
            lambda value: f"{value:,.0f}원"
        )

        table["수익률"] = table["수익률"].map(
            lambda value: f"{value:+.2f}%"
        )

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
        )

        labels = [
            f"{row['학번']} {row['이름']}"
            for row in rows
        ]

        selected = st.selectbox(
            "학생 상세 보기",
            labels,
        )

        person = rows[
            labels.index(selected)
        ]

        holdings = (
            db()
            .table("holdings")
            .select("*")
            .eq(
                "player_id",
                person["player_id"],
            )
            .gt("quantity", 0)
            .execute()
            .data
        )

        trades = (
            db()
            .table("trades")
            .select("*")
            .eq(
                "player_id",
                person["player_id"],
            )
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
        )

        left, right = st.columns(2)

        holding_rows = [
            {
                "종목": STOCKS[
                    holding["ticker"]
                ][0],
                "수량": holding["quantity"],
            }
            for holding in holdings
        ]

        left.write("보유 종목")

        left.dataframe(
            pd.DataFrame(holding_rows),
            hide_index=True,
            use_container_width=True,
        )

        trade_rows = [
            {
                "일차": trade["day_index"] + 1,
                "종목": STOCKS[
                    trade["ticker"]
                ][0],
                "구분": (
                    "매수"
                    if trade["side"] == "buy"
                    else "매도"
                ),
                "수량": trade["quantity"],
                "가격": (
                    f"{float(trade['price']):,.0f}원"
                ),
            }
            for trade in trades
        ]

        right.write("최근 거래")

        right.dataframe(
            pd.DataFrame(trade_rows),
            hide_index=True,
            use_container_width=True,
        )

    if (
        comp["status"] == "active"
        and st.button(
            "대회 종료",
            use_container_width=True,
        )
    ):
        (
            db()
            .table("competitions")
            .update({"status": "ended"})
            .eq("id", comp["id"])
            .execute()
        )

        st.rerun()

    if comp["status"] == "ended":
        reveal_market(comp)


def student(comp, player, prices):
    day = current_day(comp)
    rows = ranking(comp, prices)

    me = next(
        row
        for row in rows
        if row["player_id"] == player["id"]
    )

    st.markdown(
        f"""
        <div class="hero">
            <h1>{comp["title"]}</h1>
            <p>
                {day + 1}일 차 ·
                실제 연도와 날짜는 종료 전까지 비공개
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

    metric1, metric2, metric3 = st.columns(3)

    metric1.metric(
        "총자산",
        f"{me['총자산']:,.0f}원",
        f"{me['수익률']:+.2f}%",
    )

    metric2.metric(
        "보유 현금",
        f"{float(player['cash']):,.0f}원",
    )

    rank = [
        row["player_id"]
        for row in rows
    ].index(player["id"]) + 1

    metric3.metric(
        "현재 순위",
        f"{rank}위",
    )

    stock_options = {
        f"{name} · {market}": ticker
        for ticker, (
            name,
            market,
            real_name,
        ) in STOCKS.items()
    }

    selected_stock = st.selectbox(
        "거래할 종목",
        stock_options,
    )

    ticker = stock_options[selected_stock]
    series = prices[ticker].iloc[:day + 1]
    price = float(series.iloc[-1])

    if len(series) > 1:
        previous_price = float(series.iloc[-2])
    else:
        previous_price = price

    change_rate = (
        (price - previous_price)
        / previous_price
        * 100
    )

    st.subheader(STOCKS[ticker][0])

    st.metric(
        "오늘의 종가",
        f"{price:,.0f}원",
        f"{change_rate:+.2f}%",
    )

    chart_data = pd.DataFrame(
        {
            "일차": range(1, len(series) + 1),
            "종가": series.values,
        }
    )

    price_chart = px.line(
        chart_data,
        x="일차",
        y="종가",
        markers=True,
    )

    price_chart.update_traces(
        marker={"size": 11}
    )

    price_chart.update_xaxes(
        tickmode="linear",
        dtick=1,
    )

    if len(series) == 1:
        price_chart.update_yaxes(
            range=[
                price * 0.98,
                price * 1.02,
            ]
        )

    st.plotly_chart(
        price_chart,
        use_container_width=True,
    )

    if comp["status"] == "active":
        quantity = st.number_input(
            "수량",
            min_value=1,
            value=1,
            step=1,
        )

        buy_column, sell_column = st.columns(2)

        if buy_column.button(
            "매수",
            type="primary",
            use_container_width=True,
        ):
            try:
                db().rpc(
                    "execute_trade",
                    {
                        "p_player_id": player["id"],
                        "p_ticker": ticker,
                        "p_side": "buy",
                        "p_quantity": quantity,
                        "p_price": price,
                        "p_day_index": day,
                    },
                ).execute()

                st.rerun()

            except Exception as error:
                st.error(str(error))

        if sell_column.button(
            "매도",
            use_container_width=True,
        ):
            try:
                db().rpc(
                    "execute_trade",
                    {
                        "p_player_id": player["id"],
                        "p_ticker": ticker,
                        "p_side": "sell",
                        "p_quantity": quantity,
                        "p_price": price,
                        "p_day_index": day,
                    },
                ).execute()

                st.rerun()

            except Exception as error:
                st.error(str(error))

    my_holdings = (
        db()
        .table("holdings")
        .select("*")
        .eq("player_id", player["id"])
        .gt("quantity", 0)
        .execute()
        .data
    )

    st.subheader("내 보유 현황")

    if my_holdings:
        portfolio = []

        for holding in my_holdings:
            holding_ticker = holding["ticker"]

            current_price = float(
                prices[holding_ticker].iloc[day]
            )

            portfolio.append(
                {
                    "종목": STOCKS[
                        holding_ticker
                    ][0],
                    "수량": holding["quantity"],
                    "현재가": current_price,
                    "평가금액": (
                        current_price
                        * holding["quantity"]
                    ),
                }
            )

        display_table = pd.DataFrame(portfolio)

        display_table["현재가"] = (
            display_table["현재가"].map(
                lambda value: f"{value:,.0f}원"
            )
        )

        display_table["평가금액"] = (
            display_table["평가금액"].map(
                lambda value: f"{value:,.0f}원"
            )
        )

        left, right = st.columns([3, 2])

        left.dataframe(
            display_table,
            hide_index=True,
            use_container_width=True,
        )

        allocation_rows = [
            {
                "구분": row["종목"],
                "금액": row["평가금액"],
            }
            for row in portfolio
        ]

        allocation_rows.append(
            {
                "구분": "현금",
                "금액": float(player["cash"]),
            }
        )

        allocation = pd.DataFrame(
            allocation_rows
        )

        allocation_chart = px.pie(
            allocation,
            names="구분",
            values="금액",
            hole=0.45,
        )

        right.plotly_chart(
            allocation_chart,
            use_container_width=True,
        )

    else:
        st.info(
            "아직 보유한 종목이 없습니다. "
            "종목을 매수하면 보유 현황과 "
            "자산 비중 그래프가 표시됩니다."
        )

    st.subheader("실시간 순위")

    ranking_table = pd.DataFrame(
        [
            {
                "순위": index + 1,
                "이름": row["이름"],
                "수익률": (
                    f"{row['수익률']:+.2f}%"
                ),
            }
            for index, row in enumerate(rows)
        ]
    )

    st.dataframe(
        ranking_table,
        hide_index=True,
        use_container_width=True,
    )

    if comp["status"] == "ended":
        reveal_market(comp)


try:
    if "role" not in st.session_state:
        login()

    elif st.session_state.role == "teacher":
        if st.session_state.page == "list":
            teacher_home()

        else:
            competition = one(
                "competitions",
                id=st.session_state.competition_id,
            )

            price_data = load_prices(
                str(competition["scenario_start"]),
                int(competition["duration"]),
            )

            manage(
                competition,
                price_data,
            )

    else:
        competition = one(
            "competitions",
            id=st.session_state.competition_id,
        )

        player = one(
            "players",
            id=st.session_state.player_id,
        )

        price_data = load_prices(
            str(competition["scenario_start"]),
            int(competition["duration"]),
        )

        student(
            competition,
            player,
            price_data,
        )

except KeyError:
    st.error(
        "Streamlit Secrets에 Supabase 주소와 키를 "
        "입력하세요. README를 확인하세요."
    )

except Exception as error:
    st.error(
        f"오류가 발생했습니다: {error}"
    )


st.caption(f"앱 버전 · {APP_VERSION}")
