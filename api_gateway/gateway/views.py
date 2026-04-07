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
AI_SERVICE_URL = "http://ai-service:8006/api/chat/"

def fetch_data(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

def home_view(request):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_laptops = executor.submit(fetch_data, LAPTOP_SERVICE_URL)
        future_mobiles = executor.submit(fetch_data, MOBILE_SERVICE_URL)
        future_clothes = executor.submit(fetch_data, CLOTHES_SERVICE_URL)
        
        laptops = future_laptops.result()
        mobiles = future_mobiles.result()
        clothes = future_clothes.result()
    
    products = laptops + mobiles + clothes
    return render(request, 'gateway/home.html', {'products': products})

def search_view(request):
    q = request.GET.get('q', '')
    if not q:
        return redirect('home')
        
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_laptops = executor.submit(fetch_data, LAPTOP_SERVICE_URL, {'q': q})
        future_mobiles = executor.submit(fetch_data, MOBILE_SERVICE_URL, {'q': q})
        future_clothes = executor.submit(fetch_data, CLOTHES_SERVICE_URL + 'search/', {'q': q})
        
        laptops = future_laptops.result()
        mobiles = future_mobiles.result()
        clothes = future_clothes.result()
    
    products = laptops + mobiles + clothes
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
        future_laptops = executor.submit(fetch_data, LAPTOP_SERVICE_URL)
        future_mobiles = executor.submit(fetch_data, MOBILE_SERVICE_URL)
        future_clothes = executor.submit(fetch_data, CLOTHES_SERVICE_URL)
        
        laptops = future_laptops.result()
        mobiles = future_mobiles.result()
        clothes = future_clothes.result()
        
    return render(request, 'gateway/dashboard.html', {'laptops': laptops, 'mobiles': mobiles, 'clothes': clothes})

def product_action_view(request, product_type):
    role = str(request.session.get('role', '')).lower()
    if role not in ['staff', 'admin']:
        return redirect('login')
        
    if product_type == 'laptop':
        url = LAPTOP_SERVICE_URL
    elif product_type == 'mobile':
        url = MOBILE_SERVICE_URL
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
