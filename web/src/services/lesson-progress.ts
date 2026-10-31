import { query } from "../db/pool";

export interface CourseProgress {
  status: "saved" | "in_progress" | "completed";
  progress: number;
}

/**
 * Progress counts only lessons that are publicly approved. A single statement keeps
 * the numerator/denominator snapshot consistent under concurrent completions.
 */
export async function recomputeLessonProgress(userId: number, courseId: number): Promise<CourseProgress> {
  const rows = await query<CourseProgress>(
    `INSERT INTO enrollments (user_id, course_id, status, progress, updated_at)
     SELECT $1, s.course_id,
            CASE WHEN s.total > 0 AND s.done = s.total THEN 'completed'
                 WHEN s.done > 0 THEN 'in_progress' ELSE 'saved' END,
            CASE WHEN s.total > 0 THEN round(s.done * 100.0 / s.total)::int ELSE 0 END,
            now()
       FROM (SELECT $2::int AS course_id,
                    count(*) FILTER (WHERE l.approved) AS total,
                    count(*) FILTER (WHERE l.approved AND EXISTS (
                      SELECT 1 FROM lesson_progress lp
                       WHERE lp.lesson_id = l.id AND lp.user_id = $1)) AS done
               FROM lessons l WHERE l.course_id = $2) s
     ON CONFLICT (user_id, course_id) DO UPDATE
        SET status = EXCLUDED.status, progress = EXCLUDED.progress, updated_at = now()
     RETURNING status, progress`,
    [userId, courseId],
  );
  return rows[0] ?? { status: "saved", progress: 0 };
}

/**
 * Recompute every enrollment touched by a course after its approved lesson set changes
 * (approve/delete). Covers users who completed a lesson without an enrollment row.
 */
export async function syncCourseEnrollments(courseId: number): Promise<void> {
  await query(
    `WITH stats AS (
       SELECT count(*) FILTER (WHERE approved) AS total FROM lessons WHERE course_id = $1
     ), affected AS (
       SELECT DISTINCT user_id FROM lesson_progress
        WHERE lesson_id IN (SELECT id FROM lessons WHERE course_id = $1)
       UNION
       SELECT user_id FROM enrollments WHERE course_id = $1
     )
     INSERT INTO enrollments (user_id, course_id, status, progress, updated_at)
     SELECT a.user_id, $1,
            CASE WHEN s.total > 0 AND d.done = s.total THEN 'completed'
                 WHEN d.done > 0 THEN 'in_progress' ELSE 'saved' END,
            CASE WHEN s.total > 0 THEN round(d.done * 100.0 / s.total)::int ELSE 0 END,
            now()
       FROM affected a
       CROSS JOIN stats s
       CROSS JOIN LATERAL (
         SELECT count(*) AS done FROM lesson_progress lp
           JOIN lessons l ON l.id = lp.lesson_id
          WHERE l.course_id = $1 AND l.approved AND lp.user_id = a.user_id
       ) d
     ON CONFLICT (user_id, course_id) DO UPDATE
        SET status = EXCLUDED.status, progress = EXCLUDED.progress, updated_at = now()`,
    [courseId],
  );
}
