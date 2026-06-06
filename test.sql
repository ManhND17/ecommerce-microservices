CREATE TABLE catalog (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);
CREATE TABLE product (
    id SERIAL PRIMARY KEY,
    catalog_id INT REFERENCES catalog(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    stock INT DEFAULT 0,
    description TEXT,
    image_url VARCHAR(500),
    specific_attributes JSONB DEFAULT '{}', -- Lưu linh hoạt các thuộc tính JSON cũ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- 1. SÁCH
CREATE TABLE book_product (
    product_ptr_id INT PRIMARY KEY REFERENCES product(id) ON DELETE CASCADE,
    author VARCHAR(255),
    isbn VARCHAR(20) UNIQUE NOT NULL,
    publisher VARCHAR(255),
    pages INT,
    language VARCHAR(50) DEFAULT 'Tiếng Việt'
);
-- 2. ĐIỆN TỬ (Bảng cha cho các thiết bị điện tử)
CREATE TABLE electronics_product (
    product_ptr_id INT PRIMARY KEY REFERENCES product(id) ON DELETE CASCADE,
    brand VARCHAR(100),
    warranty INT DEFAULT 12,
    color VARCHAR(50)
);
-- 2.1 LAPTOP
CREATE TABLE laptop_product (
    electronicsproduct_ptr_id INT PRIMARY KEY REFERENCES electronics_product(product_ptr_id) ON DELETE CASCADE,
    ram VARCHAR(50),
    cpu VARCHAR(100),
    storage VARCHAR(50),
    screen_size VARCHAR(50),
    battery VARCHAR(50),
    os VARCHAR(100),
    weight VARCHAR(50),
    graphics_card VARCHAR(100)
);
-- 2.2 ĐIỆN THOẠI DI ĐỘNG
CREATE TABLE mobile_product (
    electronicsproduct_ptr_id INT PRIMARY KEY REFERENCES electronics_product(product_ptr_id) ON DELETE CASCADE,
    ram VARCHAR(50),
    storage VARCHAR(50),
    screen_size VARCHAR(50),
    battery VARCHAR(50),
    camera VARCHAR(200),
    os VARCHAR(100),
    chip VARCHAR(100),
    sim VARCHAR(50)
);
-- 2.3 TỦ LẠNH
CREATE TABLE refrigerator_product (
    electronicsproduct_ptr_id INT PRIMARY KEY REFERENCES electronics_product(product_ptr_id) ON DELETE CASCADE,
    capacity VARCHAR(50),
    energy_rating VARCHAR(50),
    cooling_type VARCHAR(100),
    dimensions VARCHAR(100),
    doors INT,
    compressor VARCHAR(100)
);
-- 2.4 TIVI
CREATE TABLE tv_product (
    electronicsproduct_ptr_id INT PRIMARY KEY REFERENCES electronics_product(product_ptr_id) ON DELETE CASCADE,
    screen_size VARCHAR(50),
    resolution VARCHAR(50),
    smart_tv BOOLEAN DEFAULT TRUE,
    panel_type VARCHAR(50),
    refresh_rate VARCHAR(50),
    os VARCHAR(100),
    hdr_support VARCHAR(100)
);
-- 3. THỜI TRANG
CREATE TABLE fashion_product (
    product_ptr_id INT PRIMARY KEY REFERENCES product(id) ON DELETE CASCADE,
    sizes JSONB,    -- VD: ["S", "M", "L"]
    colors JSONB,   -- VD: ["Đỏ", "Xanh"]
    material VARCHAR(255),
    gender VARCHAR(10) DEFAULT 'unisex', -- male, female, unisex
    fashion_type VARCHAR(50)
);