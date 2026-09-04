import random
from datetime import datetime
import pandas as pd
import plotly.express as px
import pytz
import streamlit as st
from database import db, one, sha
from market import STOCKS, SCENARIOS, load_prices

st.set_page_config(page_title="주식 타임머신",page_icon="📈",layout="wide")
KST=pytz.timezone("Asia/Seoul")
st.markdown("""<style>
.stApp{background:#f4f7fb}.block-container{max-width:1400px;padding-top:1.4rem}
.hero{padding:28px;border-radius:22px;background:linear-gradient(130deg,#10203b,#1557d5);color:white;margin-bottom:18px}
.hero h1{margin:0;font-size:2.4rem}.hero p{opacity:.8;margin:.5rem 0 0}
.code{font-size:2rem;font-weight:800;letter-spacing:.15em;color:#1557d5}
</style>""",unsafe_allow_html=True)

def make_code():
    chars="ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        value="".join(random.choice(chars) for _ in range(6))
        if not one("competitions",code=value): return value

def current_day(comp):
    started=datetime.fromisoformat(comp["starts_at"].replace("Z","+00:00")).astimezone(KST).date()
    return max(0,min(int(comp["duration"])-1,(datetime.now(KST).date()-started).days))

def ranking(comp,prices):
    day=current_day(comp)
    players=db().table("players").select("*").eq("competition_id",comp["id"]).execute().data
    ids=[p["id"] for p in players]
    holds=db().table("holdings").select("*").in_("player_id",ids).gt("quantity",0).execute().data if ids else []
    rows=[]
    for player in players:
        asset=float(player["cash"])+sum(float(prices[h["ticker"]].iloc[day])*h["quantity"] for h in holds if h["player_id"]==player["id"])
        rows.append({"학번":player["student_id"],"이름":player["name"],"총자산":asset,"수익률":(asset-float(comp["initial_cash"]))/float(comp["initial_cash"])*100,"player_id":player["id"]})
    return sorted(rows,key=lambda row:row["총자산"],reverse=True)

def login():
    st.markdown('<div class="hero"><h1>📈 주식 타임머신</h1><p>연도를 숨긴 과거 한국 주식시장 모의투자 대회</p></div>',unsafe_allow_html=True)
    student,teacher=st.tabs(["학생 참가","교사 관리"])
    with student:
        with st.form("student_login"):
            code=st.text_input("대회 코드",max_chars=6).strip().upper()
            student_id=st.text_input("학번").strip()
            name=st.text_input("이름").strip()
            pin=st.text_input("개인 비밀번호",type="password",help="다른 컴퓨터에서 다시 접속할 때 사용합니다.")
            if st.form_submit_button("참가 또는 다시 접속",type="primary",use_container_width=True):
                comp=one("competitions",code=code)
                if not comp: st.error("대회 코드를 확인하세요.")
                elif not student_id or not name: st.error("학번과 이름을 입력하세요.")
                elif len(pin)<4: st.error("비밀번호는 4자리 이상이어야 합니다.")
                else:
                    player=one("players",competition_id=comp["id"],student_id=student_id)
                    if player and player["pin_hash"]!=sha(pin): st.error("학번 또는 비밀번호가 맞지 않습니다.")
                    else:
                        if not player:
                            player=db().table("players").insert({"competition_id":comp["id"],"student_id":student_id,"name":name,"pin_hash":sha(pin),"cash":comp["initial_cash"]}).execute().data[0]
                        st.session_state.update(role="student",competition_id=comp["id"],player_id=player["id"]);st.rerun()
    with teacher:
        with st.form("teacher_login"):
            pin=st.text_input("교사 관리 비밀번호",type="password")
            if st.form_submit_button("내 대회 보기",use_container_width=True):
                if len(pin)<4: st.error("비밀번호를 4자리 이상 입력하세요.")
                else: st.session_state.update(role="teacher",teacher_hash=sha(pin),page="list");st.rerun()

def teacher_home():
    teacher_hash=st.session_state.teacher_hash
    st.title("교사 관리")
    if st.button("로그아웃"):st.session_state.clear();st.rerun()
    with st.expander("새 대회 만들기",expanded=True):
        with st.form("create"):
            title=st.text_input("대회 이름","우리 학교 모의투자 대회")
            duration=st.slider("진행 기간(거래일)",5,60,20)
            if st.form_submit_button("대회 만들기",type="primary"):
                scenario=random.choice(SCENARIOS);load_prices(scenario,duration)
                db().table("competitions").insert({"code":make_code(),"title":title,"teacher_hash":teacher_hash,"scenario_start":scenario,"duration":duration}).execute()
                st.success("대회를 만들었습니다.");st.rerun()
    comps=db().table("competitions").select("*").eq("teacher_hash",teacher_hash).order("created_at",desc=True).execute().data
    if not comps: st.info("이 비밀번호로 만든 대회가 없습니다.")
    for comp in comps:
        with st.container(border=True):
            left,middle,right=st.columns([2,1,1])
            left.subheader(comp["title"]);left.markdown(f'<div class="code">{comp["code"]}</div>',unsafe_allow_html=True)
            middle.metric("진행",f"{current_day(comp)+1}/{comp['duration']}일")
            right.write("진행 중" if comp["status"]=="active" else "종료")
            if st.button("관리하기",key=comp["id"]):st.session_state.update(page="manage",competition_id=comp["id"]);st.rerun()

