DO $$ 
DECLARE 
    _tbl text; 
BEGIN 
    FOR _tbl IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') 
    LOOP 
        EXECUTE 'TRUNCATE TABLE ' || _tbl || ' CASCADE'; 
    END LOOP; 
END $$;