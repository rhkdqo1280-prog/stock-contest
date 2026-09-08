import hashlib

import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def db() -> Client:
    """
    Streamlit Secrets에 저장된 Supabase 정보를 이용해
    데이터베이스에 연결합니다.
    """

    supabase_url = st.secrets[
        "SUPABASE_URL"
    ]

    supabase_service_key = st.secrets[
        "SUPABASE_SERVICE_KEY"
    ]

    return create_client(
        supabase_url,
        supabase_service_key,
    )


def sha(text: str) -> str:
    """
    비밀번호를 그대로 데이터베이스에 저장하지 않고
    SHA-256 해시값으로 변환합니다.
    """

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def one(
    table_name: str,
    **conditions,
):
    """
    조건에 맞는 데이터 한 건을 가져옵니다.
    데이터가 없으면 None을 반환합니다.
    """

    query = (
        db()
        .table(table_name)
        .select("*")
    )

    for column, value in conditions.items():
        query = query.eq(
            column,
            value,
        )

    result = (
        query
        .limit(1)
        .execute()
        .data
    )

    if result:
        return result[0]

    return None
