"""Offline catalog answer formatting, independent of retrieval and LLM transport."""

from itlr.chatbot import knowledge_base as kb
from itlr.core.recommender import QUERY_STOP_WORDS, normalize_text, row_to_dict, strip_accents


_BEGINNER_KW = ["co ban", "nhap mon", "can ban", "beginner", "fundamental",
                "introduction", "bat dau", "zero", "101", "basic", "lam quen"]
_ADVANCED_KW = ["nang cao", "advanced", "chuyen sau", "master", "expert",
                "production", "scale", "toi uu", "kien truc", "architecture"]


_LEVEL_TO_RANK = {"co ban": 0, "trung cap": 1, "nang cao": 2}


def difficulty_rank(item):
    """0 = nền tảng, 1 = trung cấp, 2 = nâng cao.

    Ưu tiên trường `level` THẬT trong catalog (chính xác nhất). Nếu dataset cũ
    không có `level`, mới suy ra từ từ khóa tiêu đề/chủ đề/mô tả (kiểm tra từ khóa
    nền tảng TRƯỚC nâng cao để khóa "Cơ bản đến nâng cao X" vẫn coi là điểm khởi đầu).
    """
    level = strip_accents(str(item.get("level", ""))).strip()
    if level in _LEVEL_TO_RANK:
        return _LEVEL_TO_RANK[level]

    text = strip_accents(
        f"{item.get('title', '')} {item.get('topics', '')} {item.get('description', '')}"
    )
    if any(k in text for k in _BEGINNER_KW):
        return 0
    if any(k in text for k in _ADVANCED_KW):
        return 2
    return 1


def suggest_followups(query, category, all_items, mode=None):
    """Gợi ý câu hỏi tiếp theo theo ngữ cảnh — tránh lặp lại đúng ý vừa hỏi."""
    cat = category or (all_items[0]["category"] if all_items else "lĩnh vực này")
    pool = [
        ("learning_path", f"Lộ trình học {cat} từ cơ bản đến nâng cao"),
        ("compare", f"So sánh các khóa học nổi bật về {cat}"),
        ("recommend", f"Gợi ý tài liệu thực hành {cat} cho người mới"),
        ("answer", f"{cat} cần chuẩn bị kiến thức nền nào trước?"),
        ("search", f"Có những khóa học {cat} nào đáng học nhất?"),
    ]
    picks = [q for m, q in pool if m != mode]
    return picks[:3]


def followup_block(query, category, all_items, mode=None):
    qs = suggest_followups(query, category, all_items, mode=mode)
    lines = "\n".join(f"- {q}" for q in qs)
    return f"\n\n---\n### 💡 Có thể bạn muốn hỏi tiếp\n{lines}"


def dedupe_items(items):
    seen = set()
    result = []
    for item in items:
        key = item["item_id"]
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def matched_keywords(query, item, limit=5):
    """Từ khóa trong truy vấn khớp với mục — hiển thị nguyên văn nhưng so khớp cả dạng stem."""
    hay = normalize_text(
        f"{item.get('title', '')} {item.get('topics', '')} "
        f"{item.get('category', '')} {item.get('description', '')}"
    )
    words = [
        w for w in dict.fromkeys(normalize_text(query).split())
        if len(w) > 2 and w not in QUERY_STOP_WORDS
    ]
    hay_tokens = hay.split()
    hits = []
    for w in words:
        if w in hay or (len(w) >= 5 and any(t.startswith(w[:5]) for t in hay_tokens)):
            hits.append(w)
    return hits[:limit]


def grounding_line(query, item):
    """Một dòng 'Vì sao phù hợp' bám sát từ khóa người dùng hỏi."""
    hits = matched_keywords(query, item)
    if not hits:
        return ""
    kws = ", ".join(f"`{k}`" for k in hits)
    return f"\n\n🎯 **Bám sát câu hỏi của bạn** — khớp trực tiếp các từ khóa: {kws}."


def format_sources_inline(items, limit=5):
    lines = []
    for i, item in enumerate(items[:limit], 1):
        score = f" · {item['score']}% phù hợp" if "score" in item else ""
        lines.append(
            f"**{i}. {item['title']}** — {item['type']} · {item['category']}{score}\n"
            f"> {item['description'][:180]}{'...' if len(item['description']) > 180 else ''}\n"
            f"> 👤 {item['instructor']} · 🌐 {item['platform']}"
        )
    return "\n\n".join(lines)


