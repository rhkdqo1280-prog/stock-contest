from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf


# 종목코드: (가상 종목명, 시장, 실제 종목명)
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


# 학생에게 보여주는 종목 정보
# 미래 가격은 사용하지 않고 일반적인 기업 특징과
# 현재까지 공개된 가격 움직임만 사용합니다.
STOCK_INFO = {
    "005930.KS": {
        "업종": "전자",
        "규모": "대형주",
        "위험도": "보통",
        "특징": (
            "경기와 소비 수요, 수출 환경의 "
            "영향을 받는 종목입니다."
        ),
        "상승": (
            "전자제품 수요와 수출 회복에 대한 "
            "기대가 커지고 있습니다."
        ),
        "하락": (
            "소비 둔화와 비용 부담에 대한 "
            "우려가 나타나고 있습니다."
        ),
        "보합": (
            "수요 회복 기대와 경기 불확실성이 "
            "함께 나타나고 있습니다."
        ),
    },

    "000660.KS": {
        "업종": "반도체",
        "규모": "대형주",
        "위험도": "높음",
        "특징": (
            "반도체 가격과 세계 정보기술 경기에 "
            "민감한 종목입니다."
        ),
        "상승": (
            "반도체 수요 회복과 가격 상승 기대가 "
            "커지고 있습니다."
        ),
        "하락": (
            "반도체 수요 둔화와 재고 부담에 대한 "
            "우려가 커지고 있습니다."
        ),
        "보합": (
            "반도체 업황의 방향을 확인하려는 "
            "움직임이 이어지고 있습니다."
        ),
    },

    "035420.KS": {
        "업종": "인터넷·포털",
        "규모": "대형주",
        "위험도": "보통",
        "특징": (
            "광고, 콘텐츠와 온라인 서비스 성장의 "
            "영향을 받습니다."
        ),
        "상승": (
            "온라인 서비스 성장과 광고시장 회복 "
            "기대가 나타나고 있습니다."
        ),
        "하락": (
            "광고시장 둔화와 성장 비용에 대한 "
            "우려가 나타나고 있습니다."
        ),
        "보합": (
            "서비스 성장 기대와 비용 부담이 "
            "맞서고 있습니다."
        ),
    },

    "035720.KS": {
        "업종": "플랫폼",
        "규모": "대형주",
        "위험도": "높음",
        "특징": (
            "플랫폼 이용자와 신사업 성과, "
            "규제 변화에 민감합니다."
        ),
        "상승": (
            "플랫폼 이용 증가와 신사업 성장 기대가 "
            "커지고 있습니다."
        ),
        "하락": (
            "플랫폼 규제와 신사업 비용에 대한 "
            "우려가 나타나고 있습니다."
        ),
        "보합": (
            "신사업 기대와 규제 불확실성이 "
            "함께 나타나고 있습니다."
        ),
    },

    "051910.KS": {
        "업종": "화학·소재",
        "규모": "대형주",
        "위험도": "높음",
        "특징": (
            "원자재 가격과 세계 제조업 경기의 "
            "영향을 크게 받습니다."
        ),
        "상승": (
            "소재 수요 회복과 원가 안정에 대한 "
            "기대가 커지고 있습니다."
        ),
        "하락": (
            "원자재 비용과 수요 둔화에 대한 "
            "우려가 나타나고 있습니다."
        ),
        "보합": (
            "원가 부담과 수요 회복 기대가 "
            "맞서고 있습니다."
        ),
    },

    "068270.KS": {
        "업종": "바이오",
        "규모": "대형주",
        "위험도": "높음",
        "특징": (
            "신제품, 허가와 연구개발 성과에 따라 "
            "변동할 수 있습니다."
        ),
        "상승": (
            "신제품과 해외시장 확대에 대한 "
            "기대가 커지고 있습니다."
        ),
        "하락": (
            "연구개발 불확실성과 경쟁 심화에 대한 "
            "우려가 나타나고 있습니다."
        ),
        "보합": (
            "성장 기대와 연구개발 불확실성이 "
            "함께 나타나고 있습니다."
        ),
    },

    "207940.KS": {
        "업종": "바이오 생산",
        "규모": "대형주",
        "위험도": "보통",
        "특징": (
            "의약품 생산 계약과 설비 투자 소식의 "
            "영향을 받습니다."
        ),
        "상승": (
            "의약품 생산 계약과 수주 확대에 대한 "
            "기대가 나타나고 있습니다."
        ),
        "하락": (
            "설비 투자 비용과 수주 불확실성에 대한 "
            "우려가 나타나고 있습니다."
        ),
        "보합": (
            "수주 성장 기대와 투자 비용 부담이 "
            "맞서고 있습니다."
        ),
    },

    "096530.KQ": {
        "업종": "진단·의료",
        "규모": "중형주",
        "위험도": "매우 높음",
        "특징": (
            "질병 유행과 진단 수요 변화에 따라 "
            "가격 변동이 큽니다."
        ),
        "상승": (
            "진단 수요 증가와 해외 판매 확대 "
            "기대가 나타나고 있습니다."
        ),
        "하락": (
            "진단 수요 감소와 실적 둔화에 대한 "
            "우려가 나타나고 있습니다."
        ),
        "보합": (
            "새로운 수요 기대와 기존 수요 감소 "
            "우려가 맞서고 있습니다."
        ),
    },
}


