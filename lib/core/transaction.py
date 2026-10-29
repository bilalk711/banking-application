from threading import Lock
from uuid import uuid4

from .bank_account import BankAccountCore
from .interfaces import TransactionType
from .money import Money, as_money


class Transaction:
    def __init__(
        self,
        amount: Money,
        id1: BankAccountCore,
        id2: BankAccountCore,
        transaction_type: TransactionType = TransactionType.TRANSFER_LOCAL,
    ):
        if not isinstance(id1, BankAccountCore) or not isinstance(id2, BankAccountCore):
            raise TypeError("Sender and recipient must be bank accounts")
        if id1 is id2:
            raise ValueError("Sender and recipient must be different accounts")
        if not isinstance(transaction_type, TransactionType):
            raise TypeError("transaction_type must be a TransactionType")
        if transaction_type not in (
            TransactionType.TRANSFER_LOCAL,
            TransactionType.TRANSFER_INTERNATIONAL,
        ):
            raise ValueError("A transaction between accounts requires a transfer type")

        self.__id1 = id1
        self.__id2 = id2
        self.__amount = as_money(amount)
        self.__transaction_type = transaction_type
        self.__transaction_id = str(uuid4())
        self.__committed = False
        self.__lock = Lock()

    @property
    def transaction_id(self) -> str:
        return self.__transaction_id

    @property
    def committed(self) -> bool:
        with self.__lock:
            return self.__committed

    def commit_transaction(self) -> bool:
        with self.__lock:
            if self.__committed:
                raise ValueError("Transaction has already been committed")
            self.__id1.transfer_to(
                self.__id2, self.__amount, self.__transaction_type
            )
            self.__committed = True
        return True
