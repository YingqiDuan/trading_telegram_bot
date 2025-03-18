# modal_app.py
from modal_functions import app


@app.local_entrypoint()
def main():
    print("Solana Block Processing App")
    print("Commands:")
    print("  modal run modal_app.py --latest [--max-blocks N]")
    print('  modal run modal_app.py --query "SQL query"')
    print("  modal run modal_app.py START_SLOT END_SLOT")
    print("  modal deploy modal_app.py")
    print("Optional: --timeout N (default 30 sec)")
    print("Scheduled task auto_fetch_latest_blocks runs every 20 seconds.")
