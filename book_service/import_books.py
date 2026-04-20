import os
import django

# Setup environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'book_service.settings')
django.setup()

from books.models import Book

def run():
    books_data = [
        {
            "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
            "author": "Robert C. Martin",
            "description": "Clean Code is divided into three parts. The first describes the principles, patterns, and practices of writing clean code. The second part consists of several case studies of increasing complexity. The third part is the payoff: a single chapter containing a list of heuristics and 'smells' gathered while creating the case studies.",
            "price": "450000.00",
            "stock": 100,
            "category": "IT",
            "image_url": "https://m.media-amazon.com/images/I/41xShlnTZTL._SX376_BO1,204,203,200_.jpg",
        },
        {
            "title": "Đắc Nhân Tâm",
            "author": "Dale Carnegie",
            "description": "Cuốn sách nghệ thuật thu phục lòng người bán chạy nhất mọi thời đại.",
            "price": "120000.00",
            "stock": 50,
            "category": "Văn học",
            "image_url": "https://salt.tikicdn.com/cache/w1200/ts/product/bc/dc/18/84224ee31bfe611aed8ca31ffec9f4fa.jpg",
        },
        {
            "title": "Nhà Giả Kim",
            "author": "Paulo Coelho",
            "description": "Mọi giấc mơ đều có thể trở thành hiện thực nếu ta đủ quyết tâm theo đuổi nó.",
            "price": "90000.00",
            "stock": 150,
            "category": "Tiểu thuyết",
            "image_url": "https://salt.tikicdn.com/cache/w1200/ts/product/5e/18/24/2a6154ba08df6ce6161c13f4303fa19e.jpg",
        },
        {
            "title": "Design Patterns: Elements of Reusable Object-Oriented Software",
            "author": "Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides",
            "description": "The quintessential book on design patterns.",
            "price": "550000.00",
            "stock": 30,
            "category": "IT",
            "image_url": "https://images-na.ssl-images-amazon.com/images/I/81GtLyjgwkL.jpg",
        },
        {
            "title": "Sapiens: Lược Sử Loài Người",
            "author": "Yuval Noah Harari",
            "description": "Khoa học, lịch sử và sự tiến hóa của loài người qua các kỷ nguyên.",
            "price": "200000.00",
            "stock": 25,
            "category": "Khoa học - Lịch sử",
            "image_url": "https://salt.tikicdn.com/cache/w1200/ts/product/bf/fb/8e/31ccff7fb1604a8b7dd55743a6d71cb9.jpg",
        }
    ]

    for data in books_data:
        book, created = Book.objects.get_or_create(
            title=data['title'],
            defaults=data
        )
        if created:
            print(f"Created book: {book.title}")
        else:
            print(f"Book already exists: {book.title}")
            
    print(f"Total books in DB: {Book.objects.count()}")

if __name__ == '__main__':
    run()
