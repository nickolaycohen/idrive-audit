-- device registry scripts
SELECT d.device_name, u.used_bytes, u.free_bytes
FROM devices d
JOIN device_usage u ON d.device_id = u.device_id
WHERE u.recorded_at = (
    SELECT MAX(recorded_at)
    FROM device_usage u2
    WHERE u2.device_id = d.device_id
);

select *
from devices d 
join device_usage du on du.device_id = d.device_id
order by recorded_at 

select * 
from folders f 
order by f.last_scanned desc

-- show all folders without class and not drilled down - pick select item to tag/classify
select --f.folder_id, f.device_id, 
replace(path,'/Volumes','/'), size_bytes / 1024 / 1024 / 1024 AS size_gb, size_bytes, -- needs_backup,
datetime(last_modified, 'unixepoch', 'localtime') AS modified_time, f.last_scanned, tag, f.class_id, class_name, fp.priority_name, bp.policy_name 
from folders f 
left join folder_classes fc on fc.class_id = f.class_id 
left join folder_priorities fp on fp.priority_id = fc.priority_id 
left join backup_policies bp on bp.policy_id = fp.backup_policy_id 
where (f.class_id = 0 ) and not f.drilled 
order by size_bytes desc

-- list all tagged folders
select --f.folder_id, f.device_id,
replace(path,'/Volumes','/'), size_bytes / 1024 / 1024 / 1024 AS size_gb, 
datetime(last_modified, 'unixepoch', 'localtime') AS modified_time, f.last_scanned, tag, class_name, fp.priority_name, bp.policy_name, f.drilled 
from folders f 
left join folder_classes fc on fc.class_id = f.class_id 
left join folder_priorities fp on fp.priority_id = fc.priority_id 
left join backup_policies bp on bp.policy_id = fp.backup_policy_id 
where tag is not null or (f.class_id <> 0 and f.drilled)
order by size_bytes desc

-- list all drilled folders
select --f.folder_id, f.device_id,
replace(path,'/Volumes','/'), size_bytes / 1024 / 1024 / 1024 AS size_gb, 
datetime(last_modified, 'unixepoch', 'localtime') AS modified_time, f.last_scanned, tag, f.finder_tag, class_name, fp.priority_name, bp.policy_name, f.drilled 
from folders f 
left join folder_classes fc on fc.class_id = f.class_id 
left join folder_priorities fp on fp.priority_id = fc.priority_id 
left join backup_policies bp on bp.policy_id = fp.backup_policy_id 
where f.drilled 
order by size_bytes desc

-- all larger than 500GB
select --f.folder_id, f.device_id,
replace(path,'/Volumes','/'), size_bytes / 1024 / 1024 / 1024 AS size_gb, 
tag, class_name, fp.priority_name, bp.policy_name, f.drilled,
datetime(last_modified, 'unixepoch', 'localtime') AS modified_time, f.last_scanned
from folders f 
left join folder_classes fc on fc.class_id = f.class_id 
left join folder_priorities fp on fp.priority_id = fc.priority_id 
left join backup_policies bp on bp.policy_id = fp.backup_policy_id 
where size_gb > 400
order by tag desc, class_name, drilled desc

-- delete
-- from folders 
-- where between 122 and 2676

--delete 
--from devices

SELECT 
    path, 
    size_bytes / 1024 / 1024 / 1024 AS size_gb,
    datetime(last_modified, 'unixepoch', 'localtime') AS modified_time
FROM folders
ORDER BY modified_time  DESC;

select * 
from folders

-- delete FROM folders where folder_id = 4

select * 
from folder_classes fc 

update folder_classes 
set policy = "IDriveBackup"
where class_id =1

select *
from folder_priorities fp 

select * 
from backup_policies bp 

insert INTO 
backup_policies(policy_id, policy_name) values (0,'None')

insert into 
folder_classes(class_id, class_name, priority_id) values (0,'None', 0)

update 
folders 
set class_id = 0

insert into 
folder_priorities (priority_id, priority_name, backup_policy_id) values (0,'0-None',0)

-- list folders by location
select --f.folder_id, f.device_id, 
replace(path,'/Volumes','/'), size_bytes / 1024 / 1024 / 1024 AS size_gb, -- needs_backup,
datetime(last_modified, 'unixepoch', 'localtime') AS modified_time, f.last_scanned, tag, f.class_id, class_name, fp.priority_name, bp.policy_name 
from folders f 
left join folder_classes fc on fc.class_id = f.class_id 
left join folder_priorities fp on fp.priority_id = fc.priority_id 
left join backup_policies bp on bp.policy_id = fp.backup_policy_id 
where (f.class_id = 0 ) and not f.drilled 
order by path

-- show all
-- show all folders without class and not drilled down - pick select item to tag/classify
select --f.folder_id, f.device_id, 
replace(path,'/Volumes','/'), size_bytes / 1024 / 1024 / 1024 AS size_gb, --size_bytes, -- needs_backup,
datetime(last_modified, 'unixepoch', 'localtime') AS modified_time, strftime('%Y-%m-%d %H:%M', datetime(f.last_scanned, 'localtime')) as lastScanned, 
tag, f.finder_tag, class_name, fp.priority_name, bp.policy_name 
from folders f 
left join folder_classes fc on fc.class_id = f.class_id 
left join folder_priorities fp on fp.priority_id = fc.priority_id 
left join backup_policies bp on bp.policy_id = fp.backup_policy_id 
-- where (f.class_id = 0 ) and not f.drilled 
order by size_bytes desc

update folders
SET finder_tag = NULL
where finder_tag like '%tmp%'