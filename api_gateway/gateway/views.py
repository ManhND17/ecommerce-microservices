import concurrent.futures
import requests
from django.shortcuts import render, redirect
from django.contrib import messages

# Service URLs
CUSTOMER_SERVICE_URL = "http://customer-service:8001/api/customers/"
STAFF_SERVICE_URL = "http://staff-service:8002/api/staff/"
LAPTOP_SERVICE_URL = "http://laptop-service:8003/api/laptops/"
MOBILE_SERVICE_URL = "http://mobile-service:8004/api/mobiles/"
CLOTHES_SERVICE_URL = "http://clothes-service:8005/clothes/"
BOOK_SERVICE_URL = "http://book-service:8007/api/books/"
AI_SERVICE_URL = "http://ai-service:8006/api/chat/"

def fetch_data(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

def normalize_products(products):
    for p in products:
        if 'author' in p and 'type' not in p:
            p['type'] = 'book'
        if 'title' in p and 'name' not in p:
            p['name'] = p['title']
        if 'author' in p and 'brand' not in p:
            p['brand'] = p['author']
    return products

def home_view(request):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_books = executor.submit(fetch_data, BOOK_SERVICE_URL)
        future_laptops = executor.submit(fetch_data, LAPTOP_SERVICE_URL)
        future_mobiles = executor.submit(fetch_data, MOBILE_SERVICE_URL)
        future_clothes = executor.submit(fetch_data, CLOTHES_SERVICE_URL)
        
        books = future_books.result()
        laptops = future_laptops.result()
        mobiles = future_mobiles.result()
        clothes = future_clothes.result()
    
    products = normalize_products(books + laptops + mobiles + clothes)
            
    return render(request, 'gateway/home.html', {'products': products})

def search_view(request):
    q = request.GET.get('q', '')
    if not q:
        return redirect('home')
        
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_books = executor.submit(fetch_data, BOOK_SERVICE_URL, {'q': q})
        future_laptops = executor.submit(fetch_data, LAPTOP_SERVICE_URL, {'q': q})
        future_mobiles = executor.submit(fetch_data, MOBILE_SERVICE_URL, {'q': q})
        future_clothes = executor.submit(fetch_data, CLOTHES_SERVICE_URL + 'search/', {'q': q})
        
        books = future_books.result()
        laptops = future_laptops.result()
        mobiles = future_mobiles.result()
        clothes = future_clothes.result()
    
    products = normalize_products(books + laptops + mobiles + clothes)
    
    # Log search behavior
    try:
        from .models import SearchLog
        user_id = request.session.get('user_id')
        SearchLog.objects.create(user_id=user_id, query_text=q)
    except Exception as e:
        print(f"Error logging search: {e}")
        
    return render(request, 'gateway/search_results.html', {'products': products, 'query': q})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        try:
            response = requests.post(f"{CUSTOMER_SERVICE_URL}login/", json={'username': username, 'password': password})
            if response.status_code == 200:
                data = response.json()
                request.session['user_id'] = data.get('id')
                request.session['role'] = data.get('role', 'customer')
                messages.success(request, 'Đăng nhập thành công!')
                return redirect('home')
            else:
                messages.error(request, 'Sai tên đăng nhập hoặc mật khẩu.')
        except Exception as e:
            messages.error(request, 'Dịch vụ đang bảo trì.')
            
    return render(request, 'gateway/login.html')

def staff_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        try:
            response = requests.post(f"{STAFF_SERVICE_URL}login/", json={'username': username, 'password': password})
            if response.status_code == 200:
                data = response.json()
                request.session['user_id'] = data.get('id')
                request.session['role'] = data.get('role', 'staff')
                messages.success(request, 'Nhân viên đăng nhập thành công!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Sai thông tin nhân viên hoặc không có quyền truy cập.')
        except Exception as e:
            messages.error(request, 'Dịch vụ quản trị đang bảo trì.')
            
    return render(request, 'gateway/staff_login.html')

def register_view(request):
    if request.method == 'POST':
        data = {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'}
        try:
            response = requests.post(CUSTOMER_SERVICE_URL, json=data)
            if response.status_code == 201:
                messages.success(request, 'Registration successful! Please login.')
                return redirect('login')
            else:
                messages.error(request, f'Registration failed: {response.text}')
        except Exception as e:
            messages.error(request, 'Customer service unavailable')
            
    return render(request, 'gateway/register.html')

def logout_view(request):
    request.session.flush()
    messages.success(request, 'Đã đăng xuất thành công.')
    return redirect('login')

def cart_view(request):
    cart = request.session.get('cart', {})
    
    if request.method == 'POST':
        action = request.POST.get('action')
        product_id = request.POST.get('product_id')
        product_type = request.POST.get('product_type')
        product_name = request.POST.get('product_name')
        price = request.POST.get('price')
        qty = int(request.POST.get('qty', 1))
        product_size = request.POST.get('selected_size', '')
        
        if product_type == 'clothes' and product_size:
            cart_key = f"{product_type}_{product_id}_{product_size}"
        else:
            cart_key = f"{product_type}_{product_id}"
        
        if action == 'add':
            if cart_key in cart:
                cart[cart_key]['qty'] += qty
            else:
                cart[cart_key] = {
                    'id': product_id,
                    'type': product_type,
                    'name': product_name,
                    'price': price,
                    'qty': qty,
                    'size': product_size
                }
            request.session['cart'] = cart
            request.session.modified = True
            size_msg = f" (Size {product_size})" if product_size else ""
            messages.success(request, f'Đã thêm {product_name}{size_msg} vào giỏ hàng.')
            
            # Log add to cart action
            try:
                from .models import InteractionLog
                user_id = request.session.get('user_id')
                InteractionLog.objects.create(
                    user_id=user_id,
                    product_id=str(product_id),
                    product_type=product_type,
                    action_type='cart'
                )
            except Exception as e:
                print(f"Tracking cart error: {e}")
            
            
        elif action == 'remove':
            cart_key_to_remove = request.POST.get('cart_key', cart_key)
            if cart_key_to_remove in cart:
                del cart[cart_key_to_remove]
                request.session['cart'] = cart
                request.session.modified = True
                messages.success(request, 'Đã xóa sản phẩm khỏi giỏ hàng.')
                
        return redirect('cart')
        
    total = sum(float(item['price']) * item['qty'] for item in cart.values())
    return render(request, 'gateway/cart.html', {'cart': cart, 'total': total})

def dashboard_view(request):
    role = str(request.session.get('role', '')).lower()
    if role not in ['staff', 'admin']:
        messages.error(request, 'Truy cập bị từ chối.')
        return redirect('login')
        
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_books = executor.submit(fetch_data, BOOK_SERVICE_URL)
        future_laptops = executor.submit(fetch_data, LAPTOP_SERVICE_URL)
        future_mobiles = executor.submit(fetch_data, MOBILE_SERVICE_URL)
        future_clothes = executor.submit(fetch_data, CLOTHES_SERVICE_URL)
        
        books = future_books.result()
        laptops = future_laptops.result()
        mobiles = future_mobiles.result()
        clothes = future_clothes.result()
        
    return render(request, 'gateway/dashboard.html', {'books': books, 'laptops': laptops, 'mobiles': mobiles, 'clothes': clothes})

def product_action_view(request, product_type):
    role = str(request.session.get('role', '')).lower()
    if role not in ['staff', 'admin']:
        return redirect('login')
        
    if product_type == 'laptop':
        url = LAPTOP_SERVICE_URL
    elif product_type == 'mobile':
        url = MOBILE_SERVICE_URL
    elif product_type == 'book':
        url = BOOK_SERVICE_URL
    else:
        url = CLOTHES_SERVICE_URL
    
    if request.method == 'POST':
        action = request.POST.get('action')
        product_id = request.POST.get('product_id')
        
        if action == 'delete':
            requests.delete(f"{url}{product_id}/")
            messages.success(request, 'Product deleted.')
        elif action == 'add' or action == 'edit':
            data = {k: v for k, v in request.POST.items() if k not in ['csrfmiddlewaretoken', 'action', 'product_id', 'product_type', 'image_upload']}
            
            if product_type == 'clothes':
                sizes = request.POST.getlist('size')
                if sizes:
                    data['size'] = sizes
                    
            if 'image_upload' in request.FILES:
                try:
                    upload_result = cloudinary.uploader.upload(request.FILES['image_upload'])
                    data['image_url'] = upload_result.get('secure_url')
                except Exception as e:
                    print(f"Cloudinary upload error: {e}")
                    # Allow to proceed without image_url update if it fails, or maybe just log it.
                    pass
                
            if action == 'add':
                requests.post(url, json=data)
                messages.success(request, 'Product added.')
            elif action == 'edit':
                requests.put(f"{url}{product_id}/", json=data)
                messages.success(request, 'Product updated.')
            
    return redirect('dashboard')

from django.http import JsonResponse
import json

def chat_view(request):
    return render(request, 'gateway/chat.html')

def ai_chat_api(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            query = body.get('query', '')
            user_id = request.session.get('user_id')
            
            # Forward to AI service
            response = requests.post(AI_SERVICE_URL, json={'query': query, 'user_id': user_id}, timeout=10)
            return JsonResponse(response.json(), status=response.status_code)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

def track_click_view(request):
    """API for frontend to ping when a product is viewed"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            product_id = body.get('product_id')
            product_type = body.get('product_type')
            
            if product_id and product_type:
                from .models import InteractionLog
                user_id = request.session.get('user_id')
                InteractionLog.objects.create(
                    user_id=user_id,
                    product_id=str(product_id),
                    product_type=product_type,
                    action_type='click'
                )
                return JsonResponse({'status': 'ok'})
        except Exception as e:
            print(f"Tracking click error: {e}")
    return JsonResponse({'status': 'error'}, status=400)

def export_analytics_view(request):
    """API strictly for AI Service to sync knowledge base"""
    from django.db.models import Count
    from .models import InteractionLog, SearchLog
    
    interactions = InteractionLog.objects.values('product_type', 'product_id', 'action_type').annotate(count=Count('id'))
    recent_searches = list(SearchLog.objects.order_by('-created_at')[:200].values_list('query_text', flat=True))
    
    return JsonResponse({
        'interactions': list(interactions),
        'recent_searches': recent_searches
    })

def product_detail_view(request, p_type, p_id):
    if p_type == 'laptop':
        url = f"{LAPTOP_SERVICE_URL}{p_id}/"
    elif p_type == 'mobile':
        url = f"{MOBILE_SERVICE_URL}{p_id}/"
    elif p_type == 'clothes':
        url = f"{CLOTHES_SERVICE_URL}{p_id}/"
    elif p_type == 'book':
        url = f"{BOOK_SERVICE_URL}{p_id}/"
    else:
        messages.error(request, 'Sản phẩm không hợp lệ.')
        return redirect('home')
        
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            product = response.json()
            product['type'] = p_type
            normalize_products([product])
            
            # Backend analytic tracking for the click/view
            try:
                from .models import InteractionLog
                user_id = request.session.get('user_id')
                InteractionLog.objects.create(
                    user_id=user_id,
                    product_id=str(p_id),
                    product_type=p_type,
                    action_type='click'
                )
            except Exception as e:
                print(f"Tracking error in detail view: {e}")
                
            return render(request, 'gateway/product_detail.html', {'p': product})
    except Exception as e:
        print(f"Gateway Detail view network error: {e}")
        
    messages.error(request, 'Sản phẩm này tạm thời không khả dụng.')
    return redirect('home')
