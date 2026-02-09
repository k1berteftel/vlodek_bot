
def account_err_log(msg: str):
    with open('accounts.log', 'a', encoding='utf-8') as file:
        file.write(msg)