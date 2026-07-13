-- dotx RPC API (run after schema.sql in Supabase SQL Editor)

create table if not exists public.app_settings (
  key text primary key,
  value text not null
);

insert into public.app_settings (key, value) values
  ('site_api_token', 'CghI7o7bKeoevRU074_kPm08OrDq6EqcQVsCGX3xBnQ'),
  ('owner_discord_ids', '1284140942764539985')
on conflict (key) do update set value = excluded.value;

create or replace function public._site_token_ok(p_site_token text) returns boolean
language sql stable as $$
  select coalesce(p_site_token, '') = (select value from public.app_settings where key = 'site_api_token' limit 1);
$$;

create or replace function public._is_owner_id(p_discord_id text) returns boolean
language sql stable as $$
  select p_discord_id = any(
    string_to_array(coalesce((select value from public.app_settings where key = 'owner_discord_ids' limit 1), ''), ',')
  );
$$;

create or replace function public._customer_allowed(p_discord_id text) returns boolean
language sql stable as $$
  select
    public._is_owner_id(p_discord_id)
    or exists (
      select 1 from public.site_users u
      where u.discord_id = p_discord_id
        and (
          u.panel_role in ('owner', 'admin', 'staff')
          or (u.license_expires_at is not null and u.license_expires_at > now())
          or u.licensed_status = 'Customer'
        )
    );
$$;

create or replace function public.api_health() returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object('ok', true, 'service', 'dotx-api', 'database', 'supabase');
$$;

create or replace function public.get_license_rpc(p_discord_id text) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  u public.site_users%rowtype;
  active boolean := false;
begin
  select * into u from public.site_users where discord_id = p_discord_id;
  if public._is_owner_id(p_discord_id) then
    return jsonb_build_object(
      'status', 'Customer', 'licenseActive', true, 'panelRole', 'owner',
      'isOwner', true, 'isAdmin', true, 'isStaff', true, 'method', 'config_owner'
    );
  end if;
  if not found then
    return jsonb_build_object('status', 'Standard', 'licenseActive', false, 'panelRole', 'member');
  end if;
  active := u.license_expires_at is not null and u.license_expires_at > now();
  if u.panel_role in ('owner', 'admin', 'staff') then
    return jsonb_build_object(
      'status', 'Customer', 'licenseActive', true, 'panelRole', u.panel_role,
      'isOwner', u.panel_role = 'owner', 'isAdmin', u.panel_role in ('owner', 'admin'),
      'isStaff', u.panel_role in ('owner', 'admin', 'staff'),
      'licenseExpiresAt', u.license_expires_at, 'licenseGrantedAt', u.license_granted_at,
      'method', 'panel_role'
    );
  end if;
  if active then
    return jsonb_build_object(
      'status', 'Customer', 'licenseActive', true, 'panelRole', coalesce(u.panel_role, 'member'),
      'licenseExpiresAt', u.license_expires_at, 'licenseGrantedAt', u.license_granted_at,
      'licenseSource', 'site_key', 'method', 'site_key'
    );
  end if;
  return jsonb_build_object('status', 'Standard', 'licenseActive', false, 'panelRole', coalesce(u.panel_role, 'member'));
end;
$$;

