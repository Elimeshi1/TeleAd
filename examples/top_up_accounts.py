"""Top up every related account whose budget has fallen below a threshold.

    TELEGRAM_ADS_TOKEN=... python examples/top_up_accounts.py
"""

import os

from telead import Client, NotEnoughBudgetError

THRESHOLD = 50
TOP_UP_TO = 200

with Client(os.environ["TELEGRAM_ADS_TOKEN"]) as client:
    main = client.get_current_account()
    print(f"Main account: {main.remaining_budget} {main.currency}")

    for account in client.iter_related_accounts():
        if account.remaining_budget >= THRESHOLD:
            continue
        amount = TOP_UP_TO - account.remaining_budget
        try:
            # An idempotency key is attached automatically, so a retry after a
            # dropped connection never moves the money twice.
            pending = client.increase_account_budget(account.account_id, amount)
        except NotEnoughBudgetError:
            print("The main account has run out of budget.")
            break
        final = client.wait_for_transaction(pending)
        print(f"{account.title}: +{amount} {account.currency} -> {final.status}"
              + (f" ({final.error})" if final.error else ""))
