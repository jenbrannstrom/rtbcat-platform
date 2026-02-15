-- Migration 044: Canonical compatibility views for legacy precompute tables
-- Introduces canonical Google-centric table names via read-only views.
-- Keeps legacy physical tables unchanged while callers migrate gradually.

DO $$
DECLARE
    alias_map CONSTANT TEXT[][] := ARRAY[
        ARRAY['pretarg_daily', 'home_config_daily'],
        ARRAY['pretarg_size_daily', 'config_size_daily'],
        ARRAY['pretarg_geo_daily', 'config_geo_daily'],
        ARRAY['pretarg_publisher_daily', 'config_publisher_daily'],
        ARRAY['pretarg_creative_daily', 'config_creative_daily'],
        ARRAY['seat_size_daily', 'home_size_daily'],
        ARRAY['seat_geo_daily', 'home_geo_daily'],
        ARRAY['seat_publisher_daily', 'home_publisher_daily'],
        ARRAY['seat_daily', 'home_seat_daily']
    ];
    pair TEXT[];
    target_view TEXT;
    source_table TEXT;
    target_kind CHAR;
BEGIN
    FOREACH pair SLICE 1 IN ARRAY alias_map LOOP
        target_view := pair[1];
        source_table := pair[2];
        target_kind := NULL;

        IF to_regclass('public.' || source_table) IS NULL THEN
            RAISE NOTICE 'Skipping canonical view %: source table % does not exist', target_view, source_table;
            CONTINUE;
        END IF;

        SELECT c.relkind
        INTO target_kind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = target_view;

        IF target_kind IS NOT NULL AND target_kind <> 'v' THEN
            RAISE NOTICE 'Skipping canonical view %: object exists and is not a view', target_view;
            CONTINUE;
        END IF;

        EXECUTE format(
            'CREATE OR REPLACE VIEW %I AS SELECT * FROM %I',
            target_view,
            source_table
        );
    END LOOP;
END $$;

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '044_canonical_alias_views',
    CURRENT_TIMESTAMP,
    'Add canonical compatibility views for legacy precompute serving tables'
)
ON CONFLICT (version) DO NOTHING;
