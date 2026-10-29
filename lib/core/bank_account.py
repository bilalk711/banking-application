from __future__ import annotations

from decimal import Decimal
from threading import RLock

from ..constants.bank import SERVICE_FEES_BASIC
from .interfaces import TransactionType, UserProfile
from .money import Money, add_money, as_money


def _copy_profile(profile: UserProfile) -> UserProfile:
    if not isinstance(profile, dict):
        raise TypeError("Profile must be a dictionary")
    if not isinstance(profile.get("id_card"), str) or not profile["id_card"].strip():
        raise ValueError("Profile must have a non-empty id_card")
    age = profile.get("age")
    if isinstance(age, bool) or not isinstance(age, int) or age < 0:
        raise ValueError("Profile age must be a non-negative integer")
    if not isinstance(profile.get("is_active"), bool):
        raise ValueError("Profile is_active must be a boolean")
    return {
        "id_card": profile["id_card"],
        "age": age,
        "is_active": profile["is_active"],
    }


class BankAccountCore:
    def __init__(self, balance: Money, profile: UserProfile):
        self.__balance = as_money(balance, allow_zero=True)
        self.__userprofile = _copy_profile(profile)
        self.__lock = RLock()

    # Encapsulation: Only providing whats required for the user using Python name mangling, @property
    # and conventions; Python don't provides strict access modifiers such as `private`, `protected` and `public`
    @property
    def balance(self) -> Decimal:
        with self.__lock:
            return self.__balance

    @property
    def service_fee(self) -> Decimal:
        """Fee paid by this account for each outgoing transfer or withdrawal."""
        return Decimal("0.00")

    def _change_balance(self, amount: Money) -> None:
        """Apply a signed internal adjustment without allowing an overdraft."""
        adjustment = as_money(amount, allow_zero=True, allow_negative=True)
        with self.__lock:
            new_balance = add_money(self.__balance, adjustment)
            if new_balance < 0:
                raise ValueError("Insufficient balance")
            self.__balance = new_balance

    def set_userprofile(self, profile: UserProfile) -> str:
        validated_profile = _copy_profile(profile)
        with self.__lock:
            self.__userprofile = validated_profile
            return validated_profile["id_card"]

    def get_userprofile(self) -> UserProfile:
        with self.__lock:
            return self.__userprofile.copy()

    def _require_active(self) -> None:
        if not self.__userprofile["is_active"]:
            raise ValueError("Account is inactive")

    def deposit(self, amount: Money) -> bool:
        credit = as_money(amount)
        with self.__lock:
            self._require_active()
            self._change_balance(credit)
        return True

    def _debit_total(self, amount: Decimal, transaction_type: TransactionType) -> Decimal:
        if not isinstance(transaction_type, TransactionType):
            raise TypeError("transaction_type must be a TransactionType")
        fee = as_money(self.service_fee, allow_zero=True)
        return add_money(amount, fee)

    def transact(self, amount: Money, transaction_type: TransactionType) -> bool:
        """Debit an amount plus this account's outgoing service fee."""
        debit = self._debit_total(as_money(amount), transaction_type)
        with self.__lock:
            self._require_active()
            self._change_balance(debit.copy_negate())
        return True

    def transfer_to(
        self,
        recipient: BankAccountCore,
        amount: Money,
        transaction_type: TransactionType = TransactionType.TRANSFER_LOCAL,
    ) -> bool:
        """Validate and prepare both balances before applying an in-memory transfer."""
        if not isinstance(recipient, BankAccountCore):
            raise TypeError("Recipient must be a bank account")
        if recipient is self:
            raise ValueError("Sender and recipient must be different accounts")
        if not isinstance(transaction_type, TransactionType):
            raise TypeError("transaction_type must be a TransactionType")
        if transaction_type not in (
            TransactionType.TRANSFER_LOCAL,
            TransactionType.TRANSFER_INTERNATIONAL,
        ):
            raise ValueError("A transfer requires a transfer transaction type")

        credit = as_money(amount)
        debit = self._debit_total(credit, transaction_type)
        # Stable ordering also handles simultaneous transfers in opposite directions.
        first, second = sorted((self, recipient), key=id)
        with first.__lock, second.__lock:
            self._require_active()
            recipient._require_active()
            sender_balance = add_money(self.__balance, debit.copy_negate())
            if sender_balance < 0:
                raise ValueError("Insufficient balance for amount plus service fee")
            recipient_balance = add_money(recipient.__balance, credit)
            self.__balance = sender_balance
            recipient.__balance = recipient_balance
        return True

    def get_balance(self) -> Decimal:
        return self.balance

# Inheritance
class BankAccountBasic(BankAccountCore):
    # Polymorphism in Practice
    @property
    def service_fee(self) -> Decimal:
        return SERVICE_FEES_BASIC
