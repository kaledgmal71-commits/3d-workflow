create table public.rooms_registry (
  id text primary key,
  type text not null check (type in ('stage','router','loop','gate','store','test','metric')),
  std_level text not null check (std_level in ('S','F','P','C')),
  std_term text not null,
  pack text
);
alter table public.rooms_registry enable row level security;
create policy "registry readable by signed-in users" on public.rooms_registry for select to authenticated using (true);

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 120),
  idea text not null check (char_length(idea) <= 8000),
  domain text check (domain is null or char_length(domain) <= 80),
  created_at timestamptz not null default now()
);
create index projects_owner_idx on public.projects(owner);
alter table public.projects enable row level security;
create policy "owner reads projects" on public.projects for select to authenticated using (owner = (select auth.uid()));
create policy "owner inserts projects" on public.projects for insert to authenticated with check (owner = (select auth.uid()));
create policy "owner updates projects" on public.projects for update to authenticated using (owner = (select auth.uid())) with check (owner = (select auth.uid()));
create policy "owner deletes projects" on public.projects for delete to authenticated using (owner = (select auth.uid()));

create table public.workflow_versions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  version int not null check (version > 0),
  plan jsonb not null,
  model text,
  created_at timestamptz not null default now(),
  unique (project_id, version)
);
create index workflow_versions_project_idx on public.workflow_versions(project_id);
alter table public.workflow_versions enable row level security;
create policy "owner reads versions" on public.workflow_versions for select to authenticated using (exists (select 1 from public.projects p where p.id = project_id and p.owner = (select auth.uid())));
create policy "owner inserts versions" on public.workflow_versions for insert to authenticated with check (exists (select 1 from public.projects p where p.id = project_id and p.owner = (select auth.uid())));
create policy "owner deletes versions" on public.workflow_versions for delete to authenticated using (exists (select 1 from public.projects p where p.id = project_id and p.owner = (select auth.uid())));

create table public.generations (
  id bigint generated always as identity primary key,
  owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  input_tokens int,
  output_tokens int
);
create index generations_owner_time_idx on public.generations(owner, created_at desc);
alter table public.generations enable row level security;
create policy "owner reads generations" on public.generations for select to authenticated using (owner = (select auth.uid()));
create policy "owner inserts generations" on public.generations for insert to authenticated with check (owner = (select auth.uid()));
