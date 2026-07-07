# Lab 28 - Câu Trả Lời Khi Nộp

## 1. Trade-offs kiến trúc AI platform

Kiến trúc được tách thành local infrastructure và Kaggle GPU để cân bằng chi phí, hiệu năng và khả năng bảo trì. Local Docker Compose chạy Kafka, Prefect, Qdrant, Redis, Prometheus, Grafana và API Gateway để dễ tái lập, debug và demo. Kaggle chỉ xử lý phần nặng như vLLM/embedding, giúp tận dụng GPU mà không làm local stack phụ thuộc vào phần cứng mạnh.

Trade-off chính là độ trễ mạng giữa local và Kaggle. Để đổi lại, hệ thống rẻ hơn, dễ triển khai hơn và có separation rõ ràng: data pipeline, vector store, feature store, serving và monitoring nằm ở các service riêng. Maintainability được ưu tiên bằng cấu trúc thư mục tách biệt, script bootstrap, smoke test và readiness check.

## 2. Xử lý ngắt kết nối Local + Kaggle

API Gateway đọc `VLLM_NGROK_URL` qua biến môi trường. Khi URL chưa được cấu hình, gateway không crash mà trả lời bằng `local-fallback` để health check, metrics và các workflow demo local vẫn chạy được. Khi URL có cấu hình nhưng vLLM timeout hoặc không phản hồi, gateway trả `503 LLM service unavailable` thay vì treo hoặc làm chết process.

Với embedding, script `05_embed_to_qdrant.py` cũng có fallback embedding cố định 384 chiều nếu `EMBED_NGROK_URL` chưa có. Cơ chế này là graceful degradation cho môi trường lab: local vẫn test được pipeline, còn chất lượng câu trả lời sẽ tăng khi Kaggle GPU được nối thật.

## 3. Kafka giúp decouple components như thế nào

Kafka đóng vai trò event bus giữa data ingestion và các bước xử lý downstream. Producer chỉ cần publish record vào topic `data.raw`, không cần biết Prefect flow, Delta Lake, Feast hay Qdrant đang chạy thế nào. Prefect consumer đọc event theo nhịp riêng và ghi ra Delta Lake.

Cách này giảm coupling theo thời gian và theo ownership: ingestion có thể chạy trước, consumer có thể restart sau, và các consumer mới có thể được thêm vào cùng topic để phục vụ indexing, feature generation hoặc audit mà không phải sửa producer.

## 4. Observability đã implement như thế nào

API Gateway dùng `prometheus-fastapi-instrumentator` để expose `/metrics`, Prometheus scrape job `api-gateway`, sau đó Grafana dùng Prometheus làm nguồn dữ liệu để visualize service status/latency/request metrics. Script `production_readiness_check.py` kiểm tra Prometheus, Grafana và metrics endpoint để xác nhận monitoring path hoạt động.

Logs được lấy qua `docker compose logs <service>`. Prefect UI tại `localhost:4200` hiển thị flow/deployment run, trạng thái task và lịch sử pipeline. Trong bản mở rộng production, LangSmith/trace key có thể được cấu hình qua `LANGCHAIN_API_KEY` để trace request LLM end-to-end.

## 5. Khi Qdrant hoặc Kafka crash thì hệ thống xử lý thế nào

Nếu Qdrant crash hoặc collection chưa sẵn sàng, API Gateway bỏ qua vector context và vẫn có thể trả lời bằng LLM hoặc fallback, đồng thời metrics/health vẫn sống để debug. Khi Qdrant quay lại, script bootstrap hoặc embedding script có thể tạo lại collection `documents` và seed dữ liệu demo.

Nếu Kafka crash, ingestion sẽ fail nhanh thay vì silently drop event. Data serving path qua API Gateway vẫn chạy vì nó không phụ thuộc trực tiếp vào Kafka ở request time. Khi Kafka phục hồi, topic `data.raw` được kiểm tra/tạo lại bằng `scripts/00_bootstrap_local.py`, producer có thể gửi lại data, và Prefect flow tiếp tục consume để đồng bộ Delta/Feature Store.