def manage(comp,prices):
    if st.button("← 대회 목록"):st.session_state.page="list";st.rerun()
    st.title(comp["title"]);st.caption(f"학생 참가 코드 · {comp['code']}")
    rows=ranking(comp,prices)
    a,b,c=st.columns(3);a.metric("참가 인원",f"{len(rows)}명");b.metric("진행",f"{current_day(comp)+1}/{comp['duration']}일");c.metric("상태","진행 중" if comp["status"]=="active" else "종료")
    if rows:
        table=pd.DataFrame(rows).drop(columns=["player_id"]);table.insert(0,"순위",range(1,len(table)+1))
        table["총자산"]=table["총자산"].map(lambda x:f"{x:,.0f}원");table["수익률"]=table["수익률"].map(lambda x:f"{x:+.2f}%")
        st.dataframe(table,use_container_width=True,hide_index=True)
        labels=[f"{r['학번']} {r['이름']}" for r in rows];selected=st.selectbox("학생 상세 보기",labels);person=rows[labels.index(selected)]
        holds=db().table("holdings").select("*").eq("player_id",person["player_id"]).gt("quantity",0).execute().data
        trades=db().table("trades").select("*").eq("player_id",person["player_id"]).order("created_at",desc=True).limit(50).execute().data
        left,right=st.columns(2)
        left.write("보유 종목");left.dataframe(pd.DataFrame([{"종목":STOCKS[h["ticker"]][0],"수량":h["quantity"]} for h in holds]),hide_index=True,use_container_width=True)
        right.write("최근 거래");right.dataframe(pd.DataFrame([{"일차":t["day_index"]+1,"종목":STOCKS[t["ticker"]][0],"구분":"매수" if t["side"]=="buy" else "매도","수량":t["quantity"],"가격":f"{float(t['price']):,.0f}원"} for t in trades]),hide_index=True,use_container_width=True)
    if comp["status"]=="active" and st.button("대회 종료"):
        db().table("competitions").update({"status":"ended"}).eq("id",comp["id"]).execute();st.rerun()

def student(comp,player,prices):
    day=current_day(comp);rows=ranking(comp,prices);me=next(r for r in rows if r["player_id"]==player["id"])
    st.markdown(f'<div class="hero"><h1>{comp["title"]}</h1><p>{day+1}일 차 · 실제 연도와 날짜는 종료 전까지 비공개</p></div>',unsafe_allow_html=True)
    if st.button("로그아웃"):st.session_state.clear();st.rerun()
    a,b,c=st.columns(3);a.metric("총자산",f"{me['총자산']:,.0f}원",f"{me['수익률']:+.2f}%");b.metric("보유 현금",f"{float(player['cash']):,.0f}원");c.metric("현재 순위",f"{[r['player_id'] for r in rows].index(player['id'])+1}위")
    options={f"{name} · {market}":ticker for ticker,(name,market) in STOCKS.items()}
    ticker=options[st.selectbox("거래할 종목",options)];series=prices[ticker].iloc[:day+1];price=float(series.iloc[-1]);prev=float(series.iloc[-2]) if len(series)>1 else price
    st.subheader(STOCKS[ticker][0]);st.metric("오늘의 종가",f"{price:,.0f}원",f"{(price-prev)/prev*100:+.2f}%")
    frame=pd.DataFrame({"일차":range(1,len(series)+1),"종가":series.values});st.plotly_chart(px.line(frame,x="일차",y="종가",markers=True),use_container_width=True)
    if comp["status"]=="active":
        quantity=st.number_input("수량",min_value=1,value=1,step=1);buy,sell=st.columns(2)
        if buy.button("매수",type="primary",use_container_width=True):
            try:db().rpc("execute_trade",{"p_player_id":player["id"],"p_ticker":ticker,"p_side":"buy","p_quantity":quantity,"p_price":price,"p_day_index":day}).execute();st.rerun()
            except Exception as error:st.error(str(error))
        if sell.button("매도",use_container_width=True):
            try:db().rpc("execute_trade",{"p_player_id":player["id"],"p_ticker":ticker,"p_side":"sell","p_quantity":quantity,"p_price":price,"p_day_index":day}).execute();st.rerun()
            except Exception as error:st.error(str(error))
    st.subheader("실시간 순위");st.dataframe(pd.DataFrame([{"순위":i+1,"이름":r["이름"],"수익률":f"{r['수익률']:+.2f}%"} for i,r in enumerate(rows)]),hide_index=True,use_container_width=True)

try:
    if "role" not in st.session_state:login()
    elif st.session_state.role=="teacher":
        if st.session_state.page=="list":teacher_home()
        else:
            comp=one("competitions",id=st.session_state.competition_id);manage(comp,load_prices(str(comp["scenario_start"]),int(comp["duration"])))
    else:
        comp=one("competitions",id=st.session_state.competition_id);player=one("players",id=st.session_state.player_id)
        student(comp,player,load_prices(str(comp["scenario_start"]),int(comp["duration"])))
except KeyError:
    st.error("Streamlit Secrets에 Supabase 주소와 키를 입력하세요. README를 확인하세요.")
except Exception as error:
    st.error(f"오류가 발생했습니다: {error}")
