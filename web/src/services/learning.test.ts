import { describe, expect, it } from "vitest";
import { assess, publicQuiz, buildRoadmap, progressSchema } from "./learning";

describe("learning diagnostic", () => {
  it("keeps scoring keys server-side and requires exactly three valid answers", () => {
    expect(publicQuiz("python")).toHaveLength(3);
    expect(JSON.stringify(publicQuiz("python"))).not.toMatch(/correct|answer/);
    expect(() => assess("python", [0])).toThrow();
    expect(() => assess("python", [0, 0, 99])).toThrow();
  });
  it("scores submitted answers and keeps weak learners on prerequisites", () => {
    expect(assess("python", [1, 0, 2])).toEqual({ score: 3, level: "intermediate" });
    expect(assess("python", [0, 1, 0])).toEqual({ score: 0, level: "beginner" });
  });
});
it("orders prerequisites, excludes unrelated resources, preserves saved progress and does not invent resources", () => {
  const rows = [
    { item_id: 2, title: "Python functions", description: "", topics: "python functions", level: "Intermediate", progress: 50, status: "in_progress" },
    { item_id: 1, title: "Python basics", description: "", topics: "python", level: "Beginner", progress: 100, status: "completed" },
    { item_id: 3, title: "CSS", description: "", topics: "css", level: "Beginner", progress: null, status: null },
  ];
  const roadmap = buildRoadmap("python", "beginner", rows);
  expect(roadmap.flatMap(s => s.resources.map(r => r.item_id))).toEqual([1, 2]);
  expect(roadmap[0].resources[0].progress).toBe(100);
  expect(roadmap[1].resources[0].item_id).toBe(2);
  expect(roadmap[1].prerequisite).toBe(roadmap[0].title);
  expect(buildRoadmap("python", "beginner", [...rows].reverse())).toEqual(roadmap);
  expect(buildRoadmap("devops", "beginner", []) .every(s => !s.resources.length)).toBe(true);
});
it("rejects contradictory enrollment status/progress", () => {
  expect(progressSchema.safeParse({ course_id: 1, status: "completed", progress: 20 }).success).toBe(false);
  expect(progressSchema.safeParse({ course_id: 1, status: "saved", progress: 20 }).success).toBe(false);
  expect(progressSchema.safeParse({ course_id: 1, status: "in_progress", progress: 100 }).success).toBe(false);
  expect(progressSchema.safeParse({ course_id: 1, status: "completed", progress: 100 }).success).toBe(true);
});
it("uses Python tutorial prerequisites before library references from the real catalog snapshot", () => {
  const snapshot = [
    [5059, "copy — Shallow and deep copy operations", "library/copy.html"],
    [5060, "inspect — Inspect live objects", "library/inspect.html"],
    [5062, "fractions — Rational numbers", "library/fractions.html"],
    [5087, "unittest — Unit testing framework", "library/unittest.html"],
    [5091, "csv — CSV file reading and writing", "library/csv.html"],
    [5092, "json — JSON encoder and decoder", "library/json.html"],
    [5098, "pathlib — Object-oriented filesystem paths", "library/pathlib.html"],
    [5108, "datetime — Basic date and time types", "library/datetime.html"],
    [5121, "8. Errors and Exceptions", "tutorial/errors.html"],
    [5123, "6. Modules", "tutorial/modules.html"],
    [5124, "5. Data Structures", "tutorial/datastructures.html"],
    [5125, "4. More Control Flow Tools", "tutorial/controlflow.html"],
    [5126, "3. An Informal Introduction to Python", "tutorial/introduction.html"],
  ] as const;
  const rows = snapshot.map(([item_id, title, path]) => ({ item_id, title, link: `https://docs.python.org/3/${path}`, topics: "python,programming", description: "", level: "Trung cấp", status: "saved", progress: 0 }));
  const roadmap = buildRoadmap("python", "beginner", rows);
  expect(roadmap.map(step => step.resources.map(r => r.item_id))).toEqual([[5126, 5125], [5123, 5121], [5091, 5092]]);
  expect(buildRoadmap("python", "beginner", [...rows].reverse())).toEqual(roadmap);
  const updated = rows.map(r => r.item_id === 5126 ? { ...r, progress: 50, status: "in_progress" } : r);
  expect(buildRoadmap("python", "beginner", updated)[0].resources[0].progress).toBe(50);
  expect(buildRoadmap("python", "beginner", rows.filter(r => r.item_id === 5108)).every(s => !s.resources.length)).toBe(true);
});
