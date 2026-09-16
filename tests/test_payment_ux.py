"""Regression tests for card-to-card payment confirmation UX helpers."""

from src.bot.keyboards.payment_keyboard import buy_keyboard, receipt_waiting_keyboard


def test_receipt_waiting_keyboard_has_cancel_and_confirm():
    markup = receipt_waiting_keyboard()
    callbacks = {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    }
    assert "pay_cancel" in callbacks
    assert "pay_confirm_paid" in callbacks


def test_buy_keyboard_unchanged_contract():
    markup = buy_keyboard(42)
    callbacks = {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    }
    assert "buy_42" in callbacks
    assert "discount_42" in callbacks
