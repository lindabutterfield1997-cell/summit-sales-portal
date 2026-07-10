-- Customer order ledger for Summit Sales Portal
-- Run this once in Supabase SQL Editor.

create table if not exists public.customer_orders (
    id bigint generated always as identity primary key,
    customer_id bigint not null references public.customers(id) on delete cascade,
    order_number text not null unique,
    quote_number text,
    created_at timestamptz not null default now(),
    order_date date not null,
    salesperson text,

    subtotal numeric not null default 0,
    discount numeric not null default 0,
    tax numeric not null default 0,
    installation numeric not null default 0,
    shipping numeric not null default 0,
    total numeric not null default 0,

    first_payment_date date,
    first_payment_amount numeric not null default 0,
    first_payment_paid boolean not null default false,
    second_payment_enabled boolean not null default true,
    second_payment_date date,
    second_payment_amount numeric not null default 0,
    second_payment_paid boolean not null default false,

    payload jsonb not null default '{}'::jsonb
);

create index if not exists customer_orders_customer_id_idx on public.customer_orders(customer_id);
create index if not exists customer_orders_order_date_idx on public.customer_orders(order_date);
create index if not exists customer_orders_salesperson_idx on public.customer_orders(salesperson);

alter table public.customer_orders enable row level security;

-- The Streamlit app uses your server-side Supabase secret/service key, so RLS policies
-- are not required for the app. If you later switch to a publishable/anon key, add
-- restricted policies before exposing this table to users.
