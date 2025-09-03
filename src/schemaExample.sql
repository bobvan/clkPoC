create table if not exists events(
  id integer primary key,
  tsMonoNs integer not null,
  tsUtcNs integer,
  source text not null,
  kind text not null,
  level integer default 20,
  data text
);
create index if not exists idx_events_ts on events(tsMonoNs);

create table if not exists samples(
  id integer primary key,
  tsMonoNs integer not null,
  ppsErrorNs integer not null,
  dacCode integer,
  tempMilliC integer,
  flags integer default 0
);
create index if not exists idx_samples_ts on samples(tsMonoNs);
