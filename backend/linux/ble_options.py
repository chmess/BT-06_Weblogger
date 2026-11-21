"""BlueZ discovery options shared by diagnostics and continuous reception."""


def scan_options(adapter):
    # Bleak otherwise sets DuplicateData=False. Repeated identical reports are
    # needed to distinguish a steady climate from a device that stopped sending.
    return {"adapter": adapter, "filters": {"DuplicateData": True}}
