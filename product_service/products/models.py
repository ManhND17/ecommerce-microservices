from django.db import models

class Catalog(models.Model):
    """
    Model đại diện cho danh mục sản phẩm (ví dụ: Laptop, Mobile, Sách...).
    """
    name = models.CharField(max_length=100, help_text="Tên danh mục")
    slug = models.SlugField(unique=True, help_text="Slug cho URL (ví dụ: laptop, dien-thoai)")
    description = models.TextField(blank=True, null=True, help_text="Mô tả danh mục")

    def __str__(self):
        return self.name

class Product(models.Model):
    """
    Model đại diện cho sản phẩm. Liên kết tới Catalog qua ForeignKey.
    Sử dụng JSONField để lưu các thuộc tính riêng biệt.
    """
    catalog = models.ForeignKey(
        Catalog, 
        on_delete=models.CASCADE, 
        related_name='products',
        help_text="Danh mục mà sản phẩm này thuộc về"
    )
    name = models.CharField(max_length=255, help_text="Tên sản phẩm")
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Giá sản phẩm")
    stock = models.IntegerField(default=0, help_text="Số lượng tồn kho")
    description = models.TextField(blank=True, null=True, help_text="Mô tả sản phẩm")
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="Link ảnh sản phẩm")
    
    # JSONField để lưu các thuộc tính riêng của từng loại (RAM, Tác giả, v.v.)
    specific_attributes = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Cấu hình riêng của sản phẩm dạng JSON"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
