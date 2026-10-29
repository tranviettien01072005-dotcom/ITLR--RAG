import { pool } from "./pool";
import { syncCourses } from "./sync-courses";
// Safe upsert also seeds an empty database without destroying account enrollments.
syncCourses().catch(error => { console.error("[seed]", error.message); process.exitCode = 1; }).finally(() => pool.end());
