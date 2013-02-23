import requests

from stdlib.configs.localconf import MAIL_KEYS

MAILCHIMP = MAIL_KEYS['mailchimp']
MAILGUN = MAIL_KEYS['mailgun']

class Mailer(object):

    def __init__(self):
        pass

    def send_activation():
        pass

    @classmethod
    def sendmail(cls, sender, subject="", recipients=[],
                 msg="", format="text", method="mailgun"):
        lambduh = getattr(cls, method, cls.mailgun)
        try:
            return lambduh(sender, subject, recipients, msg, format)
        except:
            cls.mailgun(sender, subject, recipients, msg, format)

    @classmethod
    def mailchimp(cls):
        ms = MailSnake(MAILCHIMP['key'])
        print(ms.ping())

    @classmethod
    def mailgun(cls, sender, subject="", recipients=[],
                msg="", format="text"):
        """
        >>> from sendr_stdlib.api.v1.mail import Mailer;
        >>> r = Mailer.mailgun("email@org.com", subject="",
        ...                    recipients=["recipient@org.com"],
        ...                    msg="<p><strong>Salutations!</strong> What's going on?</p>", format="html")
        >>> r.text
        u'{\n  "message": "Queued. Thank you.",\n  "id": "<20120328062856.20096.24811@org.com>"\n}'
        
        """
        r = requests.\
            post(("https://api.mailgun.net/v2/" + MAILGUN['domain'] + "/"
                  "messages"),
                 auth=("api", MAILGUN['key']),
                 data={"from": sender,
                       "to": recipients,
                       "subject": subject,
                       format: msg
                       }
                 )
        return r
    
