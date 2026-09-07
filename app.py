import random
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st

from database import db, one, sha
from market import STOCKS, STOCK_INFO, SCENARIOS, load_prices


st.set_page_config(
    page_title="주식 타임머신",
    page_icon="📈",
    layout="wide",
)

KST = pytz.timezone("Asia/Seoul")
APP_VERSION = "2026.09.07-11"
TEACHER_HASH = (
    "4d0394d43c5c04173e8de51f3e4fff9"
    "ba8f5a2ee5e229020ea19511f48b43c6b"
)

st.markdown("""
<style>
.stApp{background:#f4f7fb}
.block-container{max-width:1400px;padding-top:5rem!important}
.hero{padding:28px;border-radius:22px;background:linear-gradient(130deg,#10203b,#1557d5);color:white;margin-bottom:18px}
.hero h1{margin:0;font-size:2.4rem}
.hero p{opacity:.8;margin:.5rem 0 0}
.code{font-size:2rem;font-weight:800;letter-spacing:.15em;color:#1557d5}

@media (max-width:768px){
 .block-container{padding:4.5rem .8rem 2rem!important}
 .hero{padding:18px 16px;border-radius:16px;margin-bottom:12px}
 .hero h1{font-size:1.65rem;line-height:1.25}
 .hero p{font-size:.9rem}
 .code{font-size:1.5rem;letter-spacing:.1em}
 [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.5rem}
 [data-testid="stColumn"]{min-width:100%!important;flex:1 1 100%!important}
 [data-testid="stMetric"]{padding:.35rem 0}
 [data-testid="stDataFrame"]{overflow-x:auto}
 .stButton button,.stFormSubmitButton button{min-height:46px;font-size:1rem}
 h1{font-size:1.8rem!important}
 h2{font-size:1.45rem!important}
 h3{font-size:1.2rem!important}
}
</style>
""", unsafe_allow_html=True)


def setting(comp, key):
    return bool(comp.get(key, False))


def display_stock_name(comp, ticker):
    if setting(comp, "show_real_names"):
        return STOCKS[ticker][2]

    return STOCKS[ticker][0]


def display_period(comp, day):
    if setting(comp, "show_year"):
        return (
            f"{str(comp['scenario_start'])[:4]}년 · "
            f"{day + 1}일 차"
        )

    return (
        f"{day + 1}일 차 · "
        "실제 연도와 날짜는 비공개"
    )


def make_code():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    while True:
        value = "".join(
            random.choice(chars)
            for _ in range(6)
        )

        if not one("competitions", code=value):
            return value


def current_day(comp):
    started = datetime.fromisoformat(
        comp["starts_at"].replace("Z", "+00:00")
    ).astimezone(KST).date()

    elapsed = (
        datetime.now(KST).date() - started
    ).days

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

    player_ids = [
        player["id"]
        for player in players
    ]

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
            float(
                prices[
                    holding["ticker"]
                ].iloc[day]
            ) * holding["quantity"]
            for holding in holdings
            if holding["player_id"] == player["id"]
        )

        asset = (
            float(player["cash"])
            + stock_value
        )

        initial_cash = float(
            comp["initial_cash"]
        )

        rows.append({
            "학번": player["student_id"],
            "이름": player["name"],
            "총자산": asset,
            "수익률": (
                (asset - initial_cash)
                / initial_cash
                * 100
            ),
            "player_id": player["id"],
        })

    return sorted(
        rows,
        key=lambda row: row["총자산"],
        reverse=True,
    )


