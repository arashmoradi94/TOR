from woocommerce import API
import aiohttp
from database.operations import get_user

async def get_woo_product_price(telegram_id: int, product_name: str):
    user = await get_user(telegram_id)
    if not user or not user.woo_key or not user.woo_secret:
        return None
        
    wcapi = API(
        url="your-woocommerce-site.com",
        consumer_key=user.woo_key,
        consumer_secret=user.woo_secret,
        version="wc/v3"
    )
    
    products = wcapi.get("products", params={"search": product_name}).json()
    if products:
        return float(products[0]["price"])
    return None
