import { z } from "zod";

export const trackSchema = z.enum(["python", "web", "devops"]);
export type Track = z.infer<typeof trackSchema>;
export const tracks: Record<Track, string> = { python: "Lập trình Python", web: "Phát triển Web", devops: "Linux & DevOps" };
const quizzes = {
  python: [
    { prompt: "Kiểu nào lưu một dãy có thể thay đổi?", options: ["tuple", "list", "int"], correct: 1 },
    { prompt: "len([1, 2, 3]) trả về gì?", options: ["3", "2", "6"], correct: 0 },
    { prompt: "Từ khóa định nghĩa hàm trong Python?", options: ["function", "class", "def"], correct: 2 },
  ],
  web: [
    { prompt: "HTML dùng chủ yếu để làm gì?", options: ["Cấu trúc nội dung", "Truy vấn dữ liệu", "Mã hóa mạng"], correct: 0 },
    { prompt: "Thuộc tính CSS nào tạo khoảng cách bên trong phần tử?", options: ["margin", "padding", "display"], correct: 1 },
    { prompt: "Mã HTTP 404 có nghĩa gì?", options: ["Thành công", "Chuyển hướng", "Không tìm thấy"], correct: 2 },
  ],
  devops: [
    { prompt: "Lệnh nào liệt kê tệp trên Linux?", options: ["ls", "cd", "pwd"], correct: 0 },
    { prompt: "Git dùng để làm gì?", options: ["Lưu mật khẩu", "Quản lý phiên bản", "Cấp IP"], correct: 1 },
    { prompt: "Container thường đóng gói gì?", options: ["Chỉ mã nguồn", "Toàn bộ phần cứng", "Ứng dụng và các phụ thuộc"], correct: 2 },
  ],
} satisfies Record<Track, { prompt: string; options: string[]; correct: number }[]>;

export function publicQuiz(track: Track) {
  return quizzes[track].map(({ prompt, options }) => ({ prompt, options }));
}
export function assess(track: Track, input: unknown) {
  const answers = z.array(z.number().int().min(0).max(2)).length(3).parse(input);
  const score = answers.reduce((n, answer, i) => n + Number(answer === quizzes[track][i].correct), 0);
  return { score, level: score >= 2 ? "intermediate" : "beginner" } as const;
}

export const diagnosticSchema = z.object({
  track: trackSchema,
  goal: z.string().trim().min(5).max(240),
  answers: z.array(z.number().int().min(0).max(2)).length(3),
}).strict();
export const progressSchema = z.object({
  course_id: z.number().int().positive(),
  status: z.enum(["saved", "in_progress", "completed"]),
  progress: z.number().int().min(0).max(100),
}).strict().refine(v => v.status === "completed" ? v.progress === 100 : v.status === "saved" ? v.progress === 0 : v.progress < 100);

export interface LearningResource {
  item_id: number; title: string; description: string | null; topics: string | null; level: string | null;
  progress: number | null; status: string | null; link?: string | null; platform?: string | null;
}
const plans = {
  python: [
    { title: "Nền tảng Python", outcome: "Biến, điều kiện, vòng lặp và cấu trúc dữ liệu.", terms: /python/i },
    { title: "Hàm và tổ chức chương trình", outcome: "Viết hàm, xử lý lỗi và chia nhỏ chương trình.", terms: /python/i },
    { title: "Thực hành dự án", outcome: "Xây dựng công cụ nhỏ; tự viết kiểm thử và README.", terms: /python/i },
  ],
  web: [
    { title: "HTML & CSS", outcome: "Dựng trang có cấu trúc, biểu mẫu và giao diện responsive.", terms: /html|css|web/i },
    { title: "JavaScript & trình duyệt", outcome: "DOM, sự kiện và gọi HTTP API.", terms: /javascript|typescript|web/i },
    { title: "Ứng dụng Web", outcome: "Kết nối frontend với backend và triển khai dự án.", terms: /react|node|web|frontend|backend/i },
  ],
  devops: [
    { title: "Linux & Git", outcome: "Làm việc với terminal và quản lý phiên bản.", terms: /linux|git|devops/i },
    { title: "Container", outcome: "Đóng gói ứng dụng và cấu hình môi trường.", terms: /docker|container|devops/i },
    { title: "Triển khai & vận hành", outcome: "Tự động hóa triển khai và theo dõi ứng dụng.", terms: /kubernetes|deploy|ci\/cd|devops/i },
  ],
};

// Match chapter paths/titles, not generic catalog topics or words such as "Basic" in datetime.
const pythonStages = [
  [/\/tutorial\/introduction\.html/i, /\/tutorial\/controlflow\.html/i, /\/tutorial\/datastructures\.html/i, /\/tutorial\/(?:interpreter|appetite)\.html/i, /python (?:basics|introduction)|introduction to python/i],
  [/\/tutorial\/modules\.html/i, /\/tutorial\/errors\.html/i, /\/library\/functions\.html|python functions/i, /\/tutorial\/(?:classes|venv)\.html/i, /python (?:modules|errors)/i],
  [/\/library\/csv\.html/i, /\/library\/json\.html/i, /\/library\/pathlib\.html/i, /\/tutorial\/inputoutput\.html/i, /\/library\/(?:unittest|doctest)\.html|python (?:testing|project)/i],
];
function pythonRank(resource: LearningResource, stage: number) {
  const text = `${resource.title} ${resource.link || ""}`;
  return pythonStages[stage].findIndex(pattern => pattern.test(text));
}

export function buildRoadmap(track: Track, level: string, resources: LearningResource[]) {
  const used = new Set<number>();
  return plans[track].map((step, index) => {
    const candidates = resources.filter(r => !used.has(r.item_id) && step.terms.test(`${r.title} ${r.topics || ""}`) && (track !== "python" || pythonRank(r, index) >= 0));
    candidates.sort((a, b) => {
      if (track === "python") return pythonRank(a, index) - pythonRank(b, index) || a.item_id - b.item_id;
      const rank = (r: LearningResource) => /beginner|cơ bản|basic|intro/i.test(`${r.level} ${r.title}`) ? 0 : /advanced|nâng cao/i.test(`${r.level} ${r.title}`) ? 2 : 1;
      const target = index === 0 ? 0 : index === 1 ? 1 : 2;
      return Math.abs(rank(a) - target) - Math.abs(rank(b) - target) || a.item_id - b.item_id;
    });
    // Leave resources for later prerequisites when the real catalog is still small.
    const selected = candidates.slice(0, track === "python" || candidates.length > 3 ? 2 : 1);
    selected.forEach(r => used.add(r.item_id));
    return { title: step.title, outcome: step.outcome, prerequisite: index ? plans[track][index - 1].title : "Không yêu cầu", suggestion: index === 0 && level === "intermediate" ? "Ôn nhanh nền tảng trước khi tiếp tục." : "Học theo thứ tự và tự kiểm tra đầu ra.", resources: selected };
  });
}
