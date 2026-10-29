import { Router } from "express";
import { query } from "../db/pool";
import { requireAuth } from "../middleware/auth";
import { assess, buildRoadmap, diagnosticSchema, LearningResource, progressSchema, publicQuiz, tracks, Track, trackSchema } from "../services/learning";

export const learningRouter = Router();
type Profile = { track: Track; goal: string; score: number; level: string; updated_at: string };

async function resources(userId: number) {
  return query<LearningResource>(
    `SELECT c.item_id, c.title, c.description, c.topics, c.level, c.link, c.platform, e.progress, e.status
       FROM courses c LEFT JOIN enrollments e ON e.course_id = c.item_id AND e.user_id = $1
      WHERE c.origin LIKE 'crawl:%' AND c.link ~ '^https?://' ORDER BY c.item_id`, [userId]);
}

learningRouter.get("/learning", requireAuth, async (req, res) => {
  const [profile] = await query<Profile>("SELECT track, goal, score, level, updated_at FROM learning_profiles WHERE user_id = $1", [req.user!.id]);
  const parsed = trackSchema.safeParse(req.query.track);
  const track = parsed.success ? parsed.data : profile?.track || "python";
  const roadmap = profile ? buildRoadmap(profile.track, profile.level, await resources(req.user!.id)) : [];
  res.setHeader("Cache-Control", "private, no-store");
  res.render("learning", { title: "Lộ trình học", profile: profile || null, track, tracks, quiz: publicQuiz(track), roadmap });
});

learningRouter.post("/api/learning/diagnostic", requireAuth, async (req, res) => {
  const parsed = diagnosticSchema.safeParse(req.body);
  if (!parsed.success) return res.status(400).json({ error: "Chọn mục tiêu và trả lời đủ 3 câu hỏi (mục tiêu 5–240 ký tự)." });
  const { track, goal, answers } = parsed.data;
  const result = assess(track, answers);
  await query(
    `INSERT INTO learning_profiles (user_id, track, goal, score, level)
     VALUES ($1,$2,$3,$4,$5) ON CONFLICT (user_id)
     DO UPDATE SET track = EXCLUDED.track, goal = EXCLUDED.goal, score = EXCLUDED.score,
       level = EXCLUDED.level, updated_at = now()`, [req.user!.id, track, goal, result.score, result.level]);
  res.json({ ok: true, ...result });
});

learningRouter.post("/api/learning/progress", requireAuth, async (req, res) => {
  const parsed = progressSchema.safeParse(req.body);
  if (!parsed.success) return res.status(400).json({ error: "Tiến độ không hợp lệ: đã lưu = 0%, hoàn thành = 100%." });
  const { course_id, status, progress } = parsed.data;
  // The current roadmap is computed server-side so a client cannot save an unrelated or synthetic item here.
  const [profile] = await query<Profile>("SELECT track, level FROM learning_profiles WHERE user_id = $1", [req.user!.id]);
  if (!profile) return res.status(409).json({ error: "Hãy hoàn thành đánh giá đầu vào trước." });
  const allowed = buildRoadmap(profile.track, profile.level, await resources(req.user!.id)).some(s => s.resources.some(r => r.item_id === course_id));
  if (!allowed) return res.status(404).json({ error: "Tài nguyên không thuộc lộ trình hiện tại." });
  const [enrollment] = await query(
    `INSERT INTO enrollments (user_id, course_id, status, progress) VALUES ($1,$2,$3,$4)
     ON CONFLICT (user_id, course_id) DO UPDATE SET status = EXCLUDED.status, progress = EXCLUDED.progress, updated_at = now()
     RETURNING status, progress`, [req.user!.id, course_id, status, progress]);
  res.json({ ok: true, enrollment });
});