# 교사가 선택할 수 있는 실제 과거 주식시장 시작 시점입니다.
# 대회가 20일이면 여기서 선택된 날짜부터
# 연속된 실제 거래일 20일을 사용합니다.
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
    use_real_prices: bool = False,
):
    """
    대회 진행에 사용할 실제 과거 주가를 불러옵니다.

    duration이 20이면 1년을 20개로 압축하는 것이 아니라,
    시작 시점부터 연속된 실제 거래일 20일을 사용합니다.
    """

    start = datetime.strptime(
        scenario_start,
        "%Y-%m-%d",
    )

    result = {}

    for ticker in STOCKS:
        frame = yf.download(
            ticker,
            start=start,
            end=start + timedelta(days=180),
            progress=False,
            auto_adjust=False,
        )

        if frame.empty:
            raise RuntimeError(
                f"{STOCKS[ticker][0]}의 과거 주가를 "
                "불러오지 못했습니다."
            )

        close = frame["Close"]

        # yfinance 버전에 따라 데이터프레임으로
        # 반환되는 경우를 처리합니다.
        if isinstance(
            close,
            pd.DataFrame,
        ):
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

        if use_real_prices:
            # 실제 종가 그대로 사용
            result[ticker] = (
                close.round(0)
            )

        else:
            # 실제 등락률 흐름은 그대로 유지하면서
            # 모든 종목의 첫날 가격을 10,000원으로 맞춥니다.
            result[ticker] = (
                close
                / close.iloc[0]
                * 10000
            ).round(-1)

    return result


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def load_pre_history(
    scenario_start: str,
    history_days: int,
    use_real_prices: bool = False,
):
    """
    대회 시작 전 5일, 10일 또는 20일의
    실제 과거 가격 흐름을 불러옵니다.
    """

    start = datetime.strptime(
        scenario_start,
        "%Y-%m-%d",
    )

    result = {}

    for ticker in STOCKS:
        frame = yf.download(
            ticker,
            start=start - timedelta(days=90),
            end=start + timedelta(days=10),
            progress=False,
            auto_adjust=False,
        )

        if frame.empty:
            raise RuntimeError(
                f"{STOCKS[ticker][0]}의 이전 주가를 "
                "불러오지 못했습니다."
            )

        close = frame["Close"]

        if isinstance(
            close,
            pd.DataFrame,
        ):
            close = close.iloc[:, 0]

        close = (
            close
            .dropna()
            .astype(float)
        )

        # 시간대 정보가 있는 날짜와 없는 날짜가
        # 비교될 때 생길 수 있는 오류를 방지합니다.
        date_index = (
            close.index.tz_localize(None)
        )

        before = close[
            date_index < start
        ].iloc[-history_days:]

        after = close[
            date_index >= start
        ]

        if (
            len(before) < history_days
            or after.empty
        ):
            raise RuntimeError(
                "대회 시작 전 주가 데이터가 부족합니다."
            )

        if use_real_prices:
            result[ticker] = (
                before
                .reset_index(drop=True)
                .round(0)
            )

        else:
            # 대회 첫날 가격을 10,000원으로 환산합니다.
            # 시작 전 가격도 같은 비율로 바꾸므로
            # 실제 등락률 흐름은 그대로 유지됩니다.
            first_day_price = float(
                after.iloc[0]
            )

            result[ticker] = (
                before
                / first_day_price
                * 10000
            ).reset_index(
                drop=True
            ).round(-1)

    return result
