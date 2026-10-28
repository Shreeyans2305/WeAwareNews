import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:weaware/api.dart';
import 'package:weaware/main.dart';

void main() {
  testWidgets('Guest can navigate public and account-gated mobile screens', (
    tester,
  ) async {
    final api = Api(
      client: MockClient((request) async {
        if (request.url.path.endsWith('/topics')) {
          return http.Response('{"topics":["Science"]}', 200);
        }
        if (request.url.path.endsWith('/episodes')) {
          return http.Response('{"episodes":[]}', 200);
        }
        return http.Response('{"articles":[],"total":0}', 200);
      }),
    );
    await tester.pumpWidget(WeAwareApp(api: api));
    await tester.pumpAndSettle();
    expect(
      find.text('No stories found. Try another topic or search.'),
      findsOneWidget,
    );
    await tester.tap(find.byIcon(Icons.mail_outline));
    await tester.pumpAndSettle();
    expect(
      find.text('Sign in and verify your email to manage delivery.'),
      findsOneWidget,
    );
    await tester.tap(find.byIcon(Icons.travel_explore));
    await tester.pumpAndSettle();
    expect(find.text('Sign in to open your notebook'), findsOneWidget);
    await tester.tap(find.byTooltip('Appearance'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Dark'));
    await tester.pumpAndSettle();
    expect(appearance.value, ThemeMode.dark);
    appearance.value = ThemeMode.system;
  });
}
