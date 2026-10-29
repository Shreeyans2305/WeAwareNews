import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';

/// A single account boundary shared by routes and the app's private API calls.
abstract class AccountAuth {
  User? get currentUser;
  Stream<User?> userChanges();
  Future<void> signIn(String email, String password);
  Future<String?> createAccount(String email, String password);
  Future<void> google();
  Future<void> signOut();
  Future<void> refresh();
  Future<void> verifyEmail();
  Future<void> resetPassword(String email);
}

class FirebaseAccountAuth implements AccountAuth {
  FirebaseAccountAuth({FirebaseAuth? firebase})
    : _firebase = firebase ?? FirebaseAuth.instance;
  final FirebaseAuth _firebase;
  static Future<void>? _googleInitialization;

  @override
  User? get currentUser => _firebase.currentUser;
  @override
  Stream<User?> userChanges() => _firebase.userChanges();
  @override
  Future<void> signIn(String email, String password) async {
    await _firebase.signInWithEmailAndPassword(
      email: email.trim(),
      password: password,
    );
  }

  @override
  Future<String?> createAccount(String email, String password) async {
    final result = await _firebase.createUserWithEmailAndPassword(
      email: email.trim(),
      password: password,
    );
    try {
      await result.user?.sendEmailVerification();
      return 'Account created. Check your email to verify your address.';
    } catch (_) {
      // Account creation already succeeded. Email delivery is a separate step.
      return 'Account created. Use Send verification email to retry verification delivery.';
    }
  }

  @override
  Future<void> google() async {
    const serverClientId = String.fromEnvironment('GOOGLE_WEB_CLIENT_ID');
    // The plugin requires initialize exactly once, including after cancel/retry.
    await (_googleInitialization ??= GoogleSignIn.instance.initialize(
      serverClientId: serverClientId.isEmpty ? null : serverClientId,
    ));
    final account = await GoogleSignIn.instance.authenticate();
    final token = account.authentication.idToken;
    if (token == null || token.isEmpty) {
      throw StateError('Google did not return an identity. Please try again.');
    }
    await _firebase.signInWithCredential(
      GoogleAuthProvider.credential(idToken: token),
    );
  }

  @override
  Future<void> signOut() async {
    await _firebase.signOut();
    if (_googleInitialization != null) {
      try {
        await GoogleSignIn.instance.signOut();
      } catch (_) {
        /* Firebase session is already cleared. */
      }
    }
  }

  @override
  Future<void> refresh() async {
    await currentUser?.reload();
    await currentUser?.getIdToken(true);
  }

  @override
  Future<void> verifyEmail() async {
    await currentUser?.sendEmailVerification();
  }

  @override
  Future<void> resetPassword(String email) =>
      _firebase.sendPasswordResetEmail(email: email.trim());
}

String accountError(Object error) {
  if (error is GoogleSignInException) {
    if (error.code == GoogleSignInExceptionCode.canceled) {
      return 'Google sign-in cancelled. You can try again.';
    }
    if (error.code == GoogleSignInExceptionCode.clientConfigurationError) {
      return 'Google sign-in configuration does not match this app. Please contact WeAware.';
    }
    return 'Google sign-in could not finish. Check your connection and try again.';
  }
  if (error is FirebaseAuthException) {
    return switch (error.code) {
      'invalid-email' => 'Enter a valid email address.',
      'invalid-credential' ||
      'wrong-password' ||
      'user-not-found' => 'The email or password is incorrect.',
      'email-already-in-use' =>
        'An account already uses this email. Sign in instead.',
      'weak-password' => 'Choose a password with at least six characters.',
      'network-request-failed' => 'Check your connection and try again.',
      'too-many-requests' => 'Too many attempts. Please wait and try again.',
      'user-disabled' => 'This account is disabled. Please contact WeAware.',
      _ => error.message ?? 'Sign-in could not finish. Please try again.',
    };
  }
  return error
      .toString()
      .replaceFirst('Exception: ', '')
      .replaceFirst('Bad state: ', '');
}
