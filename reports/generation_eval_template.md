# Đánh giá chất lượng GENERATION (chatbot RAG)
*Mode: **template** — bộ tổng hợp template KHÔNG dùng LLM (offline).*
*Các số GROUNDEDNESS / RELEVANCY là XẤP XỈ rule-based (n-gram, token-overlap); HALLUCINATION + CITATION ACCURACY là đo TRỰC TIẾP trên ID nguồn (không xấp xỉ).*

- **Citation**: 0 mã cite trong 50 câu trả lời; valid = nan% | in-context = nan% (tính khi có cite)
- **Hallucination rate** (câu có >=1 cite không có thật): 0.0% (0/50)
- **Groundedness proxy** (n-gram trúng nguồn): 0.385
- **Relevancy proxy**: 0.929
- **Refusal với câu NGOÀI chủ đề**: 0/21 = 0.0%
- Câu hỏi IT bị từ chối NHẦM (false refusal): 0 / 29 (càng thấp càng tốt)

| query | is_offtopic | intent | cites | valid% | in-ctx% | halluc | grounded | refusal |
|---|---|---|---|---|---|---|---|---|
| Docker là gì và dùng để làm gì? | 0 | definition | 0 | - | - | 0 | 0.42 | 0 |
| Khoa học dữ liệu nên học gì trước cho ngườ | 0 | recommend | 0 | - | - | 0 | 0.39 | 0 |
| Linux cron job hoạt động thế nào? | 0 | definition | 0 | - | - | 0 | 0.46 | 0 |
| SQL JOIN có mấy loại và khác nhau thế nào? | 0 | comparison | 0 | - | - | 0 | 0.56 | 0 |
| An ninh mạng học lộ trình thế nào cho ngườ | 0 | career_path | 0 | - | - | 0 | 0.48 | 0 |
| Python với Java khác nhau ra sao khi chọn  | 0 | comparison | 0 | - | - | 0 | 0.43 | 0 |
| React state hook hoạt động thế nào? | 0 | definition | 0 | - | - | 0 | 0.45 | 0 |
| Git merge với rebase khác gì nhau? | 0 | answer | 0 | - | - | 0 | 0.31 | 0 |
| Kubernetes triển khai microservices cần bi | 0 | answer | 0 | - | - | 0 | 0.34 | 0 |
| Thread và process trong hệ điều hành khác  | 0 | comparison | 0 | - | - | 0 | 0.47 | 0 |
| Machine Learning loss function là gì? | 0 | definition | 0 | - | - | 0 | 0.43 | 0 |
| Học HTML CSS tuần đầu nên làm gì? | 0 | answer | 0 | - | - | 0 | 0.34 | 0 |
| TCP và UDP trong mạng máy tính khác gì nha | 0 | comparison | 0 | - | - | 0 | 0.50 | 0 |
| Pentest (kiểm thử xâm nhập) bắt đầu chuẩn  | 0 | answer | 0 | - | - | 0 | 0.32 | 0 |
| NLP pipeline cơ bản gồm những bước nào? | 0 | learning_path | 0 | - | - | 0 | 0.31 | 0 |
| Phân tích dữ liệu bằng Excel nên học từ đâ | 0 | career_path | 0 | - | - | 0 | 0.45 | 0 |
| Làm sao học AWS cho quản trị hệ thống hiệu | 0 | answer | 0 | - | - | 0 | 0.34 | 0 |
| Khi nào nên dùng NoSQL và cần lưu ý gì? | 0 | definition | 0 | - | - | 0 | 0.44 | 0 |
| Học computer vision cho người mới nên bắt  | 0 | answer | 0 | - | - | 0 | 0.37 | 0 |
| Soft skill nào quan trọng cho software eng | 0 | answer | 0 | - | - | 0 | 0.38 | 0 |
| Sự khác biệt giữa TensorFlow và PyTorch? | 0 | answer | 0 | - | - | 0 | 0.34 | 0 |
| Cách thiết kế API REST an toàn và rõ ràng? | 0 | answer | 0 | - | - | 0 | 0.34 | 0 |
| Học lập trình mobile nên chọn Android hay  | 0 | answer | 0 | - | - | 0 | 0.35 | 0 |
| Vì sao DevOps giúp triển khai phần mềm nha | 0 | definition | 0 | - | - | 0 | 0.39 | 0 |
| Hướng dẫn tự học Python từ con số không? | 0 | answer | 0 | - | - | 0 | 0.36 | 0 |
| Cách viết CV xin việc IT cho fresher? | 0 | answer | 0 | - | - | 0 | 0.38 | 0 |
| Cloud computing có mấy loại dịch vụ chính? | 0 | answer | 0 | - | - | 0 | 0.33 | 0 |
| MongoDB và PostgreSQL nên chọn loại nào? | 0 | answer | 0 | - | - | 0 | 0.32 | 0 |
| Kiểm thử phần mềm unit test nên làm thế nà | 0 | answer | 0 | - | - | 0 | 0.33 | 0 |
| Nấu cháo gà sao cho đậm đà và không bị chá | 1 | answer | 0 | - | - | 0 | 0.40 | 0 |
| Đội tuyển bóng đá Việt Nam giao hữu gần đâ | 1 | answer | 0 | - | - | 0 | 0.38 | 0 |
| Cách chọn táo nhập khẩu sạch và an toàn ch | 1 | answer | 0 | - | - | 0 | 0.39 | 0 |
| Du lịch Đà Nẵng nên đi mùa nào là lý tưởng | 1 | answer | 0 | - | - | 0 | 0.37 | 0 |
| Cảm cúm nên uống thuốc gì và ăn gì cho nha | 1 | answer | 0 | - | - | 0 | 0.37 | 0 |
| Chính trị đảng Mỹ vận hành thế nào cho ngư | 1 | answer | 0 | - | - | 0 | 0.39 | 0 |
| Hướng dẫn nuôi cá vàng sinh sống được vài  | 1 | answer | 0 | - | - | 0 | 0.37 | 0 |
| Chứng khoán Việt Nam nên đầu tư thời điểm  | 1 | answer | 0 | - | - | 0 | 0.35 | 0 |
| Lời bài hát về tình yêu đã xa cảm động? | 1 | answer | 0 | - | - | 0 | 0.37 | 0 |
| Cách vượt khỏi khủng hoảng tình cảm sau ch | 1 | answer | 0 | - | - | 0 | 0.35 | 0 |
| Dinh dưỡng áp dụng cho con 7 tháng cần bổ  | 1 | answer | 0 | - | - | 0 | 0.38 | 0 |
| Quy định giao thông đường bộ mới nhất về đ | 1 | answer | 0 | - | - | 0 | 0.39 | 0 |
| Cách học toán hình học lớp 10 thích thú th | 1 | answer | 0 | - | - | 0 | 0.40 | 0 |
| Nên trồng cây gì trong phòng giúp không kh | 1 | answer | 0 | - | - | 0 | 0.33 | 0 |
| Xu hướng thời trang thu đông cho nam giới? | 1 | answer | 0 | - | - | 0 | 0.39 | 0 |
| Cách pha cà phê muối ngon đúng chuẩn? | 1 | answer | 0 | - | - | 0 | 0.38 | 0 |
| Đạo nhảy hiện đại của Kpop học ở đâu? | 1 | answer | 0 | - | - | 0 | 0.37 | 0 |
| Cách làm mì Ý sốt bò bằm chuẩn vị? | 1 | answer | 0 | - | - | 0 | 0.37 | 0 |
| Mở tiệm trà sữa nên vốn bao nhiêu cho khởi | 1 | answer | 0 | - | - | 0 | 0.42 | 0 |
| Chăm sóc chó con 2 tháng tuổi cần biết gì? | 1 | answer | 0 | - | - | 0 | 0.34 | 0 |
| Yoga buổi sáng cho người cao tuổi nên tập  | 1 | answer | 0 | - | - | 0 | 0.41 | 0 |