def topics_list(item):
    return [t.strip() for t in str(item.get("topics", "")).split(",") if t.strip()]


def primary_topic(item):
    """Chủ đề chính của mục — dùng để đa dạng hóa lộ trình."""
    tl = topics_list(item)
    return strip_accents(tl[0]) if tl else ""


def dominant_category(sources, top=5):
    """Chuyên mục chiếm đa số trong các nguồn truy hồi đầu bảng.

    Đáng tin hơn đoán theo từ khóa truy vấn: nếu truy hồi ngữ nghĩa trả về toàn mục Machine
    Learning thì chuyên mục đúng là 'Trí tuệ nhân tạo' bất kể câu hỏi diễn đạt thế nào.
    """
    from collections import Counter
    cats = [s["item"].get("category") for s in sources[:top] if s.get("item")]
    cats = [c for c in cats if c]
    if not cats:
        return None
    return Counter(cats).most_common(1)[0][0]


def category_stage_items(item_list, category, level, exclude_ids, k, query=None, diversify=True):
    """Lấy thêm mục ĐÚNG CẤP ĐỘ từ chuyên mục trong catalog để lấp đầy giai đoạn.

    Truy hồi theo độ tương đồng có thể bỏ sót mục nền tảng (vd 'lập trình cơ bản' trả về
    toàn mục nâng cao) nên bổ sung trực tiếp từ data: lọc difficulty_rank == level, ưu tiên
    ĐA DẠNG chủ đề chính (để Giai đoạn 1 không bị trùng vd 4 khóa C mà phủ Python/Java/JS...),
    và ưu tiên mục khớp đúng công nghệ người dùng nêu trước khi đa dạng hóa phần còn lại.
    """
    if not category:
        return []
    q_terms = {strip_accents(t) for t in normalize_text(query).split()} if query else set()

    candidates = []
    for _, row in item_list[item_list["category"] == category].iterrows():
        item = row_to_dict(row)
        if item["item_id"] in exclude_ids or difficulty_rank(item) != level:
            continue
        pt = primary_topic(item)
        hay = strip_accents(normalize_text(f"{item['title']} {item['topics']}"))
        matches_q = bool(q_terms) and (
            any(t in pt for t in q_terms if len(t) > 2)
            or any(t in hay for t in q_terms if len(t) > 2)
        )
        candidates.append((0 if matches_q else 1, pt, item))

    candidates.sort(key=lambda x: x[0])

    picked, seen_topic, leftover = [], set(), []
    for _, pt, item in candidates:
        if diversify and pt and pt in seen_topic:
            leftover.append(item)
            continue
        seen_topic.add(pt)
        picked.append(item)
        if len(picked) >= k:
            return picked
    for item in leftover:
        if len(picked) >= k:
            break
        picked.append(item)
    return picked


def format_item_detailed(item, idx=None, query=None):
    """Khối mô tả chi tiết cho một mục — chỉ dùng dữ liệu thật từ catalog, mô tả không cắt."""
    head = f"{idx}. " if idx is not None else ""
    score = f" · **{item['score']}% phù hợp**" if "score" in item else ""
    lvl = f" · 🎚️ {item['level']}" if item.get("level") else ""
    parts = [f"**{head}{item['title']}**  \n`{item['type']}`{lvl} · 📂 {item['category']}{score}"]

    desc = str(item.get("description", "")).strip()
    if desc:
        parts.append(f"> {desc}")

    tl = topics_list(item)
    if tl:
        parts.append("🧩 **Chủ đề bạn sẽ học:** " + " · ".join(f"`{t}`" for t in tl))

    meta = []
    if item.get("instructor"):
        meta.append(f"👤 {item['instructor']}")
    if item.get("platform"):
        meta.append(f"🌐 {item['platform']}")
    if meta:
        parts.append(" · ".join(meta))

    if query:
        hits = matched_keywords(query, item)
        if hits:
            parts.append("🎯 **Khớp câu hỏi:** " + ", ".join(f"`{k}`" for k in hits))

    if item.get("link"):
        parts.append(f"🔗 [Mở tài nguyên này →]({item['link']})")

    return "\n\n".join(parts)


