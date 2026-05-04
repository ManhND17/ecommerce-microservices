import uuid
import hashlib
import hmac
from django.conf import settings
from urllib.parse import urlencode


def generate_vnpay_url(order_id: int, amount: float, txn_ref: str) -> str:
    """
    Tạo URL redirect sang cổng thanh toán VNPay.
    Toàn bộ cấu hình được đọc từ Django settings (load từ file .env).
    """
    vnpay_url = settings.VNPAY_URL
    tmn_code = settings.VNPAY_TMN_CODE
    hash_secret = settings.VNPAY_HASH_SECRET
    return_url = settings.VNPAY_RETURN_URL

    params = {
        'vnp_Version': '2.1.0',
        'vnp_Command': 'pay',
        'vnp_TmnCode': tmn_code,
        'vnp_Amount': int(amount * 100),  # VNPay tính theo đơn vị đồng (x100)
        'vnp_CurrCode': 'VND',
        'vnp_TxnRef': txn_ref,
        'vnp_OrderInfo': f'Thanh toan don hang #{order_id}',
        'vnp_OrderType': 'other',
        'vnp_Locale': 'vn',
        'vnp_ReturnUrl': return_url,
    }

    # Tạo chữ ký bảo mật HMAC-SHA512
    sorted_params = sorted(params.items())
    sign_data = urlencode(sorted_params)
    signature = hmac.new(
        hash_secret.encode('utf-8'),
        sign_data.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()
    params['vnp_SecureHash'] = signature

    return f"{vnpay_url}?{urlencode(sorted(params.items()))}"


def verify_vnpay_response(data: dict) -> bool:
    """
    Xác minh chữ ký từ VNPay Webhook/Return URL.
    Trả về True nếu chữ ký hợp lệ.
    """
    hash_secret = settings.VNPAY_HASH_SECRET
    received_hash = data.pop('vnp_SecureHash', '')
    params_to_verify = {k: v for k, v in data.items() if k != 'vnp_SecureHashType'}
    sorted_params = sorted(params_to_verify.items())
    sign_data = urlencode(sorted_params)
    expected_hash = hmac.new(
        hash_secret.encode('utf-8'),
        sign_data.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected_hash, received_hash)
