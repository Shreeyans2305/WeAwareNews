import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:weaware/auth_service.dart';

// Uses only the local Firebase Auth emulator. Run seed then restore with the
// same installed app via flutter drive --keep-app-running (flutter test uninstalls
// after completion). No production users or verification emails are created.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Native Firebase account persistence: seed or restore', (
    tester,
  ) async {
    await Firebase.initializeApp();
    final firebase = FirebaseAuth.instance;
    await firebase.useAuthEmulator('10.0.2.2', 9099);
    await firebase.authStateChanges().first;
    const phase = String.fromEnvironment(
      'AUTH_TEST_PHASE',
      defaultValue: 'seed',
    );
    const address = 'android-native-test@example.invalid';
    const password = 'local-emulator-test-password';
    final auth = FirebaseAccountAuth(firebase: firebase);
    if (phase == 'seed') {
      await firebase.signOut();
      final message = await auth.createAccount(address, password);
      expect(message, contains('Account created'));
      expect(firebase.currentUser?.email, address);
      await auth.signOut();
      expect(firebase.currentUser, isNull);
      await auth.signIn(address, password);
      expect(firebase.currentUser?.email, address);
    } else {
      expect(
        firebase.currentUser?.email,
        address,
        reason: 'Native Firebase must restore the user after process restart',
      );
      expect(await firebase.currentUser?.getIdToken(), isNotEmpty);
      await auth.signOut();
      expect(firebase.currentUser, isNull);
    }
  });
}