def format_items_detailed(items, start=1, query=None):
    blocks = [
        format_item_detailed(it, idx=i, query=query)
        for i, it in enumerate(items, start)
    ]
    return "\n\n".join(blocks)


def stage_overview(items):
    """Đoạn markdown tổng hợp số liệu THẬT của riêng các mục trong một giai đoạn (chỉ từ catalog)."""
    if not items:
        return ""
    facts = aggregate_facts(items)
    skills = []
    for it in items:
        for t in topics_list(it):
            if t not in skills:
                skills.append(t)

    lines = [
        f"> 📦 **Tài nguyên giai đoạn:** {facts['courses']} khóa học · {facts['docs']} tài liệu"
    ]
    if facts["platforms"]:
        lines.append(f"> 🌐 **Nền tảng:** {', '.join(facts['platforms'])}")
    if skills:
        lines.append(f"> ✅ **Kỹ năng đạt được:** {', '.join(skills[:8])}")
    return "\n".join(lines)


CATEGORY_CONTEXT = {
    "An ninh mạng": "An ninh mạng (Cybersecurity) là việc bảo vệ hệ thống, mạng và dữ liệu khỏi tấn công. Bạn sẽ đi qua các mảng như bảo mật web, kiểm thử xâm nhập (pentest), mã hóa và phòng thủ hệ thống.",
    "Cơ sở dữ liệu": "Cơ sở dữ liệu là nền tảng lưu trữ và truy vấn dữ liệu của mọi ứng dụng. Lĩnh vực này bao trùm SQL/NoSQL, thiết kế schema, tối ưu truy vấn và quản trị dữ liệu.",
    "Cấu trúc dữ liệu & Giải thuật": "Cấu trúc dữ liệu & Giải thuật (DSA) là tư duy cốt lõi của lập trình hiệu quả và là phần cực kỳ quan trọng khi phỏng vấn. Bạn sẽ học mảng, cây, đồ thị, sắp xếp, tìm kiếm và cách tối ưu độ phức tạp.",
    "DevOps": "DevOps kết nối phát triển và vận hành để giao phần mềm nhanh và ổn định. Trọng tâm gồm CI/CD, container (Docker/Kubernetes), hạ tầng dạng mã (IaC) và giám sát.",
    "Dữ liệu lớn": "Dữ liệu lớn (Big Data) tập trung xử lý khối lượng dữ liệu khổng lồ vượt khả năng công cụ truyền thống. Bạn sẽ tiếp cận Hadoop, Spark, Kafka, data warehouse và xử lý luồng.",
    "Khoa học dữ liệu": "Khoa học dữ liệu biến dữ liệu thô thành hiểu biết và quyết định. Nó kết hợp thống kê, trực quan hóa, xử lý dữ liệu (Pandas) và mô hình hóa.",
    "Khoa học máy tính": "Khoa học máy tính là nền tảng lý thuyết của ngành: hệ điều hành, kiến trúc máy tính, mạng, trình biên dịch và lý thuyết tính toán. Đây là kiến thức gốc giúp bạn hiểu sâu mọi công nghệ phía trên.",
    "Kỹ thuật phần mềm": "Kỹ thuật phần mềm tập trung vào cách xây dựng phần mềm chất lượng, dễ bảo trì ở quy mô lớn. Bạn sẽ học kiến trúc, design pattern (SOLID, MVC), microservices và quy trình phát triển.",
    "Lập trình": "Lập trình là kỹ năng nền tảng để biến ý tưởng thành phần mềm. Phần này giúp bạn nắm vững cú pháp ngôn ngữ, tư duy giải quyết vấn đề và viết code sạch.",
    "Lập trình Mobile": "Lập trình Mobile là phát triển ứng dụng cho điện thoại (iOS, Android). Bạn sẽ tiếp cận Swift/Kotlin hoặc framework đa nền tảng như Flutter, React Native.",
    "Lập trình Web": "Lập trình Web gồm xây dựng giao diện (frontend) và phía máy chủ (backend). Bạn sẽ học HTML/CSS/JS, các framework như React/Vue/Next.js và cách xử lý API, cơ sở dữ liệu.",
    "Phát triển Game": "Phát triển Game kết hợp lập trình, đồ họa và thiết kế trải nghiệm. Trọng tâm gồm engine (Unity/Unreal), vật lý game, gameplay và tối ưu hiệu năng.",
    "Trí tuệ nhân tạo": "Trí tuệ nhân tạo (AI) giúp máy học và ra quyết định từ dữ liệu. Lĩnh vực trải dài machine learning, deep learning, mạng nơ-ron, NLP và các mô hình ngôn ngữ lớn (LLM).",
    "Điện toán đám mây": "Điện toán đám mây cung cấp hạ tầng và dịch vụ qua Internet (AWS, Azure, GCP). Bạn sẽ học triển khai, mở rộng, lưu trữ và kiến trúc hệ thống trên cloud.",
    "Mạng máy tính": "Mạng máy tính là cách các thiết bị kết nối và trao đổi dữ liệu. Bạn sẽ học mô hình TCP/IP/OSI, định tuyến, chuyển mạch, DNS, VPN và xử lý sự cố mạng.",
    "Kiểm thử phần mềm": "Kiểm thử phần mềm đảm bảo chất lượng và độ tin cậy của sản phẩm. Lĩnh vực gồm unit/integration test, tự động hóa (Selenium, Cypress), TDD/BDD và kiểm thử hiệu năng.",
    "Thiết kế UI/UX": "Thiết kế UI/UX tập trung vào trải nghiệm và giao diện người dùng. Bạn sẽ học nghiên cứu người dùng, wireframe, prototype (Figma) và design system.",
    "Blockchain & Web3": "Blockchain & Web3 xây dựng ứng dụng phi tập trung trên sổ cái phân tán. Trọng tâm gồm Ethereum, smart contract (Solidity), DeFi, NFT và DApp.",
    "IoT & Hệ thống nhúng": "IoT & Hệ thống nhúng lập trình cho thiết bị phần cứng và cảm biến. Bạn sẽ làm việc với Arduino, ESP32, MQTT, embedded C và RTOS.",
    "MLOps & AI Engineering": "MLOps đưa mô hình AI/ML vào vận hành thực tế một cách ổn định. Trọng tâm gồm triển khai, giám sát mô hình, CI/CD cho ML, MLflow và LLMOps.",
    "Quản trị hệ thống & Linux": "Quản trị hệ thống & Linux vận hành máy chủ và hạ tầng. Bạn sẽ thành thạo Linux, shell scripting, SSH, Nginx/Apache, ảo hóa và giám sát.",
    "Quản lý dự án CNTT": "Quản lý dự án CNTT điều phối con người và tiến độ để giao sản phẩm. Bạn sẽ học Agile, Scrum, Kanban, quản lý rủi ro và công cụ như Jira.",
    "AR/VR & Thực tế ảo": "AR/VR tạo trải nghiệm thực tế tăng cường và thực tế ảo. Trọng tâm gồm Unity XR, ARKit/ARCore, mô hình 3D và tương tác không gian.",
    "Đồ họa máy tính": "Đồ họa máy tính nghiên cứu cách máy tính tạo và xử lý hình ảnh. Bạn sẽ học OpenGL/Vulkan, shader, rendering, ray tracing và lập trình GPU.",
    "Phân tích nghiệp vụ (BA)": "Phân tích nghiệp vụ là cầu nối giữa nghiệp vụ và kỹ thuật. Bạn sẽ học thu thập yêu cầu, mô hình hóa quy trình (UML/BPMN), use case và viết tài liệu.",
    "Điện toán lượng tử": "Điện toán lượng tử dùng quy luật cơ học lượng tử để tính toán vượt giới hạn máy tính cổ điển. Bạn sẽ tiếp cận qubit, cổng lượng tử, Qiskit và các thuật toán Shor/Grover.",
}

