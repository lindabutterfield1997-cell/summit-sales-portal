-- Summit Sales Portal product catalog table
-- Run this first in Supabase SQL Editor.

create table if not exists public.products (
    id text primary key,
    section text not null,
    category text not null,
    name text not null,
    subtitle text default '',
    description text default '',
    base_rate numeric not null default 0,
    minimum_price numeric not null default 0,
    directions jsonb not null default '[]'::jsonb,
    glass_colors jsonb not null default '[]'::jsonb,
    frame_colors jsonb not null default '[]'::jsonb,
    accent text default '#1F3D33',
    hero_image text default '',
    detail_images jsonb not null default '[]'::jsonb,
    active boolean not null default true,
    updated_at timestamptz,
    color_options jsonb not null default '[]'::jsonb,
    color_information text default '',
    stock_information text default '',
    created_at timestamptz not null default now()
);

create index if not exists products_section_idx on public.products (section);
create index if not exists products_category_idx on public.products (category);
create index if not exists products_active_idx on public.products (active);

alter table public.products enable row level security;

-- The app uses your Supabase secret/service key, so RLS policies are optional for the app.
-- If you later want browser/public access, add stricter policies before using the publishable key.
