-- Run once in Supabase SQL Editor. Uses a PUBLIC bucket: review photos are public.
-- Does not modify or remove an existing bucket or any existing policies.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('review-photos', 'review-photos', true, 512000, array['image/jpeg','image/png'])
on conflict (id) do nothing;

-- Run these CREATE POLICY statements only once.
create policy "pump_check_upload_own_review_photos"
on storage.objects for insert to authenticated
with check (bucket_id = 'review-photos'
  and (storage.foldername(name))[1] = 'reviews'
  and (storage.foldername(name))[2] = (select auth.uid())::text);

create policy "pump_check_read_own_review_photo_info"
on storage.objects for select to authenticated
using (bucket_id = 'review-photos'
  and (storage.foldername(name))[1] = 'reviews'
  and (storage.foldername(name))[2] = (select auth.uid())::text);
