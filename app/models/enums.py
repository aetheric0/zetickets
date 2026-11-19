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


class PaymentAttemptStatus(str, PyEnum):
    INITIALIZING = "INITIALIZING"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class PaymentEnvironment(str, PyEnum):
    TEST = "TEST"
    LIVE = "LIVE"


class WebhookAuthenticationStatus(str, PyEnum):
    UNVERIFIED = "UNVERIFIED"
    AUTHENTICATED = "AUTHENTICATED"
    REJECTED = "REJECTED"


class WebhookProcessingStatus(str, PyEnum):
    RECEIVED = "RECEIVED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class RefundStatus(str, PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"


class ReconciliationStatus(str, PyEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class ReconciliationDiscrepancyType(str, PyEnum):
    NONE = "NONE"
    STATUS_MISMATCH = "STATUS_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    MISSING_PROVIDER_RECORD = "MISSING_PROVIDER_RECORD"
    MISSING_INTERNAL_RECORD = "MISSING_INTERNAL_RECORD"
    REFUND_MISMATCH = "REFUND_MISMATCH"
    OTHER = "OTHER"
