-- PC Check EXE branding (Account → custom image/GIF + Discord avatar toggle)
-- Run in Supabase SQL Editor after deploying site changes.

alter table public.site_users
  add column if not exists tool_branding jsonb;

create or replace function public.save_tool_branding_rpc(
  p_site_token text,
  p_discord_id text,
  p_branding jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  u public.site_users%rowtype;
  clean jsonb;
begin
  if not public._site_token_ok(p_site_token) then
    raise exception 'invalid_site_token';
  end if;
  if coalesce(nullif(trim(p_discord_id), ''), '') = '' then
    raise exception 'discord_id_required';
  end if;

  select * into u from public.site_users where discord_id = p_discord_id;
  if not found then
    raise exception 'user_not_found';
  end if;

  -- Only licensed customers (or owners) may save branding
  if not public._customer_allowed(p_discord_id) and not public._is_owner_id(p_discord_id) then
    raise exception 'license_required';
  end if;

  clean := jsonb_build_object(
    'showDiscordAvatar', coalesce((p_branding->>'showDiscordAvatar')::boolean, true),
    'username', left(coalesce(p_branding->>'username', u.username, ''), 64),
    'discordId', p_discord_id,
    'avatarUrl', left(coalesce(p_branding->>'avatarUrl', ''), 500),
    'customImage', case
      when jsonb_typeof(p_branding->'customImage') = 'string'
           and length(p_branding->>'customImage') between 1 and 320000
        then to_jsonb(p_branding->>'customImage')
      else null
    end
  );

  update public.site_users
  set tool_branding = clean
  where discord_id = p_discord_id
  returning * into u;

  return jsonb_build_object('ok', true, 'branding', coalesce(u.tool_branding, '{}'::jsonb));
end;
$$;

create or replace function public.verify_pin_rpc(p_pin text) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  row public.pins%rowtype;
  u public.site_users%rowtype;
  branding jsonb := null;
  avatar_url text;
begin
  select * into row from public.pins where pin = p_pin;
  if not found then raise exception 'invalid_pin'; end if;

  select * into u from public.site_users where discord_id = row.discord_id;
  if found and u.tool_branding is not null and u.tool_branding <> '{}'::jsonb then
    branding := u.tool_branding;
  elsif found then
    if coalesce(u.avatar_hash, '') <> '' then
      avatar_url := 'https://cdn.discordapp.com/avatars/' || u.discord_id || '/' || u.avatar_hash || '.png?size=128';
    else
      avatar_url := 'https://cdn.discordapp.com/embed/avatars/' || ((u.discord_id::bigint >> 22) % 6) || '.png';
    end if;
    branding := jsonb_build_object(
      'showDiscordAvatar', true,
      'username', coalesce(u.username, ''),
      'discordId', u.discord_id,
      'avatarUrl', avatar_url,
      'customImage', null
    );
  end if;

  return jsonb_build_object(
    'ok', true,
    'pin', p_pin,
    'game', row.game,
    'branding', branding
  );
end;
$$;

grant execute on function public.save_tool_branding_rpc(text, text, jsonb) to anon, authenticated;
grant execute on function public.verify_pin_rpc(text) to anon, authenticated;
