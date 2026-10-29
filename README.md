# Banking core

Run from the parent `Banking Application` directory:

```powershell
python -m lib.core.main
python -m unittest discover -s lib/tests -v
```

## Money and fees

Balances and calculations use `Decimal` with two decimal places. Inputs accept
integers, floats (converted through their decimal string), and `Decimal` values.
Use `Decimal("0.10")` for exact decimal input. Strings, booleans, non-finite values,
negative balances, non-positive operation amounts, and fractional cents are rejected.

Deposits credit the full amount without a fee. Each outgoing transfer or withdrawal
charges the sender's service fee: 50.00 for `BankAccountBasic`, zero for the base
account. The sender must cover both the amount and fee. Local and international
transfers currently use the same fee and currency; no currency conversion occurs.

## Accounts and transfers

`balance` is read-only, and `get_balance()` remains available. Subclasses can use
`_change_balance()` for validated signed adjustments. Underscores express internal
access conventions; Python does not enforce private access against deliberate bypasses.

Profiles are validated and copied when stored and returned. Inactive accounts
cannot deposit, withdraw, send, or receive transfers.

Use `TransactionType` enum members for operations. `Transaction` accepts only
transfer types, assigns a unique UUID exposed by `transaction_id`, and exposes a
read-only `committed` flag. Committing twice raises `ValueError` without moving
money again. A failed transfer remains uncommitted and may be retried.

Transfers lock both accounts in a consistent order, validate their state, and
calculate both balances before applying either change. This provides atomic
transfers within this process. Accounts and commit state are currently in memory;
durability and protection across processes or restarts require database transactions
and persisted transaction IDs.
