from .bank_account import BankAccountBasic
from .transaction import Transaction


def main():
    usama_profile = {"id_card": "32423523", "age": 27, "is_active": True}
    awais_profile = {"id_card": "23412312", "age": 25, "is_active": True}
    usama_account = BankAccountBasic(5000, usama_profile)
    awais_account = BankAccountBasic(10000, awais_profile)

    transaction1 = Transaction(500, usama_account, awais_account)
    # Abstraction: We don't need to know how the transaction actually happens inside Transaction class
    transaction1.commit_transaction()
    print(awais_account.get_balance())
    print(usama_account.get_balance())


if __name__ == "__main__":
    main()
