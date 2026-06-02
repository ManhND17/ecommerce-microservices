import concurrent.futures
import os
import requests
import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Service URLs
USER_SERVICE_URL     = os.getenv("USER_SERVICE_URL", "http://user-service:9001/api/user/")
PRODUCT_SERVICE_URL  = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:9008/api/products/")
ORDER_SERVICE_URL    = os.getenv("ORDER_SERVICE_URL", "http://order-service:9002/api/")
PAYMENT_SERVICE_URL  = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:9003/api/")
SHIPMENT_SERVICE_URL = os.getenv("SHIPMENT_SERVICE_URL", "http://shipment-service:9004/api/")
CART_SERVICE_URL     = os.getenv("CART_SERVICE_URL", "http://cart-service:9006/api/")
BEHAVIOR_SERVICE_URL = os.getenv("BEHAVIOR_SERVICE_URL", "http://behavior-service:9007/api/logs/")
REVIEW_SERVICE_URL   = os.getenv("REVIEW_SERVICE_URL", "http://review-service:9009/api/reviews/")
AI_BASE_URL          = os.getenv("AI_SERVICE_URL", "http://ai-service:9005/api/")

def get_client_info(request):
    if not request.session.session_key:
        request.session.create()
    session_id = request.session.session_key

    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if any(m in user_agent for m in ['mobile', 'android', 'iphone', 'ipod']):
        device = 'Mobile'
    elif any(t in user_agent for t in ['tablet', 'ipad']):
        device = 'Tablet'
    else:
        device = 'Desktop'

    region = request.META.get('HTTP_ACCEPT_LANGUAGE', 'vi')[:2].upper()
    if not region or region == 'VI':
        region = 'VN'
    
    return {
        'session_id': session_id,
        'device': device,
        'region': region
    }


def _cart_fetch(user_id):
    """Lấy giỏ hàng từ cart_service, trả về dict {cart_key: item}."""
    try:
        resp = requests.get(f"{CART_SERVICE_URL}cart/", params={'user_id': user_id}, timeout=3)
        if resp.status_code == 200:
            db_cart = {}
            for item in resp.json():
                key = f"{item['product_type']}_{item['product_id']}"
                if item.get('size'):
                    key += f"_{item['size']}"
                db_cart[key] = {
                    'id': item['product_id'],
                    'type': item['product_type'],
                    'name': item['product_name'],
                    'price': item['price'],
                    'qty': item['quantity'],
                    'size': item.get('size', ''),
                    'image': item.get('image_url', ''),
                    '_db_pk': item['id'],
                }
            return db_cart
    except Exception as e:
        print(f"[cart_service] fetch error: {e}")
    return {}


def _cart_upsert(user_id, product_id, product_type, product_name, price, quantity, size='', **kwargs):
    """Upsert một item vào cart_service."""
    try:
        requests.post(f"{CART_SERVICE_URL}cart/items/", json={
            'user_id': user_id,
            'product_id': product_id,
            'product_type': product_type,
            'product_name': product_name,
            'price': price,
            'quantity': quantity,
            'size': size or '',
            'image_url': kwargs.get('image_url', ''),
        }, timeout=3)
    except Exception as e:
        print(f"[cart_service] upsert error: {e}")


def _cart_update_qty(user_id, product_id, product_type, quantity, size=''):
    """Cập nhật số lượng item theo composite key."""
    try:
        # Tìm pk trước
        resp = requests.get(f"{CART_SERVICE_URL}cart/", params={'user_id': user_id}, timeout=3)
        if resp.status_code == 200:
            for item in resp.json():
                if (item['product_id'] == str(product_id)
                        and item['product_type'] == product_type
                        and item.get('size', '') == (size or '')):
                    requests.patch(
                        f"{CART_SERVICE_URL}cart/items/{item['id']}/",
                        json={'quantity': quantity}, timeout=3
                    )
                    return
    except Exception as e:
        print(f"[cart_service] update_qty error: {e}")


def _cart_delete_item(user_id, product_id, product_type, size=''):
    """Xóa item khỏi cart_service theo composite key."""
    try:
        requests.delete(f"{CART_SERVICE_URL}cart/items/by-key/", params={
            'user_id': user_id,
            'product_id': product_id,
            'product_type': product_type,
            'size': size or '',
        }, timeout=3)
    except Exception as e:
        print(f"[cart_service] delete error: {e}")


def _cart_clear(user_id):
    """Xóa toàn bộ giỏ hàng của user trong cart_service."""
    try:
        requests.delete(f"{CART_SERVICE_URL}cart/clear/", params={'user_id': user_id}, timeout=3)
    except Exception as e:
        print(f"[cart_service] clear error: {e}")

# AI Service Endpoints
AI_CHAT_URL = f"{AI_BASE_URL}chat/"
AI_RECOMMEND_URL = f"{AI_BASE_URL}recommend/"
AI_RECOMMEND_SEARCH_URL = f"{AI_RECOMMEND_URL}search/"
AI_RECOMMEND_CART_URL = f"{AI_RECOMMEND_URL}cart/"

