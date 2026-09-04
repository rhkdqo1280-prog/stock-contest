import hashlib
from supabase import create_client
import streamlit as st

@st.cache_resource
def db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])

def sha(value: str):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def one(table: str, **filters):
    query = db().table(table).select("*")
    for key, value in filters.items(): query = query.eq(key, value)
    rows = query.limit(1).execute().data
    return rows[0] if rows else None
