import Foundation

for host in ["identitytoolkit.googleapis.com", "securetoken.googleapis.com"] {
    let request = try FirebaseAuthRequest.make(url: URL(string: "https://\(host)/test?key=test-key")!, body: ["test": "value"], bundleID: "news.weaware.ios")
    precondition(request.value(forHTTPHeaderField: "X-Ios-Bundle-Identifier") == "news.weaware.ios")
    precondition(request.httpMethod == "POST")
    let body = try JSONSerialization.jsonObject(with: request.httpBody!) as! [String: String]
    precondition(body["test"] == "value")
}
for (address, bundle) in [("http://identitytoolkit.googleapis.com/test", "news.weaware.ios"), ("https://example.com/test", "news.weaware.ios"), ("https://securetoken.googleapis.com/test", "")] {
    do {
        _ = try FirebaseAuthRequest.make(url: URL(string: address)!, body: [:], bundleID: bundle)
        fatalError("Invalid authentication configuration accepted")
    } catch is APIError { }
}
print("Firebase request regression checks passed")
