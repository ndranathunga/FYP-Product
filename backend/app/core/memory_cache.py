# backend/app/core/memory_cache.py
from cachetools import TTLCache

# For results: key = review_id, value = analysis result dict
analysis_result_cache = TTLCache(maxsize=10000, ttl=3600)  # 1 hour

# For stats: key = (user_id, org_id, product_id), value = stats dict
user_stats_cache = TTLCache(maxsize=1000, ttl=600)  # 10 mins
