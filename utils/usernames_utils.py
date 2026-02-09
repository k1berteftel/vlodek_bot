

def add_usernames(new_data: list[str], old_data: list[str]) -> list[str]:
    for username in new_data:
        if username not in old_data:
            old_data.append(username)
    if len(old_data) > 50:
        old_data = old_data[:50:]
    return old_data