create or replace function public.register_user_rpc(
  p_site_token text, p_discord_id text, p_username text default 'Unknown',
  p_avatar_hash text default '', p_licensed_status text default 'Standard'
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  u public.site_users%rowtype;
  now_ts timestamptz := now();
  token text;
begin
  if not public._site_token_ok(p_site_token) then
    raise exception 'invalid_site_token';
  end if;
  select * into u from public.site_users where discord_id = p_discord_id;
  if found then
    token := u.user_token;
    update public.site_users set
      username = coalesce(nullif(p_username, ''), username),
      avatar_hash = coalesce(nullif(p_avatar_hash, ''), avatar_hash),
      licensed_status = case when license_expires_at > now() then 'Customer' else p_licensed_status end,
      last_seen = now_ts,
      login_count = login_count + 1
    where discord_id = p_discord_id
    returning * into u;
  else
    token := 'DX-' || upper(substr(md5(random()::text), 1, 4)) || '-' || upper(substr(md5(random()::text), 1, 4));
    insert into public.site_users (
      discord_id, username, avatar_hash, user_token, panel_role, licensed_status,
      first_seen, joined_at, last_seen, login_count
    ) values (
      p_discord_id, coalesce(nullif(p_username, ''), 'Unknown'), coalesce(p_avatar_hash, ''),
      token, case when public._is_owner_id(p_discord_id) then 'owner' else 'member' end,
      p_licensed_status, now_ts, now_ts, now_ts, 1
    ) returning * into u;
  end if;
  return jsonb_build_object(
    'ok', true,
    'user', jsonb_build_object(
      'discordId', u.discord_id, 'username', u.username, 'avatarHash', u.avatar_hash,
      'userToken', u.user_token, 'panelRole', u.panel_role, 'licensedStatus', u.licensed_status,
      'firstSeen', u.first_seen, 'joinedAt', u.joined_at, 'lastSeen', u.last_seen,
      'loginCount', u.login_count, 'licenseExpiresAt', u.license_expires_at
    )
  );
end;
$$;

create or replace function public.register_pin_rpc(
  p_site_token text, p_discord_id text, p_pin text,
  p_player_name text default '—', p_game text default 'FiveM',
  p_id text default null, p_date timestamptz default null
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  row public.pins%rowtype;
  now_ts timestamptz := coalesce(p_date, now());
begin
  if not public._site_token_ok(p_site_token) then raise exception 'invalid_site_token'; end if;
  if not public._customer_allowed(p_discord_id) then raise exception 'license_required'; end if;
  insert into public.pins (id, pin, discord_id, player_name, game, status, result, date, scan_id)
  values (
    coalesce(p_id, 'pin_' || (extract(epoch from now()) * 1000)::bigint::text),
    p_pin, p_discord_id, coalesce(nullif(p_player_name, ''), '—'), coalesce(nullif(p_game, ''), 'FiveM'),
    'pending', 'Pending', now_ts, null
  )
  on conflict (pin) do update set
    discord_id = excluded.discord_id,
    player_name = excluded.player_name,
    game = excluded.game,
    date = excluded.date
  returning * into row;
  return jsonb_build_object('ok', true, 'pin', jsonb_build_object(
    'id', row.id, 'pin', row.pin, 'discordId', row.discord_id, 'playerName', row.player_name,
    'game', row.game, 'status', row.status, 'result', row.result, 'date', row.date, 'scanId', row.scan_id
  ));
end;
$$;

create or replace function public.list_pins_rpc(p_site_token text, p_discord_id text) returns jsonb
language plpgsql stable security definer set search_path = public as $$
begin
  if not public._site_token_ok(p_site_token) then raise exception 'invalid_site_token'; end if;
  if not public._customer_allowed(p_discord_id) then raise exception 'license_required'; end if;
  return jsonb_build_object('pins', coalesce((
    select jsonb_agg(jsonb_build_object(
      'id', id, 'pin', pin, 'discordId', discord_id, 'playerName', player_name, 'game', game,
      'status', status, 'result', result, 'date', date, 'scanId', scan_id
    ) order by date desc)
    from public.pins where discord_id = p_discord_id
  ), '[]'::jsonb));
end;
$$;

create or replace function public.delete_pin_rpc(p_site_token text, p_discord_id text, p_pin_id text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare deleted int;
begin
  if not public._site_token_ok(p_site_token) then raise exception 'invalid_site_token'; end if;
  if not public._customer_allowed(p_discord_id) then raise exception 'license_required'; end if;
  delete from public.pins where id = p_pin_id and discord_id = p_discord_id;
  get diagnostics deleted = row_count;
  if deleted = 0 then raise exception 'not_found'; end if;
  return jsonb_build_object('ok', true);
end;
$$;

create or replace function public.verify_pin_rpc(p_pin text) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare row public.pins%rowtype;
begin
  select * into row from public.pins where pin = p_pin;
  if not found then raise exception 'invalid_pin'; end if;
  return jsonb_build_object('ok', true, 'pin', p_pin, 'game', row.game);
end;
$$;

create or replace function public.list_scans_rpc(p_site_token text, p_discord_id text) returns jsonb
language plpgsql stable security definer set search_path = public as $$
begin
  if not public._site_token_ok(p_site_token) then raise exception 'invalid_site_token'; end if;
  if not public._customer_allowed(p_discord_id) then raise exception 'license_required'; end if;
  return jsonb_build_object('scans', coalesce((
    select jsonb_agg(jsonb_build_object(
      'id', id, 'discordId', discord_id, 'pinId', pin_id, 'pin', pin, 'date', date,
      'playerName', player_name, 'verdict', verdict, 'threats', threats, 'warnings', warnings,
      'summary', summary, 'reportText', report_text, 'hostname', hostname, 'username', username
    ) order by date desc)
    from public.scans where discord_id = p_discord_id
  ), '[]'::jsonb));
end;
$$;

create or replace function public.submit_scan_rpc(
  p_pin text, p_verdict text default '', p_player_name text default null,
  p_threats int default 0, p_warnings int default 0, p_summary text default '',
  p_report_text text default '', p_hostname text default '', p_username text default '',
  p_id text default null, p_date timestamptz default null
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  pin_row public.pins%rowtype;
  scan_id text := coalesce(p_id, 'scan_' || (extract(epoch from now()) * 1000)::bigint::text);
  now_ts timestamptz := coalesce(p_date, now());
  verdict text; result_label text; pin_status text; v text := upper(coalesce(p_verdict, ''));
begin
  select * into pin_row from public.pins where pin = p_pin;
  if not found then raise exception 'invalid_pin'; end if;
  if v = 'CLEAN' then verdict := 'passed'; result_label := 'Clean'; pin_status := 'finished';
  elsif v = 'REVIEW NEEDED' then verdict := 'review'; result_label := 'Review'; pin_status := 'finished';
  elsif v = 'SUSPICIOUS' then verdict := 'suspicious'; result_label := 'Suspicious'; pin_status := 'cheated';
  elsif v = 'CHEATING LIKELY' then verdict := 'failed'; result_label := 'Cheated'; pin_status := 'cheated';
  else verdict := 'review'; result_label := 'Review'; pin_status := 'finished';
  end if;
  insert into public.scans (
    id, discord_id, pin_id, pin, date, player_name, verdict, threats, warnings,
    summary, report_text, hostname, username
  ) values (
    scan_id, pin_row.discord_id, pin_row.id, p_pin, now_ts,
    coalesce(nullif(p_player_name, ''), pin_row.player_name, '—'),
    verdict, coalesce(p_threats, 0), coalesce(p_warnings, 0),
    coalesce(p_summary, ''), coalesce(p_report_text, ''), coalesce(p_hostname, ''), coalesce(p_username, '')
  );
  update public.pins set status = pin_status, result = result_label, scan_id = scan_id where pin = p_pin;
  return jsonb_build_object('ok', true, 'scan', jsonb_build_object(
    'id', scan_id, 'discordId', pin_row.discord_id, 'pinId', pin_row.id, 'pin', p_pin,
    'date', now_ts, 'playerName', coalesce(nullif(p_player_name, ''), pin_row.player_name),
    'verdict', verdict, 'threats', coalesce(p_threats, 0), 'warnings', coalesce(p_warnings, 0),
    'summary', coalesce(p_summary, ''), 'reportText', coalesce(p_report_text, '')
  ));
end;
$$;

grant usage on schema public to anon, authenticated;
grant execute on function public.api_health() to anon, authenticated;
grant execute on function public.get_license_rpc(text) to anon, authenticated;
grant execute on function public.register_user_rpc(text, text, text, text, text) to anon, authenticated;
grant execute on function public.register_pin_rpc(text, text, text, text, text, text, timestamptz) to anon, authenticated;
grant execute on function public.list_pins_rpc(text, text) to anon, authenticated;
grant execute on function public.delete_pin_rpc(text, text, text) to anon, authenticated;
grant execute on function public.verify_pin_rpc(text) to anon, authenticated;
grant execute on function public.list_scans_rpc(text, text) to anon, authenticated;
grant execute on function public.submit_scan_rpc(text, text, text, int, int, text, text, text, text, text, timestamptz) to anon, authenticated;
