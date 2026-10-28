import unittest
from datetime import datetime, timezone
from backend.api.newsletter import render_newsletter

class NewsletterTemplateTests(unittest.TestCase):
    def test_unsafe_content_and_links_are_escaped(self):
        article = dict(title='<script>bad</script>', summary='A & B', topic='World', image='javascript:bad',
                       sources=[dict(url='javascript:bad',outlet='Unsafe'),dict(url='https://example.com/story',outlet='A & B')],
                       flaggedClaims=[dict(claim='<img src=x>',reason='Unclear')])
        html,text = render_newsletter([article], 'daily', 'https://example.com/unsubscribe', now=datetime(2026,10,28,tzinfo=timezone.utc))
        self.assertNotIn('<script>',html)
        self.assertNotIn('javascript:',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('https://example.com/story',html)
        self.assertIn('The Crosscheck',html)
        self.assertIn('Worth a closer look',html)
        self.assertIn('A & B',text)
        self.assertIn('October 28, 2026',html)

    def test_edition_bounds_and_truthful_test_footer(self):
        html,text=render_newsletter([dict(title='Story',body=['Lead body'],summary='Summary')]*10,'weekly','https://example.com/unsubscribe',test=True)
        self.assertIn('Weekly edition',html)
        self.assertIn('8 stories',html)
        self.assertIn('one-time preview',text)
        self.assertEqual(text.count('Lead body'),1)
        self.assertLess(len(html.encode()),80000)
        with self.assertRaises(ValueError):
            render_newsletter([], 'daily', 'javascript:bad')

    def test_every_article_gets_its_own_image(self):
        articles = [dict(title=f'Story {i}', summary='Summary', image=f'https://images.example.com/{i}.jpg') for i in range(6)]
        html, _ = render_newsletter(articles, 'daily', 'https://example.com/unsubscribe')
        self.assertEqual(html.count('<img '), 6)
        for article in articles:
            self.assertIn(article['image'], html)
        articles[2]['image'] = 'javascript:bad'
        html, _ = render_newsletter(articles, 'daily', 'https://example.com/unsubscribe')
        self.assertEqual(html.count('<img '), 5)
        self.assertNotIn('javascript:', html)

    def test_source_urls_not_duplicated_in_plain_text(self):
        article = dict(title='Story', sources=[dict(outlet='Example',url='https://example.com/long-source-url',stance='agree')])
        html, text = render_newsletter([article], 'daily', 'https://example.com/unsubscribe')
        self.assertIn('https://example.com/long-source-url', html)
        self.assertNotIn('https://example.com/long-source-url', text)
        self.assertIn('Example (agree)', text)
        self.assertIn('Unsubscribe: https://example.com/unsubscribe', text)

    def test_known_blocked_image_has_credited_source_replacement(self):
        from backend.api.newsletter import IMAGE_REPLACEMENTS
        original, replacement = next(iter(IMAGE_REPLACEMENTS.items()))
        html, _ = render_newsletter([dict(title='Cyclone coverage',image=original)], 'daily', 'https://example.com/unsubscribe')
        self.assertNotIn(original, html)
        self.assertIn(replacement['url'], html)
        self.assertIn(replacement['credit'], html)

if __name__ == '__main__':
    unittest.main()
