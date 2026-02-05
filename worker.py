def handler(event, _context):
    print("SQS_EVENT:", event)
    return {"ok": True}
