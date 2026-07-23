-- Add product color-to-image mappings and attach the Walnut image to WD-650.
-- Run this once in the Supabase SQL Editor after deploying the matching app code.

alter table public.products
add column if not exists color_images jsonb not null default '{}'::jsonb;

update public.products
set
    color_options = case
        when coalesce(color_options, '[]'::jsonb) @> '["Walnut"]'::jsonb
            then coalesce(color_options, '[]'::jsonb)
        else coalesce(color_options, '[]'::jsonb) || '["Walnut"]'::jsonb
    end,
    detail_images = case
        when coalesce(detail_images, '[]'::jsonb)
             @> '["uploads/wd-650-horizontal-wood-door-walnut-3x2.webp"]'::jsonb
            then coalesce(detail_images, '[]'::jsonb)
        else coalesce(detail_images, '[]'::jsonb)
             || '["uploads/wd-650-horizontal-wood-door-walnut-3x2.webp"]'::jsonb
    end,
    color_images = coalesce(color_images, '{}'::jsonb)
        || jsonb_build_object(
            'Walnut',
            'uploads/wd-650-horizontal-wood-door-walnut-3x2.webp'
        ),
    updated_at = now()
where id = 'WD-650';
