-- Add customer location fields used by the Streamlit CRM.
-- Run this once in Supabase SQL Editor before saving customers with zip codes.

alter table public.customers
  add column if not exists zip_code text,
  add column if not exists city text,
  add column if not exists state text;

-- Optional cleanup: if older rows only used area_zip, copy it into zip_code.
update public.customers
set zip_code = area_zip
where (zip_code is null or zip_code = '')
  and area_zip is not null
  and area_zip <> '';
