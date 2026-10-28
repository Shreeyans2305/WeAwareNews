import Foundation

enum AppConfig {
    static var origin: String { (Bundle.main.object(forInfoDictionaryKey: "APIOrigin") as? String ?? "").trimmingCharacters(in: CharacterSet(charactersIn: "/")) }
    static var firebaseKey: String { Bundle.main.object(forInfoDictionaryKey: "FirebaseAPIKey") as? String ?? "" }
    static var googleClientID: String { Bundle.main.object(forInfoDictionaryKey: "GoogleClientID") as? String ?? "" }
}
struct APIError: LocalizedError { let message: String; var errorDescription: String? { message } }
struct API {
    static func data(_ path: String, method: String = "GET", body: [String: Any]? = nil, token: String? = nil) async throws -> Data {
        guard let url = URL(string: AppConfig.origin + path) else { throw APIError(message: "The API address is invalid.") }
        var request = URLRequest(url: url); request.httpMethod = method; request.timeoutInterval = 45
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body { request.httpBody = try JSONSerialization.data(withJSONObject: body); request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let response = response as? HTTPURLResponse, (200..<300).contains(response.statusCode) else {
            let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            let detail = json?["detail"]
            throw APIError(message: (detail as? String) ?? (detail as? [String: Any])?["message"] as? String ?? "The service could not complete this request. Please try again.")
        }
        return data
    }
    static func get<T: Decodable>(_ path: String, method: String = "GET", body: [String: Any]? = nil, token: String? = nil) async throws -> T {
        try JSONDecoder().decode(T.self, from: await data(path, method: method, body: body, token: token))
    }
    static func id(_ value: String) -> String { value.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? value }
}