TOPIC_CONTEXT = {
    "machine learning": "Machine Learning dạy máy tự rút quy luật từ dữ liệu thay vì lập trình thủ công từng luật.",
    "deep learning": "Deep Learning dùng mạng nơ-ron nhiều lớp, đặc biệt mạnh với ảnh, ngôn ngữ và dữ liệu phi cấu trúc.",
    "docker": "Docker đóng gói ứng dụng vào container để chạy đồng nhất ở mọi môi trường.",
    "kubernetes": "Kubernetes tự động điều phối và mở rộng hàng loạt container ở quy mô lớn.",
    "react": "React là thư viện UI dạng component được dùng phổ biến nhất cho frontend.",
    "python": "Python dễ học, đa dụng và là ngôn ngữ chủ lực cho AI/ML lẫn khoa học dữ liệu.",
    "javascript": "JavaScript là ngôn ngữ của web, chạy được cả ở trình duyệt lẫn máy chủ (Node.js).",
    "sql": "SQL là ngôn ngữ chuẩn để truy vấn và thao tác dữ liệu quan hệ.",
    "owasp": "OWASP tổng hợp các lỗ hổng bảo mật web phổ biến nhất mà lập trình viên cần phòng tránh.",
    "llm": "LLM (mô hình ngôn ngữ lớn) là nền tảng của các trợ lý AI hiện đại như ChatGPT.",
    "spark": "Apache Spark xử lý dữ liệu lớn song song, nhanh hơn nhiều so với MapReduce truyền thống.",
    "kafka": "Apache Kafka là nền tảng truyền dữ liệu theo luồng (streaming) thời gian thực.",
    "tcp": "TCP/IP là bộ giao thức nền tảng giúp các máy tính giao tiếp qua mạng.",
    "neural network": "Mạng nơ-ron mô phỏng cách não bộ liên kết tín hiệu để học các mẫu phức tạp.",
}

