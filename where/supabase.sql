-- «Где группа» (umra.jurt.kz/where/) — база для живого режима в Supabase. Версия 2 (26.10.2026).
-- Запустить один раз: Supabase → SQL Editor → вставить весь файл → Run (повторный запуск безопасен).
--
-- Что здесь хранится: ТОЛЬКО группы (код + отпечаток ключа руководителя), точки сбора и объявления.
-- Местоположение людей в базу не пишется вообще: оно идёт через Realtime Presence
-- (в памяти сервера) и исчезает, когда человек закрывает страницу.
--
-- Защита: к таблицам у публичного ключа доступа НЕТ совсем (ни чтения, ни записи).
-- Всё — только через функции ниже: каждая требует код группы, а действия руководителя —
-- ещё и ключ руководителя (в базе лежит только его отпечаток sha256, сам ключ — у руководителя).

create extension if not exists pgcrypto with schema extensions;

-- Группы: код вида UMRA-0009-K7Q2XZ (случайный хвост — не угадать), отпечаток ключа руководителя
create table if not exists public.where_groups (
  grp         text primary key check (grp ~ '^[A-Z0-9]+(-[A-Z0-9]+)*$' and char_length(grp) between 8 and 40),
  lead_hash   text not null,
  created_at  timestamptz not null default now(),
  expires_at  timestamptz not null default now() + interval '45 days'
);

create table if not exists public.where_points (
  id          text primary key,
  grp         text not null check (char_length(grp) between 4 and 40),
  name        text not null check (char_length(name) <= 60),
  lat         double precision not null check (lat between 21.0 and 25.0),   -- только Мекка и Медина
  lon         double precision not null check (lon between 39.0 and 40.5),
  meet_at     text check (meet_at ~ '^\d{1,2}:\d{2}$'),
  by_id       text,
  created_at  timestamptz not null default now(),
  expires_at  timestamptz not null default now() + interval '21 days'    -- точка живёт не дольше поездки
);
create index if not exists where_points_grp on public.where_points (grp);

-- Объявления руководителя («Сбор у ворот 79 после иша», «Автобус в 15:00»).
create table if not exists public.where_notes (
  id          text primary key,
  grp         text not null check (char_length(grp) between 4 and 40),
  body        text not null check (char_length(body) between 1 and 280),
  by_name     text check (char_length(by_name) <= 40),
  created_at  timestamptz not null default now(),
  expires_at  timestamptz not null default now() + interval '21 days'
);
create index if not exists where_notes_grp on public.where_notes (grp, created_at desc);

-- Закрыть прямой доступ: RLS включён, политик нет, прав нет
alter table public.where_groups enable row level security;
alter table public.where_points enable row level security;
alter table public.where_notes  enable row level security;
drop policy if exists "where read"   on public.where_points;
drop policy if exists "where write"  on public.where_points;
drop policy if exists "where update" on public.where_points;
drop policy if exists "where delete" on public.where_points;
drop policy if exists "notes read"   on public.where_notes;
drop policy if exists "notes write"  on public.where_notes;
drop policy if exists "notes delete" on public.where_notes;
revoke all on public.where_groups, public.where_points, public.where_notes from anon, authenticated;

-- Таблицы больше не транслируются через Realtime: об изменениях участники узнают по сигналу группы
do $$ begin alter publication supabase_realtime drop table public.where_points; exception when others then null; end $$;
do $$ begin alter publication supabase_realtime drop table public.where_notes;  exception when others then null; end $$;

-- ---------- Внутренние проверки ----------
create or replace function public.where_hash(p_grp text, p_key text) returns text
language sql immutable set search_path = '' as
$$ select encode(extensions.digest(p_grp || ':' || coalesce(p_key, ''), 'sha256'), 'hex') $$;
revoke all on function public.where_hash(text, text) from public, anon, authenticated;

-- 0 — группы нет (или срок вышел), 1 — участник, 2 — руководитель
create or replace function public.where_role(p_grp text, p_key text) returns int
language sql stable security definer set search_path = '' as $$
  select coalesce((select case when p_key is not null and char_length(p_key) >= 12 and g.lead_hash = public.where_hash(p_grp, p_key) then 2 else 1 end
                   from public.where_groups g where g.grp = p_grp and g.expires_at > now()), 0)
$$;
revoke all on function public.where_role(text, text) from public, anon, authenticated;

-- ---------- Вход в группу / создание новой ----------
-- p_create = true: создать группу с этим ключом руководителя (если кода ещё нет).
-- Ответ: {"ok": есть ли группа, "lead": руководитель ли, "created": создана ли сейчас}
create or replace function public.where_join(p_grp text, p_key text default null, p_create boolean default false) returns json
language plpgsql security definer set search_path = '' as $$
declare r int; made boolean := false;
begin
  r := public.where_role(p_grp, p_key);
  if r = 0 and p_create then
    if p_grp !~ '^[A-Z0-9]+(-[A-Z0-9]+)*-[A-Z0-9]{6,}$' or char_length(p_grp) not between 8 and 40 then raise exception 'bad code'; end if;
    if p_key is null or char_length(p_key) < 12 or char_length(p_key) > 64 then raise exception 'bad key'; end if;
    if (select count(*) from public.where_groups where created_at > now() - interval '1 hour') >= 30 then raise exception 'too many new groups, try later'; end if;
    insert into public.where_groups (grp, lead_hash) values (p_grp, public.where_hash(p_grp, p_key)) on conflict (grp) do nothing;
    made := found;
    r := public.where_role(p_grp, p_key);
  end if;
  return json_build_object('ok', r > 0, 'lead', r = 2, 'created', made);
