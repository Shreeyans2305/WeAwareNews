import SwiftUI

struct AccountView: View {
    @EnvironmentObject var account: Account
    @AppStorage("appearance") private var appearance = "system"
    @State private var email = ""; @State private var password = ""; @State private var register = false
    @State private var message = ""; @State private var busy = false
    var body: some View { Form {
        Section { NewsHeading(eyebrow: "Your reading room", title: "Account", subtitle: "Follow the reporting. Keep your preferences.") }
        if account.restoring {
            Section { ProgressView("Restoring your account…") }
        } else if account.signedIn {
            Section("Signed in") { Text(account.email); Label(account.verified ? "Email verified" : "Verify your email to use newsletters and Sherlock", systemImage: account.verified ? "checkmark.seal" : "envelope.badge")
                if !account.verified { Button("Send verification email") { run { try await account.verifyEmail(); message = "Verification email sent." } }; Button("I have verified my email") { run { try await account.reload(); message = account.verified ? "Email verified." : "Email is not verified yet." } } }
                Button("Sign out", role: .destructive) { account.signOut() }
            }
        } else {
            Section {
                Text(register ? "Create your WeAware account" : "Sign in to WeAware").font(.headline).accessibilityIdentifier("auth.mode.title")
                TextField("Email", text: $email).textContentType(.emailAddress).keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                SecureField("Password", text: $password).textContentType(register ? .newPassword : .password)
                Button(register ? "Create account" : "Sign in") { run { try await account.signIn(email: email, password: password, register: register) } }.disabled(email.isEmpty || password.count < 6 || busy)
                Button("Continue with Google") { run { try await account.google() } }.disabled(busy)
                Button(register ? "Already have an account? Sign in" : "Create an account") { register.toggle(); message = ""; password = "" }.disabled(busy).accessibilityIdentifier("auth.mode.switch")
                Button("Reset password") { run { try await account.reset(email: email); message = "Password reset requested. Check your inbox." } }.disabled(email.isEmpty)
            }
        }
        if !account.notice.isEmpty { Section { Text(account.notice).font(.callout) } }
        if busy { ProgressView(); if account.googleSigningIn { Button("Cancel Google sign-in") { account.cancelGoogle() } } }; if !message.isEmpty { Section { Text(message).font(.callout).textSelection(.enabled) } }
        Section("Appearance") { Picker("Theme", selection: $appearance) { Text("System").tag("system"); Text("Light").tag("light"); Text("Dark").tag("dark") } }
        Section("About WeAware") {
            Text("WeAware brings multiple reports together, keeping sources, differences and uncertainty in view so you can make up your own mind.")
            Text("AI helps cluster coverage, draft summaries and synthesize audio. Published articles and podcasts pass editorial review. Automated signals and summaries can contain errors; inspect the original reporting for important claims.").font(.footnote).foregroundStyle(.secondary)
            Link("Visit WeAware", destination: URL(string: AppConfig.siteOrigin)!)
        }
    }.navigationTitle("Account").buttonStyle(.borderless)
        .onChange(of: account.signedIn) { _, signedIn in if signedIn { register = false; password = ""; message = "" } }
    }
    func run(_ action: @escaping () async throws -> Void) { busy = true; message = ""; Task { do { try await action() } catch is CancellationError { message = "Sign-in cancelled. You can try again." } catch { message = error.localizedDescription }; busy = false } }
}
struct NewsletterView: View {
    @EnvironmentObject var account: Account
    @State private var topics: [String] = []; @State private var selected: Set<String> = []; @State private var cadence = "weekly"; @State private var consent = false; @State private var subscribed = false; @State private var busy = false; @State private var message = ""; @State private var deliveryReady = true
    var body: some View { Form {
        Section { NewsHeading(eyebrow: "Newsletters", title: "The Crosscheck", subtitle: "The stories you follow, delivered at your pace.") }
        if !account.signedIn || !account.verified { Section { Notice(text: "Sign in and verify your email in Account to manage email delivery.") } }
        else {
            Section("Topics") { ForEach(topics, id: \.self) { topic in Toggle(topic, isOn: Binding(get: { selected.contains(topic) }, set: { if $0 { selected.insert(topic) } else { selected.remove(topic) } })) } }
            Section("Delivery") { Picker("Frequency", selection: $cadence) { Text("Daily").tag("daily"); Text("Weekly").tag("weekly") }; Toggle("I agree to receive The Crosscheck by email. I can unsubscribe at any time.", isOn: $consent) }
            Section { Button(subscribed ? "Update subscription" : "Subscribe") { perform { _ = try await API.data("/api/v1/newsletters/preferences", method: "PUT", body: ["topics": Array(selected), "cadence": cadence, "consent": consent], token: account.token()); subscribed = true; message = "Preferences saved." } }.disabled(!consent || selected.isEmpty || selected.count > 20 || busy)
                if subscribed { Button("Send a test email") { perform { _ = try await API.data("/api/v1/newsletters/test", method: "POST", token: account.token()); message = "Test email accepted. Allow a few minutes for delivery." } }.disabled(busy || !deliveryReady); Button("Unsubscribe", role: .destructive) { perform { _ = try await API.data("/api/v1/newsletters/preferences/unsubscribe", method: "POST", token: account.token()); subscribed = false; consent = false; message = "You are unsubscribed." } }.disabled(busy) }
            }
            if !deliveryReady { Notice(text: "Email delivery is not currently configured on the server. Your preferences can still be saved.") }
        }
        if busy { ProgressView() }; if !message.isEmpty { Text(message).font(.callout) }
    }.navigationTitle("The Crosscheck").task(id: "\(account.generation)|\(account.verified)") { selected = []; subscribed = false; consent = false; message = ""; guard account.signedIn && account.verified else { return }; let expected = account.generation; perform { let result: Topics = try await API.get("/api/v1/topics"); topics = result.topics; let prefs: Preferences = try await API.get("/api/v1/newsletters/preferences", token: account.token()); guard expected == account.generation else { return }; selected = Set(prefs.topics); cadence = prefs.cadence; subscribed = prefs.subscribed; consent = prefs.subscribed; deliveryReady = prefs.deliveryReady ?? true } } }
    func perform(_ action: @escaping () async throws -> Void) { busy = true; message = ""; Task { do { try await action() } catch { message = error.localizedDescription }; busy = false } }
}