def reveal_market(comp):
    year = str(comp["scenario_start"])[:4]

    st.success(
        f"정답 공개 · "
        f"{year}년 실제 한국 주식시장"
    )

    st.caption(
        "대회 중에는 종목명과 가격을 바꿨지만 "
        "실제 일별 등락률은 그대로 사용했습니다."
    )

    reveal_rows = [
        {
            "대회 종목": alias,
            "실제 종목": real_name,
            "시장": market,
        }
        for alias, market, real_name
        in STOCKS.values()
    ]

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

    if st.button(
        "대회 영구 삭제",
        key=f"delete_{comp['id']}",
        disabled=confirmation != comp["code"],
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
        st.session_state.pop(
            "competition_id",
            None,
        )

        st.rerun()


def advance_competition_day(comp):
    started = datetime.fromisoformat(
        comp["starts_at"].replace(
            "Z",
            "+00:00",
        )
    )

    new_started = (
        started - timedelta(days=1)
    )

    (
        db()
        .table("competitions")
        .update({
            "starts_at": new_started.isoformat()
        })
        .eq("id", comp["id"])
        .execute()
    )


def investment_information(
    prices,
    ticker,
    day,
):
    info = STOCK_INFO[ticker]

    if day == 0:
        trend = "판단 자료 부족"
        mood = "대회 첫 거래일"
        news = info["보합"]

    else:
        start = max(0, day - 4)

        recent = prices[ticker].iloc[
            start:day + 1
        ]

        momentum = (
            float(recent.iloc[-1])
            / float(recent.iloc[0])
            - 1
        ) * 100

        if momentum > 2:
            trend = "상승세"
        elif momentum < -2:
            trend = "하락세"
        else:
            trend = "횡보"

        market_changes = []

        for values in prices.values():
            change = (
                float(values.iloc[day])
                / float(values.iloc[day - 1])
                - 1
            ) * 100

            market_changes.append(change)

        average = (
            sum(market_changes)
            / len(market_changes)
        )

        if average > 1:
            mood = "전체적으로 강한 상승"
        elif average < -1:
            mood = "전체적으로 강한 하락"
        elif average > 0.2:
            mood = "대체로 상승"
        elif average < -0.2:
            mood = "대체로 하락"
        else:
            mood = "혼조세"

        today_change = (
            float(prices[ticker].iloc[day])
            / float(prices[ticker].iloc[day - 1])
            - 1
        ) * 100

        if today_change > 1:
            news = info["상승"]
        elif today_change < -1:
            news = info["하락"]
        else:
            news = info["보합"]

    st.subheader("투자 정보")

    first, second, third = st.columns(3)

    first.metric(
        "기업 유형",
        f"{info['업종']} · {info['규모']}",
    )

    second.metric(
        "위험도",
        info["위험도"],
    )

    third.metric(
        "최근 흐름",
        trend,
    )

    st.info(
        f"📢 오늘의 시장 분위기: {mood}\n\n"
        f"📰 오늘의 가상 뉴스: {news}"
    )

    st.caption(
        f"투자 특징 · {info['특징']} | "
        "공개된 현재와 과거 정보만 사용하며 "
        "미래 가격은 반영하지 않습니다."
    )


def login():
    st.markdown(
        """
        <div class="hero">
            <h1>📈 주식 타임머신</h1>
            <p>
                연도를 숨긴 과거 한국 주식시장
                모의투자 대회
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    student_tab, teacher_tab = st.tabs([
        "학생 참가",
        "교사 관리",
    ])

    with student_tab:
        with st.form("student_login"):
            code = st.text_input(
                "대회 코드",
                max_chars=6,
            ).strip().upper()

            student_id = st.text_input(
                "학번"
            ).strip()

            name = st.text_input(
                "이름"
            ).strip()

            pin = st.text_input(
                "개인 비밀번호",
                type="password",
            )

            submitted = st.form_submit_button(
                "참가 또는 다시 접속",
                type="primary",
                use_container_width=True,
            )

            if submitted:
                comp = one(
                    "competitions",
                    code=code,
                )

                if not comp:
                    st.error(
                        "대회 코드를 확인하세요."
                    )

                elif not student_id or not name:
                    st.error(
                        "학번과 이름을 입력하세요."
                    )

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
                            player = (
                                db()
                                .table("players")
                                .insert({
                                    "competition_id": comp["id"],
                                    "student_id": student_id,
                                    "name": name,
                                    "pin_hash": sha(pin),
                                    "cash": comp["initial_cash"],
                                })
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
            teacher_pin = st.text_input(
                "교사 관리 비밀번호",
                type="password",
                max_chars=4,
            )

            submitted = st.form_submit_button(
                "내 대회 보기",
                use_container_width=True,
            )

            if submitted:
                if teacher_pin != "6340":
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

            available_years = sorted({
                scenario[:4]
                for scenario in SCENARIOS
            })

            year_choice = st.selectbox(
                "주식시장 연도",
                ["랜덤"] + [
                    f"{year}년"
                    for year in available_years
                ],
            )

            st.write("학생 화면 공개 설정")

            show_real_names = st.checkbox(
                "실제 종목명 공개"
            )

            use_real_prices = st.checkbox(
                "실제 주가 사용"
            )

            show_year = st.checkbox(
                "연도 공개"
            )

            if (
                show_real_names
                and use_real_prices
                and not show_year
            ):
                st.warning(
                    "실제 종목명과 실제 가격을 함께 공개하면 "
                    "학생이 검색해서 비공개 연도를 "
                    "알아낼 수 있습니다."
                )

            submitted = st.form_submit_button(
                "대회 만들기",
                type="primary",
                use_container_width=True,
            )

            if submitted:
                if year_choice == "랜덤":
                    candidates = SCENARIOS
                else:
                    selected_year = year_choice[:4]

                    candidates = [
                        scenario
                        for scenario in SCENARIOS
                        if scenario.startswith(
                            selected_year
                        )
                    ]

                scenario = random.choice(
                    candidates
                )

                load_prices(
                    scenario,
                    duration,
                    use_real_prices,
                )

                (
                    db()
                    .table("competitions")
                    .insert({
                        "code": make_code(),
                        "title": title,
                        "teacher_hash": TEACHER_HASH,
                        "scenario_start": scenario,
                        "duration": duration,
                        "show_real_names": show_real_names,
                        "use_real_prices": use_real_prices,
                        "show_year": show_year,
                    })
                    .execute()
                )

                st.success(
                    "대회를 만들었습니다."
                )

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
        st.info(
            "아직 만들어진 대회가 없습니다."
        )

    for comp in competitions:
        with st.container(border=True):
            left, middle, right = st.columns(
                [2, 1, 1]
            )

            left.subheader(
                comp["title"]
            )

            left.markdown(
                f'<div class="code">{comp["code"]}</div>',
                unsafe_allow_html=True,
            )

            year = str(
                comp["scenario_start"]
            )[:4]

            settings_text = (
                f"{year}년 · "
                f"{'실제 종목명' if setting(comp, 'show_real_names') else '가상 종목명'} · "
                f"{'실제 가격' if setting(comp, 'use_real_prices') else '10,000원 시작'} · "
                f"{'연도 공개' if setting(comp, 'show_year') else '연도 비공개'}"
            )

            left.caption(
                f"교사용 설정 · {settings_text}"
            )

            middle.metric(
                "진행",
                f"{current_day(comp) + 1}/"
                f"{comp['duration']}일",
            )

            right.write(
                "진행 중"
                if comp["status"] == "active"
                else "종료"
            )

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

    first, second, third = st.columns(3)

    first.metric(
        "참가 인원",
        f"{len(rows)}명",
    )

    second.metric(
        "진행",
        f"{day + 1}/{comp['duration']}일",
    )

    third.metric(
        "상태",
        "진행 중"
        if comp["status"] == "active"
        else "종료",
    )

    st.subheader("교사 기능")

    if comp["status"] == "active":
        if st.button(
            "⏭️ 다음 날짜로 넘기기",
            type="primary",
            disabled=(
                day
                >= int(comp["duration"]) - 1
            ),
            use_container_width=True,
        ):
            advance_competition_day(comp)
            st.rerun()

    with st.expander(
        "🔑 학생 비밀번호 초기화"
    ):
        if not rows:
            st.info(
                "참가한 학생이 없습니다."
            )

        else:
            labels = [
                f"{row['학번']} {row['이름']}"
                for row in rows
            ]

            selected_label = st.selectbox(
                "학생 선택",
                labels,
            )

            selected_student = rows[
                labels.index(selected_label)
            ]

            new_pin = st.text_input(
                "새 비밀번호",
                type="password",
            )

            if st.button(
                "이 비밀번호로 초기화"
            ):
                if len(new_pin) < 4:
                    st.error(
                        "4자리 이상 입력하세요."
                    )
                else:
                    (
                        db()
                        .table("players")
                        .update({
                            "pin_hash": sha(new_pin)
                        })
                        .eq(
                            "id",
                            selected_student["player_id"],
                        )
                        .execute()
                    )

                    st.success(
                        "비밀번호를 초기화했습니다."
                    )

    if comp["status"] == "ended":
        with st.expander(
            "🗑️ 종료된 대회 삭제",
            expanded=True,
        ):
            delete_competition(comp)

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
            hide_index=True,
            use_container_width=True,
        )

        labels = [
            f"{row['학번']} {row['이름']}"
            for row in rows
        ]

        selected = st.selectbox(
            "학생 상세 보기",
            labels,
        )

        selected_student = rows[
            labels.index(selected)
        ]

        holdings = (
            db()
            .table("holdings")
            .select("*")
            .eq(
                "player_id",
                selected_student["player_id"],
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
                selected_student["player_id"],
            )
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
        )

        left, right = st.columns(2)

        left.write("보유 종목")

        left.dataframe(
            pd.DataFrame([
                {
                    "종목": display_stock_name(
                        comp,
                        holding["ticker"],
                    ),
                    "수량": holding["quantity"],
                }
                for holding in holdings
            ]),
            hide_index=True,
            use_container_width=True,
        )

        right.write("최근 거래")

        right.dataframe(
            pd.DataFrame([
                {
                    "일차": trade["day_index"] + 1,
                    "종목": display_stock_name(
                        comp,
                        trade["ticker"],
                    ),
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
            ]),
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

    if (
        comp["status"] == "ended"
        and not setting(
            comp,
            "show_real_names",
        )
    ):
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
            <p>{display_period(comp, day)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

    first, second, third = st.columns(3)

    first.metric(
        "총자산",
        f"{me['총자산']:,.0f}원",
        f"{me['수익률']:+.2f}%",
    )

    second.metric(
        "보유 현금",
        f"{float(player['cash']):,.0f}원",
    )

    rank = [
        row["player_id"]
        for row in rows
    ].index(player["id"]) + 1

    third.metric(
        "현재 순위",
        f"{rank}위",
    )

    options = {
        (
            f"{display_stock_name(comp, ticker)}"
            f" · {values[1]}"
        ): ticker
        for ticker, values in STOCKS.items()
    }

    ticker = options[
        st.selectbox(
            "거래할 종목",
            options,
        )
    ]

    series = prices[ticker].iloc[
        :day + 1
    ]

    price = float(series.iloc[-1])

    previous_price = (
        float(series.iloc[-2])
        if len(series) > 1
        else price
    )

    investment_information(
        prices,
        ticker,
        day,
    )

    st.subheader(
        display_stock_name(
            comp,
            ticker,
        )
    )

    st.metric(
        "오늘의 종가",
        f"{price:,.0f}원",
        (
            f"{(price - previous_price) / previous_price * 100:+.2f}%"
        ),
    )

    chart_data = pd.DataFrame({
        "일차": range(1, len(series) + 1),
        "종가": series.values,
    })

    chart = px.line(
        chart_data,
        x="일차",
        y="종가",
        markers=True,
    )

    chart.update_traces(
        marker={"size": 11}
    )

    chart.update_xaxes(
        tickmode="linear",
        dtick=1,
    )

    if len(series) == 1:
        chart.update_yaxes(
            range=[
                price * 0.98,
                price * 1.02,
            ]
        )

    st.plotly_chart(
        chart,
        use_container_width=True,
    )

    if comp["status"] == "active":
        quantity = st.number_input(
            "수량",
            min_value=1,
            value=1,
            step=1,
        )

        buy, sell = st.columns(2)

        if buy.button(
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

        if sell.button(
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
            current_price = float(
                prices[
                    holding["ticker"]
                ].iloc[day]
            )

            portfolio.append({
                "종목": display_stock_name(
                    comp,
                    holding["ticker"],
                ),
                "수량": holding["quantity"],
                "현재가": current_price,
                "평가금액": (
                    current_price
                    * holding["quantity"]
                ),
            })

        display = pd.DataFrame(portfolio)

        display["현재가"] = display[
            "현재가"
        ].map(
            lambda value: f"{value:,.0f}원"
        )

        display["평가금액"] = display[
            "평가금액"
        ].map(
            lambda value: f"{value:,.0f}원"
        )

        left, right = st.columns([3, 2])

        left.dataframe(
            display,
            hide_index=True,
            use_container_width=True,
        )

        allocation = pd.DataFrame(
            [
                {
                    "구분": row["종목"],
                    "금액": row["평가금액"],
                }
                for row in portfolio
            ]
            + [{
                "구분": "현금",
                "금액": float(player["cash"]),
            }]
        )

        right.plotly_chart(
            px.pie(
                allocation,
                names="구분",
                values="금액",
                hole=0.45,
            ),
            use_container_width=True,
        )

    else:
        st.info(
            "아직 보유한 종목이 없습니다. "
            "종목을 매수하면 보유 현황과 "
            "자산 비중 그래프가 표시됩니다."
        )

    st.subheader("실시간 순위")

    st.dataframe(
        pd.DataFrame([
            {
                "순위": index + 1,
                "이름": row["이름"],
                "수익률": f"{row['수익률']:+.2f}%",
            }
            for index, row in enumerate(rows)
        ]),
        hide_index=True,
        use_container_width=True,
    )

    if (
        comp["status"] == "ended"
        and not setting(
            comp,
            "show_real_names",
        )
    ):
        reveal_market(comp)


try:
    if "role" not in st.session_state:
        login()

    elif st.session_state.role == "teacher":
        if st.session_state.page == "list":
            teacher_home()

        else:
            comp = one(
                "competitions",
                id=st.session_state.competition_id,
            )

            prices = load_prices(
                str(comp["scenario_start"]),
                int(comp["duration"]),
                setting(
                    comp,
                    "use_real_prices",
                ),
            )

            manage(comp, prices)

    else:
        comp = one(
            "competitions",
            id=st.session_state.competition_id,
        )

        player = one(
            "players",
            id=st.session_state.player_id,
        )

        prices = load_prices(
            str(comp["scenario_start"]),
            int(comp["duration"]),
            setting(
                comp,
                "use_real_prices",
            ),
        )

        student(
            comp,
            player,
            prices,
        )

except KeyError:
    st.error(
        "Streamlit Secrets에 Supabase 주소와 키를 "
        "입력하세요."
    )

except Exception as error:
    st.error(
        f"오류가 발생했습니다: {error}"
    )


st.caption(
    f"앱 버전 · {APP_VERSION}"
)
