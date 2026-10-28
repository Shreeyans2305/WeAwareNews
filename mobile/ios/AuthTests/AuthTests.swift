import XCTest
@testable import WeAware

final class MemorySessionStore: SessionStore {
    var data: Data?
    var rejectSave = false
    func read() throws -> Data? { data }
    func save(_ data: Data) throws {
        if rejectSave { throw APIError(message: "Simulated secure storage failure") }
        self.data = data
    }
    func delete() throws { data = nil }
}
final class AuthURLProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (Int, [String: Any]))?
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        do {
            let (status, json) = try Self.handler!(request)
            client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: try JSONSerialization.data(withJSONObject: json))
            client?.urlProtocolDidFinishLoading(self)
        } catch { client?.urlProtocol(self, didFailWithError: error) }
    }
    override func stopLoading() { }
}
@MainActor final class AuthTests: XCTestCase {
    func network() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [AuthURLProtocol.self]
        return URLSession(configuration: config)
    }
    func successResponses(_ request: URLRequest) throws -> (Int, [String: Any]) {
        XCTAssertEqual(request.value(forHTTPHeaderField: "X-Ios-Bundle-Identifier"), "news.weaware.ios")
        if request.url!.host == "securetoken.googleapis.com" {
            return (200, ["id_token": "refreshed-id", "refresh_token": "rotated-refresh"])
        }
        if request.url!.path.hasSuffix(":lookup") {
            return (200, ["users": [["localId": "test-user", "email": "auth-test@example.invalid", "emailVerified": true]]])
        }
        return (200, ["idToken": "initial-id", "refreshToken": "initial-refresh", "expiresIn": "3600"])
    }
    func testRealKeychainCanSaveUpdateReadAndDelete() throws {
        // Uses the simulator's real securityd, so missing signing entitlements fail this test.
        let store = KeychainSessionStore(service: "news.weaware.auth-tests.\(UUID().uuidString)")
        defer { try? store.delete() }
        try store.save(Data("first".utf8))
        XCTAssertEqual(try store.read(), Data("first".utf8))
        try store.save(Data("updated".utf8))
        XCTAssertEqual(try store.read(), Data("updated".utf8))
        try store.delete()
        XCTAssertNil(try store.read())
    }
    func testGoogleCallbackPersistsRealSessionAndRestoresProfile() async throws {
        let store = KeychainSessionStore(service: "news.weaware.google-tests.\(UUID().uuidString)")
        defer { try? store.delete() }
        AuthURLProtocol.handler = { [self] request in
            if request.url!.host == "oauth2.googleapis.com" {
                return (200, ["id_token": "test-google-identity"])
            }
            return try successResponses(request)
        }
        let account = Account(network: network(), storage: store, firebaseKey: "test-key", googleClientID: "test-client.apps.googleusercontent.com", googleBrowser: { url, scheme in
            let items = URLComponents(url: url, resolvingAgainstBaseURL: false)!.queryItems!
            XCTAssertEqual(items.first { $0.name == "code_challenge_method" }?.value, "S256")
            let state = items.first { $0.name == "state" }!.value!
            return URL(string: "\(scheme):/oauthredirect?code=test-code&state=\(state)")!
        }, restore: false)
        try await account.google()
        XCTAssertTrue(account.signedIn)
        XCTAssertEqual(account.email, "auth-test@example.invalid")
        XCTAssertNotNil(try store.read())
        let restored = Account(network: network(), storage: store, firebaseKey: "test-key", restore: false)
        await restored.restoreSession()
        XCTAssertEqual(restored.user, account.user)
        XCTAssertTrue(restored.signedIn)
        restored.signOut()
        XCTAssertNil(try store.read())
    }
    func testGoogleRejectsMismatchedCallbackState() async throws {
        let store = MemorySessionStore()
        let account = Account(network: network(), storage: store, firebaseKey: "test-key", googleClientID: "test-client.apps.googleusercontent.com", googleBrowser: { _, scheme in
            URL(string: "\(scheme):/oauthredirect?code=test-code&state=wrong-state")!
        }, restore: false)
        do { try await account.google(); XCTFail("Wrong OAuth state accepted") } catch { }
        XCTAssertFalse(account.signedIn)
        XCTAssertNil(store.data)
    }
    func testSignInPublishesProfileAndSurvivesAccountRestart() async throws {
        AuthURLProtocol.handler = successResponses
        let store = MemorySessionStore()
        let account = Account(network: network(), storage: store, firebaseKey: "test-key", restore: false)
        try await account.signIn(email: "auth-test@example.invalid", password: "not-a-real-password", register: false)
        XCTAssertTrue(account.signedIn)
        XCTAssertEqual(account.email, "auth-test@example.invalid")
        XCTAssertTrue(account.verified)
        let restored = Account(network: network(), storage: store, firebaseKey: "test-key", restore: false)
        await restored.restoreSession()
        XCTAssertTrue(restored.signedIn)
        XCTAssertEqual(restored.email, account.email)
        let restoredToken = try await restored.token()
        XCTAssertEqual(restoredToken, "refreshed-id")
        restored.signOut()
        XCTAssertFalse(restored.signedIn)
        XCTAssertEqual(restored.email, "")
        XCTAssertNil(store.data)
    }
    func testKeychainFailureDoesNotPublishPartialLogin() async throws {
        AuthURLProtocol.handler = successResponses
        let store = MemorySessionStore(); store.rejectSave = true
        let account = Account(network: network(), storage: store, firebaseKey: "test-key", restore: false)
        do {
            try await account.signIn(email: "auth-test@example.invalid", password: "not-a-real-password", register: false)
            XCTFail("A failed secure save must fail sign-in")
        } catch { XCTAssertTrue(error.localizedDescription.contains("storage failure")) }
        XCTAssertFalse(account.signedIn)
        XCTAssertEqual(account.email, "")
        XCTAssertNil(store.data)
        do { _ = try await account.token(); XCTFail("No partial token should remain") } catch { }
    }
    func testMissingProfileCannotProduceSignedInState() async throws {
        AuthURLProtocol.handler = { request in
            request.url!.path.hasSuffix(":lookup") ? (200, ["users": []]) : (200, ["idToken": "id", "refreshToken": "refresh"])
        }
        let store = MemorySessionStore()
        let account = Account(network: network(), storage: store, firebaseKey: "test-key", restore: false)
        do { try await account.signIn(email: "auth-test@example.invalid", password: "password", register: false); XCTFail("Missing profile accepted") } catch { }
        XCTAssertFalse(account.signedIn)
        XCTAssertNil(store.data)
    }
    func testRefreshNetworkFailureKeepsExistingAccount() async throws {
        AuthURLProtocol.handler = successResponses
        let account = Account(network: network(), storage: MemorySessionStore(), firebaseKey: "test-key", restore: false)
        try await account.signIn(email: "auth-test@example.invalid", password: "password", register: false)
        AuthURLProtocol.handler = { _ in throw URLError(.notConnectedToInternet) }
        do { try await account.reload(); XCTFail("Expected network failure") } catch { }
        XCTAssertTrue(account.signedIn)
        XCTAssertEqual(account.email, "auth-test@example.invalid")
    }
    func testInvalidRefreshClearsSession() async throws {
        AuthURLProtocol.handler = successResponses
        let store = MemorySessionStore()
        let account = Account(network: network(), storage: store, firebaseKey: "test-key", restore: false)
        try await account.signIn(email: "auth-test@example.invalid", password: "password", register: false)
        AuthURLProtocol.handler = { _ in (400, ["error": ["message": "INVALID_REFRESH_TOKEN"]]) }
        do { try await account.reload(); XCTFail("Expected rejected refresh") } catch { }
        XCTAssertFalse(account.signedIn)
        XCTAssertNil(store.data)
    }
}