def fetch_data(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

def normalize_products(products):
    """
    Chuẩn hóa dữ liệu từ Product Service mới để tương thích với các Template cũ.
    - Chuyển catalog_slug thành type.
    - Phẳng hóa specific_attributes ra ngoài dictionary gốc.
    """
    if isinstance(products, dict) and 'results' in products:
        products = products['results']
    
    normalized = []
    for p in products:
        # Clone để tránh side effects
        item = p.copy()
        
        # Ánh xạ catalog_slug hoặc category -> type
        item['type'] = p.get('catalog_slug') or p.get('category') or 'unknown'
        
        # Phẳng hóa các thuộc tính đặc tả (specific_attributes)
        attrs = p.get('specific_attributes', {})
        if isinstance(attrs, dict):
            for k, v in attrs.items():
                if k not in item: # Tránh ghi đè các trường chính
                    item[k] = v
        
        # Đảm bảo các trường cơ bản có mặt (cho legacy code)
        if 'title' in item and 'name' not in item:
            item['name'] = item['title']
        if 'brand' not in item:
            item['brand'] = attrs.get('brand', '')
            
        # Chuẩn hóa ảnh
        img = p.get('image_url') or p.get('image') or p.get('thumbnail') or ''
        if img and img.startswith('/media/'):
             # Giả định media nằm ở product-service nếu là path tương đối
             img = f"http://localhost:9008{img}"
        item['image_url'] = img
            
        normalized.append(item)
    return normalized

def home_view(request):
    # Lấy toàn bộ sản phẩm và danh mục
    all_products_raw = fetch_data(PRODUCT_SERVICE_URL)
    products = normalize_products(all_products_raw)
    catalogs = fetch_data("http://product-service:9008/api/catalogs/")
    
    # Nhóm sản phẩm theo từng catalog để hiển thị theo phần (Section)
    grouped_products = {}
    for cat in catalogs:
        slug = cat['slug']
        # Lấy tối đa 4 sản phẩm cho mỗi danh mục để hiển thị ở trang chủ (1 dòng)
        grouped_products[slug] = [p for p in products if p['type'] == slug][:4]
    
    # Lấy thêm Gợi ý AI (Trending hoặc Cá nhân hóa theo user_id)
    ai_recommendations = []
    try:
        user_id = request.session.get('user_id')
        payload = {'user_id': user_id, 'limit': 10}
        response = requests.post(AI_RECOMMEND_URL, json=payload, timeout=3)
        if response.status_code == 200:
            ai_data = response.json()
            ai_recommendations = normalize_products(ai_data.get('products', []))
    except Exception as e:
        print(f"AI Home Recommendation failed: {e}")
        
    import json
    return render(request, 'gateway/home.html', {
        'grouped_products': grouped_products,
        'catalogs': catalogs,
        'all_products': products,
        'ai_recommendations': ai_recommendations
    })

def search_view(request):
    q = request.GET.get('q', '')
    if not q:
        return redirect('home')
    
    # Sử dụng tính năng Search Filter của Product Service
    search_results_raw = fetch_data(PRODUCT_SERVICE_URL, {'search': q})
    products = normalize_products(search_results_raw)
    
    # Log search behavior to behavior_service
    try:
        user_id = request.session.get('user_id')
        client_info = get_client_info(request)
        payload = {'user_id': user_id, 'query_text': q, **client_info}
        requests.post(f"{BEHAVIOR_SERVICE_URL}search/", json=payload, timeout=1)
    except Exception as e:
        print(f"Error logging search: {e}")

    # AI Recommendation for Search
    ai_recommendations = []
    try:
        response = requests.get(AI_RECOMMEND_SEARCH_URL, params={'q': q, 'user_id': request.session.get('user_id'), 'limit': 10}, timeout=3)
        if response.status_code == 200:
            ai_data = response.json()
            # Normalize AI products to match UI expectations
            ai_recommendations = normalize_products(ai_data.get('products', []))
    except Exception as e:
        print(f"AI Search Recommendation failed: {e}")
        
    return render(request, 'gateway/search_results.html', {
        'products': products, 
        'query': q,
        'ai_recommendations': ai_recommendations
    })

def login_view(request):
    """Unified login for all roles (Customer, Staff, Admin)"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            # Gọi API Login của UserService (JWT Token Obtain)
            response = requests.post(f"{USER_SERVICE_URL}login/", json={'username': username, 'password': password}, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                # Lưu thông tin cơ bản vào Session
                request.session['user_id'] = data.get('id')
                request.session['username'] = data.get('username')
                role = str(data.get('role', 'customer')).lower()
                request.session['role'] = role
                
                # Lưu JWT Tokens
                request.session['access_token'] = data.get('access')
                request.session['refresh_token'] = data.get('refresh')
                
                messages.success(request, f'Đăng nhập thành công! Chào mừng {username}.')

                # Điều hướng dựa trên Role
                if role == 'admin':
                    return redirect('dashboard')
                elif role == 'staff':
                    return redirect('shipper_dashboard')
                
                # Nếu là Customer, thực hiện logic khôi phục giỏ hàng
                user_id = data.get('id')
                session_cart = request.session.get('cart', {})
                # Lấy giỏ hàng đã lưu từ cart_service
                db_cart = _cart_fetch(user_id)
                # Merge session_cart vào db_cart
                for key, item in session_cart.items():
                    if key in db_cart:
                        db_cart[key]['qty'] += item['qty']
                    else:
                        db_cart[key] = item
                request.session['cart'] = db_cart
                # Đồng bộ ngược lại cart_service
                for key, item in db_cart.items():
                    _cart_upsert(
                        user_id=user_id,
                        product_id=item['id'],
                        product_type=item['type'],
                        product_name=item['name'],
                        price=item['price'],
                        quantity=item['qty'],
                        size=item.get('size', ''),
                    )

                return render(request, 'gateway/login_success.html', {
                    'access_token': data.get('access'),
                    'refresh_token': data.get('refresh')
                })
            else:
                messages.error(request, 'Sai tên đăng nhập hoặc mật khẩu.')
        except Exception as e:
            print(f"Login error: {e}")
            messages.error(request, 'Dịch vụ xác thực đang bảo trì.')
    return render(request, 'gateway/login.html')

def staff_login_view(request):
    """Redirect to unified login"""
    return redirect('login')

def register_view(request):
    if request.method == 'POST':
        data = {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'}
        try:
            response = requests.post(f"{USER_SERVICE_URL}register/", json=data, timeout=5)
            if response.status_code == 201:
                messages.success(request, 'Đăng ký thành công! Vui lòng đăng nhập.')
                return redirect('login')
            else:
                messages.error(request, f'Đăng ký thất bại: {response.text}')
        except Exception as e:
            messages.error(request, 'UserService không khả dụng.')
    return render(request, 'gateway/register.html')

def logout_view(request):
    request.session.flush()
    messages.success(request, 'Đã đăng xuất thành công.')
    return redirect('login')

def profile_view(request):
    """Trang thông tin cá nhân của người dùng."""
    if not request.session.get('user_id'):
        return redirect('login')

    token = request.session.get('access_token')
    if not token:
        return redirect('login')
        
    headers = {'Authorization': f'Bearer {token}'}
    url = f"{USER_SERVICE_URL}profile/"
    
    if request.method == 'POST':
        data = {
            'email': request.POST.get('email', ''),
            'full_name': request.POST.get('full_name', ''),
            'phone': request.POST.get('phone', ''),
            'address': request.POST.get('address', '')
        }
        try:
            resp = requests.patch(url, json=data, headers=headers, timeout=5)
            if resp.status_code in [200, 204]:
                messages.success(request, 'Cập nhật thông tin thành công.')
                # Cập nhật username trong session nếu cần
                user_data = resp.json()
                if 'username' in user_data:
                    request.session['username'] = user_data['username']
            else:
                messages.error(request, f"Lỗi cập nhật: {resp.text}")
        except Exception as e:
            messages.error(request, f"Lỗi kết nối: {e}")
        return redirect('profile')

    user_info = {}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            user_info = resp.json()
        elif resp.status_code == 401:
            request.session.flush()
            return redirect('login')
    except Exception as e:
        print(f"Error fetching profile: {e}")

    return render(request, 'gateway/profile.html', {'user_info': user_info})


def cart_view(request):
    user_id = request.session.get('user_id')
    
    # Nếu đã đăng nhập, ưu tiên lấy dữ liệu từ cart_service để đảm bảo đồng nhất với DB
    if user_id:
        cart = _cart_fetch(user_id)
        request.session['cart'] = cart
        request.session.modified = True
    else:
        cart = request.session.get('cart', {})
        
    if request.method == 'POST':
        action = request.POST.get('action')
        product_id = request.POST.get('product_id')
        product_type = request.POST.get('product_type')
        product_name = request.POST.get('product_name')
        price_raw = request.POST.get('price', '0')
        try:
            # First, try direct float conversion (handles "750000.0" correctly)
            price = float(price_raw)
        except (ValueError, TypeError):
            # If it fails, it might have thousands separators (e.g., "750.000")
            # In VND context, we assume no decimals, so we strip all non-digits
            import re
            price_clean = re.sub(r'[^\d]', '', str(price_raw))
            price = float(price_clean) if price_clean else 0.0
        
        qty_raw = request.POST.get('qty', '1')
        try:
            qty = int(qty_raw)
        except (ValueError, TypeError):
            qty = int(re.sub(r'[^\d]', '', str(qty_raw)) or 1)
        product_size = request.POST.get('selected_size', '')
        image_url = request.POST.get('image_url', '')
        
        cart_key = f"{product_type}_{product_id}"
        if product_size: cart_key += f"_{product_size}"
        
        if action == 'add':
            if cart_key in cart:
                cart[cart_key]['qty'] += qty
            else:
                cart[cart_key] = {
                    'id': product_id, 'type': product_type, 'name': product_name,
                    'price': price, 'qty': qty, 'size': product_size, 'image': image_url
                }
            request.session['cart'] = cart
            request.session.modified = True
            messages.success(request, f'Đã thêm {product_name} vào giỏ hàng.')
            
            # Tracking and Persistence
            try:
                user_id = request.session.get('user_id')
                client_info = get_client_info(request)
                # Log to behavior_service
                requests.post(f"{BEHAVIOR_SERVICE_URL}interaction/", json={
                    'user_id': user_id,
                    'product_id': str(product_id),
                    'product_type': product_type,
                    'action_type': 'add_to_cart',
                    **client_info
                }, timeout=1)
                
                if user_id:
                    _cart_upsert(
                        user_id=user_id,
                        product_id=product_id,
                        product_type=product_type,
                        product_name=product_name,
                        price=price,
                        quantity=cart[cart_key]['qty'],
                        size=product_size,
                        image_url=image_url
                    )
            except Exception: pass

        elif action == 'update':
            cart_key_to_update = request.POST.get('cart_key')
            new_qty_str = request.POST.get('qty', '1')
            try:
                new_qty = int(new_qty_str)
            except ValueError:
                new_qty = 1
            if cart_key_to_update in cart:
                if new_qty < 1: new_qty = 1
                cart[cart_key_to_update]['qty'] = new_qty
                request.session['cart'] = cart
                request.session.modified = True
                # Persistence
                try:
                    user_id = request.session.get('user_id')
                    if user_id:
                        item = cart[cart_key_to_update]
                        _cart_update_qty(
                            user_id=user_id,
                            product_id=item['id'],
                            product_type=item['type'],
                            quantity=new_qty,
                            size=item.get('size', ''),
                        )
                except Exception: pass

                except Exception: pass

        elif action == 'remove':
            cart_key_to_remove = request.POST.get('cart_key')
            if cart_key_to_remove in cart:
                item_to_remove = cart[cart_key_to_remove]
                del cart[cart_key_to_remove]
                request.session['cart'] = cart
                request.session.modified = True
                messages.success(request, 'Đã xóa sản phẩm khỏi giỏ hàng.')
                # Persistence
                try:
                    user_id = request.session.get('user_id')
                    if user_id:
                        _cart_delete_item(
                            user_id=user_id,
                            product_id=item_to_remove['id'],
                            product_type=item_to_remove['type'],
                            size=item_to_remove.get('size', ''),
                        )
                except Exception: pass

        elif action == 'update_selected':
            cart_key_to_update = request.POST.get('cart_key')
            is_selected = request.POST.get('selected') == 'true'
            if cart_key_to_update in cart:
                cart[cart_key_to_update]['selected'] = is_selected
                request.session['cart'] = cart
                request.session.modified = True
                return JsonResponse({'status': 'ok'})

        return redirect('cart')
        
    # Pre-calculate totals for template
    total = 0
    for key, item in cart.items():
        p = item['price']
        # Robust price parsing logic
        try:
            # Try direct conversion first
            item_price = float(p)
        except (ValueError, TypeError):
            # Handle formatted strings
            import re
            price_clean = re.sub(r'[^\d]', '', str(p))
            item_price = float(price_clean) if price_clean else 0.0
        
        item_qty = int(item['qty'])
        subtotal = item_price * item_qty
        item['subtotal'] = subtotal
        
        # Chỉ cộng vào tổng tiền nếu được chọn
        if item.get('selected') != False:
            total += subtotal
            
    # AI Recommendation for Cart
    ai_recommendations = []
    try:
        payload = {'user_id': request.session.get('user_id'), 'limit': 10}
        if cart:
            # Ưu tiên ngữ cảnh sản phẩm cuối cùng trong giỏ
            last_key = list(cart.keys())[-1]
            last_item = cart[last_key]
            payload['product_id'] = last_item.get('id')
            payload['category'] = last_item.get('type')
            
        response = requests.post(AI_RECOMMEND_URL, json=payload, timeout=3)
        if response.status_code == 200:
            ai_data = response.json()
            ai_recommendations = normalize_products(ai_data.get('products', []))
    except Exception as e:
        print(f"AI Cart Recommendation failed: {e}")

    return render(request, 'gateway/cart.html', {
        'cart': cart, 
        'total': total,
        'ai_recommendations': ai_recommendations
    })

from django.core.paginator import Paginator

def dashboard_view(request):
    role = str(request.session.get('role', '')).lower()
    if role not in ['staff', 'admin']:
        return redirect('login')
        
    # Fetch all data and catalogs
    all_raw = fetch_data(PRODUCT_SERVICE_URL)
    all_p = normalize_products(all_raw)
    
    catalogs = fetch_data("http://product-service:9008/api/catalogs/")
    
    # Lấy trang hiện tại từ query params
    page_number = request.GET.get('page', 1)
    current_catalog_slug = request.GET.get('catalog', catalogs[0]['slug'] if catalogs else '')

    # Group products by catalog slug
    grouped_products = {}
    for cat in catalogs:
        slug = cat['slug']
        products_in_cat = [p for p in all_p if p['type'] == slug]
        
        # Chỉ phân trang cho Catalog đang được chọn để tối ưu
        if slug == current_catalog_slug:
            paginator = Paginator(products_in_cat, 8)
            page_obj = paginator.get_page(page_number)
            grouped_products[slug] = page_obj
        else:
            grouped_products[slug] = products_in_cat # Các tab khác giữ nguyên hoặc để trống
    
    return render(request, 'gateway/dashboard.html', {
        'grouped_products': grouped_products,
        'catalogs': catalogs,
        'current_catalog': current_catalog_slug,
    })

def product_action_view(request, product_type):
    """Xử lý thêm/sửa/xóa sản phẩm từ Dashboard nhân viên."""
    role = str(request.session.get('role', '')).lower()
    if role not in ['staff', 'admin']:
        return redirect('login')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        product_id = request.POST.get('product_id')
        
        if action == 'delete':
            requests.delete(f"{PRODUCT_SERVICE_URL}{product_id}/")
            messages.success(request, 'Đã xóa sản phẩm thành công.')
        elif action in ['add', 'edit']:
            import json
            data = {k: v for k, v in request.POST.items() if k not in ['csrfmiddlewaretoken', 'action', 'product_id', 'product_type']}
            
            if 'specific_attributes' in data and data['specific_attributes'].strip():
                try:
                    data['specific_attributes'] = json.loads(data['specific_attributes'])
                except Exception:
                    data['specific_attributes'] = {}
            
            # Cloudinary upload if any
            if 'image_upload' in request.FILES:
                import cloudinary.uploader
                try:
                    res = cloudinary.uploader.upload(request.FILES['image_upload'])
                    data['image_url'] = res.get('secure_url')
                except Exception: pass

            if action == 'add':
                resp = requests.post(PRODUCT_SERVICE_URL, json=data)
            else:
                # Xóa catalog khỏi data khi edit để tránh lưu đè nhầm (do select bị ẩn)
                if 'catalog' in data:
                    del data['catalog']
                resp = requests.patch(f"{PRODUCT_SERVICE_URL}{product_id}/", json=data)
                
            if resp.status_code in [200, 201]:
                msg = "Thêm mới" if action == 'add' else "Cập nhật"
                messages.success(request, f'Đã {msg} sản phẩm thành công.')
            else:
                messages.error(request, f'Lỗi khi lưu: {resp.text}')
            
    return redirect('dashboard')

def admin_orders_view(request):
    role = str(request.session.get('role', '')).lower()
    if role not in ['staff', 'admin']:
        return redirect('login')
        
    orders = []
    try:
        resp = requests.get(f"{ORDER_SERVICE_URL}orders/", timeout=5)
        if resp.status_code == 200:
            orders = resp.json()
            orders.sort(key=lambda x: x.get('id', 0), reverse=True)
    except Exception as e:
        print(f"Error fetching all orders: {e}")
    
    paginator = Paginator(orders, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'gateway/admin_orders.html', {'orders': page_obj})

def admin_customers_view(request):
    role = str(request.session.get('role', '')).lower()
    if role not in ['staff', 'admin']:
        return redirect('login')
        
    token = request.session.get('access_token')
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    
    customers = []
    try:
        resp = requests.get(f"{USER_SERVICE_URL}admin/users/", headers=headers, timeout=5)
        if resp.status_code == 200:
            customers = [u for u in resp.json() if u.get('role', '').lower() == 'customer']
    except Exception as e:
        print(f"Error fetching users: {e}")
        
    paginator = Paginator(customers, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'gateway/admin_customers.html', {'customers': page_obj})

def admin_stats_view(request):
    role = str(request.session.get('role', '')).lower()
    if role not in ['staff', 'admin']:
        return redirect('login')
        
    period = request.GET.get('period', 'month') # day, month, quarter, year
    # 1. Lấy dữ liệu song song để tối ưu tốc độ
    orders = []
    total_users = 0
    token = request.session.get('access_token')
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    
    def fetch_orders():
        try:
            r = requests.get(f"{ORDER_SERVICE_URL}orders/", timeout=3)
            return r.json() if r.status_code == 200 else []
        except: return []

    def fetch_users():
        try:
            r = requests.get(f"{USER_SERVICE_URL}admin/users/", headers=headers, timeout=3)
            return len(r.json()) if r.status_code == 200 else 0
        except: return 0

    def fetch_products():
        try:
            # Lấy toàn bộ sản phẩm để mapping category cho các đơn hàng cũ
            r = requests.get(PRODUCT_SERVICE_URL, timeout=3)
            if r.status_code == 200:
                # { "1": "laptop", "2": "mobile" }
                return {str(p['id']): p.get('type', 'Khác') for p in r.json()}
            return {}
        except: return {}

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_orders = executor.submit(fetch_orders)
        future_users = executor.submit(fetch_users)
        future_products = executor.submit(fetch_products)
        
        orders = future_orders.result()
        total_users = future_users.result()
        product_type_map = future_products.result()
    
    from datetime import datetime, timedelta
    from django.utils import timezone
    now = timezone.now()
    
    total_orders_all_time = len(orders)
    
    # 1. Lọc đơn hàng theo thời gian
    filtered_orders = []
    for o in orders:
        try:
            # Chuyển string thành aware datetime
            o_date = datetime.fromisoformat(o['created_at'].replace('Z', '+00:00'))
            is_match = False
            if period == 'day' and o_date.date() == now.date():
                is_match = True
            elif period == 'month' and o_date.month == now.month and o_date.year == now.year:
                is_match = True
            elif period == 'quarter':
                now_quarter = (now.month - 1) // 3 + 1
                o_quarter = (o_date.month - 1) // 3 + 1
                if now_quarter == o_quarter and o_date.year == now.year:
                    is_match = True
            elif period == 'year' and o_date.year == now.year:
                is_match = True
            
            if is_match:
                filtered_orders.append(o)
        except: continue

    # 2. Tính toán doanh thu & số lượng
    total_revenue = sum(float(o.get('total_price', 0)) for o in filtered_orders if o.get('status') == 'delivered')
    total_orders_period = len(filtered_orders)
    completed_orders = len([o for o in filtered_orders if o.get('status') == 'delivered'])
    
    # 3. Top Sản phẩm bán chạy (chỉ tính đơn delivered)
    product_sales = {}
    category_sales = {} # { 'laptop': 15, 'mobile': 10 }
    category_revenue = {} # { 'laptop': 1500000, ... }
    category_product_detail = {} # { 'laptop': { 'Macbook': 5, 'Dell': 10 } }
    
    # Status metrics for Revenue
    status_revenue = { 'pending': 0, 'pending_payment': 0, 'preparing': 0, 'prepared': 0, 'shipping': 0, 'delivered': 0, 'cancelled': 0 }

    for o in filtered_orders:
        s = o.get('status', 'unknown')
        val = float(o.get('total_price', 0))
        if s in status_revenue: status_revenue[s] += val

        if s == 'delivered':
            for item in o.get('items', []):
                p_id = str(item.get('product_id'))
                p_name = item.get('product_name', f"Sản phẩm #{p_id}")
                
                # Fallback mapping cho các đơn hàng cũ bị thiếu product_type
                p_type = item.get('product_type')
                if not p_type or p_type == 'Khác':
                    p_type = product_type_map.get(p_id, 'Khác')
                
                p_image = item.get('image_url', '')
                qty = int(item.get('quantity', 0))
                price = float(item.get('price', 0))
                revenue = qty * price
                
                # Fix URL ảnh
                if p_image:
                    if p_image.startswith('/media/'):
                        p_image = f"http://localhost:9008{p_image}"
                    elif 'product-service' in p_image:
                        p_image = p_image.replace('product-service', 'localhost')

                # Theo Sản phẩm tổng quát
                if p_id not in product_sales:
                    product_sales[p_id] = {'name': p_name, 'image': p_image, 'qty': 0, 'revenue': 0, 'type': p_type}
                product_sales[p_id]['qty'] += qty
                product_sales[p_id]['revenue'] += revenue
                
                # Theo Danh mục
                category_sales[p_type] = category_sales.get(p_type, 0) + qty
                category_revenue[p_type] = category_revenue.get(p_type, 0) + revenue
                
                # Chi tiết sản phẩm trong từng danh mục
                if p_type not in category_product_detail:
                    category_product_detail[p_type] = {}
                category_product_detail[p_type][p_name] = category_product_detail[p_type].get(p_name, 0) + qty

    limit = int(request.GET.get('limit', 5))
    
    top_products = sorted(product_sales.values(), key=lambda x: x['qty'], reverse=True)[:limit]
    for p in top_products:
        p['avg_price'] = p['revenue'] / p['qty'] if p['qty'] > 0 else 0
    total_qty_sold = sum(cat_qty for cat_qty in category_sales.values())

    # 4. Top Khách hàng (chỉ tính đơn delivered)
    customer_stats = {}
    for o in filtered_orders:
        if o.get('status') == 'delivered':
            uid = o.get('user_id')
            uname = o.get('customer_name', f"Khách #{uid}")
            if uid not in customer_stats:
                customer_stats[uid] = {'name': uname, 'total_spent': 0, 'order_count': 0}
            customer_stats[uid]['total_spent'] += float(o.get('total_price', 0))
            customer_stats[uid]['order_count'] += 1
            
    for uid in customer_stats:
        stats = customer_stats[uid]
        stats['aov'] = stats['total_spent'] / stats['order_count'] if stats['order_count'] > 0 else 0
        
    top_customers = sorted(customer_stats.values(), key=lambda x: x['total_spent'], reverse=True)[:limit]

    # 5. Dữ liệu biểu đồ 7 ngày gần nhất (luôn hiển thị 7 ngày để thấy xu hướng)
    revenue_by_date = {}
    for i in range(6, -1, -1):
        date_str = (now - timedelta(days=i)).strftime('%d/%m')
        revenue_by_date[date_str] = 0
        
    for o in orders: # Dùng toàn bộ đơn hàng cho biểu đồ xu hướng
        if o.get('status') == 'delivered':
            try:
                o_date = datetime.fromisoformat(o['created_at'].replace('Z', '+00:00')).strftime('%d/%m')
                if o_date in revenue_by_date:
                    revenue_by_date[o_date] += float(o.get('total_price', 0))
            except: continue
            
    revenue_labels = list(revenue_by_date.keys())
    revenue_data = list(revenue_by_date.values())
    
    import json
    return render(request, 'gateway/admin_stats.html', {
        'total_revenue': total_revenue,
        'total_orders_period': total_orders_period,
        'total_orders_all_time': total_orders_all_time,
        'completed_orders': completed_orders,
        'total_users': total_users,
        'total_qty_sold': total_qty_sold,
        'orders_js': json.dumps(filtered_orders), 
        'revenue_labels_js': json.dumps(revenue_labels),
        'revenue_data_js': json.dumps(revenue_data),
        'category_sales_js': json.dumps(category_sales),
        'category_revenue_js': json.dumps(category_revenue),
        'category_product_detail_js': json.dumps(category_product_detail),
        'status_revenue_js': json.dumps(status_revenue),
        'top_products': top_products,
        'top_customers': top_customers,
        'current_period': period,
        'current_limit': limit,
    })

def ai_chat_api(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            query = body.get('query', '')
            user_id = request.session.get('user_id')
            response = requests.post(AI_CHAT_URL, json={'query': query, 'user_id': user_id}, timeout=10)
            return JsonResponse(response.json(), status=response.status_code)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

def chat_view(request):
    return render(request, 'gateway/chat.html')

def product_detail_view(request, p_type, p_id):
    # Làm sạch p_id: Nếu p_id có dạng 'laptop_10', chúng ta chỉ lấy phần '10'
    clean_id = str(p_id).split('_')[-1] if '_' in str(p_id) else p_id
    
    url = f"{PRODUCT_SERVICE_URL}{clean_id}/"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            product = response.json()
            # Normalize single product
            normalized = normalize_products([product])[0]
            
            # Map specific_attributes to Vietnamese
            KEY_MAP = {
                "ram": "Bộ nhớ RAM",
                "chip": "Vi xử lý",
                "storage": "Ổ cứng/Lưu trữ",
                "screen": "Màn hình",
                "battery": "Dung lượng pin",
                "waterproof": "Chống nước",
                "camera": "Camera",
                "size": "Kích cỡ",
                "material": "Chất liệu",
                "color": "Màu sắc",
                "author": "Tác giả",
                "publisher": "Nhà xuất bản",
                "pages": "Số trang",
                "power": "Công suất",
                "capacity": "Dung tích/Khối lượng",
                "voltage": "Điện áp",
                "connection": "Kết nối",
                "series": "Dòng sản phẩm",
                "warranty": "Bảo hành"
            }
            
            if 'specific_attributes' in normalized and isinstance(normalized['specific_attributes'], dict):
                formatted_attrs = {}
                for k, v in normalized['specific_attributes'].items():
                    formatted_attrs[KEY_MAP.get(k, k.title())] = v
                normalized['display_attributes'] = formatted_attrs
            else:
                normalized['display_attributes'] = {}
            
            # Log Interaction
            try:
                user_id = request.session.get('user_id')
                client_info = get_client_info(request)
                requests.post(f"{BEHAVIOR_SERVICE_URL}interaction/", json={
                    'user_id': user_id,
                    'product_id': str(p_id),
                    'product_type': p_type,
                    'action_type': 'click',
                    **client_info
                }, timeout=1)
            except Exception: pass
            
            return render(request, 'gateway/product_detail.html', {'p': normalized})
    except Exception as e:
        print(f"Error detail view: {e}")
        
    messages.error(request, 'Sản phẩm không tồn tại.')
    return redirect('home')

@csrf_exempt
def track_click_api(request):
    """Lưu vết click qua behavior_service"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            data['user_id'] = request.session.get('user_id')
            client_info = get_client_info(request)
            data.update(client_info)
            requests.post(f"{BEHAVIOR_SERVICE_URL}interaction/", json=data, timeout=1)
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'POST required'}, status=405)


