import logging

# Configure logging for suspicious activity
logging.basicConfig(level=logging.WARNING)
security_logger = logging.getLogger("bank.security")