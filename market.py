from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf


STOCKS = {
    "005930.KS": (
        "A전자",
        "KOSPI",
        "삼성전자",
    ),
    "000660.KS": (
        "B반도체",
        "KOSPI",
        "SK하이닉스",
    ),
    "035420.KS": (
        "C포털",
        "KOSPI",
        "NAVER",
    ),
    "035720.KS": (
        "D플랫폼",
        "KOSPI",
        "카카오",
    ),
    "051910.KS": (
        "E화학",
        "KOSPI",
        "LG화학",
    ),
    "068270.KS": (
        "F바이오",
        "KOSPI",
        "셀트리온",
    ),
    "207940.KS": (
        "G바이오",
        "KOSPI",
        "삼성바이오로직스",
    ),
    "096530.KQ": (
        "H진단",
        "KOSDAQ",
        "씨젠",
    ),
}


SCENARIOS = [
    "2017-03-02",
    "2017-08-01",
    "2018-03-02",
    "2018-08-01",
    "2019-01-02",
    "2019-07-01",
    "2020-01-02",
    "2020-08-03",
    "2021-02-01",
    "2021-09-01",
    "2022-01-03",
    "2022-08-01",
    "2023-01-02",
    "2023-07-03",
    "2024-01-02",
    "2024-07-01",
    "2025-01-02",
    "2025-07-01",
]


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def load_prices(
    scenario_start: str,
    duration: int,
):
    start = datetime.strptime(
        scenario_start,
        "%Y-%m-%d",
    )

    end = start + timedelta(days=180)
    result = {}

    for ticker in STOCKS:
        frame = yf.download(
            ticker,
            start=start,
            end=end,
            progress=False,
            auto_adjust=False,
        )

        if frame.empty:
            stock_name = STOCKS[ticker][0]

            raise RuntimeError(
                f"{stock_name}의 과거 주가를 "
                "불러오지 못했습니다."
            )

        close = frame["Close"]

        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        close = (
            close
            .dropna()
            .astype(float)
            .iloc[:duration]
            .reset_index(drop=True)
        )

        if len(close) < duration:
            raise RuntimeError(
                "선택한 기간의 주가 데이터가 부족합니다."
            )

        # 실제 등락률은 유지하면서
        # 모든 종목을 10,000원에서 시작하게 변경
        normalized_price = (
            close
            / close.iloc[0]
            * 10000
        ).round(-1)

        result[ticker] = normalized_price

    return result