_INTROS = [
    "Câu hỏi rất hay! ",
    "Rất vui được đồng hành cùng bạn. ",
    "Được thôi, để mình gợi ý cho bạn nhé. ",
    "Mình hiểu bạn đang quan tâm chủ đề này. ",
]


def _pick(seq, key):
    return seq[len(str(key)) % len(seq)]


def aggregate_facts(items):
    """Tổng hợp đặc điểm của tập tài nguyên để viết đoạn ngữ cảnh tự nhiên."""
    from collections import Counter

    topic_counter = Counter()
    for it in items:
        for t in str(it.get("topics", "")).split(","):
            t = t.strip()
            if t:
                topic_counter[t] += 1
    courses = sum(1 for i in items if i.get("type") == "Khóa học")
    docs = sum(1 for i in items if i.get("type") == "Tài liệu")
    platforms = []
    for i in items:
        p = i.get("platform")
        if p and p not in platforms:
            platforms.append(p)
    diff = {0: 0, 1: 0, 2: 0}
    for i in items:
        diff[difficulty_rank(i)] += 1
    return {
        "top_topics": [t for t, _ in topic_counter.most_common(5)],
        "courses": courses,
        "docs": docs,
        "platforms": platforms[:4],
        "diff": diff,
    }


def topic_context_snippets(query, items, limit=2):
    hay = strip_accents(query + " " + " ".join(str(i.get("topics", "")) for i in items[:3]))
    out = []
    for key, blurb in TOPIC_CONTEXT.items():
        if key in hay:
            out.append(blurb)
        if len(out) >= limit:
            break
    return out


def build_overview(query, items, category):
    """Bức tranh TÀI NGUYÊN trong catalog (số khóa học/tài liệu, chủ đề, độ trải cấp độ).

    Phần KHÁI NIỆM của lĩnh vực đã tách sang `concept_overview_block` để tránh lặp ngữ cảnh.
    """
    facts = aggregate_facts(items)
    agg = f"Trong catalog mình tìm được **{facts['courses']} khóa học** và **{facts['docs']} tài liệu** liên quan"
    if facts["top_topics"]:
        agg += f", xoay quanh các chủ đề như *{', '.join(facts['top_topics'][:4])}*"
    agg += "."
    spread = facts["diff"]
    if spread[0] and spread[2]:
        agg += " Nội dung trải từ mức nền tảng đến nâng cao nên bạn có thể đi theo lộ trình tăng dần."
    return agg


