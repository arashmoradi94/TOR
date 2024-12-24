async def get_torob_price(product_name: str, torob_key: str):
    # Implementation would depend on Torob's API or web scraping
    # This is a placeholder that would need to be implemented based on 
    # actual Torob API documentation or scraping requirements
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.torob.com/search?q={product_name}", 
                             headers={"Authorization": f"Bearer {torob_key}"}) as response:
            if response.status == 200:
                data = await response.json()
                return float(data["min_price"])
    return None
