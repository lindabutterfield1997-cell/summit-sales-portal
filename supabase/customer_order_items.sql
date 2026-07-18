-- Customer order item ledger for product-level finance, inventory, and commission reporting.
-- Run this in Supabase SQL Editor before running backfill_customer_order_items.py.

create table if not exists public.customer_order_items (
  id bigserial primary key,
  order_id bigint not null references public.customer_orders(id) on delete cascade,
  customer_id bigint references public.customers(id) on delete set null,
  order_number text not null,
  line_index integer not null,
  line_id text,
  product_id text,
  product_name text not null,
  section text,
  category text,
  quantity integer not null default 1,
  width numeric default 0,
  height numeric default 0,
  area_sqft numeric default 0,
  direction text,
  glass text,
  frame text,
  color text,
  notes text,
  unit_price numeric default 0,
  original_unit_price numeric default 0,
  line_subtotal numeric default 0,
  order_discount_allocated numeric default 0,
  line_total_after_discount numeric default 0,
  price_adjusted boolean default false,
  price_adjustment_mode text,
  inventory_deducted boolean default false,
  inventory_deducted_quantity integer default 0,
  inventory_short_quantity integer default 0,
  production_required boolean default false,
  payload jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(order_id, line_index)
);

create index if not exists idx_customer_order_items_order_id
on public.customer_order_items(order_id);

create index if not exists idx_customer_order_items_customer_id
on public.customer_order_items(customer_id);

create index if not exists idx_customer_order_items_order_number
on public.customer_order_items(order_number);

create index if not exists idx_customer_order_items_product_id
on public.customer_order_items(product_id);

create index if not exists idx_customer_order_items_product_name
on public.customer_order_items(product_name);
