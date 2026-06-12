# TechNova - Microservices E-Commerce Platform

TechNova is a robust, scalable e-commerce platform built using a microservices architecture. It leverages Django for its core services, RabbitMQ for asynchronous communication, and a variety of databases (PostgreSQL, MySQL, Neo4j) to handle specialized data needs.

## 🏗️ Architecture Overview

The system has been recently refactored to separate the frontend from the API gateway. It consists of the following independent microservices:

| Service | Responsibility | Port | Database / Tech |
| :--- | :--- | :--- | :--- |
| **API Gateway** | Entry point, routing, and reverse proxy (Nginx). | 9000 | Nginx |
| **Frontend Service** | User interface, web views, and main entry point. | 9010 | PostgreSQL (`log_tracking_db`) |
| **User Service** | Manages users, authentication (JWT), and profiles. | 9001 | MySQL (`user_db`) |
| **Order Service** | Handles order creation, status management, and history. | 9002 | PostgreSQL (`order_db`) |
| **Payment Service** | Integrates with payment providers (e.g., VNPay). | 9003 | PostgreSQL (`payment_db`) |
| **Shipment Service** | Manages shipping status and tracking. | 9004 | PostgreSQL (`shipment_db`) |
| **AI Service** | Product recommendations and search using Graph DB & Gemini. | 9005 | Neo4j |
| **Cart Service** | Manages user shopping carts. | 9006 | PostgreSQL (`cart_db`) |
| **Product Service** | Catalog management, inventory, and categories. | 9008 | PostgreSQL (`product_db`) |
| **Review Service** | Product reviews and ratings. | 9009 | PostgreSQL (`review_db`) |

## 🛠️ Technology Stack

- **Framework**: Django, Django REST Framework
- **Proxy**: Nginx (API Gateway)
- **Messaging**: RabbitMQ (Message Broker)
- **Databases**: 
  - **Relational**: PostgreSQL, MySQL
  - **Graph**: Neo4j
- **Containerization**: Docker, Docker Compose
- **AI**: Google Gemini API (for recommendations)

---

## 🚀 Getting Started (Hướng dẫn chạy dự án)

Follow these steps to set up and run the project locally.

### 📋 Prerequisites (Điều kiện tiên quyết)
- **Docker Desktop** installed.
- **PostgreSQL** installed locally (Port 5432).
- **MySQL** installed locally (Port 3306).

### 🛠️ Step 1: Database Setup (Thiết lập Cơ sở dữ liệu)
Since many services connect to `host.docker.internal`, you must create the following databases on your host machine:

**On PostgreSQL (5432):**
- `product_db`, `cart_db`, `order_db`, `payment_db`, `shipment_db`, `log_tracking_db`

**On MySQL (3306):**
- `user_db`

*(Note: `review-service` has its own containerized database and doesn't require manual setup).*

### 🔑 Step 2: Environment Configuration
Check the `.env` file in the root directory. Ensure your `GEMINI_API_KEY` is set if you want to use AI features.

### 🐳 Step 3: Run with Docker Compose
Open your terminal in the root directory and run:

```bash
docker compose up -d
```

This command will build the microservices, start RabbitMQ, Neo4j, and the services in detached mode. It also runs database migrations automatically.

### 🌐 Step 4: Access the Application
- **Main Website (via API Gateway)**: [http://localhost:9000/](http://localhost:9000/)
- **Frontend Service Direct**: [http://localhost:9010/](http://localhost:9010/)
- **RabbitMQ Management**: [http://localhost:15673/](http://localhost:15673/) (Default login: `guest`/`guest`)

### 🔐 Login & Role Access (Đăng nhập theo vai trò)
Hệ thống sử dụng cơ chế đăng nhập tập trung (Unified Login) tại một đường dẫn duy nhất cho tất cả các vai trò. Sau khi đăng nhập thành công, hệ thống tự động kiểm tra và điều hướng người dùng dựa vào vai trò (Role) của tài khoản:

1. **Customer (Khách hàng)**
   - **Link đăng nhập**: [http://localhost:9000/login/](http://localhost:9000/login/)
   - **Sau khi đăng nhập**: Có thể mua sắm, xem giỏ hàng, cập nhật thông tin cá nhân và theo dõi lịch sử đơn hàng.

2. **Staff / Shipper (Nhân viên giao hàng)**
   - **Link đăng nhập**: [http://localhost:9000/login/](http://localhost:9000/login/) (hoặc truy cập trực tiếp `http://localhost:9000/staff-login/`)
   - **Sau khi đăng nhập**: Tự động điều hướng đến **Shipper Dashboard** (`http://localhost:9000/shipper/dashboard/`) để xem danh sách đơn hàng cần giao và cập nhật trạng thái.

3. **Admin (Quản trị viên)**
   - **Link đăng nhập Website**: [http://localhost:9000/login/](http://localhost:9000/login/)
   - **Sau khi đăng nhập**: Tự động điều hướng đến **Admin Dashboard** (`http://localhost:9000/dashboard/`) để quản lý toàn diện (sản phẩm, đơn hàng, khách hàng, nhân viên, v.v.) và xem thống kê kinh doanh.
   - **Trang quản trị hệ thống (Django Admin)**: Dành cho kỹ thuật viên hoặc thao tác dữ liệu thô, truy cập tại [http://localhost:9000/django-admin/](http://localhost:9000/django-admin/).

---

## 💡 Notes
- **Migrations**: On the first run, Django will automatically migrate schemas to your local databases.
- **Service Communication**: Services communicate asynchronously via RabbitMQ exchanges.
- **Port Conflict Fix**: The RabbitMQ host port mapping has been changed to `6672:5672` to avoid Windows Hyper-V port reservation conflicts.
- **Superuser**: To create an admin account for the user service:
  `docker exec -it <user-service-container-id> python user_service/manage.py createsuperuser`
