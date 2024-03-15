select sum(file_tokens) / 1000000 * .25
from resource_links 
where text is not null 
and text != 'unparsable' 
and text != 'adobe-error'
and text != 'encoding-error';


select count(file_tokens) * 2000 / 1000000 * .50
from resource_links 
where text is not null 
and text != 'unparsable' 
and text != 'adobe-error'
and text != 'encoding-error';
SELECT sum(file_tokens)
from resource_links
WHERE text is NOT NULL;

-- Combined Cost for using just construction items 
select sum(file_tokens) / 1000000 * .25
from resource_links 
where text is not null 
and text != 'unparsable' 
and text != 'adobe-error'
and text != 'encoding-error'
;

SELECT sum(file_tokens) / 1000000 * .25 as cost
-- select *
FROM notices
INNER JOIN resource_links ON notices.id = resource_links.notice_id
INNER JOIN naics_codes ON notices.naics_code_id = naics_codes.id
where "naicsCode" = 236220; 
