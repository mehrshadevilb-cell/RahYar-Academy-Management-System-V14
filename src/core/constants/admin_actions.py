"""
Action-name constants for `AdminLog.action`. Kept as plain strings (not a
DB enum) so new action types can be added without a migration - the
column is just an indexed `String(50)`.
"""

PRODUCT_TOGGLE = "product_toggle"
PRODUCT_PRICE_CHANGE = "product_price_change"
PRODUCT_PHOTO_CHANGE = "product_photo_change"
SPOTPLAYER_COURSE_ADD = "spotplayer_course_add"
SPOTPLAYER_COURSE_TOGGLE = "spotplayer_course_toggle"
CHANNEL_ADD = "channel_add"
CHANNEL_TOGGLE = "channel_toggle"
PAYMENT_CARD_ADD = "payment_card_add"

PAYMENT_APPROVE = "payment_approve"
PAYMENT_REJECT = "payment_reject"
LICENSE_RETRY = "license_retry"
ARTISTYAR_RETRY = "artistyar_retry"

ONLINE_COURSE_CREATE = "online_course_create"
ONLINE_COURSE_EDIT = "online_course_edit"
ONLINE_COURSE_TOGGLE = "online_course_toggle"
ONLINE_ENROLLMENT_CREATE = "online_enrollment_create"
RESERVATION_CONFIRM = "reservation_confirm"
RESERVATION_REJECT = "reservation_reject"
ATTENDANCE_MARK = "attendance_mark"

INSTALLMENT_MARK_PAID = "installment_mark_paid"

DISCOUNT_CODE_CREATE = "discount_code_create"
DISCOUNT_CODE_TOGGLE = "discount_code_toggle"

BROADCAST_SENT = "broadcast_sent"

REFERRAL_REWARD = "referral_reward"

SUPPORT_REPLY = "support_reply"
SUPPORT_CLOSE = "support_close"

AI_AGENT_RUN = "ai_agent_run"
