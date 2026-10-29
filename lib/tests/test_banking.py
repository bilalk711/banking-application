from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, localcontext
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import UUID

from lib.core.bank_account import BankAccountBasic, BankAccountCore
from lib.core.interfaces import TransactionType
from lib.core.transaction import Transaction


def profile(id_card="sender", active=True):
    return {"id_card": id_card, "age": 25, "is_active": active}


class AccountTests(unittest.TestCase):
    def test_balance_is_read_only_and_inherited(self):
        account = BankAccountBasic(100, profile())
        self.assertEqual(account.balance, Decimal("100.00"))
        self.assertEqual(account.get_balance(), account.balance)
        with self.assertRaises(AttributeError):
            account.balance = 24
        self.assertEqual(account.balance, Decimal("100.00"))

    def test_deposits_credit_full_amount_even_below_fee(self):
        for cls in (BankAccountCore, BankAccountBasic):
            with self.subTest(account_type=cls):
                account = cls(100, profile())
                self.assertTrue(account.deposit(10))
                self.assertEqual(account.balance, Decimal("110.00"))

    def test_constructor_rejects_invalid_balances(self):
        for invalid in (
            True, False, "100", None, -1, 1.001,
            float("nan"), float("inf"), float("-inf"),
            Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"),
        ):
            with self.subTest(value=invalid), self.assertRaises((TypeError, ValueError)):
                BankAccountBasic(invalid, profile())
        self.assertEqual(BankAccountBasic(0, profile()).balance, Decimal("0.00"))

    def test_invalid_operations_do_not_mutate_balance(self):
        account = BankAccountBasic(1000, profile())
        operations = (
            account.deposit,
            lambda value: account.transact(value, TransactionType.WITHDRAW),
        )
        for operation in operations:
            for invalid in (
                True, "100", None, 0, -1, 0.001,
                float("nan"), float("inf"), Decimal("sNaN"),
            ):
                with self.subTest(value=invalid), self.assertRaises((TypeError, ValueError)):
                    operation(invalid)
                self.assertEqual(account.balance, Decimal("1000.00"))

    def test_decimal_arithmetic_is_exact(self):
        account = BankAccountCore(0.1, profile())
        account.deposit(0.2)
        self.assertEqual(account.balance, Decimal("0.30"))
        with localcontext() as context:
            context.prec = 3
            original = Decimal("123456789012345678901234567890.12")
            account = BankAccountCore(original, profile())
            account.deposit(Decimal("0.01"))
            account.transact(Decimal("0.01"), TransactionType.WITHDRAW)
            self.assertEqual(account.balance, original)

    def test_withdrawal_deducts_amount_and_fee(self):
        account = BankAccountBasic(550, profile())
        self.assertTrue(account.transact(500, TransactionType.WITHDRAW))
        self.assertEqual(account.balance, Decimal("0.00"))

    def test_insufficient_funds_include_fee(self):
        account = BankAccountBasic(549, profile())
        with self.assertRaises(ValueError):
            account.transact(500, TransactionType.WITHDRAW)
        self.assertEqual(account.balance, Decimal("549.00"))

    def test_internal_adjustments_cannot_overdraw(self):
        account = BankAccountBasic(100, profile())
        with self.assertRaises(ValueError):
            account._change_balance(-101)
        self.assertEqual(account.balance, Decimal("100.00"))

    def test_transaction_type_must_be_enum(self):
        account = BankAccountBasic(1000, profile())
        with self.assertRaises(TypeError):
            account.transact(100, "LOCAL_TRANSACTION")
        self.assertEqual(account.balance, Decimal("1000.00"))

    def test_profile_is_copied_on_input_and_output(self):
        supplied = profile()
        account = BankAccountBasic(100, supplied)
        supplied["id_card"] = "changed"
        returned = account.get_userprofile()
        returned["is_active"] = False
        self.assertEqual(account.get_userprofile(), profile())
        replacement = profile("replacement")
        self.assertEqual(account.set_userprofile(replacement), "replacement")
        replacement["id_card"] = "changed"
        self.assertEqual(account.get_userprofile()["id_card"], "replacement")

    def test_invalid_profiles_do_not_replace_existing_profile(self):
        account = BankAccountBasic(100, profile())
        for invalid in (
            None, {}, profile(""), profile(active="yes"),
            {**profile(), "age": True}, {**profile(), "age": -1},
        ):
            with self.subTest(value=invalid), self.assertRaises((TypeError, ValueError)):
                account.set_userprofile(invalid)
            with self.assertRaises((TypeError, ValueError)):
                BankAccountBasic(100, invalid)
            self.assertEqual(account.get_userprofile(), profile())

    def test_inactive_account_rejects_deposits_and_withdrawals(self):
        account = BankAccountBasic(1000, profile(active=False))
        with self.assertRaises(ValueError):
            account.deposit(100)
        with self.assertRaises(ValueError):
            account.transact(100, TransactionType.WITHDRAW)
        self.assertEqual(account.balance, Decimal("1000.00"))


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.sender = BankAccountBasic(5000, profile())
        self.recipient = BankAccountBasic(10000, profile("recipient"))

    def test_sender_pays_fee_recipient_gets_full_amount(self):
        transaction = Transaction(500, self.sender, self.recipient)
        self.assertFalse(transaction.committed)
        self.assertTrue(transaction.commit_transaction())
        self.assertTrue(transaction.committed)
        self.assertEqual(self.sender.balance, Decimal("4450.00"))
        self.assertEqual(self.recipient.balance, Decimal("10500.00"))

    def test_fee_comes_from_sender_account_type(self):
        sender = BankAccountCore(500, profile())
        Transaction(500, sender, self.recipient).commit_transaction()
        self.assertEqual(sender.balance, Decimal("0.00"))
        self.assertEqual(self.recipient.balance, Decimal("10500.00"))

    def test_repeated_commit_does_not_transfer_twice(self):
        transaction = Transaction(500, self.sender, self.recipient)
        transaction.commit_transaction()
        with self.assertRaises(ValueError):
            transaction.commit_transaction()
        self.assertEqual(self.sender.balance, Decimal("4450.00"))
        self.assertEqual(self.recipient.balance, Decimal("10500.00"))

    def test_transaction_ids_are_unique_and_read_only(self):
        first = Transaction(500, self.sender, self.recipient)
        second = Transaction(500, self.sender, self.recipient)
        self.assertNotEqual(first.transaction_id, second.transaction_id)
        self.assertEqual(UUID(first.transaction_id).version, 4)
        with self.assertRaises(AttributeError):
            first.transaction_id = second.transaction_id
        with self.assertRaises(AttributeError):
            first.committed = True

    def test_insufficient_funds_leave_both_accounts_unchanged(self):
        transaction = Transaction(5000, self.sender, self.recipient)
        with self.assertRaises(ValueError):
            transaction.commit_transaction()
        self.assertFalse(transaction.committed)
        self.assertEqual(self.sender.balance, Decimal("5000.00"))
        self.assertEqual(self.recipient.balance, Decimal("10000.00"))

    def test_failed_recipient_validation_does_not_debit_sender(self):
        self.recipient.set_userprofile(profile("recipient", active=False))
        transaction = Transaction(500, self.sender, self.recipient)
        with self.assertRaises(ValueError):
            transaction.commit_transaction()
        self.assertFalse(transaction.committed)
        self.assertEqual(self.sender.balance, Decimal("5000.00"))
        self.assertEqual(self.recipient.balance, Decimal("10000.00"))
        self.recipient.set_userprofile(profile("recipient"))
        self.assertTrue(transaction.commit_transaction())

    def test_failed_credit_calculation_does_not_debit_sender(self):
        from lib.core.money import add_money

        def fail_on_recipient_balance(left, right):
            if left == Decimal("10000.00"):
                raise ArithmeticError("Simulated credit failure")
            return add_money(left, right)

        transaction = Transaction(500, self.sender, self.recipient)
        with patch("lib.core.bank_account.add_money", side_effect=fail_on_recipient_balance):
            with self.assertRaises(ArithmeticError):
                transaction.commit_transaction()
        self.assertFalse(transaction.committed)
        self.assertEqual(self.sender.balance, Decimal("5000.00"))
        self.assertEqual(self.recipient.balance, Decimal("10000.00"))

    def test_inactive_sender_cannot_transfer(self):
        self.sender.set_userprofile(profile(active=False))
        with self.assertRaises(ValueError):
            Transaction(500, self.sender, self.recipient).commit_transaction()
        self.assertEqual(self.sender.balance, Decimal("5000.00"))
        self.assertEqual(self.recipient.balance, Decimal("10000.00"))

    def test_transaction_rejects_invalid_inputs(self):
        for amount in (True, "500", 0, -1, 0.001, float("nan"), float("inf")):
            with self.subTest(amount=amount), self.assertRaises((TypeError, ValueError)):
                Transaction(amount, self.sender, self.recipient)
        with self.assertRaises(TypeError):
            Transaction(500, self.sender, object())
        with self.assertRaises(ValueError):
            Transaction(500, self.sender, self.sender)
        with self.assertRaises(TypeError):
            Transaction(500, self.sender, self.recipient, "TRANSFER_LOCAL")
        with self.assertRaises(ValueError):
            Transaction(500, self.sender, self.recipient, TransactionType.WITHDRAW)

    def test_direct_transfer_validates_recipient_and_type(self):
        for recipient, transaction_type, error_type in (
            (object(), TransactionType.TRANSFER_LOCAL, TypeError),
            (self.sender, TransactionType.TRANSFER_LOCAL, ValueError),
            (self.recipient, "TRANSFER_LOCAL", TypeError),
            (self.recipient, TransactionType.WITHDRAW, ValueError),
        ):
            with self.subTest(recipient=recipient, transaction_type=transaction_type):
                with self.assertRaises(error_type):
                    self.sender.transfer_to(recipient, 500, transaction_type)
        self.assertEqual(self.sender.balance, Decimal("5000.00"))
        self.assertEqual(self.recipient.balance, Decimal("10000.00"))

    def test_international_transfer_uses_enum(self):
        transaction = Transaction(
            500, self.sender, self.recipient, TransactionType.TRANSFER_INTERNATIONAL
        )
        self.assertTrue(transaction.commit_transaction())
        self.assertEqual(self.sender.balance, Decimal("4450.00"))
        self.assertEqual(self.recipient.balance, Decimal("10500.00"))

    def test_concurrent_commits_only_apply_once(self):
        transaction = Transaction(500, self.sender, self.recipient)
        barrier = Barrier(8)

        def commit(_):
            barrier.wait(timeout=5)
            try:
                return transaction.commit_transaction()
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(commit, range(8)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.sender.balance, Decimal("4450.00"))
        self.assertEqual(self.recipient.balance, Decimal("10500.00"))

    def test_concurrent_transfers_cannot_overdraw_shared_sender(self):
        sender = BankAccountBasic(550, profile())
        recipients = [BankAccountBasic(0, profile(str(i))) for i in range(8)]
        barrier = Barrier(8)

        def commit(recipient):
            barrier.wait(timeout=5)
            try:
                Transaction(500, sender, recipient).commit_transaction()
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(commit, recipients))
        self.assertEqual(sum(results), 1)
        self.assertEqual(sender.balance, Decimal("0.00"))
        self.assertEqual(sum(account.balance for account in recipients), Decimal("500.00"))


if __name__ == "__main__":
    unittest.main()
