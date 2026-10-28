import SwiftUI
import Security
import AuthenticationServices
import CryptoKit

@MainActor final class Account: NSObject, ObservableObject, ASWebAuthenticationPresentationContextProviding {
    struct User: Equatable { let id: String; let email: String; let verified: Bool }
    @Published private(set) var user: User?
    @Published private(set) var restoring = false
    @Published private(set) var notice = ""
    var email: String { user?.email ?? "" }
    var verified: Bool { user?.verified ?? false }
    var signedIn: Bool { user != nil }
    private let googleClientID: String
    private let googleBrowser: ((URL, String) async throws -> URL)?
    private let firebaseKey: String
    private let network: URLSession
    private let storage: SessionStore
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
    init(network: URLSession = .shared, storage: SessionStore = KeychainSessionStore(), firebaseKey: String = AppConfig.firebaseKey, googleClientID: String = AppConfig.googleClientID, googleBrowser: ((URL, String) async throws -> URL)? = nil, restore: Bool = true) {
        self.network = network; self.storage = storage; self.firebaseKey = firebaseKey; self.googleBrowser = googleBrowser; self.googleClientID = googleClientID
        super.init()
        guard restore else { return }
        restoring = true
        Task { await restoreSession() }
    }
    func restoreSession() async {
        let expected = generation
        restoring = true
        defer { restoring = false }
        do {
            guard let data = try storage.read(),
                  let json = try JSONSerialization.jsonObject(with: data) as? [String: String],
                  let refresh = json["refreshToken"], !refresh.isEmpty else { return }
            guard generation == expected else { return }
            refreshToken = refresh
            try await reload()
        } catch is CancellationError { }
        catch { if generation == expected { notice = error.localizedDescription } }
    }
    func firebase(_ operation: String, _ body: [String: Any]) async throws -> [String: Any] {
        guard !firebaseKey.isEmpty, !firebaseKey.hasPrefix("REPLACE") else { throw APIError(message: "Add your Firebase API key in Config.local.xcconfig to enable sign-in.") }
        let expected = generation
        let url = URL(string: "https://identitytoolkit.googleapis.com/v1/accounts:\(operation)?key=\(firebaseKey)")!
        let request = try FirebaseAuthRequest.make(url: url, body: body)
        let (data, response) = try await network.data(for: request)
        guard generation == expected else { throw CancellationError() }
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw APIError(message: (json["error"] as? [String: Any])?["message"] as? String ?? "Authentication failed.") }
        return json
    }
    private func completeSignIn(_ json: [String: Any]) async throws {
        guard let token = json["idToken"] as? String, !token.isEmpty,
              let refresh = json["refreshToken"] as? String, !refresh.isEmpty else {
            throw APIError(message: "The sign-in response was incomplete. Please try again.")
        }
        let expected = generation
        let profile = try await firebase("lookup", ["idToken": token])
        let nextUser = try Self.profile(profile)
        guard generation == expected else { throw CancellationError() }
        // Persist first. A failed Keychain write must not leave a half-signed-in account.
        try storage.save(JSONSerialization.data(withJSONObject: ["refreshToken": refresh]))
        idToken = token; refreshToken = refresh
        expires = Date().addingTimeInterval(TimeInterval(json["expiresIn"] as? String ?? "3600") ?? 3600).addingTimeInterval(-60)
        notice = ""; user = nextUser; generation = UUID()
    }
    private static func profile(_ json: [String: Any]) throws -> User {
        guard let profile = (json["users"] as? [[String: Any]])?.first,
              let id = profile["localId"] as? String, !id.isEmpty,
              let email = profile["email"] as? String, !email.isEmpty else {
            throw APIError(message: "Your account details could not be loaded. Please sign in again.")
        }
        return User(id: id, email: email, verified: profile["emailVerified"] as? Bool ?? false)
    }
    func signIn(email: String, password: String, register: Bool) async throws {
        notice = ""
        let result = try await firebase(register ? "signUp" : "signInWithPassword", ["email": email.trimmingCharacters(in: .whitespacesAndNewlines), "password": password, "returnSecureToken": true])
        try await completeSignIn(result)
        if register {
            do { try await verifyEmail() }
            catch { notice = "Account created. Verification email could not be sent; use Send verification email to retry." }
        }
    }
    func token() async throws -> String {
        if expires > Date() { return idToken }
        guard !refreshToken.isEmpty else { throw APIError(message: "Sign in to continue.") }
        let expected = generation
        let request = try FirebaseAuthRequest.make(
            url: URL(string: "https://securetoken.googleapis.com/v1/token?key=\(firebaseKey)")!,
            body: ["grant_type": "refresh_token", "refresh_token": refreshToken]
        )
        let (data, response) = try await network.data(for: request)
        guard generation == expected else { throw CancellationError() }
        let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        guard (response as? HTTPURLResponse)?.statusCode == 200,
              let token = json["id_token"] as? String else {
            let reason = (json["error"] as? [String: Any])?["message"] as? String ?? ""
            if ["TOKEN_EXPIRED", "INVALID_REFRESH_TOKEN", "USER_DISABLED", "USER_NOT_FOUND"].contains(reason) { signOut() }
            throw APIError(message: "Your session could not be refreshed. Please try again or sign in again.")
        }
        let refresh = json["refresh_token"] as? String ?? refreshToken
        try storage.save(JSONSerialization.data(withJSONObject: ["refreshToken": refresh]))
        idToken = token; refreshToken = refresh; expires = Date().addingTimeInterval(3500)
        return token
    }
    func reload() async throws {
        let expected = generation
        expires = .distantPast
        let token = try await token()
        let json = try await firebase("lookup", ["idToken": token])
        let nextUser = try Self.profile(json)
        guard generation == expected else { throw CancellationError() }
        let changedAccount = user?.id != nextUser.id
        user = nextUser; notice = ""
        if changedAccount { generation = UUID() }
    }
    func verifyEmail() async throws { _ = try await firebase("sendOobCode", ["requestType": "VERIFY_EMAIL", "idToken": token()]) }
    func reset(email: String) async throws { _ = try await firebase("sendOobCode", ["requestType": "PASSWORD_RESET", "email": email.trimmingCharacters(in: .whitespacesAndNewlines)]) }
    func signOut() {
        generation = UUID(); cancelGoogle(); user = nil
        idToken = ""; refreshToken = ""; expires = .distantPast; notice = ""
        do { try storage.delete() } catch { notice = error.localizedDescription }
    }
    func google() async throws {
        let expected = generation
        let client = googleClientID
        guard !client.isEmpty, !client.hasPrefix("REPLACE") else { throw APIError(message: "Configure the Google iOS client ID and callback scheme in Xcode to enable Google sign-in.") }
        let scheme = client.components(separatedBy: ".").reversed().joined(separator: ".")
        let redirect = "\(scheme):/oauthredirect"; let verifier = UUID().uuidString + UUID().uuidString
        let challenge = Data(SHA256.hash(data: Data(verifier.utf8))).base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
        let state = UUID().uuidString
        var components = URLComponents(string: "https://accounts.google.com/o/oauth2/v2/auth")!
        components.queryItems = ["client_id": client, "redirect_uri": redirect, "response_type": "code", "scope": "openid email profile", "code_challenge": challenge, "code_challenge_method": "S256", "state": state].map { URLQueryItem(name: $0.key, value: $0.value) }
        let callback: URL
        if let googleBrowser { callback = try await googleBrowser(components.url!, scheme) }
        else { callback = try await openGoogle(components.url!, scheme: scheme) }
        guard generation == expected else { throw CancellationError() }
        let items = URLComponents(url: callback, resolvingAgainstBaseURL: false)?.queryItems ?? []
        guard items.first(where: { $0.name == "state" })?.value == state, let code = items.first(where: { $0.name == "code" })?.value else { throw APIError(message: "Google sign-in could not be verified.") }
        var request = URLRequest(url: URL(string: "https://oauth2.googleapis.com/token")!); request.httpMethod = "POST"; request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        var form = URLComponents(); form.queryItems = ["client_id": client, "redirect_uri": redirect, "code": code, "code_verifier": verifier, "grant_type": "authorization_code"].map { URLQueryItem(name: $0.key, value: $0.value) }; request.httpBody = form.percentEncodedQuery?.data(using: .utf8)
        let (data, _) = try await network.data(for: request)
        guard generation == expected else { throw CancellationError() }
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any], let googleToken = json["id_token"] as? String else { throw APIError(message: "Google did not return a valid identity.") }
        var post = URLComponents(); post.queryItems = [URLQueryItem(name: "id_token", value: googleToken), URLQueryItem(name: "providerId", value: "google.com")]
        let result = try await firebase("signInWithIdp", ["postBody": post.percentEncodedQuery ?? "", "requestUri": "http://localhost", "returnSecureToken": true])
        try await completeSignIn(result)
    }
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor { UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.keyWindow }.first ?? ASPresentationAnchor() }
}
protocol SessionStore {
    func read() throws -> Data?
    func save(_ data: Data) throws
    func delete() throws
}
struct KeychainSessionStore: SessionStore {
    var service = "com.weaware.ios.session"
    private var query: [String: Any] { [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "firebase"] }
    func read() throws -> Data? {
        var request = query; request[kSecReturnData as String] = true; request[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(request as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else { throw failure(status) }
        return result as? Data
    }
    func save(_ data: Data) throws {
        let attributes: [String: Any] = [kSecValueData as String: data, kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        var status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            var item = query; attributes.forEach { item[$0.key] = $0.value }
            status = SecItemAdd(item as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw failure(status) }
    }
    func delete() throws {
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw failure(status) }
    }
    private func failure(_ status: OSStatus) -> APIError {
        APIError(message: "Secure session storage is unavailable (\(status)). Please reopen the app or install a correctly signed build.")
    }
}
