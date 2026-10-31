-- Schema/logic check on a disposable PostgreSQL 16 container.
\set ON_ERROR_STOP on

-- migrated schema must expose token_version
SELECT column_name, data_type, column_default
  FROM information_schema.columns
 WHERE table_name = 'users' AND column_name = 'token_version';

INSERT INTO courses (item_id, title) VALUES (1, 'Course A');
INSERT INTO users (email, password_hash, name) VALUES ('a@example.test', 'x', 'A');
INSERT INTO users (email, password_hash, name) VALUES ('b@example.test', 'x', 'B');

INSERT INTO lessons (course_id, title, youtube_id, approved) VALUES (1, 'L1', 'v1', true);
INSERT INTO lessons (course_id, title, youtube_id, approved) VALUES (1, 'L2', 'v2', true);
INSERT INTO lessons (course_id, title, youtube_id, approved) VALUES (1, 'L3', 'v3', false);

-- user A completed one approved lesson
INSERT INTO lesson_progress (user_id, lesson_id) SELECT 1, id FROM lessons WHERE title = 'L1';

-- per-user recompute (same statement as web/src/services/lesson-progress.ts)
INSERT INTO enrollments (user_id, course_id, status, progress, updated_at)
SELECT 1, s.course_id,
       CASE WHEN s.total > 0 AND s.done = s.total THEN 'completed'
            WHEN s.done > 0 THEN 'in_progress' ELSE 'saved' END,
       CASE WHEN s.total > 0 THEN round(s.done * 100.0 / s.total)::int ELSE 0 END,
       now()
  FROM (SELECT 1::int AS course_id,
               count(*) FILTER (WHERE l.approved) AS total,
               count(*) FILTER (WHERE l.approved AND EXISTS (
                 SELECT 1 FROM lesson_progress lp
                  WHERE lp.lesson_id = l.id AND lp.user_id = 1)) AS done
          FROM lessons l WHERE l.course_id = 1) s
ON CONFLICT (user_id, course_id) DO UPDATE
   SET status = EXCLUDED.status, progress = EXCLUDED.progress, updated_at = now();

SELECT 'after_complete' AS step, status, progress FROM enrollments WHERE user_id = 1 AND course_id = 1;

-- approving L3 changes the denominator for every learner (course-wide resync)
UPDATE lessons SET approved = true WHERE title = 'L3';

WITH stats AS (
  SELECT count(*) FILTER (WHERE approved) AS total FROM lessons WHERE course_id = 1
), affected AS (
  SELECT DISTINCT user_id FROM lesson_progress
   WHERE lesson_id IN (SELECT id FROM lessons WHERE course_id = 1)
  UNION
  SELECT user_id FROM enrollments WHERE course_id = 1
)
INSERT INTO enrollments (user_id, course_id, status, progress, updated_at)
SELECT a.user_id, 1,
       CASE WHEN s.total > 0 AND d.done = s.total THEN 'completed'
            WHEN d.done > 0 THEN 'in_progress' ELSE 'saved' END,
       CASE WHEN s.total > 0 THEN round(d.done * 100.0 / s.total)::int ELSE 0 END,
       now()
  FROM affected a
  CROSS JOIN stats s
  CROSS JOIN LATERAL (
    SELECT count(*) AS done FROM lesson_progress lp
      JOIN lessons l ON l.id = lp.lesson_id
     WHERE l.course_id = 1 AND l.approved AND lp.user_id = a.user_id
  ) d
ON CONFLICT (user_id, course_id) DO UPDATE
   SET status = EXCLUDED.status, progress = EXCLUDED.progress, updated_at = now();

SELECT 'after_approve' AS step, status, progress FROM enrollments WHERE user_id = 1 AND course_id = 1;

-- completion of an approved lesson reaches 100 only when every approved lesson is done
INSERT INTO lesson_progress (user_id, lesson_id) SELECT 1, id FROM lessons WHERE title = 'L2';
INSERT INTO lesson_progress (user_id, lesson_id) SELECT 1, id FROM lessons WHERE title = 'L3';

WITH stats AS (
  SELECT count(*) FILTER (WHERE approved) AS total FROM lessons WHERE course_id = 1
), affected AS (
  SELECT DISTINCT user_id FROM lesson_progress
   WHERE lesson_id IN (SELECT id FROM lessons WHERE course_id = 1)
  UNION
  SELECT user_id FROM enrollments WHERE course_id = 1
)
INSERT INTO enrollments (user_id, course_id, status, progress, updated_at)
SELECT a.user_id, 1,
       CASE WHEN s.total > 0 AND d.done = s.total THEN 'completed'
            WHEN d.done > 0 THEN 'in_progress' ELSE 'saved' END,
       CASE WHEN s.total > 0 THEN round(d.done * 100.0 / s.total)::int ELSE 0 END,
       now()
  FROM affected a
  CROSS JOIN stats s
  CROSS JOIN LATERAL (
    SELECT count(*) AS done FROM lesson_progress lp
      JOIN lessons l ON l.id = lp.lesson_id
     WHERE l.course_id = 1 AND l.approved AND lp.user_id = a.user_id
  ) d
ON CONFLICT (user_id, course_id) DO UPDATE
   SET status = EXCLUDED.status, progress = EXCLUDED.progress, updated_at = now();

SELECT 'after_all' AS step, status, progress FROM enrollments WHERE user_id = 1 AND course_id = 1;

-- unapproved completion must not be countable: insert L4 pending, complete it, resync
INSERT INTO lessons (course_id, title, youtube_id, approved) VALUES (1, 'L4', 'v4', false);
INSERT INTO lesson_progress (user_id, lesson_id) SELECT 1, id FROM lessons WHERE title = 'L4';

WITH stats AS (
  SELECT count(*) FILTER (WHERE approved) AS total FROM lessons WHERE course_id = 1
), affected AS (
  SELECT DISTINCT user_id FROM lesson_progress
   WHERE lesson_id IN (SELECT id FROM lessons WHERE course_id = 1)
  UNION
  SELECT user_id FROM enrollments WHERE course_id = 1
)
INSERT INTO enrollments (user_id, course_id, status, progress, updated_at)
SELECT a.user_id, 1,
       CASE WHEN s.total > 0 AND d.done = s.total THEN 'completed'
            WHEN d.done > 0 THEN 'in_progress' ELSE 'saved' END,
       CASE WHEN s.total > 0 THEN round(d.done * 100.0 / s.total)::int ELSE 0 END,
       now()
  FROM affected a
  CROSS JOIN stats s
  CROSS JOIN LATERAL (
    SELECT count(*) AS done FROM lesson_progress lp
      JOIN lessons l ON l.id = lp.lesson_id
     WHERE l.course_id = 1 AND l.approved AND lp.user_id = a.user_id
  ) d
ON CONFLICT (user_id, course_id) DO UPDATE
   SET status = EXCLUDED.status, progress = EXCLUDED.progress, updated_at = now();

SELECT 'unapproved_not_counted' AS step, status, progress FROM enrollments WHERE user_id = 1 AND course_id = 1;

-- token version revocation
UPDATE users SET token_version = token_version + 1 WHERE id = 1 RETURNING token_version;
