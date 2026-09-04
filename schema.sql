create extension if not exists pgcrypto;
create table if not exists competitions (
 id uuid primary key default gen_random_uuid(), code text unique not null, title text not null,
 teacher_hash text not null, scenario_start date not null, starts_at timestamptz not null default now(),
 duration integer not null check(duration between 5 and 60), initial_cash numeric not null default 10000000,
 status text not null default 'active' check(status in ('active','ended')), created_at timestamptz not null default now());
create table if not exists players (
 id uuid primary key default gen_random_uuid(), competition_id uuid not null references competitions(id) on delete cascade,
 student_id text not null, name text not null, pin_hash text not null, cash numeric not null,
 created_at timestamptz not null default now(), unique(competition_id,student_id));
create table if not exists holdings (
 id bigint generated always as identity primary key, player_id uuid not null references players(id) on delete cascade,
 ticker text not null, quantity integer not null default 0 check(quantity>=0), unique(player_id,ticker));
create table if not exists trades (
 id bigint generated always as identity primary key, player_id uuid not null references players(id) on delete cascade,
 ticker text not null, side text not null check(side in('buy','sell')), quantity integer not null check(quantity>0),
 price numeric not null check(price>0), day_index integer not null, created_at timestamptz not null default now());
create index if not exists idx_players_competition on players(competition_id);
create index if not exists idx_holdings_player on holdings(player_id);
create index if not exists idx_trades_player on trades(player_id);

create or replace function execute_trade(p_player_id uuid,p_ticker text,p_side text,p_quantity integer,p_price numeric,p_day_index integer)
returns void language plpgsql security definer as $$
declare v_cash numeric; v_owned integer;
begin
 if p_quantity<1 or p_price<=0 then raise exception '잘못된 주문입니다.'; end if;
 select cash into v_cash from players where id=p_player_id for update;
 select coalesce(quantity,0) into v_owned from holdings where player_id=p_player_id and ticker=p_ticker;
 if p_side='buy' then
  if v_cash<p_quantity*p_price then raise exception '보유 현금이 부족합니다.'; end if;
  update players set cash=cash-p_quantity*p_price where id=p_player_id;
  insert into holdings(player_id,ticker,quantity) values(p_player_id,p_ticker,p_quantity)
   on conflict(player_id,ticker) do update set quantity=holdings.quantity+excluded.quantity;
 elsif p_side='sell' then
  if coalesce(v_owned,0)<p_quantity then raise exception '보유 수량이 부족합니다.'; end if;
  update players set cash=cash+p_quantity*p_price where id=p_player_id;
  update holdings set quantity=quantity-p_quantity where player_id=p_player_id and ticker=p_ticker;
 else raise exception '잘못된 거래 유형입니다.'; end if;
 insert into trades(player_id,ticker,side,quantity,price,day_index)
 values(p_player_id,p_ticker,p_side,p_quantity,p_price,p_day_index);
end $$;
alter table competitions enable row level security;
alter table players enable row level security;
alter table holdings enable row level security;
alter table trades enable row level security;