def concept_overview_block(query, items, category):
    """Khối MỞ ĐẦU mọi câu trả lời IT: khái niệm cốt lõi của từ khóa, trước gợi ý/lộ trình/tìm kiếm
    (yêu cầu sản phẩm). Thứ tự ưu tiên nguồn: glossary (kb.CONCEPTS) > ngữ cảnh lĩnh vực
    (CATEGORY_CONTEXT) > TOPIC_CONTEXT khớp truy vấn. Trả "" nếu không có khái niệm nào.
    """
    keys = kb.safe_concepts(query, limit=4)
    key = keys[0] if keys else None
    parts, title = [], None

    if key:
        c = kb.CONCEPTS[key]
        title = c["name"]
        if c.get("def"):
            parts.append(c["def"])
        cat = c.get("category")
        if cat and cat in CATEGORY_CONTEXT and CATEGORY_CONTEXT[cat] not in parts:
            parts.append(CATEGORY_CONTEXT[cat])
        if c.get("example"):
            parts.append(f"💡 **Ví dụ:** {c['example']}")
        rel = [kb.CONCEPTS[r]["name"] for r in c.get("related", []) if r in kb.CONCEPTS]
        if rel:
            parts.append("🔗 **Khái niệm liên quan:** " + ", ".join(f"*{r}*" for r in rel))
        extra_lines = []
        for k in keys[1:]:
            ce = kb.CONCEPTS[k]
            short = (ce.get("def") or "").split(". ")[0].strip().rstrip(".")
            if short:
                extra_lines.append(f"- **{ce['name']}**: {short}.")
        if extra_lines:
            parts.append("📌 **Các từ khóa khác trong câu hỏi:**\n" + "\n".join(extra_lines))
    else:
        if category and category in CATEGORY_CONTEXT:
            title = category
            parts.append(CATEGORY_CONTEXT[category])
        parts.extend(topic_context_snippets(query, items, limit=2))

    parts = list(dict.fromkeys(p for p in parts if p))
    if not parts:
        return ""
    head = f"## 📖 Khái niệm: {title}\n\n" if title else "## 📖 Khái niệm\n\n"
    return head + "\n\n".join(parts) + "\n\n---\n\n"


def practical_tips(category, all_items):
    """Vài lời khuyên thực hành, có ngữ cảnh theo lĩnh vực."""
    facts = aggregate_facts(all_items)
    tips = []
    if facts["courses"] and facts["docs"]:
        tips.append("Kết hợp **khóa học** (học có hướng dẫn) với **tài liệu** (tra cứu sâu) để hiểu chắc hơn.")
    tips.append("Vừa học vừa làm một **dự án nhỏ** để biến kiến thức thành kỹ năng thực tế.")
    if facts["platforms"]:
        tips.append(f"Các nền tảng đáng tham khảo: {', '.join(facts['platforms'])}.")
    domain_tip = {
        "Trí tuệ nhân tạo": "Nắm vững toán nền (đại số tuyến tính, xác suất) sẽ giúp bạn học AI nhanh hơn rất nhiều.",
        "An ninh mạng": "Luyện tập trên môi trường mô phỏng (CTF, lab) thay vì thử trên hệ thống thật.",
        "Lập trình Web": "Học chắc HTML/CSS/JS trước khi nhảy vào framework để không bị 'hổng gốc'.",
        "DevOps": "Tự dựng một pipeline CI/CD đơn giản là cách học DevOps hiệu quả nhất.",
        "Khoa học dữ liệu": "Thực hành trên bộ dữ liệu thật (Kaggle) để rèn tư duy phân tích.",
        "Cấu trúc dữ liệu & Giải thuật": "Luyện đều trên LeetCode/HackerRank để giải thuật trở thành phản xạ.",
    }.get(category)
    if domain_tip:
        tips.insert(0, domain_tip)
    return "\n".join(f"- {t}" for t in tips[:4])


