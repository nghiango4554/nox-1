"""Marketing Hub services — module nghiệp vụ tách khỏi routes.

GA4 Analytics (Batch 2):
- ga4_config         : đọc state/ga4_config.json
- url_normalize      : normalize_landing_path() dùng chung GA4 × GSC
- ga4_client         : OAuth + Google Analytics Data API v1beta
- ga4_sync_service   : pull → upsert SQLite + sync run log
"""
