"""Verify scheduled daily/weekly messages use the shared subject and design."""
import ast
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch
from backend.api.newsletter import render_newsletter, newsletter_subject

class NewsletterSubjectTests(TestCase):
    def test_ordinals_and_frequency(self):
        for day,suffix in [(1,'st'),(2,'nd'),(3,'rd'),(4,'th'),(11,'th'),(12,'th'),(13,'th'),(21,'st'),(22,'nd'),(23,'rd'),(28,'th'),(31,'st')]:
            for cadence in ['daily','weekly']:
                self.assertEqual(newsletter_subject(cadence,now=datetime(2026,10,day)),f'The Crosscheck {day}{suffix} October 2026 | {cadence.title()} Newsletter')
        self.assertEqual(newsletter_subject('daily',now=datetime(2026,10,27,20,tzinfo=timezone.utc)), 'The Crosscheck 28th October 2026 | Daily Newsletter')
        with self.assertRaises(ValueError):
            newsletter_subject('monthly')

class NewsletterScheduleTests(TestCase):
    def dispatch(self, article_rows):
        import os
        tree=ast.parse(Path('backend/api/main.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_dispatch_newsletters')
        send=MagicMock()
        scope=dict(os=os,hashlib=hashlib,timedelta=timedelta,logger=logging.getLogger(__name__),
                   _newsletter_delivery_ready=lambda:True,_newsletter_unsubscribe_token=lambda uid:uid+'-signed',
                   _ARTICLE_FIELDS='article_fields',_article_dict=lambda a:a,render_newsletter=render_newsletter,
                   newsletter_subject=newsletter_subject,_send_newsletter_email=send)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'dispatcher','exec'),scope)
        db=MagicMock();cursor=db.cursor.return_value
        due=datetime(2026,10,28,tzinfo=timezone.utc)
        cursor.fetchall.side_effect=[[
            ('daily-user','daily@example.com',['World'],'daily',due,None),
            ('weekly-user','weekly@example.com',['Climate'],'weekly',due,None),
        ],*article_rows]
        cursor.fetchone.side_effect=[(1,),(2,)]
        with patch.dict(os.environ,{'NEWSLETTER_API_ORIGIN':'https://example.com'}):
            result=scope['_dispatch_newsletters'](db)
        return result,send,cursor

    def test_due_subscribers_receive_matching_design_and_schedule(self):
        world=dict(id='world',title='World story',topic='World',image='https://example.com/world.jpg',summary='World summary')
        climate=dict(id='climate',title='Climate story',topic='Climate',image='https://example.com/climate.jpg',summary='Climate summary')
        result,send,cursor=self.dispatch([[world],[climate]])
        self.assertEqual(result,dict(status='ok',sent=2,failed=0))
        for call,cadence,article in zip(send.call_args_list,['daily','weekly'],[world,climate]):
            self.assertEqual(call.args[1],newsletter_subject(cadence))
            self.assertIn('The Crosscheck',call.args[2])
            self.assertIn(article['image'],call.args[2])
            self.assertIn(article['title'],call.args[2])
        queries=cursor.execute.call_args_list
        self.assertIn('unsubscribed_at IS NULL AND next_delivery_at <= NOW()',queries[0].args[0])
        topic_queries=[c for c in queries if 'LOWER(topic)=ANY' in c.args[0]]
        self.assertEqual(topic_queries[0].args[1],(['world'],None,1))
        self.assertEqual(topic_queries[1].args[1],(['climate'],None,7))
        updates=[c for c in queries if 'next_delivery_at=NOW() +' in c.args[0]]
        self.assertEqual(updates[0].args[1],(timedelta(days=1),'daily-user'))
        self.assertEqual(updates[1].args[1],(timedelta(days=7),'weekly-user'))

    def test_empty_period_does_not_send_fake_newsletter(self):
        result,send,_=self.dispatch([[],[]])
        self.assertEqual(result['sent'],0)
        send.assert_not_called()