end $$;

-- ---------- Чтение ----------
create or replace function public.where_list(p_grp text) returns table (id text, name text, lat double precision, lon double precision, meet_at text, by_id text)
language sql stable security definer set search_path = '' as $$
  select p.id, p.name, p.lat, p.lon, p.meet_at, p.by_id from public.where_points p
  where p.grp = p_grp and p.expires_at > now() and public.where_role(p_grp, null) > 0
$$;
create or replace function public.where_notes_list(p_grp text) returns table (id text, body text, by_name text, created_at timestamptz)
language sql stable security definer set search_path = '' as $$
  select n.id, n.body, n.by_name, n.created_at from public.where_notes n
  where n.grp = p_grp and n.expires_at > now() and public.where_role(p_grp, null) > 0
  order by n.created_at desc limit 20
$$;

-- ---------- Точки: ставит любой участник, правит/удаляет своё; место сбора и чужие точки — руководитель ----------
create or replace function public.where_put_point(p_grp text, p_key text, p_id text, p_name text, p_lat double precision, p_lon double precision, p_meet text, p_by text) returns void
language plpgsql security definer set search_path = '' as $$
declare r int := public.where_role(p_grp, p_key); old public.where_points; ex boolean;
begin
  if r = 0 then raise exception 'no group'; end if;
  if p_id is null or p_id !~ '^[A-Za-z0-9-]{3,60}$' then raise exception 'bad id'; end if;
  select * into old from public.where_points where id = p_id;
  ex := found;
  if ex and old.grp <> p_grp then raise exception 'bad id'; end if;
  if ex and r < 2 and old.by_id is distinct from p_by then raise exception 'not yours'; end if;
  if r < 2 then p_meet := case when ex then old.meet_at else null end; end if;   -- время сбора назначает только руководитель
  if not ex and (select count(*) from public.where_points where grp = p_grp) >= 40 then raise exception 'too many points'; end if;
  if p_meet is not null then update public.where_points set meet_at = null where grp = p_grp and id <> p_id and meet_at is not null; end if;
  insert into public.where_points (id, grp, name, lat, lon, meet_at, by_id)
  values (p_id, p_grp, left(coalesce(p_name, ''), 60), p_lat, p_lon, p_meet, left(p_by, 40))
  on conflict (id) do update set name = excluded.name, lat = excluded.lat, lon = excluded.lon, meet_at = excluded.meet_at;
end $$;

create or replace function public.where_del_point(p_grp text, p_key text, p_id text, p_by text) returns void
language plpgsql security definer set search_path = '' as $$
declare r int := public.where_role(p_grp, p_key);
begin
  if r = 0 then raise exception 'no group'; end if;
  delete from public.where_points where id = p_id and grp = p_grp and (r = 2 or by_id = p_by);
end $$;

-- ---------- Объявления и очистка — только руководитель ----------
create or replace function public.where_put_note(p_grp text, p_key text, p_id text, p_body text, p_by text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if public.where_role(p_grp, p_key) < 2 then raise exception 'leader only'; end if;
  if (select count(*) from public.where_notes where grp = p_grp) >= 60 then raise exception 'too many notes'; end if;
  insert into public.where_notes (id, grp, body, by_name) values (p_id, p_grp, left(p_body, 280), left(p_by, 40));
end $$;

create or replace function public.where_del_note(p_grp text, p_key text, p_id text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if public.where_role(p_grp, p_key) < 2 then raise exception 'leader only'; end if;
  delete from public.where_notes where id = p_id and grp = p_grp;
end $$;

create or replace function public.where_clear(p_grp text, p_key text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if public.where_role(p_grp, p_key) < 2 then raise exception 'leader only'; end if;
  delete from public.where_points where grp = p_grp;
  delete from public.where_notes  where grp = p_grp;
end $$;

revoke all on function public.where_join(text, text, boolean), public.where_list(text), public.where_notes_list(text),
  public.where_put_point(text, text, text, text, double precision, double precision, text, text), public.where_del_point(text, text, text, text),
  public.where_put_note(text, text, text, text, text), public.where_del_note(text, text, text), public.where_clear(text, text) from public;
grant execute on function public.where_join(text, text, boolean), public.where_list(text), public.where_notes_list(text),
  public.where_put_point(text, text, text, text, double precision, double precision, text, text), public.where_del_point(text, text, text, text),
  public.where_put_note(text, text, text, text, text), public.where_del_note(text, text, text), public.where_clear(text, text) to anon, authenticated;

-- Автоудаление: каждый час стирать просроченное
-- (Если расширение pg_cron не включено: Database → Extensions → pg_cron → Enable.)
create extension if not exists pg_cron;
select cron.unschedule('where-cleanup') where exists (select 1 from cron.job where jobname = 'where-cleanup');
select cron.schedule('where-cleanup', '0 * * * *', $$ delete from public.where_points where expires_at < now(); delete from public.where_notes where expires_at < now(); delete from public.where_groups where expires_at < now() $$);
