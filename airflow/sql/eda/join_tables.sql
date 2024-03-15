SELECT *
    -- notices.id AS notices_id, 
    -- resource_links.id AS resource_links_id
    -- summary_chunks.id AS summary_chunks_id,
FROM notices
INNER JOIN resource_links ON notices.id = resource_links.notice_id;
-- INNER JOIN summary_chunks ON resource_links.id = summary_chunks.resource_link_id;