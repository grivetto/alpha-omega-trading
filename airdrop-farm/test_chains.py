import sys
sys.path.insert(0, "")

from chains import get_factory

print("=== Testing chain connections ===")
factory = get_factory("config.nuvola.yaml")
for chain in ["base", "scroll", "abstract", "linea", "monad", "hyperliquid"]:
    try:
        conn = factory.get_connector(chain)
        if chain == "hyperliquid":
            print(f"  ✅ {chain}: connected={conn.is_connected()}")
        else:
            print(f"  ✅ {chain}: connected={conn.is_connected()}, block={conn.get_block_number()}")
    except Exception as e:
        print(f"  ❌ {chain}: {e}")