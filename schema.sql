-- Ejecutar una vez en Supabase > SQL Editor

create table if not exists clientes (
  id bigint generated always as identity primary key,
  nombre text not null,
  telefono text, email text, nif text, direccion text, notas text,
  created_at timestamptz default now()
);

create table if not exists servicios (
  id bigint generated always as identity primary key,
  nombre text not null,
  descripcion text,
  precio numeric default 0
);

create table if not exists eventos (
  id bigint generated always as identity primary key,
  cliente_id bigint references clientes(id) on delete set null,
  titulo text not null,
  tipo text,
  fecha date,
  hora_inicio text, hora_fin text,
  lugar text,
  invitados int,
  estado text default 'Consulta',
  servicios text[] default '{}',
  notas text,
  guion jsonb default '[]',
  created_at timestamptz default now()
);

create table if not exists presupuestos (
  id bigint generated always as identity primary key,
  numero text unique not null,
  evento_id bigint references eventos(id) on delete cascade,
  cliente_id bigint references clientes(id) on delete set null,
  fecha date default current_date,
  validez_dias int default 15,
  lineas jsonb default '[]',
  descuento numeric default 0,
  iva numeric default 21,
  estado text default 'Borrador',
  condiciones text,
  created_at timestamptz default now()
);

create table if not exists facturas (
  id bigint generated always as identity primary key,
  numero text unique not null,
  presupuesto_id bigint references presupuestos(id) on delete set null,
  evento_id bigint references eventos(id) on delete set null,
  cliente_id bigint references clientes(id) on delete set null,
  fecha date default current_date,
  vencimiento date,
  lineas jsonb default '[]',
  descuento numeric default 0,
  iva numeric default 21,
  estado text default 'Pendiente',
  metodo_pago text,
  notas text,
  created_at timestamptz default now()
);

-- La app usa la clave service_role guardada en los secrets de Streamlit (nunca en el repo),
-- así que dejamos RLS activado y sin políticas públicas: nadie más puede leer los datos.
alter table clientes enable row level security;
alter table servicios enable row level security;
alter table eventos enable row level security;
alter table presupuestos enable row level security;
alter table facturas enable row level security;
