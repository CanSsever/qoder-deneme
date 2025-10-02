do $$
begin
  if not exists (select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='read_own_files_like') then
    create policy "read_own_files_like" on storage.objects
      for select using (bucket_id in ('uploads','outputs') and name like auth.uid()::text || '/%');
  end if;
  if not exists (select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='upload_own_files_like') then
    create policy "upload_own_files_like" on storage.objects
      for insert with check (bucket_id in ('uploads','outputs') and name like auth.uid()::text || '/%');
  end if;
  if not exists (select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='update_own_files_like') then
    create policy "update_own_files_like" on storage.objects
      for update using (bucket_id in ('uploads','outputs') and name like auth.uid()::text || '/%');
  end if;
end$$;