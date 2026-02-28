-- Migration 051: RBAC role model update to sudo/admin/read
--
-- Changes:
-- - Introduce explicit global role `sudo`
-- - Keep `admin` and `read` as seat-scoped roles
-- - Backfill legacy values:
--     admin -> sudo
--     user  -> read

DO $$
DECLARE
    role_check_name text;
BEGIN
    -- Drop existing users.role CHECK constraint (name may vary by environment).
    SELECT con.conname
      INTO role_check_name
      FROM pg_constraint con
      JOIN pg_class rel ON rel.oid = con.conrelid
      JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
     WHERE rel.relname = 'users'
       AND nsp.nspname = 'public'
       AND con.contype = 'c'
       AND pg_get_constraintdef(con.oid) ILIKE '%role%'
     LIMIT 1;

    IF role_check_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.users DROP CONSTRAINT %I', role_check_name);
    END IF;

    -- Backfill legacy roles.
    UPDATE public.users SET role = 'sudo' WHERE role = 'admin';
    UPDATE public.users SET role = 'read' WHERE role = 'user';
    UPDATE public.users SET role = 'read' WHERE role IS NULL OR role NOT IN ('sudo', 'admin', 'read');

    -- Enforce new role model.
    ALTER TABLE public.users
        ALTER COLUMN role SET DEFAULT 'read';

    ALTER TABLE public.users
        ADD CONSTRAINT users_role_check
        CHECK (role IN ('sudo', 'admin', 'read'));
END $$;
