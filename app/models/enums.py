from enum import Enum as PyEnum


class OrderStatus(str, PyEnum):
    PENDING = "PENDING"
    # Kept for rows created by the preserved initial migration. Their mapping
    # to the newer lifecycle is not known well enough to rewrite safely.
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
