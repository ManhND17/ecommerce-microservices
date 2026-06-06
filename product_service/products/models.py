from django.db import models


# ── Catalog ───────────────────────────────────────────────────────────────────
class Catalog(models.Model):
    """
    Model đại diện cho danh mục sản phẩm (ví dụ: Sách, Điện tử, Thời trang...).
    """
    name        = models.CharField(max_length=100, help_text="Tên danh mục")
    slug        = models.SlugField(unique=True, help_text="Slug cho URL (ví dụ: sach, dien-tu)")
    description = models.TextField(blank=True, null=True, help_text="Mô tả danh mục")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name        = "Danh mục"
        verbose_name_plural = "Danh mục"


# ── Base Product ──────────────────────────────────────────────────────────────
class Product(models.Model):
    catalog   = models.ForeignKey(
        Catalog, on_delete=models.CASCADE,
        related_name='products', help_text="Danh mục sản phẩm"
    )
    name        = models.CharField(max_length=255, help_text="Tên sản phẩm")
    price       = models.DecimalField(max_digits=12, decimal_places=2, help_text="Giá (VNĐ)")
    stock       = models.IntegerField(default=0, help_text="Số lượng tồn kho")
    description = models.TextField(blank=True, null=True, help_text="Mô tả sản phẩm")
    image_url   = models.URLField(max_length=500, blank=True, null=True, help_text="Link ảnh")

    # Giữ lại để tương thích dữ liệu cũ — sản phẩm mới dùng model con thay thế
    specific_attributes = models.JSONField(
        default=dict, blank=True,
        help_text="[Legacy] Thuộc tính riêng dạng JSON (dành cho dữ liệu cũ)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering            = ['-created_at']
        verbose_name        = "Sản phẩm (base)"
        verbose_name_plural = "Sản phẩm (base)"


# ══════════════════════════════════════════════════════════════════════════════
#  1. SÁCH (Book)
# ══════════════════════════════════════════════════════════════════════════════
class BookProduct(Product):
    author    = models.CharField(max_length=255, help_text="Tác giả")
    isbn      = models.CharField(max_length=20, unique=True, help_text="Mã ISBN")
    publisher = models.CharField(max_length=255, help_text="Nhà xuất bản")
    pages     = models.IntegerField(null=True, blank=True, help_text="Số trang")
    language  = models.CharField(
        max_length=50, blank=True, default='Tiếng Việt',
        help_text="Ngôn ngữ (VD: Tiếng Việt, English)"
    )

    def __str__(self):
        return f"[Sách] {self.name} — {self.author}"

    class Meta:
        verbose_name        = "Sách"
        verbose_name_plural = "Sách"


# ══════════════════════════════════════════════════════════════════════════════
#  2. ĐỒ ĐIỆN TỬ (Electronics) — Cấu trúc 2 tầng
#     ElectronicsProduct (chung) → LaptopProduct / MobileProduct / ...
# ══════════════════════════════════════════════════════════════════════════════
class ElectronicsProduct(Product):
    brand    = models.CharField(max_length=100, help_text="Thương hiệu (VD: Apple, Samsung)")
    warranty = models.IntegerField(default=12, help_text="Bảo hành (tháng)")
    color    = models.CharField(max_length=50, blank=True, default='', help_text="Màu sắc")

    def __str__(self):
        return f"[Điện tử] {self.name} — {self.brand}"

    class Meta:
        verbose_name        = "Điện tử (chung)"
        verbose_name_plural = "Điện tử (chung)"


class LaptopProduct(ElectronicsProduct):
    ram           = models.CharField(max_length=50, help_text="RAM (VD: 8GB, 16GB DDR5)")
    cpu           = models.CharField(max_length=100, help_text="CPU (VD: Intel Core i7-1355U)")
    storage       = models.CharField(max_length=50, help_text="Bộ nhớ (VD: 512GB SSD NVMe)")
    screen_size   = models.CharField(max_length=50, help_text="Màn hình (VD: 15.6 inch Full HD)")
    battery       = models.CharField(max_length=50, blank=True, default='', help_text="Pin (VD: 56Wh, ~8 giờ)")
    os            = models.CharField(max_length=100, blank=True, default='', help_text="Hệ điều hành (VD: Windows 11 Home)")
    weight        = models.CharField(max_length=50, blank=True, default='', help_text="Khối lượng (VD: 1.8kg)")
    graphics_card = models.CharField(max_length=100, blank=True, default='', help_text="Card đồ họa (VD: NVIDIA RTX 4060 8GB)")

    def __str__(self):
        return f"[Laptop] {self.name} — {self.cpu}"

    class Meta:
        verbose_name        = "Laptop"
        verbose_name_plural = "Laptop"


class MobileProduct(ElectronicsProduct):
    ram         = models.CharField(max_length=50, help_text="RAM (VD: 8GB, 12GB)")
    storage     = models.CharField(max_length=50, help_text="Bộ nhớ trong (VD: 128GB, 256GB)")
    screen_size = models.CharField(max_length=50, help_text="Màn hình (VD: 6.7 inch AMOLED)")
    battery     = models.CharField(max_length=50, help_text="Pin (VD: 5000mAh)")
    camera      = models.CharField(max_length=200, blank=True, default='', help_text="Camera (VD: 50MP + 12MP + 10MP)")
    os          = models.CharField(max_length=100, blank=True, default='', help_text="HĐH (VD: Android 14, iOS 17)")
    chip        = models.CharField(max_length=100, blank=True, default='', help_text="Chip xử lý (VD: Snapdragon 8 Gen 3)")
    sim         = models.CharField(max_length=50, blank=True, default='', help_text="SIM (VD: Dual SIM nano)")

    def __str__(self):
        return f"[Mobile] {self.name} — {self.chip}"

    class Meta:
        verbose_name        = "Điện thoại di động"
        verbose_name_plural = "Điện thoại di động"


class RefrigeratorProduct(ElectronicsProduct):
    capacity      = models.CharField(max_length=50, help_text="Dung tích (VD: 320L, 490L)")
    energy_rating = models.CharField(max_length=50, blank=True, default='', help_text="Hiệu suất năng lượng (VD: 5 sao, Inverter)")
    cooling_type  = models.CharField(max_length=100, blank=True, default='', help_text="Công nghệ làm lạnh (VD: No Frost, Multi-Door)")
    dimensions    = models.CharField(max_length=100, blank=True, default='', help_text="Kích thước (VD: 60 x 63.5 x 185.5 cm)")
    doors         = models.IntegerField(null=True, blank=True, help_text="Số cánh tủ (VD: 2, 4)")
    compressor    = models.CharField(max_length=100, blank=True, default='', help_text="Máy nén (VD: Inverter Linear)")

    def __str__(self):
        return f"[Tủ lạnh] {self.name} — {self.capacity}"

    class Meta:
        verbose_name        = "Tủ lạnh"
        verbose_name_plural = "Tủ lạnh"


class TVProduct(ElectronicsProduct):
    screen_size   = models.CharField(max_length=50, help_text="Màn hình (VD: 55 inch, 65 inch)")
    resolution    = models.CharField(max_length=50, help_text="Độ phân giải (VD: 4K UHD, 8K)")
    smart_tv      = models.BooleanField(default=True, help_text="Có phải Smart TV không?")
    panel_type    = models.CharField(max_length=50, blank=True, default='', help_text="Tấm nền (VD: OLED, QLED, IPS, VA)")
    refresh_rate  = models.CharField(max_length=50, blank=True, default='', help_text="Tần số quét (VD: 60Hz, 120Hz)")
    os            = models.CharField(max_length=100, blank=True, default='', help_text="HĐH (VD: WebOS, Tizen, Android TV)")
    hdr_support   = models.CharField(max_length=100, blank=True, default='', help_text="HDR (VD: HDR10+, Dolby Vision)")

    def __str__(self):
        return f"[Tivi] {self.name} — {self.screen_size}"

    class Meta:
        verbose_name        = "Tivi"
        verbose_name_plural = "Tivi"


# ══════════════════════════════════════════════════════════════════════════════
#  3. THỜI TRANG (Fashion)
# ══════════════════════════════════════════════════════════════════════════════
class FashionProduct(Product):
    # JSONField để lưu danh sách (linh hoạt hơn CharField)
    sizes    = models.JSONField(default=list, help_text='Danh sách kích cỡ (VD: ["S","M","L","XL","XXL"])')
    colors   = models.JSONField(default=list, help_text='Danh sách màu sắc (VD: ["Đỏ","Đen","Trắng"])')
    material = models.CharField(max_length=255, blank=True, default='', help_text="Chất liệu (VD: Cotton 100%, Polyester)")
    gender   = models.CharField(
        max_length=10, blank=True, default='unisex',
        choices=[('male', 'Nam'), ('female', 'Nữ'), ('unisex', 'Unisex')],
        help_text="Giới tính phù hợp"
    )
    fashion_type = models.CharField(
        max_length=50, blank=True, default='',
        help_text="Loại sản phẩm (VD: Áo thun, Quần jean, Giày sneaker)"
    )

    def __str__(self):
        return f"[Thời trang] {self.name}"

    class Meta:
        verbose_name        = "Thời trang"
        verbose_name_plural = "Thời trang"
