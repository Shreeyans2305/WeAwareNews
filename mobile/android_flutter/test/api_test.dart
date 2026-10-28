import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:weaware/api.dart';

void main() {
  test(
    'Feed requests preserve query encoding and decode published articles',
    () async {
      final api = Api(
        client: MockClient((request) async {
          expect(request.url.path, '/api/v1/articles');
          expect(request.url.queryParameters['q'], 'climate & policy');
          return http.Response(
            '{"articles":[{"id":"story-1","title":"A story"}],"total":1}',
            200,
          );
        }),
      );
      final result = await api.call('/articles?q=climate%20%26%20policy');
      expect(result['articles'][0]['id'], 'story-1');
    },
  );
  test('Research denial exposes useful server message', () async {
    final api = Api(
      client: MockClient(
        (_) async => http.Response(
          '{"detail":{"code":"no_access","message":"An invitation is required."}}',
          403,
        ),
      ),
    );
    expect(
      () => api.call('/sherlock/entitlement'),
      throwsA(
        predicate((e) => e.toString().contains('An invitation is required.')),
      ),
    );
  });
  test(
    'Authenticated endpoints reject guests before any network request',
    () async {
      final api = Api(
        client: MockClient((_) async {
          fail('Guest must not call private endpoint');
        }),
      );
      expect(
        () => api.call('/newsletters/preferences', authenticated: true),
        throwsA(predicate((e) => e.toString().contains('Sign in'))),
      );
    },
  );
}
