"""QR login flow through the local API (prints the QR as a PNG file)."""

from pathlib import Path

from douyin_api.sdk import DouyinApiClient

OUT = Path(__file__).with_name("qr.png")

with DouyinApiClient("http://127.0.0.1:8787") as dy:
    start = dy.start_qr()
    OUT.write_bytes(dy.qr_image(start["qr_id"]))
    print(f"scan {OUT.resolve()} with the <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> app")
    print("qr_id:", start["qr_id"], "| expires in:", start["expires_in_seconds"], "s")

    # Poll until the phone confirms. Stop on any terminal state.
    terminal = {"confirmed", "expired", "cancelled", "failed"}
    while True:
        state = dy.qr_status(start["qr_id"])
        print("  status:", state["status"])
        if state["status"] in terminal:
            break

    print("session:", dy.session())
