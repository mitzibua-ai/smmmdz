-- FIX: submit_scan_rpc (ambiguous scan_id broke PC Check uploads)
-- Run this in Supabase SQL Editor, then rebuild is not required for this SQL part.

create or replace function public.submit_scan_rpc(
  p_pin text, p_verdict text default '', p_player_name text default null,
  p_threats int default 0, p_warnings int default 0, p_summary text default '',
  p_report_text text default '', p_hostname text default '', p_username text default '',
  p_id text default null, p_date timestamptz default null
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  pin_row public.pins%rowtype;
  v_scan_id text := coalesce(p_id, 'scan_' || (extract(epoch from now()) * 1000)::bigint::text);
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
    v_scan_id, pin_row.discord_id, pin_row.id, p_pin, now_ts,
    coalesce(nullif(p_player_name, ''), pin_row.player_name, '—'),
    verdict, coalesce(p_threats, 0), coalesce(p_warnings, 0),
    coalesce(p_summary, ''), coalesce(p_report_text, ''), coalesce(p_hostname, ''), coalesce(p_username, '')
  );
  update public.pins
  set status = pin_status, result = result_label, scan_id = v_scan_id
  where public.pins.pin = p_pin;
  return jsonb_build_object('ok', true, 'scan', jsonb_build_object(
    'id', v_scan_id, 'discordId', pin_row.discord_id, 'pinId', pin_row.id, 'pin', p_pin,
    'date', now_ts, 'playerName', coalesce(nullif(p_player_name, ''), pin_row.player_name),
    'verdict', verdict, 'threats', coalesce(p_threats, 0), 'warnings', coalesce(p_warnings, 0),
    'summary', coalesce(p_summary, ''), 'reportText', coalesce(p_report_text, '')
  ));
end;
$$;

grant execute on function public.submit_scan_rpc(text, text, text, int, int, text, text, text, text, text, timestamptz) to anon, authenticated;
