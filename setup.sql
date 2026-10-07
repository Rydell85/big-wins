-- Run once in Supabase: SQL Editor > New query > paste > Run.
-- Creates the table the mock generator writes to and the live page reads from,
-- and switches on Realtime for it so new rows are pushed to open pages.

create table if not exists public.big_wins (
    id          bigint generated always as identity primary key,
    created_at  timestamptz not null default now(),
    game        text not null,
    brand       text not null,
    country     text not null,
    player      text not null,          -- masked, e.g. "ka***81"
    bet_eur     numeric(12,2) not null,
    multiplier  numeric(10,2) not null,
    win_eur     numeric(14,2) not null
);

create index if not exists big_wins_created_at on public.big_wins (created_at desc);

-- New projects do not grant table access to the API roles automatically.
-- MOCK DATA ONLY: anon may insert so the generator can run on the publishable
-- key. With real data, inserts must come from a server with the secret key and
-- this insert grant and policy must go.
grant select, insert on public.big_wins to anon;

alter table public.big_wins enable row level security;

drop policy if exists "big_wins read" on public.big_wins;
create policy "big_wins read" on public.big_wins
    for select to anon using (true);

drop policy if exists "big_wins mock insert" on public.big_wins;
create policy "big_wins mock insert" on public.big_wins
    for insert to anon with check (true);

-- Realtime: push every new row to subscribed pages.
do $$
begin
    if not exists (select 1 from pg_publication_tables
                   where pubname = 'supabase_realtime' and tablename = 'big_wins') then
        alter publication supabase_realtime add table public.big_wins;
    end if;
end $$;
