import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';
import 'auth_service.dart';

const apiBase = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://weaware-api-777322408950.us-central1.run.app',
);
typedef Json = Map<String, dynamic>;

class Api {
  Api({http.Client? client, this.authReady = false, AccountAuth? accountAuth})
    : client = client ?? http.Client(),
      accountAuth = accountAuth ?? (authReady ? FirebaseAccountAuth() : null);
  final http.Client client;
  final bool authReady;
  final AccountAuth? accountAuth;
  User? get user => authReady ? accountAuth?.currentUser : null;
  Future<http.Response> response(
    String path, {
    String method = 'GET',
    Json? body,
    bool authenticated = false,
  }) async {
    final owner = user?.uid;
    final request = http.Request(method, Uri.parse('$apiBase/api/v1$path'));
    if (authenticated) {
      final token = await user?.getIdToken(true);
      if (token == null) throw Exception('Sign in to continue.');
      request.headers['Authorization'] = 'Bearer $token';
    }
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    final result = await client
        .send(request)
        .then(http.Response.fromStream)
        .timeout(const Duration(seconds: 35));
    if (authenticated && user?.uid != owner) {
      throw Exception('Account changed. Please retry.');
    }
    if (result.statusCode < 200 || result.statusCode >= 300) {
      dynamic detail;
      try {
        detail = jsonDecode(result.body)['detail'];
      } catch (_) {}
      throw Exception(
        detail is String
            ? detail
            : detail is Map
            ? detail['message'] ?? 'Request failed (${result.statusCode}).'
            : 'Request failed (${result.statusCode}). Please retry.',
      );
    }
    return result;
  }

  Future<Json> call(
    String path, {
    String method = 'GET',
    Json? body,
    bool authenticated = false,
  }) async =>
      jsonDecode(
            (await response(
              path,
              method: method,
              body: body,
              authenticated: authenticated,
            )).body,
          )
          as Json;
}
