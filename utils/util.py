import email

def objectify_email(raw_email):
    return email.message_from_string(raw_email)

