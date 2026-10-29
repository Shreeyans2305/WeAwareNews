import 'dart:async';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:weaware/api.dart';
import 'package:weaware/auth_service.dart';
import 'package:weaware/main.dart';

class TestUser extends Fake implements User {
  @override
  String get uid => 'test-reader';
  @override
  String get email => 'reader@example.invalid';
  @override
  bool get emailVerified => true;
}

class TestAuth implements AccountAuth {
  User? savedUser;
  final events = StreamController<User?>.broadcast();
  bool failGoogle = false;
  int googleCalls = 0;
  @override
  User? get currentUser => savedUser;
  @override
  Stream<User?> userChanges() async* {
    yield savedUser;
    yield* events.stream;
  }

  void publish(User? user) {
    savedUser = user;
    events.add(user);
  }

  @override
  Future<void> google() async {
    googleCalls++;
    if (failGoogle) throw FirebaseAuthException(code: 'network-request-failed');
    publish(TestUser());
  }

  @override
  Future<void> signIn(String email, String password) async {
    publish(TestUser());
  }

  @override
  Future<String?> createAccount(String email, String password) async {
    publish(TestUser());
    return 'Account created.';
  }

  @override
  Future<void> signOut() async {
    publish(null);
  }

  @override
  Future<void> refresh() async {
    events.add(savedUser);
  }

  @override
  Future<void> verifyEmail() async {}
  @override
  Future<void> resetPassword(String email) async {}
}

Widget account(TestAuth auth) => MaterialApp(
  home: Account(api: Api(authReady: true, accountAuth: auth)),
);
void main() {
  testWidgets(
    'Google success updates account and remains visible on route reopening',
    (tester) async {
      final auth = TestAuth();
      await tester.pumpWidget(account(auth));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('auth.google')));
      await tester.pumpAndSettle();
      expect(find.text('Signed in'), findsOneWidget);
      expect(find.text('reader@example.invalid'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(account(auth));
      await tester.pumpAndSettle();
      expect(find.text('reader@example.invalid'), findsOneWidget);
      await tester.tap(find.text('Sign out'));
      await tester.pumpAndSettle();
      expect(find.text('Sign in to WeAware'), findsOneWidget);
      expect(find.text('reader@example.invalid'), findsNothing);
    },
  );
  testWidgets(
    'Create account mode submits registration and clears stale form state',
    (tester) async {
      final auth = TestAuth();
      await tester.pumpWidget(account(auth));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('auth.mode')));
      await tester.pumpAndSettle();
      expect(find.text('Create your WeAware account'), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('auth.email')),
        'reader@example.invalid',
      );
      await tester.enterText(
        find.byKey(const Key('auth.password')),
        'fake-password',
      );
      await tester.tap(find.byKey(const Key('auth.submit')));
      await tester.pumpAndSettle();
      expect(find.text('Signed in'), findsOneWidget);
      expect(find.text('Account created.'), findsOneWidget);
    },
  );
  testWidgets(
    'External account restoration updates an already open account route',
    (tester) async {
      final auth = TestAuth();
      await tester.pumpWidget(account(auth));
      await tester.pumpAndSettle();
      auth.publish(TestUser());
      await tester.pumpAndSettle();
      expect(find.text('reader@example.invalid'), findsOneWidget);
    },
  );
  testWidgets('Failed Google attempt releases busy state and supports retry', (
    tester,
  ) async {
    final auth = TestAuth()..failGoogle = true;
    await tester.pumpWidget(account(auth));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('auth.google')));
    await tester.pumpAndSettle();
    expect(find.text('Check your connection and try again.'), findsOneWidget);
    auth.failGoogle = false;
    await tester.tap(find.byKey(const Key('auth.google')));
    await tester.pumpAndSettle();
    expect(auth.googleCalls, 2);
    expect(find.text('Signed in'), findsOneWidget);
  });
}
