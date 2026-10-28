"""Verify Gmail transport without sending real messages or starting cloud clients."""
import ast
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path
import unittest
from unittest.mock import patch

source = Path(__file__).parents[1] / 'api' / 'main.py'
tree = ast.parse(source.read_text())
helpers = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef)
                          and node.name in {'_send_newsletter_email', '_newsletter_delivery_ready'}], type_ignores=[])
scope = dict(os=os, smtplib=smtplib, ssl=ssl, EmailMessage=EmailMessage, formatdate=formatdate)
exec(compile(helpers, str(source), 'exec'), scope)
CONFIG = dict(NEWSLETTER_SMTP_USER='sender@gmail.com', NEWSLETTER_SMTP_PASSWORD='test password',
              NEWSLETTER_FROM_EMAIL='WeAware <sender@gmail.com>', NEWSLETTER_UNSUBSCRIBE_SECRET='secret',
              NEWSLETTER_API_ORIGIN='https://example.com', NEWSLETTER_DISPATCH_TOKEN='token')

class NewsletterDeliveryTests(unittest.TestCase):
    def test_configuration_requires_scheduler_and_provider(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(scope['_newsletter_delivery_ready']())
        with patch.dict(os.environ, CONFIG, clear=True):
            self.assertTrue(scope['_newsletter_delivery_ready']())
            del os.environ['NEWSLETTER_SMTP_PASSWORD']
            self.assertFalse(scope['_newsletter_delivery_ready']())

    @patch.dict(os.environ, CONFIG, clear=True)
    @patch('smtplib.SMTP_SSL')
    def test_private_recipient_and_tls(self, smtp_class):
        smtp = smtp_class.return_value.__enter__.return_value
        smtp.send_message.return_value = {}
        for recipient in ('first@example.com', 'second@example.com'):
            scope['_send_newsletter_email'](recipient, 'Briefing', '<p>News</p>', 'News',
                                            'https://example.com/unsubscribe', 'stable-key')
            call = smtp.send_message.call_args
            self.assertEqual(call.kwargs['to_addrs'], [recipient])
            message = call.args[0]
            self.assertEqual(message['To'], recipient)
            self.assertEqual(message['Reply-To'], CONFIG['NEWSLETTER_SMTP_USER'])
            self.assertIsNotNone(parsedate_to_datetime(message['Date']))
            self.assertEqual(message['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click')
            self.assertEqual(len(list(message.iter_parts())), 2)
            smtp.login.assert_called_with('sender@gmail.com', 'testpassword')
            self.assertEqual(smtp_class.call_args.args, ('smtp.gmail.com', 465))
            self.assertIsInstance(smtp_class.call_args.kwargs['context'], ssl.SSLContext)

    @patch.dict(os.environ, CONFIG, clear=True)
    @patch('smtplib.SMTP_SSL')
    def test_rejection_is_not_reported_as_success(self, smtp_class):
        smtp_class.return_value.__enter__.return_value.send_message.return_value = {'bad@example.com': (550, b'rejected')}
        with self.assertRaisesRegex(RuntimeError, 'rejected'):
            scope['_send_newsletter_email']('bad@example.com', 'Briefing', 'News', 'News', 'https://example.com', 'key')

if __name__ == '__main__':
    unittest.main()
