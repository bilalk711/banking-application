# Abstract Classes; We don't have the `interface` keyword in Python so Abstract Classes help
# achieve the same functionality.

from typing import TypedDict
from enum import Enum

class UserProfile(TypedDict):
    id_card: str
    age: int
    is_active: bool

class TransactionType(Enum):
    TRANSFER_LOCAL= "TRANSFER_LOCAL"
    TRANSFER_INTERNATIONAL= "TRANSFER_INTERNATIONAL"
    WITHDRAW = "WITHDRAW"