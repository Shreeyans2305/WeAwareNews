import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:weaware/api.dart';
import 'package:weaware/discover.dart';

class MemoryDiscoveryStore implements DiscoveryStore {
  final Map<String, Json> scopes = {};
  @override
  Future<Json> read(String scope) async => scopes[scope] ?? {};
  @override
  Future<void> write(String scope, Json data) async {
    scopes[scope] = Map<String, dynamic>.from(
      jsonDecode(jsonEncode(data)) as Map,
    );
  }
}

void main() {
  test('Facts preserve qualifications, decimal numbers and attribution', () {
    final facts = articleFacts({
      'title': 'This headline must never become a made-up fact',
      'summary':
          'Dr. Rao said rates fell by 0.25 percentage points. The estimate remains provisional.',
      'body': [
        'Dr. Rao said rates fell by 0.25 percentage points.',
        'The estimate remains provisional.',
        'Officials have not confirmed when the measure will begin.',
        'This fourth point is not necessary for the compact card.',
      ],
    });
    expect(facts, [
      'Dr. Rao said rates fell by 0.25 percentage points.',
      'The estimate remains provisional.',
      'Officials have not confirmed when the measure will begin.',
    ]);
    expect(articleFacts({'title': 'No fabricated fallback'}), isEmpty);
  });

  test('Explicit factual briefs are used without generating extra claims', () {
    expect(
      articleFacts({
        'keyFacts': [
          'One supported point.',
          'One supported point.',
          'Another supported point.',
        ],
        'summary': 'A summary not needed when a brief is supplied.',
      }),
      ['One supported point.', 'Another supported point.'],
    );
  });

  final articles = List.generate(
    4,
    (index) => <String, dynamic>{
      'id': 'story-$index',
      'title': 'Reported story $index',
      'topic': 'Science',
      'summary':
          'The agency published its findings. Independent review is still pending.',
      'body': ['Researchers will release the full data next month.'],
      'consensus': 82,
      'sources': [
        {'outlet': 'Public agency', 'url': 'https://example.com/source'},
      ],
      'flaggedClaims': [],
    },
  );
  Api api() => Api(
    client: MockClient(
      (_) async =>
          http.Response(jsonEncode({'articles': articles, 'total': 4}), 200),
    ),
  );
  Widget page(
    Api api,
    MemoryDiscoveryStore store, {
    ValueChanged<Json>? onOpen,
  }) => MaterialApp(
    home: Scaffold(
      body: Discover(
        api: api,
        store: store,
        onOpen: onOpen ?? (_) {},
        onSignIn: () {},
      ),
    ),
  );

  testWidgets(
    'Save and skip survive reopening; buttons and undo match swipes',
    (tester) async {
      final store = MemoryDiscoveryStore();
      await tester.pumpWidget(page(api(), store));
      await tester.pumpAndSettle();
      expect(find.text('Reported story 0'), findsOneWidget);
      expect(find.text('82% consensus'), findsOneWidget);
      expect(find.text('Researchers will release the full data next month.'), findsOneWidget);
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();
      expect(find.text('Saved (1)'), findsOneWidget);
      expect(find.text('Reported story 1'), findsOneWidget);
      await tester.drag(find.byType(FactCard), const Offset(-220, 0));
      await tester.pumpAndSettle();
      expect(find.text('Reported story 2'), findsOneWidget);
      await tester.tap(find.text('Undo skip'));
      await tester.pumpAndSettle();
      expect(find.text('Reported story 1'), findsOneWidget);
      await tester.tap(find.text('Skip'));
      await tester.pumpAndSettle();
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      await tester.pumpWidget(page(api(), store));
      await tester.pumpAndSettle();
      expect(find.text('Saved (1)'), findsOneWidget);
      expect(find.text('Reported story 2'), findsOneWidget);
      expect(store.scopes['guest']!['skipped'], ['story-1']);
      await tester.tap(find.text('Skip'));
      await tester.pumpAndSettle();
      expect(find.text('Sign in for more stories'), findsOneWidget);
      expect(find.text('Reported story 3'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Saved stories can reopen the original reader', (tester) async {
    final store = MemoryDiscoveryStore();
    Json? opened;
    await tester.pumpWidget(
      page(api(), store, onOpen: (article) => opened = article),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Saved (1)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Reported story 0'));
    await tester.pumpAndSettle();
    expect(opened?['id'], 'story-0');
  });
}