def export_analytics_view(request):
    """Proxy tới behavior_service để xuất dữ liệu analytics cho AI"""
    try:
        resp = requests.get(f"{BEHAVIOR_SERVICE_URL}export/", timeout=5)
        return JsonResponse(resp.json(), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def bulk_insert_interactions_api(request):
    """Proxy tới behavior_service để lưu bulk interactions"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            resp = requests.post(f"{BEHAVIOR_SERVICE_URL}interactions/bulk/", json=data, timeout=5)
            return JsonResponse(resp.json(), status=resp.status_code, safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'POST required'}, status=405)


def get_all_interactions_api(request):
    """Proxy tới behavior_service để lấy danh sách tương tác"""
    try:
        resp = requests.get(f"{BEHAVIOR_SERVICE_URL}export/", timeout=5)
        data = resp.json()
        return JsonResponse({'data': data.get('interactions', [])})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# ORDER SERVICE PROXY
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
def order_list_create_api(request):
    """
    GET  /api/orders/        – Danh sách đơn hàng của user hiện tại
    POST /api/orders/        – Tạo đơn hàng mới (tự điền user_id từ session)
    """
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Bạn cần đăng nhập để thực hiện thao tác này.'}, status=401)

    url = f"{ORDER_SERVICE_URL}orders/"
    try:
        if request.method == 'GET':
            resp = requests.get(url, params={'user_id': user_id}, timeout=5)
        elif request.method == 'POST':
            body = json.loads(request.body)
            body['user_id'] = user_id   # Điền user_id tự động từ session
            resp = requests.post(url, json=body, timeout=5)
        else:
            return JsonResponse({'error': 'Method not allowed'}, status=405)

        return JsonResponse(resp.json(), status=resp.status_code, safe=False)
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Order Service không phản hồi.'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def order_detail_api(request, order_id):
    """
    GET   /api/orders/<id>/         – Chi tiết đơn hàng
    PATCH /api/orders/<id>/status/  – Cập nhật trạng thái đơn hàng
    """
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Bạn cần đăng nhập.'}, status=401)

    url = f"{ORDER_SERVICE_URL}orders/{order_id}/"
    try:
        resp = requests.get(url, timeout=5)
        return JsonResponse(resp.json(), status=resp.status_code, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def order_status_update_api(request, order_id):
    """
    PATCH /api/orders/<id>/status/
    Body: { "status": "preparing" | "prepared" | "shipping" | "delivered" | "cancelled" }
    """
    if request.method != 'PATCH':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    user_id = request.session.get('user_id')
    role = str(request.session.get('role', 'customer')).lower()
    if not user_id:
        return JsonResponse({'error': 'Bạn cần đăng nhập.'}, status=401)
    
    if role not in ['staff', 'admin']:
        return JsonResponse({'error': 'Bạn không có quyền thực hiện thao tác này.'}, status=403)

    url = f"{ORDER_SERVICE_URL}orders/{order_id}/status/"
    try:
        body = json.loads(request.body)
        resp = requests.patch(url, json=body, timeout=5)
        
        try:
            data = resp.json()
        except Exception:
            data = {'error': resp.text or 'Lỗi không xác định từ Order Service'}
            
        return JsonResponse(data, status=resp.status_code, safe=False)
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Order Service không phản hồi.'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# PAYMENT SERVICE PROXY
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
def payment_create_api(request):
    """
    POST /api/payments/create/
    Body: { "order_id": 1, "amount": 150000 }
    Trả về VNPay URL để redirect người dùng sang trang thanh toán.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Bạn cần đăng nhập.'}, status=401)

    url = f"{PAYMENT_SERVICE_URL}payments/create/"
    try:
        body = json.loads(request.body)
        body['user_id'] = user_id
        body['method'] = 'vnpay'
        resp = requests.post(url, json=body, timeout=5)
        
        try:
            data = resp.json()
            return JsonResponse(data, status=resp.status_code, safe=False)
        except ValueError:
            return JsonResponse({
                'error': 'Payment Service trả về nội dung không hợp lệ.',
                'details': resp.text[:200]
            }, status=500)
            
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Payment Service không phản hồi.'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def payment_list_api(request):
    """GET /api/payments/ – Danh sách giao dịch thanh toán"""
    url = f"{PAYMENT_SERVICE_URL}payments/"
    try:
        resp = requests.get(url, timeout=5)
        return JsonResponse(resp.json(), status=resp.status_code, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def payment_detail_api(request, payment_id):
    """GET /api/payments/<id>/ – Chi tiết giao dịch"""
    url = f"{PAYMENT_SERVICE_URL}payments/{payment_id}/"
    try:
        resp = requests.get(url, timeout=5)
        return JsonResponse(resp.json(), status=resp.status_code, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def vnpay_return_proxy(request):
    """
    GET /payments/vnpay-return/
    Nhận callback từ VNPay sau khi người dùng thanh toán xong.
    Forward toàn bộ query params sang Payment Service, rồi redirect sang trang kết quả.
    """
    url = f"{PAYMENT_SERVICE_URL}payments/vnpay-return/"
    try:
        resp = requests.get(url, params=request.GET.dict(), timeout=5)
        data = resp.json()
        order_id = request.GET.get('vnp_TxnRef', '')  # Lấy order_id từ params
        if resp.status_code == 200:
            return redirect(f"/order-success/?order_id={data.get('order_id', '')}&method=vnpay")
        else:
            return redirect('/order-success/?success=false')
    except Exception as e:
        return redirect('/order-success/?success=false')


# ─────────────────────────────────────────────────────────────────────────────
# CHECKOUT & ORDER RESULT PAGES
# ─────────────────────────────────────────────────────────────────────────────

import json as _json

def checkout_view(request):
    """Trang đặt hàng – render checkout.html với dữ liệu giỏ hàng từ session."""
    if not request.session.get('user_id'):
        return redirect('login')

    cart = request.session.get('cart', {})
    # Chỉ lấy những sản phẩm đã được tích chọn
    selected_cart = {k: v for k, v in cart.items() if v.get('selected') != False}
    
    if not selected_cart:
        messages.warning(request, 'Bạn chưa chọn sản phẩm nào để thanh toán.')
        return redirect('cart')

    cart_json = _json.dumps(selected_cart)
    return render(request, 'gateway/checkout.html', {'cart_json': cart_json})


def order_success_view(request):
    """Trang kết quả đơn hàng sau khi đặt hoặc sau khi VNPay callback."""
    order_id = request.GET.get('order_id', '')
    payment_method = request.GET.get('method', 'cod')
    is_success = request.GET.get('success', 'true').lower() != 'false'

    # Xóa những sản phẩm đã mua khỏi giỏ hàng
    if is_success and 'cart' in request.session:
        user_id = request.session.get('user_id')
        cart = request.session['cart']
        # Tìm những key đã được chọn mua
        keys_to_remove = [k for k, v in cart.items() if v.get('selected') != False]
        
        for k in keys_to_remove:
            item = cart[k]
            # Xóa trong session
            del cart[k]
            # Xóa trong cart_service (persistence)
            if user_id:
                try:
                    _cart_delete_item(
                        user_id=user_id,
                        product_id=item['id'],
                        product_type=item['type'],
                        size=item.get('size', '')
                    )
                except Exception: pass
        
        request.session['cart'] = cart
        request.session.modified = True

    return render(request, 'gateway/order_success.html', {
        'order_id': order_id,
        'payment_method': payment_method,
        'is_success': is_success,
    })


def my_orders_view(request):
    """Trang danh sách đơn hàng đã đặt của người dùng."""
    if not request.session.get('user_id'):
        return redirect('login')

    user_id = request.session.get('user_id')
    url = f"{ORDER_SERVICE_URL}orders/"
    orders = []
    try:
        resp = requests.get(url, params={'user_id': user_id}, timeout=5)
        if resp.status_code == 200:
            orders = resp.json()
    except Exception as e:
        print(f"Error fetching orders: {e}")

    return render(request, 'gateway/my_orders.html', {'orders': orders})


def my_order_detail_view(request, order_id):
    """Trang chi tiết đơn hàng đã đặt của người dùng."""
    if not request.session.get('user_id'):
        return redirect('login')

    url = f"{ORDER_SERVICE_URL}orders/{order_id}/"
    order = None
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            order = resp.json()
            # Ensure it belongs to the current user
            if str(order.get('user_id')) != str(request.session.get('user_id')):
                order = None
    except Exception as e:
        print(f"Error fetching order {order_id}: {e}")

    if not order:
        messages.error(request, 'Không tìm thấy đơn hàng hoặc bạn không có quyền truy cập.')
        return redirect('my_orders')

    return render(request, 'gateway/my_order_detail.html', {'order': order})


# ─────────────────────────────────────────────────────────────────────────────
# SHIPMENT SERVICE PROXY
# ─────────────────────────────────────────────────────────────────────────────

def shipment_list_api(request):
    """GET /api/shipments/?order_id=<id> – Lấy thông tin lô hàng theo đơn"""
    params = {}
    if request.GET.get('order_id'):
        params['order_id'] = request.GET['order_id']
    if request.GET.get('user_id'):
        params['user_id'] = request.GET['user_id']
    url = f"{SHIPMENT_SERVICE_URL}shipments/"
    try:
        resp = requests.get(url, params=params, timeout=5)
        return JsonResponse(resp.json(), status=resp.status_code, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def shipment_detail_api(request, shipment_id):
    """GET /api/shipments/<id>/ – Chi tiết lô hàng"""
    url = f"{SHIPMENT_SERVICE_URL}shipments/{shipment_id}/"
    try:
        resp = requests.get(url, timeout=5)
        return JsonResponse(resp.json(), status=resp.status_code, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def shipment_status_update_api(request, shipment_id):
    """
    PATCH /api/shipments/<id>/status/
    Body: { "status": "preparing"|"prepared"|"picked_up"|"in_transit"|"delivered"|"failed" }
    """
    if request.method != 'PATCH':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    user_id = request.session.get('user_id')
    role = str(request.session.get('role', 'customer')).lower()
    if not user_id:
        return JsonResponse({'error': 'Bạn cần đăng nhập.'}, status=401)
    
    if role not in ['staff', 'admin']:
        return JsonResponse({'error': 'Bạn không có quyền thực hiện thao tác này.'}, status=403)

    url = f"{SHIPMENT_SERVICE_URL}shipments/{shipment_id}/status/"
    try:
        body = json.loads(request.body)
        resp = requests.patch(url, json=body, timeout=5)
        return JsonResponse(resp.json(), status=resp.status_code, safe=False)
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Shipment Service không phản hồi.'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# REVIEW SERVICE PROXY
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
def review_list_create_api(request):
    """
    GET  /api/reviews/?product_id=X  – Lấy danh sách đánh giá
    POST /api/reviews/               – Gửi đánh giá mới
    """
    if request.method == 'GET':
        p_id = request.GET.get('product_id')
        try:
            resp = requests.get(REVIEW_SERVICE_URL, params={'product_id': p_id}, timeout=3)
            return JsonResponse(resp.json(), status=resp.status_code, safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    elif request.method == 'POST':
        user_id = request.session.get('user_id')
        if not user_id:
            return JsonResponse({'error': 'Bạn cần đăng nhập để đánh giá.'}, status=401)

        try:
            body = json.loads(request.body)
            body['user_id'] = user_id
            body['username'] = request.session.get('username', 'Khách hàng')
            resp = requests.post(REVIEW_SERVICE_URL, json=body, timeout=3)
            return JsonResponse(resp.json(), status=resp.status_code, safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


def shipper_dashboard_view(request):
    role = str(request.session.get('role', '')).lower()
    if role not in ['staff', 'admin']:
        return redirect('login')

    shipments = []
    orders_map = {}

    try:
        # Fetch shipments from shipment_service
        ship_resp = requests.get(f"{SHIPMENT_SERVICE_URL}shipments/", timeout=5)
        if ship_resp.status_code == 200:
            shipments = ship_resp.json()
            shipments.sort(key=lambda x: x.get('id', 0), reverse=True)
    except Exception as e:
        print(f"Error fetching shipments: {e}")

    try:
        # Fetch all orders to map customer and pricing details
        order_resp = requests.get(f"{ORDER_SERVICE_URL}orders/", timeout=5)
        if order_resp.status_code == 200:
            for order in order_resp.json():
                orders_map[str(order.get('id'))] = order
    except Exception as e:
        print(f"Error fetching orders: {e}")

    # Combine shipment with order receiver details
    for shipment in shipments:
        order_id = str(shipment.get('order_id'))
        order_info = orders_map.get(order_id, {})
        shipment['receiver_name'] = order_info.get('receiver_name', 'Khách hàng')
        shipment['receiver_phone'] = order_info.get('receiver_phone', '')
        shipment['receiver_address'] = order_info.get('receiver_address', '')
        shipment['total_price'] = order_info.get('total_price', 0)

    return render(request, 'gateway/shipper_dashboard.html', {
        'shipments': shipments
    })
