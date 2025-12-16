-- Fix database permissions for polyedgeuser
-- Run this as PostgreSQL superuser (postgres)

-- Grant usage and create privileges on the public schema
GRANT USAGE ON SCHEMA public TO polyedgeuser;
GRANT CREATE ON SCHEMA public TO polyedgeuser;

-- If the schema already has objects, grant privileges on existing objects
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO polyedgeuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO polyedgeuser;

-- Grant privileges on future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO polyedgeuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO polyedgeuser;


