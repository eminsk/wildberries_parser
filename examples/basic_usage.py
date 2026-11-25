"""
Basic SDK usage example showing direct CDN card fetch, sharded feedbacks, and Excel export.
Run: uv run python examples/basic_usage.py
"""

from wb_parser import WBClient, calculate_feedback_shard, to_excel


def main() -> None:
    with WBClient(tracker_db="wb_prices.db") as client:
        # 1. Sync live basket-01..65+ shard ranges from cdn.wbbasket.ru
        count = client.sync_upstreams()
        print(f"Loaded {count} live WB basket shard routes.")

        # 2. Fetch product directly from wbbasket.ru CDN + sharded feedbacks1/2
        product = client.get_product("https://www.wildberries.ru/catalog/141217830/detail.aspx")
        shard = calculate_feedback_shard(product.root)
        print(f"Product: {product.name}")
        print(f"Root ID: {product.root} -> feedbacks{shard}.wb.ru")
        print(f"Reviews: {product.feedback_count} (rating {product.valuation})")
        print(f"Photos (.webp): {len(product.image_links)}")

        # 3. Export styled spreadsheet
        out = to_excel([product], "result/demo_wb.xlsx")
        print(f"Saved Excel report to {out}")


if __name__ == "__main__":
    main()
