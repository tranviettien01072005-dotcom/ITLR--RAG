\set ON_ERROR_STOP on
-- fresh schema already applied by -f schema.sql; re-apply is idempotent (tested separately)
SELECT 'token_version' AS check, column_name, column_default FROM information_schema.columns
 WHERE table_name='users' AND column_name='token_version';

INSERT INTO courses (item_id,title) VALUES (1,'C');
INSERT INTO users (email,password_hash,name) VALUES ('u@example.test','old-hash','U');
INSERT INTO lessons (course_id,title,youtube_id,approved) VALUES (1,'L1','v1',true),(1,'L2','v2',true);

-- rollback drill: claim + change password, then fail and roll back
BEGIN;
UPDATE password_resets SET used_at=now() WHERE token_hash='x' RETURNING id;
INSERT INTO password_resets (user_id,token_hash,expires_at) VALUES (1,'t1',now()+interval '10 minutes') RETURNING id;
UPDATE users SET password_hash='new-hash', token_version=token_version+1 WHERE id=1;
SELECT 'inside_tx' AS step, password_hash, token_version FROM users WHERE id=1;
ROLLBACK;
SELECT 'after_rollback' AS step, password_hash, token_version,
       (SELECT count(*) FROM password_resets WHERE used_at IS NOT NULL AND token_hash='x') AS wrongly_used
  FROM users WHERE id=1;

-- idempotent progress recompute (derived from counts, no lost update)
INSERT INTO lesson_progress (user_id,lesson_id) SELECT 1,id FROM lessons WHERE title='L1';
INSERT INTO enrollments (user_id,course_id,status,progress,updated_at)
SELECT 1,1,'saved',0,now() ON CONFLICT DO NOTHING;
INSERT INTO enrollments (user_id,course_id,status,progress,updated_at)
SELECT 1,s.course_id, CASE WHEN s.done=s.total THEN 'completed' WHEN s.done>0 THEN 'in_progress' ELSE 'saved' END,
       round(s.done*100.0/s.total)::int, now()
FROM (SELECT 1::int course_id, count(*) FILTER (WHERE approved) total,
      count(*) FILTER (WHERE approved AND EXISTS(SELECT 1 FROM lesson_progress lp WHERE lp.lesson_id=l.id AND lp.user_id=1)) done
      FROM lessons l WHERE course_id=1) s
ON CONFLICT (user_id,course_id) DO UPDATE SET status=EXCLUDED.status,progress=EXCLUDED.progress,updated_at=now();
SELECT 'recompute_1' AS step, status, progress FROM enrollments WHERE user_id=1 AND course_id=1;
-- same statement again must not change the result
INSERT INTO enrollments (user_id,course_id,status,progress,updated_at)
SELECT 1,s.course_id, CASE WHEN s.done=s.total THEN 'completed' WHEN s.done>0 THEN 'in_progress' ELSE 'saved' END,
       round(s.done*100.0/s.total)::int, now()
FROM (SELECT 1::int course_id, count(*) FILTER (WHERE approved) total,
      count(*) FILTER (WHERE approved AND EXISTS(SELECT 1 FROM lesson_progress lp WHERE lp.lesson_id=l.id AND lp.user_id=1)) done
      FROM lessons l WHERE course_id=1) s
ON CONFLICT (user_id,course_id) DO UPDATE SET status=EXCLUDED.status,progress=EXCLUDED.progress,updated_at=now();
SELECT 'recompute_2' AS step, status, progress FROM enrollments WHERE user_id=1 AND course_id=1;
