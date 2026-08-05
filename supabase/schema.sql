-- dotx store schema for Supabase (project: bumuisxrzbteeymzeidh)
-- Run in Supabase Dashboard → SQL Editor → New query

create table if not exists public.site_users (
  discord_id text primary key,
  username text not null default 'Unknown',
  avatar_hash text not null default '',
  user_token text not null unique,
  panel_role text not null default 'member',
  licensed_status text not null default 'Standard',
  first_seen timestamptz,
  joined_at timestamptz,
  last_seen timestamptz,
  login_count integer not null default 0,
  license_expires_at timestamptz,
  license_key_id text,
  license_granted_at timestamptz,
  license_revoked_at timestamptz,
  license_revoked_by text,
  promoted_at timestamptz,
  tool_branding jsonb
);

create table if not exists public.pins (
  id text primary key,
  pin text not null unique,
  discord_id text not null,
  player_name text not null default '—',
  game text not null default 'FiveM',
  status text not null default 'pending',
  result text not null default 'Pending',
  date timestamptz,
  scan_id text
);

create table if not exists public.scans (
  id text primary key,
  discord_id text not null,
  pin_id text,
  pin text not null,
  date timestamptz,
  player_name text not null default '—',
  verdict text not null default 'review',
  threats integer not null default 0,
  warnings integer not null default 0,
  summary text not null default '',
  report_text text not null default '',
  hostname text not null default '',
  username text not null default ''
);

create table if not exists public.license_keys (
  id text primary key,
  code_hash text not null unique,
  created_by text not null,
  created_at timestamptz not null,
  duration_seconds integer not null,
  duration_label text not null,
  status text not null default 'active',
  redeemed_by text,
  redeemed_at timestamptz,
  license_expires_at timestamptz,
  ticket_channel_id text,
  ticket_ref text,
  redeemed_by_staff text,
  revoked_at timestamptz,
  revoked_by text
);

create index if not exists idx_pins_discord_id on public.pins (discord_id);
create index if not exists idx_pins_pin on public.pins (pin);
create index if not exists idx_scans_discord_id on public.scans (discord_id);
create index if not exists idx_license_keys_code_hash on public.license_keys (code_hash);
create index if not exists idx_license_keys_status on public.license_keys (status);

alter table public.site_users enable row level security;
alter table public.pins enable row level security;
alter table public.scans enable row level security;
alter table public.license_keys enable row level security;
