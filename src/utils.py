from uuid import uuid4

def generate_account_number():
    return uuid4().hex[:8].upper()