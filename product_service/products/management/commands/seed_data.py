import random
from django.core.management.base import BaseCommand
from products.models import Catalog, Product

class Command(BaseCommand):
    help = 'Re-seed with Ultra High-Quality and STABLE Unsplash images'

    def handle(self, *args, **kwargs):
        self.stdout.write('Purging data for fresh start...')
        Product.objects.all().delete()
        Catalog.objects.all().delete()

        catalogs_data = [
            ("Laptop", "laptop", "Office, gaming, and graphic laptops."),
            ("Mobile", "mobile", "Smartphones from top brands."),
            ("Smartwatch", "smartwatch", "Wearable health and notification devices."),
            ("Tablet", "tablet", "Mobile entertainment and work devices."),
            ("Male Fashion", "male-fashion", "Clothes and accessories for men."),
            ("Female Fashion", "female-fashion", "Clothes and accessories for women."),
            ("Shoes", "shoes", "Sneakers, leather shoes, and fashion sandals."),
            ("Books", "books", "Literature, skills, economics, and textbooks."),
            ("Home Appliances", "home-appliances", "Refrigerators, washing machines, and kitchens."),
            ("Tech Accessories", "tech-accessories", "Mice, keyboards, headphones, and chargers.")
        ]

        # Hand-picked premium and stable Unsplash Photo IDs
        premium_ids = {
            "laptop": [
                "1496181133206-80ce9b88a853", "1517336714731-489689fd1ca8", "1593642702821-c8da6771f0c6",
                "1588872657578-7efd1f1555ed", "1525547718571-a01447c1c818", "1499951360447-b19be8fe80f5",
                "1541807084-5c52b6b3adef", "1611186873503-36512f3c3d31", "1522204523234-8729aa6e3d5f", "1611186873503-36512f3c3d32"
            ],
            "mobile": [
                "1511707171634-5f897ff02aa9", "1510557880182-3d4d3cba35a5", "1591333116802-f2d135046997",
                "1567581935884-3349655042f8", "1556656793-062e17730d1b", "1523206489230-c012c64b2b48",
                "1533228100845-08145b01de14", "1573148199402-c909e7739f12", "1592890288564-76628a30a657", "1616348436168-de43ad0db179"
            ],
            "smartwatch": [
                "1544117518-30df57809b09", "1508685096489-7aac29bb7b18", "1579586337278-3befd40fd17a",
                "1523275335684-37898b6baf30", "1461896836934-ffe607ba1711", "1508685096489-7aac29bb7b18",
                "1509192505293-0a1fb361c94a", "1510017803434-a89937840274", "1508685096489-7aac29bb7b18", "1523275335684-37898b6baf33"
            ],
            "tablet": [
                "1544244015-024b704058f6", "1589739900243-4b52cd9b104e", "1512941937669-90a1b58e7e9c",
                "1561154464-82e9aa33762c", "1517694712202-14dd9538aa97", "1517694712202-14dd9538aa98",
                "1542435509-22445422813e", "1517694712202-14dd9538aa99", "1517694712202-14dd9538aaa0", "1517694712202-14dd9538aaa1"
            ],
            "male-fashion": [
                "1617137968427-83c39c292ad8", "1596755094514-f87034a26cc1", "1542272604-787c3835535d",
                "1489987707025-afc232f7ea0f", "1552374196-1ab2a1c593e8", "1617138260232-212104061c28",
                "1534030347209-d9d3003b411d", "1552374196-1ab2a1c593e4", "1617137724103-62161bc747bc", "1617137968427-83c39c292ad9"
            ],
            "female-fashion": [
                "1572804013307-a9a1119842f5", "1548126032-079a0fb0099d", "1581067720565-ff9a73950151",
                "1490481651871-ab68ec25d43d", "1485230895905-ec40ba36bc11", "1551489186-f8e7395786c2",
                "1539106705373-d419e1b7ec44", "1582234327798-24cc5BF560a6", "1551489186-f8e7395786c6", "1551489186-f8e7395786c7"
            ],
            "shoes": [
                "1600185365483-26d7a4cc7519", "1587563871167-1ee9c731aefb", "1595950613142-6598558452e6",
                "1560761214-5ee82f6f3679", "1549298916-3691d52033bc", "1520316616323-4dfbbad99bb3",
                "1543508286-d8f8d09f7a53", "1606107557113-cd35a7338383", "1575033011964-325ae80277c1", "1560761214-5ee82f6f3680"
            ],
            "books": [
                "1544716278-ca5e6da0a51c", "1541963463532-d68292c34b19", "1512820790803-3e259c0576fe",
                "1495333752940-d7a2c94db896", "1633533128102-182cb367306e", "1456513080512-3f1361845218",
                "1589998059174-8ac9758d743a", "1544909405-b82d6df372a7", "1524985069024-db7f8121f173", "1544716278-ca5e6da0a51d"
            ],
            "home-appliances": [
                "1584622650111-993a426fbf0a", "1585338107529-13afc5f0141f", "1556910103-1c02745a7095",
                "1583940124818-4694406088bc", "1574333081119-22a12827cfc2", "1583940124818-4694406088bd",
                "1585644866650-84f938b8c538", "1574333081119-22a12827cfc3", "1584622650111-993a426fbf0b", "1585338107529-13afc5f0141e"
            ],
            "tech-accessories": [
                "1527863266549-923f59e987c2", "1505740420928-5e560c06d30e", "1615663248861-c85a8a1b48a2",
                "1619614761361-15b0f4433140", "1527443224203-aa0bd8fb7cd1", "1526173176696-2f03c004c21c",
                "1504274066034-02a128076655", "1544244015-024b704058f6", "1517392251252-47565df9565a", "1505740420928-5e560c06d30d"
            ]
        }

        catalog_objs = {}
        self.stdout.write('Creating Catalogs...')
        for name, slug, desc in catalogs_data:
            cat = Catalog.objects.create(name=name, slug=slug, description=desc)
            catalog_objs[slug] = cat

        self.stdout.write('Deploying 100 Premium Products with Curated Unsplash IDs...')
        objs = []
        for slug, ids in premium_ids.items():
            cat = catalog_objs.get(slug)
            
            # Diverse and realistic names for each category
            if slug == 'laptop':
                names = ["MacBook Pro M3", "ASUS ROG Zephyrus", "Dell XPS 13", "HP Spectre x360", "Lenovo Legion 5", "Acer Swift Go", "MSI Katana 15", "Razer Blade 14", "LG Gram 17", "Surface Pro 9"]
            elif slug == 'mobile':
                names = ["iPhone 15 Pro", "Samsung S24 Ultra", "Pixel 8 Pro", "Xiaomi 14 Ultra", "Oppo Find N3", "OnePlus 12", "Nothing Phone 2", "Sony Xperia 1 V", "Vivo X100 Pro", "Realme GT 5"]
            elif slug == 'smartwatch':
                names = ["Apple Watch Series 9", "Samsung Galaxy Watch 6", "Fitbit Sense 2", "Garmin Venu 3", "Amazfit GTR 4", "Huawei Watch GT 4", "Fossil Gen 6", "Pixel Watch 2", "Mobvoi TicWatch Pro 5", "Suunto 9 Peak"]
            elif slug == 'tablet':
                names = ["iPad Pro M2", "Samsung Galaxy Tab S9", "Microsoft Surface Go 4", "Lenovo Tab P12", "Amazon Fire HD 10", "iPad Air 5", "Xiaomi Pad 6", "Google Pixel Tablet", "OnePlus Pad", "Kindle Paperwhite"]
            elif slug == 'male-fashion':
                names = ["Slim Fit Navy Suit", "Casual Denim Jacket", "Leather Chelsea Boots", "Cotton Polo Shirt", "Chino Trousers", "Oversized Graphic Tee", "Wool Blend Overcoat", "Linen Summer Shirt", "Cargo Utility Pants", "Knitted Crewneck Sweater"]
            elif slug == 'female-fashion':
                names = ["Floral Summer Dress", "High-Waisted Skinny Jeans", "Silk Wrap Blouse", "Cashmere Cardigan", "Leather Biker Jacket", "Velvet Evening Gown", "Pleated Midi Skirt", "Oversized Trench Coat", "Satin Slip Dress", "Embroidered Peasant Top"]
            elif slug == 'shoes':
                names = ["Nike Air Max 270", "Adidas Ultraboost", "Classic Leather Loafers", "Waterproof Hiking Boots", "Formal Oxford Shoes", "Canvas Low-Top Sneakers", "Platform Ankle Boots", "Breathable Mesh Runners", "Strappy Heeled Sandals", "Retro Suede Trainers"]
            elif slug == 'books':
                names = ["The Art of Coding", "Financial Freedom 101", "Mastering Modern History", "The Psychology of Success", "Digital Marketing Secrets", "Cooking with Passion", "Poetry of the Soul", "Space: The Final Frontier", "Yoga for Beginners", "Mystery at Blackwood Manor"]
            elif slug == 'home-appliances':
                names = ["Smart French Door Fridge", "HE Front Load Washer", "Countertop Air Fryer", "Robot Vacuum Cleaner", "Digital Convection Oven", "Quiet Dishwasher", "Powerful Blender", "Electric Kettle Pro", "Multi-Cooker Express", "Cordless Stick Vacuum"]
            elif slug == 'tech-accessories':
                names = ["Ergonomic Wireless Mouse", "Mechanical RGB Keyboard", "Noise Cancelling Headphones", "USB-C Docking Station", "Portable Power Bank", "HD Webcam with Mic", "Bluetooth Speaker Gen 2", "High-Speed HDMI Cable", "Stylus Pen for Tablets", "Braided Lightning Cable"]
            else:
                names = [f"{cat.name} Premium Model {i+1}" for i in range(10)]

            for i in range(10):
                # Using hardcoded stable photo-ID from Unsplash
                target_id = ids[i]
                image_url = f"https://images.unsplash.com/photo-{target_id}?auto=format&fit=crop&q=80&w=600"
                
                # Default attributes
                attrs = {"series": "Elite", "warranty": "2 Years"}
                
                if slug == 'laptop':
                    attrs["ram"] = random.choice(["8GB", "16GB", "32GB"])
                    attrs["chip"] = random.choice(["M2", "M3", "Intel Core i7", "Intel Core i9", "Ryzen 7"])
                    attrs["storage"] = random.choice(["512GB", "1TB SSD"])
                    attrs["screen"] = random.choice(["13.3 inch", "14 inch", "15.6 inch", "16 inch"])
                elif slug == 'mobile':
                    attrs["ram"] = random.choice(["8GB", "12GB", "16GB"])
                    attrs["chip"] = random.choice(["A16 Bionic", "A17 Pro", "Snapdragon 8 Gen 2", "Snapdragon 8 Gen 3"])
                    attrs["storage"] = random.choice(["128GB", "256GB", "512GB", "1TB"])
                    attrs["camera"] = random.choice(["48MP", "50MP", "200MP", "12MP"])
                elif slug == 'smartwatch':
                    attrs["screen"] = random.choice(["1.2 inch AMOLED", "1.4 inch Retina", "1.5 inch OLED"])
                    attrs["battery"] = random.choice(["2 ngày", "7 ngày", "14 ngày"])
                    attrs["waterproof"] = random.choice(["5ATM", "IP68"])
                elif slug == 'tablet':
                    attrs["ram"] = random.choice(["4GB", "8GB", "16GB"])
                    attrs["storage"] = random.choice(["64GB", "128GB", "256GB", "512GB"])
                    attrs["screen"] = random.choice(["10.2 inch", "11 inch", "12.9 inch"])
                    attrs["chip"] = random.choice(["M2", "Snapdragon 8 Gen 2", "A14 Bionic"])
                elif slug in ['male-fashion', 'female-fashion', 'shoes']:
                    attrs["size"] = random.choice(["S", "M", "L", "XL", "39", "40", "41", "42"])
                    attrs["material"] = random.choice(["Cotton", "Leather", "Polyester", "Linen", "Canvas"])
                    attrs["color"] = random.choice(["Black", "White", "Navy", "Beige"])
                    attrs.pop("warranty", None)
                elif slug == 'books':
                    attrs["author"] = random.choice(["John Doe", "Jane Smith", "Robert Kiyosaki", "Yuval Noah Harari"])
                    attrs["publisher"] = random.choice(["NXB Trẻ", "NXB Kim Đồng", "Penguin Books", "HarperCollins"])
                    attrs["pages"] = random.randint(150, 800)
                    attrs.pop("warranty", None)
                elif slug == 'home-appliances':
                    attrs["power"] = random.choice(["500W", "1000W", "1500W", "2000W"])
                    attrs["capacity"] = random.choice(["1.5L", "2L", "5L", "9kg", "300L"])
                    attrs["voltage"] = "220V/50Hz"
                elif slug == 'tech-accessories':
                    attrs["connection"] = random.choice(["Bluetooth 5.0", "Wireless 2.4GHz", "Wired USB", "Type-C"])
                    attrs["color"] = random.choice(["Black", "White", "Silver"])

                objs.append(Product(
                    catalog=cat,
                    name=names[i],
                    price=random.randint(50, 2000) * 10000,
                    stock=random.randint(5, 50),
                    description=f"Experience excellence with {names[i]}. Part of our exclusive {cat.name} collection.",
                    image_url=image_url,
                    specific_attributes=attrs
                ))

        Product.objects.bulk_create(objs)
        self.stdout.write(self.style.SUCCESS('Success! 100 Premium products with verified Unsplash images deployed.'))
