-- Preserve Customer / lifetime licenses on login register.
-- Run in Supabase SQL Editor after deploy.

create or replace function public.register_user_rpc(
  p_site_token text,
  p_discord_id text,
  p_username text default 'Unknown',
  p_avatar_hash text default '',
  p_licensed_status text default 'Standard'
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  u public.site_users%rowtype;
  now_ts timestamptz := now();
  token text;
  keep_customer boolean := false;
  next_status text;
begin
  if not public._site_token_ok(p_site_token) then
    raise exception 'invalid_site_token';
  end if;

  select * into u from public.site_users where discord_id = p_discord_id;
  if found then
    token := u.user_token;
    keep_customer :=
      (u.license_expires_at is not null and u.license_expires_at > now_ts)
      or (
        lower(coalesce(u.licensed_status, '')) = 'customer'
        and u.license_key_id is not null
        and u.license_expires_at is null
      );

    next_status := case
      when keep_customer then 'Customer'
      else coalesce(nullif(p_licensed_status, ''), 'Standard')
    end;

    update public.site_users set
      username = coalesce(nullif(p_username, ''), username),
      avatar_hash = coalesce(nullif(p_avatar_hash, ''), avatar_hash),
      licensed_status = next_status,
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
      coalesce(nullif(p_licensed_status, ''), 'Standard'), now_ts, now_ts, now_ts, 1
    ) returning * into u;
  end if;

  return jsonb_build_object(
    'ok', true,
    'user', jsonb_build_object(
      'discordId', u.discord_id, 'username', u.username, 'avatarHash', u.avatar_hash,
      'userToken', u.user_token, 'panelRole', u.panel_role, 'licensedStatus', u.licensed_status,
      'firstSeen', u.first_seen, 'joinedAt', u.joined_at, 'lastSeen', u.last_seen,
      'loginCount', u.login_count, 'licenseExpiresAt', u.license_expires_at,
      'licenseKeyId', u.license_key_id, 'licenseGrantedAt', u.license_granted_at
    )
  );
end;
$$;

grant execute on function public.register_user_rpc(text, text, text, text, text) to anon, authenticated;
