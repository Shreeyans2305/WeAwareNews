import SwiftUI
import Security
import AuthenticationServices
import CryptoKit

@MainActor final class Account: NSObject, ObservableObject, ASWebAuthenticationPresentationContextProviding {
    @Published var email = ""; @Published var verified = false; @Published var signedIn = false
    private var idToken = ""; private var refreshToken = ""; private var expires = Date.distantPast
    @Published private(set) var generation = UUID()
    private var session: ASWebAuthenticationSession?
    private var googleContinuation: CheckedContinuation<URL, Error>?
    private var googleTimeout: Task<Void, Never>?
    private var googleBrowserID: UUID?
    @Published private(set) var googleSigningIn = false

    private func finishGoogleBrowser(_ result: Result<URL, Error>) {
        guard let continuation = googleContinuation else { return }
        googleContinuation = nil
        googleBrowserID = nil
        googleTimeout?.cancel(); googleTimeout = nil
        googleSigningIn = false
        session = nil
        continuation.resume(with: result)
    }
    func cancelGoogle() {
        let activeSession = session
        finishGoogleBrowser(.failure(CancellationError()))
        activeSession?.cancel()
    }
    private func openGoogle(_ url: URL, scheme: String) async throws -> URL {
        guard googleContinuation == nil else { throw APIError(message: "Google sign-in is already open.") }
        return try await withCheckedThrowingContinuation { continuation in
            let browserID = UUID()
            googleBrowserID = browserID
            googleContinuation = continuation
            googleSigningIn = true
            let browser = ASWebAuthenticationSession(url: url, callbackURLScheme: scheme) { [weak self] url, error in
                Task { @MainActor in
                    guard self?.googleBrowserID == browserID else { return }
                    if let url { self?.finishGoogleBrowser(.success(url)) }
                    else if let authError = error as? ASWebAuthenticationSessionError, authError.code == .canceledLogin { self?.finishGoogleBrowser(.failure(CancellationError())) }
                    else { self?.finishGoogleBrowser(.failure(error ?? APIError(message: "Google sign-in was closed. Please try again."))) }
                }
            }
            session = browser
            browser.presentationContextProvider = self
            browser.prefersEphemeralWebBrowserSession = true
            guard browser.start() else {
                finishGoogleBrowser(.failure(APIError(message: "Could not open Google sign-in. Please try again.")))
                return
            }
            // A crashed system browser can omit its completion callback.
            googleTimeout = Task { [weak self] in
                do { try await Task.sleep(for: .seconds(180)) } catch { return }
                guard let self, self.googleBrowserID == browserID, self.googleContinuation != nil else { return }
                let activeSession = self.session
                self.finishGoogleBrowser(.failure(APIError(message: "Google sign-in did not finish. Close the browser and try again.")))
                activeSession?.cancel()
            }
        }
    }
    override init() { super.init(); if let data = Keychain.read(), let json = try? JSONSerialization.jsonObject(with: data) as? [String: String] { refreshToken = json["refreshToken"] ?? ""; Task { try? await reload() } } }
    func firebase(_ operation: String, _ body: [String: Any]) async throws -> [String: Any] {
        guard !AppConfig.firebaseKey.isEmpty, !AppConfig.firebaseKey.hasPrefix("REPLACE") else { throw APIError(message: "Add your Firebase API key in Config.local.xcconfig to enable sign-in.") }
        let expected = generation
        let url = URL(string: "https://identitytoolkit.googleapis.com/v1/accounts:\(operation)?key=\(AppConfig.firebaseKey)")!
        let request = try FirebaseAuthRequest.make(url: url, body: body)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard generation == expected else { throw CancellationError() }
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw APIError(message: (json["error"] as? [String: Any])?["message"] as? String ?? "Authentication failed.") }
        return json
    }
    private func accept(_ json: [String: Any]) throws {
        guard let token = json["idToken"] as? String, let refresh = json["refreshToken"] as? String else { throw APIError(message: "The sign-in response was incomplete.") }
        generation = UUID(); idToken = token; refreshToken = refresh; expires = Date().addingTimeInterval(3500)
        try Keychain.save(JSONSerialization.data(withJSONObject: ["refreshToken": refresh])); signedIn = true
    }
    func signIn(email: String, password: String, register: Bool) async throws {
        try accept(await firebase(register ? "signUp" : "signInWithPassword", ["email": email.trimmingCharacters(in: .whitespaces), "password": password, "returnSecureToken": true]))
        try await reload(); if register { try await verifyEmail() }
    }
    func token() async throws -> String {
        if expires > Date() { return idToken }
        guard !refreshToken.isEmpty else { throw APIError(message: "Sign in to continue.") }
        let expected = generation
        let request = try FirebaseAuthRequest.make(
            url: URL(string: "https://securetoken.googleapis.com/v1/token?key=\(AppConfig.firebaseKey)")!,
            body: ["grant_type": "refresh_token", "refresh_token": refreshToken]
        )
        let (data, response) = try await URLSession.shared.data(for: request)
        guard generation == expected else { throw CancellationError() }
        guard (response as? HTTPURLResponse)?.statusCode == 200, let json = try JSONSerialization.jsonObject(with: data) as? [String: Any], let token = json["id_token"] as? String else { signOut(); throw APIError(message: "Your session expired. Sign in again.") }
        idToken = token; expires = Date().addingTimeInterval(3500); signedIn = true
        if let refresh = json["refresh_token"] as? String { refreshToken = refresh; try Keychain.save(JSONSerialization.data(withJSONObject: ["refreshToken": refresh])) }
        return token
    }
    func reload() async throws { expires = .distantPast; let json = try await firebase("lookup", ["idToken": token()]); if let user = (json["users"] as? [[String: Any]])?.first { email = user["email"] as? String ?? ""; verified = user["emailVerified"] as? Bool ?? false; signedIn = true } }
    func verifyEmail() async throws { _ = try await firebase("sendOobCode", ["requestType": "VERIFY_EMAIL", "idToken": token()]) }
    func reset(email: String) async throws { _ = try await firebase("sendOobCode", ["requestType": "PASSWORD_RESET", "email": email]) }
    func signOut() { generation = UUID(); cancelGoogle(); idToken = ""; refreshToken = ""; email = ""; verified = false; signedIn = false; expires = .distantPast; Keychain.delete() }
    func google() async throws {
        let expected = generation
        let client = AppConfig.googleClientID
        guard !client.isEmpty, !client.hasPrefix("REPLACE") else { throw APIError(message: "Configure the Google iOS client ID and callback scheme in Xcode to enable Google sign-in.") }
        let scheme = client.components(separatedBy: ".").reversed().joined(separator: ".")
        let redirect = "\(scheme):/oauthredirect"; let verifier = UUID().uuidString + UUID().uuidString
        let challenge = Data(SHA256.hash(data: Data(verifier.utf8))).base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
        let state = UUID().uuidString
        var components = URLComponents(string: "https://accounts.google.com/o/oauth2/v2/auth")!
        components.queryItems = ["client_id": client, "redirect_uri": redirect, "response_type": "code", "scope": "openid email profile", "code_challenge": challenge, "code_challenge_method": "S256", "state": state].map { URLQueryItem(name: $0.key, value: $0.value) }
        let callback = try await openGoogle(components.url!, scheme: scheme)
        guard generation == expected else { throw CancellationError() }
        let items = URLComponents(url: callback, resolvingAgainstBaseURL: false)?.queryItems ?? []
        guard items.first(where: { $0.name == "state" })?.value == state, let code = items.first(where: { $0.name == "code" })?.value else { throw APIError(message: "Google sign-in could not be verified.") }
        var request = URLRequest(url: URL(string: "https://oauth2.googleapis.com/token")!); request.httpMethod = "POST"; request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        var form = URLComponents(); form.queryItems = ["client_id": client, "redirect_uri": redirect, "code": code, "code_verifier": verifier, "grant_type": "authorization_code"].map { URLQueryItem(name: $0.key, value: $0.value) }; request.httpBody = form.percentEncodedQuery?.data(using: .utf8)
        let (data, _) = try await URLSession.shared.data(for: request)
        guard generation == expected else { throw CancellationError() }
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any], let googleToken = json["id_token"] as? String else { throw APIError(message: "Google did not return a valid identity.") }
        var post = URLComponents(); post.queryItems = [URLQueryItem(name: "id_token", value: googleToken), URLQueryItem(name: "providerId", value: "google.com")]
        try accept(await firebase("signInWithIdp", ["postBody": post.percentEncodedQuery ?? "", "requestUri": "http://localhost", "returnSecureToken": true])); try await reload()
    }
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor { UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.keyWindow }.first ?? ASPresentationAnchor() }
}
enum Keychain {
    static let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "com.weaware.ios.session", kSecAttrAccount as String: "firebase"]
    static func read() -> Data? { var query = base; query[kSecReturnData as String] = true; query[kSecMatchLimit as String] = kSecMatchLimitOne; var result: CFTypeRef?; guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess else { return nil }; return result as? Data }
    static func save(_ data: Data) throws { delete(); var query = base; query[kSecValueData as String] = data; query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly; guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else { throw APIError(message: "Could not securely save the session.") } }
    static func delete() { SecItemDelete(base as CFDictionary) }
}
