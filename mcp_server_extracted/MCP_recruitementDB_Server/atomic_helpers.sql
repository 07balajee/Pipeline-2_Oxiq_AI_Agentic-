-- Optional but recommended. Deploy these two functions in Supabase
-- (SQL Editor -> New query -> Run), then set in .env:
--
--   USE_RPC_CASCADE=true
--   USE_RPC_APPEND=true
--
-- Without them the server still works: the cascade runs sequentially with
-- compensation, and append_json does a read-modify-write. With them, both
-- become single atomic statements.

-- ---------------------------------------------------------------------------
-- 1. Offer response cascade: offer_links -> offer_letters -> offers -> candidates
-- ---------------------------------------------------------------------------
create or replace function record_offer_response(
    p_token    text,
    p_decision text
)
returns jsonb
language plpgsql
security definer
as $$
declare
    v_link        record;
    v_letter      record;
    v_candidate   bigint;
    v_link_status text;
    v_cand_status text;
begin
    if p_decision not in ('accepted', 'declined') then
        raise exception 'decision must be accepted or declined, got %', p_decision;
    end if;

    v_link_status := case when p_decision = 'accepted' then 'Accepted' else 'Declined' end;
    v_cand_status := case when p_decision = 'accepted' then 'Hired'    else 'Declined' end;

    -- lock the link row for the duration of the transaction
    select * into v_link
    from offer_links
    where token = p_token
    for update;

    if not found then
        raise exception 'no offer link for token %', p_token;
    end if;

    if lower(coalesce(v_link.status, '')) not in ('pending', 'sent', '') then
        return jsonb_build_object(
            'noop', true,
            'message', format('offer link already resolved as %s', v_link.status)
        );
    end if;

    select * into v_letter
    from offer_letters
    where id = v_link.offer_letter_id
    for update;

    if not found then
        raise exception 'offer_letters row % is missing', v_link.offer_letter_id;
    end if;

    v_candidate := v_letter.candidate_id;

    update offer_links   set status = v_link_status where id = v_link.id;
    update offer_letters set status = v_link_status where id = v_letter.id;
    update offers        set status = v_link_status where candidate_id = v_candidate;
    update candidates    set status = v_cand_status where id = v_candidate;

    return jsonb_build_object(
        'noop', false,
        'decision', p_decision,
        'candidate_id', v_candidate,
        'applied', jsonb_build_array('offer_links', 'offer_letters', 'offers', 'candidates')
    );
end;
$$;

-- ---------------------------------------------------------------------------
-- 2. Atomic append to a JSONB array column
--    Used for requisitions.approval_chain, jobs_details.channels,
--    candidate_details.timeline / notes, campus_drives.candidates
-- ---------------------------------------------------------------------------
create or replace function append_json_array(
    p_table     text,
    p_column    text,
    p_pk_column text,
    p_pk_value  text,
    p_value     jsonb
)
returns jsonb
language plpgsql
security definer
as $$
declare
    v_allowed_tables text[] := array[
        'requisitions', 'jobs_details', 'candidate_details', 'campus_drives'
    ];
    v_result jsonb;
begin
    if not (p_table = any(v_allowed_tables)) then
        raise exception 'append_json_array not permitted on table %', p_table;
    end if;

    execute format(
        'update %I
            set %I = coalesce(%I, ''[]''::jsonb) || $1
          where %I::text = $2
      returning %I',
        p_table, p_column, p_column, p_pk_column, p_column
    )
    into v_result
    using p_value, p_pk_value;

    if v_result is null then
        raise exception 'no row in % where % = %', p_table, p_pk_column, p_pk_value;
    end if;

    return jsonb_build_object('column', p_column, 'length', jsonb_array_length(v_result));
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. Column introspection, used by validate_registry.py
--    Without this, empty tables cannot be verified against registry.yaml and
--    are reported as "unverified" rather than quietly passing.
-- ---------------------------------------------------------------------------
create or replace function table_columns(p_table text)
returns table (column_name text, data_type text, is_nullable text)
language sql
stable
security definer
as $$
    select c.column_name::text, c.data_type::text, c.is_nullable::text
      from information_schema.columns c
     where c.table_schema = 'public'
       and c.table_name = p_table
     order by c.ordinal_position;
$$;
