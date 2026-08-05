-- Lifetime + timed license access rules.
-- Run in Supabase SQL Editor.

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
          or (
            u.licensed_status = 'Customer'
            and u.license_key_id is not null
            and u.license_expires_at is null
          )
        )
    );
$$;

create or replace function public.get_license_rpc(p_discord_id text) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  u public.site_users%rowtype;
  active boolean := false;
  lifetime boolean := false;
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
  lifetime := u.licensed_status = 'Customer'
    and u.license_key_id is not null
    and u.license_expires_at is null;
  active := (u.license_expires_at is not null and u.license_expires_at > now()) or lifetime;
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
      'licenseSource', 'site_key', 'method', 'site_key', 'lifetime', lifetime
    );
  end if;
  return jsonb_build_object('status', 'Standard', 'licenseActive', false, 'panelRole', coalesce(u.panel_role, 'member'));
end;
$$;