def synthesize_answer(query, sources, recommendations, mode, category=None, item_list=None):
    """Soạn câu trả lời GIÀU NGỮ CẢNH, bám sát catalog, không cần LLM."""
    if not sources:
        return (
            "Tôi chưa tìm thấy tài nguyên phù hợp trong catalog với câu hỏi này. "
            "Tôi chuyên hỗ trợ các chủ đề **CNTT** (lập trình, web, AI/ML, dữ liệu, "
            "cloud, DevOps, an ninh mạng, mobile...).\n\n"
            "Bạn có thể thử:\n"
            "- Nêu rõ lĩnh vực (VD: *Machine Learning*, *DevOps*, *An ninh mạng*)\n"
            "- Chỉ định loại: *khóa học* hoặc *tài liệu*\n"
            "- Mô tả mục tiêu học tập cụ thể hơn"
        )

    top = sources[0]["item"]
    all_items = dedupe_items([s["item"] for s in sources] + recommendations)
    foot = followup_block(query, category, all_items, mode=mode)
    intro = _pick(_INTROS, query)
    overview = build_overview(query, all_items, category)
    tips = practical_tips(category, all_items)
    tips_block = f"\n\n### 🎯 Lời khuyên cho bạn\n{tips}" if tips else ""

    if mode == "learning_path":
        staged = sorted(enumerate(all_items), key=lambda x: (difficulty_rank(x[1]), x[0]))
        ordered = [it for _, it in staged]
        used = []

        def take(pred, k):
            picked = []
            for it in ordered:
                if it in used:
                    continue
                if pred(it):
                    picked.append(it)
                    used.append(it)
                if len(picked) >= k:
                    break
            return picked

        basics = take(lambda it: difficulty_rank(it) == 0, 3)
        mids = take(lambda it: difficulty_rank(it) == 1, 4)
        adv = take(lambda it: difficulty_rank(it) == 2, 3)

        if item_list is not None and category:
            used_ids = {it["item_id"] for it in used}

            def backfill(stage, level, target):
                need = target - len(stage)
                if need <= 0:
                    return stage
                extra = category_stage_items(
                    item_list, category, level, used_ids, need, query=query
                )
                for it in extra:
                    used_ids.add(it["item_id"])
                return stage + extra

            basics = backfill(basics, 0, 3)
            mids = backfill(mids, 1, 4)
            adv = backfill(adv, 2, 3)

        basics = basics or take(lambda it: True, 3)
        mids = mids or take(lambda it: True, 4)

        def render_stage(emoji, name, subtitle, goal, items, start):
            if not items:
                return "", start
            head = (
                f"\n\n### {emoji} {name}\n"
                f"_{subtitle}_\n\n"
                f"{stage_overview(items)}\n\n"
                f"🎯 **Mục tiêu giai đoạn:** {goal}\n\n"
            )
            body = format_items_detailed(items, start=start, query=query)
            return head + body, start + len(items)

        out = "## 🗺️ Lộ trình học tập"
        if category:
            out += f" — {category}"
        out += f"\n\n{intro}{overview}\n\n"
        n_stages = sum(1 for s in (basics, mids, adv) if s)
        out += (
            f"Dựa trên *\"{query}\"*, mình thiết kế lộ trình **{n_stages} giai đoạn** dưới đây — "
            f"toàn bộ tài nguyên đều lấy trực tiếp từ catalog ({len(all_items)} mục liên quan), "
            "sắp xếp theo độ khó tăng dần để bạn đi từng bước vững chắc. "
            "Mỗi mục kèm mô tả đầy đủ, chủ đề sẽ học và liên kết truy cập:\n"
        )

        idx = 1
        block, idx = render_stage(
            "🟢", "Giai đoạn 1 — Nền tảng",
            "Nắm vững khái niệm cốt lõi trước khi đi sâu.",
            "Hiểu các khái niệm gốc, làm quen công cụ và hoàn thành bài tập cơ bản đầu tiên.",
            basics[:3], idx,
        )
        out += block
        block, idx = render_stage(
            "🟡", "Giai đoạn 2 — Trung cấp & chuyên môn",
            "Thực hành dự án, đi sâu vào kỹ thuật.",
            "Vận dụng kiến thức vào một dự án thực tế, nắm chắc các kỹ thuật cốt lõi của lĩnh vực.",
            mids[:4], idx,
        )
        out += block
        block, idx = render_stage(
            "🔴", "Giai đoạn 3 — Nâng cao & thực chiến",
            "Tối ưu, kiến trúc, triển khai thực tế.",
            "Làm chủ kiến trúc/triển khai ở quy mô lớn và tối ưu hiệu năng cho bài toán thực.",
            adv[:3], idx,
        )
        out += block

        out += tips_block
        out += (
            "\n\n💪 Cứ đi tuần tự từng giai đoạn, hoàn thành một **dự án nhỏ** ở mỗi bước "
            "rồi mới sang giai đoạn sau — đó là cách tiến bộ nhanh và chắc nhất. Chúc bạn học vui!"
        )
        return out + foot

    if mode == "compare":
        picks = all_items[:5]
        out = f"## ⚖️ So sánh tài nguyên liên quan\n\n{intro}{overview}\n\n"
        out += f"Với *\"{query}\"*, dưới đây là các lựa chọn nổi bật để bạn cân nhắc:\n\n"
        out += format_items_detailed(picks, query=query)
        categories = sorted({i["category"] for i in picks})
        courses = [i for i in picks if i["type"] == "Khóa học"]
        docs = [i for i in picks if i["type"] == "Tài liệu"]
        out += "\n\n### 📊 Nên chọn cái nào?\n"
        out += f"- **Phạm vi:** {len(picks)} tài nguyên thuộc {len(categories)} chuyên mục ({', '.join(categories)}).\n"
        out += f"- **Loại hình:** {len(courses)} khóa học, {len(docs)} tài liệu.\n"
        if courses:
            out += f"- **Muốn học có hướng dẫn bài bản** → ưu tiên *{courses[0]['title']}* trên {courses[0]['platform']}.\n"
        if docs:
            out += f"- **Muốn tra cứu nhanh / tự đọc sâu** → chọn *{docs[0]['title']}*.\n"
        out += "- **Người mới** nên bắt đầu từ mục có chữ *cơ bản/nhập môn*; đã có nền thì nhảy thẳng vào mục *nâng cao*.\n"
        out += tips_block
        return out + foot

    if mode == "search":
        out = f"## 🔍 Kết quả tìm kiếm\n\n{intro}{overview}\n\n"
        out += f"Mình tìm thấy **{len(all_items)}** tài nguyên liên quan đến *\"{query}\"*, "
        out += "xếp theo độ phù hợp giảm dần (kèm mô tả đầy đủ, chủ đề và liên kết):\n\n"
        out += format_items_detailed(all_items[:6], query=query)
        out += tips_block
        return out + foot

    if mode == "recommend":
        out = f"## 💡 Gợi ý học tập\n\n{intro}{overview}\n\n"
        out += (
            f"Phù hợp nhất với yêu cầu của bạn là **{top['title']}** "
            f"({top['type']} · {top['category']}) — và đây là lý do mình chọn nó:\n\n"
        )
        out += f"> {top['description'][:280]}{'...' if len(top['description']) > 280 else ''}\n\n"
        out += f"👤 {top['instructor']} · 🌐 {top['platform']}"
        if str(top.get("topics", "")).strip():
            out += f" · 🏷️ {top['topics']}"
        out += grounding_line(query, top)
        out += "\n\n### Một vài lựa chọn liên quan khác\n\n"
        others = [i for i in all_items if i["item_id"] != top["item_id"]]
        out += format_items_detailed(others[:5], query=query)
        out += tips_block
        return out + foot

    out = f"## 💬 Trả lời\n\n{intro}{overview}\n\n"
    out += (
        f"Đi vào câu hỏi *\"{query}\"*: nội dung sát nhất trong catalog là "
        f"**{top['title']}** ({top['type']} · {top['category']}). Cụ thể:\n\n"
    )
    out += f"{top['description']}\n\n"
    out += f"- **Giảng viên/Tác giả:** {top['instructor']}\n"
    out += f"- **Nền tảng:** {top['platform']}\n"
    out += f"- **Chủ đề chính:** {top['topics']}\n"
    out += grounding_line(query, top)

    others = [i for i in all_items[1:] if i["item_id"] != top["item_id"]]
    if others:
        out += "\n### 📚 Tài nguyên liên quan khác\n\n"
        out += format_items_detailed(others[:4], query=query)
    out += tips_block
    return out + foot
