# TechNova - Microservices E-Commerce Platform

TechNova is a robust, scalable e-commerce platform built using a microservices architecture. It leverages Django for its core services, RabbitMQ for asynchronous communication, and a variety of databases (PostgreSQL, MySQL, Neo4j) to handle specialized data needs.

## 🏗️ Architecture Overview

The system consists of several independent microservices:

| Service | Responsibility | Port | Database |
| :--- | :--- | :--- | :--- |
| **API Gateway** | Entry point, authentication, routing, and log tracking. | 9000 | PostgreSQL (`log_tracking_db`) |
| **User Service** | Manages users, authentication (JWT), and profiles. | 9001 | MySQL (`user_db`) |
| **Order Service** | Handles order creation, status management, and history. | 9002 | PostgreSQL (`order_db`) |
| **Payment Service** | Integrates with payment providers (e.g., VNPay). | 9003 | PostgreSQL (`payment_db`) |
| **Shipment Service** | Manages shipping status and tracking. | 9004 | PostgreSQL (`shipment_db`) |
| **AI Service** | Product recommendations and search using Graph DB & Gemini. | 9005 | Neo4j |
| **Cart Service** | Manages user shopping carts. | 9006 | PostgreSQL (`cart_db`) |
| **Behavior Service** | Tracks user interactions for analytics. | 9007 | PostgreSQL (`behavior_db`) |
| **Product Service** | Catalog management, inventory, and categories. | 9008 | PostgreSQL (`product_db`) |
| **Review Service** | Product reviews and ratings. | 9009 | PostgreSQL (`review_db`) |

## 🛠️ Technology Stack

- **Framework**: Django, Django REST Framework
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
- `product_db`, `cart_db`, `order_db`, `payment_db`, `shipment_db`, `behavior_db`, `log_tracking_db`

**On MySQL (3306):**
- `user_db`

*(Note: `review-service` has its own containerized database and doesn't require manual setup).*

### 🔑 Step 2: Environment Configuration
Check the `.env` file in the root directory. Ensure your `GEMINI_API_KEY` is set if you want to use AI features.

### 🐳 Step 3: Run with Docker Compose
Open your terminal in the root directory and run:

```bash
docker-compose up --build
```

This command will build the microservices, start RabbitMQ, Neo4j, and the services. It also runs database migrations automatically.

### 🌐 Step 4: Access the Application
- **Admin Dashboard**: [http://localhost:9000/dashboard/](http://localhost:9000/dashboard/)
- **API Gateway**: [http://localhost:9000/](http://localhost:9000/)
- **RabbitMQ Management**: [http://localhost:15673/](http://localhost:15673/) (Default login: `guest`/`guest`)

---

## 💡 Notes
- **Migrations**: On the first run, Django will automatically migrate schemas to your local databases.
- **Service Communication**: Services communicate asynchronously via RabbitMQ exchanges.
- **Superuser**: To create an admin account for the user service:
  `docker exec -it <user-service-container-id> python user_service/manage.py createsuperuser`
