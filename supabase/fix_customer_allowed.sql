-- Fix: expired licenses must not keep Pins/Reports access.
-- Run in Supabase SQL Editor (Dashboard → SQL → New query).

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
        )
    );
$$;
