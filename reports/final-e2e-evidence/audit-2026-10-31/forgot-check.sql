\set ON_ERROR_STOP on
INSERT INTO users (email, password_hash, name) VALUES ('f@example.test','x','F');
-- first request inserts
INSERT INTO password_resets (user_id, token_hash, expires_at)
SELECT 1, repeat('a',64), now() + interval '15 minutes'
 WHERE NOT EXISTS (SELECT 1 FROM password_resets WHERE user_id = 1 AND created_at > now() - (60 * interval '1 second'))
RETURNING id;
-- immediate retry is throttled
INSERT INTO password_resets (user_id, token_hash, expires_at)
SELECT 1, repeat('b',64), now() + interval '15 minutes'
 WHERE NOT EXISTS (SELECT 1 FROM password_resets WHERE user_id = 1 AND created_at > now() - (60 * interval '1 second'))
RETURNING id;
SELECT count(*) AS tokens FROM password_resets WHERE user_id = 1;
-- invalidate all but newest
UPDATE password_resets SET used_at = now() WHERE user_id = 1 AND used_at IS NULL AND id <> (SELECT max(id) FROM password_resets WHERE user_id = 1);
SELECT count(*) FILTER (WHERE used_at IS NULL) AS active FROM password_resets WHERE user_id = 1;
